# Wave 1 Review Deck Contract

Status: generated and Gate 5-reconciled for `W1-20260727-001`; human external
publication approval remains pending.

| Slide | Decision-relevant message | Generated evidence | Claim IDs |
|---:|---|---|---|
| 1 | This is a controlled credit-risk data, SQL, validation, and reporting workflow | run/definition/publication metadata | scope |
| 2 | One validated evidence packet drives every review artifact | source, population, QA, and Gate summary | W1-CLM-001–006 |
| 3 | The relational transformation preserves rows and amounts | source/raw/borrower/month and bill/payment reconciliation | W1-CLM-001–003 |
| 4 | SQL controls expose failures and retain source-domain warnings | DQ result table and limitation | W1-CLM-004 |
| 5 | Initial risk bands separate observed outcomes but are not ratings or Stage | three-band generated chart/table | W1-CLM-006 |
| 6 | Six-month delinquency frequency has explicit samples and denominators | generated bucket chart/table | W1-CLM-005 |
| 7 | Claims remain traceable and publication-controlled | claim manifest, validation hash, limitations, approval boundary | W1-CLM-001–006 |

## Evidence

- [Generated PPTX](../outputs/final/wave1_office_pack__W1-20260727-001.pptx)
- [Office manifest](../outputs/final/wave1_office_manifest__W1-20260727-001.json)
- [Office validation](../outputs/qa/validated/wave1_office/wave1_office_validation__W1-20260727-001.json)
- [Gate 5 packet](../outputs/qa/validated/latest/gate_5.json)

## Prohibited edits

- typing or pasting a numerical result into the deck;
- mixing run IDs or definition versions;
- removing a warning, failed test, or limitation;
- describing the bands as a bank rating, Stage, or approved model;
- treating structural OOXML QA as visual-render approval;
- changing publication status without human approval.
