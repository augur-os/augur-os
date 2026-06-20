from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import src.scripts.agent_launch as agent_launch
from tests.scripts.test_ai_launch import git, init_main_repo_pair

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE = "src.scripts.agent_launch"


def run_agent_launch(
    *args: str,
    input_text: str = "",
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env["PYTHONPATH"] = str(PROJECT_ROOT)
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", MODULE, *args],
        cwd=PROJECT_ROOT,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        env=merged_env,
    )


def test_help_mentions_clients_and_modes() -> None:
    result = run_agent_launch("--help")

    assert result.returncode == 0
    assert "codex" in result.stdout
    assert "main" in result.stdout
    assert "new worktree" in result.stdout
    assert "desktop" in result.stdout


def test_codex_desktop_dry_run_bypasses_mode_prompt(tmp_path: Path) -> None:
    local, _ = init_main_repo_pair(tmp_path)

    result = run_agent_launch(
        "--client",
        "codex",
        "--desktop",
        "--dry-run",
        env={"AI_PROJECT_ROOT": str(local)},
    )

    assert result.returncode == 0, result.stderr
    assert "mode=desktop" in result.stdout
    assert f"repo={local}" in result.stdout
    assert f"command=codex app {local}" in result.stdout


def test_invalid_choice_reprompts_until_valid_worktree_selection() -> None:
    result = run_agent_launch("--client", "codex", "--dry-run", input_text="bad\n2\n")

    assert result.returncode == 0, result.stderr
    assert "Invalid choice" in result.stdout
    assert "mode=worktree" in result.stdout
    assert "codex --dangerously-bypass-approvals-and-sandbox" in result.stdout


def test_extra_args_after_separator_are_forwarded() -> None:
    result = run_agent_launch(
        "--client",
        "codex",
        "--dry-run",
        "--",
        "--resume",
        "abc123",
        input_text="1\n",
    )

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert "codex --dangerously-bypass-approvals-and-sandbox --resume abc123" in result.stdout


def test_client_flags_without_separator_are_forwarded() -> None:
    result = run_agent_launch(
        "--client",
        "codex",
        "--dry-run",
        "--version",
        input_text="1\n",
    )

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert "codex --dangerously-bypass-approvals-and-sandbox --version" in result.stdout


def test_choose_main_selects_main_without_prompt_or_forwarding_words() -> None:
    result = run_agent_launch("--client", "codex", "--dry-run", "choose", "main")

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert "command=codex --dangerously-bypass-approvals-and-sandbox\n" in result.stdout
    assert "choose main" not in result.stdout


def test_main_mode_fast_forwards_and_restores_dirty_changes(tmp_path: Path) -> None:
    local, upstream = init_main_repo_pair(tmp_path)
    (upstream / "remote.txt").write_text("remote change\n", encoding="utf-8")
    git(upstream, "add", "remote.txt")
    git(upstream, "commit", "-m", "remote change")
    git(upstream, "push", "origin", "main")

    (local / "tracked.txt").write_text("base\nlocal dirty\n", encoding="utf-8")
    (local / "untracked.txt").write_text("keep me\n", encoding="utf-8")

    result = run_agent_launch(
        "--client",
        "codex",
        input_text="1\n",
        env={"AI_PROJECT_ROOT": str(local), "AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert git(local, "rev-parse", "HEAD") == git(local, "rev-parse", "origin/main")
    assert "local dirty" in (local / "tracked.txt").read_text(encoding="utf-8")
    assert (local / "untracked.txt").read_text(encoding="utf-8") == "keep me\n"
    assert (local / "remote.txt").read_text(encoding="utf-8") == "remote change\n"


def test_main_mode_prompts_before_syncing_local_main_that_is_ahead(tmp_path: Path) -> None:
    local, _ = init_main_repo_pair(tmp_path)
    (local / "local-only.txt").write_text("ahead\n", encoding="utf-8")
    git(local, "add", "local-only.txt")
    git(local, "commit", "-m", "ahead")

    result = run_agent_launch(
        "--client",
        "codex",
        input_text="1\nn\n",
        env={"AI_PROJECT_ROOT": str(local), "AI_NO_EXEC": "1"},
    )

    assert result.returncode != 0
    assert "Run safe sync now" in result.stdout
    assert "safe sync declined" in result.stderr


def test_main_mode_safe_syncs_diverged_main_and_preserves_dirty_changes(tmp_path: Path) -> None:
    local, upstream = init_main_repo_pair(tmp_path)

    (local / "local-only.txt").write_text("ahead\n", encoding="utf-8")
    git(local, "add", "local-only.txt")
    git(local, "commit", "-m", "ahead")

    (upstream / "remote.txt").write_text("remote change\n", encoding="utf-8")
    git(upstream, "add", "remote.txt")
    git(upstream, "commit", "-m", "remote change")
    git(upstream, "push", "origin", "main")

    (local / "tracked.txt").write_text("base\nlocal dirty\n", encoding="utf-8")
    git(local, "add", "tracked.txt")
    (local / "untracked.txt").write_text("keep me\n", encoding="utf-8")

    result = run_agent_launch(
        "--client",
        "codex",
        input_text="1\ny\n",
        env={"AI_PROJECT_ROOT": str(local), "AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "Run safe sync now" in result.stdout
    assert git(local, "rev-parse", "HEAD") == git(local, "rev-parse", "origin/main")
    assert (local / "local-only.txt").read_text(encoding="utf-8") == "ahead\n"
    assert (local / "remote.txt").read_text(encoding="utf-8") == "remote change\n"
    assert "local dirty" in (local / "tracked.txt").read_text(encoding="utf-8")
    assert (local / "untracked.txt").read_text(encoding="utf-8") == "keep me\n"
    assert "M  tracked.txt" in git(local, "status", "--short")
    assert len(git(local, "show", "-s", "--pretty=%P").split()) == 1


def test_main_mode_safe_sync_avoids_merge_commit_hooks_when_main_diverged(tmp_path: Path) -> None:
    local, upstream = init_main_repo_pair(tmp_path)

    (local / "local-only.txt").write_text("ahead\n", encoding="utf-8")
    git(local, "add", "local-only.txt")
    git(local, "commit", "-m", "ahead")

    hooks = local / ".git" / "hooks"
    hook = hooks / "commit-msg"
    hook.write_text(
        "#!/bin/sh\n"
        "if grep -q '^Merge' \"$1\"; then\n"
        "  echo 'merge commit blocked by test hook' >&2\n"
        "  exit 1\n"
        "fi\n",
        encoding="utf-8",
    )

    (upstream / "remote.txt").write_text("remote change\n", encoding="utf-8")
    git(upstream, "add", "remote.txt")
    git(upstream, "commit", "-m", "remote change")
    git(upstream, "push", "origin", "main")

    result = run_agent_launch(
        "--client",
        "codex",
        input_text="1\ny\n",
        env={"AI_PROJECT_ROOT": str(local), "AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert git(local, "rev-parse", "HEAD") == git(local, "rev-parse", "origin/main")
    assert len(git(local, "show", "-s", "--pretty=%P").split()) == 1


def test_main_mode_refuses_dirty_non_main_branch_without_moving_changes(tmp_path: Path) -> None:
    local, _ = init_main_repo_pair(tmp_path)
    git(local, "checkout", "-b", "feature")
    (local / "tracked.txt").write_text("base\nfeature dirty\n", encoding="utf-8")
    (local / "feature-untracked.txt").write_text("keep on feature\n", encoding="utf-8")

    result = run_agent_launch(
        "--client",
        "codex",
        input_text="1\n",
        env={"AI_PROJECT_ROOT": str(local), "AI_NO_EXEC": "1"},
    )

    assert result.returncode != 0
    assert "clean working tree before switching to main" in result.stderr
    assert git(local, "rev-parse", "--abbrev-ref", "HEAD") == "feature"
    assert "feature dirty" in (local / "tracked.txt").read_text(encoding="utf-8")
    assert (local / "feature-untracked.txt").read_text(encoding="utf-8") == "keep on feature\n"


def test_missing_client_executable_names_client(monkeypatch, capsys) -> None:
    monkeypatch.setattr(agent_launch, "prompt_mode", lambda client: "main")
    monkeypatch.setattr(agent_launch, "sync_main_checkout", lambda repo: None)

    def fake_exec_client(command, env=None):
        raise RuntimeError(f"AI client executable not found: {command[0]}")

    monkeypatch.setattr(agent_launch, "exec_client", fake_exec_client)

    result = agent_launch.main(["--client", "codex"])

    captured = capsys.readouterr()
    assert result == 1
    assert "codex" in captured.err


def test_exec_client_waits_for_windows_npm_shim(monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, str] | None]] = []

    monkeypatch.setattr("src.scripts._launch_session._is_windows", lambda: True)
    monkeypatch.setattr(agent_launch, "_reset_windows_terminal_input_modes", lambda: None)
    monkeypatch.setattr(
        agent_launch.shutil,
        "which",
        lambda command, path=None: f"C:\\Users\\intel\\AppData\\Roaming\\npm\\{command}.CMD",
    )

    def fake_run(command, *, env=None, check=False):
        calls.append((command, env))
        assert check is False
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(agent_launch.subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as exit_info:
        agent_launch.exec_client(["claude", "--dangerously-skip-permissions"], {"PATH": "shim-path"})

    assert exit_info.value.code == 7
    assert calls == [
        (
            [
                "C:\\Users\\intel\\AppData\\Roaming\\npm\\claude.CMD",
                "--dangerously-skip-permissions",
            ],
            {"PATH": "shim-path"},
        )
    ]


def test_exec_client_reports_missing_windows_client(monkeypatch) -> None:
    monkeypatch.setattr("src.scripts._launch_session._is_windows", lambda: True)
    monkeypatch.setattr(agent_launch.shutil, "which", lambda command, path=None: None)

    with pytest.raises(RuntimeError) as exc_info:
        agent_launch.exec_client(["missing-client"])

    assert "missing-client" in str(exc_info.value)


def test_run_handoff_client_claims_and_releases_child_pid(monkeypatch, tmp_path: Path) -> None:
    events: list[object] = []

    class FakeProcess:
        pid = 4242

        def wait(self) -> int:
            events.append("wait")
            return 7

    def fake_popen(command, *, cwd=None, env=None):
        events.append(("popen", command, cwd, env))
        return FakeProcess()

    def fake_claim(session_id: str, pid: int, cli_id: str) -> None:
        events.append(("claim", session_id, pid, cli_id))

    def fake_release(session_id: str, pid: int) -> None:
        events.append(("release", session_id, pid))

    monkeypatch.setattr(agent_launch.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(agent_launch, "claim_native_terminal_session", fake_claim)
    monkeypatch.setattr(agent_launch, "release_native_terminal_session", fake_release)
    monkeypatch.setattr(
        agent_launch.shutil,
        "which",
        lambda command, path=None: f"C:\\Users\\intel\\AppData\\Roaming\\npm\\{command}.CMD",
    )

    result = agent_launch.run_handoff_client(
        ["codex", "resume", "session-123"],
        cwd=tmp_path,
        session_id="session-123",
        cli_id="codex",
        env={"PATH": "shim-path"},
    )

    assert result == 7
    expected_exe = "C:\\Users\\intel\\AppData\\Roaming\\npm\\codex.CMD" if os.name == "nt" else "codex"
    assert events == [
        ("popen", [expected_exe, "resume", "session-123"], tmp_path, {"PATH": "shim-path"}),
        ("claim", "session-123", 4242, "codex"),
        "wait",
        ("release", "session-123", 4242),
    ]


def test_run_handoff_client_releases_child_pid_when_wait_fails(monkeypatch, tmp_path: Path) -> None:
    events: list[object] = []

    class FakeProcess:
        pid = 5151

        def wait(self) -> int:
            events.append("wait")
            raise RuntimeError("client wait failed")

    def fake_popen(command, *, cwd=None, env=None):
        return FakeProcess()

    def fake_claim(session_id: str, pid: int, cli_id: str) -> None:
        events.append(("claim", session_id, pid, cli_id))

    def fake_release(session_id: str, pid: int) -> None:
        events.append(("release", session_id, pid))

    monkeypatch.setattr(agent_launch.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(agent_launch, "claim_native_terminal_session", fake_claim)
    monkeypatch.setattr(agent_launch, "release_native_terminal_session", fake_release)
    monkeypatch.setattr(
        agent_launch.shutil,
        "which",
        lambda command, path=None: f"C:\\Users\\intel\\AppData\\Roaming\\npm\\{command}.CMD",
    )

    with pytest.raises(RuntimeError, match="client wait failed"):
        agent_launch.run_handoff_client(
            ["codex", "resume", "session-123"],
            cwd=tmp_path,
            session_id="session-123",
            cli_id="codex",
        )

    assert events == [
        ("claim", "session-123", 5151, "codex"),
        "wait",
        ("release", "session-123", 5151),
    ]


def test_session_owner_watchdog_terminates_child_when_claim_is_released(monkeypatch) -> None:
    events: list[str] = []

    class FakeProcess:
        pid = 6161

        def terminate(self) -> None:
            events.append("terminate")

        def wait(self, timeout: int | None = None) -> int:
            events.append(f"wait:{timeout}")
            return 0

        def kill(self) -> None:
            events.append("kill")

    monkeypatch.setattr(
        agent_launch,
        "_native_terminal_owner_is_current",
        lambda session_id, pid: False,
    )
    monkeypatch.setattr(agent_launch, "SESSION_OWNER_WATCHDOG_INTERVAL_SECONDS", 0.001)

    stop_event = agent_launch._start_session_owner_watchdog(
        FakeProcess(),
        session_id="session-123",
        pid=6161,
    )
    try:
        deadline = time.monotonic() + 1
        while "terminate" not in events and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        stop_event.set()

    assert events[:2] == ["terminate", "wait:5"]


def write_handoff_payload(tmp_path: Path, **overrides: object) -> Path:
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "version": 1,
        "created_at": created_at,
        "cli_id": "codex",
        "shortcut": "xa",
        "session_id": "session-123",
        "cwd": str(tmp_path),
        "current_page": "/workspace/inbox",
        "dashboard_mode": "operation",
        "theme_mode": "dark",
        "route": {"airplane_mode": False, "local_model": None},
    }
    payload.update(overrides)
    path = tmp_path / "handoff.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_handoff_file_builds_codex_resume_command(tmp_path: Path) -> None:
    payload = write_handoff_payload(tmp_path)

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert f"mode=handoff repo={tmp_path}" in result.stdout
    assert "codex resume session-123 --dangerously-bypass-approvals-and-sandbox" in result.stdout


def test_handoff_file_runs_handoff_client_with_payload_session(monkeypatch, tmp_path: Path) -> None:
    payload = write_handoff_payload(tmp_path)
    calls: list[dict[str, object]] = []

    def fake_run_handoff_client(
        command: list[str],
        *,
        cwd: Path,
        session_id: str,
        cli_id: str,
        env: dict[str, str] | None = None,
    ) -> int:
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "session_id": session_id,
                "cli_id": cli_id,
                "env": env,
            }
        )
        return 23

    monkeypatch.setattr(agent_launch, "run_handoff_client", fake_run_handoff_client)

    result = agent_launch.main(["--client", "codex", "--handoff-file", str(payload)])

    assert result == 23
    assert calls == [
        {
            "command": ["codex", "resume", "session-123", "--dangerously-bypass-approvals-and-sandbox"],
            "cwd": tmp_path,
            "session_id": "session-123",
            "cli_id": "codex",
            "env": None,
        }
    ]


def test_handoff_file_passes_handoff_prompt_to_resumed_client(tmp_path: Path) -> None:
    payload = write_handoff_payload(
        tmp_path,
        handoff_prompt="Exited dashboard chat. Continue in Terminal.",
    )

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert (
        "codex resume session-123 --dangerously-bypass-approvals-and-sandbox "
        "Exited dashboard chat. Continue in Terminal."
    ) in result.stdout


def test_handoff_file_builds_codex_latest_resume_command(tmp_path: Path) -> None:
    payload = write_handoff_payload(tmp_path, session_id="__codex_latest__")

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert f"mode=handoff repo={tmp_path}" in result.stdout
    assert "codex resume --last --dangerously-bypass-approvals-and-sandbox" in result.stdout


def test_handoff_file_rejects_client_mismatch(tmp_path: Path) -> None:
    payload = write_handoff_payload(tmp_path, cli_id="gemini", shortcut="ga")

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode != 0
    assert "handoff payload cli_id gemini does not match requested client codex" in result.stderr


def test_handoff_file_uses_airplane_launch_argv_and_strips_auto_flags(tmp_path: Path) -> None:
    payload = write_handoff_payload(
        tmp_path,
        handoff_prompt="Exited dashboard chat. Continue in Terminal.",
        route={
            "airplane_mode": True,
            "local_model": "qwen3:4b",
            "launch_argv": [
                "/opt/homebrew/bin/ollama",
                "launch",
                "codex",
                "--model",
                "qwen3:4b",
                "--",
            ],
        },
    )

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "/opt/homebrew/bin/ollama launch codex --model qwen3:4b -- resume session-123" in result.stdout
    assert "Exited dashboard chat. Continue in Terminal." in result.stdout
    assert "--dangerously-bypass-approvals-and-sandbox" not in result.stdout


def test_handoff_file_rejects_missing_session_id(tmp_path: Path) -> None:
    payload = write_handoff_payload(tmp_path, session_id="")

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode != 0
    assert "handoff payload session_id must be a non-empty string" in result.stderr


def test_handoff_file_rejects_missing_airplane_mode(tmp_path: Path) -> None:
    payload = write_handoff_payload(tmp_path, route={"local_model": None})

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode != 0
    assert "handoff payload route.airplane_mode must be a boolean" in result.stderr


def test_handoff_file_rejects_string_airplane_mode(tmp_path: Path) -> None:
    payload = write_handoff_payload(tmp_path, route={"airplane_mode": "true", "local_model": "qwen3:4b"})

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode != 0
    assert "handoff payload route.airplane_mode must be a boolean" in result.stderr


def test_handoff_file_rejects_future_created_at(tmp_path: Path) -> None:
    created_at = datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    payload = write_handoff_payload(tmp_path, created_at=created_at)

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode != 0
    assert "handoff payload created_at is outside the allowed time window" in result.stderr


def test_handoff_file_rejects_malformed_json(tmp_path: Path) -> None:
    payload = tmp_path / "handoff.json"
    payload.write_text("{not-json", encoding="utf-8")

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode != 0
    assert "handoff payload must be valid JSON" in result.stderr


def test_handoff_file_rejects_empty_current_page(tmp_path: Path) -> None:
    payload = write_handoff_payload(tmp_path, current_page="")

    result = run_agent_launch(
        "--client",
        "codex",
        "--handoff-file",
        str(payload),
        env={"AI_NO_EXEC": "1"},
    )

    assert result.returncode != 0
    assert "handoff payload current_page must be a non-empty string" in result.stderr


def test_create_worktree_writes_to_last_worktree_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_launch, "derive_worktree_name", lambda: "test-wt")
    monkeypatch.setattr(agent_launch, "resolve_base_ref", lambda repo: "main")
    monkeypatch.setattr(agent_launch, "run_git", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_launch, "register_worktree", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_launch, "bootstrap_worktree", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_launch, "generate_mcp_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_launch.os, "chdir", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_launch, "exec_client", lambda *args, **kwargs: None)

    last_wt_file = tmp_path / "last_wt_file.txt"
    monkeypatch.setenv("AUGUR_LAST_WORKTREE_FILE", str(last_wt_file))

    repo = tmp_path / "repo"
    repo.mkdir()

    agent_launch.create_worktree(repo, ["codex"])

    assert last_wt_file.exists()
    content = last_wt_file.read_text(encoding="utf-8")
    assert content == str(tmp_path / "augur-test-wt")


def test_help_mentions_copilot_client() -> None:
    result = run_agent_launch("--help")

    assert result.returncode == 0
    assert "copilot" in result.stdout


def test_copilot_choose_main_uses_allow_all() -> None:
    result = run_agent_launch("--client", "copilot", "--dry-run", "choose", "main")

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert "command=copilot --allow-all\n" in result.stdout


def test_copilot_resume_command_appends_resume_flag() -> None:
    command = agent_launch.resume_command_for("copilot", "sess-123")

    assert command == ["copilot", "--allow-all", "--resume", "sess-123"]


def test_copilot_shortcut_is_gca() -> None:
    assert agent_launch.SHORTCUTS["copilot"] == "gca"


def test_with_copilot_project_mcp_injects_when_config_exists(tmp_path: Path) -> None:
    (tmp_path / ".mcp.json").write_text("{}")
    command = agent_launch.with_copilot_project_mcp(["copilot", "--allow-all"], tmp_path)
    assert command == ["copilot", "--additional-mcp-config", "@.mcp.json", "--allow-all"]


def test_with_copilot_project_mcp_skips_when_config_missing(tmp_path: Path) -> None:
    command = agent_launch.with_copilot_project_mcp(["copilot", "--allow-all"], tmp_path)
    assert command == ["copilot", "--allow-all"]


def test_with_copilot_project_mcp_ignores_other_clients(tmp_path: Path) -> None:
    (tmp_path / ".mcp.json").write_text("{}")
    command = agent_launch.with_copilot_project_mcp(["claude", "--dangerously-skip-permissions"], tmp_path)
    assert command == ["claude", "--dangerously-skip-permissions"]


def test_with_copilot_project_mcp_respects_explicit_flag(tmp_path: Path) -> None:
    (tmp_path / ".mcp.json").write_text("{}")
    command = agent_launch.with_copilot_project_mcp(["copilot", "--additional-mcp-config", "@custom.json"], tmp_path)
    assert command == ["copilot", "--additional-mcp-config", "@custom.json"]


def test_separator_after_choose_words_is_not_forwarded() -> None:
    result = run_agent_launch("--client", "codex", "--dry-run", "choose", "main", "--", "--resume", "abc123")

    assert result.returncode == 0, result.stderr
    assert "command=codex --dangerously-bypass-approvals-and-sandbox --resume abc123\n" in result.stdout
    assert " -- " not in result.stdout


def test_copilot_prompt_after_choose_and_separator_is_forwarded_clean() -> None:
    result = run_agent_launch("--client", "copilot", "--dry-run", "choose", "main", "--", "-p", "hello world")

    assert result.returncode == 0, result.stderr
    assert "command=copilot --allow-all -p hello world\n" in result.stdout
    assert " -- " not in result.stdout
