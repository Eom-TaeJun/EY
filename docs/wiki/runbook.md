# Runbook

## Purpose and safety boundary

This runbook reproduces Wave 1 without repairing source data, relaxing a
threshold, overwriting evidence, or publishing an unapproved result. Run every
command from the repository root. `PROJECT_STATE.md` is the current-state
authority; this page is the operating procedure.

The retained run `W1-20260727-001` passed Gates 1–3 and Office Gate 5.
External publication remains pending human approval. Wave 2 model metrics were
independently reproduced, but Gate 4 is blocked and must not be promoted to a
time-validated or IFRS 9 result.

## 1. Preflight

Confirm the expected root and scaffold before a database or Git command.

```bash
pwd
python scripts/validate_scaffold.py
```

Copy the environment template once, set a local-only password, and do not print
or commit the resulting `.env`.

```bash
cp -n .env.example .env
```

Install the project dependencies in an isolated Python environment. The
workbook inspector additionally requires `xlrd>=2.0`.

```bash
python -m pip install -e .
python -m pip install "xlrd>=2.0"
```

## 2. Inspect the immutable source

The inspector verifies pinned archive/workbook hashes, workbook structure,
integer representation, and duplicate IDs. It creates a new log and never
updates the source.

```bash
python src/ingestion/load_uci_credit_card.py --inspect-only
```

Expected behavior:

- exit `0` only after all source checks pass;
- create a new JSON log under `logs/ingestion/`;
- refuse to overwrite an existing run log;
- make no database connection in inspect-only mode.

If the check fails, stop the raw-loading branch. Do not edit, rename, unzip
over, or repair a file under `data/raw/`.

## 3. Start PostgreSQL and load raw data

Start the repository service and check its health.

```bash
docker compose up -d postgres
docker compose ps
```

Set `DATABASE_URL` in the current shell without echoing it. Use a new, explicit
run ID for every attempt.

```bash
python src/ingestion/load_uci_credit_card.py \
  --run-id <NEW_INGESTION_RUN_ID>
```

The loader creates the raw/audit objects, loads insert-only, and reconciles the
source to raw. A repeated proof run uses another run ID and must match existing
rows without replacing them.

## 4. Build core, QA, and signals

Use a new `RUN_ID`; the run-scoped tables prevent overwriting prior evidence.

```bash
export RUN_ID=<NEW_WAVE1_RUN_ID>
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/ddl/010_core_mart_audit.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/ddl/030_meta_graph.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v run_id="$RUN_ID" -f sql/staging/020_build_core.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v run_id="$RUN_ID" -f sql/reconciliation/030_core_reconciliation.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v run_id="$RUN_ID" -f sql/quality/040_data_quality.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v run_id="$RUN_ID" -f sql/business_rules/050_behavior_flags.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v run_id="$RUN_ID" -f sql/features/060_risk_signals.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v run_id="$RUN_ID" -f sql/reporting/070_signal_summaries.sql
python scripts/export_wave1_snapshot.py \
  --database-url "$DATABASE_URL" \
  --run-id "$RUN_ID" \
  --output "outputs/qa/attempts/$RUN_ID/wave1_snapshot.json"
```

The exporter queries database facts; do not hand-build a snapshot or copy
numbers from a SQL client into JSON.

The required snapshot contract is documented in
[`model_validation_plan.md`](../validation/model_validation_plan.md). It must
be generated from the database objects for one run ID and include source,
core, SQL-test, signal-definition, signal-outcome, and risk-band evidence.

## 5. Reproduce Gate 1–3 evidence independently

Validation writes a new output and refuses to overwrite an existing result.

```bash
python -m src.validation.wave1_reproduction \
  --snapshot "outputs/qa/attempts/$RUN_ID/wave1_snapshot.json" \
  --output "outputs/qa/validated/$RUN_ID/wave1_independent_validation.json" \
  --emit-gate-packets "outputs/qa/validated/$RUN_ID"
```

Then run the public Gate checks after the Orchestrator has installed the
reviewed packets at their canonical locations.

```bash
make gate1
make gate2
make gate3
```

A nonzero exit, missing packet, different run ID, missing artifact, or
non-empty validation issue blocks downstream claims.

## 6. Generate an internal reader-facing report

First check eligibility without writing a report.

```bash
python -m src.reporting.build_wave1_report \
  --validation outputs/qa/validated/latest/wave1_independent_validation.json \
  --check-only
```

If eligible, generate a new Markdown report and claim manifest.

```bash
python -m src.reporting.build_wave1_report \
  --validation outputs/qa/validated/latest/wave1_independent_validation.json \
  --output-dir outputs/final
```

The command:

- revalidates Gate 1–3 packets and run identity;
- recomputes key reconciliations and observed default rates;
- writes run-specific files without overwriting;
- labels publication `pending`;
- does not imply Gate 5 or human approval.

Use [`evidence_map.md`](../final/evidence_map.md) to review each claim's
activation condition and [`reporting_contract.md`](../final/reporting_contract.md)
for the generated-file contract.

## 7. Gate 5 and publication

Check the Office inputs without writing:

```bash
python -m src.reporting.build_wave1_office_pack --check-only
```

For a new eligible run, generate the review pack from that run's validation and
claim manifest. Use a new output directory/path; the builder does not
overwrite.

```bash
python -m src.reporting.build_wave1_office_pack \
  --validation <NEW_VALIDATION_JSON> \
  --claim-manifest <NEW_CLAIM_MANIFEST> \
  --output-dir <NEW_OUTPUT_DIR>
```

Independently reopen and reconcile the new files, again using new evidence
paths:

```bash
python -m src.validation.wave1_office_validation \
  --office-manifest <NEW_OFFICE_MANIFEST> \
  --validation <NEW_VALIDATION_JSON> \
  --claim-manifest <NEW_CLAIM_MANIFEST> \
  --evidence-map docs/final/evidence_map.md \
  --artifact-root . \
  --output <NEW_OFFICE_VALIDATION_JSON> \
  --gate-output <NEW_GATE5_PACKET>
```

Gate 5 requires Markdown/Excel/PowerPoint/Word outputs to share one run ID and
reconcile. Recheck the retained canonical packet with:

```bash
make gate5
```

The current [Gate 5 packet](../../outputs/qa/validated/latest/gate_5.json)
passes with zero mismatches and zero unresolved claims. Human publication
approval is still pending. LibreOffice was unavailable, so visual-render QA is
`not_run`; structural OOXML reopen and value QA completed. Inspect charts,
clipping, and pagination in an Office-compatible renderer before approval.

## 8. Check Wave 2 and Wave 3 boundaries

Read the independent Wave 2 result; do not infer approval from passing numeric
checks:

```bash
python -m pytest -q tests/models tests/validation
```

The retained [attempt 2](../../outputs/qa/validated/wave2_attempt_02/wave2_validation.json)
is a cross-sectional retrospective internal benchmark. Gate 4 is blocked by
missing genuine time direction and approved sensitivity values. No Stage,
EAD, LGD, or ECL was estimated.

Verify the bounded knowledge interface:

```bash
python -m src.knowledge.query --list-questions
python -m src.knowledge.query --question-id metric_calculation
python -m pytest -q tests/knowledge
```

The CLI accepts only six fixed question IDs and allowlisted evidence. PostgreSQL
keeps `data_lineage` and `economic_transmission` in separate graph scopes; see
the exact SQL checks in the [lineage specification](../data/lineage_spec.md).

## Recovery matrix

| Symptom | Safe recovery | Forbidden shortcut |
|---|---|---|
| Source inspection fails | retain failed log; compare file/hash with source registry; obtain the official file through the approved source process | edit or replace `data/raw/` without approval |
| PostgreSQL unavailable | retain source inspection evidence; record the environment blocker; retry the same code in a working PostgreSQL environment with a new run ID | claim raw/core/SQL execution passed |
| Raw conflict detected | preserve the failed ingestion run; inspect conflicting IDs read-only; escalate source/raw mismatch | update, delete, truncate, or recode raw rows |
| Core reconciliation fails | preserve failing tests; fix the earliest deterministic transformation; create a new run | alter an amount, count, or tolerance in output |
| Signal gate fails | inspect timing, leakage, definition, and population evidence; rerun upstream as needed | tune a threshold solely to force separation |
| Validation output exists | use a new output path and run ID | overwrite the existing validation JSON |
| Report output exists | keep it as historical evidence and generate from a new validated run | edit or overwrite report numbers |
| Cross-artifact mismatch | identify the first differing producer and regenerate downstream outputs | copy/paste numbers to make artifacts agree |
| Visual renderer unavailable | retain structural QA, record `not_run`, inspect in an Office-compatible renderer before approval | treat OOXML reopen as visual-layout approval |
| Wave 2 numerical checks pass but Gate 4 is blocked | retain the benchmark and blockers; obtain eligible time/scenario evidence | call an ID split time validation or infer Stage/EAD/LGD/ECL |

## Resume checklist

1. Read `PROJECT_STATE.md` and `docs/governance/work_status.md`.
2. Identify the latest run that passed the last completed Gate.
3. Confirm source hash and database target before resuming.
4. Preserve all failed run IDs, logs, tests, and issue links.
5. Resume from the earliest affected transformation.
6. Regenerate every downstream artifact from the new run.
7. Request independent review; do not self-approve the Gate.
