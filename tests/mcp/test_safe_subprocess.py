"""Unit tests for the bridge-safe subprocess wrapper (``safe_run``).

``safe_run`` injects two safety defaults without overriding explicit caller
intent:

  - ``stdin=DEVNULL`` so a child never inherits the MCP stdio bridge's
    JSON-RPC pipe (the real hang fix), and
  - ``GIT_TERMINAL_PROMPT=0`` so git never blocks on an interactive prompt.

Because every injected value uses ``setdefault``, explicit caller values must
always win. These tests assert the default injection, the setdefault semantics
(including the subtle case where an explicit ``None`` is preserved), that the
caller's ``env`` dict and the process ``os.environ`` are never mutated, that a
timeout is never forced, and that all other args/kwargs pass through untouched.
A final group runs a real harmless ``python -c`` child to prove the stdin and
env safety behavior end to end (no dangerous commands).

Run with: pytest tests/mcp/test_safe_subprocess.py -v
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Project root on path so ``src.mcp.augur_shared.*`` resolves like production.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.mcp.augur_shared.safe_subprocess import safe_run  # noqa: E402


@pytest.fixture
def mock_run():
    """Patch ``subprocess.run`` and yield the mock.

    ``safe_run`` calls ``subprocess.run`` via attribute access (never a captured
    reference), so patching the module attribute intercepts the call. The mock
    returns a sentinel so passthrough of the return value can be asserted.
    """
    with patch("subprocess.run") as m:
        m.return_value = MagicMock(name="completed_process")
        yield m


def _kwargs_of(mock) -> dict:
    """Keyword args of the single recorded ``subprocess.run`` call."""
    assert mock.call_count == 1, f"expected one call, saw {mock.call_count}"
    return mock.call_args.kwargs


# =============================================================================
# stdin: the core hang fix
# =============================================================================


class TestStdin:
    def test_defaults_stdin_to_devnull(self, mock_run):
        safe_run(["echo", "hi"])
        assert _kwargs_of(mock_run)["stdin"] is subprocess.DEVNULL

    def test_explicit_stdin_preserved(self, mock_run):
        sentinel = object()
        safe_run(["echo", "hi"], stdin=sentinel)
        assert _kwargs_of(mock_run)["stdin"] is sentinel

    def test_explicit_stdin_none_is_preserved_not_overridden(self, mock_run):
        # setdefault only fills *absent* keys: an explicit None means the caller
        # deliberately wants inherited stdin and must not be silently rewritten
        # to DEVNULL.
        safe_run(["echo", "hi"], stdin=None)
        assert _kwargs_of(mock_run)["stdin"] is None


# =============================================================================
# env: GIT_TERMINAL_PROMPT injection without mutation
# =============================================================================


class TestEnv:
    def test_injects_git_terminal_prompt_when_no_env(self, mock_run):
        safe_run(["git", "status"])
        env = _kwargs_of(mock_run)["env"]
        assert env["GIT_TERMINAL_PROMPT"] == "0"

    def test_env_inherits_os_environ_keys(self, mock_run, monkeypatch):
        monkeypatch.setenv("AUGUR_SAFE_RUN_MARKER", "present")
        safe_run(["git", "status"])
        env = _kwargs_of(mock_run)["env"]
        assert env["AUGUR_SAFE_RUN_MARKER"] == "present"

    def test_explicit_git_terminal_prompt_preserved(self, mock_run):
        safe_run(["git", "fetch"], env={"GIT_TERMINAL_PROMPT": "1"})
        env = _kwargs_of(mock_run)["env"]
        assert env["GIT_TERMINAL_PROMPT"] == "1"

    def test_caller_env_dict_not_mutated(self, mock_run):
        caller_env = {"PATH": "/bin"}
        safe_run(["git", "status"], env=caller_env)
        # The injected default must land on a copy, not the caller's object.
        assert "GIT_TERMINAL_PROMPT" not in caller_env
        passed = _kwargs_of(mock_run)["env"]
        assert passed is not caller_env
        assert passed["GIT_TERMINAL_PROMPT"] == "0"
        assert passed["PATH"] == "/bin"

    def test_explicit_env_does_not_inherit_os_environ(self, mock_run, monkeypatch):
        # When the caller supplies env, only that env (+ injected default) is
        # used; unrelated process vars must not leak in.
        monkeypatch.setenv("AUGUR_SAFE_RUN_LEAK", "should_not_appear")
        safe_run(["git", "status"], env={"PATH": "/bin"})
        env = _kwargs_of(mock_run)["env"]
        assert "AUGUR_SAFE_RUN_LEAK" not in env

    def test_env_none_treated_as_environ_copy(self, mock_run, monkeypatch):
        # Explicit env=None is the documented "use process environment" path.
        monkeypatch.setenv("AUGUR_SAFE_RUN_NONE", "from_environ")
        safe_run(["git", "status"], env=None)
        env = _kwargs_of(mock_run)["env"]
        assert env["AUGUR_SAFE_RUN_NONE"] == "from_environ"
        assert env["GIT_TERMINAL_PROMPT"] == "0"

    def test_os_environ_not_mutated(self, mock_run):
        before = dict(os.environ)
        had_prompt = "GIT_TERMINAL_PROMPT" in os.environ
        safe_run(["git", "status"])
        assert dict(os.environ) == before
        # Specifically, the injected default must not leak into the real env.
        assert ("GIT_TERMINAL_PROMPT" in os.environ) == had_prompt

    def test_passed_env_is_isolated_from_os_environ(self, mock_run):
        safe_run(["git", "status"])
        env = _kwargs_of(mock_run)["env"]
        # Mutating the env handed to subprocess must not touch the live process.
        env["AUGUR_SAFE_RUN_ISOLATION"] = "1"
        assert "AUGUR_SAFE_RUN_ISOLATION" not in os.environ


# =============================================================================
# timeout: deliberately NOT forced
# =============================================================================


class TestTimeout:
    def test_timeout_not_forced(self, mock_run):
        safe_run(["sleep", "1"])
        assert "timeout" not in _kwargs_of(mock_run)

    def test_explicit_timeout_preserved(self, mock_run):
        safe_run(["sleep", "1"], timeout=5)
        assert _kwargs_of(mock_run)["timeout"] == 5


# =============================================================================
# passthrough of args / kwargs / return value
# =============================================================================


class TestPassthrough:
    def test_positional_command_forwarded_unchanged(self, mock_run):
        cmd = ["git", "rev-parse", "HEAD"]
        safe_run(cmd)
        assert mock_run.call_args.args[0] == cmd

    def test_other_kwargs_forwarded(self, mock_run):
        safe_run(["git", "status"], capture_output=True, text=True, cwd="/tmp")
        kwargs = _kwargs_of(mock_run)
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["cwd"] == "/tmp"

    def test_return_value_passthrough(self, mock_run):
        sentinel = MagicMock(name="cp")
        mock_run.return_value = sentinel
        assert safe_run(["echo", "hi"]) is sentinel

    def test_exceptions_propagate(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=1)
        with pytest.raises(subprocess.TimeoutExpired):
            safe_run(["git", "status"], timeout=1)


# =============================================================================
# real (harmless) subprocess: proves the safety behavior end to end
# =============================================================================


class TestRealSubprocess:
    def test_child_stdin_is_devnull_eof(self):
        # The actual hang fix: the child must see immediate EOF on stdin instead
        # of inheriting and blocking on the bridge pipe. Reading stdin yields "".
        result = safe_run(
            [sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "0"

    def test_child_sees_git_terminal_prompt_zero(self):
        result = safe_run(
            [
                sys.executable,
                "-c",
                "import os; print(os.environ.get('GIT_TERMINAL_PROMPT', 'UNSET'))",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "0"

    def test_real_explicit_env_overrides_prompt(self):
        result = safe_run(
            [
                sys.executable,
                "-c",
                "import os; print(os.environ['GIT_TERMINAL_PROMPT'])",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "1"},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "1"

    def test_returns_completed_process(self):
        result = safe_run(
            [sys.executable, "-c", "print('ok')"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.stdout.strip() == "ok"
