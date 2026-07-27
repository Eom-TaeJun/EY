# Decision Ledger

| Decision ID | Date | Problem | Options considered | Decision | Rationale | Reversible | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| DEC-001 | 2026-07-27 | Same-day data choice | UCI vs large loan-performance data | Use UCI for Wave 1 | User-directed; faster deterministic DB and SQL evidence; retain expansion path | Yes | User | Accepted |
| DEC-002 | 2026-07-27 | Graph technology | PostgreSQL metadata vs graph DB | Start with typed metadata tables | User-directed; traceability without infrastructure overhead | Yes | User | Accepted |
| DEC-003 | 2026-07-27 | Initial scoring method | Rules vs complex ML | Explainable SQL rules first | User-directed; directly reviewable and reproducible | Yes | User | Accepted |
| DEC-004 | 2026-07-27 | Repository root | Flatten nested folder vs preserve supplied structure | Use the nested project folder as repository root | No ZIP exists; preserves supplied structure and names | Yes | Orchestrator | Accepted |
| DEC-005 | 2026-07-27 | Initial risk-band thresholds | Outcome-tuned cutoffs vs predeclared points | Use version 0.1.0 points and Low 0–1, Medium 2–3, High 4+ | Reversible, explainable, fixed before outcome review | Yes | Orchestrator | Accepted |
| DEC-006 | 2026-07-27 | PostgreSQL runtime blocker | Stop unexecuted vs system install vs local extraction | Run unpacked PostgreSQL 16.14 under `/tmp` | Docker/psql absent and sudo password unavailable; enables actual SQL without system install | Yes | Orchestrator | Accepted |
| DEC-007 | 2026-07-27 | Undocumented source codes | Recode/delete vs fail all data vs preserve+warn | Preserve exact values and record DQ-016–018 warnings | Protects source integrity without inventing category meaning | Yes | Orchestrator | Accepted |

### Decision impact and rollback

| Decision ID | Affected paths | Discarded alternative | Approval basis | Rollback | Downstream nodes |
|---|---|---|---|---|---|
| DEC-001 | `config/data_sources.yml`, ingestion/core/signal paths | larger loan-performance source for same-day MVP | explicit user instruction | register another approved source in a later Wave; never replace raw in place | Source → raw → core → signals |
| DEC-002 | `sql/ddl/`, `meta.node`, `meta.edge` | separate graph database | explicit user instruction | add a separate store only through a later approved decision | lineage and economic graphs |
| DEC-003 | `config/risk_definitions.yml`, `sql/features/` | complex ML-first score | explicit user instruction | version a later approved method; retain prior definition | signals → band → reports |
| DEC-004 | repository-local paths | moving/renaming supplied files | reversible Orchestrator assumption | re-open from an explicitly supplied repo path | all project files |
| DEC-005 | `config/risk_definitions.yml`, `sql/features/060_risk_signals.sql` | tune cutoffs on full-sample outcomes | conservative reversible assumption under user instruction | create a new approved definition version; retain 0.1.0 outputs | signals → risk band → reports |
| DEC-006 | `/tmp/credit-risk-pg-*` runtime only | leave PostgreSQL unexecuted | safe reversible execution step | stop the temporary server; standard Docker path remains canonical | SQL execution evidence |
| DEC-007 | raw/core code-domain checks and data dictionary | assign undocumented meanings or remove rows | source-preservation rule | supersede only with authoritative code documentation; never rewrite raw | DQ warnings → interpretation limits |

## Required fields for new decisions

- affected files and outputs
- discarded alternatives
- approval requirement
- rollback method
- downstream nodes affected
