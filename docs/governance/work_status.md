# Work Status

## Current summary

- Wave: Wave 4 supported scope complete; human publication review pending
- Gate reached: G0–G3 passed; G4 blocked; Wave 1 G5 passed
- Current owner: Orchestrator
- Latest analytical run: `W1-20260727-001`, definition `0.1.0`
- Latest model run: `W2-PD-20260727-001`, definition `0.2.0`
- Current limitations: `DATA-001`, `MODEL-001`, `SCEN-001`, and `RPT-001`;
  external publication remains blocked by human approval

## Run log

| Run ID | Date | Agent | Objective | Changed files | Commands/tests | Result | Issues | Next action |
|---|---|---|---|---|---|---|---|---|
| RUN-000 | 2026-07-27 | Scaffold | Create agent-ready repository | initial files | `python scripts/validate_scaffold.py` | Passed | None | Run Wave 0 review |
| RUN-001 | 2026-07-27 | Orchestrator | PUR-001–004: repair Wave 0 controls and make Gate 0 executable | Harness, agent contracts, governance controls, validator, Makefile, state | `make gate0`; `make gate1` (expected pre-evidence failure); `python -m compileall scripts` | Passed; Gate 1 failed closed as designed | GOV-001 | Independent re-review |
| RUN-002 | 2026-07-27 | Reviewer | Independently re-review Gate 0 repairs | read-only governance evidence | contract review; confirmed `make gate0` result | Approve; Critical 0, Major 0 | GOV-001 resolved | Start Wave 1 Hermes packet |
| RUN-003 | 2026-07-27 | Hermes | Register, inspect, hash, and load the immutable UCI source | source registry, pinned loader/DDL, raw audit logs | official download; `--inspect-only`; DB load IDs `uci350-raw-load-20260727-001` and `-002` | 30,000 inserted on first run; second run inserted 0 and matched 30,000; 0 rejects | ENV-001 opened then resolved | Build run-scoped core |
| RUN-004 | 2026-07-27 | Data Model / SQL QA | Build borrower and customer-month data, reconcile, and execute SQL tests | core/mart/audit DDL; staging, reconciliation, DQ and business-rule SQL | local PostgreSQL 16.14; SQL files `010` through `050` for `W1-20260727-001` | borrower 30,000; customer-month 180,000; 16/16 reconciliations pass; DQ 15 pass, 0 fail, 3 warn; BR 5 warn | SQL-001 resolved; DATA-001 open | Build signals |
| RUN-005 | 2026-07-27 | Risk Signal / Validation | Build seven signals and predeclared risk bands; export and independently reproduce evidence | risk definition `0.1.0`, signal/summary SQL, snapshots, Gate packets | `060_risk_signals.sql`; `070_signal_summaries.sql`; exporter; reproduction module; `make gate1 gate2 gate3` | Attempt 1 failed closed; attempt 2 passed Gates 1–3 with empty validation issues | VAL-001 resolved | Generate controlled internal report |
| RUN-006 | 2026-07-27 | Graph / Documentation | Register validated data lineage and generate a run-bound internal report | `meta.node`/`meta.edge`, Wave 1 lineage seed, report and claim manifest | graph DDL/test; lineage SQL executed twice; report check/generation | 20 durable lineage nodes, 35 edges, 7 validated feature nodes; report publication remains pending | Gate 5 not attempted | Full regression and local checkpoints |
| RUN-007 | 2026-07-27 | Risk Component | Execute static, behavioral, and combined PD prototypes without unsupported components | Wave 2 SQL extract/reconciliation, model code, scope/scenario controls | actual PostgreSQL reconciliation; `W2-PD-20260727-001`; 7 model tests | input 30,000/default 6,636; split 18,000/6,000/6,000; model artifact created | W2-SQL-001 resolved; MODEL-001 and SCEN-001 blocked | Independent reproduction |
| RUN-008 | 2026-07-27 | Validation | Recompute Wave 2 populations, predictions, metrics, calibration, and segments | independent validator and two immutable attempts | attempt 1 fail retained; attempt 2 blocked with all numerical checks pass; 5 validator tests | static/behavioral/combined AUC 0.634600/0.740660/0.754496 on the same 6,000 test rows | W2-VAL-001 resolved; G4 remains blocked | Do not publish model conclusions |
| RUN-009 | 2026-07-27 | Graph | Complete both graph scopes without mixing causal hypotheses and lineage | additive claim-to-source dependencies; economic-hypothesis seed and tests | final SQL applied/replayed; exact path/economic contract tests | data-lineage 20 nodes/59 edges; economic 14 nodes/20 edges | no numerical definition impact | Add governed retrieval |
| RUN-010 | 2026-07-27 | Documentation | Generate a run-bound Wave 1 Office review pack | Office generator, manifest, XLSX/PPTX/DOCX | 5 reporting tests; OOXML integrity; library reopen and cross-value checks | Excel 8 sheets; PPT 7 slides/2 charts; Word 11 headings/7 tables | RPT-001 open | Independent Gate 5 |
| RUN-011 | 2026-07-27 | Validation | Independently reopen and reconcile every Wave 1 Office artifact | Office validation report and Gate 5 packet | tamper/mixed-run/no-overwrite tests; `make gate5` | mismatch 0; unresolved claims 0/6; Gate 5 pass | human approval pending | Update evidence map |
| RUN-012 | 2026-07-27 | Documentation / Knowledge | Answer six governed traceability questions without free-form SQL or numerical generation | code+YAML allowlist, query CLI, Wiki contract | 14 knowledge tests; all six CLI queries | six evidence-cited answers; Wave 2 blocked status preserved | semantic search/LLM deferred | Final regression |
| RUN-013 | 2026-07-27 | Orchestrator / Documentation | Reframe the completed project as a 30-second EY FSRM hiring evidence package and close the internal checkpoint | README, final/handoff docs, recruiter-facing SVG, SVG drift tests, governance state | headless SVG render review; `python -m pytest -q`; Ruff; compile; scaffold/governance; `make gate0 gate1 gate2 gate3 gate5`; final PostgreSQL readback | SVG had no visible clipping/overlap; 63 tests passed; Gates 0–3 and 5 passed; DB readback matched 30,000/180,000, 16 reconciliation passes, 15 DQ passes, 3 warnings, 0 failures | Gate 4 remains blocked; RPT-001 and human publication approval pending | Stop temporary PostgreSQL and hand off exact review commands |

## Verified Wave 1 execution summary

| Control | Result | Evidence |
|---|---|---|
| Official source identity | XLS SHA-256 `30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933` | `docs/data/source_registry.md` |
| Raw ingestion | source/staged/raw 30,000; 0 rejected | `logs/ingestion/uci350-raw-load-20260727-001.json` |
| Idempotency | inserted 0; existing exact matches 30,000 | `logs/ingestion/uci350-raw-load-20260727-002.json` |
| Core population | 30,000 borrower; 180,000 customer-month | independent validation JSON |
| Amount reconciliation | bill and payment differences both 0 NTD | `audit.reconciliation_result` |
| SQL QA | 16 reconciliations pass; 15 enforced DQ pass; 0 fail; 3 DQ warnings; 5 analytical flags | `audit.reconciliation_result`, `audit.test_result` |
| Signal outcomes | 23 buckets across seven signals; all denominators and default counts reconciled | independent validation JSON |
| Risk bands | Low 14,952 / 11.69%; Medium 8,138 / 16.45%; High 6,910 / 51.36% | independent validation JSON |
| Lineage | 20 nodes and 59 edges in `data_lineage`; exact Artifact-to-Source paths pass for all seven Features | `meta.node`, `meta.edge`, `tests/graph/test_wave1_lineage_path.sql` |

## Wave 2 retrospective benchmark

The same 6,000-row test population contains 1,332 observed defaults.
Independent attempt 2 reproduced every reported population, probability,
metric, calibration, segment, run, version, and component-scope check.

| Model | ROC AUC | PR AUC | Brier score |
|---|---:|---:|---:|
| Static | 0.634600 | 0.320896 | 0.166000 |
| Behavioral | 0.740660 | 0.488144 | 0.144819 |
| Combined | 0.754496 | 0.494651 | 0.143825 |

These values are a cross-sectional retrospective internal benchmark, not an
out-of-time or external validation result. Gate 4 remains blocked by the two
explicit issues below; no Stage, EAD, LGD, ECL, or scenario value exists.

## Wave 3–4 verification summary

| Control | Result | Evidence |
|---|---|---|
| Claim-to-source path | exact depth-10 Artifact-to-Source path for all seven features | `tests/graph/test_wave1_lineage_path.sql` |
| Economic hypotheses | 14 nodes / 20 edges; positive, negative, mixed, and contradicted statuses retained | `tests/graph/test_wave1_economic_hypotheses.sql` |
| Governed knowledge | six fixed question IDs; failed/scratch evidence excluded | `tests/knowledge/test_governed_knowledge_query.py` |
| Office pack | XLSX/PPTX/DOCX reopened; manifest hashes and all governed values matched | Office manifest and independent Office validation |
| Gate 5 | mismatch 0; unresolved claim count 0; limitations 6/6 | `outputs/qa/validated/latest/gate_5.json` |

Gate 5 establishes internal cross-artifact consistency. It does not replace the
pending human publication approval or the unrun LibreOffice visual-layout
inspection.

The PostgreSQL process used for this run is a reversible unpacked local runtime
under `/tmp`; Docker remains the canonical clean-environment command. No
system package, external listener, secret, push, or deployment was used.

The README evidence-map SVG is a presentation layer, not a numerical authority.
`tests/reporting/test_fsrm_portfolio_evidence_map.py` binds its run ID, population,
risk-band rates, Gate 5 mismatch count, and IFRS 9 limitation to validated JSON.

## Update format

Every completed task must record:

- objective and purpose ID
- input and output files
- exact commands
- test evidence
- failed checks and issue IDs
- decisions made
- next unblocked task
