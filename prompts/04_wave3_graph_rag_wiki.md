# Wave 3 Graph, RAG, and Wiki Prompt

Proceed after definitions, tests, and core outputs are stable.

## Objective

Improve traceability and handoff without turning LLM output into a numerical authority.

## Work

- populate typed economic-transmission and data-lineage graphs separately
- implement impact analysis for failed tests and changed definitions
- generate Mermaid or queryable lineage views
- define approved RAG sources: dictionaries, tests, decisions, issues, runbook, validation reports
- exclude scratch and unvalidated outputs
- implement answer formats that cite repository paths, run IDs, and definition versions
- create Wiki pages for concepts, data, signals, tests, decisions, runs, issues, and handoff

## Prohibited

- unrestricted natural-language SQL execution
- LLM-defined risk classifications
- LLM approval of model results
- source-free explanations
