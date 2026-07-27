/*
Purpose:
  Convert approved economic/behavioral pathways into seven versioned,
  observation-time-safe borrower signals and an explainable initial risk band.
Input tables:
  core.borrower, core.account_month, audit.test_result,
  audit.reconciliation_result.
Output definition:
  mart.borrower_risk_signal has one row per borrower for the supplied run.
Observation point:
  2005-09-30. Only April-September 2005 source history is used; the source
  next-month default field is carried only as the outcome, never as a feature.
Key assumptions:
  Delinquency severity is greatest(repayment_status, 0), leaving undocumented
  non-positive source codes un-reinterpreted. Payment coverage is September
  payment / August positive bill. Risk points were fixed before outcome review:
  Low 0-1, Medium 2-3, High 4+.
Validation:
  The script refuses to run after any failed DQ or reconciliation test.
  sql/reporting/070_signal_summaries.sql compares outcomes by every signal/band.
*/

\if :{?run_id}
\else
  \echo 'run_id is required: psql -v run_id=...'
  \quit 2
\endif

BEGIN;
SET LOCAL jit = off;
SELECT set_config('credit_risk.run_id', :'run_id', false);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM audit.reconciliation_result
        WHERE pipeline_run_id = current_setting('credit_risk.run_id')
          AND status = 'fail'
    ) OR EXISTS (
        SELECT 1
        FROM audit.test_result
        WHERE pipeline_run_id = current_setting('credit_risk.run_id')
          AND test_type = 'data_quality'
          AND status = 'fail'
    ) THEN
        RAISE EXCEPTION 'Gate 2 evidence has failures; risk signals are blocked';
    END IF;
    IF (
        SELECT count(*)
        FROM audit.test_result
        WHERE pipeline_run_id = current_setting('credit_risk.run_id')
          AND test_type = 'data_quality'
    ) < 12 THEN
        RAISE EXCEPTION 'at least 12 executed data-quality tests are required';
    END IF;
END;
$$;

WITH history AS (
    SELECT
        borrower.pipeline_run_id,
        borrower.customer_id,
        borrower.observation_date,
        borrower.next_month_default,
        borrower.credit_limit_ntd,
        max(greatest(account.repayment_status, 0))
            FILTER (WHERE account.month_offset BETWEEN -2 AND 0) AS recent_max_delinquency,
        count(*) FILTER (WHERE account.repayment_status > 0) AS delinquent_months_6m,
        max(greatest(account.repayment_status, 0))
            FILTER (WHERE account.month_offset BETWEEN -2 AND 0)
            - max(greatest(account.repayment_status, 0))
            FILTER (WHERE account.month_offset BETWEEN -5 AND -3)
            AS delinquency_deterioration,
        max(account.bill_amount_ntd) FILTER (WHERE account.month_offset = 0)
            AS latest_bill,
        max(account.bill_amount_ntd) FILTER (WHERE account.month_offset = -1)
            AS prior_bill,
        max(account.bill_amount_ntd) FILTER (WHERE account.month_offset = -3)
            AS bill_three_months_earlier,
        max(account.payment_amount_ntd) FILTER (WHERE account.month_offset = 0)
            AS latest_payment
    FROM core.borrower AS borrower
    JOIN core.account_month AS account
      ON account.pipeline_run_id = borrower.pipeline_run_id
     AND account.customer_id = borrower.customer_id
    WHERE borrower.pipeline_run_id = current_setting('credit_risk.run_id')
    GROUP BY
        borrower.pipeline_run_id,
        borrower.customer_id,
        borrower.observation_date,
        borrower.next_month_default,
        borrower.credit_limit_ntd
),
zero_months AS (
    SELECT
        account.pipeline_run_id,
        account.customer_id,
        account.month_offset,
        account.month_offset
            - row_number() OVER (
                PARTITION BY account.pipeline_run_id, account.customer_id
                ORDER BY account.month_offset
            ) AS consecutive_group
    FROM core.account_month AS account
    WHERE account.pipeline_run_id = current_setting('credit_risk.run_id')
      AND account.payment_amount_ntd = 0
),
zero_streak AS (
    SELECT
        pipeline_run_id,
        customer_id,
        max(streak_length)::integer AS zero_payment_streak
    FROM (
        SELECT
            pipeline_run_id,
            customer_id,
            consecutive_group,
            count(*) AS streak_length
        FROM zero_months
        GROUP BY pipeline_run_id, customer_id, consecutive_group
    ) AS streak
    GROUP BY pipeline_run_id, customer_id
),
features AS (
    SELECT
        history.pipeline_run_id,
        history.customer_id,
        history.observation_date,
        history.next_month_default,
        history.recent_max_delinquency::integer,
        history.delinquent_months_6m::integer,
        history.delinquency_deterioration::integer,
        history.latest_bill::numeric / nullif(history.credit_limit_ntd, 0)
            AS latest_utilization_ratio,
        CASE
            WHEN history.prior_bill > 0
            THEN history.latest_payment::numeric / history.prior_bill
        END AS payment_coverage_ratio,
        coalesce(zero_streak.zero_payment_streak, 0) AS zero_payment_streak,
        CASE
            WHEN history.bill_three_months_earlier <> 0
            THEN (
                history.latest_bill - history.bill_three_months_earlier
            )::numeric / abs(history.bill_three_months_earlier)
        END AS recent_bill_growth
    FROM history
    LEFT JOIN zero_streak
      ON zero_streak.pipeline_run_id = history.pipeline_run_id
     AND zero_streak.customer_id = history.customer_id
),
scored AS (
    SELECT
        features.*,
        (
            CASE
                WHEN recent_max_delinquency >= 2 THEN 2
                WHEN recent_max_delinquency = 1 THEN 1
                ELSE 0
            END
            + CASE
                WHEN delinquent_months_6m >= 2 THEN 2
                WHEN delinquent_months_6m = 1 THEN 1
                ELSE 0
            END
            + CASE WHEN delinquency_deterioration >= 2 THEN 1 ELSE 0 END
            + CASE WHEN latest_utilization_ratio >= 1 THEN 1 ELSE 0 END
            + CASE
                WHEN payment_coverage_ratio >= 0
                 AND payment_coverage_ratio < 0.10 THEN 1
                ELSE 0
              END
            + CASE WHEN zero_payment_streak >= 2 THEN 1 ELSE 0 END
            + CASE WHEN recent_bill_growth >= 0.25 THEN 1 ELSE 0 END
        )::integer AS risk_points
    FROM features
)
INSERT INTO mart.borrower_risk_signal (
    pipeline_run_id,
    customer_id,
    observation_date,
    next_month_default,
    recent_max_delinquency,
    delinquent_months_6m,
    delinquency_deterioration,
    latest_utilization_ratio,
    payment_coverage_ratio,
    zero_payment_streak,
    recent_bill_growth,
    risk_points,
    risk_band,
    definition_version
)
SELECT
    pipeline_run_id,
    customer_id,
    observation_date,
    next_month_default,
    recent_max_delinquency,
    delinquent_months_6m,
    delinquency_deterioration,
    latest_utilization_ratio,
    payment_coverage_ratio,
    zero_payment_streak,
    recent_bill_growth,
    risk_points,
    CASE
        WHEN risk_points <= 1 THEN 'Low'
        WHEN risk_points <= 3 THEN 'Medium'
        ELSE 'High'
    END,
    '0.1.0'
FROM scored
ORDER BY customer_id;

COMMIT;
