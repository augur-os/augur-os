"""Tests for push_local_impl."""
from __future__ import annotations

import json
import subprocess


def test_push_codex_overwrites_drifted_toml_with_seed_values(tmp_path, monkeypatch) -> None:
    from src.lib.runtime.codex_automations import sync_codex_automations
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        push_local_impl,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    schedules = [
        {
            "id": "codex-dev-loop-testing",
            "title": "Testing",
            "rrule": "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0",
            "prompt": "/dev-loops run testing",
            "workspace": str(tmp_path),
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "runs_in": "local",
        }
    ]
    sync_codex_automations(schedules, apply=True, prune=False)
    toml_path = tmp_path / ".codex" / "automations" / "codex-dev-loop-testing" / "automation.toml"
    body = toml_path.read_text(encoding="utf-8")
    body = body.replace(
        'rrule = "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"',
        'rrule = "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"',
    )
    toml_path.write_text(body, encoding="utf-8")

    result = push_local_impl(
        routine_id="codex:codex-dev-loop-testing",
        desired_schedules=schedules,
    )

    payload = json.loads(result)
    assert payload["success"] is True
    final = toml_path.read_text(encoding="utf-8")
    assert 'rrule = "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"' in final
    assert "BYDAY=WE" not in final


def test_push_codex_unknown_id_returns_error(tmp_path, monkeypatch) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        push_local_impl,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    result = push_local_impl(
        routine_id="codex:does-not-exist",
        desired_schedules=[],
    )
    payload = json.loads(result)
    assert payload["success"] is False
    assert "not in desired" in payload["error"].lower() or "not found" in payload["error"].lower()


def test_push_claude_remote_spawns_claude_print_with_update_prompt(tmp_path, monkeypatch) -> None:
    """When subprocess succeeds, the impl reports success and echoes the trigger id."""
    import json as _json
    from src.mcp.augur_framework.tools.infrastructure.browse import scheduled_conflict
    from src.config import paths as _paths

    # Redirect get_cache_dir to tmp_path so the test never touches the
    # user's real ~/Library/Caches/Augur/claude-remote-routines.json.
    monkeypatch.setattr(_paths, "get_cache_dir", lambda: tmp_path)
    cache_dir = tmp_path
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "claude-remote-routines.json"
    cache_path.write_text(
        _json.dumps(
            {
                "fetched_at": "2026-05-17T22:00:00Z",
                "routines": [
                    {
                        "id": "trig_abc123",
                        "name": "Augur Dream",
                        "cron_expression": "0 1 * * *",
                        "enabled": True,
                        "prompt_summary": "/a-loops run dream",
                        "model": "claude-sonnet-4-6",
                        "repo": "https://github.com/gsannikov/augur",
                        "last_run_at": None,
                        "next_run_at": "2026-05-18T01:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    class _StubResult:
        returncode = 0
        stdout = "OK"
        stderr = ""

    def _fake_run(cmd, capture_output, timeout, text, check, stdin=None, env=None):
        captured["cmd"] = cmd
        captured["stdin"] = stdin
        captured["env"] = env
        return _StubResult()

    monkeypatch.setattr(scheduled_conflict.subprocess, "run", _fake_run)
    monkeypatch.setattr(scheduled_conflict.shutil, "which", lambda _: "/usr/local/bin/claude")

    result = scheduled_conflict.push_local_impl(routine_id="claude-remote:trig_abc123")
    payload = _json.loads(result)

    assert payload["success"] is True
    assert "trig_abc123" in payload["message"]
    assert captured["stdin"] is subprocess.DEVNULL
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"
    cmd = captured["cmd"]
    assert cmd[0] == "/usr/local/bin/claude"
    assert "--print" in cmd
    prompt = cmd[-1]
    assert "trig_abc123" in prompt
    assert "RemoteTrigger" in prompt
    assert "update" in prompt
