/*
Purpose:
  Create the PostgreSQL metadata graph used for economic-transmission
  hypotheses and data-lineage traceability.
Input tables:
  None. This DDL depends only on the PostgreSQL `meta` schema, which it creates
  when absent.
Output definition and grain:
  `meta.node` has one row per graph scope, canonical name, and definition
  version. `meta.edge` has one row per graph scope, endpoint pair, relationship
  type, and validity start date.
Observation point:
  Node versions and edge validity dates are supplied by the registering
  workflow; this DDL does not infer an as-of date from analytical data.
Main assumptions:
  The two graph scopes are `economic_transmission` and `data_lineage`.
  Node and edge types are limited to the lists approved in HARNESS.md.
  A composite foreign key prevents edges from crossing graph scopes.
  Data-lineage edges cannot carry economic sign or lag semantics.
Validation:
  Run `psql "$DATABASE_URL" -v ON_ERROR_STOP=1
  -f tests/graph/test_meta_graph.sql` after applying this file.
*/

CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS meta.node (
    node_id bigint GENERATED ALWAYS AS IDENTITY,
    graph_scope text NOT NULL,
    node_type text NOT NULL,
    canonical_name text NOT NULL,
    version text NOT NULL,
    status text NOT NULL DEFAULT 'draft',
    owner text,
    path_or_object text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT pk_meta_node PRIMARY KEY (node_id),
    CONSTRAINT uq_meta_node_scope_id UNIQUE (graph_scope, node_id),
    CONSTRAINT uq_meta_node_identity
        UNIQUE (graph_scope, canonical_name, version),
    CONSTRAINT ck_meta_node_graph_scope
        CHECK (graph_scope IN ('economic_transmission', 'data_lineage')),
    CONSTRAINT ck_meta_node_type
        CHECK (
            node_type IN (
                'Problem',
                'Decision',
                'Constraint',
                'Shock',
                'Agent',
                'Incentive',
                'Behavior',
                'Source',
                'Field',
                'Table',
                'Transformation',
                'Query',
                'Feature',
                'RiskComponent',
                'Scenario',
                'Metric',
                'Test',
                'Result',
                'Artifact',
                'Run',
                'Version',
                'Issue',
                'Owner',
                'Approval',
                'DecisionRecord',
                'Checkpoint'
            )
        ),
    CONSTRAINT ck_meta_node_canonical_name_nonempty
        CHECK (btrim(canonical_name) <> ''),
    CONSTRAINT ck_meta_node_version_nonempty
        CHECK (btrim(version) <> ''),
    CONSTRAINT ck_meta_node_status_nonempty
        CHECK (btrim(status) <> ''),
    CONSTRAINT ck_meta_node_owner_nonempty
        CHECK (owner IS NULL OR btrim(owner) <> ''),
    CONSTRAINT ck_meta_node_path_nonempty
        CHECK (path_or_object IS NULL OR btrim(path_or_object) <> '')
);

CREATE INDEX IF NOT EXISTS ix_meta_node_scope_type
    ON meta.node (graph_scope, node_type);

CREATE TABLE IF NOT EXISTS meta.edge (
    edge_id bigint GENERATED ALWAYS AS IDENTITY,
    graph_scope text NOT NULL,
    from_node_id bigint NOT NULL,
    to_node_id bigint NOT NULL,
    edge_type text NOT NULL,
    expected_sign text,
    lag interval,
    evidence_reference text,
    valid_from date NOT NULL,
    valid_to date,
    status text NOT NULL DEFAULT 'draft',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT pk_meta_edge PRIMARY KEY (edge_id),
    CONSTRAINT uq_meta_edge_identity
        UNIQUE (
            graph_scope,
            from_node_id,
            to_node_id,
            edge_type,
            valid_from
        ),
    CONSTRAINT fk_meta_edge_from_node
        FOREIGN KEY (graph_scope, from_node_id)
        REFERENCES meta.node (graph_scope, node_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    CONSTRAINT fk_meta_edge_to_node
        FOREIGN KEY (graph_scope, to_node_id)
        REFERENCES meta.node (graph_scope, node_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    CONSTRAINT ck_meta_edge_graph_scope
        CHECK (graph_scope IN ('economic_transmission', 'data_lineage')),
    CONSTRAINT ck_meta_edge_type
        CHECK (
            edge_type IN (
                'causes',
                'amplifies',
                'mitigates',
                'observed_by',
                'constrained_by',
                'computed_from',
                'transformed_by',
                'validated_by',
                'fails',
                'explains',
                'supports',
                'reported_in',
                'owned_by',
                'supersedes',
                'requires_approval'
            )
        ),
    CONSTRAINT ck_meta_edge_not_self_loop
        CHECK (from_node_id <> to_node_id),
    CONSTRAINT ck_meta_edge_expected_sign
        CHECK (
            expected_sign IS NULL
            OR expected_sign IN ('positive', 'negative', 'mixed', 'unknown')
        ),
    CONSTRAINT ck_meta_edge_lag_nonnegative
        CHECK (lag IS NULL OR lag >= interval '0 seconds'),
    CONSTRAINT ck_meta_edge_lineage_has_no_economic_semantics
        CHECK (
            graph_scope <> 'data_lineage'
            OR (expected_sign IS NULL AND lag IS NULL)
        ),
    CONSTRAINT ck_meta_edge_evidence_reference_nonempty
        CHECK (
            evidence_reference IS NULL
            OR btrim(evidence_reference) <> ''
        ),
    CONSTRAINT ck_meta_edge_approved_has_evidence
        CHECK (
            status <> 'approved'
            OR evidence_reference IS NOT NULL
        ),
    CONSTRAINT ck_meta_edge_valid_window
        CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT ck_meta_edge_status_nonempty
        CHECK (btrim(status) <> '')
);

CREATE INDEX IF NOT EXISTS ix_meta_edge_from
    ON meta.edge (graph_scope, from_node_id, edge_type);

CREATE INDEX IF NOT EXISTS ix_meta_edge_to
    ON meta.edge (graph_scope, to_node_id, edge_type);

/*
Deterministic node registration:
  Repeating the same immutable definition returns the existing node_id.
  Reusing the same identity with conflicting metadata fails closed; definition
  changes must use a new version or an explicitly governed update.
*/
CREATE OR REPLACE FUNCTION meta.register_node (
    p_graph_scope text,
    p_node_type text,
    p_canonical_name text,
    p_version text,
    p_status text DEFAULT 'draft',
    p_owner text DEFAULT NULL,
    p_path_or_object text DEFAULT NULL
)
RETURNS bigint
LANGUAGE plpgsql
AS $function$
DECLARE
    v_node_id bigint;
    v_existing meta.node%ROWTYPE;
BEGIN
    INSERT INTO meta.node (
        graph_scope,
        node_type,
        canonical_name,
        version,
        status,
        owner,
        path_or_object
    )
    VALUES (
        p_graph_scope,
        p_node_type,
        p_canonical_name,
        p_version,
        p_status,
        p_owner,
        p_path_or_object
    )
    ON CONFLICT ON CONSTRAINT uq_meta_node_identity DO NOTHING
    RETURNING node_id INTO v_node_id;

    IF v_node_id IS NOT NULL THEN
        RETURN v_node_id;
    END IF;

    SELECT
        n.node_id,
        n.graph_scope,
        n.node_type,
        n.canonical_name,
        n.version,
        n.status,
        n.owner,
        n.path_or_object,
        n.created_at
    INTO STRICT v_existing
    FROM meta.node AS n
    WHERE n.graph_scope = p_graph_scope
      AND n.canonical_name = p_canonical_name
      AND n.version = p_version;

    IF v_existing.node_type IS DISTINCT FROM p_node_type
       OR v_existing.status IS DISTINCT FROM p_status
       OR v_existing.owner IS DISTINCT FROM p_owner
       OR v_existing.path_or_object IS DISTINCT FROM p_path_or_object THEN
        RAISE EXCEPTION
            'conflicting node registration for scope %, name %, version %',
            p_graph_scope,
            p_canonical_name,
            p_version
            USING ERRCODE = '23505';
    END IF;

    RETURN v_existing.node_id;
END;
$function$;

/*
Deterministic edge registration:
  Repeating the same immutable relationship returns the existing edge_id.
  Reusing its identity with different semantics or evidence fails closed.
*/
CREATE OR REPLACE FUNCTION meta.register_edge (
    p_graph_scope text,
    p_from_node_id bigint,
    p_to_node_id bigint,
    p_edge_type text,
    p_valid_from date,
    p_expected_sign text DEFAULT NULL,
    p_lag interval DEFAULT NULL,
    p_evidence_reference text DEFAULT NULL,
    p_valid_to date DEFAULT NULL,
    p_status text DEFAULT 'draft'
)
RETURNS bigint
LANGUAGE plpgsql
AS $function$
DECLARE
    v_edge_id bigint;
    v_existing meta.edge%ROWTYPE;
BEGIN
    INSERT INTO meta.edge (
        graph_scope,
        from_node_id,
        to_node_id,
        edge_type,
        expected_sign,
        lag,
        evidence_reference,
        valid_from,
        valid_to,
        status
    )
    VALUES (
        p_graph_scope,
        p_from_node_id,
        p_to_node_id,
        p_edge_type,
        p_expected_sign,
        p_lag,
        p_evidence_reference,
        p_valid_from,
        p_valid_to,
        p_status
    )
    ON CONFLICT ON CONSTRAINT uq_meta_edge_identity DO NOTHING
    RETURNING edge_id INTO v_edge_id;

    IF v_edge_id IS NOT NULL THEN
        RETURN v_edge_id;
    END IF;

    SELECT
        e.edge_id,
        e.graph_scope,
        e.from_node_id,
        e.to_node_id,
        e.edge_type,
        e.expected_sign,
        e.lag,
        e.evidence_reference,
        e.valid_from,
        e.valid_to,
        e.status,
        e.created_at
    INTO STRICT v_existing
    FROM meta.edge AS e
    WHERE e.graph_scope = p_graph_scope
      AND e.from_node_id = p_from_node_id
      AND e.to_node_id = p_to_node_id
      AND e.edge_type = p_edge_type
      AND e.valid_from = p_valid_from;

    IF v_existing.expected_sign IS DISTINCT FROM p_expected_sign
       OR v_existing.lag IS DISTINCT FROM p_lag
       OR v_existing.evidence_reference IS DISTINCT FROM p_evidence_reference
       OR v_existing.valid_to IS DISTINCT FROM p_valid_to
       OR v_existing.status IS DISTINCT FROM p_status THEN
        RAISE EXCEPTION
            'conflicting edge registration for scope %, from %, to %, type %, valid_from %',
            p_graph_scope,
            p_from_node_id,
            p_to_node_id,
            p_edge_type,
            p_valid_from
            USING ERRCODE = '23505';
    END IF;

    RETURN v_existing.edge_id;
END;
$function$;

COMMENT ON TABLE meta.node IS
    'Typed graph nodes separated by economic_transmission or data_lineage scope.';
COMMENT ON TABLE meta.edge IS
    'Typed, same-scope graph edges; approved edges require an evidence reference.';
COMMENT ON FUNCTION meta.register_node(text, text, text, text, text, text, text) IS
    'Idempotently register one immutable, versioned graph node.';
COMMENT ON FUNCTION meta.register_edge(
    text,
    bigint,
    bigint,
    text,
    date,
    text,
    interval,
    text,
    date,
    text
) IS
    'Idempotently register one immutable, validity-dated graph edge.';
