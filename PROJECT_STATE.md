# Project State

## Current status

- Active Wave: `Wave 4 supported scope complete; human publication review pending`
- Portfolio deadline mode: `same-day critical path with parallel extensions`
- Primary dataset for first implementation: `UCI Default of Credit Card Clients`
- Target database: `PostgreSQL`
- Latest validated analytical run: `W1-20260727-001`
- Definition version: `0.1.0`
- Latest model run: `W2-PD-20260727-001`, definition `0.2.0`
- Current objective: preserve the completed internal evidence package and obtain
  a human visual/publication review without changing validated numbers.

## Critical path

- [x] Confirm repository scaffold
- [x] Register source and license
- [x] Create raw schema and ingestion run
- [x] Load source without changing values
- [x] Split borrower and account-month structures
- [x] Reconcile 30,000 borrowers and 180,000 customer-month rows
- [x] Run data-quality and business-rule SQL tests
- [x] Build seven initial behavioral risk signals
- [x] Compare observed default rate by signal and risk band
- [x] Independently reproduce evidence and pass Gates 1–3
- [x] Update README and evidence map with verified internal values only
- [x] Compare static, behavioral, and combined PD prototypes on one fixed holdout
- [x] Independently recompute Wave 2 metrics and preserve failed validation history
- [x] Block Gate 4 because time-direction and approved sensitivity evidence are absent
- [x] Generate and independently reconcile Excel, PowerPoint, and Word
- [x] Map EY FSRM hiring signals to run-bound evidence on the README first screen
- [x] Complete the final 63-test regression and pass Gates 0–3 and 5

## Parallel tracks

- [x] Data dictionary and test catalog
- [x] Graph node/edge schema and validated Wave 1 lineage seed
- [x] Separate 14-node/20-edge economic-transmission hypothesis graph
- [x] Validation scaffold and fail-closed regression tests
- [x] Internal report generator and PowerPoint page structure
- [x] Generated and independently reconciled Excel/PowerPoint/Word artifacts
- [x] Wave 2 model interfaces and retrospective internal benchmark
- [x] Six-question allowlisted governed knowledge query

## Deferred

- Gate 4 model/scenario conclusion because the current source has no eligible
  time direction or approved sensitivity
- external publication approval
- LGD and EAD estimates until an eligible performance/recovery dataset exists
- genuine time-based validation until a borrower-level observation timestamp exists
- semantic/vector RAG and generative LLM Wiki
- full multi-run scheduling and recovery automation

## Latest checkpoint

| Field | Value |
|---|---|
| checkpoint_id | CP-006 |
| date | 2026-07-27 |
| owner | Orchestrator |
| completed | Waves 0–4 implemented to supported public-data scope; recruiter-facing evidence map and handoff reconciled |
| verified | 63 tests passed; Ruff/scaffold/governance passed; Gates 0–3 and 5 passed; Gate 4 failed closed as designed |
| open issues | `DATA-001`, `MODEL-001`, `SCEN-001`, and `RPT-001` visual-render review |
| Gate 4 | Blocked; this is not a time-validated, IFRS 9, or production PD result |
| Gate 5 | Passed for Wave 1 cross-artifact consistency |
| publication | internal evidence only; human approval pending |
| next action | Open the Office files in Microsoft Office or LibreOffice, resolve `RPT-001`, and approve or reject external publication |

## Update rule

Every agent run must update this file only through the Orchestrator or with explicit Orchestrator approval. Do not replace historical evidence; link to detailed status in `docs/governance/work_status.md`.
