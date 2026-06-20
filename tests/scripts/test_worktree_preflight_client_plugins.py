"""Tests for per-worktree AI-client plugin registration in worktree_preflight.

Covers the Claude Code project-scoped plugin registry repair: a fresh worktree
inherits the committed ``.claude/settings.json`` ``enabledPlugins`` but not the
per-``projectPath`` install records, so preflight clones an existing install
record (pointing at the shared plugin cache) under the new worktree's path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import worktree_preflight  # noqa: E402


def _install_record(scope: str, project_path: str | None, install_path: str) -> dict:
    entry = {
        "scope": scope,
        "installPath": install_path,
        "version": "5.1.0",
        "installedAt": "2026-01-01T00:00:00.000Z",
        "lastUpdated": "2026-01-01T00:00:00.000Z",
        "gitCommitSha": "deadbeef",
    }
    if project_path is not None:
        entry["projectPath"] = project_path
    return entry


def _make_cache(tmp_path: Path) -> str:
    cache = tmp_path / "cache" / "claude-plugins-official" / "superpowers" / "5.1.0"
    cache.mkdir(parents=True, exist_ok=True)
    return str(cache)


# --------------------------------------------------------------------------- #
# Pure planner
# --------------------------------------------------------------------------- #


def test_plan_registers_missing_project_scope_entry(tmp_path: Path):
    wt = tmp_path / "augur-wt-new"
    wt.mkdir()
    cache = _make_cache(tmp_path)
    installed = {
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [
                _install_record("project", str(tmp_path / "augur-wt-old"), cache),
            ],
        },
    }

    updated, registered, missing = worktree_preflight._plan_claude_worktree_plugins(
        wt, {"superpowers@claude-plugins-official": True}, installed
    )

    assert registered == ["superpowers@claude-plugins-official"]
    assert missing == []
    entries = updated["plugins"]["superpowers@claude-plugins-official"]
    assert len(entries) == 2
    new_entry = entries[-1]
    assert new_entry["scope"] == "project"
    assert new_entry["projectPath"] == str(wt.resolve())
    assert new_entry["installPath"] == cache  # cloned shared cache
    assert new_entry["gitCommitSha"] == "deadbeef"
    # Original input is not mutated.
    assert len(installed["plugins"]["superpowers@claude-plugins-official"]) == 1


def test_plan_idempotent_when_entry_exists_for_path(tmp_path: Path):
    wt = tmp_path / "augur-wt-new"
    wt.mkdir()
    cache = _make_cache(tmp_path)
    installed = {
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [
                _install_record("project", str(wt.resolve()), cache),
            ],
        },
    }

    updated, registered, missing = worktree_preflight._plan_claude_worktree_plugins(
        wt, {"superpowers@claude-plugins-official": True}, installed
    )

    assert registered == []
    assert missing == []
    assert len(updated["plugins"]["superpowers@claude-plugins-official"]) == 1


def test_plan_user_scope_covers_all_paths(tmp_path: Path):
    wt = tmp_path / "augur-wt-new"
    wt.mkdir()
    cache = _make_cache(tmp_path)
    installed = {
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [
                _install_record("user", None, cache),
            ],
        },
    }

    _, registered, missing = worktree_preflight._plan_claude_worktree_plugins(
        wt, {"superpowers@claude-plugins-official": True}, installed
    )

    assert registered == []
    assert missing == []


def test_plan_missing_cache_when_install_path_absent(tmp_path: Path):
    wt = tmp_path / "augur-wt-new"
    wt.mkdir()
    installed = {
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [
                _install_record("project", str(tmp_path / "old"), str(tmp_path / "gone")),
            ],
        },
    }

    updated, registered, missing = worktree_preflight._plan_claude_worktree_plugins(
        wt, {"superpowers@claude-plugins-official": True}, installed
    )

    assert registered == []
    assert missing == ["superpowers@claude-plugins-official"]
    # No new entry appended when there is no cache to clone.
    assert len(updated["plugins"]["superpowers@claude-plugins-official"]) == 1


def test_plan_missing_cache_when_never_installed(tmp_path: Path):
    wt = tmp_path / "augur-wt-new"
    wt.mkdir()
    installed = {"version": 2, "plugins": {}}

    _, registered, missing = worktree_preflight._plan_claude_worktree_plugins(
        wt, {"episodic-memory@superpowers-marketplace": True}, installed
    )

    assert registered == []
    assert missing == ["episodic-memory@superpowers-marketplace"]


def test_plan_disabled_plugin_ignored(tmp_path: Path):
    wt = tmp_path / "augur-wt-new"
    wt.mkdir()
    cache = _make_cache(tmp_path)
    installed = {
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [
                _install_record("project", str(tmp_path / "old"), cache),
            ],
        },
    }

    _, registered, missing = worktree_preflight._plan_claude_worktree_plugins(
        wt, {"superpowers@claude-plugins-official": False}, installed
    )

    assert registered == []
    assert missing == []


# --------------------------------------------------------------------------- #
# Orchestrator (I/O against a CLAUDE_CONFIG_DIR-scoped registry)
# --------------------------------------------------------------------------- #


def _setup_orchestrator(tmp_path, monkeypatch, *, enabled, installed):
    config_dir = tmp_path / "claude-config"
    (config_dir / "plugins").mkdir(parents=True)
    registry = config_dir / "plugins" / "installed_plugins.json"
    if installed is not None:
        registry.write_text(json.dumps(installed, indent=2), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

    wt = tmp_path / "augur-wt-new"
    (wt / ".claude").mkdir(parents=True)
    (wt / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": enabled}, indent=2), encoding="utf-8")
    return wt, registry


def test_ensure_writes_registry_and_records_repair(tmp_path: Path, monkeypatch):
    cache = _make_cache(tmp_path)
    installed = {
        "version": 2,
        "plugins": {"superpowers@claude-plugins-official": [_install_record("project", str(tmp_path / "old"), cache)]},
    }
    wt, registry = _setup_orchestrator(
        tmp_path,
        monkeypatch,
        enabled={"superpowers@claude-plugins-official": True},
        installed=installed,
    )

    repairs: list = []
    incidents: list = []
    ok, details = worktree_preflight._ensure_client_plugin_registrations(
        wt, repairs, incidents, wt / ".claude" / "settings.json", repair=True
    )

    assert ok is True
    assert any(r.type == "claude-plugin-register" for r in repairs)
    assert incidents == []

    written = json.loads(registry.read_text(encoding="utf-8"))
    entries = written["plugins"]["superpowers@claude-plugins-official"]
    assert any(e["projectPath"] == str(wt.resolve()) for e in entries)
    assert "registered=1" in details


def test_ensure_successful_registration_is_not_an_incident(tmp_path: Path, monkeypatch):
    cache = _make_cache(tmp_path)
    installed = {
        "version": 2,
        "plugins": {"superpowers@claude-plugins-official": [_install_record("project", str(tmp_path / "old"), cache)]},
    }
    wt, _ = _setup_orchestrator(
        tmp_path,
        monkeypatch,
        enabled={"superpowers@claude-plugins-official": True},
        installed=installed,
    )

    repairs: list = []
    incidents: list = []
    ok, details = worktree_preflight._ensure_client_plugin_registrations(
        wt, repairs, incidents, wt / ".claude" / "settings.json", repair=True
    )

    assert ok is True
    assert details == "registered=1"
    assert any(r.type == "claude-plugin-register" for r in repairs)
    assert incidents == []


def test_ensure_dry_run_does_not_write(tmp_path: Path, monkeypatch):
    cache = _make_cache(tmp_path)
    installed = {
        "version": 2,
        "plugins": {"superpowers@claude-plugins-official": [_install_record("project", str(tmp_path / "old"), cache)]},
    }
    wt, registry = _setup_orchestrator(
        tmp_path,
        monkeypatch,
        enabled={"superpowers@claude-plugins-official": True},
        installed=installed,
    )
    before = registry.read_text(encoding="utf-8")

    repairs: list = []
    incidents: list = []
    ok, details = worktree_preflight._ensure_client_plugin_registrations(
        wt, repairs, incidents, wt / ".claude" / "settings.json", repair=False
    )

    assert ok is True
    assert repairs == []
    assert registry.read_text(encoding="utf-8") == before
    assert any(i.fingerprint == "worktree/bootstrap/claude-plugins-unregistered" for i in incidents)
    assert "pending=1" in details


def test_ensure_absent_registry_is_noop(tmp_path: Path, monkeypatch):
    wt, registry = _setup_orchestrator(
        tmp_path,
        monkeypatch,
        enabled={"superpowers@claude-plugins-official": True},
        installed=None,
    )

    repairs: list = []
    incidents: list = []
    ok, details = worktree_preflight._ensure_client_plugin_registrations(
        wt, repairs, incidents, wt / ".claude" / "settings.json", repair=True
    )

    assert ok is True
    assert repairs == []
    assert incidents == []
    assert "absent" in details


def test_ensure_missing_cache_incident_blocks_check_but_not_write(tmp_path: Path, monkeypatch):
    installed = {"version": 2, "plugins": {}}
    wt, registry = _setup_orchestrator(
        tmp_path,
        monkeypatch,
        enabled={"episodic-memory@superpowers-marketplace": True},
        installed=installed,
    )
    before = registry.read_text(encoding="utf-8")

    repairs: list = []
    incidents: list = []
    ok, details = worktree_preflight._ensure_client_plugin_registrations(
        wt, repairs, incidents, wt / ".claude" / "settings.json", repair=True
    )

    assert ok is False
    assert repairs == []
    assert registry.read_text(encoding="utf-8") == before
    missing = [i for i in incidents if i.fingerprint == "worktree/bootstrap/claude-plugin-not-installed"]
    assert len(missing) == 1
    assert missing[0].safe_to_repair is False
    assert "claude plugin install" in missing[0].message


def test_ensure_no_enabled_plugins_is_noop(tmp_path: Path, monkeypatch):
    wt, _ = _setup_orchestrator(tmp_path, monkeypatch, enabled={}, installed={"version": 2, "plugins": {}})

    repairs: list = []
    incidents: list = []
    ok, details = worktree_preflight._ensure_client_plugin_registrations(
        wt, repairs, incidents, wt / ".claude" / "settings.json", repair=True
    )

    assert ok is True
    assert repairs == []
    assert "no client plugins" in details


def test_write_json_atomic_roundtrip(tmp_path: Path):
    target = tmp_path / "registry.json"
    payload = {"version": 2, "plugins": {"x@y": [{"scope": "user"}]}}
    worktree_preflight._write_json_atomic(target, payload)
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert not (tmp_path / "registry.json.augur-tmp").exists()
