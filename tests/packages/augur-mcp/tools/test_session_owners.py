"""Session-ownership registry contract tests (ADR-766 v1)."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

import src.mcp.augur_framework.tools.infrastructure.session_owners as so
from src.mcp.augur_framework.tools.infrastructure.session_owners import (
    SessionClaimInput,
    SessionReleaseInput,
    SessionStatusInput,
    session_claim_impl,
    session_release_impl,
    session_status_impl,
)

PROJECT_ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[4])


def _run(coro):
    return json.loads(asyncio.run(coro))


@pytest.fixture
def reg(tmp_path, monkeypatch):
    path = tmp_path / "session-owners.json"
    monkeypatch.setattr(so, "_registry_path", lambda: path)
    monkeypatch.setattr(so, "_host_id", lambda: "host-A")
    monkeypatch.setattr(so, "_pid_alive", lambda pid: pid == 111)
    monkeypatch.setattr(so, "_proc_start_time", lambda pid: "S1" if pid == 111 else None)
    return path


def test_claim_then_status_returns_owner(reg):
    res = _run(
        session_claim_impl(SessionClaimInput(session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude"))
    )
    assert res["ok"] is True
    assert res["session_id"] == "sess1"

    status = _run(session_status_impl(SessionStatusInput(session_id="sess1")))
    assert status["owner"]["pid"] == 111
    assert status["owner"]["surface"] == "dashboard-pty"


def test_cross_surface_live_owner_is_conflict(reg):
    _run(session_claim_impl(SessionClaimInput(session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude")))

    res = _run(
        session_claim_impl(SessionClaimInput(session_id="sess1", surface="native-terminal", pid=111, cli_id="claude"))
    )
    assert res["ok"] is False
    assert res["conflict"]["surface"] == "dashboard-pty"
    assert res["conflict"]["pid"] == 111


def test_same_surface_reclaim_after_dead_pid(reg):
    so._atomic_save(
        {
            "sess1": {
                "pid": 222,
                "surface": "dashboard-pty",
                "host": "host-A",
                "cli_id": "claude",
                "started_at": "t",
                "proc_start_time": "old",
                "last_seen": "t",
            }
        }
    )

    res = _run(
        session_claim_impl(SessionClaimInput(session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude"))
    )
    assert res["ok"] is True


def test_pid_reuse_detected_via_start_time(reg):
    so._atomic_save(
        {
            "sess1": {
                "pid": 111,
                "surface": "native-terminal",
                "host": "host-A",
                "cli_id": "claude",
                "started_at": "t",
                "proc_start_time": "OLD_DIFFERENT",
                "last_seen": "t",
            }
        }
    )

    res = _run(
        session_claim_impl(SessionClaimInput(session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude"))
    )
    assert res["ok"] is True


def test_other_host_entry_is_not_a_local_owner(reg):
    so._atomic_save(
        {
            "sess1": {
                "pid": 111,
                "surface": "native-terminal",
                "host": "host-B",
                "cli_id": "claude",
                "started_at": "t",
                "proc_start_time": "S1",
                "last_seen": "t",
            }
        }
    )

    res = _run(
        session_claim_impl(SessionClaimInput(session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude"))
    )
    assert res["ok"] is True


def test_release_removes_owner(reg):
    _run(session_claim_impl(SessionClaimInput(session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude")))

    _run(session_release_impl(SessionReleaseInput(session_id="sess1", surface="dashboard-pty", pid=111)))

    status = _run(session_status_impl(SessionStatusInput(session_id="sess1")))
    assert status["owner"] is None


def test_release_without_pid_does_not_remove_live_owner(reg):
    _run(session_claim_impl(SessionClaimInput(session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude")))

    release = _run(session_release_impl(SessionReleaseInput(session_id="sess1", surface="dashboard-pty")))

    assert release["ok"] is True
    assert release["released"] is False
    status = _run(session_status_impl(SessionStatusInput(session_id="sess1")))
    assert status["owner"]["pid"] == 111


def test_missing_registry_file_is_empty(reg):
    status = _run(session_status_impl(SessionStatusInput(session_id="nope")))
    assert status["owner"] is None


def test_malformed_registry_file_is_treated_as_empty(reg):
    reg.write_text("{not valid json", encoding="utf-8")

    status = _run(session_status_impl(SessionStatusInput(session_id="nope")))
    assert status["owner"] is None

    claim = _run(
        session_claim_impl(SessionClaimInput(session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude"))
    )
    assert claim["ok"] is True


def test_start_time_unavailable_degrades_to_pid_alive(reg, monkeypatch):
    so._atomic_save(
        {
            "sess1": {
                "pid": 111,
                "surface": "dashboard-pty",
                "host": "host-A",
                "cli_id": "claude",
                "started_at": "t",
                "proc_start_time": "S1",
                "last_seen": "t",
            }
        }
    )
    monkeypatch.setattr(so, "_proc_start_time", lambda pid: None)

    res = _run(
        session_claim_impl(SessionClaimInput(session_id="sess1", surface="native-terminal", pid=111, cli_id="claude"))
    )
    assert res["ok"] is False
    assert res["conflict"]["surface"] == "dashboard-pty"


def test_start_time_unavailable_allows_idempotent_same_owner_claim(reg, monkeypatch):
    so._atomic_save(
        {
            "sess1": {
                "pid": 111,
                "surface": "dashboard-pty",
                "host": "host-A",
                "cli_id": "claude",
                "started_at": "t",
                "proc_start_time": "S1",
                "last_seen": "t",
            }
        }
    )
    monkeypatch.setattr(so, "_proc_start_time", lambda pid: None)

    res = _run(
        session_claim_impl(SessionClaimInput(session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude"))
    )
    assert res["ok"] is True


def test_release_with_stale_pid_does_not_remove_newer_same_surface_owner(reg):
    so._atomic_save(
        {
            "sess1": {
                "pid": 111,
                "surface": "dashboard-pty",
                "host": "host-A",
                "cli_id": "claude",
                "started_at": "t",
                "proc_start_time": "S1",
                "last_seen": "t",
            }
        }
    )

    release = _run(session_release_impl(SessionReleaseInput(session_id="sess1", surface="dashboard-pty", pid=222)))

    assert release["ok"] is True
    assert release["released"] is False
    status = _run(session_status_impl(SessionStatusInput(session_id="sess1")))
    assert status["owner"]["pid"] == 111


def test_status_reclaims_stale_local_entries(reg):
    so._atomic_save(
        {
            "dead": {
                "pid": 222,
                "surface": "dashboard-pty",
                "host": "host-A",
                "cli_id": "claude",
                "started_at": "t",
                "proc_start_time": "old",
                "last_seen": "t",
            },
            "live": {
                "pid": 111,
                "surface": "native-terminal",
                "host": "host-A",
                "cli_id": "claude",
                "started_at": "t",
                "proc_start_time": "S1",
                "last_seen": "t",
            },
        }
    )

    status = _run(session_status_impl(SessionStatusInput()))
    assert set(status["owners"]) == {"live"}

    saved = json.loads(reg.read_text(encoding="utf-8"))
    assert "dead" not in saved
    assert "live" in saved


def test_concurrent_claims_do_not_corrupt_registry(reg):
    def claim(session_id: str):
        return _run(
            session_claim_impl(
                SessionClaimInput(session_id=session_id, surface="dashboard-pty", pid=111, cli_id="claude")
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, ["sess1", "sess2"]))

    assert all(result["ok"] is True for result in results)
    saved = json.loads(reg.read_text(encoding="utf-8"))
    assert sorted(saved) == ["sess1", "sess2"]


@pytest.mark.skipif(sys.platform == "win32", reason="Windows cross-process file-lock semantics differ; validation pending (ROADMAP)")
def test_cross_process_claims_do_not_lose_updates(reg, tmp_path):
    start_file = tmp_path / "start"
    code = r"""
import asyncio
import json
import sys
import time
from pathlib import Path

import src.mcp.augur_framework.tools.infrastructure.session_owners as so
from src.mcp.augur_framework.tools.infrastructure.session_owners import (
    SessionClaimInput,
    session_claim_impl,
)

registry_path = Path(sys.argv[1])
start_file = Path(sys.argv[2])
session_id = sys.argv[3]
pid = int(sys.argv[4])

so._registry_path = lambda: registry_path
so._host_id = lambda: "host-A"
so._pid_alive = lambda value: True
so._proc_start_time = lambda value: f"S{value}"

original_atomic_save = so._atomic_save

def delayed_atomic_save(data):
    time.sleep(0.2)
    original_atomic_save(data)

so._atomic_save = delayed_atomic_save

while not start_file.exists():
    time.sleep(0.01)

result = asyncio.run(session_claim_impl(SessionClaimInput(
    session_id=session_id,
    surface="dashboard-pty",
    pid=pid,
    cli_id="claude",
)))
print(result)
"""

    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(reg), str(start_file), f"sess{i}", str(100 + i)],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(4)
    ]
    start_file.write_text("go", encoding="utf-8")

    for process in processes:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr or stdout
        assert json.loads(stdout)["ok"] is True

    saved = json.loads(reg.read_text(encoding="utf-8"))
    assert sorted(saved) == ["sess0", "sess1", "sess2", "sess3"]
