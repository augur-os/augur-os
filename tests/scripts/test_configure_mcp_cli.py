from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_fixture_manifest(
    monkeypatch,
    tmp_path: Path,
    *,
    bundle_export_to: str = "[]",
) -> None:
    """Pin configure_mcp to a manifest that exports augur-core to home clients.

    ADR-783 made the real ``augur-core``/``augur-framework`` servers project-scoped,
    so they are emitted to the checkout-local ``.mcp.json`` and intentionally
    excluded from home/IDE client configs. These CLI tests assert the home-config
    export behaviour (core kept, vault/bundle servers dropped), so they pin a
    controlled manifest where ``augur-core`` is global-scoped and policy-approved
    rather than depending on the real repo manifest. The real repo is still used
    for the IDE registry and module-existence checks (augur_core lives under
    ``src/mcp``); only the manifest source is swapped.

    ``bundle_export_to`` controls the vault-tier bundle export policy so a test can
    choose whether bundles are dropped by *policy* (default ``"[]"``) or are
    policy-approved and must instead be dropped by the gemini/plugin skip logic
    (e.g. ``"[gemini, mcp-config]"``).
    """
    from scripts import configure_mcp
    from src.cli_config.manifest import load_manifest as _real_load_manifest

    manifest_dir = tmp_path / "fixture-manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "mcp_servers.yaml"
    manifest_path.write_text(
        """
project_tier:
  - id: augur-core
    description: Core discovery server
    scope: global
    command: python
    args: [-m, augur_core]
    startup_timeout_sec: 90
    cwd_required: true
    per_client_args:
      claude: ["--client-id", "claude"]
      codex: ["--client-id", "codex"]
      gemini: ["--client-id", "gemini"]
  - id: augur-framework
    description: Framework operations server
    scope: global
    command: python
    args: [-m, augur_framework]
    cwd_required: true
vault_tier:
  - id: augur-vault
    description: Vault bundle
    scope: global
    command: python
    args: [-m, augur_shared.bundle_server, vault]
    bundle: vault
    bundle_path: /tmp/vault
  - id: augur-ingest
    description: Ingest bundle
    scope: global
    command: python
    args: [-m, augur_shared.bundle_server, ingest]
    bundle: ingest
    bundle_path: /tmp/ingest
monolith_exclusions:
  - vault
  - ingest
""".lstrip(),
        encoding="utf-8",
    )
    (manifest_dir / "capability_exposure.yaml").write_text(
        f"""
version: 1
capabilities:
  mcp-server:augur-core:
    classification_status: approved
    export_to: [mcp-config]
    management: generated
    owner_kind: augur
  mcp-server:augur-framework:
    classification_status: approved
    export_to: []
    management: generated
    owner_kind: augur
  mcp-server:augur-vault:
    classification_status: approved
    export_to: {bundle_export_to}
    management: generated
    owner_kind: augur
  mcp-server:augur-ingest:
    classification_status: approved
    export_to: {bundle_export_to}
    management: generated
    owner_kind: augur
""".lstrip(),
        encoding="utf-8",
    )

    def _load_fixture_manifest(_path=None):
        return _real_load_manifest(manifest_path)

    monkeypatch.setattr(configure_mcp, "load_manifest", _load_fixture_manifest)


def test_global_client_config_from_worktree_uses_main_checkout_root(tmp_path, monkeypatch):
    """Global MCP configs must not be stamped with linked-worktree paths."""
    from scripts import configure_mcp

    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / "linked-worktree"
    gitdir = main_root / ".git" / "worktrees" / "linked-worktree"
    gitdir.mkdir(parents=True)
    main_root.mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    cursor_config = tmp_path / "cursor.mcp.json"

    monkeypatch.setattr(
        configure_mcp,
        "_load_ide_registry",
        lambda _registry_path: {
            "ides": {
                "cursor": {
                    "enabled": True,
                    "display_name": "Cursor IDE",
                    "config_format": "json",
                    "config_structure": "flat",
                    "config_path": {"all": str(cursor_config)},
                    "server_key": "mcpServers",
                    "cli_arg": "--cursor-config",
                }
            }
        },
    )

    def fake_entries(ide_name, python_path, repo_root, existing_server_ids=None):
        del ide_name, python_path, existing_server_ids
        return {
            "augur-core": {
                "command": "python",
                "args": ["-m", "augur_core"],
                "cwd": str(repo_root),
                "env": {"AUGUR_ROOT": str(repo_root)},
            }
        }

    monkeypatch.setattr(
        configure_mcp,
        "_build_augur_server_entries_for_ide",
        fake_entries,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "configure_mcp.py",
            "--repo-root",
            str(worktree_root),
            "--client",
            "cursor",
            "--auto",
            "--no-external",
        ],
    )

    assert configure_mcp.main() == 0
    written = cursor_config.read_text(encoding="utf-8")
    assert main_root.resolve().as_posix() in written
    assert worktree_root.as_posix() not in written


def test_repo_local_client_config_from_worktree_keeps_requested_root(tmp_path, monkeypatch):
    """Repo-local MCP configs intentionally follow the active worktree."""
    from scripts import configure_mcp

    worktree_root = tmp_path / "linked-worktree"
    worktree_root.mkdir()
    vscode_config = worktree_root / ".vscode" / "mcp.json"

    monkeypatch.setattr(
        configure_mcp,
        "_load_ide_registry",
        lambda _registry_path: {
            "ides": {
                "vscode_copilot": {
                    "enabled": True,
                    "display_name": "VS Code Copilot",
                    "config_format": "json",
                    "config_structure": "flat",
                    "config_path": {"all": "{repo_root}/.vscode/mcp.json"},
                    "server_key": "servers",
                    "cli_arg": "--vscode-copilot-config",
                }
            }
        },
    )
    monkeypatch.setattr(
        configure_mcp,
        "_is_linked_worktree",
        lambda repo_root: Path(repo_root).resolve() == worktree_root.resolve(),
        raising=False,
    )
    monkeypatch.setattr(
        configure_mcp,
        "_main_checkout_for_repo",
        lambda _repo_root: PROJECT_ROOT,
        raising=False,
    )

    def fake_entries(ide_name, python_path, repo_root, existing_server_ids=None):
        del ide_name, python_path, existing_server_ids
        return {
            "augur-core": {
                "command": "python",
                "args": ["-m", "augur_core"],
                "cwd": str(repo_root),
                "env": {"AUGUR_ROOT": str(repo_root)},
            }
        }

    monkeypatch.setattr(
        configure_mcp,
        "_build_augur_server_entries_for_ide",
        fake_entries,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "configure_mcp.py",
            "--repo-root",
            str(worktree_root),
            "--client",
            "vscode-copilot",
            "--auto",
            "--no-external",
        ],
    )

    assert configure_mcp.main() == 0
    written = vscode_config.read_text(encoding="utf-8")
    assert worktree_root.as_posix() in written
    assert str(PROJECT_ROOT) not in written


@pytest.mark.usefixtures("monkeypatch")
def test_configure_mcp_check_passes_after_auto_prunes_cursor_config(tmp_path, monkeypatch):
    from scripts import configure_mcp

    _install_fixture_manifest(monkeypatch, tmp_path)
    cursor_config = tmp_path / "cursor.mcp.json"
    cursor_config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "context7": {"command": "context7", "args": []},
                    "augur": {"command": "old-python", "args": ["-m", "augur_mcp"]},
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "configure_mcp.py",
            "--client",
            "cursor",
            "--cursor-config",
            str(cursor_config),
            "--check",
            "--no-external",
        ],
    )
    assert configure_mcp.main() == 1

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "configure_mcp.py",
            "--client",
            "cursor",
            "--cursor-config",
            str(cursor_config),
            "--auto",
            "--no-external",
        ],
    )
    assert configure_mcp.main() == 0
    assert cursor_config.exists()
    config = json.loads(cursor_config.read_text(encoding="utf-8"))
    servers = config["mcpServers"]
    assert "context7" in servers
    assert "augur" not in servers
    assert "augur-core" in servers
    assert "augur-framework" not in servers
    assert "augur_mcp" not in cursor_config.read_text(encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "configure_mcp.py",
            "--client",
            "cursor",
            "--cursor-config",
            str(cursor_config),
            "--check",
            "--no-external",
        ],
    )
    assert configure_mcp.main() == 0


def test_claude_code_skips_bundle_servers_when_plugin_installed(tmp_path, monkeypatch):
    """Claude Code direct MCP config follows policy and does not duplicate bundles.

    The Augur cowork plugin registers its own bundle servers. Direct generated
    config should keep only the policy-approved project server.
    """
    from scripts import configure_mcp

    fake_home = tmp_path / "home"
    plugins_dir = fake_home / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {"augur@augur-cowork": [{"scope": "user"}]}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    # Bundles are policy-approved so the plugin-installed dedup skip is what must
    # drop them (the plugin's own .mcp.json owns the bundle entries).
    _install_fixture_manifest(monkeypatch, tmp_path, bundle_export_to="[claude, mcp-config]")

    claude_config = tmp_path / "claude.json"
    claude_config.write_text(json.dumps({}), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "configure_mcp.py",
            "--client",
            "claude-code",
            "--claude-code-config",
            str(claude_config),
            "--auto",
            "--no-external",
        ],
    )
    assert configure_mcp.main() == 0

    written = json.loads(claude_config.read_text(encoding="utf-8"))
    project_section = next(iter(written["projects"].values()))
    servers = project_section["mcpServers"]
    assert "augur-core" in servers
    for bundle in (
        "augur-framework",
        "augur-apple",
        "augur-lifestyle",
        "augur-file-manager",
        "augur-obsidian",
        "augur-ingest",
        "augur-vault",
    ):
        assert bundle not in servers, f"{bundle} must be skipped — plugin owns it"


def test_claude_code_policy_blocks_bundle_servers_when_plugin_absent(
    tmp_path,
    monkeypatch,
):
    """Plugin absence must not bypass direct MCP export policy."""
    from scripts import configure_mcp

    fake_home = tmp_path / "home"
    (fake_home / ".claude" / "plugins").mkdir(parents=True)
    # No installed_plugins.json — plugin not installed.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    _install_fixture_manifest(monkeypatch, tmp_path)

    claude_config = tmp_path / "claude.json"
    claude_config.write_text(json.dumps({}), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "configure_mcp.py",
            "--client",
            "claude-code",
            "--claude-code-config",
            str(claude_config),
            "--auto",
            "--no-external",
        ],
    )
    assert configure_mcp.main() == 0

    written = json.loads(claude_config.read_text(encoding="utf-8"))
    project_section = next(iter(written["projects"].values()))
    servers = project_section["mcpServers"]
    assert "augur-core" in servers
    for entry in (
        "augur-framework",
        "augur-vault",
        "augur-ingest",
        "augur-apple",
        "augur-lifestyle",
        "augur-file-manager",
    ):
        assert entry not in servers, f"{entry} must stay retired"


def test_gemini_skips_bundle_servers_to_stay_under_function_cap(tmp_path, monkeypatch):
    """Gemini rejects requests with more than 512 function declarations.

    The project-tier Augur servers already expose a broad tool surface, so
    Gemini config generation must not add the vault-tier bundle servers too.
    """
    from scripts import configure_mcp

    # Bundles are policy-approved for Gemini so the function-cap skip in
    # _build_augur_server_entries_for_ide is what must drop them.
    _install_fixture_manifest(monkeypatch, tmp_path, bundle_export_to="[gemini, mcp-config]")
    gemini_config = tmp_path / "settings.json"
    gemini_config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "context7": {"command": "npx", "args": []},
                    "augur-apple": {"command": "old", "args": []},
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "configure_mcp.py",
            "--client",
            "gemini",
            "--gemini-config",
            str(gemini_config),
            "--auto",
            "--no-external",
        ],
    )
    assert configure_mcp.main() == 0

    written = json.loads(gemini_config.read_text(encoding="utf-8"))
    servers = written["mcpServers"]
    assert "context7" in servers
    assert "augur-core" in servers
    for bundle in (
        "augur-framework",
        "augur-apple",
        "augur-lifestyle",
        "augur-file-manager",
        "augur-obsidian",
        "augur-ingest",
        "augur-vault",
    ):
        assert bundle not in servers, f"{bundle} must be skipped for Gemini"
