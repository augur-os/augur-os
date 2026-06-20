# skills/auto-agent-digest/augur/tests/test_compiler.py
"""Tests for the digest compiler (OpsCommand entry point)."""

import sys
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts" / "ops")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import json
from datetime import datetime, timezone

import pytest

from agent_digest.compile_digest import (
    compile_hot_tier,
    compile_warm_tier,
    format_hot_section,
    format_warm_section,
)


@pytest.fixture
def directive_map() -> dict[str, dict]:
    return {
        "no_fs_in_dashboard": {
            "label": "NO fs/spawn in dashboard",
            "sources": ["rule_11", "ADR-453"],
            "description": "All data via useMcpQuery/useMcpMutation. No import fs.",
        },
        "no_emojis": {
            "label": "NO emojis",
            "sources": ["preference"],
            "description": "Unless user explicitly requests them.",
        },
    }


@pytest.fixture
def sample_events() -> list[dict]:
    return [
        {"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
        {"ts": "2026-03-24T03:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
        {"ts": "2026-03-23T10:00:00Z", "source": "session_log", "type": "user_correction", "rule": "no_emojis"},
    ]


def test_compile_hot_tier(sample_events, directive_map):
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    lines = compile_hot_tier(sample_events, directive_map, reference_date=ref)
    assert len(lines) >= 2
    assert "NO fs/spawn" in lines[0] or "NO emojis" in lines[0]


def test_compile_hot_empty():
    lines = compile_hot_tier([], {})
    assert len(lines) == 1
    assert "clean this week" in lines[0].lower()


def test_format_hot_section(sample_events, directive_map):
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    section = format_hot_section(sample_events, directive_map, reference_date=ref)
    assert "## Hot Directives" in section
    assert "auto-generated" in section
    assert "do not edit manually" in section


def test_compile_warm_tier_with_adrs(tmp_path):
    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    (adr_dir / "ADR-490-dashboard-imports.md").write_text(
        "---\ntitle: Dashboard import architecture\nstatus: accepted\ndate: 2026-03-18\n---\n\nSplit imports into @/ and @skill/.\n"
    )
    (adr_dir / "ADR-100-old-decision.md").write_text(
        "---\ntitle: Old decision\nstatus: accepted\ndate: 2025-01-01\n---\n\nSomething old.\n"
    )
    ref = datetime(2026, 3, 24, tzinfo=timezone.utc)
    lines = compile_warm_tier(adr_dir, days=30, reference_date=ref)
    assert len(lines) == 1
    assert "ADR-490" in lines[0]


def test_format_warm_section(tmp_path):
    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    (adr_dir / "ADR-490-dashboard-imports.md").write_text(
        "---\ntitle: Dashboard import architecture\nstatus: accepted\ndate: 2026-03-18\n---\n\nContent.\n"
    )
    ref = datetime(2026, 3, 24, tzinfo=timezone.utc)
    section = format_warm_section(adr_dir, reference_date=ref)
    assert "## Recent Decisions" in section
    assert "auto-generated" in section


def test_hot_section_within_token_budget(directive_map):
    events = []
    for i in range(50):
        events.append({
            "ts": "2026-03-24T02:00:00Z",
            "source": "git",
            "type": "pattern_violation",
            "rule": f"rule_{i}",
        })
    big_map = {f"rule_{i}": {"label": f"Rule {i} violation with a long description", "sources": [f"src_{i}"], "description": f"Long description for rule {i} to consume token budget"} for i in range(50)}
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    section = format_hot_section(events, big_map, reference_date=ref)
    from agent_digest.scoring import estimate_tokens
    body_lines = [l for l in section.split("\n") if l.startswith("- ")]
    assert len(body_lines) < 50  # budget truncated
