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
| DEC-008 | 2026-07-27 | Wave 2 validation design with one observation date | label ID split temporal vs use cross-sectional benchmark vs stop all modeling | Use a stable SHA-256 rank 60/20/20 split only as a retrospective internal benchmark | permits reproducible comparison while explicitly blocking time-validation claims | Yes | Orchestrator | Accepted |
| DEC-009 | 2026-07-27 | Unsupported Risk Components | create numeric proxies vs defer | Do not estimate Stage, EAD, LGD, ECL, or sensitivity from the current source | current fields cannot support governed component definitions; Stage and scenario assumptions need human approval | Yes | Orchestrator | Accepted |
| DEC-010 | 2026-07-27 | Gate 5 with no Office GUI renderer | block all consistency evidence vs separate structural/value QA from visual publication review | Pass Gate 5 on independent structural/value/hash reconciliation and keep human publication pending until visual inspection | Gate 5 tests numerical consistency; the unrun layout review remains visible as `RPT-001` | Yes | Orchestrator | Accepted |
| DEC-011 | 2026-07-27 | Make the GitHub repository legible to an EY FSRM hiring reviewer without creating a second numerical truth | prose-only README vs decorative static graphic vs tested run-bound evidence map | Add a recruiter-facing SVG and capability table whose numerical labels are checked against validated JSON | Shows SQL, QA, Risk Component boundaries, Office, PM, and control evidence in 30 seconds while preserving the Harness authority chain | Yes | User / Orchestrator | Accepted |

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
| DEC-008 | `src/models/`, `sql/risk_components/`, Wave 2 outputs | call the customer-ID split pseudo-temporal | conservative modeling and validation boundary | use an approved timestamped source and a new model definition/run | model result → validation → blocked Gate 4 |
| DEC-009 | `config/scenarios.yml`, `docs/methodology/risk_component_scope.md` | fabricate unsupported proxy values | explicit user and Harness approval boundaries | introduce a new approved definition only when eligible data and assumptions exist | deferred components → limitations/report |
| DEC-010 | Office manifest, validation report, Gate 5 packet | silently treat structural reopen as visual rendering | reporting and publication separation-of-duties | run LibreOffice/Office visual inspection and resolve `RPT-001`; Gate 5 evidence remains historical | Office artifacts → human publication decision |
| DEC-011 | `README.md`, `docs/assets/fsrm_portfolio_evidence_map.svg`, SVG reporting tests | repeat verified numbers in an untested decorative asset | explicit user clarification of the portfolio goal plus existing Gate evidence | update or remove the SVG through its drift test; never edit validation evidence to fit presentation | validated JSON/Gate 5 → tested SVG → recruiter capability map |

## Required fields for new decisions

- affected files and outputs
- discarded alternatives
- approval requirement
- rollback method
- downstream nodes affected
