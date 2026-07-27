# Data Dictionary

## Definition rules

Each field or feature must include:

- canonical name
- business meaning
- source field or transformation
- table grain
- data type and allowed values
- observation timing
- missing-value rule
- leakage risk
- validation query
- definition version

## Initial tables

| Table | Grain | Purpose | Status |
|---|---|---|---|
| `raw.credit_card_client` | one row per customer | insert-only source representation with file/run provenance | Implemented and Gate 1 validated |
| `core.borrower` | one row per run/customer | fixed borrower/account attributes and source outcome | Implemented and Gate 2 validated |
| `core.account_month` | one row per run/customer/month offset | repayment, bill, and payment history | Implemented and Gate 2 validated |
| `mart.borrower_risk_signal` | one row per run/customer | seven explainable signals and rule-based band | Implemented and Gate 3 validated |
| `mart.signal_default_summary` | one row per run/signal/bucket | observed outcome counts and rates | Implemented and Gate 3 validated |
| `mart.risk_band_summary` | one row per run/risk band | observed outcome counts and rates | Implemented and Gate 3 validated |
| `audit.test_result` | one row per run/test | quality, warning, and business-flag evidence | Implemented |
| `audit.reconciliation_result` | one row per run/reconciliation | source/derived values and difference | Implemented |

## Core fields

| Field | Meaning and source | Timing / allowed values | Missing rule | Validation |
|---|---|---|---|---|
| `core.borrower.customer_id` | source `ID` | run snapshot key | not null | DQ-001, DQ-014 |
| `credit_limit_ntd` | source `LIMIT_BAL`, NTD | fixed at source observation | not null; positive test | DQ-008 |
| `sex_code` | source `SEX` | UCI documents 1–2 | preserve, do not recode | DQ-013 |
| `education_code` | source `EDUCATION` | UCI documents 1–4; source also contains other values | preserve and warn | DQ-016 |
| `marriage_code` | source `MARRIAGE` | UCI documents 1–3; source also contains 0 | preserve and warn | DQ-017 |
| `age_years` | source `AGE` | plausible review range 18–120 | not null | DQ-009 |
| `next_month_default` | source `default payment next month` | outcome only; 0/1 | never used as feature | DQ-007, leakage review |
| `month_offset` | explicit wide-to-long map | 0=Sep 2005, …, -5=Apr 2005 | not null | DQ-003, DQ-012 |
| `repayment_status` | `PAY_0`, `PAY_2`…`PAY_6` | source integer preserved; undocumented non-positive codes warned | not null | DQ-010, DQ-018 |
| `bill_amount_ntd` | `BILL_AMT1`…`BILL_AMT6` | source integer NTD | not null; no clipping | REC-003 and monthly tie-outs |
| `payment_amount_ntd` | `PAY_AMT1`…`PAY_AMT6` | source integer NTD | not null; no clipping | REC-004 and monthly tie-outs |

Signal definitions and denominator rules are canonical in
`config/risk_definitions.yml` and `docs/methodology/signal_dictionary.md`.
