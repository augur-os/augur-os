"""Tests for augur/lib/token_estimator.py — token estimation utilities.

Validates token counting, budget checking, and workflow cost estimation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
AI_BRIDGE_AUGUR = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(AI_BRIDGE_AUGUR) not in sys.path:
    sys.path.insert(0, str(AI_BRIDGE_AUGUR))

from src.lib.ai.token_estimator import (
    estimate_tokens,
    estimate_file_tokens,
    estimate_module_tokens,
    check_token_budget,
    estimate_phase_tokens,
    can_fit_in_budget,
    format_token_report,
    estimate_cv_load_tokens,
    estimate_total_workflow_tokens,
)


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_normal_text(self):
        result = estimate_tokens("Hello world, this is a test.")
        assert result > 0

    def test_special_chars_add_tokens(self):
        text_no_special = "hello world"
        text_with_special = "hello {world} [test]"
        tokens_plain = estimate_tokens(text_no_special)
        tokens_special = estimate_tokens(text_with_special)
        assert tokens_special > tokens_plain

    def test_whitespace_normalized(self):
        result = estimate_tokens("hello    \n\n\n   world")
        # Should be similar to a clean string
        assert result > 0


# ---------------------------------------------------------------------------
# estimate_file_tokens
# ---------------------------------------------------------------------------


class TestEstimateFileTokens:
    def test_existing_file(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_text("Hello world " * 100, encoding="utf-8")
        result = estimate_file_tokens(str(f))
        assert result > 0

    def test_nonexistent_file(self, tmp_path: Path):
        result = estimate_file_tokens(str(tmp_path / "missing.txt"))
        assert result == 0


# ---------------------------------------------------------------------------
# estimate_module_tokens
# ---------------------------------------------------------------------------


class TestEstimateModuleTokens:
    def test_multiple_modules(self):
        modules = {
            "module_a": "Short content",
            "module_b": "A much longer piece of content " * 50,
        }
        result = estimate_module_tokens(modules)
        assert "module_a" in result
        assert "module_b" in result
        assert result["module_b"] > result["module_a"]


# ---------------------------------------------------------------------------
# check_token_budget
# ---------------------------------------------------------------------------


class TestCheckTokenBudget:
    def test_ok_status(self):
        result = check_token_budget(50000)
        assert result["status"] == "OK"
        assert result["used"] == 50000
        assert result["remaining"] == 140000

    def test_warning_status(self):
        result = check_token_budget(120000)
        assert result["status"] == "WARNING"

    def test_critical_status(self):
        result = check_token_budget(160000)
        assert result["status"] == "CRITICAL"

    def test_custom_max(self):
        result = check_token_budget(80, max_tokens=100)
        assert result["status"] == "WARNING"
        assert result["max"] == 100


# ---------------------------------------------------------------------------
# estimate_phase_tokens
# ---------------------------------------------------------------------------


class TestEstimatePhaseTokens:
    def test_known_phases(self):
        assert estimate_phase_tokens("init") == 5000
        assert estimate_phase_tokens("research") == 15000

    def test_unknown_phase_returns_default(self):
        assert estimate_phase_tokens("unknown_phase") == 10000


# ---------------------------------------------------------------------------
# can_fit_in_budget
# ---------------------------------------------------------------------------


class TestCanFitInBudget:
    def test_fits(self):
        assert can_fit_in_budget(100000, 50000) is True

    def test_does_not_fit(self):
        assert can_fit_in_budget(180000, 20000) is False

    def test_safety_margin(self):
        # 180000 + 5000 = 185000, with margin 10000 needs <= 180000
        assert can_fit_in_budget(175000, 5000) is True
        assert can_fit_in_budget(180000, 5000) is False


# ---------------------------------------------------------------------------
# format_token_report
# ---------------------------------------------------------------------------


class TestFormatTokenReport:
    def test_contains_key_fields(self):
        data = check_token_budget(75000)
        report = format_token_report(data)
        assert "75,000" in report
        assert "OK" in report or "WARNING" in report or "CRITICAL" in report


# ---------------------------------------------------------------------------
# estimate_cv_load_tokens
# ---------------------------------------------------------------------------


class TestEstimateCvLoad:
    def test_default_size(self):
        assert estimate_cv_load_tokens(4) == 8000

    def test_custom_size(self):
        assert estimate_cv_load_tokens(2, avg_cv_size=3000) == 6000


# ---------------------------------------------------------------------------
# estimate_total_workflow_tokens
# ---------------------------------------------------------------------------


class TestEstimateTotalWorkflow:
    def test_without_research(self):
        result = estimate_total_workflow_tokens(cv_count=2)
        assert "breakdown" in result
        assert "total" in result
        assert "research" not in result["breakdown"]

    def test_with_research(self):
        result = estimate_total_workflow_tokens(cv_count=2, is_new_company=True)
        assert "research" in result["breakdown"]
        assert result["total"] > estimate_total_workflow_tokens(cv_count=2)["total"]
