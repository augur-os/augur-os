from __future__ import annotations

import importlib
from pathlib import Path


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / "feature"
    gitdir = main_root / ".git" / "worktrees" / "feature"
    gitdir.mkdir(parents=True)
    main_root.mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    return main_root, worktree_root


def _write_codex_manifest(root: Path) -> None:
    manifest_path = root / "config" / "system" / "mcp_servers.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        """\
project_tier:
  - id: augur-core
    command: python
    args: [-m, augur_core]
    startup_timeout_sec: 90
    cwd_required: true
    env:
      PYTHONPATH: "${AUGUR_ROOT}/project-brain/capabilities:${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"
    per_client_args:
      codex: ["--client-id", "codex"]
vault_tier: []
monolith_exclusions: []
""",
        encoding="utf-8",
    )


def test_sync_templates_global_mcp_project_root_returns_authority(tmp_path: Path) -> None:
    main_root, worktree_root = _linked_worktree(tmp_path)
    templates = importlib.import_module("skills.ai.scripts.sync_agents.templates")

    assert templates.global_mcp_project_root(worktree_root) == main_root.resolve()


def test_codex_adapter_global_config_uses_authority_root(tmp_path: Path, monkeypatch) -> None:
    main_root, worktree_root = _linked_worktree(tmp_path)
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.delenv("AUGUR_SYNC_REPO_LOCAL_ONLY", raising=False)

    codex = importlib.import_module("skills.ai.scripts.sync_agents.adapters.codex")
    monkeypatch.setattr(codex, "PROJECT_ROOT", worktree_root)
    monkeypatch.setattr(codex, "CODEX_HOME", codex_home)
    monkeypatch.setattr(codex.CodexAdapter, "_sync_local_codex_config", lambda self: None)
    monkeypatch.setattr(codex.CodexAdapter, "_sync_routine_automations", lambda self: None)
    monkeypatch.setattr(codex.CodexAdapter, "_sync_dev_loop_automations", lambda self: None)
    monkeypatch.setattr(codex.CodexAdapter, "_sync_dream_automations", lambda self: None)
    monkeypatch.setattr(
        codex,
        "_build_codex_mcp_servers",
        lambda existing_server_ids=None, **kwargs: {
            "augur-core": {
                "command": (main_root / "scripts" / "augur-codex-mcp").as_posix(),
                "args": ["-m", "augur_core", "--client-id", "codex"],
            }
        },
    )

    codex.CodexAdapter().generate_mcp_config()

    written = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert main_root.resolve().as_posix() in written
    assert worktree_root.resolve().as_posix() not in written


def test_codex_runtime_check_from_worktree_uses_authority_root(tmp_path: Path) -> None:
    from src.cli_config.codex_runtime import codex_runtime_config_issues

    main_root, worktree_root = _linked_worktree(tmp_path)
    _write_codex_manifest(main_root)
    _write_codex_manifest(worktree_root)
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        f"""\
[marketplaces.augur-local]
source = "{main_root.resolve()}"
source_type = "local"

[mcp_servers.augur-core]
args = ["-m", "augur_core", "--client-id", "codex"]
command = "{main_root.resolve() / "scripts" / "augur-codex-mcp"}"
startup_timeout_sec = 90

[plugins."augur@augur-local"]
enabled = true
""",
        encoding="utf-8",
    )

    assert (
        codex_runtime_config_issues(
            project_root=worktree_root,
            codex_home=codex_home,
        )
        == []
    )


def test_codex_repo_local_only_skips_global_write_but_keeps_local_sync(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _main_root, worktree_root = _linked_worktree(tmp_path)
    codex_home = tmp_path / "codex-home"
    local_calls: list[Path] = []
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("AUGUR_SYNC_REPO_LOCAL_ONLY", "1")

    codex = importlib.import_module("skills.ai.scripts.sync_agents.adapters.codex")
    monkeypatch.setattr(codex, "PROJECT_ROOT", worktree_root)
    monkeypatch.setattr(codex, "CODEX_HOME", codex_home)
    monkeypatch.setattr(
        codex.CodexAdapter,
        "_sync_local_codex_config",
        lambda self: local_calls.append(codex.PROJECT_ROOT),
    )

    codex.CodexAdapter().generate_mcp_config()

    assert local_calls == [worktree_root]
    assert not (codex_home / "config.toml").exists()
