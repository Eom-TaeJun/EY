/*
Purpose:
  Register a typed Wave 1 economic-transmission graph containing testable
  hypotheses and validated directional associations. No edge in this script is
  a causal estimate or model approval.
Input tables and evidence:
  audit.source_file, audit.pipeline_run, audit.reconciliation_result,
  audit.test_result, mart.signal_default_summary, the conceptual hypotheses in
  docs/methodology/transmission_paths.md, and the independently validated
  outputs/qa/validated/latest/wave1_independent_validation.json.
Output definition and grain:
  `economic_transmission` nodes represent one conceptual constraint/behavior,
  one observable metric, or one explicitly labelled next-month-default
  prototype. Edges represent one hypothesis or observed directional
  association with an expected sign, lag, status, and evidence reference.
Observation point:
  Signals are observed at 2005-09-30 and compared with the dataset-provided
  next-month outcome. Zero lag maps a concept to its contemporaneous proxy;
  one-month lag links a signal or pathway to that next-month prototype.
Main assumptions:
  Conceptual `causes` and `amplifies` edges have status `hypothesis`; they are
  not empirical causal claims. `explains` edges record directional separation
  only. The bill-growth expected sign remains positive but is marked
  contradicted; the zero-payment association is explicitly mixed because its
  validated buckets are non-monotonic.
Validation:
  The transaction fails closed unless the pinned run/source exists, execution
  is complete, no SQL/reconciliation failure exists, and the run-scoped
  summaries reproduce all required supported, contradicted, and mixed
  directions before any graph row is registered.
*/

\if :{?run_id}
\else
  \echo 'run_id is required: psql -v run_id=W1-20260727-001 ...'
  \quit 2
\endif

\if :{?source_sha256}
\else
  \echo 'source_sha256 is required: psql -v source_sha256=<sha256> ...'
  \quit 2
\endif

BEGIN;

SELECT set_config('credit_risk.economic_run_id', :'run_id', true);
SELECT set_config(
    'credit_risk.economic_source_sha256',
    :'source_sha256',
    true
);

DO $precondition$
DECLARE
    v_rate_1 numeric;
    v_rate_2 numeric;
    v_rate_3 numeric;
BEGIN
    IF current_setting('credit_risk.economic_run_id')
        <> 'W1-20260727-001' THEN
        RAISE EXCEPTION
            'run_id is not the independently validated Wave 1 run';
    END IF;

    IF current_setting('credit_risk.economic_source_sha256')
        <> '30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933'
    THEN
        RAISE EXCEPTION
            'source_sha256 does not match the independently validated source';
    END IF;

    IF to_regprocedure(
        'meta.register_node(text,text,text,text,text,text,text)'
    ) IS NULL
       OR to_regprocedure(
           'meta.register_edge(text,bigint,bigint,text,date,text,interval,text,date,text)'
       ) IS NULL THEN
        RAISE EXCEPTION
            'apply sql/ddl/030_meta_graph.sql before economic hypotheses';
    END IF;

    IF to_regclass('audit.source_file') IS NULL
       OR to_regclass('audit.pipeline_run') IS NULL
       OR to_regclass('audit.reconciliation_result') IS NULL
       OR to_regclass('audit.test_result') IS NULL
       OR to_regclass('mart.signal_default_summary') IS NULL THEN
        RAISE EXCEPTION
            'required Wave 1 audit or signal-summary object is absent';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM audit.source_file AS source_file
        WHERE source_file.source_id = 'uci_default_credit_card_clients'
          AND source_file.file_sha256
              = current_setting('credit_risk.economic_source_sha256')
    ) THEN
        RAISE EXCEPTION
            'validated source identity is absent from audit.source_file';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM audit.pipeline_run AS pipeline_run
        WHERE pipeline_run.pipeline_run_id
              = current_setting('credit_risk.economic_run_id')
          AND pipeline_run.source_id = 'uci_default_credit_card_clients'
          AND pipeline_run.source_file_sha256
              = current_setting('credit_risk.economic_source_sha256')
          AND pipeline_run.definition_version = '0.1.0'
          AND pipeline_run.observation_date = DATE '2005-09-30'
          AND pipeline_run.status IN ('succeeded', 'validated')
    ) THEN
        RAISE EXCEPTION
            'run/source/version identity is absent or not execution-complete';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM audit.reconciliation_result AS reconciliation
        WHERE reconciliation.pipeline_run_id
              = current_setting('credit_risk.economic_run_id')
          AND reconciliation.status = 'fail'
    ) OR EXISTS (
        SELECT 1
        FROM audit.test_result AS test_result
        WHERE test_result.pipeline_run_id
              = current_setting('credit_risk.economic_run_id')
          AND test_result.status = 'fail'
    ) THEN
        RAISE EXCEPTION
            'failed Wave 1 SQL or reconciliation evidence blocks graph registration';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM audit.reconciliation_result AS reconciliation
        WHERE reconciliation.pipeline_run_id
              = current_setting('credit_risk.economic_run_id')
    ) OR NOT EXISTS (
        SELECT 1
        FROM audit.test_result AS test_result
        WHERE test_result.pipeline_run_id
              = current_setting('credit_risk.economic_run_id')
    ) THEN
        RAISE EXCEPTION
            'executed Wave 1 SQL and reconciliation evidence is required';
    END IF;

    /* Higher recent delinquency severity must show the validated positive order. */
    SELECT
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '0'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '1'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '2+')
    INTO v_rate_1, v_rate_2, v_rate_3
    FROM mart.signal_default_summary AS summary
    WHERE summary.pipeline_run_id
          = current_setting('credit_risk.economic_run_id')
      AND summary.signal_name = 'recent_max_delinquency'
      AND summary.definition_version = '0.1.0';

    IF v_rate_1 IS NULL OR v_rate_2 IS NULL OR v_rate_3 IS NULL
       OR NOT (v_rate_1 < v_rate_2 AND v_rate_2 < v_rate_3) THEN
        RAISE EXCEPTION
            'recent_max_delinquency validated direction is absent';
    END IF;

    /* More delinquent months must show the validated positive order. */
    SELECT
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '0'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '1'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '2+')
    INTO v_rate_1, v_rate_2, v_rate_3
    FROM mart.signal_default_summary AS summary
    WHERE summary.pipeline_run_id
          = current_setting('credit_risk.economic_run_id')
      AND summary.signal_name = 'delinquent_months_6m'
      AND summary.definition_version = '0.1.0';

    IF v_rate_1 IS NULL OR v_rate_2 IS NULL OR v_rate_3 IS NULL
       OR NOT (v_rate_1 < v_rate_2 AND v_rate_2 < v_rate_3) THEN
        RAISE EXCEPTION
            'delinquent_months_6m validated direction is absent';
    END IF;

    /* Worsening delinquency must show the validated positive order. */
    SELECT
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '<=0'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '1'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '2+')
    INTO v_rate_1, v_rate_2, v_rate_3
    FROM mart.signal_default_summary AS summary
    WHERE summary.pipeline_run_id
          = current_setting('credit_risk.economic_run_id')
      AND summary.signal_name = 'delinquency_deterioration'
      AND summary.definition_version = '0.1.0';

    IF v_rate_1 IS NULL OR v_rate_2 IS NULL OR v_rate_3 IS NULL
       OR NOT (v_rate_1 < v_rate_2 AND v_rate_2 < v_rate_3) THEN
        RAISE EXCEPTION
            'delinquency_deterioration validated direction is absent';
    END IF;

    /* Higher utilization must show the validated positive order. */
    SELECT
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '<0.80'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '0.80-<1.00'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '>=1.00')
    INTO v_rate_1, v_rate_2, v_rate_3
    FROM mart.signal_default_summary AS summary
    WHERE summary.pipeline_run_id
          = current_setting('credit_risk.economic_run_id')
      AND summary.signal_name = 'latest_utilization_ratio'
      AND summary.definition_version = '0.1.0';

    IF v_rate_1 IS NULL OR v_rate_2 IS NULL OR v_rate_3 IS NULL
       OR NOT (v_rate_1 < v_rate_2 AND v_rate_2 < v_rate_3) THEN
        RAISE EXCEPTION
            'latest_utilization_ratio validated direction is absent';
    END IF;

    /* Higher payment coverage must show the validated negative order. */
    SELECT
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '<0.10'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '0.10-<0.50'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '>=0.50')
    INTO v_rate_1, v_rate_2, v_rate_3
    FROM mart.signal_default_summary AS summary
    WHERE summary.pipeline_run_id
          = current_setting('credit_risk.economic_run_id')
      AND summary.signal_name = 'payment_coverage_ratio'
      AND summary.definition_version = '0.1.0';

    IF v_rate_1 IS NULL OR v_rate_2 IS NULL OR v_rate_3 IS NULL
       OR NOT (v_rate_1 > v_rate_2 AND v_rate_2 > v_rate_3) THEN
        RAISE EXCEPTION
            'payment_coverage_ratio validated direction is absent';
    END IF;

    /* One zero-payment month exceeds two-plus, proving non-monotonicity. */
    SELECT
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '0'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '1'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '2+')
    INTO v_rate_1, v_rate_2, v_rate_3
    FROM mart.signal_default_summary AS summary
    WHERE summary.pipeline_run_id
          = current_setting('credit_risk.economic_run_id')
      AND summary.signal_name = 'zero_payment_streak'
      AND summary.definition_version = '0.1.0';

    IF v_rate_1 IS NULL OR v_rate_2 IS NULL OR v_rate_3 IS NULL
       OR NOT (v_rate_1 < v_rate_3 AND v_rate_3 < v_rate_2) THEN
        RAISE EXCEPTION
            'zero_payment_streak mixed validated pattern is absent';
    END IF;

    /* Higher recent bill growth reverses the positive ex-ante expectation. */
    SELECT
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '<=0'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '0-<0.25'),
        max(summary.observed_default_rate)
            FILTER (WHERE summary.signal_bucket = '>=0.25')
    INTO v_rate_1, v_rate_2, v_rate_3
    FROM mart.signal_default_summary AS summary
    WHERE summary.pipeline_run_id
          = current_setting('credit_risk.economic_run_id')
      AND summary.signal_name = 'recent_bill_growth'
      AND summary.definition_version = '0.1.0';

    IF v_rate_1 IS NULL OR v_rate_2 IS NULL OR v_rate_3 IS NULL
       OR NOT (v_rate_1 > v_rate_2 AND v_rate_2 > v_rate_3) THEN
        RAISE EXCEPTION
            'recent_bill_growth contradicted validated pattern is absent';
    END IF;
END;
$precondition$;

DO $register_graph$
DECLARE
    c_scope constant text := 'economic_transmission';
    c_version constant text := '0.1.0';
    c_valid_from constant date := DATE '2026-07-27';
    c_hypothesis_evidence constant text :=
        'docs/methodology/transmission_paths.md';
    c_observed_evidence constant text :=
        'outputs/qa/validated/latest/wave1_independent_validation.json';
    v_liquidity_constraint_id bigint;
    v_repayment_pressure_id bigint;
    v_low_buffer_id bigint;
    v_delinquency_persistence_id bigint;
    v_deterioration_id bigint;
    v_bill_pressure_id bigint;
    v_payment_coverage_id bigint;
    v_zero_payment_id bigint;
    v_utilization_id bigint;
    v_recent_max_delinquency_id bigint;
    v_delinquent_months_id bigint;
    v_delinquency_deterioration_id bigint;
    v_recent_bill_growth_id bigint;
    v_default_prototype_id bigint;
BEGIN
    v_liquidity_constraint_id := meta.register_node(
        c_scope,
        'Constraint',
        'economic.wave1.constraint.liquidity',
        c_version,
        'hypothesis',
        'Risk Signal',
        c_hypothesis_evidence
    );
    v_repayment_pressure_id := meta.register_node(
        c_scope,
        'Behavior',
        'economic.wave1.behavior.repayment_capacity_pressure',
        c_version,
        'hypothesis',
        'Risk Signal',
        c_hypothesis_evidence
    );
    v_low_buffer_id := meta.register_node(
        c_scope,
        'Constraint',
        'economic.wave1.constraint.low_remaining_liquidity_buffer',
        c_version,
        'hypothesis',
        'Risk Signal',
        c_hypothesis_evidence
    );
    v_delinquency_persistence_id := meta.register_node(
        c_scope,
        'Behavior',
        'economic.wave1.behavior.delinquency_persistence',
        c_version,
        'hypothesis',
        'Risk Signal',
        c_hypothesis_evidence
    );
    v_deterioration_id := meta.register_node(
        c_scope,
        'Behavior',
        'economic.wave1.behavior.repayment_deterioration',
        c_version,
        'hypothesis',
        'Risk Signal',
        c_hypothesis_evidence
    );
    v_bill_pressure_id := meta.register_node(
        c_scope,
        'Constraint',
        'economic.wave1.constraint.rising_bill_pressure',
        c_version,
        'contradicted_hypothesis',
        'Risk Signal',
        c_hypothesis_evidence
    );
    v_payment_coverage_id := meta.register_node(
        c_scope,
        'Metric',
        'economic.wave1.metric.payment_coverage_ratio',
        c_version,
        'supported_association',
        'Risk Signal',
        'mart.borrower_risk_signal.payment_coverage_ratio'
    );
    v_zero_payment_id := meta.register_node(
        c_scope,
        'Metric',
        'economic.wave1.metric.zero_payment_streak',
        c_version,
        'mixed_association',
        'Risk Signal',
        'mart.borrower_risk_signal.zero_payment_streak'
    );
    v_utilization_id := meta.register_node(
        c_scope,
        'Metric',
        'economic.wave1.metric.latest_utilization_ratio',
        c_version,
        'supported_association',
        'Risk Signal',
        'mart.borrower_risk_signal.latest_utilization_ratio'
    );
    v_recent_max_delinquency_id := meta.register_node(
        c_scope,
        'Metric',
        'economic.wave1.metric.recent_max_delinquency',
        c_version,
        'supported_association',
        'Risk Signal',
        'mart.borrower_risk_signal.recent_max_delinquency'
    );
    v_delinquent_months_id := meta.register_node(
        c_scope,
        'Metric',
        'economic.wave1.metric.delinquent_months_6m',
        c_version,
        'supported_association',
        'Risk Signal',
        'mart.borrower_risk_signal.delinquent_months_6m'
    );
    v_delinquency_deterioration_id := meta.register_node(
        c_scope,
        'Metric',
        'economic.wave1.metric.delinquency_deterioration',
        c_version,
        'supported_association',
        'Risk Signal',
        'mart.borrower_risk_signal.delinquency_deterioration'
    );
    v_recent_bill_growth_id := meta.register_node(
        c_scope,
        'Metric',
        'economic.wave1.metric.recent_bill_growth',
        c_version,
        'contradicted_hypothesis',
        'Risk Signal',
        'mart.borrower_risk_signal.recent_bill_growth'
    );
    v_default_prototype_id := meta.register_node(
        c_scope,
        'RiskComponent',
        'economic.wave1.risk_component.next_month_default_prototype',
        c_version,
        'prototype',
        'Risk Component',
        'mart.borrower_risk_signal.next_month_default'
    );

    /* Conceptual hypothesis edges: no causal estimate is asserted. */
    PERFORM meta.register_edge(
        c_scope,
        v_liquidity_constraint_id,
        v_repayment_pressure_id,
        'causes',
        c_valid_from,
        'positive',
        interval '0 months',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_repayment_pressure_id,
        v_payment_coverage_id,
        'observed_by',
        c_valid_from,
        'negative',
        interval '0 months',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_repayment_pressure_id,
        v_zero_payment_id,
        'observed_by',
        c_valid_from,
        'positive',
        interval '0 months',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_repayment_pressure_id,
        v_delinquency_persistence_id,
        'amplifies',
        c_valid_from,
        'positive',
        interval '1 month',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_low_buffer_id,
        v_utilization_id,
        'observed_by',
        c_valid_from,
        'positive',
        interval '0 months',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_low_buffer_id,
        v_default_prototype_id,
        'amplifies',
        c_valid_from,
        'positive',
        interval '1 month',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_delinquency_persistence_id,
        v_recent_max_delinquency_id,
        'observed_by',
        c_valid_from,
        'positive',
        interval '0 months',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_delinquency_persistence_id,
        v_delinquent_months_id,
        'observed_by',
        c_valid_from,
        'positive',
        interval '0 months',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_delinquency_persistence_id,
        v_default_prototype_id,
        'amplifies',
        c_valid_from,
        'positive',
        interval '1 month',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_deterioration_id,
        v_delinquency_deterioration_id,
        'observed_by',
        c_valid_from,
        'positive',
        interval '0 months',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_deterioration_id,
        v_default_prototype_id,
        'amplifies',
        c_valid_from,
        'positive',
        interval '1 month',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_bill_pressure_id,
        v_recent_bill_growth_id,
        'observed_by',
        c_valid_from,
        'positive',
        interval '0 months',
        c_hypothesis_evidence,
        NULL,
        'hypothesis'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_bill_pressure_id,
        v_default_prototype_id,
        'amplifies',
        c_valid_from,
        'positive',
        interval '1 month',
        c_observed_evidence,
        NULL,
        'contradicted_hypothesis'
    );

    /* Validated directional associations: no causality is inferred. */
    PERFORM meta.register_edge(
        c_scope,
        v_payment_coverage_id,
        v_default_prototype_id,
        'explains',
        c_valid_from,
        'negative',
        interval '1 month',
        c_observed_evidence,
        NULL,
        'supported_association'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_zero_payment_id,
        v_default_prototype_id,
        'explains',
        c_valid_from,
        'mixed',
        interval '1 month',
        c_observed_evidence,
        NULL,
        'mixed_association'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_utilization_id,
        v_default_prototype_id,
        'explains',
        c_valid_from,
        'positive',
        interval '1 month',
        c_observed_evidence,
        NULL,
        'supported_association'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_recent_max_delinquency_id,
        v_default_prototype_id,
        'explains',
        c_valid_from,
        'positive',
        interval '1 month',
        c_observed_evidence,
        NULL,
        'supported_association'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_delinquent_months_id,
        v_default_prototype_id,
        'explains',
        c_valid_from,
        'positive',
        interval '1 month',
        c_observed_evidence,
        NULL,
        'supported_association'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_delinquency_deterioration_id,
        v_default_prototype_id,
        'explains',
        c_valid_from,
        'positive',
        interval '1 month',
        c_observed_evidence,
        NULL,
        'supported_association'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_recent_bill_growth_id,
        v_default_prototype_id,
        'explains',
        c_valid_from,
        'positive',
        interval '1 month',
        c_observed_evidence,
        NULL,
        'contradicted_hypothesis'
    );
END;
$register_graph$;

COMMIT;
