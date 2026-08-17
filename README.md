# Physical Climate Risk — Sample Analyses

Two self-initiated, end-to-end notebooks in physical climate risk and parametric
insurance, built on open-source catastrophe modelling tooling (CLIMADA, OasisLMF).

Both notebooks are committed **with their outputs**, so every figure and table below
renders directly on GitHub — no environment setup needed to read them.

> **All portfolios and hazard layers here are synthetic.** Nothing in this repository
> derives from client, employer, or proprietary data. The one real dataset used is a
> public 45-year ERA5 rainfall record, downloaded at runtime from the Open-Meteo
> archive API. Details are stated in each notebook.

---

## 1. TCFD Physical Risk Assessment — CLIMADA + OasisLMF

[`tcfd-physical-risk/`](tcfd-physical-risk/) · [open the notebook](tcfd-physical-risk/tcfd_physical_risk_assessment.ipynb)

Pluvial flood risk to a 20-asset Singapore S-REIT-style portfolio (US$ 6.17bn TIV)
across three climate scenarios, from exposure through to disclosure-ready metrics.

| Scenario | AAL | AAL / TIV | 1-in-100 OEP |
|---|---|---|---|
| Current climate | US$ 7.33 M | 0.119% | US$ 53.5 M |
| +2 °C (SSP2-4.5, ~2050) | US$ 9.64 M | 0.156% | US$ 60.2 M |
| +4 °C (SSP5-8.5, ~2100) | US$ 13.26 M | 0.215% | US$ 67.8 M |

**Average annual loss rises 81% between the current climate and +4 °C**, and the
per-asset breakdown shows the driver is siting rather than value — the highest-AAL
asset carries 0.64% of TIV against a 0.119% portfolio average.

The division of labour between the two engines is explicit. **CLIMADA computes the
ground-up loss** — hazard → vulnerability → a per-asset, per-event impact matrix.
**OasisLMF supplies the financial structure**: `generate_oasis_files()` is run for real
against OED exposure, and the resulting binaries are parsed back to recover the
deductible schedule OasisLMF derived from `LocDed6All`.

That yields a cross-check with something at stake. Sections 8 and 8a reach the
deductible schedule by independent routes — one straight from the exposure table, the
other by parsing `fm_profile.bin` and `fm_policytc.bin` — and both return a gross AAL
of **US$ 3,362,686**, agreeing to zero. A mismatch would have meant the OED terms or
the aggregation-ID ordering was wrong.

Section 8b then runs the Oasis **loss kernel** itself. That normally needs vendor
model files — footprint, vulnerability, damage-bin dictionary, occurrence — which
`generate_oasis_files()` does not produce, so `oasis_model_builder.py` derives all of
them from the same CLIMADA hazard and depth–damage curve, and OasisLMF's own
`evepy → modelpy → gulpy → summarypy → eltpy` runs over them.

That makes the two engines directly comparable. Oasis returns a ground-up AAL of
**US$ 7,389,544** against CLIMADA's **US$ 7,329,554** — 0.82% apart. Rather than
attribute the gap to rounding and move on, the notebook reconstructs Oasis's binning
in NumPy and reproduces the kernel's figure **to the dollar**, which is what
establishes the residual as intensity discretisation and not a modelling error. The
residual narrows as bins refine but not monotonically, and the notebook reports that
instead of quoting the resolution that flatters it.

The reason for building two vulnerability treatments is the result they expose:
**AAL is blind to the assumption that drives the tail.** Point-mass and
Beta-distributed damage return the same AAL to the dollar, yet the 99.9th-percentile
event loss differs by 72% and the largest sampled loss by 2.7x. Two models agreeing
on the headline number would size a reinsurance layer or a capital buffer very
differently.

Covers: OED-format exposure · CLIMADA hazard, vulnerability and `ImpactCalc` ·
JRC depth–damage functions · OEP/AEP exceedance curves · deductible and XL treaty
structures · Oasis model-file construction and kernel execution · two-engine
reconciliation · TCFD / ISSB S2 disclosure framing.

---

## 2. Parametric Monsoon Rainfall Trigger

[`parametric-rainfall-trigger/`](parametric-rainfall-trigger/) · [open the notebook](parametric-rainfall-trigger/parametric_rainfall_trigger.ipynb)

Design and pricing of a US$ 10 M parametric cover on 30-day cumulative rainfall at
Singapore Changi over the Northeast Monsoon, attaching at 500 mm and exhausting at 750 mm.

**The most useful result in this notebook is a negative one.** A stochastic weather
generator calibrated to monthly climatology returned a burning cost of **2.65%**.
Validated against the observed 45-year record (ERA5, 1980–2024), the true burning cost
is **6.68%** — the model underestimated the risk by a factor of 2.5.

Sections 4a–4b diagnose why. The assumed Gamma shape parameters (0.68–0.75, all < 1)
disagree with MLE fits to observations (1.1–2.2, all > 1); the low shape was silently
compensating for the Bernoulli occurrence model's lack of wet-spell persistence
(observed P(W|W) ≈ 0.85 vs P(W|D) ≈ 0.50). A shape-sensitivity sweep confirms it:
correcting the shape without fixing the occurrence model drives the burning cost to
near zero. The recommendation is to price off the observed record, with a Markov-chain
occurrence model as the production fix.

A bootstrap 95% confidence interval of **1.83%–13.06%** is reported alongside — with
only 46 monsoon seasons, that width is the honest statement of what the data can support.

Covers: trigger and payout structure design · burning-cost analysis · GEV return-period
fitting · observed-vs-synthetic model validation · bootstrap uncertainty ·
attachment/exhaustion sensitivity · climate-scenario repricing under
Clausius–Clapeyron scaling · indicative technical premium.

---

## Running them

Each folder is independently reproducible and pins its own environment.

```bash
# 1. TCFD — pixi (CLIMADA needs conda-forge geospatial packages)
cd tcfd-physical-risk
pixi install
pixi run jupyter lab tcfd_physical_risk_assessment.ipynb

# 2. Parametric — uv
cd parametric-rainfall-trigger
uv sync
uv run jupyter lab parametric_rainfall_trigger.ipynb
```

The parametric notebook fetches its observed rainfall record at runtime from the
Open-Meteo archive API, so section 4a onwards needs an internet connection.
The saved outputs are already in the notebook if you would rather just read it.

---

## About

Built by **Dr. Liu Jiandong** — water resources and climate risk engineer, Singapore.
Ph.D. in climate and flood modelling (NUS); Willis Research Fellow at Willis Towers
Watson, 2018–2022; FRM Level 2 candidate.

Published as a work sample. The synthetic-data caveats above are load-bearing: these
demonstrate method and judgement, not calibrated risk estimates for any real portfolio.
