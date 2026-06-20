from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import runtime_marker_scanner as rms


def test_scan_and_update_only_reports_new_log_content(tmp_path: Path):
    runtime_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    runtime_dir.mkdir()
    logs_dir.mkdir()
    log_file = logs_dir / "app.log"
    log_file.write_text("Error: first issue\n", encoding="utf-8")

    with (
        patch.object(rms, "get_runtime_dir", return_value=runtime_dir),
        patch.object(rms, "get_logs_dir", return_value=logs_dir),
    ):
        first = rms.scan_and_update()
        second = rms.scan_and_update()

    assert first["new_issues"] == 1
    assert first["changed"] is True
    assert second["new_issues"] == 0
    assert second["changed"] is True
    assert "No current runtime markers detected." in (runtime_dir / "tech_debt.md").read_text(encoding="utf-8")


def test_scan_and_update_ignores_historical_lines_after_append_boundary(tmp_path: Path):
    runtime_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    runtime_dir.mkdir()
    logs_dir.mkdir()
    log_file = logs_dir / "app.log"
    log_file.write_text("Error: first issue\n", encoding="utf-8")

    with (
        patch.object(rms, "get_runtime_dir", return_value=runtime_dir),
        patch.object(rms, "get_logs_dir", return_value=logs_dir),
    ):
        rms.scan_and_update()
        log_file.write_text("Error: first issue\nWarning: second issue\n", encoding="utf-8")
        summary = rms.scan_and_update()

    assert summary["new_issues"] == 1
    content = (runtime_dir / "tech_debt.md").read_text(encoding="utf-8")
    assert "second issue" in content
    assert "first issue" not in content


def test_get_log_files_excludes_archived_rotations(tmp_path: Path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    live_log = logs_dir / "dashboard.stderr.log"
    archived_log = logs_dir / "dashboard.stderr.pre-rotate.log"
    backup_log = logs_dir / "daemon.old.log"
    live_log.write_text("Warning: live issue\n", encoding="utf-8")
    archived_log.write_text("Error: archived issue\n", encoding="utf-8")
    backup_log.write_text("Error: backup issue\n", encoding="utf-8")

    with patch.object(rms, "get_logs_dir", return_value=logs_dir):
        files = rms.get_log_files()

    assert files == [live_log]
