# Repository Bootstrap Prompt

You are creating an agent-ready repository for a credit-risk SQL and validation portfolio.

## Objective

Create the directory structure and baseline files specified by the supplied scaffold, while keeping root agent instructions concise and moving detailed procedures into versioned documents and task skills.

## Required top-level files

- README.md
- AGENTS.md
- CLAUDE.md importing AGENTS.md
- HARNESS.md
- PROJECT_STATE.md
- configuration and environment templates

## Required documentation groups

- charter
- governance
- data
- methodology
- validation
- wiki/handoff
- final portfolio evidence
- bounded agent contracts
- Wave prompts

## Rules

- Do not implement analysis or download data.
- Do not invent completed results.
- Preserve the full Wave 0–4 architecture while setting Wave 0→1 as current.
- Include Claude rules and skills in `.claude/`.
- Include a validation script that checks required paths and internal markdown links.
- End by listing created files, validation evidence, unresolved decisions, and the first Wave 0 task.
