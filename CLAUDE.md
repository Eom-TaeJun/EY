@AGENTS.md

# Claude Code additions

- Use `.claude/rules/` for topic-specific constraints; do not duplicate them here.
- Use `.claude/skills/` for repeatable procedures such as Wave execution, status checks, and reviews.
- Before starting, run `/context` and verify that this file and `AGENTS.md` are loaded.
- Prefer plan mode when changing database schemas, risk definitions, validation thresholds, or cross-directory interfaces.
- Use subagents only when tasks are independent and file ownership is explicit. Never let two agents edit the same file concurrently.
- Summarize each subagent result with changed files, tests, unresolved issues, and merge risks before accepting it.
- Do not use auto-memory as the system of record. Durable project knowledge belongs in versioned repository documents.
- Do not edit `CLAUDE.local.md`; it is reserved for the user's private machine settings.
