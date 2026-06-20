from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from skills.wiki.scripts.mcp import wiki_tools


TIER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_tier.py"
TIER_SPEC = importlib.util.spec_from_file_location("wiki_tier_for_update", TIER_PATH)
assert TIER_SPEC and TIER_SPEC.loader
wiki_tier = importlib.util.module_from_spec(TIER_SPEC)
TIER_SPEC.loader.exec_module(wiki_tier)


def _source(path: str, tier: str, weight: float) -> dict[str, object]:
    return {"source_path": path, "path": path, "tier": tier, "weight": weight}


def test_tier_filter_default_drops_noise_only() -> None:
    sources = [
        {"tier": "critical", "source_surface": "save_events"},
        {"tier": "high", "source_surface": "vault"},
        {"tier": "noise", "source_surface": "logs"},
    ]

    kept = [source for source in sources if wiki_tier.tier_meets_filter(str(source["tier"]), "")]

    assert [source["source_surface"] for source in kept] == ["save_events", "vault"]


def test_tier_caps_keep_top_k_per_tier() -> None:
    caps_path = Path(__file__).resolve().parents[2] / "scripts" / "wiki_tier_caps.py"
    spec = importlib.util.spec_from_file_location("wiki_tier_caps_under_test", caps_path)
    assert spec and spec.loader
    caps_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(caps_mod)
    sources = (
        [_source(f"/c{i}", "critical", 3.0) for i in range(10)]
        + [_source(f"/h{i}", "high", 2.0) for i in range(20)]
        + [_source(f"/m{i}", "medium", 1.0) for i in range(40)]
    )

    capped = caps_mod.apply_tier_caps(sources, {"critical": 5, "high": 15, "medium": 30, "low": 50})

    by_tier: dict[str, int] = {}
    for source in capped:
        tier = str(source["tier"])
        by_tier[tier] = by_tier.get(tier, 0) + 1
    assert by_tier == {"critical": 5, "high": 15, "medium": 30}


def test_skip_if_unchanged_uses_source_mtime(tmp_path: Path) -> None:
    guard_path = Path(__file__).resolve().parents[2] / "scripts" / "wiki_extraction_guard.py"
    spec = importlib.util.spec_from_file_location("wiki_extraction_guard_under_test", guard_path)
    assert spec and spec.loader
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    last_ts_path = tmp_path / "last-extraction.ts"
    last_ts_path.write_text("2000000000.0", encoding="utf-8")
    source_file = tmp_path / "vault.md"
    source_file.write_text("hi", encoding="utf-8")
    os.utime(source_file, (1000000000.0, 1000000000.0))

    assert guard.should_skip([{"source_path": str(source_file)}], last_ts_path) is True

    os.utime(source_file, (2000000001.0, 2000000001.0))
    assert guard.should_skip([{"source_path": str(source_file)}], last_ts_path) is False
    assert guard.should_skip([{"source_path": "episodic://abc"}], last_ts_path) is False


def test_no_change_guard_does_not_hide_pending_batch(tmp_path: Path) -> None:
    last_ts_path = tmp_path / "last-extraction.ts"
    last_ts_path.write_text("2000000000.0", encoding="utf-8")
    source_file = tmp_path / "vault.md"
    source_file.write_text("hi", encoding="utf-8")
    os.utime(source_file, (1000000000.0, 1000000000.0))
    source = {"source_path": str(source_file)}

    assert (
        wiki_tools._should_report_no_change(
            sources=[source],
            pending_sources=[source],
            last_ts_path=last_ts_path,
        )
        is False
    )
    assert (
        wiki_tools._should_report_no_change(
            sources=[source],
            pending_sources=[],
            last_ts_path=last_ts_path,
        )
        is True
    )
