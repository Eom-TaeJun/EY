/*
Purpose:
  Create the insert-only PostgreSQL raw target and source-ingestion audit tables
  for UCI dataset 350.
Input tables:
  None. The Python loader validates and streams the official XLS rows into the
  temporary load table used by the insert statement.
Output definition:
  raw.credit_card_client has one source row per customer and retains all 25
  workbook fields plus source-file and ingestion provenance. audit.source_file
  has one row per registered source-file hash. audit.ingestion_run has one row
  per attempted database load.
Observation point:
  The workbook contains the source's April-September 2005 history and its
  "default payment next month" outcome. This DDL does not reinterpret timing.
Key assumptions:
  Accepted workbook cells are non-null integral numerics. No source business
  domain is constrained here because raw loading must not recode unusual values.
Validation:
  Run src/ingestion/load_uci_credit_card.py. It requires 30,000 exact source/raw
  row matches, zero rejected rows, and refuses conflicts or raw mutation.
*/

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.source_file (
    source_id text NOT NULL,
    dataset_id integer NOT NULL,
    provider text NOT NULL,
    source_url text NOT NULL,
    doi text NOT NULL,
    license text NOT NULL,
    archive_path text NOT NULL,
    archive_bytes bigint NOT NULL CHECK (archive_bytes > 0),
    archive_sha256 text NOT NULL CHECK (archive_sha256 ~ '^[0-9a-f]{64}$'),
    file_path text NOT NULL,
    file_name text NOT NULL,
    file_bytes bigint NOT NULL CHECK (file_bytes > 0),
    file_sha256 text NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
    worksheet text NOT NULL,
    physical_row_count integer NOT NULL CHECK (physical_row_count > 0),
    data_row_count integer NOT NULL CHECK (data_row_count > 0),
    column_count integer NOT NULL CHECK (column_count > 0),
    header_row_count integer NOT NULL CHECK (header_row_count >= 0),
    registered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (source_id, file_sha256)
);

CREATE TABLE IF NOT EXISTS audit.ingestion_run (
    ingestion_run_id text PRIMARY KEY,
    source_id text NOT NULL,
    source_file_sha256 text NOT NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    source_row_count integer NOT NULL CHECK (source_row_count >= 0),
    staged_row_count integer CHECK (staged_row_count >= 0),
    inserted_row_count integer CHECK (inserted_row_count >= 0),
    existing_matching_row_count integer CHECK (existing_matching_row_count >= 0),
    raw_source_row_count integer CHECK (raw_source_row_count >= 0),
    rejected_row_count integer NOT NULL CHECK (rejected_row_count >= 0),
    error_message text,
    FOREIGN KEY (source_id, source_file_sha256)
        REFERENCES audit.source_file (source_id, file_sha256)
);

CREATE TABLE IF NOT EXISTS raw.credit_card_client (
    id integer PRIMARY KEY,
    limit_bal integer NOT NULL,
    sex integer NOT NULL,
    education integer NOT NULL,
    marriage integer NOT NULL,
    age integer NOT NULL,
    pay_0 integer NOT NULL,
    pay_2 integer NOT NULL,
    pay_3 integer NOT NULL,
    pay_4 integer NOT NULL,
    pay_5 integer NOT NULL,
    pay_6 integer NOT NULL,
    bill_amt1 integer NOT NULL,
    bill_amt2 integer NOT NULL,
    bill_amt3 integer NOT NULL,
    bill_amt4 integer NOT NULL,
    bill_amt5 integer NOT NULL,
    bill_amt6 integer NOT NULL,
    pay_amt1 integer NOT NULL,
    pay_amt2 integer NOT NULL,
    pay_amt3 integer NOT NULL,
    pay_amt4 integer NOT NULL,
    pay_amt5 integer NOT NULL,
    pay_amt6 integer NOT NULL,
    default_payment_next_month integer NOT NULL,
    source_id text NOT NULL,
    source_file_sha256 text NOT NULL,
    source_row_number integer NOT NULL CHECK (source_row_number >= 3),
    ingestion_run_id text NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (source_file_sha256, source_row_number),
    FOREIGN KEY (source_id, source_file_sha256)
        REFERENCES audit.source_file (source_id, file_sha256),
    FOREIGN KEY (ingestion_run_id)
        REFERENCES audit.ingestion_run (ingestion_run_id)
);

CREATE OR REPLACE FUNCTION raw.reject_credit_card_client_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'raw.credit_card_client is insert-only; % requires controlled rebuild approval',
        TG_OP;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgrelid = 'raw.credit_card_client'::regclass
          AND tgname = 'credit_card_client_reject_row_mutation'
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER credit_card_client_reject_row_mutation
        BEFORE UPDATE OR DELETE ON raw.credit_card_client
        FOR EACH ROW
        EXECUTE FUNCTION raw.reject_credit_card_client_mutation();
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgrelid = 'raw.credit_card_client'::regclass
          AND tgname = 'credit_card_client_reject_truncate'
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER credit_card_client_reject_truncate
        BEFORE TRUNCATE ON raw.credit_card_client
        FOR EACH STATEMENT
        EXECUTE FUNCTION raw.reject_credit_card_client_mutation();
    END IF;
END;
$$;
