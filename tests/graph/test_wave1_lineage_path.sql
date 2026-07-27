/*
Purpose:
  Prove the bounded, claim-to-source Wave 1 dependency path and graph-scope
  integrity after deterministic lineage registration.
Input tables:
  `meta.node` and `meta.edge` populated by `sql/ddl/031_wave1_lineage.sql`.
Output definition and grain:
  No durable output. One assertion is evaluated for each of the seven validated
  Feature nodes, and the script raises on any missing exact path.
Observation point:
  Wave 1 definitions observe 2005-09-30; the graph path was validated on
  2026-07-27 for the supplied run and source hash.
Main assumptions:
  Claim-to-source traversal follows only `computed_from` and `validated_by`.
  A maximum recursion depth of 12 bounds the expected depth-10 path.
Validation:
  A zero exit code with `ON_ERROR_STOP=1` proves all seven exact paths and
  confirms every stored edge scope matches both endpoint scopes.
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

SELECT set_config('credit_risk.graph_test_run_id', :'run_id', true);
SELECT set_config(
    'credit_risk.graph_test_source_sha256',
    :'source_sha256',
    true
);

DO $path_test$
DECLARE
    v_artifact_node_id bigint;
    v_source_node_id bigint;
    v_missing_features text[];
BEGIN
    SELECT artifact.node_id
    INTO STRICT v_artifact_node_id
    FROM meta.node AS artifact
    WHERE artifact.graph_scope = 'data_lineage'
      AND artifact.node_type = 'Artifact'
      AND artifact.canonical_name =
          'artifact.wave1.independent_validation.'
          || current_setting('credit_risk.graph_test_run_id')
      AND artifact.version =
          '6a12eee57f22275a759f2493fbad5a3fb68aebfeea29ccd8fc5ba04299f2b4ce';

    SELECT source_node.node_id
    INTO STRICT v_source_node_id
    FROM meta.node AS source_node
    WHERE source_node.graph_scope = 'data_lineage'
      AND source_node.node_type = 'Source'
      AND source_node.canonical_name =
          'source.uci_default_credit_card_clients'
      AND source_node.version =
          current_setting('credit_risk.graph_test_source_sha256');

    IF EXISTS (
        SELECT 1
        FROM meta.edge AS edge
        JOIN meta.node AS from_node
          ON from_node.node_id = edge.from_node_id
        JOIN meta.node AS to_node
          ON to_node.node_id = edge.to_node_id
        WHERE edge.graph_scope IS DISTINCT FROM from_node.graph_scope
           OR edge.graph_scope IS DISTINCT FROM to_node.graph_scope
           OR from_node.graph_scope IS DISTINCT FROM to_node.graph_scope
    ) THEN
        RAISE EXCEPTION
            'cross-scope graph row exists';
    END IF;

    WITH RECURSIVE dependency_walk AS (
        SELECT
            start_node.node_id,
            ARRAY[start_node.node_id] AS visited_node_ids,
            ARRAY[start_node.canonical_name] AS canonical_path,
            ARRAY[]::text[] AS edge_type_path,
            0 AS depth
        FROM meta.node AS start_node
        WHERE start_node.node_id = v_artifact_node_id
          AND start_node.graph_scope = 'data_lineage'

        UNION ALL

        SELECT
            dependency.node_id,
            dependency_walk.visited_node_ids || dependency.node_id,
            dependency_walk.canonical_path || dependency.canonical_name,
            dependency_walk.edge_type_path || edge.edge_type,
            dependency_walk.depth + 1
        FROM dependency_walk
        JOIN meta.edge AS edge
          ON edge.graph_scope = 'data_lineage'
         AND edge.from_node_id = dependency_walk.node_id
         AND edge.edge_type IN ('computed_from', 'validated_by')
        JOIN meta.node AS dependency
          ON dependency.graph_scope = edge.graph_scope
         AND dependency.node_id = edge.to_node_id
        WHERE dependency_walk.depth < 12
          AND NOT dependency.node_id =
              ANY(dependency_walk.visited_node_ids)
    ),
    required_feature (feature_name) AS (
        VALUES
            ('recent_max_delinquency'),
            ('delinquent_months_6m'),
            ('delinquency_deterioration'),
            ('latest_utilization_ratio'),
            ('payment_coverage_ratio'),
            ('zero_payment_streak'),
            ('recent_bill_growth')
    )
    SELECT array_agg(
        required_feature.feature_name
        ORDER BY required_feature.feature_name
    )
    INTO v_missing_features
    FROM required_feature
    WHERE NOT EXISTS (
        SELECT 1
        FROM dependency_walk AS exact_path
        WHERE exact_path.node_id = v_source_node_id
          AND exact_path.depth = 10
          AND exact_path.canonical_path[1] =
              'artifact.wave1.independent_validation.'
              || current_setting('credit_risk.graph_test_run_id')
          AND exact_path.canonical_path[2] =
              'result.wave1.independent_validation.'
              || current_setting('credit_risk.graph_test_run_id')
          AND exact_path.canonical_path[3] =
              'test.wave1.independent_validation'
          AND exact_path.canonical_path[4] =
              'query.wave1.signal_summaries'
          AND exact_path.canonical_path[5] =
              'mart.borrower_risk_signal.'
              || required_feature.feature_name
          AND exact_path.canonical_path[6] =
              'query.wave1.risk_signals'
          AND exact_path.canonical_path[7] IN (
              'core.borrower',
              'core.account_month'
          )
          AND exact_path.canonical_path[8] =
              'transformation.wave1.build_core'
          AND exact_path.canonical_path[9] =
              'raw.credit_card_client'
          AND exact_path.canonical_path[10] =
              'transformation.uci_default_credit_card_clients.load'
          AND exact_path.canonical_path[11] =
              'source.uci_default_credit_card_clients'
          AND exact_path.edge_type_path = ARRAY[
              'computed_from',
              'validated_by',
              'computed_from',
              'computed_from',
              'computed_from',
              'computed_from',
              'computed_from',
              'computed_from',
              'computed_from',
              'computed_from'
          ]::text[]
    );

    IF v_missing_features IS NOT NULL THEN
        RAISE EXCEPTION
            'missing exact Artifact-to-Source paths for features: %',
            array_to_string(v_missing_features, ', ');
    END IF;
END;
$path_test$;

ROLLBACK;
