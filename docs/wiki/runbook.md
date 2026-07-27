# Runbook

## Setup

1. Copy `.env.example` to `.env` and set a local password.
2. Start PostgreSQL with `docker compose up -d postgres`.
3. Create a Python environment and install the project dependencies.
4. Run `python scripts/validate_scaffold.py`.

## Planned Wave 1 execution

1. register and download the source
2. run Hermes ingestion
3. create schemas and tables
4. load raw data
5. transform borrower and account-month tables
6. run reconciliation and quality tests
7. build risk signals and summaries
8. export validated outputs
9. update work status and evidence map

Exact commands must be added as implementations are created.

## Recovery

- never repair `data/raw/` in place
- rerun from the latest validated checkpoint
- retain failed run IDs and issue records
- regenerate downstream outputs after an upstream correction
