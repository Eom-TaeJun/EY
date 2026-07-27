# Project State

## Current status

- Active Wave: `Wave 1 — source and ingestion`
- Portfolio deadline mode: `same-day critical path with parallel extensions`
- Primary dataset for first implementation: `UCI Default of Credit Card Clients`
- Target database: `PostgreSQL`
- Current objective: register and ingest the approved UCI source without changing
  values, pass Gate 1, then build the customer-month table.

## Critical path

- [x] Confirm repository scaffold
- [ ] Register source and license
- [ ] Create raw schema and ingestion run
- [ ] Load source without changing values
- [ ] Split borrower and account-month structures
- [ ] Reconcile expected (not yet verified) 30,000 borrowers and 180,000 customer-month rows
- [ ] Run data-quality and business-rule SQL tests
- [ ] Build initial behavioral risk signals
- [ ] Compare observed default rate by signal and risk band
- [ ] Update README and evidence map with verified values only

## Parallel tracks

- [ ] Data dictionary and test catalog
- [ ] Graph node/edge schema
- [ ] Validation scaffold
- [ ] Excel/PPT/Word page structure
- [ ] Wave 2 model interfaces

## Deferred

- PD model comparison
- Stage proxy
- LGD and EAD expansion
- macro scenarios
- RAG and LLM Wiki
- automated reporting agents

## Latest checkpoint

| Field | Value |
|---|---|
| checkpoint_id | CP-002 |
| date | 2026-07-27 |
| owner | Orchestrator |
| completed | Gate 0 approved after independent review; Critical 0 and Major 0 |
| blockers | Official source not yet acquired or ingested |
| next action | Execute the Hermes Wave 1 source registration and raw-ingestion packet |

## Update rule

Every agent run must update this file only through the Orchestrator or with explicit Orchestrator approval. Do not replace historical evidence; link to detailed status in `docs/governance/work_status.md`.
