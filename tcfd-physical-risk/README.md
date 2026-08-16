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
- OasisLMF `generate_oasis_files()` producing the full binary input set from OED,
  with the financial-module AAL reconciled against the analytical calculation
- Deductible and excess-of-loss treaty structures (ground-up / gross / ceded / net)

## Results

| Scenario | AAL | AAL / TIV | 1-in-10 OEP | 1-in-100 OEP |
|---|---|---|---|---|
| Current | US$ 7,329,554 | 0.119% | US$ 19.4 M | US$ 53.5 M |
| +2 °C (SSP2-4.5, ~2050) | US$ 9,639,619 | 0.156% | US$ 22.6 M | US$ 60.2 M |
| +4 °C (SSP5-8.5, ~2100) | US$ 13,255,459 | 0.215% | US$ 32.0 M | US$ 67.8 M |

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
├── data/
│   └── exposure_sreit.csv                # 20-asset synthetic exposure
├── oasis_demo/
│   ├── oed/                              # Open Exposure Data inputs (loc, acc)
│   └── keys/                             # hazard-to-area keys
├── pixi.toml / pixi.lock                 # pinned environment
└── README.md
```

`oasis_demo/oasis_files/` is not committed — it is generated when you run section 8a.

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
