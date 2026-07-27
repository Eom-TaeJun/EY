# Project Harness

## 1. Purpose

The Harness controls how humans and agents convert an ambiguous financial-risk problem into reproducible evidence. It is not a model wrapper or a long prompt. It is the combination of objective control, source preservation, task contracts, typed relationships, validation gates, decision records, and stopping rules.

## 2. Objective function

Maximize evidence that a reviewer can safely assign the author the following work:

- understand unfamiliar credit-risk data
- load and query it using SQL
- detect data and calculation issues
- translate economic reasoning into measurable signals
- explain changes in risk outputs
- create client-ready and handoff-ready documents

Subject to these constraints:

- limited time and public data
- no access to bank-internal IFRS 9 rules
- no fabricated values
- reproducibility and traceability over model complexity
- deterministic calculations over LLM judgment

## 3. Audience and decision

Primary audience:

1. EY FSRM project manager or senior consultant
2. bank credit-risk or impairment practitioner
3. recruiter

Decision supported:

> Can this person be trusted with data analysis, testing, reconciliation, issue tracking, and documentation in a financial-risk project?

## 4. System of record

### Canonical sources

- immutable source files and their hashes
- source registry and license notes
- approved data dictionary
- approved risk and default definitions
- approved test catalog and thresholds
- versioned decision ledger
- validated run outputs identified by run IDs

### Rebuildable derived views

- staging and core tables
- features and risk signals
- model outputs
- charts and summaries
- lineage views
- RAG indexes and LLM Wiki pages
- presentation and report files

Derived views must be rebuildable from canonical sources.

## 5. Authority boundaries

### Safe, reversible actions

Agents may perform these within an approved task packet:

- inspect files and database objects
- create derived tables and views
- write bounded code and SQL
- run non-destructive tests
- generate draft documentation
- produce issue samples and impact maps

### Human approval required

- deleting or replacing source files
- changing default or Stage definitions
- changing validation thresholds to make a test pass
- overwriting validated outputs
- using private credentials or external writes
- publishing final portfolio claims
- making final business interpretations
- material expansion of scope

## 6. Agent roles

- Orchestrator: task graph, dependencies, integration, status
- Hermes: source transport, hashes, raw ingestion, no interpretation
- Data Model: schemas, keys, temporal design, indexes
- SQL QA: data-quality, business-rule, and reconciliation tests
- Risk Signal: economic pathway to measurable feature
- Risk Component: PD/LGD/EAD/Stage/ECL prototypes within data limits
- Validation: independent challenge, leakage, stability, reconciliation
- Documentation: README, data dictionary, test report, handoff
- Reviewer: claim-to-evidence and cross-artifact consistency

Role details are in `agents/`.

## 7. Typed graph

Allowed node types:

- Problem, Decision, Constraint, Shock, Agent, Incentive, Behavior
- Source, Field, Table, Transformation, Query, Feature
- RiskComponent, Scenario, Metric, Test, Result, Artifact
- Run, Version, Issue, Owner, Approval, DecisionRecord, Checkpoint

Allowed edge types:

- `causes`, `amplifies`, `mitigates`, `observed_by`
- `constrained_by`, `computed_from`, `transformed_by`
- `validated_by`, `fails`, `explains`, `supports`
- `reported_in`, `owned_by`, `supersedes`, `requires_approval`

Do not add types casually. Record additions in the decision ledger.

Two graphs remain separate:

1. economic transmission graph: why risk changes
2. data lineage graph: how a number was produced

## 8. Execution loop

Each task follows:

1. Inspect — read relevant files and current state
2. Plan — define objective, files, output, tests, rollback
3. Implement — make the smallest coherent change
4. Test — run unit, SQL, integration, and reconciliation checks
5. Critique — search for leakage, invalid assumptions, and scope drift
6. Reconcile — compare source, database, code, and report outputs
7. Checkpoint — update state, decisions, issues, and next actions

## 9. Quality gates

### Gate 0: Governance

Must exist before implementation:

- charter
- purpose registry
- role boundaries
- task graph
- quality gates
- current state

### Gate 1: Source integrity

Must pass before core transformation:

- source registered
- hash recorded
- source row/column counts recorded
- raw ingestion reconciled

### Gate 2: Core data integrity

Must pass before risk signals:

- primary-key and foreign-key checks
- wide-to-long row count reconciliation
- amount reconciliation
- date and code-domain checks

### Gate 3: Signal validity

Must pass before model publication:

- definition and economic rationale
- available-at-observation-time check
- leakage review
- observed outcome comparison
- SQL reproducibility

### Gate 4: Model and scenario validity

Must pass before Risk Component conclusions:

- time-aware validation
- calibration and stability
- segment review
- sensitivity direction review
- assumptions and proxy labels

### Gate 5: External artifact consistency

Must pass before README/PPT/self-introduction numbers:

- database, code, Excel, and report values reconcile
- run ID and definition version recorded
- limitations disclosed
- claim-to-evidence map complete

## 10. Stopping rules

Stop a task when:

- requested outputs exist
- required tests ran
- failures are resolved or explicitly logged
- results reconcile within threshold
- reproduction command is documented
- limitations are documented
- reviewer has no Critical issue

Stop and escalate when:

- source integrity cannot be established
- a required definition is ambiguous and materially changes output
- a destructive action is required
- the task would violate current Wave scope
- validated values would need manual alteration

## 11. RAG and LLM policy

RAG and LLM Wiki are support layers, not numerical authorities.

Allowed:

- retrieve approved definitions, tests, decisions, issues, and runbooks
- explain validated results with citations to repository evidence
- draft handoff and report language

Not allowed:

- invent or modify numbers
- execute unrestricted natural-language SQL
- approve model results
- redefine risk classes
- index unvalidated scratch files as truth

## 12. Portfolio rule

A technical feature belongs in the project only if it improves at least one of:

- reliability
- traceability
- speed of recurring work
- explanation of a risk change
- reviewability
- handoff and onboarding

Otherwise defer it.
