# Portfolio Story

## Problem

Credit-risk calculations are only useful when the project team can trust the data, reproduce the calculation, explain a change, and hand the process to another analyst.

## Approach

- defined the decision and constraints before selecting metrics
- preserved source data through a Hermes ingestion boundary
- converted repayment history into a relational customer-month structure
- created SQL tests for source integrity, transformations, and business rules
- translated economic reasoning into observable behavioral signals
- planned independent validation and claim-to-source lineage
- restricted LLM use to retrieval, explanation, and documentation of approved evidence

## Evidence to add after execution

- source and customer-month reconciliation results
- number and status of SQL tests
- observed default-rate separation by signal and risk band
- one issue investigation and resolution path
- one claim-to-source lineage example

## Limitation

This is a public-data prototype, not an official bank IFRS 9 implementation.
