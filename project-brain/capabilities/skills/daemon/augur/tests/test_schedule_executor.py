"""
Tests for schedule_executor — Fork 4 (ADR-807).

A scheduled action is an action in ``{skill}/augur/actions.yaml`` that carries a
``schedule:`` cadence block. The DEFINITION (cadence + what to run) lives in the
version-controlled action file; the COMPUTED runtime state
(``next_run``/``last_run``/``run_count``/``last_result``) lives in
``state/schedules/{skill}__{action_id}.yaml`` and is NEVER written back into
``augur/actions.yaml``.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import src.config.paths as config_paths
import yaml


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPTS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "schedule_executor.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location("schedule_executor", SCRIPTS_PATH)
schedule_executor = importlib.util.module_from_spec(_spec)
sys.modules["schedule_executor"] = schedule_executor
assert _spec.loader is not None
_spec.loader.exec_module(schedule_executor)

from src.lib.actions.action_schema import Action  # noqa: E402


def test_standalone_skill_source_fallback_does_not_include_repo_root_skills():
    """The import-error fallback must not scan the retired repo-root skills directory."""
    source = SCRIPTS_PATH.read_text(encoding="utf-8")
    retired_root = "root / " + '"skills"'

    assert retired_root not in source


def test_execute_fast_action_is_not_used_by_scheduler():
    """The scheduler no longer POSTs execute-fast-action (Fork 4)."""
    source = SCRIPTS_PATH.read_text(encoding="utf-8")
    assert "execute-fast-action" not in source


@pytest.fixture
def daemon_layout(tmp_path, monkeypatch):
    skills_dir = tmp_path / "project-brain" / "capabilities" / "skills"
    skill_dir = skills_dir / "daemon"
    augur_dir = skill_dir / "augur"
    state_dir = tmp_path / "state" / "schedules"

    monkeypatch.setenv("AUGUR_ROOT", str(tmp_path))
    config_paths._skill_to_bundle_cache = None
    monkeypatch.setattr(
        schedule_executor,
        "get_managed_skill_source_dirs",
        lambda _project_root=None: [skills_dir],
    )
    monkeypatch.setattr(
        schedule_executor,
        "_state_schedules_dir",
        lambda: state_dir,
    )
    monkeypatch.setattr(schedule_executor, "is_skill_enabled", lambda *_a, **_k: True)

    augur_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)

    return {
        "skill_dir": skill_dir,
        "augur_dir": augur_dir,
        "state_dir": state_dir,
    }


def _write_actions_yaml(augur_dir: Path, actions: list[dict]) -> None:
    (augur_dir / "actions.yaml").write_text(
        yaml.safe_dump({"actions": actions}, sort_keys=False), encoding="utf-8"
    )


class TestScheduleDiscovery:
    def test_discovers_only_actions_with_schedule_block(self, daemon_layout):
        _write_actions_yaml(
            daemon_layout["augur_dir"],
            [
                {
                    "id": "run-nightly",
                    "label": "Run Nightly",
                    "kind": "mcp",
                    "dispatch": "fire",
                    "mcp_tool": "reindex-browse-category",
                    "surfaces": ["page"],
                    "args": {"category": "skills"},
                    "schedule": {"frequency": "daily", "time": "09:00", "timezone": "UTC"},
                },
                {
                    "id": "no-schedule",
                    "label": "No Schedule",
                    "kind": "mcp",
                    "dispatch": "fire",
                    "mcp_tool": "some-tool",
                    "surfaces": ["page"],
                },
            ],
        )

        schedules = schedule_executor.discover_schedules()

        assert len(schedules) == 1
        sched = schedules[0]
        assert sched["skill"] == "daemon"
        assert sched["action_id"] == "run-nightly"
        assert sched["schedule"] == {
            "frequency": "daily",
            "time": "09:00",
            "timezone": "UTC",
        }
        assert isinstance(sched["action"], Action)
        assert sched["action"].mcp_tool == "reindex-browse-category"
        assert sched["_state_path"] == str(
            daemon_layout["state_dir"] / "daemon__run-nightly.yaml"
        )

    def test_disabled_skill_is_skipped(self, daemon_layout, monkeypatch):
        _write_actions_yaml(
            daemon_layout["augur_dir"],
            [
                {
                    "id": "run-nightly",
                    "label": "Run Nightly",
                    "kind": "mcp",
                    "dispatch": "fire",
                    "mcp_tool": "reindex-browse-category",
                    "surfaces": ["page"],
                    "schedule": {"frequency": "daily", "time": "09:00", "timezone": "UTC"},
                },
            ],
        )
        monkeypatch.setattr(schedule_executor, "is_skill_enabled", lambda *_a, **_k: False)

        assert schedule_executor.discover_schedules() == []


class TestRuntimeState:
    def test_is_due_seeds_next_run_in_state_file_when_missing(self, daemon_layout):
        schedule = {
            "skill": "daemon",
            "action_id": "run-nightly",
            "schedule": {"frequency": "daily", "time": "09:00", "timezone": "UTC"},
            "_state_path": str(daemon_layout["state_dir"] / "daemon__run-nightly.yaml"),
        }
        state_path = Path(schedule["_state_path"])
        assert not state_path.exists()

        # No state yet → not due, but a next_run gets seeded.
        schedule_executor.is_due(schedule)

        assert state_path.exists()
        state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        assert "next_run" in state and state["next_run"]

    def test_is_due_reads_next_run_from_state_file(self, daemon_layout):
        state_path = daemon_layout["state_dir"] / "daemon__run-nightly.yaml"
        past = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        state_path.write_text(yaml.safe_dump({"next_run": past}), encoding="utf-8")

        schedule = {
            "skill": "daemon",
            "action_id": "run-nightly",
            "schedule": {"frequency": "daily", "time": "09:00", "timezone": "UTC"},
            "_state_path": str(state_path),
        }

        assert schedule_executor.is_due(schedule) is True

        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        state_path.write_text(yaml.safe_dump({"next_run": future}), encoding="utf-8")
        assert schedule_executor.is_due(schedule) is False

    def test_update_writes_state_file_not_action_yaml(self, daemon_layout):
        _write_actions_yaml(
            daemon_layout["augur_dir"],
            [
                {
                    "id": "run-nightly",
                    "label": "Run Nightly",
                    "kind": "mcp",
                    "dispatch": "fire",
                    "mcp_tool": "reindex-browse-category",
                    "surfaces": ["page"],
                    "schedule": {"frequency": "daily", "time": "09:00", "timezone": "UTC"},
                },
            ],
        )
        actions_yaml = daemon_layout["augur_dir"] / "actions.yaml"
        before = actions_yaml.read_text(encoding="utf-8")

        state_path = daemon_layout["state_dir"] / "daemon__run-nightly.yaml"
        schedule = {
            "skill": "daemon",
            "action_id": "run-nightly",
            "schedule": {"frequency": "daily", "time": "09:00", "timezone": "UTC"},
            "_state_path": str(state_path),
        }

        schedule_executor.update_schedule_file(
            schedule,
            {"status": "success", "message": "ok", "duration_ms": 42},
        )

        # Action yaml must be untouched.
        assert actions_yaml.read_text(encoding="utf-8") == before
        assert "last_run" not in before

        # State file carries runtime fields.
        state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        assert state["run_count"] == 1
        assert state["last_result"]["status"] == "success"
        assert state["last_run"]
        assert state["next_run"]


class TestActionResolution:
    def test_resolve_action_returns_action_in_hand(self, daemon_layout):
        action = Action(
            id="run-nightly",
            label="Run Nightly",
            kind="mcp",
            dispatch="fire",
            mcp_tool="reindex-browse-category",
        )
        schedule = {"skill": "daemon", "action_id": "run-nightly", "action": action}

        resolved = schedule_executor.resolve_action(schedule)
        assert resolved is action

    def test_resolve_action_orphan_guard(self, daemon_layout):
        schedule = {"skill": "daemon", "action_id": "missing", "action": None}
        assert schedule_executor.resolve_action(schedule) is None


class TestActionExecution:
    def test_execute_fire_action_posts_declared_mcp_tool(self, monkeypatch):
        calls = []

        def fake_http_post(url, payload, timeout=schedule_executor.REQUEST_TIMEOUT):
            calls.append((url, payload, timeout))
            return {"success": True, "message": "ok"}

        monkeypatch.setattr(schedule_executor, "DASHBOARD_URL", "http://localhost:3999")
        monkeypatch.setattr(schedule_executor, "_http_post", fake_http_post)

        action = Action(
            id="reindex-skills",
            label="Reindex Skills",
            kind="mcp",
            dispatch="fire",
            mcp_tool="reindex-browse-category",
            args={"category": "skills"},
        )
        result = schedule_executor.execute_action(
            {"action_id": "reindex-skills"},
            action,
        )

        assert result["status"] == "success"
        assert calls[0][0] == "http://localhost:3999/api/mcp/tool"
        assert calls[0][1] == {
            "tool": "reindex-browse-category",
            "args": {
                "category": "skills",
                "context": {
                    "source": "schedule_executor",
                    "action_id": "reindex-skills",
                },
            },
        }

    def test_execute_fire_action_without_mcp_tool_is_skipped(self, monkeypatch):
        monkeypatch.setattr(
            schedule_executor,
            "_http_post",
            lambda *_a, **_k: pytest.fail("must not POST when mcp_tool is missing"),
        )

        action = Action(
            id="bare-fire",
            label="Bare Fire",
            kind="mcp",
            dispatch="fire",
            mcp_tool=None,
        )
        result = schedule_executor.execute_action(
            {"action_id": "bare-fire"},
            action,
        )

        assert result["status"] in {"error", "skipped"}

    def test_execute_accepts_action_dict_without_mcp_tool_is_skipped(self, monkeypatch):
        """A dict-shaped action (no mcp_tool) is also rejected without a POST."""
        monkeypatch.setattr(
            schedule_executor,
            "_http_post",
            lambda *_a, **_k: pytest.fail("must not POST when mcp_tool is missing"),
        )

        result = schedule_executor.execute_action(
            {"action_id": "demo-action"},
            {"id": "demo-action", "dispatch": "fire", "args": {"category": "skills"}},
        )

        assert result["status"] in {"error", "skipped"}
