"""Tests for adaptive/incidents.py — incident normalization and aggregation.

Validates incident fingerprinting from raw error messages, aggregation to an
index file, and the recurrence promotion logic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.ai.scripts.adaptive.incidents import (
    IncidentRecord,
    aggregate_incidents,
    normalize_incident,
    should_promote_incident,
    _load_index,
    _merge_unique,
)


# ---------------------------------------------------------------------------
# normalize_incident
# ---------------------------------------------------------------------------


class TestNormalizeIncident:
    def test_empty_message_returns_none(self):
        result = normalize_incident("", command="test")
        assert result is None

    def test_port_collision(self):
        result = normalize_incident(
            "No available worktree ports in range 3100-3199",
            command="dev-merge",
        )
        assert result is not None
        assert result.fingerprint == "worktree/bootstrap/port-collision"
        assert result.severity == "high"

    def test_lock_contention(self):
        result = normalize_incident(
            "MCP lock contention: bridge already acquired",
            command="dev-test",
        )
        assert result is not None
        assert result.fingerprint == "worktree/mcp/lock-contention"

    def test_augur_root_drift(self):
        result = normalize_incident(
            "AUGUR_ROOT path does not exist: /tmp/gone",
            command="dev-build",
        )
        assert result is not None
        assert result.fingerprint == "worktree/root/env-drift"

    def test_missing_runtime(self):
        result = normalize_incident(
            "Runtime directory not available",
            command="daemon",
        )
        assert result is not None
        assert result.fingerprint == "worktree/bootstrap/missing-runtime"

    def test_missing_venv(self):
        result = normalize_incident(
            "venv python not found at /worktree/.venv/bin/python",
            command="dev-test",
        )
        assert result is not None
        assert result.fingerprint == "worktree/bootstrap/missing-venv"

    def test_unrecognized_message_returns_none(self):
        result = normalize_incident(
            "Something completely unrelated",
            command="test",
        )
        assert result is None

    def test_node_modules_missing(self):
        result = normalize_incident(
            "Error: node_modules not found in dashboard",
            command="dev-build",
        )
        assert result is not None
        assert result.fingerprint == "worktree/bootstrap/missing-dashboard-node-modules"


# ---------------------------------------------------------------------------
# should_promote_incident
# ---------------------------------------------------------------------------


class TestShouldPromote:
    def test_under_threshold_not_promoted(self):
        summary = {"occurrences": 1, "commands": ["a"], "worktrees": ["/w1"]}
        assert should_promote_incident(summary) is False

    def test_three_occurrences_promoted(self):
        summary = {"occurrences": 3, "commands": ["a"], "worktrees": ["/w1"]}
        assert should_promote_incident(summary) is True

    def test_two_commands_promoted(self):
        summary = {"occurrences": 1, "commands": ["a", "b"], "worktrees": ["/w1"]}
        assert should_promote_incident(summary) is True

    def test_two_worktrees_promoted(self):
        summary = {"occurrences": 1, "commands": ["a"], "worktrees": ["/w1", "/w2"]}
        assert should_promote_incident(summary) is True


# ---------------------------------------------------------------------------
# _merge_unique
# ---------------------------------------------------------------------------


class TestMergeUnique:
    def test_adds_new_value(self):
        result = _merge_unique(["a", "b"], "c")
        assert result == ["a", "b", "c"]

    def test_deduplicates(self):
        result = _merge_unique(["a", "b"], "a")
        assert result == ["a", "b"]

    def test_respects_limit(self):
        result = _merge_unique(["a", "b", "c"], "d", limit=3)
        assert len(result) == 3
        assert "d" in result


# ---------------------------------------------------------------------------
# aggregate_incidents
# ---------------------------------------------------------------------------


class TestAggregateIncidents:
    def test_creates_index_and_events(self, tmp_path: Path):
        runtime = tmp_path / "runtime"
        incident = IncidentRecord(
            fingerprint="test/fingerprint",
            category="test",
            severity="medium",
            owner_path="scripts/test.sh",
            message="Test failure",
            command="test-cmd",
            first_seen_at="2026-01-01T00:00:00",
            last_seen_at="2026-01-01T00:00:00",
        )
        index_path = aggregate_incidents(runtime, [incident])
        assert index_path.exists()

        index_data = json.loads(index_path.read_text())
        assert "test/fingerprint" in index_data["incidents"]
        assert "generatedAt" in index_data

        events_path = runtime / "command-evolution" / "incidents" / "events.jsonl"
        assert events_path.exists()

    def test_merges_recurring_incidents(self, tmp_path: Path):
        runtime = tmp_path / "runtime"
        inc1 = IncidentRecord(
            fingerprint="fp",
            category="test",
            severity="medium",
            owner_path="test.sh",
            message="Error 1",
            command="cmd-a",
            first_seen_at="2026-01-01T00:00:00",
            last_seen_at="2026-01-01T00:00:00",
            commands=["cmd-a"],
        )
        inc2 = IncidentRecord(
            fingerprint="fp",
            category="test",
            severity="medium",
            owner_path="test.sh",
            message="Error 1 again",
            command="cmd-b",
            first_seen_at="2026-01-02T00:00:00",
            last_seen_at="2026-01-02T00:00:00",
            commands=["cmd-b"],
        )
        aggregate_incidents(runtime, [inc1])
        aggregate_incidents(runtime, [inc2])

        index_path = runtime / "command-evolution" / "incidents" / "index.json"
        data = json.loads(index_path.read_text())
        fp_data = data["incidents"]["fp"]
        assert fp_data["occurrences"] == 2
        assert "cmd-a" in fp_data["commands"]
        assert "cmd-b" in fp_data["commands"]

    def test_does_not_promote_marker_into_json_owner(self, tmp_path: Path):
        runtime = tmp_path / "runtime"
        owner = tmp_path / ".claude" / "settings.json"
        owner.parent.mkdir(parents=True)
        owner.write_text(json.dumps({"enabledPlugins": {"example": True}}, indent=2), encoding="utf-8")

        inc1 = IncidentRecord(
            fingerprint="worktree/bootstrap/json-owner",
            category="bootstrap",
            severity="low",
            owner_path=".claude/settings.json",
            message="Expected per-worktree setup notice",
            command="cmd-a",
            first_seen_at="2026-01-01T00:00:00",
            last_seen_at="2026-01-01T00:00:00",
            commands=["cmd-a"],
        )
        inc2 = IncidentRecord(
            fingerprint="worktree/bootstrap/json-owner",
            category="bootstrap",
            severity="low",
            owner_path=".claude/settings.json",
            message="Expected per-worktree setup notice",
            command="cmd-b",
            first_seen_at="2026-01-02T00:00:00",
            last_seen_at="2026-01-02T00:00:00",
            commands=["cmd-b"],
        )

        aggregate_incidents(runtime, [inc1])
        aggregate_incidents(runtime, [inc2])

        assert json.loads(owner.read_text(encoding="utf-8")) == {
            "enabledPlugins": {"example": True}
        }
        index_path = runtime / "command-evolution" / "incidents" / "index.json"
        data = json.loads(index_path.read_text())
        assert "promoted_todo_path" not in data["incidents"]["worktree/bootstrap/json-owner"]


# ---------------------------------------------------------------------------
# _load_index
# ---------------------------------------------------------------------------


class TestLoadIndex:
    def test_missing_file_returns_default(self, tmp_path: Path):
        result = _load_index(tmp_path / "nonexistent.json")
        assert result == {"incidents": {}, "recurringIncidents": []}

    def test_corrupt_json_returns_default(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json!", encoding="utf-8")
        result = _load_index(bad)
        assert result == {"incidents": {}, "recurringIncidents": []}
