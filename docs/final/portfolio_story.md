# Portfolio Story

Status: Waves 0–4 are implemented to the supported public-data scope. Wave 1
passed internal Gate 5; external publication approval remains pending. Wave 2
Gate 4 is blocked.

## Decision-relevant result

The project turns an unfamiliar public credit-risk workbook into a reproducible
PostgreSQL, SQL-QA, risk-signal, validation, lineage, and reporting workflow.
Every numerical statement is tied to one source hash, run ID, definition
version, independent validation artifact, and claim ID.

## What was executed

- The official UCI workbook was registered and loaded without changing source
  values. Run `W1-20260727-001` reconciled 30,000 raw/borrower rows and 180,000
  borrower-month rows, with bill and payment differences of zero.
- Fifteen enforced DQ tests passed, none failed, and three source-domain
  warnings were retained. Seven behavioral signals produced 23 measured
  buckets; contradictory and non-monotonic findings were not removed.
- Excel, PowerPoint, Word, and Markdown outputs were generated from the same
  validation JSON and claim manifest. The [Gate 5 packet](../../outputs/qa/validated/latest/gate_5.json)
  records zero cross-artifact mismatches and zero unresolved claims.
- Static, behavioral, and combined PD prototypes were independently reproduced
  on one fixed 6,000-row test sample. The result is labelled a cross-sectional
  retrospective internal benchmark because the source has no eligible time
  direction; [Gate 4 remains blocked](../../outputs/qa/validated/wave2_attempt_02/wave2_validation.json).
- PostgreSQL stores [data lineage and economic hypotheses in separate graph
  scopes](../data/lineage_spec.md): 20 lineage nodes/59 edges and 14 economic
  nodes/20 edges passed their exact graph contracts. A [governed
  query](../wiki/knowledge_query.md) answers six fixed traceability questions
  from a code-and-manifest allowlist; it is not free-form SQL, semantic RAG, or
  an LLM.

## Reviewer evidence

- Source and transformation: [source registry](../data/source_registry.md),
  [data dictionary](../data/data_dictionary.md)
- SQL controls and results: [test catalog](../validation/test_catalog.md),
  [Wave 1 validation](../../outputs/qa/validated/latest/wave1_independent_validation.json)
- Risk reasoning: [signal dictionary](../methodology/signal_dictionary.md),
  [economic hypotheses](../methodology/transmission_paths.md)
- Generated review pack: [Excel](../../outputs/final/wave1_office_pack__W1-20260727-001.xlsx),
  [PowerPoint](../../outputs/final/wave1_office_pack__W1-20260727-001.pptx),
  [Word](../../outputs/final/wave1_office_pack__W1-20260727-001.docx)
- Reproduction and handoff: [runbook](../wiki/runbook.md),
  [evidence map](evidence_map.md)

## Limitations

This is a public-data prototype, not an official bank IFRS 9 implementation.
No production rating, Stage, EAD, LGD, ECL, causal, out-of-time, external
validation, or model-approval claim is made. LibreOffice was unavailable, so
visual-render QA is `not_run`; OOXML structural reopen and value reconciliation
passed, and a human must still inspect layout and approve publication.
