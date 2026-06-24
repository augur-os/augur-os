"""CLI contract tests for the ADR-755 routine orchestrator surface."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
SCRIPTS_DIR = DAEMON_DIR / "scripts"
MCP_INIT = SCRIPTS_DIR / "mcp" / "__init__.py"


def _load_mcp_module():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    module_name = "daemon_mcp_routine_cli_tests"
    spec = importlib.util.spec_from_file_location(module_name, MCP_INIT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _parser_for(module):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    module.register_subcommands(subparsers)
    return parser


def test_aug_routine_verbs_parse() -> None:
    module = _load_mcp_module()
    parser = _parser_for(module)

    scan_args = parser.parse_args(["a-loops", "scan-only", "--loop", "testing"])
    assert scan_args.cmd == "a-loops"
    assert scan_args.routine_verb == "scan-only"
    assert scan_args.loop == "testing"

    orchestrate_args = parser.parse_args(["a-loops", "orchestrate", "--loop", "hardening"])
    assert orchestrate_args.cmd == "a-loops"
    assert orchestrate_args.routine_verb == "orchestrate"
    assert orchestrate_args.loop == "hardening"

    pending_args = parser.parse_args(["a-loops", "pending-escalations", "--show"])
    assert pending_args.cmd == "a-loops"
    assert pending_args.routine_verb == "pending-escalations"
    assert pending_args.show is True


def test_aug_routine_scan_only_invokes_orchestrator_scan_only(monkeypatch, capsys) -> None:
    module = _load_mcp_module()
    calls: list[str] = []

    def scan_only(loop_name: str):
        calls.append(loop_name)
        return SimpleNamespace(
            loop_name=loop_name,
            counts={"findings": 1},
            findings=[{"kind": "fixture", "auto_command": "auto-fixture"}],
            mechanical_applied=[],
            mechanical_failed=[],
            deferred=[],
            design_gate_findings=[],
            dispatched=[],
            enqueued=[],
            events=[{"phase": "scan"}],
        )

    monkeypatch.setattr(
        module,
        "_load_routine_orchestrator",
        lambda: SimpleNamespace(scan_only=scan_only),
    )

    parser = _parser_for(module)
    args = parser.parse_args(["a-loops", "scan-only", "--loop", "testing"])
    exit_code = args.func(args, [])

    assert exit_code == 0
    assert calls == ["testing"]
    payload = json.loads(capsys.readouterr().out)
    assert payload["loop_name"] == "testing"
    assert payload["counts"] == {"findings": 1}
    assert payload["findings"][0]["auto_command"] == "auto-fixture"


def test_aug_routine_orchestrate_refuses_without_session(monkeypatch, capsys) -> None:
    module = _load_mcp_module()
    monkeypatch.setattr(module, "_detect_routine_session", lambda: SimpleNamespace())
    monkeypatch.setattr(module, "_routine_session_surface", lambda _session: None)

    parser = _parser_for(module)
    args = parser.parse_args(["a-loops", "orchestrate", "--loop", "testing"])
    exit_code = args.func(args, [])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "no session detected"
    assert "scan-only" in payload["detail"]


def test_aug_routine_no_verb_prints_help_with_exit_code_2(capsys) -> None:
    module = _load_mcp_module()
    parser = _parser_for(module)
    args = parser.parse_args(["a-loops"])

    exit_code = args.func(args, [])

    assert exit_code == 2
    out = capsys.readouterr().out
    assert "scan-only" in out
    assert "orchestrate" in out
    assert "pending-escalations" in out


def test_aug_routine_pending_escalations_show_does_not_clear_stale(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_mcp_module()
    runtime_root = tmp_path / "state"
    queue_path = runtime_root / "jobs" / "_escalations" / "pending.jsonl"
    queue_path.parent.mkdir(parents=True)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    fresh = {
        "id": "fresh",
        "finding": {"auto_command": "auto-semantic"},
        "expires_at": (now + timedelta(days=1)).isoformat(),
    }
    stale = {
        "id": "stale",
        "finding": {"auto_command": "auto-old"},
        "expires_at": (now - timedelta(days=1)).isoformat(),
    }
    queue_path.write_text(
        "\n".join(json.dumps(entry) for entry in (fresh, stale)) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "_resolve_runtime_root", lambda: runtime_root)
    parser = _parser_for(module)

    args = parser.parse_args(["a-loops", "pending-escalations", "--show"])
    assert args.func(args, []) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["pending"] == 1
    assert payload["stale"] == 1
    assert payload["entries"][0]["id"] == "fresh"
    assert len(queue_path.read_text(encoding="utf-8").splitlines()) == 2

    args = parser.parse_args(["a-loops", "pending-escalations", "--clear-stale"])
    assert args.func(args, []) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["pending"] == 1
    assert payload["cleared"] == 1
    assert json.loads(queue_path.read_text(encoding="utf-8").strip())["id"] == "fresh"
