/*
Purpose:
  Calculate observed next-month default sample sizes, counts, and rates by
  every approved Wave 1 signal and by initial explainable risk band.
Input tables:
  mart.borrower_risk_signal.
Output definition:
  mart.signal_default_summary and mart.risk_band_summary for one run ID.
Observation point:
  Signals at 2005-09-30; dataset-provided next-month default outcome.
Key assumptions:
  Buckets and risk-band thresholds are definition version 0.1.0 and were fixed
  before outcome inspection. Null ratio buckets mean the denominator was not
  economically applicable (for example a non-positive prior bill).
Validation:
  All signal buckets and risk bands must reconcile to the same 30,000 borrowers
  and portfolio default count; the independent snapshot reproduces the rates.
*/

\if :{?run_id}
\else
  \echo 'run_id is required: psql -v run_id=...'
  \quit 2
\endif

BEGIN;
SET LOCAL jit = off;
SELECT set_config('credit_risk.run_id', :'run_id', false);

WITH bucketed AS (
    SELECT
        pipeline_run_id,
        next_month_default,
        'recent_max_delinquency'::text AS signal_name,
        CASE
            WHEN recent_max_delinquency = 0 THEN '0'
            WHEN recent_max_delinquency = 1 THEN '1'
            ELSE '2+'
        END AS signal_bucket,
        CASE
            WHEN recent_max_delinquency = 0 THEN 1
            WHEN recent_max_delinquency = 1 THEN 2
            ELSE 3
        END AS bucket_order
    FROM mart.borrower_risk_signal
    WHERE pipeline_run_id = current_setting('credit_risk.run_id')
    UNION ALL
    SELECT pipeline_run_id, next_month_default, 'delinquent_months_6m',
        CASE WHEN delinquent_months_6m = 0 THEN '0'
             WHEN delinquent_months_6m = 1 THEN '1' ELSE '2+' END,
        CASE WHEN delinquent_months_6m = 0 THEN 1
             WHEN delinquent_months_6m = 1 THEN 2 ELSE 3 END
    FROM mart.borrower_risk_signal
    WHERE pipeline_run_id = current_setting('credit_risk.run_id')
    UNION ALL
    SELECT pipeline_run_id, next_month_default, 'delinquency_deterioration',
        CASE WHEN delinquency_deterioration <= 0 THEN '<=0'
             WHEN delinquency_deterioration = 1 THEN '1' ELSE '2+' END,
        CASE WHEN delinquency_deterioration <= 0 THEN 1
             WHEN delinquency_deterioration = 1 THEN 2 ELSE 3 END
    FROM mart.borrower_risk_signal
    WHERE pipeline_run_id = current_setting('credit_risk.run_id')
    UNION ALL
    SELECT pipeline_run_id, next_month_default, 'latest_utilization_ratio',
        CASE WHEN latest_utilization_ratio < 0.80 THEN '<0.80'
             WHEN latest_utilization_ratio < 1 THEN '0.80-<1.00'
             ELSE '>=1.00' END,
        CASE WHEN latest_utilization_ratio < 0.80 THEN 1
             WHEN latest_utilization_ratio < 1 THEN 2 ELSE 3 END
    FROM mart.borrower_risk_signal
    WHERE pipeline_run_id = current_setting('credit_risk.run_id')
    UNION ALL
    SELECT pipeline_run_id, next_month_default, 'payment_coverage_ratio',
        CASE WHEN payment_coverage_ratio IS NULL THEN 'not_applicable'
             WHEN payment_coverage_ratio < 0.10 THEN '<0.10'
             WHEN payment_coverage_ratio < 0.50 THEN '0.10-<0.50'
             ELSE '>=0.50' END,
        CASE WHEN payment_coverage_ratio IS NULL THEN 1
             WHEN payment_coverage_ratio < 0.10 THEN 2
             WHEN payment_coverage_ratio < 0.50 THEN 3 ELSE 4 END
    FROM mart.borrower_risk_signal
    WHERE pipeline_run_id = current_setting('credit_risk.run_id')
    UNION ALL
    SELECT pipeline_run_id, next_month_default, 'zero_payment_streak',
        CASE WHEN zero_payment_streak = 0 THEN '0'
             WHEN zero_payment_streak = 1 THEN '1' ELSE '2+' END,
        CASE WHEN zero_payment_streak = 0 THEN 1
             WHEN zero_payment_streak = 1 THEN 2 ELSE 3 END
    FROM mart.borrower_risk_signal
    WHERE pipeline_run_id = current_setting('credit_risk.run_id')
    UNION ALL
    SELECT pipeline_run_id, next_month_default, 'recent_bill_growth',
        CASE WHEN recent_bill_growth IS NULL THEN 'not_applicable'
             WHEN recent_bill_growth <= 0 THEN '<=0'
             WHEN recent_bill_growth < 0.25 THEN '0-<0.25'
             ELSE '>=0.25' END,
        CASE WHEN recent_bill_growth IS NULL THEN 1
             WHEN recent_bill_growth <= 0 THEN 2
             WHEN recent_bill_growth < 0.25 THEN 3 ELSE 4 END
    FROM mart.borrower_risk_signal
    WHERE pipeline_run_id = current_setting('credit_risk.run_id')
)
INSERT INTO mart.signal_default_summary (
    pipeline_run_id,
    signal_name,
    signal_bucket,
    bucket_order,
    sample_size,
    default_count,
    observed_default_rate,
    definition_version
)
SELECT
    pipeline_run_id,
    signal_name,
    signal_bucket,
    bucket_order,
    count(*)::integer,
    sum(next_month_default)::integer,
    avg(next_month_default::numeric),
    '0.1.0'
FROM bucketed
GROUP BY pipeline_run_id, signal_name, signal_bucket, bucket_order
ORDER BY signal_name, bucket_order;

INSERT INTO mart.risk_band_summary (
    pipeline_run_id,
    risk_band,
    band_order,
    sample_size,
    default_count,
    observed_default_rate,
    definition_version
)
SELECT
    pipeline_run_id,
    risk_band,
    CASE risk_band WHEN 'Low' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
    count(*)::integer,
    sum(next_month_default)::integer,
    avg(next_month_default::numeric),
    '0.1.0'
FROM mart.borrower_risk_signal
WHERE pipeline_run_id = current_setting('credit_risk.run_id')
GROUP BY pipeline_run_id, risk_band
ORDER BY CASE risk_band WHEN 'Low' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END;

COMMIT;
