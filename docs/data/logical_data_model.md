# Logical Data Model

## Schemas

- `raw`: immutable source representation
- `staging`: type conversion and explicit standardization
- `core`: normalized borrower and time-series facts
- `mart`: signals, model results, scenarios, reporting summaries
- `audit`: runs, tests, reconciliations, issues
- `meta`: definitions, nodes, edges, lineage

## Initial grains

- borrower: `customer_id`
- account month: `customer_id + month_offset`
- quality result: `test_run_id + test_id`
- signal snapshot: `signal_run_id + customer_id`
- risk summary: `signal_run_id + risk_band`

## Temporal fields

Where relevant, store:

- `observation_date` or `month_offset`
- `source_release_date`
- `ingested_at`
- `pipeline_run_id`
- `definition_version`

The Wave 1 dataset is retrospective and compact, but the schema should not prevent later bitemporal or revision-aware extensions.
