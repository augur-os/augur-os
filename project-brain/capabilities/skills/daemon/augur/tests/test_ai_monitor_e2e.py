"""End-to-end test: simulates a stderr error appearing and watcher detecting it."""

import json
import sys
import tempfile
import time
import threading
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
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
        def _write_error():
            time.sleep(0.3)
            with open(log_file, "a") as f:
                f.write(
                    "ERROR: TypeError: Cannot read property 'status' of undefined\n"
                )
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
        assert parsed["type"] != "timeout", (
            f"Expected error event, got timeout: {result}"
        )
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
