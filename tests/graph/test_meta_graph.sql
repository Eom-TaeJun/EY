/*
Purpose:
  Verify typed graph domains, graph-scope isolation, evidence controls, and
  deterministic registration behavior.
Input tables:
  `meta.node`, `meta.edge`, and their registration functions from
  `sql/ddl/030_meta_graph.sql`.
Output definition and grain:
  No durable rows. The script raises on the first failed assertion and rolls
  back every test fixture when all assertions pass.
Observation point:
  Fixed future validity dates are test fixtures only; they are not analytical
  observation dates or portfolio results.
Main assumptions:
  PostgreSQL check and foreign-key constraints remain enabled.
Validation:
  A zero exit code with `ON_ERROR_STOP=1` means all assertions executed; no
  test fixture remains because the transaction ends with `ROLLBACK`.
*/

BEGIN;

DO $test$
DECLARE
    v_lineage_source_id bigint;
    v_lineage_table_id bigint;
    v_economic_shock_id bigint;
    v_economic_behavior_id bigint;
    v_first_edge_id bigint;
    v_repeated_edge_id bigint;
BEGIN
    v_lineage_source_id := meta.register_node(
        'data_lineage',
        'Source',
        '__graph_test__.source',
        'test-v1',
        'approved',
        'Graph Test',
        'tests/graph/test_meta_graph.sql'
    );
    v_lineage_table_id := meta.register_node(
        'data_lineage',
        'Table',
        '__graph_test__.raw_table',
        'test-v1',
        'approved',
        'Graph Test',
        'meta.__graph_test_raw'
    );
    v_economic_shock_id := meta.register_node(
        'economic_transmission',
        'Shock',
        '__graph_test__.liquidity_shock',
        'test-v1',
        'draft',
        'Graph Test',
        'docs/methodology/transmission_paths.md'
    );
    v_economic_behavior_id := meta.register_node(
        'economic_transmission',
        'Behavior',
        '__graph_test__.missed_payment',
        'test-v1',
        'draft',
        'Graph Test',
        'docs/methodology/transmission_paths.md'
    );

    IF meta.register_node(
        'data_lineage',
        'Source',
        '__graph_test__.source',
        'test-v1',
        'approved',
        'Graph Test',
        'tests/graph/test_meta_graph.sql'
    ) <> v_lineage_source_id THEN
        RAISE EXCEPTION 'repeated node registration returned a different node_id';
    END IF;

    BEGIN
        PERFORM meta.register_node(
            'unsupported_scope',
            'Source',
            '__graph_test__.bad_scope',
            'test-v1'
        );
        RAISE EXCEPTION 'invalid graph scope was accepted';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    BEGIN
        PERFORM meta.register_node(
            'data_lineage',
            'UnapprovedNodeType',
            '__graph_test__.bad_node_type',
            'test-v1'
        );
        RAISE EXCEPTION 'unapproved node type was accepted';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    BEGIN
        PERFORM meta.register_node(
            'data_lineage',
            'Field',
            '__graph_test__.source',
            'test-v1',
            'approved',
            'Graph Test',
            'tests/graph/test_meta_graph.sql'
        );
        RAISE EXCEPTION 'conflicting deterministic node registration was accepted';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    v_first_edge_id := meta.register_edge(
        'data_lineage',
        v_lineage_table_id,
        v_lineage_source_id,
        'computed_from',
        DATE '2099-01-01',
        NULL,
        NULL,
        'tests/graph/test_meta_graph.sql',
        NULL,
        'approved'
    );
    v_repeated_edge_id := meta.register_edge(
        'data_lineage',
        v_lineage_table_id,
        v_lineage_source_id,
        'computed_from',
        DATE '2099-01-01',
        NULL,
        NULL,
        'tests/graph/test_meta_graph.sql',
        NULL,
        'approved'
    );

    IF v_first_edge_id <> v_repeated_edge_id THEN
        RAISE EXCEPTION 'repeated edge registration returned a different edge_id';
    END IF;

    PERFORM meta.register_edge(
        'economic_transmission',
        v_economic_shock_id,
        v_economic_behavior_id,
        'causes',
        DATE '2099-01-01',
        'positive',
        interval '1 month',
        NULL,
        NULL,
        'draft'
    );

    BEGIN
        PERFORM meta.register_edge(
            'data_lineage',
            v_lineage_table_id,
            v_lineage_source_id,
            'not_approved',
            DATE '2099-01-02'
        );
        RAISE EXCEPTION 'unapproved edge type was accepted';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    BEGIN
        PERFORM meta.register_edge(
            'data_lineage',
            v_economic_shock_id,
            v_lineage_table_id,
            'computed_from',
            DATE '2099-01-02'
        );
        RAISE EXCEPTION 'cross-scope edge was accepted';
    EXCEPTION
        WHEN foreign_key_violation THEN
            NULL;
    END;

    BEGIN
        PERFORM meta.register_edge(
            'data_lineage',
            v_lineage_table_id,
            v_lineage_source_id,
            'transformed_by',
            DATE '2099-01-02',
            'positive'
        );
        RAISE EXCEPTION 'economic sign was accepted on a data-lineage edge';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    BEGIN
        PERFORM meta.register_edge(
            'economic_transmission',
            v_economic_shock_id,
            v_economic_behavior_id,
            'amplifies',
            DATE '2099-01-02',
            'positive',
            interval '-1 day'
        );
        RAISE EXCEPTION 'negative lag was accepted';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    BEGIN
        PERFORM meta.register_edge(
            'economic_transmission',
            v_economic_shock_id,
            v_economic_behavior_id,
            'explains',
            DATE '2099-01-03',
            'positive',
            interval '0 days',
            NULL,
            NULL,
            'approved'
        );
        RAISE EXCEPTION 'approved edge without evidence was accepted';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    BEGIN
        PERFORM meta.register_edge(
            'economic_transmission',
            v_economic_shock_id,
            v_economic_shock_id,
            'causes',
            DATE '2099-01-04'
        );
        RAISE EXCEPTION 'self-loop edge was accepted';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    IF (
        SELECT count(*)
        FROM meta.node AS n
        WHERE n.canonical_name LIKE '__graph_test__.%'
    ) <> 4 THEN
        RAISE EXCEPTION 'unexpected graph test node count';
    END IF;

    IF (
        SELECT count(*)
        FROM meta.edge AS e
        WHERE e.from_node_id IN (
            v_lineage_table_id,
            v_economic_shock_id
        )
    ) <> 2 THEN
        RAISE EXCEPTION 'unexpected graph test edge count';
    END IF;
END;
$test$;

ROLLBACK;
