# Parametric Monsoon Rainfall Trigger

Design and pricing of a US$ 10 M parametric cover on 30-day cumulative rainfall at
Singapore Changi over the Northeast Monsoon (Oct–Mar) — trigger calibration, burning
cost, basis-risk framing, climate-scenario repricing, and model validation against
45 years of observations.

Self-initiated work sample. See the [repository README](../README.md) for headline
results.

---

## Product

| Parameter | Value |
|---|---|
| Index | 30-day rolling cumulative rainfall (mm) |
| Reference station | Singapore Changi |
| Coverage period | 1 Oct – 31 Mar (NE monsoon) |
| Attachment | 500 mm / 30 days (~1-in-8 years, observed) |
| Exhaustion | 750 mm / 30 days (~1-in-46 years, observed) |
| Payout | Linear between attachment and exhaustion |
| Notional limit | US$ 10 M |

## What it demonstrates

- Index-based trigger design: return-period framing → threshold → payout function
- Burning-cost analysis and trigger-frequency estimation
- GEV fitting for return-period attribution of the attachment and exhaustion levels
- **Model validation against observed data, and acting on the result** — see below
- Bootstrap confidence intervals on burning cost
- Sensitivity to attachment and exhaustion levels, and to the generator's shape parameter
- Climate-scenario repricing under Clausius–Clapeyron intensity scaling (+2 °C, +4 °C)
- Indicative technical premium build-up

## The main finding is a negative one

A stochastic generator calibrated to monthly climatology gave a burning cost of
**2.65%**. Validated against the observed 45-year record, the true figure is **6.68%** —
an underestimate of 2.5×.

Sections 4a–4b diagnose it rather than patch it. The assumed Gamma shape parameters
(0.68–0.75, all < 1) disagree with MLE fits to observations (1.1–2.2, all > 1), and the
low shape had been silently compensating for the Bernoulli occurrence model's missing
wet-spell persistence (observed P(W|W) ≈ 0.85 vs P(W|D) ≈ 0.50). The shape-sensitivity
sweep confirms the mechanism: correcting the shape alone collapses the burning cost to
near zero, because the underlying persistence is still absent.

Conclusion carried into the pricing: use the observed burning cost as the baseline, with
a Markov-chain occurrence model as the production fix. The bootstrap 95% CI of
**1.83%–13.06%** is reported alongside — with 46 seasons, that width is what the data
honestly supports.

---

## Run it

Managed with **`uv`**.

```bash
uv sync                                          # creates .venv from uv.lock
uv run jupyter lab parametric_rainfall_trigger.ipynb
```

Re-execute headlessly:

```bash
uv run jupyter nbconvert --to notebook --execute parametric_rainfall_trigger.ipynb --inplace
```

Python 3.10+. Outputs are committed, so the notebook is fully readable without running it.

---

## Files

```
parametric-rainfall-trigger/
├── parametric_rainfall_trigger.ipynb   # the deliverable
├── pyproject.toml / uv.lock            # pinned environment
└── README.md
```

---

## Data provenance

- **Sections 1–3 use a synthetic daily rainfall series** — a Bernoulli occurrence plus
  Gamma intensity generator calibrated to Singapore MSS monthly means and wet-day
  fractions. Its limitations are the subject of sections 4a–4b.
- **Sections 4a onward use a real 45-year daily record** (Singapore Changi, 1980–2024),
  downloaded at runtime from the [Open-Meteo](https://open-meteo.com/) historical
  archive API (ERA5 reanalysis). No API key, no redistributed data — an internet
  connection is required to re-execute those cells.
- Trigger and payout parameters are set to make the basis-risk and sensitivity
  illustrations clear. They do not reflect any transacted contract.
