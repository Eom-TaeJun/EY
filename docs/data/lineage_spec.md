# Lineage Specification

## Goal

Trace any final claim through:

`Artifact → Result → Query/Model → Feature → Core table → Transformation → Raw table → Source file`

The metadata layer contains two separate graphs. They share a PostgreSQL
storage pattern, but not a graph scope or edge:

1. `economic_transmission`: why risk may change.
2. `data_lineage`: how a definition or verified number was produced.

An edge can only connect nodes with the same `graph_scope`. Cross-scope edges
are rejected by composite foreign keys. A relation between an economic
hypothesis and analytical evidence therefore requires corresponding nodes and
relationships inside each graph; it must not be represented by one
cross-scope edge.

## PostgreSQL metadata contract

The executable contract is in `sql/ddl/030_meta_graph.sql`.

### `meta.node` grain

One row per:

`graph_scope + canonical_name + version`

Key descriptive fields are `node_type`, `status`, `owner`, and
`path_or_object`. `canonical_name` is a stable repository path, database
object, or governed concept name; `version` makes definition changes explicit.

### `meta.edge`

One row per:

`graph_scope + from_node_id + to_node_id + edge_type + valid_from`

`expected_sign` and `lag` are available only to
`economic_transmission`. A `data_lineage` edge carrying either field is
rejected. An edge with `status = 'approved'` must have a non-empty
`evidence_reference`. Validity dates preserve superseded paths instead of
overwriting them.

`meta.register_node(...)` and `meta.register_edge(...)` are deterministic
registration interfaces. An exact replay returns the existing identifier. A
replay that reuses the same identity but changes its type, evidence, status, or
other immutable metadata fails closed. A governed definition change should
register a new version or validity period.

## Approved graph types

Only the node and edge types listed in `HARNESS.md` are accepted. The database
enforces the complete approved lists with check constraints; case and spelling
are significant.

Node types:

- `Problem`, `Decision`, `Constraint`, `Shock`, `Agent`, `Incentive`, `Behavior`
- `Source`, `Field`, `Table`, `Transformation`, `Query`, `Feature`
- `RiskComponent`, `Scenario`, `Metric`, `Test`, `Result`, `Artifact`
- `Run`, `Version`, `Issue`, `Owner`, `Approval`, `DecisionRecord`, `Checkpoint`

Edge types:

- `causes`, `amplifies`, `mitigates`, `observed_by`
- `constrained_by`, `computed_from`, `transformed_by`
- `validated_by`, `fails`, `explains`, `supports`
- `reported_in`, `owned_by`, `supersedes`, `requires_approval`

Adding a type requires a decision-ledger entry and the applicable approval;
free-text types are not a bypass.

## Edge direction and families

- Economic transmission follows causal time: upstream shock or constraint
  points to the downstream behavior, signal, or risk component.
- Producer-flow lineage records how work moved operationally from an upstream
  producer to a downstream consumer. Wave 1 retains `transformed_by`,
  `supports`, and `reported_in` edges such as `Source → Loader`,
  `Query → Feature`, and `Result → Artifact`. These historical edges are useful
  for impact analysis, but are not the claim-to-source query contract.
- Dependency lineage points from a downstream object to its immediate
  dependency. Wave 1 uses `computed_from` for data/code dependencies and
  `validated_by` for `Result → Test`. The complete query direction is
  `Artifact → Result → Test → Query → Feature → Query → Core table →
  Transformation → Raw table → Loader → Source`.
- A claim-to-source traversal must follow only dependency-family edge types
  `computed_from` and `validated_by`. Mixing producer-flow types into that walk
  can reverse direction or introduce cycles because both edge families are
  intentionally retained.
- Upstream-to-downstream impact analysis can either reverse the dependency
  family or follow the producer-flow family. The selected family and direction
  must be explicit in the query.

## Minimum Wave 1 lineage

- source file to raw table
- raw columns to account-month transformation
- account-month columns to each signal
- signals to risk-band query
- risk-band result to README claim

Actual `Result`, `Run`, and `Artifact` nodes must be registered only after the
upstream run has passed its required validation gate. The base graph DDL seeds
no data. `sql/ddl/031_wave1_lineage.sql` adds the independently validated Wave
1 path while retaining its producer-flow history.

## Query paths

Forward claim-to-source lineage:

```sql
WITH RECURSIVE lineage AS (
    SELECT
        n.node_id,
        n.canonical_name,
        0 AS depth,
        ARRAY[n.node_id] AS visited
    FROM meta.node AS n
    WHERE n.graph_scope = 'data_lineage'
      AND n.node_id = :start_node_id

    UNION ALL

    SELECT
        upstream.node_id,
        upstream.canonical_name,
        lineage.depth + 1,
        lineage.visited || upstream.node_id
    FROM lineage
    JOIN meta.edge AS e
     ON e.graph_scope = 'data_lineage'
     AND e.from_node_id = lineage.node_id
     AND e.edge_type IN (
         'computed_from',
         'validated_by'
     )
    JOIN meta.node AS upstream
      ON upstream.graph_scope = e.graph_scope
     AND upstream.node_id = e.to_node_id
    WHERE NOT upstream.node_id = ANY(lineage.visited)
      AND lineage.depth < :max_depth
)
SELECT
    node_id,
    canonical_name,
    depth
FROM lineage
ORDER BY depth, node_id;
```

The caller must bind `start_node_id` and a bounded `max_depth`; Wave 1 requires
at least depth 10 for the registered Artifact-to-Source path. This is not an
unrestricted natural-language SQL interface. A visual graph is optional, while
the queryable PostgreSQL lineage is mandatory.

## Integrity validation

Apply the DDL and run:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/ddl/030_meta_graph.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f tests/graph/test_meta_graph.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -v run_id=W1-20260727-001 \
  -v source_sha256=30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933 \
  -f sql/ddl/031_wave1_lineage.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -v run_id=W1-20260727-001 \
  -v source_sha256=30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933 \
  -f tests/graph/test_wave1_lineage_path.sql
```

The test transaction verifies:

- exact replay is idempotent;
- conflicting replay fails;
- unknown graph scopes and node or edge types fail;
- cross-scope edges fail;
- lineage sign/lag semantics fail;
- negative economic lag, self-loops, and approved edges without evidence fail;
- fixtures are rolled back.

The Wave 1 path test additionally verifies:

- every one of the seven validated Feature nodes has the exact bounded
  Artifact-to-Source dependency path;
- the path uses only `computed_from` and `validated_by`;
- all edge scopes equal both endpoint scopes, so no cross-scope row exists.
