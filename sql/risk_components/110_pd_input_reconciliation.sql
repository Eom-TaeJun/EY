/*
Purpose:
  Reconcile the Wave 2 PD input population to validated Wave 1 borrower/signal
  tables without fitting or approving a model.
Input tables:
  core.borrower and mart.borrower_risk_signal for a supplied pipeline run.
Output definition:
  One row of counts, outcome totals, source/hash/version cardinalities, and join
  coverage differences.
Observation point:
  The run-scoped borrower observation_date; no post-observation feature is read.
Key assumptions:
  :source_run_id is a validated Wave 1 pipeline run. Exact row and key coverage
  are required; no tolerance or missing-row imputation is permitted.
Validation:
  borrower_rows = signal_rows = joined_rows = distinct_joined_borrowers,
  borrower_without_signal = signal_without_borrower = 0, and metadata
  cardinalities = 1.
*/

\if :{?source_run_id}
\else
  \echo 'source_run_id is required: psql -v source_run_id=...'
  \quit 2
\endif

BEGIN;
SET LOCAL jit = off;

WITH borrower AS (
    SELECT
        customer_id,
        next_month_default,
        source_id,
        source_file_sha256,
        definition_version,
        observation_date
    FROM core.borrower
    WHERE pipeline_run_id = :'source_run_id'
),
signal AS (
    SELECT customer_id
    FROM mart.borrower_risk_signal
    WHERE pipeline_run_id = :'source_run_id'
),
joined AS (
    SELECT borrower.*
    FROM borrower
    JOIN signal USING (customer_id)
)
SELECT
    (SELECT count(*) FROM borrower) AS borrower_rows,
    (SELECT count(*) FROM signal) AS signal_rows,
    (SELECT count(*) FROM joined) AS joined_rows,
    (SELECT count(DISTINCT customer_id) FROM joined) AS distinct_joined_borrowers,
    (SELECT count(*) FROM borrower LEFT JOIN signal USING (customer_id)
       WHERE signal.customer_id IS NULL) AS borrower_without_signal,
    (SELECT count(*) FROM signal LEFT JOIN borrower USING (customer_id)
       WHERE borrower.customer_id IS NULL) AS signal_without_borrower,
    (SELECT sum(next_month_default) FROM joined) AS observed_defaults,
    (SELECT count(DISTINCT source_id) FROM joined) AS source_id_count,
    (SELECT count(DISTINCT source_file_sha256) FROM joined) AS source_hash_count,
    (SELECT count(DISTINCT definition_version) FROM joined) AS definition_version_count,
    (SELECT count(DISTINCT observation_date) FROM joined) AS observation_date_count;

COMMIT;
