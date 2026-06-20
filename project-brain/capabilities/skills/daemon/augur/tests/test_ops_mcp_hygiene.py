"""Tests for auto-mcp-hygiene ops module."""
from __future__ import annotations

from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_test_ctx


def _ctx(tmp_path: Path, **kwargs) -> OpsContext:
    return make_test_ctx(tmp_path, **kwargs)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_skill_with_mcp(tmp_path: Path, bundle: str = "test",
                          skill: str = "demo", tool_names: list[str] | None = None,
                          declared_tools: list[str] | None = None) -> Path:
    """Create a skill with MCP tool registrations and SKILL frontmatter."""
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / skill
    tool_names = tool_names or ["get-demo-items"]
    declared_tools = declared_tools if declared_tools is not None else tool_names

    # Python MCP init with tool registrations
    registrations = "\n".join(
        f'@mcp.tool(name="{t}")\ndef {t.replace("-", "_")}(): pass'
        for t in tool_names
    )
    _write(skill_dir / "scripts" / "mcp" / "__init__.py", registrations)

    tool_lines = "\n".join(f"- {t}" for t in declared_tools)
    _write(
        skill_dir / "SKILL.md",
        "---\n"
        f"name: {skill}\n"
        f"description: {skill} skill\n"
        f"x-augur-hub: {bundle}\n"
        "x-augur-mcp-tools:\n"
        f"{tool_lines}\n"
        "---\n",
    )
    return skill_dir


class TestScan:
    def test_scan_no_plugins_dir_returns_clean(self, tmp_path: Path):
        from skills.daemon.scripts.ops import mcp_hygiene

        result = mcp_hygiene.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert result.issues == []

    def test_scan_d0_surface_check_only(self, tmp_path: Path):
        from skills.daemon.scripts.ops import mcp_hygiene

        (tmp_path / "plugins").mkdir()
        result = mcp_hygiene.scan(_ctx(tmp_path, difficulty=0))

        assert result.issues == []
        assert result.health == "verified"

    def test_scan_d1_detects_verb_synonyms(self, tmp_path: Path):
        from skills.daemon.scripts.ops import mcp_hygiene

        _make_skill_with_mcp(
            tmp_path, tool_names=["fetch-demo-items"],
            declared_tools=["fetch-demo-items"],
        )

        result = mcp_hygiene.scan(_ctx(tmp_path, difficulty=1))

        rename_issues = [i for i in result.issues if i["action"] == "rename-verb"]
        assert len(rename_issues) == 1
        assert rename_issues[0]["old_verb"] == "fetch"
        assert rename_issues[0]["new_verb"] == "get"

    def test_scan_d1_detects_registration_mismatch(self, tmp_path: Path):
        from skills.daemon.scripts.ops import mcp_hygiene

        _make_skill_with_mcp(
            tmp_path,
            tool_names=["get-demo-items"],
            declared_tools=["get-demo-items", "get-extra-tool"],
        )

        result = mcp_hygiene.scan(_ctx(tmp_path, difficulty=1))

        declared_only = [i for i in result.issues if i["action"] == "remove-from-skill-md"]
        assert len(declared_only) == 1
        assert declared_only[0]["tool"] == "get-extra-tool"

    def test_scan_d1_clean_skill_no_issues(self, tmp_path: Path):
        from skills.daemon.scripts.ops import mcp_hygiene

        _make_skill_with_mcp(
            tmp_path,
            tool_names=["get-demo-items", "list-demo-categories"],
            declared_tools=["get-demo-items", "list-demo-categories"],
        )

        result = mcp_hygiene.scan(_ctx(tmp_path, difficulty=1))

        assert result.issues == []
        assert result.severity == "info"

    def test_scan_d3_detects_duplicates(self, tmp_path: Path):
        from skills.daemon.scripts.ops import mcp_hygiene

        _make_skill_with_mcp(
            tmp_path,
            tool_names=["get-demo-items", "fetch-demo-items"],
            declared_tools=["get-demo-items", "fetch-demo-items"],
        )

        result = mcp_hygiene.scan(_ctx(tmp_path, difficulty=3))

        dup_issues = [i for i in result.issues if i["action"] == "potential-duplicate"]
        assert len(dup_issues) >= 1


class TestFix:
    def test_fix_dry_run(self, tmp_path: Path):
        from skills.daemon.scripts.ops import mcp_hygiene

        result = mcp_hygiene.fix(
            _ctx(tmp_path, dry_run=True),
            [{"action": "rename-verb", "file": "test", "tool": "fetch-x"}],
        )

        assert isinstance(result, FixResult)
        assert result.success is True
        assert "Dry run" in result.summary

    def test_fix_no_issues(self, tmp_path: Path):
        from skills.daemon.scripts.ops import mcp_hygiene

        result = mcp_hygiene.fix(_ctx(tmp_path), [])

        assert result.success is True
        assert "No issues" in result.summary


class TestHelpers:
    def test_extract_verb(self):
        from skills.daemon.scripts.ops.mcp_hygiene import _extract_verb

        assert _extract_verb("get-career-jobs") == "get"
        assert _extract_verb("fetch-items") == "fetch"
        assert _extract_verb("list_all_things") == "list"

    def test_get_registered_tools_from_python(self, tmp_path: Path):
        from skills.daemon.scripts.ops.mcp_hygiene import (
            _get_registered_tools_from_python,
        )

        init = tmp_path / "__init__.py"
        _write(
            init,
            '@mcp.tool(name="get-items")\n'
            'def get_items(): pass\n'
            '@mcp_tool_interceptor(name="list-items")\n'
            'def list_items(): pass\n',
        )

        tools = _get_registered_tools_from_python(init)
        assert set(tools) == {"get-items", "list-items"}

    def test_get_declared_tools_from_skill_md(self, tmp_path: Path):
        from skills.daemon.scripts.ops.mcp_hygiene import (
            _get_declared_tools_from_skill_md,
        )

        skill_md = tmp_path / "SKILL.md"
        _write(
            skill_md,
            "---\n"
            "name: demo\n"
            "description: Demo\n"
            "x-augur-mcp-tools:\n"
            "- get-items\n"
            "x-augur-config:\n"
            "  mcp:\n"
            "    tools:\n"
            "      - name: list-items\n"
            "---\n",
        )

        tools = _get_declared_tools_from_skill_md(skill_md)
        assert set(tools) == {"get-items", "list-items"}

    def test_get_declared_tools_from_missing_file(self, tmp_path: Path):
        from skills.daemon.scripts.ops.mcp_hygiene import (
            _get_declared_tools_from_skill_md,
        )

        tools = _get_declared_tools_from_skill_md(tmp_path / "SKILL.md")
        assert tools == []


class TestModuleInterface:
    def test_has_name(self):
        from skills.daemon.scripts.ops import mcp_hygiene
        assert mcp_hygiene.name == "auto-mcp-hygiene"

    def test_declares_windows_auto_fix_capabilities(self):
        from skills.daemon.scripts.ops import mcp_hygiene
        assert mcp_hygiene.OPS_CAPABILITIES.platforms == ("cross_platform",)
        assert mcp_hygiene.OPS_CAPABILITIES.windows_fix_mode == "auto_fix"

    def test_has_scan_callable(self):
        from skills.daemon.scripts.ops import mcp_hygiene
        assert callable(mcp_hygiene.scan)

    def test_has_fix_callable(self):
        from skills.daemon.scripts.ops import mcp_hygiene
        assert callable(mcp_hygiene.fix)
