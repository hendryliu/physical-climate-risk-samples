"""Build synthetic Oasis *model* files from CLIMADA objects, and run the real
Oasis loss kernel over them.

Why this module exists
----------------------
`generate_oasis_files()` produces only the **exposure-side** inputs of an Oasis
run — items, coverages, and the financial-module binaries derived from OED.  It
does not produce the **model-side** files, which in a commercial deployment ship
from the vendor:

    footprint.bin / .idx   hazard intensity per event, per area-peril
    vulnerability.bin      damage distribution per (vulnerability, intensity) bin
    damage_bin_dict.bin    the damage-ratio grid those distributions live on
    occurrence.bin         which events fall in which simulated period
    events.bin             the event set to process

Without them the Oasis kernel cannot run, which is why the notebook's earlier
sections compute losses in CLIMADA and use Oasis only for financial structure.
This module closes that gap: it derives the missing model files *from the same
CLIMADA hazard and vulnerability objects*, so the two engines can be run over
identical assumptions and reconciled.

That reconciliation is the point.  Agreement is not automatic — Oasis discretises
both hazard intensity and damage ratio onto bins, so the two engines converge
rather than match exactly, and the residual is a measurable function of bin
resolution (see `convergence_study`).

Two vulnerability treatments are provided:

    'degenerate'  all probability mass on the single damage bin containing the
                  CLIMADA mean damage ratio.  No damage uncertainty; reproduces
                  CLIMADA's deterministic MDR up to bin width.
    'beta'        a Beta distribution about that same mean.  Standard cat-model
                  practice.  The mean — and therefore AAL — is unchanged; what
                  changes is the spread, which is what drives sampled tail loss.

Platform note
-------------
`summarypy` writes through `select()` and raises on any exceptional descriptor.
macOS reports *regular files* as exceptional, so summarypy can only write to a
pipe here; `run_kernel` routes it through /dev/stdout for that reason.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

__all__ = [
    'ModelSpec', 'build_model', 'run_kernel', 'oasis_aal',
    'make_intensity_bins', 'make_damage_bins', 'make_footprint',
    'make_vulnerability', 'make_occurrence',
]

# Files that generate_oasis_files() already produced from the OED exposure.
# We reuse them unchanged, so the model files we build here meet the same
# item/coverage/area-peril numbering the OED pipeline established.
_OED_DERIVED = [
    'items.bin', 'coverages.bin', 'correlations.bin',
    'fm_programme.bin', 'fm_policytc.bin', 'fm_profile.bin', 'fm_xref.bin',
]
_OED_DERIVED_OPTIONAL = ['gul_summary_map.csv', 'fm_summary_map.csv']

_ITEMS_DTYPE = np.dtype([('item_id', 'i4'), ('coverage_id', 'u4'),
                         ('areaperil_id', 'u4'), ('vulnerability_id', 'i4'),
                         ('group_id', 'u4')])


class ModelSpec:
    """Resolution and shape of the synthetic model.

    intensity_width  hazard bin width, in the hazard's own units (m of flood depth)
    max_intensity    top of the intensity grid; must cover the hazard's maximum
    n_damage_bins    number of bins tiling (0, 1] damage ratio, plus an exact-zero bin
    cv               coefficient of variation for the 'beta' vulnerability option
    """

    def __init__(self, intensity_width=0.01, max_intensity=1.6,
                 n_damage_bins=1000, cv=0.4):
        self.intensity_width = intensity_width
        self.max_intensity = max_intensity
        self.n_damage_bins = n_damage_bins
        self.cv = cv

    def __repr__(self):
        return (f'ModelSpec(intensity_width={self.intensity_width}, '
                f'n_damage_bins={self.n_damage_bins}, cv={self.cv})')


# ---------------------------------------------------------------------------
# Model-file construction
# ---------------------------------------------------------------------------

def make_intensity_bins(spec: ModelSpec) -> pd.DataFrame:
    """Uniform hazard-intensity grid. Bin i covers ((i-1)w, iw], represented by
    its midpoint — the value the vulnerability function is evaluated at."""
    n = int(np.ceil(spec.max_intensity / spec.intensity_width))
    idx = np.arange(1, n + 1)
    w = spec.intensity_width
    return pd.DataFrame({'bin_index': idx,
                         'bin_from': (idx - 1) * w,
                         'bin_to': idx * w,
                         'interpolation': (idx - 0.5) * w})


def make_damage_bins(spec: ModelSpec) -> pd.DataFrame:
    """Damage-ratio grid. Bin 1 is the exact-zero bin Oasis expects; bins
    2..n+1 tile (0, 1].  `interpolation` is the bin's mean damage — the kernel
    uses it directly as bin_mean when computing the analytical mean loss."""
    edges = np.linspace(0.0, 1.0, spec.n_damage_bins + 1)
    rows = [(1, 0.0, 0.0, 0.0, 0)]
    rows += [(k + 2, edges[k], edges[k + 1], 0.5 * (edges[k] + edges[k + 1]), 0)
             for k in range(spec.n_damage_bins)]
    return pd.DataFrame(rows, columns=['bin_index', 'bin_from', 'bin_to',
                                       'interpolation', 'damage_type'])


def make_footprint(hazard, spec: ModelSpec) -> pd.DataFrame:
    """One area-peril per exposure location, matching the OED keys file.

    Probability 1.0 per (event, area-peril): the CLIMADA hazard is a single
    deterministic depth per location per event, so there is no intensity
    uncertainty to represent.  Locations with zero depth are omitted — absence
    from the footprint is how Oasis encodes 'not affected'.
    """
    dense = hazard.intensity.toarray()
    ev, loc = np.nonzero(dense)
    depth = dense[ev, loc]
    n_bins = int(np.ceil(spec.max_intensity / spec.intensity_width))
    bin_id = np.clip(np.ceil(depth / spec.intensity_width).astype(int), 1, n_bins)
    df = pd.DataFrame({'event_id': hazard.event_id[ev],
                       'areaperil_id': loc + 1,
                       'intensity_bin_id': bin_id,
                       'probability': 1.0})
    return df.sort_values(['event_id', 'areaperil_id']).reset_index(drop=True)


def make_vulnerability(int_bins, dmg_bins, impf_intensity, impf_mdd,
                       mode='degenerate', spec: ModelSpec | None = None,
                       vulnerability_id=1) -> pd.DataFrame:
    """Damage distribution over damage bins, for every intensity bin.

    The mean damage ratio at each intensity bin midpoint is read off the same
    depth-damage curve CLIMADA uses, so any disagreement downstream is
    discretisation, not a different vulnerability assumption.

    Oasis requires damage_bin_id to run contiguously from 1 within each
    (vulnerability_id, intensity_bin_id) group, so bins below the highest
    non-zero one are emitted with probability 0.
    """
    spec = spec or ModelSpec()
    mdr = np.interp(int_bins['interpolation'].values, impf_intensity, impf_mdd)
    interp = dmg_bins['interpolation'].values
    lo, hi = dmg_bins['bin_from'].values, dmg_bins['bin_to'].values
    bin_ids = dmg_bins['bin_index'].values

    rows = []
    for ibin, mu in zip(int_bins['bin_index'].values, mdr):
        if mode == 'degenerate' or mu <= 0:
            probs = np.zeros(len(dmg_bins))
            probs[int(np.argmin(np.abs(interp - mu)))] = 1.0
        elif mode == 'beta':
            sd = min(spec.cv * mu, 0.98 * np.sqrt(mu * (1 - mu)))
            common = mu * (1 - mu) / sd ** 2 - 1
            probs = stats.beta.cdf(hi, mu * common, (1 - mu) * common) - \
                stats.beta.cdf(lo, mu * common, (1 - mu) * common)
            probs[0] = 0.0                      # exact-zero bin carries no mass
            probs /= probs.sum()
        else:
            raise ValueError(f"mode must be 'degenerate' or 'beta', got {mode!r}")

        top = int(np.max(np.nonzero(probs > 1e-12)[0])) + 1
        p = probs[:top] / probs[:top].sum()
        rows.extend((vulnerability_id, int(ibin), int(bin_ids[k]), float(p[k]))
                    for k in range(top))

    return pd.DataFrame(rows, columns=['vulnerability_id', 'intensity_bin_id',
                                       'damage_bin_id', 'probability'])


def make_occurrence(event_ids, event_frequency, occ_per_event=3):
    """Assign events to simulated periods so the realised rate is *exact*.

    CLIMADA carries a per-event annual frequency f.  Oasis derives frequency
    from how often an event appears across N periods, so choosing
    N = occ_per_event / f makes the two rates identical by construction and
    removes frequency sampling as a source of disagreement.
    """
    n_periods = occ_per_event / event_frequency
    if abs(n_periods - round(n_periods)) > 1e-9:
        raise ValueError(
            f'{occ_per_event} occurrences at frequency {event_frequency} gives '
            f'{n_periods} periods, which is not an integer — pick another '
            f'occ_per_event so the rate is represented exactly.')
    n_periods = int(round(n_periods))

    rows = []
    for i, e in enumerate(event_ids):
        for j in range(occ_per_event):
            rows.append((int(e), ((occ_per_event * i + j) % n_periods) + 1,
                         2020, 1, 1 + (j % 27)))
    df = pd.DataFrame(rows, columns=['event_id', 'period_no', 'occ_year',
                                     'occ_month', 'occ_day'])
    return df.sort_values(['period_no', 'event_id']).reset_index(drop=True), n_periods


# ---------------------------------------------------------------------------
# Writing and running
# ---------------------------------------------------------------------------

def _sh(cmd, cwd):
    # bash explicitly: run_kernel relies on `set -o pipefail` to surface a failure
    # anywhere in the chain rather than only at the last stage.
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       cwd=str(cwd), executable='/bin/bash')
    if r.returncode != 0:
        raise RuntimeError(f'command failed: {cmd}\n\n'
                           f'{r.stdout[-2000:]}\n{r.stderr[-2000:]}')
    return r


def build_model(run_dir, hazard, impf_intensity, impf_mdd, oasis_files_dir,
                mode='degenerate', spec: ModelSpec | None = None,
                occ_per_event=3, work_dir='.', quiet=False):
    """Write a complete Oasis run directory and return a summary dict."""
    spec = spec or ModelSpec()
    run_dir = Path(run_dir)
    static, inp, csvd = run_dir / 'static', run_dir / 'input', run_dir / 'csv'
    for d in (static, inp, csvd):
        d.mkdir(parents=True, exist_ok=True)

    int_bins = make_intensity_bins(spec)
    dmg_bins = make_damage_bins(spec)
    fp = make_footprint(hazard, spec)
    vuln = make_vulnerability(int_bins, dmg_bins, impf_intensity, impf_mdd, mode, spec)
    occ, n_periods = make_occurrence(hazard.event_id, float(hazard.frequency[0]),
                                     occ_per_event)

    fp.to_csv(csvd / 'footprint.csv', index=False)
    vuln.to_csv(csvd / 'vulnerability.csv', index=False)
    dmg_bins.to_csv(csvd / 'damage_bin_dict.csv', index=False)
    occ.to_csv(csvd / 'occurrence.csv', index=False)
    pd.DataFrame({'event_id': hazard.event_id}).to_csv(csvd / 'events.csv', index=False)

    _sh(f'csvtobin footprint -i "{csvd}/footprint.csv" -o "{static}/footprint.bin" '
        f'-x "{static}/footprint.idx" -m {len(int_bins)} -n', work_dir)
    _sh(f'csvtobin vulnerability -i "{csvd}/vulnerability.csv" '
        f'-o "{static}/vulnerability.bin" -d {len(dmg_bins)}', work_dir)
    _sh(f'csvtobin damagebin -i "{csvd}/damage_bin_dict.csv" '
        f'-o "{static}/damage_bin_dict.bin"', work_dir)
    _sh(f'csvtobin occurrence -i "{csvd}/occurrence.csv" '
        f'-o "{inp}/occurrence.bin" -P {n_periods}', work_dir)
    _sh(f'csvtobin eve -i "{csvd}/events.csv" -o "{inp}/events.bin"', work_dir)

    src = Path(oasis_files_dir)
    for f in _OED_DERIVED:
        shutil.copy(src / f, inp / f)
    for f in _OED_DERIVED_OPTIONAL:
        if (src / f).exists():
            shutil.copy(src / f, inp / f)

    items = np.fromfile(inp / 'items.bin', dtype=_ITEMS_DTYPE)
    pd.DataFrame({'item_id': items['item_id'], 'summary_id': 1,
                  'summaryset_id': 1}).to_csv(csvd / 'gul_summary_xref.csv', index=False)
    # summarypy looks for 'gulsummaryxref.bin', not the csvtobin subcommand name
    _sh(f'csvtobin gul_summary_xref -i "{csvd}/gul_summary_xref.csv" '
        f'-o "{inp}/gulsummaryxref.bin"', work_dir)

    info = {'mode': mode, 'spec': spec, 'n_periods': n_periods,
            'occ_per_event': occ_per_event, 'n_intensity_bins': len(int_bins),
            'n_damage_bins': len(dmg_bins), 'footprint_rows': len(fp),
            'vulnerability_rows': len(vuln), 'run_dir': run_dir}
    if not quiet:
        print(f"built {mode:11s} | {len(int_bins):4d} intensity bins, "
              f"{len(dmg_bins):5d} damage bins | footprint {len(fp):,} rows, "
              f"vulnerability {len(vuln):,} rows | {n_periods} periods")
    return info


def run_kernel(run_dir, sample_size=0, alloc_rule=0, work_dir='.', tag=''):
    """evepy -> modelpy -> gulpy -> summarypy -> eltpy, returning the SELT.

    summarypy must write to a pipe (see module docstring), hence /dev/stdout.
    """
    run_dir = Path(run_dir)
    selt = run_dir / f'selt_S{sample_size}{tag}.csv'
    _sh(f'set -o pipefail; '
        f'evepy 1 1 -i "{run_dir}/input/events.bin" '
        f'| modelpy -r "{run_dir}" '
        f'| gulpy -S {sample_size} -a {alloc_rule} --run-dir "{run_dir}" '
        f'| summarypy -t gul -p "{run_dir}/input" -1 /dev/stdout '
        f'| eltpy -i - -s "{selt}"', work_dir)
    return pd.read_csv(selt)


def oasis_aal(selt, n_periods, occ_per_event, unit_scale=1000.0):
    """Average annual loss from the analytical-mean rows of a SELT.

    SELT losses inherit OED units ($k by default), hence unit_scale.
    """
    mean_rows = selt[selt.SampleId == -1]
    return mean_rows.Loss.sum() * unit_scale * occ_per_event / n_periods
