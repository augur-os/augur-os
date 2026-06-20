"""MCP loop readers can use ledger-derived journal records."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
MCP_ROOT = PROJECT_ROOT / "src" / "mcp"
for path in (PROJECT_ROOT, SCRIPTS_DIR, MCP_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from job_ledger import job_record


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, *, name: str, annotations: dict):
        del annotations

        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


class _FakeMetrics:
    def track_tool(self, name: str, skill: str | None = None) -> None:
        del name, skill


def _passthrough_interceptor(fn):
    return fn


def _write_loop_job(jobs: Path) -> None:
    job_dir = jobs / "20260516-100000-000-hardening"
    job_dir.mkdir(parents=True)
    (job_dir / "meta.json").write_text(
        json.dumps(
            {
                "job_id": job_dir.name,
                "kind": "loop",
                "name": "hardening",
                "submitter": "pytest",
                "args": {"mode": "run"},
                "created_at": "2026-05-16T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "type": "journal_record",
                "state": "running",
                "loop": "hardening",
                "action": "scan",
                "category": "pages",
                "result": "success",
                "timestamp": "2026-05-16T10:00:00+00:00",
                "duration_ms": 10,
                "t": "2026-05-16T10:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_mcp_loop_status_and_history_use_ledger_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    state_dir = tmp_path / "state"
    adaptive_dir = state_dir / "adaptive"
    jobs_dir = state_dir / "jobs"
    adaptive_dir.mkdir(parents=True)
    (repo_root / "config" / "system").mkdir(parents=True)
    (repo_root / "project-brain" / "capabilities" / "skills").mkdir(parents=True)
    (repo_root / "config" / "system" / "adaptive_loops.yaml").write_text(
        yaml.safe_dump(
            {
                "loops": {
                    "hardening": {
                        "enabled": True,
                        "budget": 3,
                        "categories": {"pages": {}},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (adaptive_dir / "trust_state.json").write_text(
        json.dumps(
            {
                "loops": {
                    "hardening": {
                        "budget_remaining": 2,
                        "cycle_count": 4,
                        "categories": {
                            "pages": {"consecutive_clean_scans": 7},
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    journal_event = {
        "loop": "hardening",
        "action": "scan",
        "category": "pages",
        "result": "success",
        "timestamp": "2026-05-16T10:00:00+00:00",
        "duration_ms": 10,
    }
    _write_loop_job(jobs_dir)

    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_STATE", str(state_dir))
    monkeypatch.setattr(job_record, "jobs_dir", lambda: jobs_dir)

    import skills.daemon.scripts.mcp as daemon_mcp
    import skills.daemon.scripts.mcp._loops as loop_tools

    monkeypatch.setattr(loop_tools, "get_project_root", lambda: repo_root)
    monkeypatch.setattr(loop_tools, "get_runtime_dir", lambda: state_dir)

    mcp = _FakeMCP()
    daemon_mcp.register_tools(mcp, _passthrough_interceptor, _FakeMetrics())

    status_payload = json.loads(asyncio.run(mcp.tools["get-daemon-loop-status"]()))
    history_payload = json.loads(asyncio.run(mcp.tools["get-daemon-loop-history"]()))

    assert status_payload["success"] is True
    assert status_payload["loops"][0]["lastRun"] == "2026-05-16T10:00:00+00:00"
    assert status_payload["journal"] == [journal_event]
    assert history_payload == {"success": True, "events": [journal_event], "total": 1}
