/*
Purpose:
  Verify exact Wave 1 economic-hypothesis graph identity, idempotency, scope,
  type, status, expected-sign, lag, and evidence controls.
Input tables:
  `meta.node` and `meta.edge` after
  `sql/ddl/032_wave1_economic_hypotheses.sql`.
Output definition and grain:
  No durable output. Assertions cover the complete
  `economic.wave1.%` node/edge set and roll back idempotency replays.
Observation point:
  Wave 1 signals are observed at 2005-09-30 and the prototype outcome is the
  dataset-provided next-month indicator.
Main assumptions:
  Hypothesis status does not assert causality. Supported, mixed, and
  contradicted statuses describe validated directional association only.
Validation:
  A zero exit code with `ON_ERROR_STOP=1` proves the exact graph contract.
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

SELECT set_config('credit_risk.economic_test_run_id', :'run_id', true);
SELECT set_config(
    'credit_risk.economic_test_source_sha256',
    :'source_sha256',
    true
);

DO $graph_test$
DECLARE
    c_scope constant text := 'economic_transmission';
    c_version constant text := '0.1.0';
    c_valid_from constant date := DATE '2026-07-27';
    c_hypothesis_evidence constant text :=
        'docs/methodology/transmission_paths.md';
    c_observed_evidence constant text :=
        'outputs/qa/validated/latest/wave1_independent_validation.json';
    v_metric_node_id bigint;
    v_default_node_id bigint;
    v_existing_edge_id bigint;
    v_replayed_edge_id bigint;
BEGIN
    IF current_setting('credit_risk.economic_test_run_id')
        <> 'W1-20260727-001'
       OR current_setting('credit_risk.economic_test_source_sha256')
        <> '30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933'
    THEN
        RAISE EXCEPTION
            'test inputs do not match the validated Wave 1 identity';
    END IF;

    IF (
        SELECT count(*)
        FROM meta.node AS node
        WHERE node.graph_scope = c_scope
          AND node.canonical_name LIKE 'economic.wave1.%'
          AND node.version = c_version
    ) <> 14 THEN
        RAISE EXCEPTION
            'economic Wave 1 graph must contain exactly 14 versioned nodes';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM meta.node AS node
        WHERE node.canonical_name LIKE 'economic.wave1.%'
          AND node.graph_scope <> c_scope
    ) THEN
        RAISE EXCEPTION
            'economic Wave 1 node exists outside economic_transmission';
    END IF;

    IF (
        SELECT count(*)
        FROM meta.node AS node
        WHERE node.graph_scope = c_scope
          AND node.canonical_name LIKE 'economic.wave1.%'
          AND (
              (node.node_type = 'Constraint' AND node.status IN (
                  'hypothesis',
                  'contradicted_hypothesis'
              ))
              OR (node.node_type = 'Behavior' AND node.status = 'hypothesis')
              OR (node.node_type = 'Metric' AND node.status IN (
                  'supported_association',
                  'mixed_association',
                  'contradicted_hypothesis'
              ))
              OR (node.node_type = 'RiskComponent' AND node.status = 'prototype')
          )
    ) <> 14 THEN
        RAISE EXCEPTION
            'economic Wave 1 node type/status contract is incomplete';
    END IF;

    IF EXISTS (
        WITH expected_node (
            canonical_name,
            node_type,
            status,
            path_or_object
        ) AS (
            VALUES
                (
                    'economic.wave1.constraint.liquidity',
                    'Constraint',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.repayment_capacity_pressure',
                    'Behavior',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.constraint.low_remaining_liquidity_buffer',
                    'Constraint',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.delinquency_persistence',
                    'Behavior',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.repayment_deterioration',
                    'Behavior',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.constraint.rising_bill_pressure',
                    'Constraint',
                    'contradicted_hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.metric.payment_coverage_ratio',
                    'Metric',
                    'supported_association',
                    'mart.borrower_risk_signal.payment_coverage_ratio'
                ),
                (
                    'economic.wave1.metric.zero_payment_streak',
                    'Metric',
                    'mixed_association',
                    'mart.borrower_risk_signal.zero_payment_streak'
                ),
                (
                    'economic.wave1.metric.latest_utilization_ratio',
                    'Metric',
                    'supported_association',
                    'mart.borrower_risk_signal.latest_utilization_ratio'
                ),
                (
                    'economic.wave1.metric.recent_max_delinquency',
                    'Metric',
                    'supported_association',
                    'mart.borrower_risk_signal.recent_max_delinquency'
                ),
                (
                    'economic.wave1.metric.delinquent_months_6m',
                    'Metric',
                    'supported_association',
                    'mart.borrower_risk_signal.delinquent_months_6m'
                ),
                (
                    'economic.wave1.metric.delinquency_deterioration',
                    'Metric',
                    'supported_association',
                    'mart.borrower_risk_signal.delinquency_deterioration'
                ),
                (
                    'economic.wave1.metric.recent_bill_growth',
                    'Metric',
                    'contradicted_hypothesis',
                    'mart.borrower_risk_signal.recent_bill_growth'
                ),
                (
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'RiskComponent',
                    'prototype',
                    'mart.borrower_risk_signal.next_month_default'
                )
        )
        SELECT 1
        FROM expected_node AS expected
        WHERE NOT EXISTS (
            SELECT 1
            FROM meta.node AS actual
            WHERE actual.graph_scope = c_scope
              AND actual.canonical_name = expected.canonical_name
              AND actual.version = c_version
              AND actual.node_type = expected.node_type
              AND actual.status = expected.status
              AND actual.path_or_object = expected.path_or_object
        )
    ) THEN
        RAISE EXCEPTION
            'exact economic Wave 1 node mapping is incomplete';
    END IF;

    IF (
        SELECT count(*)
        FROM meta.edge AS edge
        JOIN meta.node AS from_node
          ON from_node.graph_scope = edge.graph_scope
         AND from_node.node_id = edge.from_node_id
        JOIN meta.node AS to_node
          ON to_node.graph_scope = edge.graph_scope
         AND to_node.node_id = edge.to_node_id
        WHERE edge.graph_scope = c_scope
          AND from_node.canonical_name LIKE 'economic.wave1.%'
          AND to_node.canonical_name LIKE 'economic.wave1.%'
          AND edge.valid_from = c_valid_from
    ) <> 20 THEN
        RAISE EXCEPTION
            'economic Wave 1 graph must contain exactly 20 typed edges';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM meta.edge AS edge
        JOIN meta.node AS from_node
          ON from_node.node_id = edge.from_node_id
        JOIN meta.node AS to_node
          ON to_node.node_id = edge.to_node_id
        WHERE (
            from_node.canonical_name LIKE 'economic.wave1.%'
            OR to_node.canonical_name LIKE 'economic.wave1.%'
        )
          AND (
              edge.graph_scope <> c_scope
              OR from_node.graph_scope <> c_scope
              OR to_node.graph_scope <> c_scope
          )
    ) THEN
        RAISE EXCEPTION
            'economic Wave 1 cross-scope edge exists';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM meta.edge AS edge
        JOIN meta.node AS from_node
          ON from_node.graph_scope = edge.graph_scope
         AND from_node.node_id = edge.from_node_id
        JOIN meta.node AS to_node
          ON to_node.graph_scope = edge.graph_scope
         AND to_node.node_id = edge.to_node_id
        WHERE edge.graph_scope = c_scope
          AND from_node.canonical_name LIKE 'economic.wave1.%'
          AND to_node.canonical_name LIKE 'economic.wave1.%'
          AND (
              edge.edge_type NOT IN (
                  'causes',
                  'amplifies',
                  'observed_by',
                  'explains'
              )
              OR edge.expected_sign IS NULL
              OR edge.lag IS NULL
              OR edge.valid_to IS NOT NULL
              OR edge.evidence_reference NOT IN (
                  c_hypothesis_evidence,
                  c_observed_evidence
              )
              OR edge.status NOT IN (
                  'hypothesis',
                  'supported_association',
                  'mixed_association',
                  'contradicted_hypothesis'
              )
          )
    ) THEN
        RAISE EXCEPTION
            'economic Wave 1 edge type/status/sign/lag/evidence contract failed';
    END IF;

    IF EXISTS (
        WITH expected_edge (
            from_name,
            to_name,
            edge_type,
            expected_sign,
            lag,
            status,
            evidence_reference
        ) AS (
            VALUES
                (
                    'economic.wave1.constraint.liquidity',
                    'economic.wave1.behavior.repayment_capacity_pressure',
                    'causes',
                    'positive',
                    interval '0 months',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.repayment_capacity_pressure',
                    'economic.wave1.metric.payment_coverage_ratio',
                    'observed_by',
                    'negative',
                    interval '0 months',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.repayment_capacity_pressure',
                    'economic.wave1.metric.zero_payment_streak',
                    'observed_by',
                    'positive',
                    interval '0 months',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.repayment_capacity_pressure',
                    'economic.wave1.behavior.delinquency_persistence',
                    'amplifies',
                    'positive',
                    interval '1 month',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.constraint.low_remaining_liquidity_buffer',
                    'economic.wave1.metric.latest_utilization_ratio',
                    'observed_by',
                    'positive',
                    interval '0 months',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.constraint.low_remaining_liquidity_buffer',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'amplifies',
                    'positive',
                    interval '1 month',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.delinquency_persistence',
                    'economic.wave1.metric.recent_max_delinquency',
                    'observed_by',
                    'positive',
                    interval '0 months',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.delinquency_persistence',
                    'economic.wave1.metric.delinquent_months_6m',
                    'observed_by',
                    'positive',
                    interval '0 months',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.delinquency_persistence',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'amplifies',
                    'positive',
                    interval '1 month',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.repayment_deterioration',
                    'economic.wave1.metric.delinquency_deterioration',
                    'observed_by',
                    'positive',
                    interval '0 months',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.behavior.repayment_deterioration',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'amplifies',
                    'positive',
                    interval '1 month',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.constraint.rising_bill_pressure',
                    'economic.wave1.metric.recent_bill_growth',
                    'observed_by',
                    'positive',
                    interval '0 months',
                    'hypothesis',
                    c_hypothesis_evidence
                ),
                (
                    'economic.wave1.constraint.rising_bill_pressure',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'amplifies',
                    'positive',
                    interval '1 month',
                    'contradicted_hypothesis',
                    c_observed_evidence
                ),
                (
                    'economic.wave1.metric.payment_coverage_ratio',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'explains',
                    'negative',
                    interval '1 month',
                    'supported_association',
                    c_observed_evidence
                ),
                (
                    'economic.wave1.metric.zero_payment_streak',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'explains',
                    'mixed',
                    interval '1 month',
                    'mixed_association',
                    c_observed_evidence
                ),
                (
                    'economic.wave1.metric.latest_utilization_ratio',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'explains',
                    'positive',
                    interval '1 month',
                    'supported_association',
                    c_observed_evidence
                ),
                (
                    'economic.wave1.metric.recent_max_delinquency',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'explains',
                    'positive',
                    interval '1 month',
                    'supported_association',
                    c_observed_evidence
                ),
                (
                    'economic.wave1.metric.delinquent_months_6m',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'explains',
                    'positive',
                    interval '1 month',
                    'supported_association',
                    c_observed_evidence
                ),
                (
                    'economic.wave1.metric.delinquency_deterioration',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'explains',
                    'positive',
                    interval '1 month',
                    'supported_association',
                    c_observed_evidence
                ),
                (
                    'economic.wave1.metric.recent_bill_growth',
                    'economic.wave1.risk_component.next_month_default_prototype',
                    'explains',
                    'positive',
                    interval '1 month',
                    'contradicted_hypothesis',
                    c_observed_evidence
                )
        )
        SELECT 1
        FROM expected_edge AS expected
        WHERE NOT EXISTS (
            SELECT 1
            FROM meta.edge AS actual_edge
            JOIN meta.node AS actual_from
              ON actual_from.graph_scope = actual_edge.graph_scope
             AND actual_from.node_id = actual_edge.from_node_id
            JOIN meta.node AS actual_to
              ON actual_to.graph_scope = actual_edge.graph_scope
             AND actual_to.node_id = actual_edge.to_node_id
            WHERE actual_edge.graph_scope = c_scope
              AND actual_from.canonical_name = expected.from_name
              AND actual_to.canonical_name = expected.to_name
              AND actual_edge.edge_type = expected.edge_type
              AND actual_edge.expected_sign = expected.expected_sign
              AND actual_edge.lag = expected.lag
              AND actual_edge.status = expected.status
              AND actual_edge.evidence_reference =
                  expected.evidence_reference
              AND actual_edge.valid_from = c_valid_from
              AND actual_edge.valid_to IS NULL
        )
    ) THEN
        RAISE EXCEPTION
            'exact economic Wave 1 edge mapping is incomplete';
    END IF;

    IF (
        SELECT count(*)
        FROM meta.edge AS edge
        JOIN meta.node AS metric
          ON metric.graph_scope = edge.graph_scope
         AND metric.node_id = edge.from_node_id
        JOIN meta.node AS prototype
          ON prototype.graph_scope = edge.graph_scope
         AND prototype.node_id = edge.to_node_id
        WHERE edge.graph_scope = c_scope
          AND metric.node_type = 'Metric'
          AND metric.canonical_name LIKE 'economic.wave1.metric.%'
          AND prototype.canonical_name =
              'economic.wave1.risk_component.next_month_default_prototype'
          AND edge.edge_type = 'explains'
          AND edge.lag = interval '1 month'
          AND edge.evidence_reference = c_observed_evidence
    ) <> 7 THEN
        RAISE EXCEPTION
            'seven observed metric-to-prototype associations are required';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM meta.edge AS edge
        JOIN meta.node AS metric
          ON metric.graph_scope = edge.graph_scope
         AND metric.node_id = edge.from_node_id
        JOIN meta.node AS prototype
          ON prototype.graph_scope = edge.graph_scope
         AND prototype.node_id = edge.to_node_id
        WHERE metric.canonical_name =
              'economic.wave1.metric.payment_coverage_ratio'
          AND prototype.canonical_name =
              'economic.wave1.risk_component.next_month_default_prototype'
          AND edge.expected_sign = 'negative'
          AND edge.status = 'supported_association'
    ) OR NOT EXISTS (
        SELECT 1
        FROM meta.edge AS edge
        JOIN meta.node AS metric
          ON metric.graph_scope = edge.graph_scope
         AND metric.node_id = edge.from_node_id
        JOIN meta.node AS prototype
          ON prototype.graph_scope = edge.graph_scope
         AND prototype.node_id = edge.to_node_id
        WHERE metric.canonical_name =
              'economic.wave1.metric.zero_payment_streak'
          AND prototype.canonical_name =
              'economic.wave1.risk_component.next_month_default_prototype'
          AND edge.expected_sign = 'mixed'
          AND edge.status = 'mixed_association'
    ) OR NOT EXISTS (
        SELECT 1
        FROM meta.edge AS edge
        JOIN meta.node AS metric
          ON metric.graph_scope = edge.graph_scope
         AND metric.node_id = edge.from_node_id
        JOIN meta.node AS prototype
          ON prototype.graph_scope = edge.graph_scope
         AND prototype.node_id = edge.to_node_id
        WHERE metric.canonical_name =
              'economic.wave1.metric.recent_bill_growth'
          AND prototype.canonical_name =
              'economic.wave1.risk_component.next_month_default_prototype'
          AND edge.expected_sign = 'positive'
          AND edge.status = 'contradicted_hypothesis'
    ) THEN
        RAISE EXCEPTION
            'negative, mixed, or contradicted association is misclassified';
    END IF;

    SELECT metric.node_id
    INTO STRICT v_metric_node_id
    FROM meta.node AS metric
    WHERE metric.graph_scope = c_scope
      AND metric.canonical_name =
          'economic.wave1.metric.zero_payment_streak'
      AND metric.version = c_version;

    IF meta.register_node(
        c_scope,
        'Metric',
        'economic.wave1.metric.zero_payment_streak',
        c_version,
        'mixed_association',
        'Risk Signal',
        'mart.borrower_risk_signal.zero_payment_streak'
    ) <> v_metric_node_id THEN
        RAISE EXCEPTION
            'exact node replay did not return the existing identifier';
    END IF;

    SELECT prototype.node_id
    INTO STRICT v_default_node_id
    FROM meta.node AS prototype
    WHERE prototype.graph_scope = c_scope
      AND prototype.canonical_name =
          'economic.wave1.risk_component.next_month_default_prototype'
      AND prototype.version = c_version;

    SELECT edge.edge_id
    INTO STRICT v_existing_edge_id
    FROM meta.edge AS edge
    WHERE edge.graph_scope = c_scope
      AND edge.from_node_id = v_metric_node_id
      AND edge.to_node_id = v_default_node_id
      AND edge.edge_type = 'explains'
      AND edge.valid_from = c_valid_from;

    v_replayed_edge_id := meta.register_edge(
        c_scope,
        v_metric_node_id,
        v_default_node_id,
        'explains',
        c_valid_from,
        'mixed',
        interval '1 month',
        c_observed_evidence,
        NULL,
        'mixed_association'
    );

    IF v_replayed_edge_id <> v_existing_edge_id THEN
        RAISE EXCEPTION
            'exact edge replay did not return the existing identifier';
    END IF;
END;
$graph_test$;

ROLLBACK;
