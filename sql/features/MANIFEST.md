# Wave 1 Signal Query Manifest

Definition version: `0.1.0`

| Order | Artifact | Deterministic output |
|---:|---|---|
| 1 | `sql/features/060_risk_signals.sql` | `mart.borrower_risk_signal` |
| 2 | `sql/reporting/070_signal_summaries.sql` | `mart.signal_default_summary`, `mart.risk_band_summary` |

Both queries require a supplied `run_id`, use only run-scoped validated core
tables, and do not use the next-month outcome in feature or band construction.
