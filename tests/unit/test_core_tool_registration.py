"""Tests for core MCP tool registration names."""

from types import SimpleNamespace


class _FakeMCP:
    def __init__(self):
        self.names: list[str] = []
        self.annotations: dict[str, object] = {}

    def tool(self, *, name: str, annotations=None):
        def decorator(fn):
            self.names.append(name)
            self.annotations[name] = annotations
            return fn

        return decorator


def test_register_core_tools_uses_updated_skill_command_names():
    from src.mcp.augur_core.tools.core import register_core_tools

    fake_mcp = _FakeMCP()

    register_core_tools(
        fake_mcp,
        skill_cache=SimpleNamespace(),
        metrics=SimpleNamespace(),
        registry_list_skills=lambda **kwargs: [],
        resolve_skill_entry=lambda *args, **kwargs: None,
        available_skill_ids=lambda: [],
    )

    assert "skill-resync" in fake_mcp.names
    assert "skill-refresh" not in fake_mcp.names
    assert "skill-upstream-status" in fake_mcp.names
    assert "update-skill-doc" in fake_mcp.names
    assert "brain-active-context" in fake_mcp.names
    assert "brain-set-active-context" in fake_mcp.names
    assert "brain-folder-scan" in fake_mcp.names
    assert fake_mcp.annotations["brain-active-context"].readOnlyHint is False
    assert fake_mcp.annotations["brain-set-active-context"].readOnlyHint is False
    assert fake_mcp.annotations["brain-folder-scan"].readOnlyHint is True
