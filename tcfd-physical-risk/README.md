# TCFD Physical Risk Assessment — CLIMADA + OasisLMF

End-to-end TCFD physical risk assessment on a 20-asset Singapore S-REIT-style
portfolio (US$ 6.17bn TIV): pluvial flood hazard under three climate scenarios,
CLIMADA impact modelling, OEP/AEP loss curves, and a real OasisLMF financial-module
run.

Self-initiated work sample. See the [repository README](../README.md) for headline
results.

---

## What it demonstrates

- The full TCFD physical-risk chain: exposure → hazard → vulnerability → impact → financial
- Multi-scenario framing (current, +2 °C SSP2-4.5 ~2050, +4 °C SSP5-8.5 ~2100)
- CLIMADA impact computation on OED-schema exposure, with JRC depth–damage functions
- OEP / AEP exceedance-curve construction, and the difference between the two
- Per-asset AAL attribution — showing siting, not value, drives the concentration
- OasisLMF `generate_oasis_files()` producing the binary input set from OED exposure,
  and the generated `fm_profile` / `fm_policytc` binaries parsed back to recover the
  deductible hierarchy OasisLMF derived from `LocDed6All`
- A cross-check with something at stake: sections 8 and 8a reach that schedule by
  independent routes and agree exactly (gross AAL US$ 3,362,686 both ways). A mismatch
  would have exposed wrong OED terms or a bad aggregation-ID ordering
- Deductible and excess-of-loss treaty structures (ground-up / gross / ceded / net)
- **Section 8b — building the missing Oasis model files and running the real loss
  kernel.** `generate_oasis_files()` yields only the exposure side of an Oasis run;
  the model side (`footprint`, `vulnerability`, `damage_bin_dict`, `occurrence`,
  `events`) ships from the vendor. `oasis_model_builder.py` derives all five from
  the same CLIMADA hazard and depth–damage curve, then runs OasisLMF's own
  `evepy → modelpy → gulpy → summarypy → eltpy` over them
- A two-engine reconciliation where the residual is explained rather than waved at:
  Oasis returns a ground-up AAL 0.82% above CLIMADA, and a NumPy reconstruction of
  the binning predicts the kernel's figure **to the dollar**, pinning the gap on
  intensity discretisation. The residual narrows as bins refine but not
  monotonically, and the notebook says so instead of quoting the best resolution
- The finding that motivates building two vulnerability options: **AAL cannot see
  the assumption that drives the tail.** Point-mass and Beta-distributed damage
  give the same AAL to the dollar, while the 99.9th-percentile event loss differs
  by 72% and the largest sampled loss by 2.7x

## Results

| Scenario | AAL | AAL / TIV | 1-in-10 OEP | 1-in-100 OEP |
|---|---|---|---|---|
| Current | US$ 7,329,554 | 0.119% | US$ 19.4 M | US$ 53.5 M |
| +2 °C (SSP2-4.5, ~2050) | US$ 9,639,619 | 0.156% | US$ 22.6 M | US$ 60.2 M |
| +4 °C (SSP5-8.5, ~2100) | US$ 13,255,459 | 0.215% | US$ 32.0 M | US$ 67.8 M |

### Section 8b — Oasis kernel vs CLIMADA (current climate, ground-up)

| engine | AAL | vs CLIMADA |
|---|---|---|
| CLIMADA `ImpactCalc` | US$ 7,329,554 | — |
| Oasis kernel, point-mass damage | US$ 7,389,544 | +0.818% |
| Oasis kernel, Beta damage (cv 0.4) | US$ 7,389,543 | +0.818% |

A NumPy reconstruction of the binning reproduces the kernel's US$ 7,389,543.75
exactly (difference US$ 0.00), which is what identifies the residual as
intensity-bin discretisation rather than a modelling discrepancy.

Same models, sampled 1,000 times — where the two vulnerability assumptions part:

| | point-mass | Beta | ratio |
|---|---|---|---|
| AAL (analytical) | US$ 7,389,544 | US$ 7,389,543 | 1.00x |
| event loss SD | US$ 105,113 | US$ 4,627,697 | 44x |
| event loss p99 | US$ 53.8 M | US$ 66.2 M | 1.23x |
| event loss p99.9 | US$ 54.0 M | US$ 93.0 M | 1.72x |
| largest sampled loss | US$ 54.0 M | US$ 145.4 M | 2.69x |

---

## Run it

Managed with **`pixi`** rather than `uv`, because CLIMADA needs conda-forge
geospatial dependencies that do not install cleanly through pure-PyPI tooling.
Install pixi: <https://pixi.sh/latest/#installation>

```bash
pixi install                                       # solves from pixi.lock
pixi run jupyter lab tcfd_physical_risk_assessment.ipynb
```

Re-execute headlessly:

```bash
pixi run jupyter nbconvert --to notebook --execute tcfd_physical_risk_assessment.ipynb --inplace
```

> `osx-64` is the only platform pinned in `pixi.toml`. Add `osx-arm64` or `linux-64`
> and re-run `pixi install` if you are on another architecture.

---

## Files

```
tcfd-physical-risk/
├── tcfd_physical_risk_assessment.ipynb   # the deliverable
├── oasis_model_builder.py                # builds the Oasis model files (§8b)
├── data/
│   └── exposure_sreit.csv                # 20-asset synthetic exposure
├── oasis_demo/
│   ├── oed/                              # Open Exposure Data inputs (loc, acc)
│   └── keys/                             # hazard-to-area keys
├── pixi.toml / pixi.lock                 # pinned environment
└── README.md
```

`oasis_demo/oasis_files/` is not committed — it is generated when you run section 8a.
`oasis_runs/` likewise: section 8b writes a full Oasis run directory per
vulnerability option. Run the notebook in order, since 8b reuses the item,
coverage and financial-module binaries 8a produced.

> **macOS note.** `summarypy` writes through `select()` and raises on any
> exceptional file descriptor; macOS reports *regular files* as exceptional, so it
> can only write to a pipe there. `run_kernel()` routes it via `/dev/stdout`
> for that reason.

---

## Data provenance — please read

- **The exposure is synthetic.** `data/exposure_sreit.csv` is a hand-built portfolio,
  not a real S-REIT: placeholder accounts (`SREIT-01`…`SREIT-05`), generic building
  names, district-centroid coordinates, and round illustrative TIVs. It is designed to
  be *plausible* for Singapore — real districts, realistic Office / Retail / DataCentre
  / Logistics / Industrial mix — and OED-conformant so the pipeline runs end to end.
- **The flood hazard is synthetic**, generated to exercise the CLIMADA → OasisLMF chain.
  A production assessment would substitute a real hazard product (national flood maps,
  JBA, Fathom, or hydraulic modelling under CMIP6).
- **All assets use the commercial depth–damage curve** in this demo. A production run
  would assign occupancy-specific vulnerability functions per location.

The loss numbers therefore demonstrate method and judgement. They are not a calibrated
risk estimate for any real portfolio.
