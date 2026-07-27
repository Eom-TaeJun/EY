from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from openpyxl import load_workbook

from src.validation.gate_evidence import GateEvidenceValidator
from src.validation.wave1_office_validation import (
    _write_new_json,
    validate_office_pack,
)


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "W1-20260727-001"
MANIFEST_REL = Path(f"outputs/final/wave1_office_manifest__{RUN_ID}.json")
VALIDATION_REL = Path("outputs/qa/validated/latest/wave1_independent_validation.json")
CLAIMS_REL = Path(f"outputs/final/wave1_claim_manifest__{RUN_ID}.json")
EVIDENCE_MAP_REL = Path("docs/final/evidence_map.md")
OFFICE_FILES = (
    Path(f"outputs/final/wave1_office_pack__{RUN_ID}.xlsx"),
    Path(f"outputs/final/wave1_office_pack__{RUN_ID}.pptx"),
    Path(f"outputs/final/wave1_office_pack__{RUN_ID}.docx"),
)


def _copy_pack(tmp_path: Path) -> dict[str, Path]:
    paths = [MANIFEST_REL, VALIDATION_REL, CLAIMS_REL, EVIDENCE_MAP_REL, *OFFICE_FILES]
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    return {
        "manifest": tmp_path / MANIFEST_REL,
        "validation": tmp_path / VALIDATION_REL,
        "claims": tmp_path / CLAIMS_REL,
        "evidence_map": tmp_path / EVIDENCE_MAP_REL,
        "xlsx": tmp_path / OFFICE_FILES[0],
    }


def _validate(paths: dict[str, Path], root: Path):
    return validate_office_pack(
        paths["manifest"],
        paths["validation"],
        paths["claims"],
        paths["evidence_map"],
        artifact_root=root,
        generated_at="2026-07-27T14:00:00+00:00",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_office_pack_passes_independent_gate5_contract(tmp_path: Path) -> None:
    paths = _copy_pack(tmp_path)

    report = _validate(paths, tmp_path)

    assert report.status == "pass"
    assert report.mismatch_count == 0
    assert report.unresolved_claim_count == 0
    assert report.gate_packet is not None
    contract = GateEvidenceValidator(artifact_root=tmp_path).validate(
        report.gate_packet,
        expected_gate=5,
        expected_run_id=RUN_ID,
    )
    assert contract.valid
    assert report.visual_render["status"] == "not_run"
    assert report.visual_render["structural_qa"] == "completed"


def test_tampered_xlsx_value_fails_even_when_manifest_hash_is_updated(
    tmp_path: Path,
) -> None:
    paths = _copy_pack(tmp_path)
    workbook = load_workbook(paths["xlsx"])
    workbook["Signal_Buckets"]["C2"] = (
        int(workbook["Signal_Buckets"]["C2"].value) + 1
    )
    workbook.save(paths["xlsx"])
    workbook.close()
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    excel = next(
        row for row in manifest["artifacts"] if row["artifact_type"] == "excel"
    )
    excel["sha256"] = _sha256(paths["xlsx"])
    excel["bytes"] = paths["xlsx"].stat().st_size
    paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")

    report = _validate(paths, tmp_path)

    assert report.status == "fail"
    assert report.gate_packet is None
    assert any(issue.code == "xlsx_signal_values" for issue in report.issues)


def test_mixed_run_manifest_fails_closed(tmp_path: Path) -> None:
    paths = _copy_pack(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    manifest["run_id"] = "W1-OTHER-RUN"
    paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")

    report = _validate(paths, tmp_path)

    assert report.status == "fail"
    assert report.gate_packet is None
    assert any(issue.code == "manifest_identity_mismatch" for issue in report.issues)


def test_missing_evidence_map_claim_blocks_gate5(tmp_path: Path) -> None:
    paths = _copy_pack(tmp_path)
    text = paths["evidence_map"].read_text(encoding="utf-8")
    text = "\n".join(
        line for line in text.splitlines() if not line.startswith("| W1-CLM-006 |")
    )
    paths["evidence_map"].write_text(text, encoding="utf-8")

    report = _validate(paths, tmp_path)

    assert report.status == "fail"
    assert report.unresolved_claim_count == 1
    assert report.gate_packet is None


def test_office_validation_report_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "office-validation.json"
    _write_new_json(output, {"status": "pass"})

    with pytest.raises(FileExistsError):
        _write_new_json(output, {"status": "tampered"})

    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "pass"}
