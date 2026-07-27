# Governed Knowledge Query

## Decision-relevant outcome

The Wave 3 knowledge layer answers six fixed repository questions with
machine-checkable citations. It does not execute SQL, call an LLM, create
numbers, approve a model, or search arbitrary files.

## Approved boundary

`config/knowledge_sources.yml` is the reader-facing allowlist. The same exact
paths and evidence-status labels are pinned in `src/knowledge/query.py`, so a
manifest edit cannot silently add a scratch file. At startup, the service also
requires:

- Wave 1 status `pass`, an empty issue list, and a validation SHA-256 matching
  the run-bound claim manifest;
- a shared Wave 1 run ID and definition version;
- publication status `pending`;
- Wave 2 status `blocked`, Gate 4 ineligible, approval not granted, and one or
  more explicit blockers.

Failed Wave 1 evidence, Wave 2 attempt 1, attempt snapshots, scratch, and
notebooks are excluded. The CLI accepts a question ID, not a path, SQL, or
free-form prompt.

## Six governed questions

| Question ID | Governed question | Evidence outcome |
|---|---|---|
| `metric_calculation` | How is the observed default-rate metric calculated? | Formula and values copied from validated Wave 1 evidence |
| `source_fields` | Which source fields feed the six-month delinquency signal? | Approved source, data, and signal dictionaries |
| `failed_test_impact` | What is affected if DQ-003 fails? | Test-to-table-to-claim impact with the latest actual result retained |
| `report_consumers` | Which governed report consumes the risk-band result? | Run-bound internal-report claim manifest and report procedure; publication remains pending |
| `definition_rationale` | Why were the initial risk-band thresholds chosen? | Accepted DEC-005 text, including reversibility |
| `latest_run_changes` | What changed in the latest validated or blocked run? | Wave 2 scope and blockers, explicitly labelled blocked |

Every response includes `run_id`, `definition_version`, `evidence_status`,
repository paths, and either Markdown headings or resolvable JSON pointers.

## Execution

List supported IDs:

```bash
python -m src.knowledge.query --list-questions
```

Answer one question:

```bash
python -m src.knowledge.query --question-id metric_calculation
python -m src.knowledge.query --question-id source_fields
python -m src.knowledge.query --question-id failed_test_impact
python -m src.knowledge.query --question-id report_consumers
python -m src.knowledge.query --question-id definition_rationale
python -m src.knowledge.query --question-id latest_run_changes
```

Run the fail-closed contract:

```bash
python -m pytest -q tests/knowledge
python -m ruff check src/knowledge tests/knowledge
```

An unknown question, source ID, traversal attempt, missing citation, changed
artifact hash, broadened allowlist, or unblocked Wave 2 label terminates with a
nonzero result.

## Limitations

This is deterministic governed retrieval, not semantic search. It has no
vector database and makes no claim that an LLM is implemented. Adding a source
or question requires a reviewed code-and-manifest change. The impact query is
the predeclared DQ-003 dependency packet; broader graph traversal remains in
the PostgreSQL lineage layer and is not exposed as natural-language SQL.
