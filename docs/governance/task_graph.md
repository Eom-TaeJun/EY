# Task Graph

## Critical path

```mermaid
graph LR
  A[Charter and Harness] --> B[Source registry]
  B --> C[Hermes raw ingestion]
  C --> D[Core relational model]
  D --> E[SQL QA and reconciliation]
  E --> F[Risk signals]
  F --> G[Observed outcome summaries]
  G --> H[README and evidence map]
```

## Parallel tracks

```mermaid
graph TD
  A[Wave 0 complete] --> B[Data dictionary]
  A --> C[Graph schema]
  A --> D[Validation scaffold]
  A --> E[Report structure]
  A --> F[Wave 2 interfaces]
  B --> G[Wiki source documents]
  C --> H[Lineage population after Wave 1]
  D --> I[Independent review after Wave 1]
```

## Blocking conditions

- Core transformation is blocked until raw reconciliation passes.
- Risk-signal publication is blocked until core QA passes.
- Model publication is blocked until leakage and time validation pass.
- External numbers are blocked until cross-artifact reconciliation passes.
