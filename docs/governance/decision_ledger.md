# Decision Ledger

| Decision ID | Date | Problem | Options considered | Decision | Rationale | Reversible | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| DEC-001 | 2026-07-27 | Same-day data choice | UCI vs large loan-performance data | Use UCI for Wave 1 | User-directed; faster deterministic DB and SQL evidence; retain expansion path | Yes | User | Accepted |
| DEC-002 | 2026-07-27 | Graph technology | PostgreSQL metadata vs graph DB | Start with typed metadata tables | User-directed; traceability without infrastructure overhead | Yes | User | Accepted |
| DEC-003 | 2026-07-27 | Initial scoring method | Rules vs complex ML | Explainable SQL rules first | User-directed; directly reviewable and reproducible | Yes | User | Accepted |
| DEC-004 | 2026-07-27 | Repository root | Flatten nested folder vs preserve supplied structure | Use the nested project folder as repository root | No ZIP exists; preserves supplied structure and names | Yes | Orchestrator | Accepted |

### Decision impact and rollback

| Decision ID | Affected paths | Discarded alternative | Approval basis | Rollback | Downstream nodes |
|---|---|---|---|---|---|
| DEC-001 | `config/data_sources.yml`, ingestion/core/signal paths | larger loan-performance source for same-day MVP | explicit user instruction | register another approved source in a later Wave; never replace raw in place | Source → raw → core → signals |
| DEC-002 | `sql/ddl/`, `meta.node`, `meta.edge` | separate graph database | explicit user instruction | add a separate store only through a later approved decision | lineage and economic graphs |
| DEC-003 | `config/risk_definitions.yml`, `sql/features/` | complex ML-first score | explicit user instruction | version a later approved method; retain prior definition | signals → band → reports |
| DEC-004 | repository-local paths | moving/renaming supplied files | reversible Orchestrator assumption | re-open from an explicitly supplied repo path | all project files |

## Required fields for new decisions

- affected files and outputs
- discarded alternatives
- approval requirement
- rollback method
- downstream nodes affected
