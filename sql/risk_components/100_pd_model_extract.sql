/*
Purpose:
  Extract the reviewable borrower-level input for the Wave 2 PD prototype.
Input tables:
  core.borrower and mart.borrower_risk_signal for one supplied Wave 1 run.
Output definition:
  One row per borrower with static attributes, seven observation-time behavioral
  signals, outcome, source/run linkage, and risk band for diagnostics only.
Observation point:
  The run-scoped observation_date (2005-09-30 for W1-20260727-001); the outcome
  is the dataset-provided next-month default indicator.
Key assumptions:
  %(source_run_id)s is supplied as a psycopg named parameter. customer_id,
  next_month_default, observation_date, run/source metadata, risk_points, and
  risk_band are never model features. risk_band is returned only for segment
  diagnostics.
Validation:
  src/models/run_pd_prototype.py checks one-to-one grain, run/version/date
  consistency, target domain, feature exclusions, and row-count reconciliation.
*/

SET jit = off;

-- MODEL_QUERY_START
SELECT
    borrower.customer_id,
    borrower.next_month_default,
    borrower.observation_date,
    borrower.credit_limit_ntd,
    borrower.sex_code,
    borrower.education_code,
    borrower.marriage_code,
    borrower.age_years,
    signal.recent_max_delinquency,
    signal.delinquent_months_6m,
    signal.delinquency_deterioration,
    signal.latest_utilization_ratio,
    signal.payment_coverage_ratio,
    signal.zero_payment_streak,
    signal.recent_bill_growth,
    signal.risk_band,
    borrower.source_id,
    borrower.source_file_sha256,
    borrower.definition_version
FROM core.borrower AS borrower
JOIN mart.borrower_risk_signal AS signal
  ON signal.pipeline_run_id = borrower.pipeline_run_id
 AND signal.customer_id = borrower.customer_id
WHERE borrower.pipeline_run_id = %(source_run_id)s
ORDER BY borrower.customer_id;
