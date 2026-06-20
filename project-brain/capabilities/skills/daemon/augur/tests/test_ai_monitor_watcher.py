"""Tests for ai_monitor_watcher.py filtering and event output."""

import json
import sys
import tempfile
import time
from pathlib import Path
import os

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
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

    lines, new_offset = _read_new_lines(path, 0)
    assert len(lines) == 3
    assert lines[0] == "line1"

    with open(path, "a") as f:
        f.write("line4\nline5\n")

    lines, new_offset2 = _read_new_lines(path, new_offset)
    assert len(lines) == 2
    assert lines[0] == "line4"
    assert new_offset2 > new_offset

    path.unlink()


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

    with tempfile.TemporaryDirectory() as tmpdir:
        result = _wait_for_event_with_timeout(
            stderr_dir=Path(tmpdir),
            state_dir=Path(tmpdir),
            vault_dir=None,
            timeout=0.5,
            debounce=0.1,
            registry={},
        )
        parsed = json.loads(result)
        assert parsed["type"] == "timeout"


def test_acquire_lock_writes_pid():
    """--acquire-lock creates lock file with the watcher's PID."""
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
            import signal

            os.kill(pid, signal.SIGTERM)


def test_release_lock_removes_file():
    """--release-lock removes lock file and kills the holder."""
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
        conflict_file.write_text(
            "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> branch\n"
        )

        issues = _vault_check(vault)
        assert len(issues) > 0
        assert any("conflict" in i.get("type", "") for i in issues)


def test_status_returns_json():
    """--status returns valid JSON with expected keys."""
    from ai_monitor_watcher import _get_status

    with tempfile.TemporaryDirectory() as tmpdir:
        runtime_dir = Path(tmpdir)
        state_dir = runtime_dir / "ai_monitor"
        state_dir.mkdir()
        # Daemon status lives under RUNTIME_DIR/stats/
        (runtime_dir / "stats").mkdir()
        (runtime_dir / "stats" / "daemon_status.json").write_text(
            json.dumps({"daemon_pid": 123, "services": {}})
        )
        # Registry lives directly under RUNTIME_DIR
        (runtime_dir / "self_heal_registry.json").write_text("{}")

        result = _get_status(state_dir, runtime_dir=runtime_dir)
        parsed = json.loads(result)
        assert "daemon" in parsed
        assert "pending_issues" in parsed
