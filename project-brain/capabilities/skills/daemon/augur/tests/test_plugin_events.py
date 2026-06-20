from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_prune_stale_removal_events_when_skill_and_hub_exist(monkeypatch):
    """Removal events are suppressed when current canonical discovery contradicts them."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.mcp._plugin_events")
    events = [
        {
            "type": "skill_removed",
            "bundle": "orchestration",
            "skill": "executor",
            "timestamp": "2026-04-07T23:00:37.058093+00:00",
            "acknowledged": False,
        },
        {
            "type": "bundle_removed",
            "bundle": "orchestration",
            "timestamp": "2026-04-07T23:00:37.071678+00:00",
            "acknowledged": False,
        },
    ]

    monkeypatch.setattr(mod, "invalidate_discovery_cache", lambda: None, raising=False)
    monkeypatch.setattr(
        mod,
        "discover_all_skills",
        lambda *, tiers=None: [
            SimpleNamespace(name="executor", hub="orchestration", path=Path("/tmp/executor")),
        ],
        raising=False,
    )

    pruned = mod._prune_contradictory_events(events)

    assert pruned == []


def test_prune_stale_removal_events_when_skill_exists_without_hub(monkeypatch):
    """ADR-802 removed hub from SkillRecord; pruning must use canonical skill names."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.mcp._plugin_events")
    events = [
        {
            "type": "skill_removed",
            "bundle": "adaptive",
            "skill": "routine-codebase",
            "timestamp": "2026-06-06T21:45:47.344276+00:00",
            "acknowledged": False,
        },
        {
            "type": "bundle_removed",
            "bundle": "adaptive",
            "timestamp": "2026-06-06T21:45:48.733341+00:00",
            "acknowledged": False,
        },
    ]

    monkeypatch.setattr(mod, "invalidate_discovery_cache", lambda: None, raising=False)
    monkeypatch.setattr(
        mod,
        "discover_all_skills",
        lambda *, tiers=None: [
            SimpleNamespace(
                name="routine-codebase",
                hub="",
                source_root="project-brain",
                path=Path("/tmp/routine-codebase"),
            ),
        ],
        raising=False,
    )

    pruned = mod._prune_contradictory_events(events)

    assert pruned == []


def test_save_events_concurrent_writers_do_not_race(monkeypatch, tmp_path):
    """Concurrent _save_events callers must not collide on a shared .tmp file."""
    import importlib
    import threading

    mod = importlib.import_module("skills.daemon.scripts.mcp._plugin_events")
    target = tmp_path / "plugin_events.json"
    monkeypatch.setattr(mod, "_events_file", lambda: target)

    errors: list[BaseException] = []

    def writer(idx: int) -> None:
        try:
            mod._save_events([{"i": idx}])
        except BaseException as exc:  # noqa: BLE001 — capture for assertion
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent writers raised: {errors!r}"
    assert target.exists()
    # No .tmp leftovers
    leftovers = sorted(p.name for p in tmp_path.iterdir() if ".tmp" in p.name)
    assert leftovers == [], f"unexpected tmp leftovers: {leftovers}"
