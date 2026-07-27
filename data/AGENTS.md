# Data-area instructions

- `raw/` is immutable after ingestion.
- Do not place secrets or credentials in this tree.
- Every source artifact needs a registry entry and hash.
- Derived data belongs in interim/processed or the database, not raw.
- Large data files are gitignored; preserve reproducible download and load instructions.
