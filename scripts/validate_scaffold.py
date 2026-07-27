from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "HARNESS.md",
    "PROJECT_STATE.md",
    "docs/INDEX.md",
    "docs/charter/project_charter.md",
    "docs/governance/quality_gates.md",
    "docs/data/data_dictionary.md",
    "docs/methodology/signal_dictionary.md",
    "docs/validation/test_catalog.md",
    "docs/wiki/runbook.md",
    "docs/final/evidence_map.md",
    "agents/hermes.md",
    "prompts/02_wave1_data_sql.md",
    ".claude/skills/wave0/SKILL.md",
    ".claude/skills/wave1/SKILL.md",
]


def check_required() -> list[str]:
    return [p for p in REQUIRED if not (ROOT / p).exists()]


def check_markdown_links() -> list[str]:
    broken: list[str] = []
    pattern = re.compile(r"\[[^\]]+\]\((?!https?://|#|mailto:)([^)]+)\)")
    for file in ROOT.rglob("*.md"):
        text = file.read_text(encoding="utf-8")
        for target in pattern.findall(text):
            clean = target.split("#", 1)[0]
            if not clean:
                continue
            path = (file.parent / clean).resolve()
            if not path.exists():
                broken.append(f"{file.relative_to(ROOT)} -> {target}")
    return broken


def main() -> int:
    missing = check_required()
    broken = check_markdown_links()
    if missing:
        print("Missing required paths:")
        for item in missing:
            print(f"  - {item}")
    if broken:
        print("Broken local markdown links:")
        for item in broken:
            print(f"  - {item}")
    if missing or broken:
        return 1
    print(f"Scaffold validation passed: {ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
