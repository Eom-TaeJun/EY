# Wave 1 Data and SQL Prompt

## Objective

Produce the strongest same-day evidence that the author can support real financial-risk project work: source handling, relational modeling, SQL testing, reconciliation, risk-signal analysis, and documentation.

## Critical path

1. register the approved UCI source and license/access notes
2. download or locate the source and record SHA-256, row count, columns, and parsing details
3. create PostgreSQL schemas: raw, staging, core, mart, audit, meta
4. load the source into `raw.credit_card_client` without changing values
5. create `core.borrower` and `core.account_month`
6. unpivot six months of repayment, bill, and payment history
7. reconcile raw borrowers, expected customer-month rows, bills, and payments
8. implement at least 12 SQL tests from the test catalog
9. build at least five approved behavioral risk signals
10. define an explainable initial risk band, recording threshold decisions
11. calculate observed default rates and sample sizes by signal and risk band
12. populate minimum lineage from source to README result
13. update README, work status, issue log, and evidence map with verified values only

## Harness constraints

- Stop at a failed gate and log an issue.
- Do not modify raw data.
- Do not claim LGD, EAD, Stage, or ECL.
- Do not tune thresholds solely to maximize full-sample separation.
- All final values must be reproducible from SQL or deterministic code.
- Builders cannot approve their own results.

## Final response

Report changed files, commands, reconciliation results, test results, verified analytical findings, issues, limitations, and next Wave 2 tasks.
