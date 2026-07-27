# Quality Gates

Gate checks fail closed: a missing command, evidence file, run ID, or required
review is a failure. Numeric tolerances come only from
`config/validation_thresholds.yml`.

| Gate | Command | Executable pass condition | Evidence location | Recommendation / approval | Blocks |
|---|---|---|---|---|---|
| G0 Governance | `make gate0` | scaffold and governance validators exit 0; ownership, accepted Wave 1 decisions, current state, and Approve/Revise step exist | validator output and `docs/governance/work_status.md` | Reviewer / Orchestrator records | implementation without scope control |
| G1 Source | `make gate1` | registered file has SHA-256 and nonzero byte/row/column counts; source rows equal raw rows; rejects are zero or logged | `audit.source_file`, `audit.ingestion_run`, ingestion log | Validation / Orchestrator records | core transformation |
| G2 Core | `make gate2` | duplicate and orphan counts are zero; borrower rows equal raw rows; account-month rows equal borrower rows × 6; bill and payment sums reconcile within configured tolerance; domains pass | `audit.test_result`, `audit.reconciliation_result` | Validation / Orchestrator records | risk signals |
| G3 Signal | `make gate3` | at least five versioned signals have rationale, observation timing, zero leakage failures, reproducible SQL, sample counts, and observed default rates from one validated run | `mart.borrower_risk_signal`, `mart.signal_default_summary`, timing review | Validation / Orchestrator records | model/report claims |
| G4 Model | `make gate4` | time-aware validation, calibration, segment stability, sensitivity direction, run/definition versions, and required proxy labels all pass | `outputs/model/` and `docs/validation/model_validation_plan.md` | Validation / Human for final interpretation | Risk Component conclusions |
| G5 Artifact | `make gate5` | DB/code/Excel/PPT/report values share one validated run ID and reconcile exactly or within configured tolerance; limitations and claim map are complete | `outputs/final/`, `docs/final/evidence_map.md` | Reviewer / Human for publication | external publication |

A failed gate creates an issue and remains visible. Do not relax a threshold to
make a check pass without a decision record and human approval.
