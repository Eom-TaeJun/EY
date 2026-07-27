/*
Purpose:
  Execute stable source, key, transformation, domain, and preservation checks.
Input tables:
  audit.source_file, audit.reconciliation_result, raw.credit_card_client,
  core.borrower, core.account_month.
Output definition:
  One audit.test_result row per DQ test with tested/failed rows, rate, severity,
  evidence query path, and bounded samples for known source-domain exceptions.
Observation point:
  Run-scoped at 2005-09-30.
Key assumptions:
  UCI-documented code sets are checked without repairing observed undocumented
  values. Undocumented education, marriage, and repayment codes are warnings,
  not silently accepted as documented meanings.
Validation:
  Gate 2 requires zero status='fail'. Warning rows remain visible and sampled.
*/

\if :{?run_id}
\else
  \echo 'run_id is required: psql -v run_id=...'
  \quit 2
\endif

BEGIN;
SET LOCAL jit = off;
SELECT set_config('credit_risk.run_id', :'run_id', false);

WITH checks AS (
    SELECT 'DQ-001'::text AS test_id, 'raw customer ID uniqueness'::text AS test_name,
        'critical'::text AS severity,
        (SELECT count(*) FROM raw.credit_card_client)::bigint AS tested_rows,
        (
            SELECT count(*) FROM (
                SELECT id FROM raw.credit_card_client GROUP BY id HAVING count(*) > 1
            ) AS duplicate_ids
        )::bigint AS failed_rows,
        'raw.credit_card_client'::text AS affected_object
    UNION ALL
    SELECT 'DQ-002', 'raw rows equal registered source rows', 'critical',
        1,
        CASE WHEN (
            SELECT count(*) FROM raw.credit_card_client
        ) = (
            SELECT data_row_count
            FROM audit.source_file
            WHERE source_id = 'uci_default_credit_card_clients'
            ORDER BY registered_at DESC
            LIMIT 1
        ) THEN 0 ELSE 1 END,
        'audit.source_file -> raw.credit_card_client'
    UNION ALL
    SELECT 'DQ-003', 'each borrower has six account months', 'critical',
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (
            SELECT count(*) FROM (
                SELECT customer_id
                FROM core.account_month
                WHERE pipeline_run_id = current_setting('credit_risk.run_id')
                GROUP BY customer_id
                HAVING count(*) <> 6
            ) AS bad_customer
        ),
        'core.account_month'
    UNION ALL
    SELECT 'DQ-004', 'account-month rows equal borrower rows times six', 'critical',
        1,
        CASE WHEN (
            SELECT count(*) FROM core.account_month
            WHERE pipeline_run_id = current_setting('credit_risk.run_id')
        ) = 6 * (
            SELECT count(*) FROM core.borrower
            WHERE pipeline_run_id = current_setting('credit_risk.run_id')
        ) THEN 0 ELSE 1 END,
        'core.borrower -> core.account_month'
    UNION ALL
    SELECT 'DQ-005', 'wide and long bill totals reconcile', 'critical',
        1,
        CASE WHEN (
            SELECT status FROM audit.reconciliation_result
            WHERE pipeline_run_id = current_setting('credit_risk.run_id')
              AND reconciliation_id = 'REC-003'
        ) = 'pass' THEN 0 ELSE 1 END,
        'audit.reconciliation_result.REC-003'
    UNION ALL
    SELECT 'DQ-006', 'wide and long payment totals reconcile', 'critical',
        1,
        CASE WHEN (
            SELECT status FROM audit.reconciliation_result
            WHERE pipeline_run_id = current_setting('credit_risk.run_id')
              AND reconciliation_id = 'REC-004'
        ) = 'pass' THEN 0 ELSE 1 END,
        'audit.reconciliation_result.REC-004'
    UNION ALL
    SELECT 'DQ-007', 'outcome is binary', 'critical',
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id') AND next_month_default NOT IN (0, 1)),
        'core.borrower.next_month_default'
    UNION ALL
    SELECT 'DQ-008', 'credit limit is positive', 'high',
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id') AND credit_limit_ntd <= 0),
        'core.borrower.credit_limit_ntd'
    UNION ALL
    SELECT 'DQ-009', 'age is within plausible reviewed bounds 18-120', 'high',
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id') AND age_years NOT BETWEEN 18 AND 120),
        'core.borrower.age_years'
    UNION ALL
    SELECT 'DQ-010', 'required history fields are populated', 'critical',
        (SELECT count(*) FROM core.account_month WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (SELECT count(*) FROM core.account_month WHERE pipeline_run_id = current_setting('credit_risk.run_id') AND (repayment_status IS NULL OR bill_amount_ntd IS NULL OR payment_amount_ntd IS NULL)),
        'core.account_month'
    UNION ALL
    SELECT 'DQ-011', 'account months have a borrower parent', 'critical',
        (SELECT count(*) FROM core.account_month WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (
            SELECT count(*)
            FROM core.account_month AS account
            LEFT JOIN core.borrower AS borrower
              ON borrower.pipeline_run_id = account.pipeline_run_id
             AND borrower.customer_id = account.customer_id
            WHERE account.pipeline_run_id = current_setting('credit_risk.run_id')
              AND borrower.customer_id IS NULL
        ),
        'core.account_month -> core.borrower'
    UNION ALL
    SELECT 'DQ-012', 'month offsets map to approved month ends', 'critical',
        (SELECT count(*) FROM core.account_month WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (
            SELECT count(*)
            FROM core.account_month
            WHERE pipeline_run_id = current_setting('credit_risk.run_id')
              AND statement_month_end <> CASE month_offset
                    WHEN 0 THEN DATE '2005-09-30'
                    WHEN -1 THEN DATE '2005-08-31'
                    WHEN -2 THEN DATE '2005-07-31'
                    WHEN -3 THEN DATE '2005-06-30'
                    WHEN -4 THEN DATE '2005-05-31'
                    WHEN -5 THEN DATE '2005-04-30'
                  END
        ),
        'core.account_month.statement_month_end'
    UNION ALL
    SELECT 'DQ-013', 'sex uses UCI documented codes 1-2', 'high',
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id') AND sex_code NOT IN (1, 2)),
        'core.borrower.sex_code'
    UNION ALL
    SELECT 'DQ-014', 'raw and core borrower attributes match exactly', 'critical',
        (SELECT count(*) FROM raw.credit_card_client),
        (
            SELECT count(*)
            FROM raw.credit_card_client AS raw_row
            JOIN core.borrower AS borrower
              ON borrower.customer_id = raw_row.id
             AND borrower.pipeline_run_id = current_setting('credit_risk.run_id')
            WHERE ROW(
                raw_row.limit_bal, raw_row.sex, raw_row.education,
                raw_row.marriage, raw_row.age
            ) IS DISTINCT FROM ROW(
                borrower.credit_limit_ntd, borrower.sex_code,
                borrower.education_code, borrower.marriage_code,
                borrower.age_years
            )
        ),
        'raw.credit_card_client -> core.borrower'
    UNION ALL
    SELECT 'DQ-015', 'raw and core outcomes match exactly', 'critical',
        (SELECT count(*) FROM raw.credit_card_client),
        (
            SELECT count(*)
            FROM raw.credit_card_client AS raw_row
            JOIN core.borrower AS borrower
              ON borrower.customer_id = raw_row.id
             AND borrower.pipeline_run_id = current_setting('credit_risk.run_id')
            WHERE raw_row.default_payment_next_month IS DISTINCT FROM borrower.next_month_default
        ),
        'raw.credit_card_client -> core.borrower.next_month_default'
    UNION ALL
    SELECT 'DQ-016', 'education code is documented by UCI', 'medium',
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id') AND education_code NOT IN (1, 2, 3, 4)),
        'core.borrower.education_code'
    UNION ALL
    SELECT 'DQ-017', 'marriage code is documented by UCI', 'medium',
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = current_setting('credit_risk.run_id') AND marriage_code NOT IN (1, 2, 3)),
        'core.borrower.marriage_code'
    UNION ALL
    SELECT 'DQ-018', 'repayment code is documented by UCI', 'medium',
        (SELECT count(*) FROM core.account_month WHERE pipeline_run_id = current_setting('credit_risk.run_id')),
        (SELECT count(*) FROM core.account_month WHERE pipeline_run_id = current_setting('credit_risk.run_id') AND repayment_status NOT IN (-1, 1, 2, 3, 4, 5, 6, 7, 8, 9)),
        'core.account_month.repayment_status'
)
INSERT INTO audit.test_result (
    pipeline_run_id,
    test_id,
    test_name,
    test_type,
    status,
    severity,
    tested_rows,
    failed_rows,
    failure_rate,
    affected_object,
    evidence_query
)
SELECT
    current_setting('credit_risk.run_id'),
    test_id,
    test_name,
    'data_quality',
    CASE
        WHEN failed_rows = 0 THEN 'pass'
        WHEN severity IN ('medium', 'low') THEN 'warn'
        ELSE 'fail'
    END,
    severity,
    tested_rows,
    failed_rows,
    CASE WHEN tested_rows = 0 THEN 0 ELSE failed_rows::numeric / tested_rows END,
    affected_object,
    'sql/quality/040_data_quality.sql#' || test_id
FROM checks
ORDER BY test_id;

UPDATE audit.test_result
SET sample_json = (
    SELECT coalesce(jsonb_agg(sample ORDER BY customer_id), '[]'::jsonb)
    FROM (
        SELECT customer_id, education_code
        FROM core.borrower
        WHERE pipeline_run_id = current_setting('credit_risk.run_id')
          AND education_code NOT IN (1, 2, 3, 4)
        ORDER BY customer_id
        LIMIT 10
    ) AS sample
)
WHERE pipeline_run_id = current_setting('credit_risk.run_id')
  AND test_id = 'DQ-016';

UPDATE audit.test_result
SET sample_json = (
    SELECT coalesce(jsonb_agg(sample ORDER BY customer_id), '[]'::jsonb)
    FROM (
        SELECT customer_id, marriage_code
        FROM core.borrower
        WHERE pipeline_run_id = current_setting('credit_risk.run_id')
          AND marriage_code NOT IN (1, 2, 3)
        ORDER BY customer_id
        LIMIT 10
    ) AS sample
)
WHERE pipeline_run_id = current_setting('credit_risk.run_id')
  AND test_id = 'DQ-017';

UPDATE audit.test_result
SET sample_json = (
    SELECT coalesce(jsonb_agg(sample ORDER BY customer_id, month_offset), '[]'::jsonb)
    FROM (
        SELECT customer_id, month_offset, repayment_status
        FROM core.account_month
        WHERE pipeline_run_id = current_setting('credit_risk.run_id')
          AND repayment_status NOT IN (-1, 1, 2, 3, 4, 5, 6, 7, 8, 9)
        ORDER BY customer_id, month_offset
        LIMIT 10
    ) AS sample
)
WHERE pipeline_run_id = current_setting('credit_risk.run_id')
  AND test_id = 'DQ-018';

COMMIT;
