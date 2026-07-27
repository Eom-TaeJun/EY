# Test Catalog

## Source and structure

| Test ID | Rule | Expected |
|---|---|---|
| DQ-001 | customer ID unique in raw | zero duplicates |
| DQ-002 | raw row count matches registry | exact match |
| DQ-003 | each borrower has six account-month rows | exact match |
| DQ-004 | total account-month rows equal borrowers × 6 | exact match |
| DQ-005 | wide and long bill totals reconcile | within tolerance |
| DQ-006 | wide and long payment totals reconcile | within tolerance |

## Domain and required fields

| Test ID | Rule | Expected |
|---|---|---|
| DQ-007 | target values are allowed binary values | zero invalid |
| DQ-008 | credit limit follows approved rule | zero invalid or documented exceptions |
| DQ-009 | age follows plausible reviewed bounds 18–120 | zero invalid |
| DQ-010 | required history values are present | zero missing or documented exceptions |
| DQ-011 | account-month rows have a borrower parent | zero orphans |
| DQ-012 | month offsets map to approved month-end dates | zero mismatches |
| DQ-013 | sex uses UCI-documented codes 1–2 | zero invalid |
| DQ-014 | raw and core fixed attributes match exactly | zero differences |
| DQ-015 | raw and core outcomes match exactly | zero differences |
| DQ-016 | education uses UCI-documented codes 1–4 | warning with samples for other source values |
| DQ-017 | marriage uses UCI-documented codes 1–3 | warning with samples for other source values |
| DQ-018 | repayment status uses codes described on the UCI page | warning with samples for undocumented source values |

## Business-rule observations

These may be warnings rather than source errors.

| Test ID | Rule | Output |
|---|---|---|
| BR-001 | repeated zero payment | customer sample and count |
| BR-002 | repeated delinquency | customer sample and count |
| BR-003 | recent deterioration | customer sample and count |
| BR-004 | high utilization | distribution and count |
| BR-005 | low payment coverage | distribution and count |

Tests must record tested rows, failed rows, failure rate, severity, affected object, and run ID.

## Validated run result

For `W1-20260727-001`, 18 DQ tests executed: 15 passed, 0 failed, and
3 produced source-domain warnings. The five business-rule checks produced
analytical flags and are not source-error failures. Canonical facts are in
`outputs/qa/validated/latest/wave1_independent_validation.json`; detailed
warning counts and samples remain in `audit.test_result`.
