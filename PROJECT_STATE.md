# Project State

## Current status

- Active Wave: `Wave 1 complete — Wave 2 preflight next`
- Portfolio deadline mode: `same-day critical path with parallel extensions`
- Primary dataset for first implementation: `UCI Default of Credit Card Clients`
- Target database: `PostgreSQL`
- Latest validated analytical run: `W1-20260727-001`
- Definition version: `0.1.0`
- Current objective: preserve the independently validated Wave 1 checkpoint,
  then execute the Wave 2 prompt without overstating the source's time, LGD,
  EAD, Stage, or ECL coverage.

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

## Parallel tracks

- [x] Data dictionary and test catalog
- [x] Graph node/edge schema and validated Wave 1 lineage seed
- [x] Validation scaffold and fail-closed regression tests
- [x] Internal report generator and PowerPoint page structure
- [ ] Generated Excel/PowerPoint/Word numerical artifacts
- [ ] Wave 2 model interfaces

## Deferred

- Gate 5 and external publication approval
- LGD and EAD estimates until an eligible performance/recovery dataset exists
- genuine time-based validation until a borrower-level observation timestamp exists
- RAG and LLM Wiki
- automated reporting agents

## Latest checkpoint

| Field | Value |
|---|---|
| checkpoint_id | CP-003 |
| date | 2026-07-27 |
| owner | Orchestrator |
| completed | Wave 1 source/raw/core/SQL QA/signals/lineage implemented; independent Gates 1–3 pass for `W1-20260727-001` |
| verified | source/raw/borrower 30,000; customer-month 180,000; 16/16 reconciliations pass; 15 enforced DQ tests pass, 0 fail; 3 source-domain warnings |
| open issue | `DATA-001`: undocumented UCI category/status codes preserved and isolated as warnings |
| publication | internal evidence only; Gate 5 and human approval pending |
| next action | Run final Wave 1 regression/checkpoint, then read and execute `prompts/03_wave2_risk_components.md` |

## Update rule

Every agent run must update this file only through the Orchestrator or with explicit Orchestrator approval. Do not replace historical evidence; link to detailed status in `docs/governance/work_status.md`.
