from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_tier.py"
SPEC = importlib.util.spec_from_file_location("wiki_tier_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
wiki_tier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_tier)


def test_tier_for_known_surfaces() -> None:
    assert wiki_tier.tier_for_surface("save_events") == "critical"
    assert wiki_tier.tier_for_surface("ask_outcomes") == "critical"
    assert wiki_tier.tier_for_surface("client_memory") == "critical"
    assert wiki_tier.tier_for_surface("memory_files") == "critical"
    assert wiki_tier.tier_for_surface("episodic") == "critical"
    assert wiki_tier.tier_for_surface("codex_threads") == "critical"
    assert wiki_tier.tier_for_surface("vault") == "high"
    assert wiki_tier.tier_for_surface("gemini") == "high"
    assert wiki_tier.tier_for_surface("copilot") == "high"
    assert wiki_tier.tier_for_surface("external_client") == "high"
    assert wiki_tier.tier_for_surface("documents") == "medium"
    assert wiki_tier.tier_for_surface("skills") == "medium"
    assert wiki_tier.tier_for_surface("repo_docs") == "medium"
    assert wiki_tier.tier_for_surface("project_deltas") == "medium"
    assert wiki_tier.tier_for_surface("adr_targets") == "medium"
    assert wiki_tier.tier_for_surface("git_history") == "low"
    assert wiki_tier.tier_for_surface("runtime_memory") == "low"
    assert wiki_tier.tier_for_surface("logs") == "noise"


def test_unknown_surface_defaults_to_medium() -> None:
    assert wiki_tier.tier_for_surface("new_surface") == "medium"


def test_weight_for_tier() -> None:
    assert wiki_tier.weight_for_tier("critical") == 3.0
    assert wiki_tier.weight_for_tier("high") == 2.0
    assert wiki_tier.weight_for_tier("medium") == 1.0
    assert wiki_tier.weight_for_tier("low") == 0.4
    assert wiki_tier.weight_for_tier("noise") == 0.0
    assert wiki_tier.weight_for_tier("unknown") == 1.0


def test_tier_meets_filter_is_inclusive_and_drops_noise_by_default() -> None:
    assert wiki_tier.tier_meets_filter("critical", "") is True
    assert wiki_tier.tier_meets_filter("low", "") is True
    assert wiki_tier.tier_meets_filter("noise", "") is False
    assert wiki_tier.tier_meets_filter("critical", "medium") is True
    assert wiki_tier.tier_meets_filter("high", "medium") is True
    assert wiki_tier.tier_meets_filter("medium", "medium") is True
    assert wiki_tier.tier_meets_filter("low", "medium") is False
    assert wiki_tier.tier_meets_filter("critical", "critical") is True
    assert wiki_tier.tier_meets_filter("high", "critical") is False
