"""Tests for auto-e2e-actions autoloop."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult, make_test_ctx

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "e2e_actions.py"
_SPEC = importlib.util.spec_from_file_location("e2e_actions_under_test", str(_MODULE_PATH))
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_module_name() -> None:
    assert mod.name == "auto-e2e-actions"


def test_has_difficulty_spec() -> None:
    assert hasattr(mod, "DIFFICULTY_SPEC")
    assert isinstance(mod.DIFFICULTY_SPEC, dict)
    assert 0 in mod.DIFFICULTY_SPEC
    assert 3 in mod.DIFFICULTY_SPEC


def test_scan_returns_scan_result(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path)
    result = mod.scan(ctx)
    assert isinstance(result, ScanResult)


def test_fix_returns_fix_result(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path)
    result = mod.fix(ctx, [])
    assert isinstance(result, FixResult)


from unittest.mock import patch


def _shared_skills(tmp_path: Path) -> Path:
    return tmp_path / "project-brain" / "capabilities" / "skills"


def test_discover_actions_from_skillmd(tmp_path: Path) -> None:
    skill_dir = _shared_skills(tmp_path) / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    actions:\n"
        "    - id: add-item\n"
        "      dispatch: fire\n"
        "      mcp_tool: add-test-item\n"
        "    blocks:\n"
        "    - id: items-table\n"
        "      row_actions:\n"
        "      - id: delete-item\n"
        "        dispatch: fire\n"
        "        mcp_tool: delete-test-item\n"
        "---\nTest"
    )
    with patch.object(mod, "get_managed_skill_source_dirs", return_value=[_shared_skills(tmp_path)]):
        actions = mod._discover_actions(tmp_path)
    assert len(actions) >= 2
    ids = {a["id"] for a in actions}
    assert "add-item" in ids
    assert "delete-item" in ids


def test_discover_actions_ignores_generated_client_wrappers(tmp_path: Path) -> None:
    repo_skill = _shared_skills(tmp_path) / "repo-skill"
    wrapper_skill = tmp_path / ".gemini" / "skills" / "wrapper-skill"
    repo_skill.mkdir(parents=True)
    wrapper_skill.mkdir(parents=True)
    skill_doc = (
        "---\nname: {name}\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    actions:\n"
        "    - id: {action}\n"
        "      dispatch: fire\n"
        "      mcp_tool: {tool}\n"
        "---\nTest"
    )
    (repo_skill / "SKILL.md").write_text(
        skill_doc.format(name="repo-skill", action="repo-action", tool="repo-tool")
    )
    (wrapper_skill / "SKILL.md").write_text(
        skill_doc.format(name="wrapper-skill", action="wrapper-action", tool="wrapper-tool")
    )

    actions = mod._discover_actions(tmp_path)

    ids = {a["id"] for a in actions}
    assert "repo-action" in ids
    assert "wrapper-action" not in ids


def test_discover_registered_tools(tmp_path: Path) -> None:
    mcp_dir = _shared_skills(tmp_path) / "test-skill" / "scripts" / "mcp"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "__init__.py").write_text(
        '@mcp.tool(name="add-test-item")\nasync def add(): pass\n'
        '@mcp.tool(name="delete-test-item")\nasync def delete(): pass\n'
    )
    with patch.object(mod, "get_managed_skill_source_dirs", return_value=[_shared_skills(tmp_path)]):
        tools = mod._discover_registered_tools(tmp_path)
    assert "add-test-item" in tools
    assert "delete-test-item" in tools


def test_discover_registered_tools_scans_core_mcp_modules(tmp_path: Path) -> None:
    core_dir = tmp_path / "src" / "mcp" / "augur_core" / "tools" / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "__init__.py").write_text(
        '@mcp.tool(name="get-skill-health")\nasync def get_skill_health(): pass\n'
    )

    tools = mod._discover_registered_tools(tmp_path)

    assert "get-skill-health" in tools


def test_fix_does_not_run_mount_plugins_for_metadata_markers(tmp_path: Path) -> None:
    skill_dir = _shared_skills(tmp_path) / "test-skill"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("---\nname: test-skill\n---\nBody\n")
    ctx = make_test_ctx(tmp_path)
    issue = {
        "broken_stage": "action_tool_missing",
        "path": str(skill_md),
        "action_id": "broken-action",
        "mcp_tool": "missing-tool",
        "skill": "test-skill",
    }

    with patch.object(mod, "_run_mount_plugins") as mount_plugins:
        result = mod.fix(ctx, [issue])

    assert result.success
    mount_plugins.assert_not_called()
    assert "TODO_BUG(auto-e2e-actions)" in skill_md.read_text()


def test_build_test_args_modal() -> None:
    action = {
        "mcp_tool": "add-symptom",
        "modal_fields": [
            {"name": "name", "type": "text", "required": True},
            {"name": "severity", "type": "number", "required": True},
        ],
    }
    args = mod._build_test_args(action)
    assert args is not None
    assert "_e2e_test_" in args["name"]
    assert args["severity"] == 1


def test_build_test_args_no_tool() -> None:
    assert mod._build_test_args({"mcp_tool": ""}) is None


def test_build_test_args_prefers_static_args() -> None:
    args = mod._build_test_args(
        {
            "mcp_tool": "get-skill-health",
            "has_static_args": True,
            "args": {"skill_name": "validator"},
        }
    )
    assert args == {"skill_name": "validator"}


def test_d0_flags_missing_tool(tmp_path: Path) -> None:
    skill_dir = _shared_skills(tmp_path) / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    actions:\n"
        "    - id: broken-action\n"
        "      dispatch: fire\n"
        "      mcp_tool: nonexistent-tool\n"
        "---\nTest"
    )
    with patch.object(mod, "get_managed_skill_source_dirs", return_value=[_shared_skills(tmp_path)]):
        ctx = make_test_ctx(tmp_path, difficulty=0)
        result = mod.scan(ctx)
    missing = [i for i in result.issues if i.get("broken_stage") == "action_tool_missing"]
    assert len(missing) >= 1


def test_fix_dry_run(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path, dry_run=True)
    result = mod.fix(ctx, [{"broken_stage": "action_unwired"}])
    assert result.success
    assert "Dry run" in result.summary


def test_fix_empty_issues(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path)
    result = mod.fix(ctx, [])
    assert result.success
    assert "No issues" in result.summary
