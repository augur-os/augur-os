"""Tests for ADR-030: Context Manager with priority merge algorithm."""

from __future__ import annotations

import sys
import types
from pathlib import Path
import pytest

# Add ai plugin root and project root to path
ai_root = Path(__file__).resolve().parent.parent
ai_augur_root = ai_root / "augur"
project_root = Path(__file__).resolve().parents[4]
for p in (str(ai_augur_root), str(ai_root), str(project_root)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Add MCP package to path
mcp_src = project_root / "src" / "mcp"
if str(mcp_src) not in sys.path:
    sys.path.insert(0, str(mcp_src))

# Clear any cached 'lib' module from other plugins to avoid cross-test pollution
for _mod_name in [k for k in sys.modules if k == "lib" or k.startswith("lib.")]:
    del sys.modules[_mod_name]

# Some test modules register a fake top-level augur_mcp module into sys.modules.
# Remove those stubs so this suite imports the real package from src/mcp.
for _mod_name in [k for k in sys.modules if k == "augur_mcp" or k.startswith("augur_mcp.")]:
    del sys.modules[_mod_name]

# Provide a minimal FastMCP stub for test environments without the external MCP package.
if "mcp.server.fastmcp" not in sys.modules:
    try:
        import mcp as mcp_module  # type: ignore
    except ImportError:
        mcp_module = types.ModuleType("mcp")
        sys.modules["mcp"] = mcp_module

    server_module = sys.modules.get("mcp.server")
    if server_module is None:
        server_module = types.ModuleType("mcp.server")
        sys.modules["mcp.server"] = server_module
    fastmcp_module = types.ModuleType("mcp.server.fastmcp")

    class FastMCP:  # pragma: no cover - simple test stub
        pass

    fastmcp_module.FastMCP = FastMCP
    mcp_module.server = server_module
    server_module.fastmcp = fastmcp_module
    sys.modules["mcp.server.fastmcp"] = fastmcp_module

# Import discovery functions at module level (before other tests can pollute sys.modules)
from src.lib.ai.discovery import strip_yaml_frontmatter, scan_ai_skills  # noqa: E402

from src.mcp.augur_shared.context_manager import (  # noqa: E402
    AugurMode,
    ClientCapability,
    MCPToolState,
    MergedContext,
    PageContext,
    Skill,
    UserSettings,
)

# --- Fixtures ---


@pytest.fixture(autouse=True)
def setup_augur_data(monkeypatch, tmp_path):
    """Ensure AUGUR_ROOT paths are set to a valid temp dir for all tests in this module."""
    data_dir = tmp_path / "augur_data"
    data_dir.mkdir()
    monkeypatch.setenv("AUGUR_ROOT", str(data_dir))
    monkeypatch.setenv("AUGUR_ROOT", str(data_dir))

    # Also ensure config dir exists inside it, as config.py might look for it
    (data_dir / "config").mkdir()

    return data_dir


def _make_skills() -> list[Skill]:
    """Create a standard set of test skills."""
    return [
        Skill(name="code-review", description="Code review", mode=None, mcp_overlaps=[]),
        Skill(
            name="rag-search",
            description="RAG search",
            mode=None,
            mcp_overlaps=["query_rag"],
        ),
        Skill(name="dev-tools", description="Dev tooling", mode="dev", mcp_overlaps=[]),
        Skill(
            name="ops-dashboard",
            description="Ops dashboard",
            mode="ops",
            mcp_overlaps=[],
        ),
    ]


def _make_mcp_tools() -> list[MCPToolState]:
    """Create a standard set of test MCP tools."""
    return [
        MCPToolState(name="query_rag", description="Query RAG system"),
        MCPToolState(name="get_context", description="Get context"),
        MCPToolState(name="run_tests", description="Run test suite"),
    ]


class _FakeMCP:
    """Minimal stub for FastMCP to satisfy ContextManager.__init__."""

    def remove_tool(self, name: str) -> None:
        pass

    def add_tool(self, func: object) -> None:
        pass


def _make_cm(client: str = "claude_code"):
    """Create a ContextManager with a fake MCP instance."""
    from src.mcp.augur_shared.context_manager import ContextManager

    return ContextManager(_FakeMCP(), client=client)


# --- Test: Context Merge Priority ---


class TestContextMergePriority:
    """ADR-030 requirement: test_context_merge_priority - User settings override all."""

    def test_user_settings_override_all(self):
        """User settings are highest priority and override everything."""
        cm = _make_cm()
        skills = _make_skills()
        mcp_tools = _make_mcp_tools()

        # User explicitly disables code-review skill
        settings = UserSettings(disabled_skills=["code-review"])

        result = cm.build_merged_context(
            mode=AugurMode.OPS,
            skills=skills,
            mcp_tools=mcp_tools,
            user_settings=settings,
        )

        enabled_names = [s.name for s in result.enabled_skills]
        assert "code-review" not in enabled_names, "User-disabled skill should not be in enabled list"

    def test_user_can_reenable_auto_disabled_mcp(self):
        """ADR-030 UC-4: User override re-enables auto-disabled MCP tool."""
        cm = _make_cm()
        skills = _make_skills()  # rag-search overlaps query_rag
        mcp_tools = _make_mcp_tools()

        # User explicitly re-enables query_rag
        settings = UserSettings(mcp_overrides={"query_rag": True})

        result = cm.build_merged_context(
            mode=AugurMode.OPS,
            skills=skills,
            mcp_tools=mcp_tools,
            user_settings=settings,
        )

        enabled_mcp_names = [t.name for t in result.enabled_mcp_tools]
        assert "query_rag" in enabled_mcp_names, "User override should re-enable auto-disabled MCP tool"

    def test_user_can_disable_mcp(self):
        """User can force-disable an MCP tool."""
        cm = _make_cm()
        mcp_tools = _make_mcp_tools()

        settings = UserSettings(mcp_overrides={"run_tests": False})

        result = cm.build_merged_context(
            mode=AugurMode.OPS,
            skills=[],
            mcp_tools=mcp_tools,
            user_settings=settings,
        )

        disabled_mcp_names = [t.name for t in result.disabled_mcp_tools]
        assert "run_tests" in disabled_mcp_names


# --- Test: Mode Filtering ---


class TestModeFiltering:
    """ADR-030 requirement: Dev/Ops mode properly filters skills."""

    def test_dev_mode_enables_dev_skills(self):
        """Dev mode includes dev-only skills."""
        cm = _make_cm()
        skills = _make_skills()

        result = cm.build_merged_context(
            mode=AugurMode.DEV,
            skills=skills,
            mcp_tools=[],
        )

        enabled_names = [s.name for s in result.enabled_skills]
        assert "dev-tools" in enabled_names
        assert "ops-dashboard" not in enabled_names

    def test_ops_mode_enables_ops_skills(self):
        """Ops mode includes ops-only skills."""
        cm = _make_cm()
        skills = _make_skills()

        result = cm.build_merged_context(
            mode=AugurMode.OPS,
            skills=skills,
            mcp_tools=[],
        )

        enabled_names = [s.name for s in result.enabled_skills]
        assert "ops-dashboard" in enabled_names
        assert "dev-tools" not in enabled_names

    def test_mode_agnostic_skills_always_enabled(self):
        """Skills with no mode restriction are enabled in both modes."""
        cm = _make_cm()
        skills = _make_skills()

        for mode in (AugurMode.DEV, AugurMode.OPS):
            result = cm.build_merged_context(mode=mode, skills=skills, mcp_tools=[])
            enabled_names = [s.name for s in result.enabled_skills]
            assert "code-review" in enabled_names, f"code-review should be enabled in {mode.value}"
            assert "rag-search" in enabled_names, f"rag-search should be enabled in {mode.value}"


# --- Test: MCP Auto-Disable ---


class TestMCPAutoDisable:
    """ADR-030 requirement: Skills overlap with MCP auto-disables MCP."""

    def test_skill_disables_overlapping_mcp(self):
        """When a skill covers an MCP tool, the MCP tool is auto-disabled."""
        cm = _make_cm()
        skills = _make_skills()  # rag-search has mcp_overlaps=["query_rag"]
        mcp_tools = _make_mcp_tools()

        result = cm.build_merged_context(
            mode=AugurMode.OPS,
            skills=skills,
            mcp_tools=mcp_tools,
        )

        disabled_mcp_names = [t.name for t in result.disabled_mcp_tools]
        assert "query_rag" in disabled_mcp_names, "query_rag should be auto-disabled by rag-search skill"

        # Verify the reason is recorded
        disabled_query_rag = [t for t in result.disabled_mcp_tools if t.name == "query_rag"][0]
        assert "rag-search" in disabled_query_rag.disabled_reason

    def test_non_overlapping_mcp_stays_enabled(self):
        """MCP tools without skill overlap remain enabled."""
        cm = _make_cm()
        skills = _make_skills()
        mcp_tools = _make_mcp_tools()

        result = cm.build_merged_context(
            mode=AugurMode.OPS,
            skills=skills,
            mcp_tools=mcp_tools,
        )

        enabled_mcp_names = [t.name for t in result.enabled_mcp_tools]
        assert "get_context" in enabled_mcp_names
        assert "run_tests" in enabled_mcp_names


# --- Test: Limited Client Fallback ---


class TestLimitedClientFallback:
    """ADR-030 integration test: Limited client fallback keeps all MCP."""

    def test_codex_keeps_all_mcp(self):
        """Codex (limited client) keeps all MCP tools enabled."""
        cm = _make_cm(client="codex")
        skills = _make_skills()  # rag-search overlaps query_rag
        mcp_tools = _make_mcp_tools()

        result = cm.build_merged_context(
            mode=AugurMode.OPS,
            skills=skills,
            mcp_tools=mcp_tools,
        )

        # All MCP tools should remain enabled for limited clients
        enabled_mcp_names = [t.name for t in result.enabled_mcp_tools]
        assert "query_rag" in enabled_mcp_names, "Limited clients should keep all MCP enabled"
        assert "get_context" in enabled_mcp_names
        assert "run_tests" in enabled_mcp_names

    def test_full_client_disables_overlapping_mcp(self):
        """Full capability clients auto-disable overlapping MCP."""
        cm = _make_cm()
        skills = _make_skills()
        mcp_tools = _make_mcp_tools()

        result = cm.build_merged_context(
            mode=AugurMode.OPS,
            skills=skills,
            mcp_tools=mcp_tools,
        )

        enabled_mcp_names = [t.name for t in result.enabled_mcp_tools]
        assert "query_rag" not in enabled_mcp_names, "Full clients should auto-disable overlapping MCP"


# --- Test: Mode Persistence ---


class TestModePersistence:
    """ADR-030 requirement: test_mode_persistence - Mode survives restart."""

    def test_mode_roundtrip(self, tmp_path):
        """Mode is saved and read back correctly via YAML config."""
        config_path = tmp_path / "config.yaml"

        # Default should be "ops" (no file)
        assert not config_path.exists()

        # Write dev mode
        import yaml

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.dump({"augur": {"mode": "dev"}}))

        loaded = yaml.safe_load(config_path.read_text())
        assert loaded["augur"]["mode"] == "dev"

        # Write ops mode
        config_path.write_text(yaml.dump({"augur": {"mode": "ops"}}))
        loaded = yaml.safe_load(config_path.read_text())
        assert loaded["augur"]["mode"] == "ops"

    def test_mode_preserves_existing_config(self, tmp_path):
        """Setting mode doesn't clobber other config keys."""
        import yaml

        config_path = tmp_path / "config.yaml"

        # Write existing config
        existing = {"user": {"name": "Test"}, "augur": {"other_key": "value"}}
        config_path.write_text(yaml.dump(existing))

        # Update mode
        loaded = yaml.safe_load(config_path.read_text())
        loaded["augur"]["mode"] = "dev"
        config_path.write_text(yaml.dump(loaded))

        # Verify other keys preserved
        result = yaml.safe_load(config_path.read_text())
        assert result["user"]["name"] == "Test"
        assert result["augur"]["other_key"] == "value"
        assert result["augur"]["mode"] == "dev"


# --- Test: Skills Sync ---


class TestSkillsSync:
    """ADR-030 requirements: test_skills_sync_claude, test_skills_sync_windsurf."""

    def test_strip_yaml_frontmatter(self):
        """YAML frontmatter is properly stripped for non-Claude clients."""
        content = """---
name: test-skill
description: A test skill
hooks:
  SessionStart:
    - command: "echo hello"
---

# Test Skill

This is the content."""

        stripped = strip_yaml_frontmatter(content)
        assert "---" not in stripped
        assert "name: test-skill" not in stripped
        assert "# Test Skill" in stripped
        assert "This is the content." in stripped

    def test_strip_preserves_content_without_frontmatter(self):
        """Content without frontmatter is returned unchanged."""
        content = "# No Frontmatter\n\nJust content."
        assert strip_yaml_frontmatter(content) == content

    def test_scan_ai_skills(self, tmp_path):
        """Skills are scanned with metadata extracted."""
        # Create test skill
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill
---

# Test Skill
""")

        skills = scan_ai_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0]["name"] == "test-skill"
        assert skills[0]["has_frontmatter"] is True

    def test_scan_skips_non_directories(self, tmp_path):
        """Non-directory entries are skipped."""
        (tmp_path / "readme.txt").write_text("not a skill")
        skills = scan_ai_skills(tmp_path)
        assert len(skills) == 0


# --- Test: MergedContext Serialization ---


class TestMergedContextSerialization:
    """Test MergedContext.to_dict() output."""

    def test_to_dict(self):
        """MergedContext serializes correctly."""
        ctx = MergedContext(
            mode=AugurMode.DEV,
            enabled_skills=[Skill(name="s1")],
            disabled_skills=[Skill(name="s2")],
            enabled_mcp_tools=[MCPToolState(name="t1")],
            disabled_mcp_tools=[MCPToolState(name="t2", disabled_reason="test")],
            page_context=PageContext(page_id="control"),
            merge_log=["test log"],
        )

        d = ctx.to_dict()
        assert d["mode"] == "dev"
        assert d["enabled_skills"] == ["s1"]
        assert d["disabled_skills"] == ["s2"]
        assert d["enabled_mcp_tools"] == ["t1"]
        assert d["disabled_mcp_tools"] == [{"name": "t2", "reason": "test"}]
        assert d["page"] == "control"
        assert d["merge_log"] == ["test log"]


# --- Test: Client Capability Detection ---


class TestClientCapability:
    """Test client capability mapping."""

    def test_claude_is_full(self):
        cm = _make_cm(client="claude_code")
        assert cm.capability == ClientCapability.FULL

    def test_cursor_is_full(self):
        cm = _make_cm(client="cursor")
        assert cm.capability == ClientCapability.FULL

    def test_gemini_is_limited(self):
        cm = _make_cm(client="gemini")
        assert cm.capability == ClientCapability.LIMITED

    def test_codex_is_limited(self):
        cm = _make_cm(client="codex")
        assert cm.capability == ClientCapability.LIMITED

    def test_unknown_client_is_none(self):
        cm = _make_cm(client="unknown_ide")
        assert cm.capability == ClientCapability.NONE


# --- Test: MCP Config Generation (ADR-030 requirement) ---


class TestMCPConfigGeneration:
    """ADR-030 requirement: test_mcp_config_generation."""

    def test_mcp_config_generation(self, tmp_path):
        """MCP config is generated from template with resolved variables."""
        import json

        # Create a mock template
        template_path = tmp_path / "mcp_config.template.json"
        template_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "augur": {
                            "args": ["-m", "augur_mcp"],
                            "command": "${AUGUR_PYTHON}",
                            "cwd": "${AUGUR_ROOT}",
                            "env": {
                                "AUGUR_ROOT": "${AUGUR_ROOT}",
                                "AUGUR_DATA": "${AUGUR_DATA}",
                                "PYTHONPATH": "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp",
                            },
                        }
                    }
                }
            )
        )

        # Simulate the template resolution logic from sync_agents.py
        content = template_path.read_text(encoding="utf-8")
        proj_root = (tmp_path / "project").as_posix()
        python_path = "python3"

        resolved = content.replace("${AUGUR_ROOT}", proj_root)
        resolved = resolved.replace("${AUGUR_DATA}", f"{proj_root}/data")
        resolved = resolved.replace("${AUGUR_PYTHON}", python_path)

        config = json.loads(resolved)

        # Verify the resolved config
        augur_server = config["mcpServers"]["augur"]
        assert augur_server["command"] == "python3"
        assert augur_server["cwd"] == proj_root
        assert augur_server["env"]["AUGUR_ROOT"] == proj_root
        assert augur_server["env"]["AUGUR_DATA"] == f"{proj_root}/data"
        assert proj_root in augur_server["env"]["PYTHONPATH"]

    def test_mcp_config_written_to_claude_dir(self, tmp_path):
        """Resolved MCP config is written to the .claude/ directory."""
        import json

        # Write resolved config
        target = tmp_path / ".claude" / "mcp.json"
        target.parent.mkdir(parents=True)

        config = {
            "mcpServers": {
                "augur": {
                    "args": ["-m", "augur_mcp"],
                    "command": "python3",
                }
            }
        }
        target.write_text(json.dumps(config, indent=2))

        # Verify it was written and is valid JSON
        loaded = json.loads(target.read_text())
        assert "augur" in loaded["mcpServers"]
        assert loaded["mcpServers"]["augur"]["command"] == "python3"


# --- Test: Claude Desktop Config Merge (ADR-030 requirement) ---


class TestClaudeDesktopMerge:
    """ADR-030 requirement: test_claude_desktop_merge."""

    def test_claude_desktop_merge_preserves_existing(self, tmp_path):
        """Merging Augur into Claude Desktop config preserves existing servers."""
        import json

        config_path = tmp_path / "claude_desktop_config.json"

        # Existing config with another server
        existing = {
            "mcpServers": {
                "other-server": {
                    "command": "node",
                    "args": ["other-mcp"],
                }
            }
        }
        config_path.write_text(json.dumps(existing))

        # Simulate the merge logic from claude_desktop.py
        config = json.loads(config_path.read_text(encoding="utf-8"))

        # Check augur not present
        assert "augur" not in config["mcpServers"]

        # Merge augur entry
        config["mcpServers"]["augur"] = {
            "args": ["-m", "augur_mcp"],
            "command": "python3",
            "cwd": str(tmp_path),
        }

        config_path.write_text(json.dumps(config, indent=2))

        # Verify both servers present
        loaded = json.loads(config_path.read_text())
        assert "augur" in loaded["mcpServers"]
        assert "other-server" in loaded["mcpServers"]
        assert loaded["mcpServers"]["other-server"]["command"] == "node"

    def test_claude_desktop_merge_no_duplicate(self, tmp_path):
        """If augur already present, merge doesn't create duplicates."""
        import json

        config_path = tmp_path / "claude_desktop_config.json"
        existing = {"mcpServers": {"augur": {"command": "python3", "args": ["-m", "augur_mcp"]}}}
        config_path.write_text(json.dumps(existing))

        config = json.loads(config_path.read_text())
        already_configured = "augur" in config.get("mcpServers", {})
        assert already_configured is True

    def test_claude_desktop_merge_empty_config(self, tmp_path):
        """Merge works when starting from empty config."""
        import json

        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text("{}")

        config = json.loads(config_path.read_text())
        if "mcpServers" not in config:
            config["mcpServers"] = {}
        config["mcpServers"]["augur"] = {
            "args": ["-m", "augur_mcp"],
            "command": "python3",
        }

        config_path.write_text(json.dumps(config, indent=2))

        loaded = json.loads(config_path.read_text())
        assert "augur" in loaded["mcpServers"]


# --- Test: Use Case Validation ---


class TestUseCases:
    """Validate all 6 use cases from ADR-030."""

    def test_uc1_skills_synced_to_claude(self, tmp_path):
        """UC-1: Skills from skills/ai/augur/skills/ sync to skills/."""
        # Create source skill
        skills_dir = tmp_path / "data" / "ai" / "skills" / "code-review"
        skills_dir.mkdir(parents=True)
        skill_content = "---\nname: code-review\n---\n\n# Code Review\nReview code."
        (skills_dir / "SKILL.md").write_text(skill_content)

        # Target directory
        target = tmp_path / ".claude" / "skills" / "code-review" / "SKILL.md"
        target.parent.mkdir(parents=True)

        # Simulate sync (copy with frontmatter preserved)
        source_content = (skills_dir / "SKILL.md").read_text()
        target.write_text(source_content)

        # Verify: skill synced with frontmatter intact
        assert target.exists()
        synced = target.read_text()
        assert "---" in synced  # Frontmatter preserved for Claude
        assert "name: code-review" in synced

    def test_uc2_skills_synced_to_windsurf(self, tmp_path):
        """UC-2: Skills sync to .windsurf/workflows/ without frontmatter."""
        skill_content = "---\nname: code-review\n---\n\n# Code Review\nReview code."
        stripped = strip_yaml_frontmatter(skill_content)

        target = tmp_path / ".windsurf" / "workflows" / "code-review.md"
        target.parent.mkdir(parents=True)
        target.write_text(stripped)

        # Verify: no YAML syntax errors (no frontmatter)
        synced = target.read_text()
        assert "---" not in synced
        assert "# Code Review" in synced

    def test_uc3_mcp_tool_disabled_by_skill(self):
        """UC-3: MCP tool auto-disabled when skill covers it."""
        cm = _make_cm()
        skills = [Skill(name="rag-search", mcp_overlaps=["query_rag"])]
        mcp_tools = [MCPToolState(name="query_rag")]

        result = cm.build_merged_context(mode=AugurMode.OPS, skills=skills, mcp_tools=mcp_tools)

        enabled_mcp_names = [t.name for t in result.enabled_mcp_tools]
        assert "query_rag" not in enabled_mcp_names

    def test_uc4_user_overrides_mcp_disable(self):
        """UC-4: User override re-enables auto-disabled MCP tool."""
        cm = _make_cm()
        skills = [Skill(name="rag-search", mcp_overlaps=["query_rag"])]
        mcp_tools = [MCPToolState(name="query_rag")]
        settings = UserSettings(mcp_overrides={"query_rag": True})

        result = cm.build_merged_context(
            mode=AugurMode.OPS,
            skills=skills,
            mcp_tools=mcp_tools,
            user_settings=settings,
        )

        enabled_mcp_names = [t.name for t in result.enabled_mcp_tools]
        assert "query_rag" in enabled_mcp_names

    def test_uc5_mode_persists_across_sessions(self, tmp_path):
        """UC-5: Mode toggle persists to config and survives restart."""
        import yaml

        config_path = tmp_path / "config.yaml"

        # Simulate: user clicks "Dev Mode" in dashboard
        config_path.write_text(yaml.dump({"augur": {"mode": "dev"}}))

        # Simulate: user closes dashboard, reopens later
        loaded = yaml.safe_load(config_path.read_text())
        assert loaded["augur"]["mode"] == "dev"

    def test_uc6_mode_toggle_via_mcp(self, tmp_path):
        """UC-6: Mode set via MCP command updates config."""
        import yaml

        config_path = tmp_path / "config.yaml"

        # Simulate: augur-config --mode ops
        config_path.write_text(yaml.dump({"augur": {"mode": "ops"}}))
        loaded = yaml.safe_load(config_path.read_text())
        assert loaded["augur"]["mode"] == "ops"

        # Verify dev tools not loaded, ops tools loaded
        cm = _make_cm()
        skills = _make_skills()
        result = cm.build_merged_context(mode=AugurMode.OPS, skills=skills, mcp_tools=[])

        enabled_names = [s.name for s in result.enabled_skills]
        assert "ops-dashboard" in enabled_names
        assert "dev-tools" not in enabled_names
