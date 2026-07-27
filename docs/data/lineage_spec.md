# Lineage Specification

## Goal

Trace any final claim through:

`Artifact → Result → Query/Model → Feature → Core table → Transformation → Raw table → Source file`

## Metadata tables

### `meta.node`

- node_id
- node_type
- canonical_name
- version
- status
- owner
- path_or_object

### `meta.edge`

- from_node_id
- to_node_id
- edge_type
- expected_sign
- lag
- evidence_reference
- valid_from
- valid_to
- status

## Minimum Wave 1 lineage

- source file to raw table
- raw columns to account-month transformation
- account-month columns to each signal
- signals to risk-band query
- risk-band result to README claim

A visual graph is optional; queryable lineage is mandatory.
