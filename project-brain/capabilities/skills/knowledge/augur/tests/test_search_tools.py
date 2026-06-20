"""Tests for ADR-739 search budget helpers and tools."""
from __future__ import annotations

import importlib


def test_search_stats_reports_bm25_freshness_and_budgets() -> None:
    mod = importlib.import_module("skills.knowledge.scripts.mcp.rag_search")

    result = mod.search_stats()

    assert "bm25_index" in result
    assert "budgets" in result
    assert set(result["budgets"]) == {"conservative", "balanced", "tokenmax"}
    assert "cost_label" in result["budgets"]["balanced"]


def test_search_tune_recommends_a_known_budget() -> None:
    mod = importlib.import_module("skills.knowledge.scripts.mcp.rag_search")

    rec = mod.search_tune(
        query="a very long deep multi-part question about retrieval internals"
    )

    assert rec["recommended_budget"] in {"conservative", "balanced", "tokenmax"}
    assert rec["applied"] is False
    assert "tokens" in rec["cost_label"]


def test_manifest_entry_score_matches_hyphenated_deck_names() -> None:
    mod = importlib.import_module("skills.knowledge.scripts.mcp.rag_search")

    score = mod.score_manifest_entry(
        {
            "name": "augur-angel-deck-v20",
            "description": "",
            "hub": "",
            "path": "documents/venture-augur/IntelSubmit/augur-angel-deck-v20.md",
        },
        "augur angel deck v20",
    )

    assert score == 1.0


def test_attach_brain_ids_preserves_explicit_document_metadata(monkeypatch) -> None:
    mod = importlib.import_module("skills.knowledge.scripts.mcp.rag_search")
    annotated = []

    def fake_annotate(record, *args, registry=None):
        annotated.append(record)
        record["attached_brain_ids"] = ["derived"]

    monkeypatch.setattr("src.lib.brain_registry.get_registry", lambda: object())
    monkeypatch.setattr("src.lib.brain_path.annotate_brain_id", fake_annotate)

    records = [
        {
            "metadata": {"attached_brain_ids": ["project-y"]},
            "source_path": "/tmp/project-y.md",
        },
        {
            "attached_brain_ids": ["personal"],
            "source_path": "/tmp/personal.md",
        },
        {
            "metadata": {"attached_brain_ids": []},
            "source_path": "/tmp/unassigned.md",
        },
        {
            "metadata": {},
            "source_path": "/tmp/unknown.md",
        },
    ]

    mod._attach_brain_ids(records)

    assert annotated == [records[3]]
    assert records[0]["metadata"]["attached_brain_ids"] == ["project-y"]
    assert records[1]["attached_brain_ids"] == ["personal"]
    assert records[2]["metadata"]["attached_brain_ids"] == []
    assert "attached_brain_ids" not in records[2]
    assert records[3]["attached_brain_ids"] == ["derived"]
