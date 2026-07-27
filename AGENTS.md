# AGENTS.md

This file is the repository map for coding agents. Keep it concise.

## Mission

Build a traceable credit-risk analysis harness that proves the author can support real financial-risk consulting work: ingest data safely, query it with SQL, test data and business rules, explain risk changes, and hand the work over to another analyst.

## Read order

Before changing anything, read:

1. `HARNESS.md`
2. `PROJECT_STATE.md`
3. `docs/charter/project_charter.md`
4. the relevant `docs/*/INDEX.md`
5. the current task prompt under `prompts/`
6. the relevant role contract under `agents/`

Do not load every document indiscriminately. Follow the indexes.

## Authority and scope

- `HARNESS.md` defines non-negotiable controls.
- `PROJECT_STATE.md` defines the active Wave and current priorities.
- A task packet defines the bounded work for the current run.
- Do not expand scope without recording a decision in `docs/governance/decision_ledger.md`.

## Non-negotiable rules

- Never modify files under `data/raw/` after ingestion.
- Never invent source data, test results, model metrics, or portfolio numbers.
- All derived values must have an explicit SQL or deterministic-code path.
- Do not publish analysis before upstream reconciliation and quality gates pass.
- Treat Stage, ECL, LGD, and EAD as prototypes or proxies unless the data supports them.
- Builders do not approve their own work. Use the validation and review contracts.
- Preserve failed tests and issue history; do not hide or manually overwrite them.
- Require human approval for destructive actions, source deletion, definition changes, threshold relaxation, external publication, and final interpretation.

## Working method

Use the loop:

`Inspect → Plan → Implement → Test → Critique → Reconcile → Checkpoint`

At the start, state:

- objective
- files to change
- inputs and outputs
- tests to run
- rollback path

At the end, update `docs/governance/work_status.md` with evidence.

## Current critical path

1. governance and repository controls
2. raw ingestion and file registry
3. relational schema and wide-to-long transformation
4. SQL data-quality and reconciliation tests
5. risk signals and observed default-rate summaries
6. documentation and evidence map

Later Waves add models, scenarios, lineage, RAG, Wiki, and automation without replacing the earlier path.

## Testing

When commands exist, run the smallest relevant checks first, then integration checks. Record exact commands and outputs in the work status. A task is not complete because code looks correct.

## Documentation

- Update definitions when code changes.
- Link every portfolio claim to a query, test, result, or decision record.
- Keep `README.md` reader-facing; keep detailed operating rules in `HARNESS.md` and `docs/`.
