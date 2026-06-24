class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, annotations=None):
        def deco(fn):
            self.tools[name] = fn
            return fn

        return deco


def test_browse_delete_tools_registered():
    from src.mcp.augur_framework.tools.infrastructure.browse_trash import register_browse_trash_tools
    from src.mcp.augur_framework.tools.infrastructure.browse_delete_triage import (
        register_browse_delete_triage_tools,
    )

    mcp = _FakeMCP()
    register_browse_trash_tools(mcp, lambda fn: fn, type("M", (), {"track_tool": lambda *a: None})())
    register_browse_delete_triage_tools(mcp, lambda fn: fn, type("M", (), {"track_tool": lambda *a: None})())
    assert "browse-trash" in mcp.tools
    assert "browse-delete-triage" in mcp.tools
