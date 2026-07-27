# Source Registry

| Source ID | Provider | File/path | Version/date | License/access | Hash | Rows | Columns | Ingested at | Status |
|---|---|---|---|---|---|---:|---:|---|---|
| `uci_default_credit_card_clients` | [UCI ML Repository, dataset 350](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients) | `data/raw/default of credit card clients.xls` (official ZIP retained alongside it) | Donated 2016-01-25; downloaded 2026-07-27 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), public; cite Yeh (2009), DOI [`10.24432/C55S3H`](https://doi.org/10.24432/C55S3H) | XLS SHA-256 `30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933` | 30,000 data rows (30,002 including two headers) | 25 | 2026-07-27 12:15:02 UTC | Loaded and reconciled; idempotency verified |

## UCI dataset 350 artifact inventory

| Artifact | Bytes | SHA-256 | Check |
|---|---:|---|---|
| `data/raw/default+of+credit+card+clients.zip` | 5,539,494 | `56c885f84457f6680f8438f02bfcdac9579323d8a94465ee5f26e32baa727602` | ZIP integrity passed; exactly one member |
| `data/raw/default of credit card clients.xls` | 5,539,328 | `30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933` | Matches the uncompressed archive member |

The ZIP was downloaded from UCI's official dataset-350 static download URL.
The workbook is an Excel 97-2003 file with worksheet `Data`. Its physical
shape is 30,002 rows by 25 columns: source variable labels on row 1, source
field labels on row 2, and 30,000 data rows beginning on spreadsheet row 3.
All 750,000 inspected data cells are numeric and integral. Inspection accepted
30,000 rows and rejected zero cells or duplicate IDs.

## Header structure

Source variable row:

```text
(blank), X1, X2, X3, X4, X5, X6, X7, X8, X9, X10, X11,
X12, X13, X14, X15, X16, X17, X18, X19, X20, X21, X22, X23, Y
```

Source field row:

```text
ID, LIMIT_BAL, SEX, EDUCATION, MARRIAGE, AGE,
PAY_0, PAY_2, PAY_3, PAY_4, PAY_5, PAY_6,
BILL_AMT1, BILL_AMT2, BILL_AMT3, BILL_AMT4, BILL_AMT5, BILL_AMT6,
PAY_AMT1, PAY_AMT2, PAY_AMT3, PAY_AMT4, PAY_AMT5, PAY_AMT6,
default payment next month
```

The raw table uses SQL-safe lowercase names while retaining each accepted
integer value exactly. The target label is named
`default_payment_next_month`; this is identifier normalization only, not a
value or definition change.

## Verified raw ingestion

Both database runs completed with status `loaded_and_reconciled` and zero
rejected rows.

| Run ID | Purpose | Source | Staged | Inserted | Existing exact matches | Raw rows for source hash | Evidence |
|---|---|---:|---:|---:|---:|---:|---|
| `uci350-raw-load-20260727-001` | Initial insert-only load | 30,000 | 30,000 | 30,000 | 0 | 30,000 | `logs/ingestion/uci350-raw-load-20260727-001.json` |
| `uci350-raw-load-20260727-002` | Idempotency rerun | 30,000 | 30,000 | 0 | 30,000 | 30,000 | `logs/ingestion/uci350-raw-load-20260727-002.json` |

The second run proves that the same pinned source is reconciled as an exact
no-op: no raw row was replaced or duplicated, and all 30,000 existing rows
matched the source values, file hash, and source row number.

## Controlled ingestion

Inspect the immutable source without a database:

```bash
python src/ingestion/load_uci_credit_card.py --inspect-only
```

When PostgreSQL is available, create/load/reconcile the raw target:

```bash
docker compose up -d postgres
export DATABASE_URL='postgresql://credit_risk:change_me@localhost:5432/credit_risk_lab'
python src/ingestion/load_uci_credit_card.py \
  --run-id uci350-raw-load-20260727-003
```

Use a new run ID for every database attempt because audit rows and JSON logs
are immutable by run ID. Runs `uci350-raw-load-20260727-001` and
`uci350-raw-load-20260727-002` above already proved the initial load and
idempotent rerun; a subsequent run should likewise insert zero rows while
matching all 30,000 existing rows.

The loader validates both pinned SHA-256 values, the archive member, worksheet,
two headers, dimensions, integral cell representation, and duplicate source
IDs before opening PostgreSQL. It copies rows into a transaction-local table,
rejects any conflict with an existing raw row, inserts missing rows only, and
requires an exact 30,000-row source/raw match. A repeated load of the same file
must report zero inserted rows and 30,000 existing matching rows. It never
updates, deletes, truncates, imputes, rounds, or recodes raw values.

The official workbook parser requires `xlrd>=2.0`. PostgreSQL loading requires
`psycopg>=3.2`. Every run creates a new JSON file under `logs/ingestion/` and
refuses to overwrite an existing run log.

## Hermes requirements

- record the exact downloaded artifact
- compute SHA-256 before transformation
- record encoding, delimiter, worksheet, header handling, and column names
- do not silently repair source values
- log parsing errors and rejected records
