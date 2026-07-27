/*
Purpose:
  Create versioned core, mart, and audit structures for Wave 1.
Input tables:
  audit.source_file and raw.credit_card_client, created by the Hermes ingestion DDL.
Output definition:
  Run-scoped borrower/account-month facts, risk-signal marts, test results,
  reconciliations, and issues. No validated run is overwritten.
Observation point:
  Borrower signals are observed at 2005-09-30; the source outcome is the
  dataset-provided next-month default indicator.
Key assumptions:
  Business grain is evaluated within pipeline_run_id. Stage, LGD, EAD, and ECL
  are outside Wave 1 and are not represented as actual risk components.
Validation:
  sql/reconciliation/030_core_reconciliation.sql and
  sql/quality/040_data_quality.sql populate independent audit evidence.
*/

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS audit.pipeline_run (
    pipeline_run_id text PRIMARY KEY,
    run_type text NOT NULL,
    source_id text NOT NULL,
    source_file_sha256 text NOT NULL,
    definition_version text NOT NULL,
    observation_date date NOT NULL,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    status text NOT NULL CHECK (
        status IN ('building', 'succeeded', 'failed', 'validated')
    ),
    error_message text,
    FOREIGN KEY (source_id, source_file_sha256)
        REFERENCES audit.source_file (source_id, file_sha256)
);

CREATE TABLE IF NOT EXISTS core.borrower (
    pipeline_run_id text NOT NULL,
    customer_id integer NOT NULL,
    credit_limit_ntd integer NOT NULL,
    sex_code integer NOT NULL,
    education_code integer NOT NULL,
    marriage_code integer NOT NULL,
    age_years integer NOT NULL,
    next_month_default integer NOT NULL,
    observation_date date NOT NULL,
    source_id text NOT NULL,
    source_file_sha256 text NOT NULL,
    definition_version text NOT NULL,
    PRIMARY KEY (pipeline_run_id, customer_id),
    FOREIGN KEY (pipeline_run_id)
        REFERENCES audit.pipeline_run (pipeline_run_id),
    FOREIGN KEY (source_id, source_file_sha256)
        REFERENCES audit.source_file (source_id, file_sha256)
);

CREATE TABLE IF NOT EXISTS core.account_month (
    pipeline_run_id text NOT NULL,
    customer_id integer NOT NULL,
    month_offset smallint NOT NULL CHECK (month_offset BETWEEN -5 AND 0),
    statement_month_end date NOT NULL,
    repayment_status integer NOT NULL,
    bill_amount_ntd integer NOT NULL,
    payment_amount_ntd integer NOT NULL,
    repayment_source_field text NOT NULL,
    bill_source_field text NOT NULL,
    payment_source_field text NOT NULL,
    definition_version text NOT NULL,
    PRIMARY KEY (pipeline_run_id, customer_id, month_offset),
    FOREIGN KEY (pipeline_run_id, customer_id)
        REFERENCES core.borrower (pipeline_run_id, customer_id)
);

CREATE INDEX IF NOT EXISTS account_month_customer_time_idx
    ON core.account_month (pipeline_run_id, customer_id, statement_month_end);

CREATE TABLE IF NOT EXISTS audit.reconciliation_result (
    pipeline_run_id text NOT NULL,
    reconciliation_id text NOT NULL,
    metric_name text NOT NULL,
    source_value numeric NOT NULL,
    derived_value numeric NOT NULL,
    difference numeric NOT NULL,
    tolerance numeric NOT NULL CHECK (tolerance >= 0),
    status text NOT NULL CHECK (status IN ('pass', 'fail')),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (pipeline_run_id, reconciliation_id),
    FOREIGN KEY (pipeline_run_id)
        REFERENCES audit.pipeline_run (pipeline_run_id)
);

CREATE TABLE IF NOT EXISTS audit.test_result (
    pipeline_run_id text NOT NULL,
    test_id text NOT NULL,
    test_name text NOT NULL,
    test_type text NOT NULL CHECK (
        test_type IN ('data_quality', 'business_rule', 'reconciliation', 'leakage')
    ),
    status text NOT NULL CHECK (status IN ('pass', 'fail', 'warn')),
    severity text NOT NULL CHECK (
        severity IN ('critical', 'high', 'medium', 'low', 'analytical_flag')
    ),
    tested_rows bigint NOT NULL CHECK (tested_rows >= 0),
    failed_rows bigint NOT NULL CHECK (failed_rows >= 0),
    failure_rate numeric NOT NULL CHECK (failure_rate BETWEEN 0 AND 1),
    affected_object text NOT NULL,
    evidence_query text NOT NULL,
    sample_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (pipeline_run_id, test_id),
    FOREIGN KEY (pipeline_run_id)
        REFERENCES audit.pipeline_run (pipeline_run_id)
);

CREATE TABLE IF NOT EXISTS audit.issue_log (
    issue_id text PRIMARY KEY,
    opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    owner text NOT NULL,
    severity text NOT NULL CHECK (
        severity IN ('Critical', 'High', 'Medium', 'Low')
    ),
    gate text NOT NULL,
    status text NOT NULL CHECK (
        status IN ('Open', 'Blocked', 'In Progress', 'Resolved', 'Accepted Risk')
    ),
    summary text NOT NULL,
    impact text NOT NULL,
    evidence text NOT NULL,
    resolution text,
    pipeline_run_id text,
    FOREIGN KEY (pipeline_run_id)
        REFERENCES audit.pipeline_run (pipeline_run_id)
);

CREATE TABLE IF NOT EXISTS mart.borrower_risk_signal (
    pipeline_run_id text NOT NULL,
    customer_id integer NOT NULL,
    observation_date date NOT NULL,
    next_month_default integer NOT NULL CHECK (next_month_default IN (0, 1)),
    recent_max_delinquency integer NOT NULL,
    delinquent_months_6m integer NOT NULL CHECK (delinquent_months_6m BETWEEN 0 AND 6),
    delinquency_deterioration integer NOT NULL,
    latest_utilization_ratio numeric,
    payment_coverage_ratio numeric,
    zero_payment_streak integer NOT NULL CHECK (zero_payment_streak BETWEEN 0 AND 6),
    recent_bill_growth numeric,
    risk_points integer NOT NULL CHECK (risk_points BETWEEN 0 AND 10),
    risk_band text NOT NULL CHECK (risk_band IN ('Low', 'Medium', 'High')),
    definition_version text NOT NULL,
    PRIMARY KEY (pipeline_run_id, customer_id),
    FOREIGN KEY (pipeline_run_id, customer_id)
        REFERENCES core.borrower (pipeline_run_id, customer_id)
);

CREATE TABLE IF NOT EXISTS mart.signal_default_summary (
    pipeline_run_id text NOT NULL,
    signal_name text NOT NULL,
    signal_bucket text NOT NULL,
    bucket_order integer NOT NULL,
    sample_size integer NOT NULL CHECK (sample_size > 0),
    default_count integer NOT NULL CHECK (default_count BETWEEN 0 AND sample_size),
    observed_default_rate numeric NOT NULL CHECK (
        observed_default_rate BETWEEN 0 AND 1
    ),
    definition_version text NOT NULL,
    PRIMARY KEY (pipeline_run_id, signal_name, signal_bucket),
    FOREIGN KEY (pipeline_run_id)
        REFERENCES audit.pipeline_run (pipeline_run_id)
);

CREATE TABLE IF NOT EXISTS mart.risk_band_summary (
    pipeline_run_id text NOT NULL,
    risk_band text NOT NULL CHECK (risk_band IN ('Low', 'Medium', 'High')),
    band_order integer NOT NULL CHECK (band_order BETWEEN 1 AND 3),
    sample_size integer NOT NULL CHECK (sample_size > 0),
    default_count integer NOT NULL CHECK (default_count BETWEEN 0 AND sample_size),
    observed_default_rate numeric NOT NULL CHECK (
        observed_default_rate BETWEEN 0 AND 1
    ),
    definition_version text NOT NULL,
    PRIMARY KEY (pipeline_run_id, risk_band),
    FOREIGN KEY (pipeline_run_id)
        REFERENCES audit.pipeline_run (pipeline_run_id)
);
