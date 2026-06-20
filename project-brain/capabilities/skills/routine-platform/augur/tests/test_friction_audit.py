"""Tests for auto-friction-audit (session-friction scan-fix routine)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "friction_audit.py"
_SPEC = importlib.util.spec_from_file_location("friction_audit_under_test", str(_MODULE_PATH))
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
# Register under the namespaced name before exec so module-level @dataclass can
# resolve cls.__module__ (and to avoid global sys.modules collisions).
sys.modules["friction_audit_under_test"] = mod
_SPEC.loader.exec_module(mod)


def _write_transcript(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "session-abc.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    return path


def _tool_result(text: str, *, is_error: bool | None = None) -> dict:
    block: dict = {"type": "tool_result", "content": text}
    if is_error is not None:
        block["is_error"] = is_error
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def _tool_use(name: str, tool_input: dict, *, tid: str = "t1") -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": tid, "name": name, "input": tool_input}],
        },
    }


# --- contract --------------------------------------------------------------


def test_module_metadata() -> None:
    assert mod.name == "auto-friction-audit"
    assert isinstance(mod.DIFFICULTY_SPEC, dict)
    assert callable(mod.scan) and callable(mod.fix)


# --- detectors -------------------------------------------------------------


def test_detect_cli_tool_unreachable(tmp_path: Path) -> None:
    path = _write_transcript(tmp_path, [_tool_result("Error: Unknown tool 'note-url'\nUse --list-tools")])
    findings: dict = {}
    mod._scan_transcript(path, findings)
    assert ("cli-tool-unreachable", "note-url") in findings


def test_detect_cli_tool_unreachable_ignores_is_error_flag(tmp_path: Path) -> None:
    # aug failures arrive via piped Bash output where is_error is often False.
    path = _write_transcript(tmp_path, [_tool_result("Error: Unknown tool 'wiki'", is_error=False)])
    findings: dict = {}
    mod._scan_transcript(path, findings)
    assert ("cli-tool-unreachable", "wiki") in findings


def test_detect_deferred_tool_miss(tmp_path: Path) -> None:
    path = _write_transcript(tmp_path, [_tool_result("No matching deferred tools found")])
    findings: dict = {}
    mod._scan_transcript(path, findings)
    assert ("tool-discovery-miss", "deferred-tool-search") in findings


def test_rule34_detected_in_user_string_message(tmp_path: Path) -> None:
    entry = {
        "type": "user",
        "message": {"role": "user", "content": "Stop hook feedback:\nValue-validation check (agent-rules rule 34): ..."},
    }
    path = _write_transcript(tmp_path, [entry])
    findings: dict = {}
    mod._scan_transcript(path, findings)
    assert ("hook-friction", "rule-34-value-validation") in findings


def test_rule34_not_false_positive_on_file_read(tmp_path: Path) -> None:
    # Reading run-hook.mjs surfaces the reason string in a tool_result; that is
    # NOT a hook fire and must not be flagged.
    path = _write_transcript(tmp_path, [_tool_result("123  reason: 'Value-validation check (agent-rules rule 34)'")])
    findings: dict = {}
    mod._scan_transcript(path, findings)
    assert ("hook-friction", "rule-34-value-validation") not in findings


def test_rule29_requires_is_error(tmp_path: Path) -> None:
    fire = _write_transcript(tmp_path, [_tool_result("Blocked by rule 29: use /dev-build", is_error=True)])
    read = tmp_path / "read.jsonl"
    read.write_text(json.dumps(_tool_result("DASHBOARD_SHORTCUT_REASON = 'Blocked by rule 29: ...'", is_error=False)), encoding="utf-8")

    fired: dict = {}
    mod._scan_transcript(fire, fired)
    assert ("hook-friction", "rule-29-dashboard-shortcut") in fired

    not_fired: dict = {}
    mod._scan_transcript(read, not_fired)
    assert ("hook-friction", "rule-29-dashboard-shortcut") not in not_fired


def test_detect_adhoc_repo_root_script(tmp_path: Path) -> None:
    path = _write_transcript(tmp_path, [_tool_use("Write", {"file_path": ".augur_note_url.py", "content": "x"})])
    findings: dict = {}
    mod._scan_transcript(path, findings)
    assert ("adhoc-script-workaround", ".augur_note_url.py") in findings


def test_deep_path_script_not_flagged(tmp_path: Path) -> None:
    # A real source file under src/ must not be mistaken for an ad-hoc workaround.
    path = _write_transcript(tmp_path, [_tool_use("Write", {"file_path": "/repo/src/mcp/augur_framework/foo.py", "content": "x"})])
    findings: dict = {}
    mod._scan_transcript(path, findings)
    assert not any(k == "adhoc-script-workaround" for k, _ in findings)


def test_repeated_bash_failure(tmp_path: Path) -> None:
    entries = [
        _tool_use("Bash", {"command": "git push"}, tid="b1"),
        _tool_result("error", is_error=True) | {},
    ]
    # tie the tool_result to the tool_use id
    entries[1]["message"]["content"][0]["tool_use_id"] = "b1"
    entries += [
        _tool_use("Bash", {"command": "git push"}, tid="b2"),
        _tool_result("error", is_error=True),
    ]
    entries[3]["message"]["content"][0]["tool_use_id"] = "b2"
    path = _write_transcript(tmp_path, entries)
    findings: dict = {}
    mod._detect_repeated_bash_failures(path, findings)
    assert ("repeated-command-failure", "git push") in findings


# --- helpers / scan / fix --------------------------------------------------


def test_clip_strips_ansi() -> None:
    assert "\x1b" not in mod._clip("\x1b[32mINFO\x1b[0m hello world")
    assert "INFO hello world" in mod._clip("\x1b[32mINFO\x1b[0m hello world")


def test_scan_no_transcripts(tmp_path: Path) -> None:
    # tmp_path has no Claude transcript dir → graceful empty result.
    result = mod.scan(OpsContext(project_root=tmp_path))
    assert isinstance(result, ScanResult)
    assert result.items_scanned == 0
    assert result.issues == []


def test_fix_dry_run_writes_nothing(tmp_path: Path) -> None:
    ctx = OpsContext(project_root=tmp_path, dry_run=True)
    issue = {
        "kind": "cli-tool-unreachable",
        "signature": "note-url",
        "label": "x",
        "severity": "error",
        "remedy": "y",
        "remedy_auto": False,
        "sessions": ["s1"],
        "session_count": 1,
        "occurrences": 1,
        "evidence": "e",
    }
    result = mod.fix(ctx, [issue])
    assert isinstance(result, FixResult)
    assert result.success
    assert "Dry run" in result.summary


def test_fix_empty_issues() -> None:
    result = mod.fix(OpsContext(project_root=Path.cwd()), [])
    assert result.success
    assert result.fix_type == "report"
