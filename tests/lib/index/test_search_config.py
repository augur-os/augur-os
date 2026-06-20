"""Tests for src/lib/index/search_config.py (ADR-739)."""

from __future__ import annotations

from pathlib import Path

from src.lib.index import search_config


def test_load_real_config_has_budgets() -> None:
    cfg = search_config.load_search_config()

    assert cfg["rrf"]["k"] == 60
    assert set(cfg["search_budgets"]) == {"conservative", "balanced", "tokenmax"}


def test_budget_top_k_resolves_and_falls_back() -> None:
    cfg = search_config.load_search_config()

    assert search_config.budget_top_k(cfg, "conservative") == 5
    assert search_config.budget_top_k(cfg, "tokenmax") == 20
    assert search_config.budget_top_k(cfg, None) == 10
    assert search_config.budget_top_k(cfg, "bogus") == 10


def test_malformed_config_fails_closed(tmp_path: Path, monkeypatch) -> None:
    bad = tmp_path / "search.yaml"
    bad.write_text("rrf: [not a mapping", encoding="utf-8")
    monkeypatch.setattr(search_config, "_config_path", lambda: bad)

    cfg = search_config.load_search_config()

    assert cfg["rrf"]["k"] == 60
    assert cfg["default_budget"] == "balanced"
