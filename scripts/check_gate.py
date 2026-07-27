"""Validate a deterministic gate evidence packet without approving the gate.

Owning pipelines write outputs/qa/gate_<n>.json. This command validates the
packet structure, run identity, required checks, and zero failed checks. It
fails closed when evidence is absent, malformed, or incomplete.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CHECKS = {
    1: {"source_registered", "sha256_recorded", "source_shape_recorded", "raw_rows_reconciled"},
    2: {"primary_key", "foreign_key", "wide_to_long_rows", "bill_amounts", "payment_amounts", "code_domains"},
    3: {"signal_count", "definition_version", "observation_timing", "leakage", "outcome_summary", "sql_reproducibility"},
    4: {"time_validation", "calibration", "segment_stability", "sensitivity_direction", "proxy_labels"},
    5: {"shared_run_id", "cross_artifact_values", "limitations", "evidence_map"},
}


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def load_packet(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot read valid gate packet {path}: {exc}")
        return None
    if not isinstance(value, dict):
        print(f"FAIL: gate packet must be a JSON object: {path}")
        return None
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", required=True, type=int, choices=range(1, 6))
    args = parser.parse_args()

    path = ROOT / "outputs" / "qa" / f"gate_{args.gate}.json"
    if not path.exists():
        return fail(f"Gate {args.gate} evidence is missing: {path}")

    packet = load_packet(path)
    if packet is None:
        return 1
    if packet.get("gate") != args.gate:
        return fail(f"packet gate must equal {args.gate}")
    if not isinstance(packet.get("run_id"), str) or not packet["run_id"].strip():
        return fail("run_id is required")
    if packet.get("status") != "pass":
        return fail("status must be 'pass'")

    checks = packet.get("checks")
    if not isinstance(checks, list):
        return fail("checks must be a list")
    by_id = {
        item.get("check_id"): item
        for item in checks
        if isinstance(item, dict) and isinstance(item.get("check_id"), str)
    }
    missing = sorted(REQUIRED_CHECKS[args.gate] - by_id.keys())
    if missing:
        return fail(f"required checks missing: {', '.join(missing)}")
    failed = sorted(
        check_id
        for check_id, item in by_id.items()
        if item.get("status") != "pass" or not item.get("evidence")
    )
    if failed:
        return fail(f"checks failed or lack evidence: {', '.join(failed)}")

    print(f"Gate {args.gate} evidence packet passed structural validation: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
