"""Unit tests for src.mcp.augur_shared.context_types — ADR-030 data models."""

from __future__ import annotations

from src.mcp.augur_shared.context_types import (
    CLIENT_CAPABILITIES,
    DEFAULT_MODE,
    VALID_MODES,
    WEB_CHAT_CLIENT,
    AugurMode,
    ClientCapability,
    MCPToolState,
    MergedContext,
    PageContext,
    Skill,
    UserSettings,
)


def test_augur_mode_enum_values():
    assert AugurMode.DEV.value == "dev"
    assert AugurMode.OPS.value == "ops"
    # str-Enum behaves as its string value.
    assert AugurMode.DEV == "dev"


def test_client_capability_mapping():
    assert CLIENT_CAPABILITIES["claude_code"] is ClientCapability.FULL
    assert CLIENT_CAPABILITIES["gemini"] is ClientCapability.LIMITED
    assert CLIENT_CAPABILITIES["web-chat"] is ClientCapability.NONE


def test_module_constants():
    assert WEB_CHAT_CLIENT == "web-chat"
    assert DEFAULT_MODE == "ops"
    assert VALID_MODES == {"dev", "ops"}


def test_skill_defaults_and_mode_properties():
    s = Skill(name="ingest")
    assert s.description == ""
    assert s.triggers == []
    assert s.mcp_overlaps == []
    assert s.enabled is True
    assert s.is_dev_only is False
    assert s.is_ops_only is False

    dev_skill = Skill(name="d", mode="dev")
    assert dev_skill.is_dev_only is True
    assert dev_skill.is_ops_only is False

    ops_skill = Skill(name="o", mode="ops")
    assert ops_skill.is_ops_only is True
    assert ops_skill.is_dev_only is False


def test_skill_independent_default_factories():
    a = Skill(name="a")
    b = Skill(name="b")
    a.triggers.append("x")
    assert b.triggers == []  # default_factory gives each instance its own list


def test_mcp_tool_state_defaults():
    t = MCPToolState(name="list-skills")
    assert t.enabled is True
    assert t.disabled_reason is None


def test_user_settings_defaults():
    u = UserSettings()
    assert u.disabled_skills == []
    assert u.enabled_skills == []
    assert u.mcp_overrides == {}
    assert u.custom_settings == {}


def test_page_context_defaults():
    p = PageContext()
    assert p.page_id is None
    assert p.hub is None
    assert p.active_tools == []


def test_merged_context_to_dict():
    merged = MergedContext(
        mode=AugurMode.DEV,
        enabled_skills=[Skill(name="ingest"), Skill(name="wiki")],
        disabled_skills=[Skill(name="legacy")],
        enabled_mcp_tools=[MCPToolState(name="list-skills")],
        disabled_mcp_tools=[MCPToolState(name="risky", disabled_reason="overlap")],
        page_context=PageContext(page_id="browse"),
        merge_log=["merged ok"],
    )
    d = merged.to_dict()
    assert d["mode"] == "dev"
    assert d["enabled_skills"] == ["ingest", "wiki"]
    assert d["disabled_skills"] == ["legacy"]
    assert d["enabled_mcp_tools"] == ["list-skills"]
    assert d["disabled_mcp_tools"] == [{"name": "risky", "reason": "overlap"}]
    assert d["page"] == "browse"
    assert d["merge_log"] == ["merged ok"]


def test_merged_context_to_dict_no_page():
    merged = MergedContext(mode=AugurMode.OPS)
    d = merged.to_dict()
    assert d["mode"] == "ops"
    assert d["page"] is None
    assert d["enabled_skills"] == []
