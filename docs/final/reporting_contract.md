# Validated-Output Reporting Contract

## Decision supported

Wave 1 reader artifacts are rebuildable views, not new numerical authorities.
The [independent validation JSON](../../outputs/qa/validated/latest/wave1_independent_validation.json)
and its source/code references remain authoritative.

## Input and fail-closed controls

The Markdown and Office builders require one passing Wave 1 validation artifact
and the run-bound claim manifest. They reject missing, failed, malformed,
mixed-run, non-finite, duplicate, or arithmetically inconsistent evidence and
recompute:

- source/raw/borrower and borrower-month row reconciliation;
- wide-to-long bill and payment reconciliation;
- SQL test counts and failures;
- signal and risk-band populations, defaults, and observed rates;
- run ID, definition version, claim IDs, validation hash, and limitations.

Outputs are created with exclusive-write semantics. Corrected evidence requires
a new run/output path; a reviewer must not edit a displayed number to repair a
mismatch.

## Generated artifacts

For `W1-20260727-001`, the controlled outputs are:

- [Markdown report](../../outputs/final/wave1_internal_report__W1-20260727-001.md)
  and [claim manifest](../../outputs/final/wave1_claim_manifest__W1-20260727-001.json);
- [Excel workbook](../../outputs/final/wave1_office_pack__W1-20260727-001.xlsx);
- [PowerPoint deck](../../outputs/final/wave1_office_pack__W1-20260727-001.pptx);
- [Word report](../../outputs/final/wave1_office_pack__W1-20260727-001.docx);
- [Office manifest](../../outputs/final/wave1_office_manifest__W1-20260727-001.json).

The workbook contains eight review sheets. The deck contains seven slides and
two generated charts. Excel, PowerPoint, and Word values are recorded in the
Office manifest and independently reopened and reconciled.

## Commands

Validate the current inputs without writing:

```bash
python -m src.reporting.build_wave1_report \
  --validation outputs/qa/validated/latest/wave1_independent_validation.json \
  --check-only
python -m src.reporting.build_wave1_office_pack --check-only
```

Generate a new eligible run's Markdown and Office artifacts:

```bash
python -m src.reporting.build_wave1_report \
  --validation <NEW_VALIDATION_JSON> \
  --output-dir <NEW_OUTPUT_DIR>
python -m src.reporting.build_wave1_office_pack \
  --validation <NEW_VALIDATION_JSON> \
  --claim-manifest <NEW_CLAIM_MANIFEST> \
  --output-dir <NEW_OUTPUT_DIR>
```

Independently validate a new Office pack and emit a new Gate 5 packet:

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

For the retained current evidence, run:

```bash
make gate5
```

## Current validation and publication boundary

The [Office validation report](../../outputs/qa/validated/wave1_office/wave1_office_validation__W1-20260727-001.json)
and [Gate 5 packet](../../outputs/qa/validated/latest/gate_5.json) both pass:
all three Office artifacts share one run ID, `mismatch_count=0`, and
`unresolved_claim_count=0`. Six limitations are documented.

Gate 5 proves internal cross-artifact consistency; it does not approve external
publication, a model, risk grade, Stage, EAD, LGD, ECL, or causal
interpretation. Human publication approval remains pending. LibreOffice was
unavailable, so visual-render QA is `not_run`; structural OOXML/package reopen
and value QA completed.
