# skills/auto-agent-digest/augur/tests/test_scoring.py
"""Tests for the directive scoring engine."""

import sys
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts" / "ops")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from datetime import datetime, timezone

import pytest

from agent_digest.scoring import (
    TOKEN_BUDGET_HOT,
    estimate_tokens,
    format_hot_directive,
    recency_decay,
    score_directives,
)


def test_recency_decay_recent():
    assert recency_decay(days_old=1) == 1.0


def test_recency_decay_mid():
    assert recency_decay(days_old=4) == 0.7


def test_recency_decay_old():
    assert recency_decay(days_old=6) == 0.4


def test_recency_decay_expired():
    assert recency_decay(days_old=8) == 0.0


def test_score_single_git_violation():
    events = [
        {"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
    ]
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    scores = score_directives(events, reference_date=ref)
    assert "no_fs_in_dashboard" in scores
    assert scores["no_fs_in_dashboard"]["score"] == 3.0


def test_score_user_correction_higher():
    events = [
        {"ts": "2026-03-24T02:00:00Z", "source": "session_log", "type": "user_correction", "rule": "no_emojis"},
    ]
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    scores = score_directives(events, reference_date=ref)
    assert scores["no_emojis"]["score"] == 5.0


def test_score_manual_flag_with_boost():
    events = [
        {"ts": "2026-03-24T02:00:00Z", "source": "manual", "type": "flag", "rule": "no_central_registry", "priority": "boost"},
    ]
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    scores = score_directives(events, reference_date=ref)
    assert scores["no_central_registry"]["score"] == 4.0 * 1.5


def test_score_repeated_violation_boost():
    events = [
        {"ts": "2026-03-24T01:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
        {"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
        {"ts": "2026-03-24T03:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
    ]
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    scores = score_directives(events, reference_date=ref)
    assert scores["no_fs_in_dashboard"]["score"] == pytest.approx(11.7)


def test_score_multiple_directives_ranked():
    events = [
        {"ts": "2026-03-24T02:00:00Z", "source": "session_log", "type": "user_correction", "rule": "no_emojis"},
        {"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
    ]
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    scores = score_directives(events, reference_date=ref)
    assert scores["no_emojis"]["score"] > scores["no_fs_in_dashboard"]["score"]


def test_format_hot_directive():
    line = format_hot_directive("NO fs/spawn in dashboard", ["rule_11", "ADR-453"], 3)
    assert "NO fs/spawn in dashboard" in line
    assert "rule_11" in line
    assert "3x" in line


def test_estimate_tokens():
    text = "This is a test line with some words in it."
    tokens = estimate_tokens(text)
    assert 5 < tokens < 20


def test_token_budget_constant():
    assert TOKEN_BUDGET_HOT == 500
