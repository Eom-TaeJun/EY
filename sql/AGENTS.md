# SQL-area instructions

- Separate SQL by lifecycle: DDL, ingestion, staging, quality, reconciliation, features, risk components, reporting.
- Each durable query states grain, inputs, output, assumptions, and expected validation.
- Avoid `SELECT *` in durable transformations.
- Write audit evidence for quality and reconciliation runs.
- Do not change upstream data or validation thresholds inside a test query.
