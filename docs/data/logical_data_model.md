# Logical Data Model

## Schemas

- `raw`: immutable source representation
- `staging`: type conversion and explicit standardization
- `core`: normalized borrower and time-series facts
- `mart`: signals, model results, scenarios, reporting summaries
- `audit`: runs, tests, reconciliations, issues
- `meta`: definitions, nodes, edges, lineage

## Initial grains

- borrower: `pipeline_run_id + customer_id`
- account month: `pipeline_run_id + customer_id + month_offset`
- quality result: `pipeline_run_id + test_id`
- signal snapshot: `pipeline_run_id + customer_id`
- signal summary: `pipeline_run_id + signal_name + signal_bucket`
- risk summary: `pipeline_run_id + risk_band`

Run-scoped keys prevent a new execution from overwriting a prior validated
result. The business grain remains customer or customer-month within a run.

## Implemented Wave 1 relationships

| Parent | Child | Relationship | Validation |
|---|---|---|---|
| `audit.source_file` | `raw.credit_card_client` | one registered file hash to source rows | Gate 1 exact row/hash reconciliation |
| `audit.pipeline_run` | `core.borrower` | one run to 30,000 borrower snapshots | DQ-002, DQ-014, DQ-015 |
| `core.borrower` | `core.account_month` | one borrower to six source months | DQ-003, DQ-004, DQ-011, DQ-012 |
| `core.borrower` | `mart.borrower_risk_signal` | one borrower to one versioned signal row | Gate 3 population reconciliation |
| `mart.borrower_risk_signal` | summary marts | bucket and risk-band aggregates | independent default-count/rate reproduction |

## Temporal fields

Where relevant, store:

- `observation_date` or `month_offset`
- `source_release_date`
- `ingested_at`
- `pipeline_run_id`
- `definition_version`

The Wave 1 dataset is retrospective and compact, but the schema should not prevent later bitemporal or revision-aware extensions.
