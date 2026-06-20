from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path

import yaml

from src.lib.ops_protocol import OpsContext, write_report

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
MCP_ROOT = PROJECT_ROOT / "src" / "mcp"
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))


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


def test_write_report_uses_runtime_state(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setenv("AUGUR_STATE", str(state_dir))

    report_path = write_report(OpsContext(project_root=tmp_path), "sample.json", {"ok": True})

    assert report_path == state_dir / "reports" / "sample.json"
    assert json.loads(report_path.read_text()) == {"ok": True}


def test_augur_mcp_logging_uses_logs_dir(monkeypatch, tmp_path):
    logs_dir = tmp_path / "logs"
    monkeypatch.delenv("AUGUR_MCP_LOG_FILE", raising=False)
    monkeypatch.delenv("AUGUR_MCP_LOG_DIR", raising=False)
    monkeypatch.setenv("AUGUR_LOGS", str(logs_dir))

    import src.mcp.augur_shared.logging as augur_logging

    log_file = augur_logging._resolve_log_file()

    assert log_file == logs_dir / "augur_mcp.log"


def test_page_telemetry_uses_runtime_state(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setenv("AUGUR_STATE", str(state_dir))

    import src.mcp.augur_framework.tools.infrastructure.page_telemetry as page_telemetry

    page_telemetry = importlib.reload(page_telemetry)
    page_telemetry.savePageMetric(
        {
            "path": "/settings",
            "metric": "load",
            "duration": 0.42,
            "timestamp": "2026-03-11T10:00:00Z",
        }
    )

    metrics_dir = state_dir / "metrics" / "page-metrics"
    assert page_telemetry.METRICS_DIR == metrics_dir
    metric_files = list(metrics_dir.glob("metrics_*.json"))
    assert len(metric_files) == 1
    assert '"path": "/settings"' in metric_files[0].read_text(encoding="utf-8")


def test_daemon_loop_tools_read_runtime_state(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    state_dir = tmp_path / "state"
    adaptive_dir = state_dir / "adaptive"
    adaptive_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / "plugins" / "observability" / "skills" / "daemon" / "augur").mkdir(
        parents=True, exist_ok=True
    )
    (repo_root / "config" / "system").mkdir(parents=True, exist_ok=True)

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
        )
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
        )
    )
    job_dir = state_dir / "jobs" / "20260311-100000-000-hardening"
    job_dir.mkdir(parents=True)
    (job_dir / "meta.json").write_text(
        json.dumps(
            {
                "job_id": job_dir.name,
                "kind": "loop",
                "name": "hardening",
                "created_at": "2026-03-11T10:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "type": "journal_record",
                "loop": "hardening",
                "timestamp": "2026-03-11T10:00:00Z",
                "action": "scan",
                "category": "pages",
                "result": "success",
                "duration_ms": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_STATE", str(state_dir))
    from src.config import paths as config_paths

    config_paths._skill_to_bundle_cache = None

    daemon_mcp = importlib.import_module(
        "skills.daemon.scripts.mcp"
    )
    loop_tools = importlib.import_module("skills.daemon.scripts.mcp._loops")
    monkeypatch.setattr(loop_tools, "get_project_root", lambda: repo_root)
    monkeypatch.setattr(loop_tools, "get_runtime_dir", lambda: state_dir)

    mcp = _FakeMCP()
    daemon_mcp.register_tools(mcp, _passthrough_interceptor, _FakeMetrics())

    status_payload = json.loads(asyncio.run(mcp.tools["get-daemon-loop-status"]()))
    history_payload = json.loads(asyncio.run(mcp.tools["get-daemon-loop-history"]()))

    assert status_payload["success"] is True
    assert status_payload["loops"][0]["name"] == "hardening"
    assert status_payload["loops"][0]["budgetRemaining"] == 2
    assert status_payload["loops"][0]["lastRun"] == "2026-03-11T10:00:00Z"

    assert history_payload["success"] is True
    assert history_payload["total"] == 1
    assert history_payload["events"][0]["loop"] == "hardening"


def test_daemon_loop_tools_do_not_imply_daemon_owner_without_metadata(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    state_dir = tmp_path / "state"
    adaptive_dir = state_dir / "adaptive"
    adaptive_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / "config" / "system").mkdir(parents=True, exist_ok=True)
    (repo_root / "project-brain" / "capabilities" / "skills").mkdir(parents=True, exist_ok=True)

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
    (adaptive_dir / "trust_state.json").write_text(json.dumps({"loops": {}}), encoding="utf-8")
    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_STATE", str(state_dir))

    daemon_mcp = importlib.import_module("skills.daemon.scripts.mcp")
    loop_tools = importlib.import_module("skills.daemon.scripts.mcp._loops")
    monkeypatch.setattr(loop_tools, "get_project_root", lambda: repo_root)
    monkeypatch.setattr(loop_tools, "get_runtime_dir", lambda: state_dir)

    mcp = _FakeMCP()
    daemon_mcp.register_tools(mcp, _passthrough_interceptor, _FakeMetrics())

    status_payload = json.loads(asyncio.run(mcp.tools["get-daemon-loop-status"]()))

    assert status_payload["loops"][0]["owner"] == "unknown"
    assert status_payload["loops"][0]["ownerDetail"] == "no discovered scheduler metadata"
