# Start Here

## 1. Validate the scaffold

```bash
python scripts/validate_scaffold.py
```

## 2. Start Claude Code

```bash
claude
```

Then run `/context`, `/wave0`, and `/status`.

Non-interactive Wave 0 review can be initiated with:

```bash
claude -p "Read AGENTS.md, HARNESS.md, PROJECT_STATE.md and execute prompts/01_wave0_governance.md. Do not perform Wave 1 work."
```

## 3. Start Codex

```bash
codex
```

Paste `prompts/01_wave0_governance.md`. After Wave 0 is reviewed, use `prompts/02_wave1_data_sql.md`.

## 4. Preserve evidence

After every run, update:

- `PROJECT_STATE.md`
- `docs/governance/work_status.md`
- `docs/governance/decision_ledger.md`
- issue records when a gate fails
