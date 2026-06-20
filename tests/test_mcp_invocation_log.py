"""ADR-804: structured MCP invocation log feeds the optimizer's replay."""

import json


def test_record_invocation_writes_structured_line(tmp_path, monkeypatch):
    from src.mcp.augur_shared import mcp_sdk
    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_logs_dir", lambda: tmp_path)
    mcp_sdk._INVOCATION_LOG_DISABLED = False
    mcp_sdk._record_invocation("find-skill", {"query": "pdf", "self": "drop-me"}, "the result", 12)
    rec = json.loads((tmp_path / "mcp_invocations.jsonl").read_text().splitlines()[-1])
    assert rec["tool"] == "find-skill" and rec["args"] == {"query": "pdf"} and rec["result"] == "the result"
    assert "self" not in rec["args"]


def test_record_invocation_never_raises(monkeypatch):
    from src.mcp.augur_shared import mcp_sdk
    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_logs_dir", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    mcp_sdk._INVOCATION_LOG_DISABLED = False
    mcp_sdk._record_invocation("t", {"a": 1}, "r", 1)  # must not raise
    assert mcp_sdk._INVOCATION_LOG_DISABLED is True
