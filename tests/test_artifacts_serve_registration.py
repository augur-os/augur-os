"""Registration smoke test for artifact-resolve / artifact-html tools."""


class _FakeMCP:
    def __init__(self): self.tools = {}
    def tool(self, name, annotations=None):
        def deco(fn): self.tools[name] = fn; return fn
        return deco


def test_artifact_serve_tools_registered():
    from src.mcp.augur_core.tools.core.artifacts_serve import register_artifacts_serve_tools
    mcp = _FakeMCP()
    register_artifacts_serve_tools(mcp, lambda fn: fn, type("M", (), {"track_tool": lambda *a: None})())
    assert "artifact-resolve" in mcp.tools
    assert "artifact-html" in mcp.tools
