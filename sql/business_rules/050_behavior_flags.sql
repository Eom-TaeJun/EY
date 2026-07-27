/*
Purpose:
  Record reviewable behavioral flags without treating them as source errors.
Input tables:
  core.borrower and core.account_month.
Output definition:
  Five audit.test_result rows with status warn when a portfolio segment is
  flagged. flagged_rows are analytical observations, not failed source rows.
Observation point:
  2005-09-30 using only April-September 2005 history.
Key assumptions:
  Delinquency means source repayment_status > 0. No meaning is assigned to the
  source's undocumented non-positive codes.
Validation:
  These flags do not fail Gate 2; their definitions are reused independently
  in the versioned risk-signal SQL.
*/

\if :{?run_id}
\else
  \echo 'run_id is required: psql -v run_id=...'
  \quit 2
\endif

BEGIN;
SET LOCAL jit = off;
SELECT set_config('credit_risk.run_id', :'run_id', false);

WITH customer_behavior AS (
    SELECT
        borrower.customer_id,
        count(*) FILTER (WHERE account.payment_amount_ntd = 0) AS zero_payment_months,
        count(*) FILTER (WHERE account.repayment_status > 0) AS delinquent_months,
        max(greatest(account.repayment_status, 0))
            FILTER (WHERE account.month_offset BETWEEN -2 AND 0) AS recent_max_status,
        max(greatest(account.repayment_status, 0))
            FILTER (WHERE account.month_offset BETWEEN -5 AND -3) AS earlier_max_status,
        max(account.bill_amount_ntd) FILTER (WHERE account.month_offset = 0)::numeric
            / nullif(borrower.credit_limit_ntd, 0) AS latest_utilization,
        max(account.payment_amount_ntd) FILTER (WHERE account.month_offset = 0)::numeric
            / nullif(
                max(account.bill_amount_ntd) FILTER (WHERE account.month_offset = -1),
                0
            ) AS payment_coverage
    FROM core.borrower AS borrower
    JOIN core.account_month AS account
      ON account.pipeline_run_id = borrower.pipeline_run_id
     AND account.customer_id = borrower.customer_id
    WHERE borrower.pipeline_run_id = current_setting('credit_risk.run_id')
    GROUP BY borrower.customer_id, borrower.credit_limit_ntd
),
checks AS (
    SELECT 'BR-001'::text AS test_id, 'at least two zero-payment months'::text AS test_name,
        count(*)::bigint AS tested_rows,
        count(*) FILTER (WHERE zero_payment_months >= 2)::bigint AS flagged_rows
    FROM customer_behavior
    UNION ALL
    SELECT 'BR-002', 'at least two delinquent months', count(*),
        count(*) FILTER (WHERE delinquent_months >= 2)
    FROM customer_behavior
    UNION ALL
    SELECT 'BR-003', 'recent delinquency deterioration', count(*),
        count(*) FILTER (WHERE recent_max_status > earlier_max_status)
    FROM customer_behavior
    UNION ALL
    SELECT 'BR-004', 'latest bill at or above credit limit', count(*),
        count(*) FILTER (WHERE latest_utilization >= 1)
    FROM customer_behavior
    UNION ALL
    SELECT 'BR-005', 'latest payment below 10 percent of prior positive bill', count(*),
        count(*) FILTER (WHERE payment_coverage >= 0 AND payment_coverage < 0.10)
    FROM customer_behavior
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
    'business_rule',
    CASE WHEN flagged_rows = 0 THEN 'pass' ELSE 'warn' END,
    'analytical_flag',
    tested_rows,
    flagged_rows,
    CASE WHEN tested_rows = 0 THEN 0 ELSE flagged_rows::numeric / tested_rows END,
    'core.account_month',
    'sql/business_rules/050_behavior_flags.sql#' || test_id
FROM checks
ORDER BY test_id;

COMMIT;
