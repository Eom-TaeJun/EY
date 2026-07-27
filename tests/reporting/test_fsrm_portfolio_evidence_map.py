"""Protect the recruiter-facing SVG from drifting away from validated evidence."""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[2]
SVG_PATH = ROOT / "docs/assets/fsrm_portfolio_evidence_map.svg"
WAVE1_VALIDATION_PATH = (
    ROOT / "outputs/qa/validated/latest/wave1_independent_validation.json"
)
GATE5_PATH = ROOT / "outputs/qa/validated/latest/gate_5.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _percent(value: str) -> str:
    rounded = (Decimal(value) * 100).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return f"{rounded}%"


def test_portfolio_svg_uses_validated_run_and_values() -> None:
    validation = _load_json(WAVE1_VALIDATION_PATH)
    gate5 = _load_json(GATE5_PATH)
    findings = validation["verified_findings"]
    assert isinstance(findings, dict)

    root = ElementTree.parse(SVG_PATH).getroot()
    rendered_text = " ".join(part.strip() for part in root.itertext() if part.strip())

    run_id = str(validation["run_id"])
    assert run_id == gate5["run_id"]
    assert run_id in rendered_text
    assert f"{int(findings['borrower_rows']):,}" in rendered_text
    assert f"{int(findings['account_month_rows']):,}" in rendered_text

    band_rows = findings["risk_band_outcomes"]
    assert isinstance(band_rows, list)
    rates = {
        str(row["risk_band"]): _percent(str(row["observed_default_rate"]))
        for row in band_rows
    }
    assert f"{rates['Low']} → {rates['High']}" in rendered_text

    checks = gate5["checks"]
    assert isinstance(checks, list)
    cross_artifact = next(
        check for check in checks if check["check_id"] == "cross_artifact_values"
    )
    mismatch_count = cross_artifact["evidence"]["mismatch_count"]
    assert str(mismatch_count) in rendered_text
    assert gate5["status"] == "pass"


def test_portfolio_svg_keeps_ifrs9_boundary_visible() -> None:
    root = ElementTree.parse(SVG_PATH).getroot()
    rendered_text = " ".join(part.strip() for part in root.itertext() if part.strip())

    for term in ("prototype", "Stage", "PD", "LGD", "EAD", "ECL"):
        assert term in rendered_text
    assert "승인 결과가 아님" in rendered_text
