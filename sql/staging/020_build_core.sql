/*
Purpose:
  Build run-scoped borrower and six-month account facts from immutable raw data.
Input tables:
  raw.credit_card_client and audit.source_file.
Output definition:
  core.borrower has one row per customer within a pipeline run.
  core.account_month has exactly six rows per customer within a pipeline run.
Observation point:
  2005-09-30. month_offset 0 is September 2005 and -5 is April 2005.
Key assumptions:
  Header renaming changes SQL identifiers only. Raw numeric values are copied
  exactly; no code repair, missing-value fill, clipping, or outlier deletion.
Validation:
  The transaction raises on source ambiguity or row-count mismatch, then
  sql/reconciliation/030_core_reconciliation.sql ties out counts and amounts.
*/

\if :{?run_id}
\else
  \echo 'run_id is required: psql -v run_id=...'
  \quit 2
\endif

BEGIN;

SELECT set_config('credit_risk.run_id', :'run_id', false);

INSERT INTO audit.pipeline_run (
    pipeline_run_id,
    run_type,
    source_id,
    source_file_sha256,
    definition_version,
    observation_date,
    status
)
SELECT
    current_setting('credit_risk.run_id'),
    'wave1_core_signal',
    min(source_id),
    min(source_file_sha256),
    '0.1.0',
    DATE '2005-09-30',
    'building'
FROM raw.credit_card_client
HAVING count(DISTINCT (source_id, source_file_sha256)) = 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM audit.pipeline_run
        WHERE pipeline_run_id = current_setting('credit_risk.run_id')
    ) THEN
        RAISE EXCEPTION 'raw source is absent or has more than one source identity';
    END IF;
END;
$$;

INSERT INTO core.borrower (
    pipeline_run_id,
    customer_id,
    credit_limit_ntd,
    sex_code,
    education_code,
    marriage_code,
    age_years,
    next_month_default,
    observation_date,
    source_id,
    source_file_sha256,
    definition_version
)
SELECT
    current_setting('credit_risk.run_id'),
    id,
    limit_bal,
    sex,
    education,
    marriage,
    age,
    default_payment_next_month,
    DATE '2005-09-30',
    source_id,
    source_file_sha256,
    '0.1.0'
FROM raw.credit_card_client
ORDER BY id;

INSERT INTO core.account_month (
    pipeline_run_id,
    customer_id,
    month_offset,
    statement_month_end,
    repayment_status,
    bill_amount_ntd,
    payment_amount_ntd,
    repayment_source_field,
    bill_source_field,
    payment_source_field,
    definition_version
)
SELECT
    current_setting('credit_risk.run_id'),
    r.id,
    history.month_offset,
    history.statement_month_end,
    history.repayment_status,
    history.bill_amount_ntd,
    history.payment_amount_ntd,
    history.repayment_source_field,
    history.bill_source_field,
    history.payment_source_field,
    '0.1.0'
FROM raw.credit_card_client AS r
CROSS JOIN LATERAL (
    VALUES
        (0::smallint, DATE '2005-09-30', r.pay_0, r.bill_amt1, r.pay_amt1, 'PAY_0', 'BILL_AMT1', 'PAY_AMT1'),
        (-1::smallint, DATE '2005-08-31', r.pay_2, r.bill_amt2, r.pay_amt2, 'PAY_2', 'BILL_AMT2', 'PAY_AMT2'),
        (-2::smallint, DATE '2005-07-31', r.pay_3, r.bill_amt3, r.pay_amt3, 'PAY_3', 'BILL_AMT3', 'PAY_AMT3'),
        (-3::smallint, DATE '2005-06-30', r.pay_4, r.bill_amt4, r.pay_amt4, 'PAY_4', 'BILL_AMT4', 'PAY_AMT4'),
        (-4::smallint, DATE '2005-05-31', r.pay_5, r.bill_amt5, r.pay_amt5, 'PAY_5', 'BILL_AMT5', 'PAY_AMT5'),
        (-5::smallint, DATE '2005-04-30', r.pay_6, r.bill_amt6, r.pay_amt6, 'PAY_6', 'BILL_AMT6', 'PAY_AMT6')
) AS history (
    month_offset,
    statement_month_end,
    repayment_status,
    bill_amount_ntd,
    payment_amount_ntd,
    repayment_source_field,
    bill_source_field,
    payment_source_field
)
ORDER BY r.id, history.month_offset;

DO $$
DECLARE
    raw_rows bigint;
    borrower_rows bigint;
    account_month_rows bigint;
BEGIN
    SELECT count(*) INTO raw_rows FROM raw.credit_card_client;
    SELECT count(*) INTO borrower_rows
    FROM core.borrower
    WHERE pipeline_run_id = current_setting('credit_risk.run_id');
    SELECT count(*) INTO account_month_rows
    FROM core.account_month
    WHERE pipeline_run_id = current_setting('credit_risk.run_id');

    IF borrower_rows <> raw_rows THEN
        RAISE EXCEPTION 'raw/core borrower mismatch: raw %, core %',
            raw_rows, borrower_rows;
    END IF;
    IF account_month_rows <> borrower_rows * 6 THEN
        RAISE EXCEPTION 'wide-to-long mismatch: expected %, actual %',
            borrower_rows * 6, account_month_rows;
    END IF;
END;
$$;

UPDATE audit.pipeline_run
SET status = 'succeeded',
    completed_at = clock_timestamp()
WHERE pipeline_run_id = current_setting('credit_risk.run_id');

COMMIT;
