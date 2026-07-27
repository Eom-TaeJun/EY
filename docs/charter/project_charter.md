# Project Charter

## Problem

Credit-risk and impairment projects can fail before modeling because source data, observation timing, definitions, transformations, and tests are not aligned. The project must distinguish real risk movement from data or calculation errors and leave a reproducible audit trail.

## Target user

- EY FSRM senior or manager assigning analysis and testing work
- bank credit-risk or impairment analyst reviewing risk outputs
- new project team member receiving a handoff

## Decision supported

Can the author independently execute a bounded module of data analysis, SQL testing, reconciliation, issue tracking, and documentation under review?

## Core claim

The author can convert economic reasoning into measurable risk signals, build a controlled relational data flow, validate it with SQL, and trace final claims to source data and approved definitions.

## Deliverables

- governed repository and task graph
- source registry and immutable raw ingestion
- core borrower and account-month tables
- SQL test pack and issue log
- behavioral risk signal mart
- observed default-rate summaries
- Risk Component prototypes in later Waves
- lineage, RAG/Wiki, and reporting extensions

## Constraints

- same-day submission pressure
- public data rather than bank-internal data
- incomplete support for LGD, EAD, SICR, and lifetime ECL
- limited human review time

## Non-goals

- official bank IFRS 9 model
- regulatory submission
- unrestricted natural-language SQL
- UI-first dashboard
- agent autonomy without approval controls
