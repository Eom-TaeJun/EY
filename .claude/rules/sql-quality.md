---
paths:
  - "sql/**"
  - "tests/data_quality/**"
  - "tests/integration/**"
---

# SQL quality rules

- Every major query documents grain, inputs, output, assumptions, and expected checks.
- Use explicit column lists; avoid `SELECT *` in durable transformations.
- Make transformations idempotent where practical.
- Separate DDL, ingestion, staging, quality, feature, reporting, and reconciliation SQL.
- Failed tests must create evidence; they are not suppressed.
