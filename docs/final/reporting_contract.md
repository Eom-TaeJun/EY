# Validated-Output Reporting Contract

## Decision supported

Allow a reviewer to read Wave 1 evidence without creating a second numerical
authority. The report is a rebuildable view; the independent validation JSON
and its referenced source/code artifacts remain the evidence.

## Input

`src.reporting.build_wave1_report` accepts exactly one independent Wave 1
validation JSON. It requires:

- schema version `1.0`;
- non-blank run ID and validation timestamp;
- overall `status=pass` and an empty issue list;
- exactly one Gate 1, Gate 2, and Gate 3 packet for the same run;
- valid independent contract reports for Gates 1–3;
- complete `verified_findings`;
- referenced repository artifacts when the CLI runs from this repository.

Missing, failed, malformed, mixed-run, non-finite, duplicate, or arithmetically
inconsistent evidence blocks generation.

## Recomputed controls

The reporting boundary does not merely trust the displayed values. It checks:

- source rows equal raw rows;
- raw rows equal borrower rows;
- borrower-month rows equal borrowers multiplied by six;
- wide and long bill/payment differences are arithmetically consistent and
  pass the configured Gate threshold;
- SQL test count matches Gate 2 and failed count is zero;
- signal and risk-band outcome counts match Gate 3;
- each outcome population ties to borrower rows;
- each observed default rate equals defaults divided by sample.

## Outputs

For run `<RUN_ID>`, the command creates new files under the selected output
directory:

- `wave1_internal_report__<RUN_ID>.md`;
- `wave1_claim_manifest__<RUN_ID>.json`.

The manifest records:

- run and definition versions;
- input validation reference and SHA-256;
- report SHA-256;
- claim IDs and JSON evidence pointers;
- deterministic percentage-display rule;
- publication status.

The builder refuses to overwrite either file. A corrected upstream result
requires a new validation output and report run.

## Publication boundary

Generated files are labelled internal drafts. The command cannot:

- pass or approve Gate 5;
- approve a model, definition, rating, Stage, or risk interpretation;
- publish a portfolio claim;
- remove a limitation;
- reconcile another artifact by editing a number.

Gate 5 and explicit human publication approval are required before external
quotation.

## Commands

Eligibility check:

```bash
python -m src.reporting.build_wave1_report \
  --validation outputs/qa/wave1_independent_validation.json \
  --check-only
```

Internal report generation:

```bash
python -m src.reporting.build_wave1_report \
  --validation outputs/qa/wave1_independent_validation.json \
  --output-dir outputs/final
```

## Report shape

The technical report follows this reading order:

1. publication boundary and technical summary;
2. scope and metric definitions;
3. source/core/amount reconciliations;
4. SQL-control status;
5. signal-bucket observed outcomes;
6. risk-band observed outcomes;
7. method and traceability;
8. limitations and uncertainty;
9. next steps and further questions.

Exact audit tables are used for Wave 1. Charts are deferred because no
publication-reviewed run output is currently available; a future visualization
must retain the same run ID, denominators, claim IDs, and source metadata.
