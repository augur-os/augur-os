"""Auto-generated importability test for plugin_watcher."""
from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_plugin_watcher_importable():
    """Verify that plugin_watcher can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.daemon.scripts.plugin_watcher")
    assert mod is not None


def test_scan_skills_uses_canonical_root_skill_discovery(
    monkeypatch,
    tmp_path: Path,
):
    """Watcher scans managed project-brain skills using canonical discovery."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.plugin_watcher")
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "search"
    save_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "save"
    skill_dir.mkdir(parents=True)
    save_dir.mkdir(parents=True)

    monkeypatch.setattr(mod, "invalidate_discovery_cache", lambda: None, raising=False)
    monkeypatch.setattr(
        mod,
        "discover_all_skills",
        lambda *, tiers=None: [
            SimpleNamespace(hub="brain", name="search", path=skill_dir),
            SimpleNamespace(hub="command", name="save", path=save_dir),
        ],
        raising=False,
    )

    scanned = mod._scan_skills()

    assert set(scanned) == {"brain/search", "command/save"}
    assert scanned["brain/search"] == skill_dir.stat().st_mtime


def test_scan_skills_uses_source_root_when_hub_was_retired(
    monkeypatch,
    tmp_path: Path,
):
    """ADR-802 leaves SkillRecord.hub blank; watcher keys by source scope instead."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.plugin_watcher")
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "routine-codebase"
    skill_dir.mkdir(parents=True)

    monkeypatch.setattr(mod, "invalidate_discovery_cache", lambda: None, raising=False)
    monkeypatch.setattr(
        mod,
        "discover_all_skills",
        lambda *, tiers=None: [
            SimpleNamespace(
                hub="",
                name="routine-codebase",
                source_root="project-brain",
                path=skill_dir,
            ),
        ],
        raising=False,
    )

    scanned = mod._scan_skills()

    assert scanned == {"project-brain/routine-codebase": skill_dir.stat().st_mtime}


def test_scan_skills_ignores_stale_repo_root_skill_records(
    monkeypatch,
    tmp_path: Path,
):
    """Watcher does not emit events from retired repo-root skills."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.plugin_watcher")
    stale_skill_dir = tmp_path / "skills" / "search"
    shared_skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "search"
    stale_skill_dir.mkdir(parents=True)
    shared_skill_dir.mkdir(parents=True)

    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(mod, "invalidate_discovery_cache", lambda: None, raising=False)
    monkeypatch.setattr(
        mod,
        "discover_all_skills",
        lambda *, tiers=None: [
            SimpleNamespace(hub="brain", name="search", path=shared_skill_dir),
            SimpleNamespace(hub="brain", name="search", path=stale_skill_dir),
        ],
        raising=False,
    )

    scanned = mod._scan_skills()

    assert scanned == {"brain/search": shared_skill_dir.stat().st_mtime}


def test_run_once_treats_empty_existing_snapshot_as_baseline(
    monkeypatch,
    tmp_path: Path,
):
    """A stale empty snapshot from the hub-teardown bug must not toast every skill."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.plugin_watcher")
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "routine-codebase"
    skill_dir.mkdir(parents=True)
    snapshot = tmp_path / "plugin_watcher_snapshot.json"
    events = tmp_path / "plugin_events.json"
    snapshot.write_text('{"skills": {}, "bundles": {}}', encoding="utf-8")

    monkeypatch.setattr(mod, "SNAPSHOT_FILE", snapshot, raising=False)
    monkeypatch.setattr(mod, "EVENTS_FILE", events, raising=False)
    monkeypatch.setattr(mod, "invalidate_discovery_cache", lambda: None, raising=False)
    monkeypatch.setattr(
        mod,
        "discover_all_skills",
        lambda *, tiers=None: [
            SimpleNamespace(
                hub="",
                name="routine-codebase",
                source_root="project-brain",
                path=skill_dir,
            ),
        ],
        raising=False,
    )

    mod.run_once()

    assert not events.exists()
    assert "project-brain/routine-codebase" in snapshot.read_text(encoding="utf-8")


def test_mark_skill_new_writes_runtime_ui_state_not_dot_config(
    monkeypatch,
    tmp_path: Path,
):
    """New skills should be tracked in runtime UI state instead of .config."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.plugin_watcher")
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "ingest"
    skill_dir.mkdir(parents=True)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    monkeypatch.setattr(mod, "_resolve_skill_dir", lambda bundle, skill: skill_dir)
    import src.plugins.skill_ui_state as skill_ui_state
    monkeypatch.setattr(skill_ui_state, "get_runtime_dir", lambda: runtime_dir)

    mod._mark_skill_new("brain", "ingest")

    assert not (skill_dir / ".config").exists()
    state_file = runtime_dir / "dashboard" / "skills-state.yaml"
    assert state_file.exists()
    assert "ingest:" in state_file.read_text(encoding="utf-8")
