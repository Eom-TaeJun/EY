# Graph Agent Contract

## Objective

Implement the typed economic-transmission and data-lineage graphs without
mixing their meanings or introducing a second database without approval.

## Outputs

- PostgreSQL `meta.node` and `meta.edge` DDL
- allowed node and edge type controls
- deterministic lineage registration interfaces
- graph integrity tests and documented query paths

## Owned paths

- `sql/ddl/030_meta_graph.sql`
- graph sections of `docs/data/lineage_spec.md`
- `tests/graph/`

## Rules

- keep economic transmission and data lineage as separate graph scopes
- use only types approved in `HARNESS.md`
- link actual results only after their upstream run is validated
- do not add a graph database or generate numerical claims
