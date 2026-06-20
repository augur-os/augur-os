"""Tests for aug discover CLI subcommand and packaging entry point."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CLI_ENV = {
    **os.environ,
    "PYTHONPATH": str(PROJECT_ROOT),
}


def _load_discovery_module():
    """Load discovery module directly, bypassing __init__.py.

    Resolves to the canonical repo package path per the augur_mcp namespace
    dismantle.
    """
    canonical = PROJECT_ROOT / "src" / "mcp" / "augur_framework" / "tools" / "domain" / "discovery.py"
    if not canonical.exists():
        pytest.skip("discovery.py not found")
    spec = importlib.util.spec_from_file_location("src.mcp.augur_framework.tools.domain.discovery", canonical)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except (ModuleNotFoundError, ImportError) as e:
        pytest.skip(f"Cannot load discovery module: {e}")
    return mod


def test_discover_returns_valid_manifest(tmp_path):
    """aug discover should return a well-structured manifest."""
    mod = _load_discovery_module()

    focus_state = {
        "current_page": "/career/jobs",
        "skill": "career",
        "hub": "career",
        "timestamp": "2026-03-06T16:00:00Z",
        "source": "dashboard",
    }
    (tmp_path / "focus_state.json").write_text(json.dumps(focus_state))

    manifest = mod.assemble_manifest(tmp_path, hub=None, tier=None)
    assert manifest["focus"]["hub"] == "career"
    assert "manifest" in manifest
    assert "recommended_tools" in manifest
    assert manifest["manifest"]["name"] == "augur"


def test_discover_with_hub_filter(tmp_path):
    """Explicit hub override should be reflected in the manifest."""
    mod = _load_discovery_module()

    manifest = mod.assemble_manifest(tmp_path, hub="finance", tier="public")
    assert manifest["focus"]["hub"] == "finance"


def test_discover_infers_dashboard_skill_name_focus(tmp_path, monkeypatch):
    """Dashboard focus_state.json uses skill_name/bundle, not the older skill key."""
    mod = _load_discovery_module()

    focus_state = {
        "current_page": "/workspace/memory",
        "skill_name": "knowledge",
        "bundle": "knowledge",
        "session_id": "dashboard-1",
        "timestamp": "2026-05-23T22:10:00Z",
        "source": "dashboard",
    }
    (tmp_path / "focus_state.json").write_text(json.dumps(focus_state))

    monkeypatch.setattr(
        mod,
        "_scan_skills",
        lambda: [{"skill": "knowledge", "hub": "workspace", "tools": [], "tiers": {}}],
    )

    manifest = mod.assemble_manifest(tmp_path, hub=None, tier=None)

    assert manifest["focus"]["hub"] == "workspace"
    assert manifest["focus"]["skill"] == "knowledge"
    assert manifest["focus"]["signals"]["has_focus"] is True
    assert manifest["focus"]["signals"]["focus_skill"] == "knowledge"


def test_discover_empty_cli_session_does_not_report_stale_global_focus(
    tmp_path,
    monkeypatch,
):
    """A new CLI session should not inherit stale dashboard focus summary state."""
    mod = _load_discovery_module()

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "cli-1.json").write_text(
        json.dumps(
            {
                "session_id": "cli-1",
                "source": "cli",
                "hub": None,
                "skill": None,
                "recent_tools": [],
            }
        )
    )
    (tmp_path / "focus_state.json").write_text(
        json.dumps({"hub": "workspace", "skill": "knowledge", "source": "dashboard"})
    )

    monkeypatch.setattr(mod, "_scan_skills", lambda: [])

    manifest = mod.assemble_manifest(tmp_path, hub=None, tier=None, session_id="cli-1")

    assert manifest["focus"]["hub"] is None
    assert manifest["focus"]["skill"] is None
    assert manifest["focus"]["signals"]["has_focus"] is False


def test_discover_manifest_separates_visible_and_managed_skill_counts(
    tmp_path,
    monkeypatch,
):
    """The manifest should not label the tier-0 count as the whole skill surface."""
    mod = _load_discovery_module()

    managed_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "knowledge"
    client_dir = tmp_path / ".codex" / "skills" / "knowledge"
    managed_dir.mkdir(parents=True)
    client_dir.mkdir(parents=True)

    managed = SimpleNamespace(
        name="knowledge",
        path=managed_dir,
        hub="workspace",
        mcp_tools=["memory-search"],
        tier=0,
        source_root="project-brain",
    )
    private = SimpleNamespace(
        name="books",
        path=tmp_path / "vault" / "skills" / "books",
        hub="life",
        mcp_tools=[],
        tier=0,
        source_root="private-vault",
    )
    client = SimpleNamespace(
        name="codex-helper",
        path=client_dir,
        hub="",
        mcp_tools=[],
        tier=2,
        source_root="external-client",
    )

    def fake_discover_all_skills(*, tiers=None, project_root=None):
        if tiers == (0,):
            return [managed, private]
        return [managed, private, client]

    monkeypatch.setattr(mod, "discover_all_skills", fake_discover_all_skills)
    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path)

    manifest = mod.assemble_manifest(tmp_path)

    caps = manifest["manifest"]["capabilities"]
    assert caps["skills"] == 3
    assert caps["managed_skills"] == 2
    assert caps["client_skills"] == 1
    assert manifest["inventory"]["skills_by_source_root"] == {
        "external-client": 1,
        "private-vault": 1,
        "project-brain": 1,
    }


def test_aug_entry_point_installed():
    """aug CLI should be importable as src.cli:main."""
    from src.cli import main

    assert callable(main)


def test_aug_cli_help():
    """aug --help should exit 0 with usage text."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(PROJECT_ROOT),
        env=_CLI_ENV,
    )
    assert result.returncode == 0
    assert "Augur CLI" in result.stdout


def test_aug_discover_outputs_valid_json(tmp_path):
    """discover should produce a valid manifest with expected keys."""
    mod = _load_discovery_module()

    manifest = mod.assemble_manifest(tmp_path, hub=None, tier=None)
    assert "manifest" in manifest
    assert "focus" in manifest
    assert "recommended_tools" in manifest
    # Verify JSON-serializable
    json.loads(json.dumps(manifest, default=str))


def test_aug_discover_commands_lists_slash_commands():
    """`aug discover --commands` must list the canonical slash commands.

    discover.md documents `aug discover --commands` as "List available slash
    commands with descriptions". The CLI previously ignored the flag and returned
    the tool manifest instead; this guards the documented behavior by routing the
    flag to the list-commands surface.
    """
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "discover", "--commands", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(PROJECT_ROOT),
        env=_CLI_ENV,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "slash_commands" in data, f"expected slash-command listing, got keys {list(data)}"
    ids = {command["id"] for group in data["slash_commands"] for command in group.get("commands", [])}
    assert {"ask", "keep", "discover", "routines"} <= ids
