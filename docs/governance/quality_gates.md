# Quality Gates

| Gate | Required evidence | Blocks |
|---|---|---|
| G0 Governance | charter, purpose, roles, task graph, state | implementation without scope control |
| G1 Source | hash, registry, raw row/column reconciliation | core transformation |
| G2 Core | keys, row counts, amount reconciliation, code domains | risk signals |
| G3 Signal | definition, timing, leakage check, outcome comparison | model/report claims |
| G4 Model | time validation, calibration, stability, assumptions | Risk Component conclusions |
| G5 Artifact | DB/code/report reconciliation, run ID, limitations | external publication |

A failed gate creates an issue. Do not relax a threshold without a decision and human approval.
