# Data Model Agent Contract

## Objective

Design relational structures that preserve grain, keys, time, definitions, and lineage.

## Outputs

- logical and physical model
- DDL and indexes
- raw/staging/core/mart/audit/meta boundaries
- data dictionary updates
- wide-to-long transformation interface

## Rules

- declare table grain and keys
- separate immutable raw from derived tables
- store run IDs and definition versions
- avoid denormalization that obscures lineage
- obtain approval before materially changing an approved schema
