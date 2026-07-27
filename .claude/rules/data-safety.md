---
paths:
  - "data/**"
  - "src/ingestion/**"
  - "sql/ingestion/**"
---

# Data safety rules

- `data/raw/` is immutable after ingestion.
- Record hashes and counts before transformation.
- Never silently repair, impute, recode, or drop source values.
- Put all transformations in versioned SQL or deterministic code.
- Log rejected records and parsing errors.
