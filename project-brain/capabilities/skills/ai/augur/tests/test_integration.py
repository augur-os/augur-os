"""Integration tests for the full agent-digest pipeline."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts" / "ops")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import pytest

from agent_digest.compile_digest import (
    compile_hot_tier,
    format_hot_section,
    format_warm_section,
)
from agent_digest.journal import append_event, read_events
from agent_digest.scoring import TOKEN_BUDGET_HOT, estimate_tokens


@pytest.fixture
def journal_dir(tmp_path):
    d = tmp_path / "agent-digest"
    d.mkdir()
    return d


@pytest.fixture
def directive_map():
    return {
        "no_fs_in_dashboard": {"label": "NO fs/spawn in dashboard", "sources": ["rule_11"], "description": "All data via MCP."},
        "no_emojis": {"label": "NO emojis", "sources": ["preference"], "description": "Unless user explicitly requests."},
        "no_suppression": {"label": "NO error suppression", "sources": ["rule_5"], "description": "Fix root cause."},
    }


def test_cold_start_empty_journal(directive_map):
    """First run with no events produces empty-state message."""
    lines = compile_hot_tier([], directive_map)
    assert len(lines) == 1
    assert "clean this week" in lines[0].lower()


def test_full_pipeline_journal_to_digest(journal_dir, directive_map):
    """Events -> journal -> read -> score -> compile -> formatted section."""
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)

    events_to_add = [
        {"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard", "evidence": "import fs"},
        {"ts": "2026-03-24T03:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard", "evidence": "execSync"},
        {"ts": "2026-03-23T10:00:00Z", "source": "session_log", "type": "user_correction", "rule": "no_emojis", "signal": "stop adding emojis"},
        {"ts": "2026-03-24T08:00:00Z", "source": "manual", "type": "flag", "rule": "no_suppression", "priority": "boost"},
    ]
    for event in events_to_add:
        append_event(journal_dir, event)

    since = datetime(2026, 3, 17, tzinfo=timezone.utc)
    events = read_events(journal_dir, since=since)
    assert len(events) == 4

    section = format_hot_section(events, directive_map, reference_date=ref)
    assert "## Hot Directives" in section
    assert "auto-generated" in section
    assert "NO" in section


def test_budget_enforcement_50_violations(directive_map):
    """50 unique violations must be truncated by token budget."""
    events = []
    big_map = {}
    for i in range(50):
        events.append({"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": f"rule_{i}"})
        big_map[f"rule_{i}"] = {"label": f"A verbose directive label number {i} with description", "sources": ["src"], "description": f"Detailed description of rule {i}"}

    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    lines = compile_hot_tier(events, big_map, reference_date=ref)
    total_tokens = sum(estimate_tokens(l) for l in lines)
    assert total_tokens <= TOKEN_BUDGET_HOT + 50  # small buffer for overflow line
    assert len(lines) < 50


def test_warm_tier_filters_old_adrs(tmp_path):
    """Warm tier excludes ADRs older than 30 days."""
    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    (adr_dir / "ADR-490-new.md").write_text("---\ntitle: New decision\nstatus: accepted\ndate: 2026-03-18\n---\nContent.\n")
    (adr_dir / "ADR-100-old.md").write_text("---\ntitle: Old decision\nstatus: accepted\ndate: 2025-06-01\n---\nContent.\n")

    ref = datetime(2026, 3, 24, tzinfo=timezone.utc)
    section = format_warm_section(adr_dir, reference_date=ref)
    assert "ADR-490" in section
    assert "ADR-100" not in section
