"""Collect real (or fallback) invocation cases for a skill, to validate edits against."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from types_opt import ReplayCase


def _parse_mcp_log(log_path, *, tool_name: str, limit: int):
    if not Path(log_path).exists():
        return []
    out = []
    for line in Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or '"tool"' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("tool") != tool_name:
            continue
        out.append(ReplayCase(inputs=dict(rec.get("args") or {}),
                              prior_output=str(rec["result"]) if rec.get("result") is not None else None,
                              source="mcp-log"))
        if len(out) >= limit:
            break
    return out


def _parse_invocation_log(log_path, *, tool_name: str, limit: int):
    """Read the structured MCP invocation log (ADR-804 mcp_invocations.jsonl) — JSON lines
    {ts, tool, args, result}, most-recent-first, returned chronologically."""
    if not Path(log_path).exists():
        return []
    out = []
    for line in reversed(Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines()):
        line = line.strip()
        if not line or '"tool"' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("tool") != tool_name or not isinstance(rec.get("args"), dict):
            continue
        out.append(ReplayCase(inputs=rec["args"],
                              prior_output=str(rec["result"]) if rec.get("result") is not None else None,
                              source="mcp-invocation-log"))
        if len(out) >= limit:
            break
    out.reverse()
    return out


def _load_curated_evals(evals_path):
    if not Path(evals_path).exists():
        return []
    try:
        data = json.loads(Path(evals_path).read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for c in (data.get("cases") or []):
        if isinstance(c, dict) and isinstance(c.get("inputs"), dict):
            out.append(ReplayCase(inputs=c["inputs"],
                                  prior_output=str(c["expected"]) if c.get("expected") is not None else None,
                                  source="curated-eval"))
    return out


def _parse_cli_log(log_path, *, command: str, limit: int):
    if not Path(log_path).exists():
        return []
    out = []
    for line in Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if command not in line:
            continue
        brace = line.find("{")
        if brace == -1:
            continue
        try:
            args = json.loads(line[brace:])
        except Exception:
            continue
        out.append(ReplayCase(inputs=dict(args), source="cli-log"))
        if len(out) >= limit:
            break
    return out


def collect_replay_cases(skill, *, limit: int = 20, invocation_log=None, mcp_log=None,
                         evals_path=None, seed_fn=None):
    """Try structured invocation log -> legacy MCP log -> CLI log -> curated evals -> seed
    evals; return the first non-empty. `skill` carries {name, tool_name?, command?}.
    Paths/seed_fn injectable for tests."""
    _logs = {}

    def logs_dir():
        if "p" not in _logs:
            from src.config.paths import get_logs_dir
            _logs["p"] = Path(get_logs_dir())
        return _logs["p"]

    if skill.get("tool_name"):
        inv = invocation_log if invocation_log is not None else (logs_dir() / "mcp_invocations.jsonl")
        cases = _parse_invocation_log(inv, tool_name=skill["tool_name"], limit=limit)
        if cases:
            return cases
        log = mcp_log if mcp_log is not None else (logs_dir() / "augur_mcp.log")
        cases = _parse_mcp_log(log, tool_name=skill["tool_name"], limit=limit)
        if cases:
            return cases
    if skill.get("command"):
        cases = _parse_cli_log(logs_dir() / "cli.log", command=skill["command"], limit=limit)
        if cases:
            return cases
    if evals_path:
        cases = _load_curated_evals(evals_path)
        if cases:
            return cases
    if seed_fn is not None:
        return [ReplayCase(inputs=c, source="seed-eval") for c in (seed_fn(skill) or [])]
    return []
