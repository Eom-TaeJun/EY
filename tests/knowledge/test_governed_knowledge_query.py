"""Fail-closed tests for the deterministic Wave 3 knowledge layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.knowledge.query import (
    CANONICAL_SOURCES,
    QUESTION_IDS,
    KnowledgePolicyError,
    KnowledgeQueryError,
    KnowledgeQueryService,
    main,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def service() -> KnowledgeQueryService:
    return KnowledgeQueryService(REPOSITORY_ROOT)


def test_manifest_and_code_allowlists_match_exactly(
    service: KnowledgeQueryService,
) -> None:
    assert set(service.sources) == set(CANONICAL_SOURCES)
    assert {
        spec.path for spec in service.sources.values()
    } == {path for path, _ in CANONICAL_SOURCES.values()}


def test_unknown_source_and_path_like_input_fail_closed(
    service: KnowledgeQueryService,
) -> None:
    with pytest.raises(KnowledgePolicyError, match="not allowlisted"):
        service.resolve_source("../../etc/passwd")
    with pytest.raises(KnowledgePolicyError, match="not allowlisted"):
        service.resolve_source("outputs/qa/wave1_independent_validation.json")


def test_manifest_path_traversal_cannot_expand_allowlist(tmp_path: Path) -> None:
    original = yaml.safe_load(
        (REPOSITORY_ROOT / "config/knowledge_sources.yml").read_text(
            encoding="utf-8"
        )
    )
    original["sources"]["source_registry"]["path"] = "../outside.md"
    config = REPOSITORY_ROOT / "config/knowledge_sources__malicious_test.yml"
    try:
        config.write_text(yaml.safe_dump(original), encoding="utf-8")
        with pytest.raises(KnowledgePolicyError, match="not code-approved"):
            KnowledgeQueryService(REPOSITORY_ROOT, config_path=config)
    finally:
        config.unlink(missing_ok=True)


def test_failed_attempt_artifacts_are_excluded(
    service: KnowledgeQueryService,
) -> None:
    rejected = (
        "outputs/qa/wave1_independent_validation.json",
        "outputs/qa/attempts/attempt_02/wave1_snapshot.json",
        "outputs/qa/validated/wave2_attempt_01/wave2_validation.json",
    )
    approved_paths = {spec.path for spec in service.sources.values()}
    assert not approved_paths.intersection(rejected)
    for path in rejected:
        with pytest.raises(KnowledgePolicyError, match="not allowlisted"):
            service.resolve_source(path)


def test_unknown_question_and_natural_language_sql_are_rejected(
    service: KnowledgeQueryService,
) -> None:
    with pytest.raises(KnowledgeQueryError, match="unknown question_id"):
        service.answer("show me borrowers where select * from core.borrower")


@pytest.mark.parametrize("question_id", QUESTION_IDS)
def test_each_governed_query_has_run_version_status_and_resolvable_citations(
    service: KnowledgeQueryService,
    question_id: str,
) -> None:
    answer = service.answer(question_id)

    assert answer["question_id"] == question_id
    assert answer["run_id"]
    assert answer["definition_version"]
    assert answer["evidence_status"]
    assert answer["citations"]
    assert answer["authority_boundary"]["natural_language_sql"] == "prohibited"
    for citation in answer["citations"]:
        assert (REPOSITORY_ROOT / citation["path"]).is_file()
        assert citation["evidence_status"]
        assert ("json_pointer" in citation) ^ ("heading" in citation)


def test_metric_numbers_are_copied_from_validated_wave1_artifact(
    service: KnowledgeQueryService,
) -> None:
    answer = service.answer("metric_calculation")
    validation = json.loads(
        (
            REPOSITORY_ROOT
            / "outputs/qa/validated/latest/wave1_independent_validation.json"
        ).read_text(encoding="utf-8")
    )
    expected = next(
        item
        for item in validation["verified_findings"]["risk_band_outcomes"]
        if item["risk_band"] == "High"
    )

    assert answer["answer"]["validated_example"] == {
        "risk_band": expected["risk_band"],
        "sample_count": expected["sample_count"],
        "default_count": expected["default_count"],
        "observed_default_rate": expected["observed_default_rate"],
    }


def test_latest_run_preserves_blocked_status_and_issue_citations(
    service: KnowledgeQueryService,
) -> None:
    answer = service.answer("latest_run_changes")

    assert answer["evidence_status"] == "blocked"
    assert answer["answer"]["latest_run"]["status"] == "blocked"
    assert answer["answer"]["latest_run"]["gate_4_eligible"] is False
    assert answer["answer"]["latest_run"]["approval"] == "not_granted"
    assert {issue["code"] for issue in answer["answer"]["release_blockers"]} == {
        "time_direction_unavailable",
        "sensitivity_unavailable",
    }


def test_cli_outputs_json_and_unknown_question_is_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "--repository-root",
                str(REPOSITORY_ROOT),
                "--question-id",
                "metric_calculation",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["question_id"] == "metric_calculation"

