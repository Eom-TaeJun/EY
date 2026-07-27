"""Static contract checks for the Wave 1 economic-hypothesis graph."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GRAPH_SQL = ROOT / "sql" / "ddl" / "032_wave1_economic_hypotheses.sql"
DB_TEST_SQL = ROOT / "tests" / "graph" / "test_wave1_economic_hypotheses.sql"

APPROVED_NODE_TYPES = {
    "Problem",
    "Decision",
    "Constraint",
    "Shock",
    "Agent",
    "Incentive",
    "Behavior",
    "Source",
    "Field",
    "Table",
    "Transformation",
    "Query",
    "Feature",
    "RiskComponent",
    "Scenario",
    "Metric",
    "Test",
    "Result",
    "Artifact",
    "Run",
    "Version",
    "Issue",
    "Owner",
    "Approval",
    "DecisionRecord",
    "Checkpoint",
}
APPROVED_EDGE_TYPES = {
    "causes",
    "amplifies",
    "mitigates",
    "observed_by",
    "constrained_by",
    "computed_from",
    "transformed_by",
    "validated_by",
    "fails",
    "explains",
    "supports",
    "reported_in",
    "owned_by",
    "supersedes",
    "requires_approval",
}


def _registered_nodes(sql: str) -> list[tuple[str, str, str]]:
    return re.findall(
        r"meta\.register_node\(\s*"
        r"c_scope,\s*"
        r"'([A-Za-z]+)',\s*"
        r"'(economic\.wave1\.[^']+)',\s*"
        r"c_version,\s*"
        r"'([a-z_]+)'",
        sql,
        flags=re.DOTALL,
    )


def _registered_edges(sql: str) -> list[tuple[str, str, str]]:
    return re.findall(
        r"meta\.register_edge\(\s*"
        r"c_scope,\s*"
        r"(v_[a-z0-9_]+),\s*"
        r"(v_[a-z0-9_]+),\s*"
        r"'([a-z_]+)'",
        sql,
        flags=re.DOTALL,
    )


def test_graph_uses_only_approved_types_and_the_economic_scope() -> None:
    sql = GRAPH_SQL.read_text(encoding="utf-8")
    nodes = _registered_nodes(sql)
    edges = _registered_edges(sql)

    assert len(nodes) == 14
    assert len(edges) == 20
    assert {node_type for node_type, _, _ in nodes} <= APPROVED_NODE_TYPES
    assert {edge_type for _, _, edge_type in edges} <= APPROVED_EDGE_TYPES
    assert "c_scope constant text := 'economic_transmission'" in sql
    assert "'data_lineage'" not in sql


def test_mixed_and_contradicted_associations_are_explicit() -> None:
    sql = GRAPH_SQL.read_text(encoding="utf-8")

    assert "'economic.wave1.metric.zero_payment_streak'" in sql
    assert "'mixed_association'" in sql
    assert "'mixed'" in sql
    assert "'economic.wave1.metric.recent_bill_growth'" in sql
    assert "'contradicted_hypothesis'" in sql
    assert "'economic.wave1.metric.payment_coverage_ratio'" in sql
    assert "'negative'" in sql


def test_graph_contains_no_out_of_scope_component_or_macro_nodes() -> None:
    sql = GRAPH_SQL.read_text(encoding="utf-8")
    canonical_names = {
        canonical_name.lower() for _, canonical_name, _ in _registered_nodes(sql)
    }

    assert len(canonical_names) == 14
    prohibited_fragments = {
        "stage",
        "ead",
        "lgd",
        "ecl",
        "unemployment",
        "interest_rate",
        "collateral",
    }
    assert all(
        fragment not in canonical_name
        for canonical_name in canonical_names
        for fragment in prohibited_fragments
    )
    assert DB_TEST_SQL.is_file()
