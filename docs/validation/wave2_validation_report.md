# Wave 2 Independent Validation Contract

Status: implemented validation interface; no model result is approved by this
document.

## Decision

The Validation role independently tests whether one Wave 2 PD prototype result
is internally reproducible and whether it can satisfy Gate 4. A passing
machine check would be evidence for review, not self-approval.

The UCI source used by this project has six within-record behavioral history
fields but no borrower-level observation timestamp. A stable borrower-ID split
can support a prototype holdout comparison, but it is not genuine
time-direction validation. The validator therefore returns `blocked` and
`gate_4_eligible: false` when `genuine_time_direction` is false, even if every
numerical check reconciles.

## Builder JSON contract

One JSON object with `schema_version: "1.0"` must contain:

- matching `run_id` / `model_run_id`
- matching `definition_version` / `model_definition_version`
- `validation_design`, including split fractions and explicit temporal flags
- `leakage_controls`, including a passed feature-timing review and passed checks
- `population`: exactly 30,000 unique borrowers assigned once to `train`,
  `calibration`, or `test`, with outcome and approved segment fields
- `models.static`, `models.behavioral`, and `models.combined`
- inside each model, matching run/version values, reported test metrics,
  reported segment summaries, and test-only row-level predictions

Population rows use:

```json
{
  "borrower_id": 1,
  "actual_default": 0,
  "split": "train",
  "sex_code": 2,
  "education_code": 2,
  "marriage_code": 1,
  "age_band": "30-39"
}
```

Each model prediction uses:

```json
{
  "borrower_id": 24001,
  "actual_default": 1,
  "predicted_pd": 0.4123,
  "split": "test"
}
```

Each reported segment row uses:

```json
{
  "segment_field": "age_band",
  "segment_value": "30-39",
  "sample_count": 2000,
  "default_count": 400,
  "default_rate": 0.2,
  "average_pd": 0.19,
  "brier_score": 0.15
}
```

## Independent calculations

`src/validation/wave2_validation.py` reconstructs, without importing Builder
code:

- 30,000 unique and exhaustive split assignments
- pairwise disjoint train, calibration, and test borrower populations
- identical and complete test-row coverage for all three models
- outcome equality between population and every prediction
- finite PD values in `[0, 1]` and no duplicate prediction IDs
- test sample count, target count, and target rate
- ROC AUC using rank statistics with tie handling and average-precision PR AUC
- Brier score and log loss
- ten fixed-width calibration bins and expected calibration error
- descriptive test calibration intercept and slope, labeled diagnostic-only
- static/behavioral/combined metric differences
- sex, education, marriage, age-band, and risk-band segment sample, outcome,
  average-PD, and Brier summaries
- exact run ID and model-definition-version consistency

Reported metrics and segment summaries are reconciled to independently
calculated values with an absolute tolerance of `1e-10`; the descriptive
test-calibration intercept/slope use the separately fixed `1e-6` tolerance.
The thresholds are part of the validation code; they are not inferred from the
Builder result.

## Run and interpretation

```bash
python -m src.validation.wave2_validation \
  --input outputs/qa/attempts/<attempt>/pd_prototype.json \
  --output outputs/qa/validated/<attempt>/wave2_validation.json
```

The command uses exclusive file creation and refuses to overwrite a prior
validation result.

- `pass`: all numerical and contract checks pass and genuine time direction is
  established. This still is not human approval.
- `blocked`: numerical checks can pass, but genuine time direction is
  unavailable.
- `fail`: at least one contract, identity, population, calculation, or reported
  value check fails.

## Current Gate 4 blocker

For the current UCI implementation, Gate 4 remains blocked until an eligible
borrower-level timestamp supports ordered train and test observation periods.
ID-hash holdout results must remain labeled `prototype`; they must not be
described as time-validated PD, IFRS 9 Stage, EAD, LGD, or ECL estimates.
