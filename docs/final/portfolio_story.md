# Portfolio Story

Status: narrative scaffold. Numerical evidence remains pending independent
Wave 1 validation, Gate 5 cross-artifact review, and human publication approval.

## Problem

Credit-risk calculations are only useful when the project team can trust the data, reproduce the calculation, explain a change, and hand the process to another analyst.

## Implemented approach

- defined the decision and constraints before selecting metrics
- preserved source data through a Hermes ingestion boundary
- specified a relational customer-month transformation with controlled ownership
- specified SQL tests for source integrity, transformations, and business rules
- mapped economic reasoning to observable behavioral-signal definitions
- planned independent validation and claim-to-source lineage
- restricted LLM use to retrieval, explanation, and documentation of approved evidence

The execution state of each producer is recorded in `PROJECT_STATE.md` and
`docs/governance/work_status.md`; this narrative does not promote a planned or
implemented component to a verified result.

## Evidence activation after execution

- source and customer-month reconciliation results
- number and status of SQL tests
- observed default-rate separation by signal and risk band
- one issue investigation and resolution path
- one claim-to-source lineage example

These items may be added only through the claim activation and publication
rules in [`evidence_map.md`](evidence_map.md), not by manually editing values.

## Limitation

This is a public-data prototype, not an official bank IFRS 9 implementation.
No production Stage, EAD, LGD, ECL, rating, causal, or model-approval claim is
made.
