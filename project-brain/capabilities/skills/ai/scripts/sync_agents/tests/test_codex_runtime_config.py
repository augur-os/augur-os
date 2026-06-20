"""Codex runtime MCP config regression tests."""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))


def _write_split_mcp_manifest(project_root: Path) -> None:
    manifest_path = project_root / "config" / "system" / "mcp_servers.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        textwrap.dedent(
            """\
            project_tier:
              - id: augur-core
                command: python
                args: [-m, augur_core]
                startup_timeout_sec: 90
                cwd_required: true
                env:
                  PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
                  PYTHONUNBUFFERED: "1"
                per_client_args:
                  codex: ["--client-id", "codex"]
              - id: augur-framework
                command: python
                args: [-m, augur_framework]
                cwd_required: true
                env:
                  PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
                  PYTHONUNBUFFERED: "1"
                per_client_args:
                  codex: ["--client-id", "codex"]
            vault_tier: []
            monolith_exclusions: []
            """
        ),
        encoding="utf-8",
    )


def test_codex_runtime_config_issues_report_missing_augur_entries(tmp_path):
    from sync_agents.adapters import codex as codex_adapter

    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_split_mcp_manifest(project_root)

    codex_home = tmp_path / "home" / ".codex"
    codex_home.mkdir(parents=True)
    (codex_home / "config.toml").write_text(
        textwrap.dedent(
            """\
            [mcp_servers.context7]
            command = "bash"
            args = ["-lc", "npx context7"]
            """
        ),
        encoding="utf-8",
    )

    with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
        "sync_agents.adapters.codex.CODEX_HOME", codex_home
    ):
        issues = codex_adapter.codex_runtime_config_issues()

    assert any("missing MCP server augur-core" in issue for issue in issues)
    assert any("missing MCP server augur-framework" in issue for issue in issues)
    assert any("missing marketplace augur-local" in issue for issue in issues)
    assert any("missing plugin augur@augur-local" in issue for issue in issues)


def test_codex_mcp_config_generation_is_idempotent_when_current(tmp_path):
    from sync_agents.adapters import codex as codex_adapter

    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_split_mcp_manifest(project_root)
    codex_home = tmp_path / "home" / ".codex"
    generated: list[Path] = []

    with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
        "sync_agents.adapters.codex.CODEX_HOME", codex_home
    ), patch("sync_agents.adapters.codex.GENERATED_FILES", generated):
        adapter = codex_adapter.CodexAdapter()
        adapter.generate_mcp_config()
        config_path = codex_home / "config.toml"
        first_render = config_path.read_text(encoding="utf-8")
        issues = codex_adapter.codex_runtime_config_issues()

        generated.clear()
        adapter.generate_mcp_config()

    assert issues == []
    assert config_path.read_text(encoding="utf-8") == first_render
    assert config_path not in generated


def test_check_mode_allows_gemini_memory_import_section(tmp_path):
    from sync_agents import modes

    target = tmp_path / ".antigravity" / "ANTIGRAVITY.md"
    expected = "# Rules\n"

    current = "# Rules\n\n## Augur Memories\n\n@./memory/one.md\n"
    assert modes._rules_content_matches_target(target, current, expected)

    stale_current = "# Old Rules\n\n## Augur Memories\n\n@./memory/one.md\n"
    assert not modes._rules_content_matches_target(target, stale_current, expected)
