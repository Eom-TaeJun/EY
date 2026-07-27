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
| DQ-009 | age and category values follow inspected source domains | zero unexplained invalid |
| DQ-010 | required history values are present | zero missing or documented exceptions |

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
