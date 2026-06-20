import importlib.util, sys
from pathlib import Path

OPT = Path(__file__).resolve().parents[2] / "scripts" / "optimizer"
sys.path.insert(0, str(OPT))
spec = importlib.util.spec_from_file_location("replay_source", OPT / "replay_source.py")
replay_source = importlib.util.module_from_spec(spec); sys.modules["replay_source"] = replay_source; spec.loader.exec_module(replay_source)


def test_parse_mcp_log_extracts_tool_calls(tmp_path):
    log = tmp_path / "augur_mcp.log"
    log.write_text(
        '{"tool": "find-skill", "args": {"query": "pdf"}, "result": "ok-1"}\n'
        '{"tool": "other-tool", "args": {"x": 1}, "result": "z"}\n'
        '{"tool": "find-skill", "args": {"query": "ocr"}, "result": "ok-2"}\n'
    )
    cases = replay_source._parse_mcp_log(log, tool_name="find-skill", limit=10)
    assert [c.inputs["query"] for c in cases] == ["pdf", "ocr"]
    assert cases[0].prior_output == "ok-1" and cases[0].source == "mcp-log"


def test_parse_mcp_log_missing_file_empty(tmp_path):
    assert replay_source._parse_mcp_log(tmp_path / "none.log", tool_name="x", limit=5) == []


def test_curated_evals_fallback(tmp_path):
    evals = tmp_path / "evals.json"
    evals.write_text('{"cases": [{"inputs": {"q": "a"}, "expected": "A"}]}')
    cases = replay_source._load_curated_evals(evals)
    assert cases[0].inputs == {"q": "a"} and cases[0].prior_output == "A" and cases[0].source == "curated-eval"


def test_collect_prefers_mcp_then_falls_back(tmp_path):
    mcp = tmp_path / "augur_mcp.log"
    mcp.write_text('{"tool": "t1", "args": {"q": "x"}, "result": "r"}\n')
    # MCP hit:
    cases = replay_source.collect_replay_cases({"name": "s", "tool_name": "t1"}, mcp_log=mcp, limit=5)
    assert cases and cases[0].source == "mcp-log"
    # No MCP match -> curated evals fallback:
    ev = tmp_path / "evals.json"; ev.write_text('{"cases": [{"inputs": {"q": "y"}}]}')
    cases2 = replay_source.collect_replay_cases({"name": "s", "tool_name": "nomatch"}, mcp_log=mcp, evals_path=ev, limit=5)
    assert cases2 and cases2[0].source == "curated-eval"


def test_parse_invocation_log_chronological(tmp_path):
    log = tmp_path / "mcp_invocations.jsonl"
    log.write_text(
        '{"ts": 1, "tool": "find-skill", "args": {"query": "pdf"}, "result": "R1"}\n'
        '{"ts": 2, "tool": "other", "args": {"x": 1}, "result": "z"}\n'
        '{"ts": 3, "tool": "find-skill", "args": {"query": "ocr"}, "result": "R2"}\n'
    )
    cases = replay_source._parse_invocation_log(log, tool_name="find-skill", limit=10)
    assert [c.inputs["query"] for c in cases] == ["pdf", "ocr"]
    assert cases[0].prior_output == "R1" and cases[0].source == "mcp-invocation-log"


def test_collect_prefers_invocation_log(tmp_path):
    inv = tmp_path / "mcp_invocations.jsonl"
    inv.write_text('{"tool": "t1", "args": {"q": "x"}, "result": "r"}\n')
    cases = replay_source.collect_replay_cases({"name": "s", "tool_name": "t1"}, invocation_log=inv, limit=5)
    assert cases and cases[0].source == "mcp-invocation-log" and cases[0].inputs == {"q": "x"}
