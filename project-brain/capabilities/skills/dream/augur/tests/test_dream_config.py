"""Tests for dream-config (ADR-744 task 8)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dream_config.py"
_SPEC = importlib.util.spec_from_file_location("dream_config", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_dream_config_reads_default_skill_local_yaml():
    """Reading with no override returns the skill's own config.yaml."""
    cfg = mod.dream_config()
    assert "phases" in cfg
    assert "order" in cfg["phases"]
    assert "cache_gc" in cfg


def test_dream_config_phase_order_is_a_list_with_known_phases():
    cfg = mod.dream_config()
    order = cfg["phases"]["order"]
    assert isinstance(order, list)
    for phase in ("orphans", "dead-citations", "cache-gc", "stale-pages", "merge-candidates"):
        assert phase in order


def test_dream_config_explicit_path_overrides_default(tmp_path: Path):
    """Pass an explicit config path to test against fixture data."""
    custom = tmp_path / "alt-config.yaml"
    custom.write_text(
        "phases:\n  order: [orphans]\n  skips: [tier-recompute]\n"
        "cache_gc:\n  retention_days: 7\n  paths: [graph]\n"
        "stale_pages:\n  gap_days: 30\n"
        "orphans:\n  max_timeline_entries: 5\n"
        "report:\n  output_dir: alt/reports\n",
        encoding="utf-8",
    )
    cfg = mod.dream_config(config_path=custom)
    assert cfg["phases"]["order"] == ["orphans"]
    assert cfg["phases"]["skips"] == ["tier-recompute"]
    assert cfg["cache_gc"]["retention_days"] == 7
