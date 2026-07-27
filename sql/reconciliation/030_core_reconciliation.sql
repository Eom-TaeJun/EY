/*
Purpose:
  Reconcile immutable wide raw data to run-scoped borrower/account-month facts.
Input tables:
  raw.credit_card_client, core.borrower, core.account_month.
Output definition:
  audit.reconciliation_result rows for counts and NTD bill/payment totals,
  including all six source months.
Observation point:
  The run observation date is 2005-09-30; offsets 0 through -5 map to
  September through April 2005.
Key assumptions:
  Amounts are source integers in NTD. The approved exact-amount tolerance is 0.
Validation:
  Every row is pass only when source_value equals derived_value. Gate 2 also
  runs independent SQL tests and the Python reproduction contract.
*/

\if :{?run_id}
\else
  \echo 'run_id is required: psql -v run_id=...'
  \quit 2
\endif

BEGIN;
SET LOCAL jit = off;
SELECT set_config('credit_risk.run_id', :'run_id', false);

WITH metrics AS (
    SELECT
        'REC-001'::text AS reconciliation_id,
        'raw_to_core_borrower_rows'::text AS metric_name,
        (SELECT count(*) FROM raw.credit_card_client)::numeric AS source_value,
        (
            SELECT count(*)
            FROM core.borrower
            WHERE pipeline_run_id = current_setting('credit_risk.run_id')
        )::numeric AS derived_value,
        jsonb_build_object('grain', 'customer') AS details
    UNION ALL
    SELECT
        'REC-002',
        'expected_to_actual_account_month_rows',
        (
            SELECT count(*) * 6
            FROM core.borrower
            WHERE pipeline_run_id = current_setting('credit_risk.run_id')
        )::numeric,
        (
            SELECT count(*)
            FROM core.account_month
            WHERE pipeline_run_id = current_setting('credit_risk.run_id')
        )::numeric,
        jsonb_build_object('months_per_borrower', 6)
    UNION ALL
    SELECT
        'REC-003',
        'wide_to_long_bill_total_ntd',
        (
            SELECT sum(
                bill_amt1::numeric + bill_amt2 + bill_amt3
                + bill_amt4 + bill_amt5 + bill_amt6
            )
            FROM raw.credit_card_client
        ),
        (
            SELECT sum(bill_amount_ntd)::numeric
            FROM core.account_month
            WHERE pipeline_run_id = current_setting('credit_risk.run_id')
        ),
        jsonb_build_object('currency', 'NTD', 'tolerance', 0)
    UNION ALL
    SELECT
        'REC-004',
        'wide_to_long_payment_total_ntd',
        (
            SELECT sum(
                pay_amt1::numeric + pay_amt2 + pay_amt3
                + pay_amt4 + pay_amt5 + pay_amt6
            )
            FROM raw.credit_card_client
        ),
        (
            SELECT sum(payment_amount_ntd)::numeric
            FROM core.account_month
            WHERE pipeline_run_id = current_setting('credit_risk.run_id')
        ),
        jsonb_build_object('currency', 'NTD', 'tolerance', 0)
),
month_metrics AS (
    SELECT
        format('REC-BILL-%s', source.month_offset) AS reconciliation_id,
        format('bill_total_month_offset_%s', source.month_offset) AS metric_name,
        source.source_total AS source_value,
        (
            SELECT sum(account.bill_amount_ntd)::numeric
            FROM core.account_month AS account
            WHERE account.pipeline_run_id = current_setting('credit_risk.run_id')
              AND account.month_offset = source.month_offset
        ) AS derived_value,
        jsonb_build_object(
            'month_offset', source.month_offset,
            'source_field', source.source_field,
            'currency', 'NTD'
        ) AS details
    FROM (
        SELECT 0 AS month_offset, 'BILL_AMT1' AS source_field, sum(bill_amt1)::numeric AS source_total FROM raw.credit_card_client
        UNION ALL SELECT -1, 'BILL_AMT2', sum(bill_amt2)::numeric FROM raw.credit_card_client
        UNION ALL SELECT -2, 'BILL_AMT3', sum(bill_amt3)::numeric FROM raw.credit_card_client
        UNION ALL SELECT -3, 'BILL_AMT4', sum(bill_amt4)::numeric FROM raw.credit_card_client
        UNION ALL SELECT -4, 'BILL_AMT5', sum(bill_amt5)::numeric FROM raw.credit_card_client
        UNION ALL SELECT -5, 'BILL_AMT6', sum(bill_amt6)::numeric FROM raw.credit_card_client
    ) AS source
    UNION ALL
    SELECT
        format('REC-PAYMENT-%s', source.month_offset),
        format('payment_total_month_offset_%s', source.month_offset),
        source.source_total,
        (
            SELECT sum(account.payment_amount_ntd)::numeric
            FROM core.account_month AS account
            WHERE account.pipeline_run_id = current_setting('credit_risk.run_id')
              AND account.month_offset = source.month_offset
        ),
        jsonb_build_object(
            'month_offset', source.month_offset,
            'source_field', source.source_field,
            'currency', 'NTD'
        )
    FROM (
        SELECT 0 AS month_offset, 'PAY_AMT1' AS source_field, sum(pay_amt1)::numeric AS source_total FROM raw.credit_card_client
        UNION ALL SELECT -1, 'PAY_AMT2', sum(pay_amt2)::numeric FROM raw.credit_card_client
        UNION ALL SELECT -2, 'PAY_AMT3', sum(pay_amt3)::numeric FROM raw.credit_card_client
        UNION ALL SELECT -3, 'PAY_AMT4', sum(pay_amt4)::numeric FROM raw.credit_card_client
        UNION ALL SELECT -4, 'PAY_AMT5', sum(pay_amt5)::numeric FROM raw.credit_card_client
        UNION ALL SELECT -5, 'PAY_AMT6', sum(pay_amt6)::numeric FROM raw.credit_card_client
    ) AS source
),
all_metrics AS (
    SELECT * FROM metrics
    UNION ALL
    SELECT * FROM month_metrics
)
INSERT INTO audit.reconciliation_result (
    pipeline_run_id,
    reconciliation_id,
    metric_name,
    source_value,
    derived_value,
    difference,
    tolerance,
    status,
    details
)
SELECT
    current_setting('credit_risk.run_id'),
    reconciliation_id,
    metric_name,
    source_value,
    derived_value,
    derived_value - source_value,
    0,
    CASE WHEN derived_value = source_value THEN 'pass' ELSE 'fail' END,
    details
FROM all_metrics
ORDER BY reconciliation_id;

COMMIT;
