# Risk Component Scope

## Decision and permissible claim

Wave 2 may produce an explainable, retrospective PD prototype for internal
review. It may compare a static borrower model, a behavioral-signal model, and a
combined model. It may not claim a production PD model, genuine time-direction
validation, Gate 4 passage, or an IFRS 9 estimate.

The UCI source has one common borrower observation date (`2005-09-30`). Its
dataset-provided next-month default target supports discrimination and
calibration benchmarking only. It does not expose borrower origination dates,
multiple observation vintages, default-event dates, cure/recovery timing, or a
bank-approved default definition.

## Implemented PD prototype contract

Model definition version `0.2.0` uses:

| Model | Inputs | Explicit exclusions |
|---|---|---|
| Static | log credit limit, age, sex, education, marriage codes | target, IDs, dates, run/source metadata, risk points/band |
| Behavioral | seven approved Wave 1 signals | same exclusions |
| Combined | static and behavioral inputs | same exclusions |

Customer IDs are assigned with the stable SHA-256 contract
`customer_sha256_v1` to 60% train, 20% calibration, and 20% test populations.
This is a deterministic cross-sectional split, not a temporal or
pseudo-temporal split. Numeric imputation and standardization and categorical
encoding are fit on train rows only. Logistic parameters are fit on train rows;
Platt calibration is fit on the disjoint calibration rows; final metrics use
test rows only.

The output retains:

- source run, hash, observation date, model run, and definition version;
- all 30,000 borrower split assignments;
- test-row target, raw score, and calibrated PD for independent recomputation;
- ROC AUC, PR AUC, Brier score, log loss, expected calibration error;
- disjoint-set Platt fit parameters, test-only diagnostic calibration
  slope/intercept, and logistic feature coefficients;
- sex, education, marriage, age, and risk-band segment diagnostics.

`risk_band` is a diagnostic segment only. It is excluded from model features
because it derives from the same behavioral signals. `risk_points` is excluded
for the same reason. The next-month target is never present in a feature matrix.

## Gate 4 status

Gate 4 is blocked regardless of cross-sectional metric values because:

- `time_validation`: unavailable; one common observation date cannot establish
  out-of-time performance or drift;
- `sensitivity_direction`: unavailable; no approved macroeconomic variables or
  shock magnitudes exist;
- `calibration` and `segment_stability`: implemented as retrospective internal
  benchmark evidence but cannot substitute for time-direction evidence;
- `proxy_labels`: enforced below.

The PD packet therefore uses the status
`retrospective_internal_benchmark_only`. Independent validation must recompute
row-level metrics and preserve the blocked Gate 4 conclusion.

## Deferred components

| Component | Status | Reason and minimum additional evidence |
|---|---|---|
| Stage | Unimplemented; human approval required | Requires approved SICR/default rules, comparison to origination PD, cure rules, and staging governance |
| EAD | Unestimated | Requires eligible exposure, utilization/limit treatment, drawdown assumptions, and default timing |
| LGD | Unestimated | Requires recoveries, costs, collateral, discounting, and cash-flow timing |
| ECL | Unestimated | Requires approved PD horizon, Stage, EAD, LGD, scenarios, weights, and discounting |
| Scenario sensitivity | Deferred | Requires sourced or explicitly approved shock values and direction tests |

These are not zero-valued outputs. No placeholder numeric value is created.

## Known empirical cautions

Wave 1 found an inverse observed direction for recent bill growth and
non-monotonic zero-payment-streak buckets. Wave 2 preserves both signal values
without changing their definitions or hiding those contradictions. Model
coefficients describe associations in this public-data sample, not causal
effects.

## Reproduction

```bash
python -m src.models.run_pd_prototype \
  --database-url "dbname=credit_risk_lab host=/tmp port=55432" \
  --source-run-id W1-20260727-001 \
  --model-run-id W2-PD-20260727-001 \
  --generated-at 2026-07-27T00:00:00+09:00 \
  --output outputs/models/attempts/attempt_01/pd_prototype.json
```

The output path is exclusive-create. Re-execution must use a new attempt path;
validated evidence must never be overwritten.

## Language controls

Use: `PD prototype`, `retrospective internal benchmark`,
`cross-sectional holdout`, `public-data implementation`, and—only for a
separately approved future definition—`proxy` or `simulation`.

Do not use: `time-validated`, `official IFRS 9 model`, `production bank model`,
`approved Stage`, `estimated EAD/LGD/ECL`, or `regulatory-compliant
calculation`.
