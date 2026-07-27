# Project State

## Current status

- Active Wave: `Wave 0 → Wave 1`
- Portfolio deadline mode: `same-day critical path with parallel extensions`
- Primary dataset for first implementation: `UCI Default of Credit Card Clients`
- Target database: `PostgreSQL`
- Current objective: establish governance, ingest source data, build the customer-month table, run SQL QA, and produce risk-signal summaries.

## Critical path

- [ ] Confirm repository scaffold
- [ ] Register source and license
- [ ] Create raw schema and ingestion run
- [ ] Load source without changing values
- [ ] Split borrower and account-month structures
- [ ] Reconcile 30,000 borrowers and expected 180,000 customer-month rows
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
| checkpoint_id | CP-000 |
| date | YYYY-MM-DD |
| owner | Human |
| completed | Repository scaffold created |
| blockers | Source not yet ingested |
| next action | Run Wave 0 review, then Hermes Wave 1 packet |

## Update rule

Every agent run must update this file only through the Orchestrator or with explicit Orchestrator approval. Do not replace historical evidence; link to detailed status in `docs/governance/work_status.md`.
