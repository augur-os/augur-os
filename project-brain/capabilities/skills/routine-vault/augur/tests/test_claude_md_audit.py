"""Tests for auto-claude-md-audit scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "claude_md_audit.py"
_SPEC = importlib.util.spec_from_file_location("claude_md_audit_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def _shared_skills(tmp_path: Path) -> Path:
    return tmp_path / "project-brain" / "capabilities" / "skills"


def test_scan_source_not_found(tmp_path: Path) -> None:
    """scan returns warning when agent-rules.md source is missing."""
    # Patch both the repo source path resolution and the legacy fallback so
    # neither resolves to anything that exists on disk.
    with patch.object(mod, "_resolve_source_rules", return_value=tmp_path / "missing.md"):
        result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert "not found" in result.summary.lower()


def test_get_actual_commands_includes_command_skill_and_contributions(tmp_path: Path) -> None:
    """Command-type skills and x-augur-config contribution commands are real commands."""
    onboard = _shared_skills(tmp_path) / "onboard"
    onboard.mkdir(parents=True)
    _write(
        onboard / "SKILL.md",
        "---\nname: onboard\nx-augur-type: command\nx-augur-hub: command\n---\n",
    )

    ai = _shared_skills(tmp_path) / "ai"
    ai.mkdir(parents=True)
    _write(
        ai / "SKILL.md",
        "---\n"
        "name: ai\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    commands:\n"
        "      - id: ask\n"
        "        type: workflow\n"
        "---\n",
    )

    cmds = mod._get_actual_commands(tmp_path)
    assert "onboard" in cmds
    assert "ask" in cmds


def test_get_actual_commands_includes_subcommand_files(tmp_path: Path) -> None:
    """Subcommands stored as skills/{skill}/commands/{name}.md must be discovered.

    Regression: the audit previously consulted only `discover_commands()` (which
    scans SKILL.md frontmatter), so subcommands like `/dev-build`, `/dev-merge`,
    and `/auto-lint` looked stale and surfaced manual-review issues every run
    despite being real, working commands.
    """
    skill_dir = _shared_skills(tmp_path) / "platform-admin"
    (skill_dir / "commands").mkdir(parents=True)
    _write(skill_dir / "SKILL.md", "---\nname: platform-admin\n---\n")
    _write(skill_dir / "commands" / "dev-build.md", "# dev-build\n")
    _write(skill_dir / "commands" / "dev-merge.md", "# dev-merge\n")

    other = _shared_skills(tmp_path) / "routine-codebase"
    (other / "commands").mkdir(parents=True)
    _write(other / "SKILL.md", "---\nname: routine-codebase\n---\n")
    _write(other / "commands" / "auto-lint.md", "# auto-lint\n")

    cmds = mod._get_actual_commands(tmp_path)
    assert "dev-build" in cmds
    assert "dev-merge" in cmds
    assert "auto-lint" in cmds


def test_scan_does_not_flag_real_subcommand_as_stale(tmp_path: Path) -> None:
    """A subcommand referenced in CLAUDE.md must NOT appear in the stale set."""
    skill_dir = _shared_skills(tmp_path) / "platform-admin"
    (skill_dir / "commands").mkdir(parents=True)
    _write(skill_dir / "SKILL.md", "---\nname: platform-admin\nx-augur-hub: dev\n---\n")
    _write(skill_dir / "commands" / "dev-build.md", "# dev-build\n")

    source = tmp_path / "docs" / "agent-topics" / "agent-rules.md"
    _write(
        source,
        "**Apps**: 1 plugin bundles: dev\n"
        "\n"
        "## Development Commands\n"
        "| Build/rebuild dashboard | `/dev-build` |\n",
    )

    with patch.object(mod, "_is_plugin_installed", return_value=True):
        result = mod.scan(_ctx(tmp_path))
    stale_issues = [i for i in result.issues if i["action"] == mod._ACTION_STALE_COMMANDS]
    assert stale_issues == [], f"unexpected stale: {stale_issues}"


def test_topic_doc_drift_ignores_dashboard_routes(tmp_path: Path) -> None:
    """Dashboard surfaces (`/browse`, `/workspace`) are routes, not commands.

    Regression: the phantom-command detector matched backtick-wrapped URL routes
    like `/browse` and `/workspace` (rule 13 / ADR-802) and reported them as
    phantom slash commands. They live in the dashboard route namespace, not the
    command namespace, so they must never surface as topic-doc drift.
    """
    topic = tmp_path / "docs" / "agent-topics" / "agent-rules.md"
    _write(
        topic,
        "The dashboard has two surfaces: Browse (`/browse`) and "
        "Workspace (`/workspace`), plus `/workspace/*` subpages.\n",
    )

    drift = mod._check_topic_doc_drift(tmp_path, actual_commands=set())
    phantom = [d for d in drift if "phantom commands" in d]
    assert phantom == [], f"dashboard routes flagged as phantom: {phantom}"


def test_topic_doc_drift_flags_phantom_command_not_route(tmp_path: Path) -> None:
    """A genuinely removed command in a topic doc must still surface as drift,
    even when dashboard routes appear in the same doc."""
    topic = tmp_path / "docs" / "agent-topics" / "SKILLS.md"
    _write(
        topic,
        "Routes `/browse` and `/workspace` are fine, but `/deleted-command` "
        "no longer exists.\n",
    )

    drift = mod._check_topic_doc_drift(tmp_path, actual_commands=set())
    phantom = [d for d in drift if "phantom commands" in d]
    assert len(phantom) == 1
    assert "deleted-command" in phantom[0]
    assert "browse" not in phantom[0]
    assert "workspace" not in phantom[0]


def test_scan_still_flags_truly_phantom_command(tmp_path: Path) -> None:
    """A command referenced only in the doc must still surface as stale."""
    skill_dir = _shared_skills(tmp_path) / "platform-admin"
    (skill_dir / "commands").mkdir(parents=True)
    _write(skill_dir / "SKILL.md", "---\nname: platform-admin\nx-augur-hub: dev\n---\n")

    source = tmp_path / "docs" / "agent-topics" / "agent-rules.md"
    _write(
        source,
        "**Apps**: 1 plugin bundles: dev\n"
        "\n"
        "## Slash Commands\n"
        "Use `/totally-made-up-command` for things.\n",
    )

    with patch.object(mod, "_is_plugin_installed", return_value=True):
        result = mod.scan(_ctx(tmp_path))
    stale_issues = [i for i in result.issues if i["action"] == mod._ACTION_STALE_COMMANDS]
    assert len(stale_issues) == 1
    assert "totally-made-up-command" in stale_issues[0]["stale"]
