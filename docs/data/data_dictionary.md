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
| `raw.credit_card_client` | one row per customer | immutable source representation | Planned |
| `core.borrower` | one row per customer | fixed borrower/account attributes | Planned |
| `core.account_month` | one row per customer-month | repayment, bill, and payment history | Planned |
| `mart.risk_signal_snapshot` | one row per customer | explainable risk signals | Planned |
| `mart.risk_band_summary` | one row per risk band | observed outcome summary | Planned |
| `audit.data_quality_result` | one row per test-run | quality evidence | Planned |

Do not finalize field definitions until the source schema is inspected.
