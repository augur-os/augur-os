"""Tests for build_sidecar_cmd() — interactive sidecar session invocation."""
import sys
from pathlib import Path

# Ensure src/ is importable
PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_sidecar_cmd_omits_print_flag():
    """Sidecar command must NOT include print/output mode flags."""
    from src.lib.llm_retry import build_sidecar_cmd

    cmd = build_sidecar_cmd("/usr/local/bin/claude", "/daemon --monitor")
    assert "--print" not in cmd, "Sidecar must not use --print (non-interactive)"
    assert "-p" not in cmd, "Claude -p is also print-and-exit mode"
    assert "/daemon --monitor" in " ".join(cmd)


def test_sidecar_cmd_includes_bypass_approvals():
    """Sidecar must run with permission bypass."""
    from src.lib.llm_retry import build_sidecar_cmd

    cmd = build_sidecar_cmd("/usr/local/bin/claude", "/daemon --monitor")
    assert "--dangerously-skip-permissions" in cmd


def test_sidecar_cmd_includes_allowed_tools():
    """Sidecar must restrict tools to Read,Edit,Bash,Grep,Glob,Write."""
    from src.lib.llm_retry import build_sidecar_cmd

    cmd = build_sidecar_cmd(
        "/usr/local/bin/claude",
        "/daemon --monitor",
        allowed_tools="Read,Edit,Bash,Grep,Glob,Write",
    )
    tools_idx = cmd.index("--allowedTools")
    assert cmd[tools_idx + 1] == "Read,Edit,Bash,Grep,Glob,Write"


def test_sidecar_cmd_includes_additional_dirs():
    """Claude sidecar can be granted runtime/log/vault directories up front."""
    from src.lib.llm_retry import build_sidecar_cmd

    cmd = build_sidecar_cmd(
        "/usr/local/bin/claude",
        "/daemon --monitor",
        additional_dirs=["/tmp/augur-state", "/tmp/augur-vault"],
    )
    add_dir_idx = cmd.index("--add-dir")
    assert cmd[add_dir_idx + 1 : add_dir_idx + 3] == ["/tmp/augur-state", "/tmp/augur-vault"]


def test_sidecar_cmd_omits_max_turns():
    """Sidecar sessions run indefinitely — no max_turns flag."""
    from src.lib.llm_retry import build_sidecar_cmd

    cmd = build_sidecar_cmd("/usr/local/bin/claude", "/daemon --monitor")
    assert "--max-turns" not in cmd


def test_sidecar_cmd_omits_no_session():
    """Sidecar sessions persist — no --no-session-persistence."""
    from src.lib.llm_retry import build_sidecar_cmd

    cmd = build_sidecar_cmd("/usr/local/bin/claude", "/daemon --monitor")
    assert "--no-session-persistence" not in cmd
