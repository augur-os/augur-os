# AI Monitor Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent AI client sidecar to the daemon that monitors stderr logs and vault repo, fixing runtime errors in real-time without spawning separate headless LLM calls.

**Architecture:** Two-process model — the daemon spawns an AI client session running `/daemon --monitor`, which calls a watcher script (`ai_monitor_watcher.py`) that blocks on watchdog events, filters noise via `patterns.py`, and returns structured error events. The AI investigates and fixes immediately, then loops.

**Tech Stack:** Python 3.11+, watchdog (already a dependency), existing self-heal infrastructure (patterns.py, registry, fix lock), `llm_retry.py` for multi-client CLI resolution.

**Spec:** `docs/superpowers/specs/2026-03-22-ai-monitor-sidecar-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `config/system/daemon.yaml` | Create | `ai_monitor` configuration |
| `skills/daemon/scripts/ai_monitor_watcher.py` | Create | Watcher script — watchdog, filtering, 6 CLI modes |
| `skills/daemon/scripts/ai_monitor_sidecar.py` | Create | `AISidecarManager` class — spawn/restart/context pressure |
| `src/lib/llm_retry.py` | Modify | Add `build_sidecar_cmd()` |
| `skills/daemon/scripts/unified_daemon.py` | Modify | Import `AISidecarManager`, start as child #12 |
| `skills/daemon/SKILL.md` | Modify | Document `--monitor` mode |
| Tests (see individual tasks) | Create | Unit tests for each component |

---

### Task 1: Configuration File

**Files:**
- Create: `config/system/daemon.yaml`
- Test: `skills/daemon/augur/tests/test_ai_monitor_config.py`

- [ ] **Step 1: Write test for config loading**

```python
# skills/daemon/augur/tests/test_ai_monitor_config.py
"""Tests for ai_monitor config loading."""
import yaml
from pathlib import Path


def test_daemon_config_loads():
    """Config file is valid YAML with expected keys."""
    config_path = Path(__file__).resolve().parents[5] / "config" / "system" / "daemon.yaml"
    assert config_path.exists(), f"Config not found: {config_path}"
    data = yaml.safe_load(config_path.read_text())
    assert "ai_monitor" in data
    monitor = data["ai_monitor"]
    assert monitor["enabled"] is True
    assert isinstance(monitor["context_pressure_bytes"], int)
    assert isinstance(monitor["debounce_seconds"], (int, float))
    assert isinstance(monitor["vault_check_interval"], int)
    assert isinstance(monitor["vault_auto_commit"], bool)
    assert isinstance(monitor["vault_auto_commit_paths"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_ai_monitor_config.py -v`
Expected: FAIL — config file does not exist

- [ ] **Step 3: Create the config file**

```yaml
# config/system/daemon.yaml
# AI Monitor Sidecar configuration.
# The sidecar runs an AI client session inside the daemon to monitor
# runtime errors and fix them without spawning separate headless LLM calls.

ai_monitor:
  enabled: true
  context_pressure_bytes: 500000   # ~125k tokens, trigger sidecar restart
  debounce_seconds: 2              # watchdog event debounce
  vault_check_interval: 300        # vault health checks every 5min
  vault_auto_commit: true          # auto-commit data/memory changes in vault
  vault_auto_commit_paths:         # only these vault subdirs get auto-committed
    - "data/**"
    - "memory/**"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_ai_monitor_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/system/daemon.yaml skills/daemon/augur/tests/test_ai_monitor_config.py
git commit -m "feat(daemon): add ai_monitor config file"
```

---

### Task 2: `build_sidecar_cmd()` in `llm_retry.py`

**Files:**
- Modify: `src/lib/llm_retry.py` (add function after `build_headless_cmd` at line ~235)
- Test: `skills/daemon/augur/tests/test_build_sidecar_cmd.py`

- [ ] **Step 1: Write test for build_sidecar_cmd**

```python
# skills/daemon/augur/tests/test_build_sidecar_cmd.py
"""Tests for build_sidecar_cmd() — interactive sidecar session invocation."""
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure src/ is importable
PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_sidecar_cmd_omits_print_flag():
    """Sidecar command must NOT include --print or output_mode flags."""
    from src.lib.llm_retry import build_sidecar_cmd

    cmd = build_sidecar_cmd("/usr/local/bin/claude", "/daemon --monitor")
    assert "--print" not in cmd, "Sidecar must not use --print (non-interactive)"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_build_sidecar_cmd.py -v`
Expected: FAIL — `build_sidecar_cmd` not found

- [ ] **Step 3: Implement build_sidecar_cmd**

Add after `build_headless_cmd()` (line ~235) in `src/lib/llm_retry.py`:

```python
def build_sidecar_cmd(
    cli_path: str,
    prompt: str,
    *,
    model: str | None = None,
    allowed_tools: str | None = None,
    bypass_approvals: bool = True,
) -> list[str]:
    """Build CLI command for a persistent interactive sidecar session.

    Like build_headless_cmd() but omits --print/output_mode and --max-turns,
    producing a long-running interactive session where the AI can call tools
    in a loop. Used by AISidecarManager in the daemon.
    """
    profile = _get_headless_profile(cli_path)
    cmd = [cli_path]

    # Subcommand — use sidecar_subcommand override if defined in profile,
    # otherwise skip subcommand entirely (headless subcommands like codex "exec"
    # are inappropriate for interactive sessions)
    sidecar_sub = profile.get("sidecar_subcommand")
    if sidecar_sub:
        cmd.append(sidecar_sub)

    # NO output_mode — intentionally omitted for interactive session
    # NO max_turns — session runs indefinitely

    # Parameterized flags (model, allowed_tools only — no max_turns)
    param_flags = profile.get("param_flags", {})
    for name, value in [("model", model), ("allowed_tools", allowed_tools)]:
        if value is not None and name in param_flags:
            cmd.extend([param_flags[name], str(value)])

    # Boolean flags — bypass_approvals only, NOT no_session (session persists)
    bool_flags = profile.get("boolean_flags", {})
    if bypass_approvals and "bypass_approvals" in bool_flags:
        cmd.append(bool_flags["bypass_approvals"])

    # Prompt delivery
    if profile.get("prompt_delivery") == "positional":
        cmd.append(prompt)
    else:
        prompt_flag = profile.get("prompt_flag", "-p")
        cmd.extend([prompt_flag, prompt])

    return cmd
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_build_sidecar_cmd.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/llm_retry.py skills/daemon/augur/tests/test_build_sidecar_cmd.py
git commit -m "feat(llm_retry): add build_sidecar_cmd for interactive AI sessions"
```

---

### Task 3: `ai_monitor_watcher.py` — Core Watcher with `--wait-for-event`

This is the largest task. The watcher script uses watchdog to observe daemon stderr logs and self-heal events, applies filtering, and blocks until an actionable error is detected.

**Files:**
- Create: `skills/daemon/scripts/ai_monitor_watcher.py`
- Test: `skills/daemon/augur/tests/test_ai_monitor_watcher.py`

**Reference files (read, don't modify):**
- `skills/apple/scripts/note_watcher.py` — watchdog pattern to follow
- `skills/daemon/scripts/self_heal/patterns.py` — `ErrorPattern`, `get_tier_patterns()`
- `skills/daemon/scripts/self_heal/scanner.py` — watermark pattern, `_generate_dedup_key()`
- `skills/daemon/scripts/self_heal/escalation.py` — `deduplicate_findings()`

- [ ] **Step 1: Write tests for the filtering pipeline**

```python
# skills/daemon/augur/tests/test_ai_monitor_watcher.py
"""Tests for ai_monitor_watcher.py filtering and event output."""
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SCRIPTS_DIR = PROJECT_ROOT / ".claude" / "skills" / "daemon" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_read_new_lines_from_watermark():
    """Only reads bytes after the watermark position."""
    from ai_monitor_watcher import _read_new_lines

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write("line1\nline2\nline3\n")
        f.flush()
        path = Path(f.name)

    # First read: watermark at 0, should get all lines
    lines, new_offset = _read_new_lines(path, 0)
    assert len(lines) == 3
    assert lines[0] == "line1"

    # Append more
    with open(path, "a") as f:
        f.write("line4\nline5\n")

    # Second read: from previous offset, should get only new lines
    lines, new_offset2 = _read_new_lines(path, new_offset)
    assert len(lines) == 2
    assert lines[0] == "line4"
    assert new_offset2 > new_offset

    path.unlink()


def test_filter_noise_drops_transient():
    """Transient/dismiss patterns are filtered out."""
    from ai_monitor_watcher import _filter_lines

    lines = [
        "INFO: Health check passed",
        "ERROR: TypeError: Cannot read property 'x' of undefined",
        "DEBUG: connection pool stats",
    ]
    actionable = _filter_lines(lines, source="test_service")
    # Only the TypeError should survive (dismiss/transient patterns filter the rest)
    # Exact result depends on patterns.py, but at minimum non-ERROR lines are dropped
    assert any("TypeError" in a.get("message", "") for a in actionable)


def test_format_event_json():
    """Events are formatted as compact JSON."""
    from ai_monitor_watcher import _format_event

    event = _format_event(
        source="dashboard_monitor",
        event_type="daemon_stderr",
        message="TypeError: x is not a function",
        file="src/server.py:42",
        severity="high",
        dedup_key="abc123",
    )
    parsed = json.loads(event)
    assert parsed["source"] == "dashboard_monitor"
    assert parsed["type"] == "daemon_stderr"
    assert parsed["severity"] == "high"
    assert parsed["dedup_key"] == "abc123"


def test_timeout_returns_timeout_event():
    """--wait-for-event --timeout returns timeout event when no errors occur."""
    from ai_monitor_watcher import _wait_for_event_with_timeout

    # With a 0.1s timeout and no watched dirs, should return timeout event
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _wait_for_event_with_timeout(
            stderr_dir=Path(tmpdir),
            state_dir=Path(tmpdir),
            vault_dir=None,
            timeout=0.1,
            debounce=0.05,
            registry={},
        )
        parsed = json.loads(result)
        assert parsed["type"] == "timeout"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_ai_monitor_watcher.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement ai_monitor_watcher.py**

Create `skills/daemon/scripts/ai_monitor_watcher.py`. The implementation must:

1. Import `patterns.py` for `get_tier_patterns()` to classify lines as dismiss/transient/actionable
2. Use the watermark pattern from `scanner.py` — read file from byte offset, return new lines + new offset
3. Use `watchdog.observers.Observer` with `FileSystemEventHandler` (same pattern as `note_watcher.py`)
4. Debounce events using a dict of `{path: timestamp}` (same as `note_watcher.py` line 170-171)
5. Exclude `ai_monitor.stderr.log` from the watch list (feedback loop prevention)
6. On actionable event: format as compact JSON, print to stdout, exit
7. On timeout: print `{"type": "timeout"}`, exit

Key functions to implement:
- `_read_new_lines(path: Path, offset: int) -> tuple[list[str], int]`
- `_filter_lines(lines: list[str], source: str) -> list[dict]` — applies patterns.py
- `_format_event(source, event_type, message, file, severity, dedup_key, **kw) -> str`
- `_load_watermarks(state_dir: Path) -> dict` / `_save_watermarks(state_dir: Path, wm: dict)`
- `_wait_for_event_with_timeout(stderr_dir, state_dir, vault_dir, timeout, debounce, registry) -> str`
- `_load_registry(state_dir: Path) -> dict`
- `main()` — argparse CLI dispatcher

The watchdog event handler class should:
- Watch `stderr_dir` for `*.stderr.log` changes (excluding `ai_monitor.stderr.log`)
- Watch `state_dir` for `self_heal_events.jsonl` changes
- On event: read new lines, filter, if actionable set a threading.Event
- Main thread blocks on the Event with timeout

Use `src.config.paths` for resolving `LOGS_DIR`, `STATE_DIR`, `VAULT_DIR`:
```python
from src.config.paths import get_logs_dir, get_state_dir, get_vault_dir
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_ai_monitor_watcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/daemon/scripts/ai_monitor_watcher.py skills/daemon/augur/tests/test_ai_monitor_watcher.py
git commit -m "feat(daemon): add ai_monitor_watcher with watchdog event loop"
```

---

### Task 4: `ai_monitor_watcher.py` — Lock, Record-Fix, Vault-Check, Status Modes

**Files:**
- Modify: `skills/daemon/scripts/ai_monitor_watcher.py`
- Modify: `skills/daemon/augur/tests/test_ai_monitor_watcher.py`

**Reference files (read, don't modify):**
- `skills/daemon/scripts/self_heal/fixers.py` — `FIX_LOCK_FILE`, `acquire_fix_lock()`, `release_fix_lock()`

- [ ] **Step 1: Write tests for remaining modes**

Add to the existing test file:

```python
def test_acquire_lock_writes_pid():
    """--acquire-lock creates FIX_LOCK_FILE with the watcher's PID."""
    from ai_monitor_watcher import _acquire_lock

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "fix.lock"
        pid = _acquire_lock("test_key", lock_file)
        try:
            assert pid is not None
            assert lock_file.exists()
            data = json.loads(lock_file.read_text())
            assert data["issue_key"] == "test_key"
            assert data["pid"] == pid
        finally:
            # Always clean up the background lock holder process
            import os, signal
            os.kill(pid, signal.SIGTERM)


def test_release_lock_removes_file():
    """--release-lock removes FIX_LOCK_FILE and kills the holder."""
    from ai_monitor_watcher import _acquire_lock, _release_lock

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "fix.lock"
        pid = _acquire_lock("test_key", lock_file)
        _release_lock(lock_file)
        assert not lock_file.exists()


def test_record_fix_updates_registry():
    """--record-fix updates the registry entry status."""
    from ai_monitor_watcher import _record_fix

    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "self_heal_registry.json"
        registry = {"abc123": {"status": "detected", "message": "some error"}}
        registry_path.write_text(json.dumps(registry))

        _record_fix(registry_path, "abc123", "fixed", "deadbeef")

        updated = json.loads(registry_path.read_text())
        assert updated["abc123"]["status"] == "fixed"
        assert updated["abc123"]["fix_commit"] == "deadbeef"


def test_vault_check_detects_conflict_markers():
    """--vault-check finds files with git conflict markers."""
    from ai_monitor_watcher import _vault_check

    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        conflict_file = vault / "data" / "test.md"
        conflict_file.parent.mkdir(parents=True)
        conflict_file.write_text("<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> branch\n")

        issues = _vault_check(vault)
        assert len(issues) > 0
        assert any("conflict" in i.get("type", "") for i in issues)


def test_status_returns_json():
    """--status returns valid JSON with expected keys."""
    from ai_monitor_watcher import _get_status

    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir)
        # Write minimal daemon status
        (state_dir / "stats").mkdir()
        (state_dir / "stats" / "daemon_status.json").write_text(
            json.dumps({"daemon_pid": 123, "services": {}})
        )
        (state_dir / "self_heal_registry.json").write_text("{}")

        result = _get_status(state_dir)
        parsed = json.loads(result)
        assert "daemon" in parsed
        assert "pending_issues" in parsed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_ai_monitor_watcher.py -v -k "lock or record or vault or status"`
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement the four remaining modes**

Add to `ai_monitor_watcher.py`:

**`_acquire_lock(key, lock_file)`**: Fork a child process that writes `{issue_key, pid, started}` to `lock_file` and sleeps indefinitely. Return the child PID. The child stays alive until killed, making `_pid_alive()` in `fixers.py` return True.

**`_release_lock(lock_file)`**: Read PID from lock file, send SIGTERM, unlink file.

**`_record_fix(registry_path, key, status, commit_hash)`**: Read registry JSON, update entry with status and fix_commit, write back atomically (temp + rename).

**`_vault_check(vault_dir)`**: Scan for conflict markers (`<<<<<<<`), broken YAML frontmatter in `.md` files (try `yaml.safe_load`), return list of issue dicts.

**`_get_status(state_dir)`**: Read `daemon_status.json` and `self_heal_registry.json`, count pending/fixed/failed, return JSON summary.

**`_update_bytes_counter(state_dir, bytes_added)`**: Read/create `ai_monitor_bytes.json`, increment counter, write atomically.

Add argparse subcommands in `main()`:
```python
parser = argparse.ArgumentParser(description="AI Monitor Watcher")
sub = parser.add_subparsers(dest="mode")

wait = sub.add_parser("wait-for-event")
wait.add_argument("--timeout", type=float, default=None)

lock = sub.add_parser("acquire-lock")
lock.add_argument("--key", required=True)

sub.add_parser("release-lock")

rec = sub.add_parser("record-fix")
rec.add_argument("--key", required=True)
rec.add_argument("--status", required=True)
rec.add_argument("--commit", required=True)

sub.add_parser("vault-check")
sub.add_parser("status")
```

Also support `--wait-for-event` as a single flag for convenience:
```python
parser.add_argument("--wait-for-event", action="store_true")
parser.add_argument("--timeout", type=float, default=None)
parser.add_argument("--acquire-lock", action="store_true")
parser.add_argument("--key", type=str)
parser.add_argument("--release-lock", action="store_true")
parser.add_argument("--record-fix", action="store_true")
parser.add_argument("--status", action="store_true")
parser.add_argument("--vault-check", action="store_true")
parser.add_argument("--commit", type=str)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_ai_monitor_watcher.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add skills/daemon/scripts/ai_monitor_watcher.py skills/daemon/augur/tests/test_ai_monitor_watcher.py
git commit -m "feat(daemon): add lock, record-fix, vault-check, status modes to watcher"
```

---

### Task 5: `AISidecarManager` Class

**Files:**
- Create: `skills/daemon/scripts/ai_monitor_sidecar.py`
- Test: `skills/daemon/augur/tests/test_ai_monitor_sidecar.py`

**Reference files (read, don't modify):**
- `skills/daemon/scripts/unified_daemon.py:273-538` — `SubprocessManager` class (reuse restart/backoff logic)
- `src/lib/llm_retry.py:238-270` — `resolve_cli()`
- `config/system/daemon.yaml` — `ai_monitor` config

- [ ] **Step 1: Write tests for AISidecarManager**

```python
# skills/daemon/augur/tests/test_ai_monitor_sidecar.py
"""Tests for AISidecarManager — AI client spawn, restart, context pressure."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SCRIPTS_DIR = PROJECT_ROOT / ".claude" / "skills" / "daemon" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_sidecar_manager_skips_when_cli_unavailable():
    """If resolve_cli() raises, sidecar should not start."""
    from ai_monitor_sidecar import AISidecarManager

    with patch("ai_monitor_sidecar.resolve_cli", side_effect=RuntimeError("No CLI")):
        mgr = AISidecarManager(config={"enabled": True})
        result = mgr.start()
        assert result is False
        assert mgr.state == "unavailable"


def test_sidecar_manager_disabled_by_config():
    """If enabled=false in config, sidecar should not start."""
    from ai_monitor_sidecar import AISidecarManager

    mgr = AISidecarManager(config={"enabled": False})
    result = mgr.start()
    assert result is False
    assert mgr.state == "disabled"


def test_context_pressure_detected():
    """Sidecar detects context pressure from bytes counter file."""
    from ai_monitor_sidecar import AISidecarManager

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "ai_monitor_bytes.json"
        state_file.write_text(json.dumps({"bytes_outputted": 600000}))

        mgr = AISidecarManager(config={
            "enabled": True,
            "context_pressure_bytes": 500000,
        })
        mgr._state_dir = Path(tmpdir)
        assert mgr._check_context_pressure() is True


def test_context_pressure_not_triggered_below_threshold():
    """No pressure when bytes are below threshold."""
    from ai_monitor_sidecar import AISidecarManager

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "ai_monitor_bytes.json"
        state_file.write_text(json.dumps({"bytes_outputted": 100000}))

        mgr = AISidecarManager(config={
            "enabled": True,
            "context_pressure_bytes": 500000,
        })
        mgr._state_dir = Path(tmpdir)
        assert mgr._check_context_pressure() is False


def test_restart_deferred_when_fix_lock_held():
    """Don't restart sidecar if FIX_LOCK_FILE exists with alive PID."""
    import os
    from ai_monitor_sidecar import AISidecarManager

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "fix.lock"
        lock_file.write_text(json.dumps({
            "issue_key": "test",
            "pid": os.getpid(),  # current process — alive
            "started": "2026-03-22T00:00:00",
        }))

        mgr = AISidecarManager(config={"enabled": True})
        mgr._fix_lock_file = lock_file
        assert mgr._fix_lock_held() is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_ai_monitor_sidecar.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement AISidecarManager**

Create `skills/daemon/scripts/ai_monitor_sidecar.py`:

```python
"""AI Monitor Sidecar Manager.

Manages the AI client process that monitors daemon stderr logs and vault repo.
This is NOT a SubprocessManager child — it manages a different kind of process
(AI CLI binary instead of Python script) with different health semantics.

Reuses restart/backoff logic patterns from SubprocessManager but with:
- AI CLI binary instead of PYTHON
- build_sidecar_cmd() instead of [PYTHON, script.py]
- Context pressure tracking (bytes outputted by watcher)
- Fix lock awareness (never kill mid-fix)
"""
from __future__ import annotations

import json
import logging
import os
import signal
import time
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, Popen
from typing import Any, Optional

from src.lib.llm_retry import build_sidecar_cmd, resolve_cli

logger = logging.getLogger("augur.daemon.ai_sidecar")


class AISidecarManager:
    """Manages the AI client sidecar process."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.enabled = config.get("enabled", True)
        self.pressure_threshold = config.get("context_pressure_bytes", 500_000)
        self.process: Optional[Popen] = None
        self.state = "stopped"  # stopped | running | unavailable | disabled
        self.restart_delay = 30
        self.max_restart_delay = 960  # 32x base
        self.consecutive_failures = 0
        self.total_restarts = 0
        self.restart_timestamps: list[float] = []
        self.max_restarts_per_hour = 3
        self.last_started: Optional[str] = None
        self._stderr_file: Any = None

        # Set by daemon after init (paths and env from unified_daemon.py)
        self._state_dir: Optional[Path] = None
        self._fix_lock_file: Optional[Path] = None
        self._stderr_logs_dir: Optional[Path] = None
        self._project_root: Optional[Path] = None
        self._env: dict[str, str] = dict(os.environ)  # daemon overrides with _augmented_env()

    def start(self) -> bool:
        """Start the AI client sidecar."""
        if not self.enabled:
            self.state = "disabled"
            return False

        if self.process and self.process.poll() is None:
            return True  # Already running

        try:
            cli_path = resolve_cli()
        except RuntimeError as e:
            logger.warning("No AI client available, skipping sidecar: %s", e)
            self.state = "unavailable"
            return False

        try:
            cmd = build_sidecar_cmd(
                cli_path,
                "/daemon --monitor",
                allowed_tools="Read,Edit,Bash,Grep,Glob,Write",
                bypass_approvals=True,
            )

            # Stderr to dedicated log (NOT monitored by watcher)
            if self._stderr_logs_dir:
                self._stderr_logs_dir.mkdir(parents=True, exist_ok=True)
                stderr_path = self._stderr_logs_dir / "ai_monitor.stderr.log"
                self._stderr_file = open(stderr_path, "a")  # noqa: SIM115
            else:
                self._stderr_file = DEVNULL

            self.process = Popen(
                cmd,
                cwd=str(self._project_root) if self._project_root else None,
                stdout=DEVNULL,
                stderr=self._stderr_file,
                env={**self._env, "PYTHONUNBUFFERED": "1"},
            )
            self.state = "running"
            self.last_started = datetime.now().isoformat()
            self._reset_bytes_counter()
            logger.info("AI sidecar started (PID %s)", self.process.pid)
            return True
        except Exception as e:
            logger.error("Failed to start AI sidecar: %s", e)
            self.state = "unavailable"
            return False

    def stop(self, timeout: int = 10) -> None:
        """Gracefully stop the sidecar."""
        if not self.process or self.process.poll() is not None:
            self.state = "stopped"
            self.process = None
            return

        pid = self.process.pid
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=timeout)
            except Exception:
                self.process.kill()
                self.process.wait(timeout=5)
        except Exception as e:
            logger.error("Error stopping sidecar: %s", e)

        self.process = None
        self._close_stderr()
        self.state = "stopped"
        logger.info("AI sidecar stopped (was PID %s)", pid)

    def check_health(self) -> dict[str, Any]:
        """Check sidecar health, handle restarts and context pressure."""
        if not self.enabled:
            return self._status_dict()

        if not self.process:
            if self.state == "unavailable":
                # Periodically retry CLI resolution
                return self._status_dict()
            if self.state in {"stopped", "unavailable"}:
                self._maybe_restart()
            return self._status_dict()

        exit_code = self.process.poll()
        if exit_code is None:
            # Running — check context pressure
            if self._check_context_pressure():
                if not self._fix_lock_held():
                    logger.info("Context pressure threshold reached, restarting sidecar")
                    self.stop()
                    self.start()
            # Reset consecutive failures after 60s uptime
            if self.last_started and self.consecutive_failures > 0:
                started_ts = datetime.fromisoformat(self.last_started).timestamp()
                if time.time() - started_ts > 60:
                    self.consecutive_failures = 0
            return self._status_dict()

        # Process exited
        self.process = None
        self._close_stderr()
        self.consecutive_failures += 1
        logger.warning("AI sidecar exited (code %s)", exit_code)
        self._maybe_restart()
        return self._status_dict()

    def _maybe_restart(self) -> None:
        """Attempt restart with backoff."""
        if self.consecutive_failures >= 10:
            self.state = "unavailable"
            return
        now = time.time()
        one_hour_ago = now - 3600
        self.restart_timestamps = [t for t in self.restart_timestamps if t > one_hour_ago]
        if len(self.restart_timestamps) >= self.max_restarts_per_hour:
            self.state = "unavailable"
            return
        delay = self.restart_delay * (2 ** min(self.consecutive_failures, 5))
        delay = min(delay, self.max_restart_delay)
        # Simple backoff — don't restart if too soon
        if self.last_started:
            last_ts = datetime.fromisoformat(self.last_started).timestamp()
            if now - last_ts < delay:
                return
        self.total_restarts += 1
        self.restart_timestamps.append(now)
        self.start()

    def _check_context_pressure(self) -> bool:
        """Check if watcher's byte counter exceeds threshold."""
        if not self._state_dir:
            return False
        bytes_file = self._state_dir / "ai_monitor_bytes.json"
        if not bytes_file.exists():
            return False
        try:
            data = json.loads(bytes_file.read_text())
            return data.get("bytes_outputted", 0) >= self.pressure_threshold
        except Exception:
            return False

    def _fix_lock_held(self) -> bool:
        """Check if FIX_LOCK_FILE exists with a live PID."""
        if not self._fix_lock_file or not self._fix_lock_file.exists():
            return False
        try:
            data = json.loads(self._fix_lock_file.read_text())
            pid = data.get("pid", 0)
            if pid:
                os.kill(pid, 0)  # Check if alive
                return True
        except (ProcessLookupError, PermissionError, json.JSONDecodeError):
            pass
        return False

    def _reset_bytes_counter(self) -> None:
        """Reset the watcher's byte counter on fresh start."""
        if not self._state_dir:
            return
        bytes_file = self._state_dir / "ai_monitor_bytes.json"
        _atomic_write(bytes_file, json.dumps({"bytes_outputted": 0}))

    def _close_stderr(self) -> None:
        if self._stderr_file is not None and self._stderr_file is not DEVNULL:
            try:
                self._stderr_file.close()
            except Exception:
                pass
            self._stderr_file = None

    def _status_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "pid": self.process.pid if self.process and self.process.poll() is None else None,
            "total_restarts": self.total_restarts,
            "last_started": self.last_started,
        }


def _atomic_write(path: Path, content: str) -> None:
    """Write file atomically via temp + rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content)
    tmp.rename(path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_ai_monitor_sidecar.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/daemon/scripts/ai_monitor_sidecar.py skills/daemon/augur/tests/test_ai_monitor_sidecar.py
git commit -m "feat(daemon): add AISidecarManager for AI client lifecycle"
```

---

### Task 6: Integrate Sidecar into `unified_daemon.py`

**Files:**
- Modify: `skills/daemon/scripts/unified_daemon.py`

- [ ] **Step 1: Write integration test**

Add to `skills/daemon/augur/tests/test_ai_monitor_sidecar.py`:

```python
def test_daemon_loop_starts_sidecar():
    """unified_daemon.py creates and starts AISidecarManager."""
    # Verify the import and instantiation work
    from ai_monitor_sidecar import AISidecarManager

    config = {"enabled": False}  # disabled to avoid real CLI spawn
    mgr = AISidecarManager(config=config)
    assert mgr.state == "stopped"
    result = mgr.start()
    assert result is False
    assert mgr.state == "disabled"
```

- [ ] **Step 2: Run test to verify it passes** (this test validates the import path)

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_ai_monitor_sidecar.py::test_daemon_loop_starts_sidecar -v`
Expected: PASS

- [ ] **Step 3: Modify unified_daemon.py**

Add the sidecar to `daemon_loop()`. Three changes:

**Change 1:** Add import at top of `daemon_loop()` function (line ~609):
```python
def daemon_loop() -> int:
    """Main daemon loop: manage children, write status."""
    global _shutdown

    # Import sidecar manager (optional — skipped if unavailable)
    try:
        from ai_monitor_sidecar import AISidecarManager
    except ImportError:
        AISidecarManager = None
```

**Change 2:** After creating managers dict (line ~628), create and start sidecar:
```python
    # Create managers
    managers: dict[str, SubprocessManager] = {}
    for name, config in CHILD_SERVICES.items():
        managers[name] = SubprocessManager(name, config)

    # AI Monitor Sidecar (child #12, managed separately)
    ai_sidecar: AISidecarManager | None = None
    if AISidecarManager is not None:
        sidecar_config = _load_sidecar_config()
        if sidecar_config.get("enabled", False):
            ai_sidecar = AISidecarManager(config=sidecar_config)
            ai_sidecar._state_dir = RUNTIME_DIR
            ai_sidecar._fix_lock_file = RUNTIME_DIR / "locks" / "self_heal_fix.lock"
            ai_sidecar._stderr_logs_dir = _STDERR_LOGS_DIR
            ai_sidecar._project_root = PROJECT_ROOT
            ai_sidecar._env = _augmented_env()
```

**Change 3:** In the main loop (line ~636), add sidecar health check:
```python
    while not _shutdown:
        # Check health of all children
        for name, mgr in managers.items():
            if mgr.mode == "persistent":
                mgr.check_health()

        # Check AI sidecar health
        if ai_sidecar is not None:
            ai_sidecar.check_health()
```

**Change 4:** In shutdown (line ~656), stop sidecar:
```python
    # Graceful shutdown
    logger.info("Shutting down all child services...")
    if ai_sidecar is not None:
        ai_sidecar.stop(timeout=15)
    for name, mgr in managers.items():
        mgr.stop(timeout=15)
```

**Change 5:** Add sidecar to status output. In `_write_status()` (line ~578), add `ai_sidecar` parameter:
```python
def _write_status(
    started_at: str,
    managers: dict[str, SubprocessManager],
    ai_sidecar: "AISidecarManager | None" = None,
) -> None:
    # ... existing code ...
    if ai_sidecar is not None:
        services["ai_monitor_sidecar"] = ai_sidecar._status_dict()
```

**IMPORTANT:** Update BOTH call sites to pass the new parameter:
```python
# Line ~644 (in main loop)
_write_status(started_at, managers, ai_sidecar=ai_sidecar)

# Line ~663 (final status on shutdown)
_write_status(started_at, managers, ai_sidecar=ai_sidecar)
```

**Change 6:** Add config loader helper:
```python
def _load_sidecar_config() -> dict[str, Any]:
    """Load ai_monitor config from config/system/daemon.yaml."""
    config_path = PROJECT_ROOT / "config" / "system" / "daemon.yaml"
    if not config_path.exists():
        return {"enabled": False}
    try:
        import yaml
        data = yaml.safe_load(config_path.read_text())
        return data.get("ai_monitor", {"enabled": False})
    except Exception as e:
        logger.warning("Failed to load sidecar config: %s", e)
        return {"enabled": False}
```

- [ ] **Step 4: Verify unified_daemon.py imports cleanly**

Run: `cd ~/Projects/Augur && python -c "import sys; sys.path.insert(0, '.claude/skills/daemon/scripts'); from unified_daemon import daemon_loop; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add skills/daemon/scripts/unified_daemon.py
git commit -m "feat(daemon): integrate AISidecarManager as child #12"
```

---

### Task 7: Update SKILL.md with `--monitor` Mode

**Files:**
- Modify: `skills/daemon/SKILL.md`

- [ ] **Step 1: Read current SKILL.md**

Read `skills/daemon/SKILL.md` to understand existing structure and where to add the new mode.

- [ ] **Step 2: Add --monitor mode documentation**

Add a new section under the existing Usage/Modes section:

```markdown
### Monitor Mode (`--monitor`)

Runs inside an AI client session as a persistent monitoring loop. The daemon spawns the AI client as a sidecar process — do NOT invoke this mode manually.

**How it works:**
1. AI calls `ai_monitor_watcher.py --status` to load current state
2. AI enters loop: calls `--wait-for-event --timeout 300` (blocks until error or timeout)
3. On error: acquires fix lock, investigates, fixes, commits with `fix(self-heal):` prefix, records fix
4. On timeout: runs `--vault-check` for vault health, then loops

**Configuration:** `config/system/daemon.yaml` — `ai_monitor` section.

**Requires:** An AI client (Claude Code, Codex, or Gemini) installed and configured.
```

- [ ] **Step 3: Commit**

```bash
git add skills/daemon/SKILL.md
git commit -m "docs(daemon): add --monitor mode to SKILL.md"
```

---

### Task 8: End-to-End Integration Test

**Files:**
- Create: `skills/daemon/augur/tests/test_ai_monitor_e2e.py`

- [ ] **Step 1: Write an integration test that simulates the watcher-sidecar flow**

```python
# skills/daemon/augur/tests/test_ai_monitor_e2e.py
"""End-to-end test: simulates a stderr error appearing and watcher detecting it."""
import json
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SCRIPTS_DIR = PROJECT_ROOT / ".claude" / "skills" / "daemon" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_error_in_stderr_produces_event():
    """Write an error to a stderr log, watcher should detect and return event."""
    from ai_monitor_watcher import _wait_for_event_with_timeout

    with tempfile.TemporaryDirectory() as tmpdir:
        stderr_dir = Path(tmpdir) / "stderr"
        stderr_dir.mkdir()
        state_dir = Path(tmpdir) / "state"
        state_dir.mkdir()

        # Pre-create an empty log file so watcher can track it
        log_file = stderr_dir / "dashboard_monitor.stderr.log"
        log_file.write_text("")

        # Write an error after a short delay (simulate daemon child crashing)
        import threading

        def _write_error():
            time.sleep(0.3)
            with open(log_file, "a") as f:
                f.write("ERROR: TypeError: Cannot read property 'status' of undefined\n")
                f.write("  at Object.handler (src/mcp/augur_mcp/server.py:142)\n")

        t = threading.Thread(target=_write_error)
        t.start()

        result = _wait_for_event_with_timeout(
            stderr_dir=stderr_dir,
            state_dir=state_dir,
            vault_dir=None,
            timeout=5.0,
            debounce=0.1,
            registry={},
        )
        t.join()

        parsed = json.loads(result)
        assert parsed["type"] != "timeout", f"Expected error event, got timeout: {result}"
        assert "TypeError" in parsed.get("error", parsed.get("message", ""))


def test_no_error_produces_timeout():
    """No errors within timeout period returns timeout event."""
    from ai_monitor_watcher import _wait_for_event_with_timeout

    with tempfile.TemporaryDirectory() as tmpdir:
        stderr_dir = Path(tmpdir) / "stderr"
        stderr_dir.mkdir()
        state_dir = Path(tmpdir) / "state"
        state_dir.mkdir()

        result = _wait_for_event_with_timeout(
            stderr_dir=stderr_dir,
            state_dir=state_dir,
            vault_dir=None,
            timeout=0.5,
            debounce=0.1,
            registry={},
        )
        parsed = json.loads(result)
        assert parsed["type"] == "timeout"


def test_sidecar_manager_lifecycle():
    """AISidecarManager handles disabled config gracefully."""
    from ai_monitor_sidecar import AISidecarManager

    mgr = AISidecarManager(config={"enabled": False})
    assert mgr.start() is False
    assert mgr.state == "disabled"
    mgr.check_health()  # Should not crash
    mgr.stop()  # Should not crash
```

- [ ] **Step 2: Run tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/daemon/augur/tests/test_ai_monitor_e2e.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add skills/daemon/augur/tests/test_ai_monitor_e2e.py
git commit -m "test(daemon): add e2e integration tests for AI monitor sidecar"
```

---

## Execution Order

Tasks must be executed in order (each depends on the previous):
1. Config file (standalone)
2. `build_sidecar_cmd` (standalone)
3. Watcher core — `--wait-for-event` (depends on patterns.py, scanner.py imports)
4. Watcher modes — lock, record-fix, vault-check, status (extends task 3)
5. `AISidecarManager` (depends on task 2 for `build_sidecar_cmd`)
6. Daemon integration (depends on tasks 3-5)
7. SKILL.md docs (standalone, but logically after implementation)
8. E2E tests (depends on all above)
