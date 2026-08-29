# External dataset anchor (prototype-phase stretch)

Goal: calibrate the synthetic ablation generator against a public fraud dataset.

- PaySim (mobile-money fraud, ~6.3M rows) is the canonical public dataset, but the
  full CSV requires a (free) Kaggle login: https://www.kaggle.com/datasets/ealaxi/paysim1
- GitHub mirrors probed 2026-08-23: only script repos and a fraud-free 1000-row
  sub-sample found — not usable as a fraud anchor.
- USER-SIDE (2 min): download `PS_20174392719_1491204439457_log.csv` from Kaggle,
  drop it in this folder, then map amount/balance ratios to the generator ranges.
- Until then, the ablation stands on 200 seeded, feature-varied synthetic cases
  (see ../run.py) — honestly labeled as synthetic validation.
