"""Tests for d0-d1 UI quality checks."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_CHECKS_PATH = SCRIPTS_DIR / "checks.py"
_CHECKS_SPEC = importlib.util.spec_from_file_location("loop_quality_checks_under_test", _CHECKS_PATH)
assert _CHECKS_SPEC and _CHECKS_SPEC.loader
checks = importlib.util.module_from_spec(_CHECKS_SPEC)
sys.modules["loop_quality_checks_under_test"] = checks
_CHECKS_SPEC.loader.exec_module(checks)

# Inline TSX snippets for testing
GOOD_BUTTON = '<button onClick={() => doThing()} className="cursor-pointer px-4 py-2 min-h-[44px]" aria-label="Do thing"><Play className="w-4 h-4" /></button>'
BAD_BUTTON_NO_CURSOR = '<button onClick={() => doThing()} className="px-4 py-2"><Play className="w-4 h-4" /></button>'
BAD_BUTTON_NO_ARIA = '<button onClick={() => doThing()} className="cursor-pointer"><Play className="w-4 h-4" /></button>'
HARDCODED_COLOR = 'className="bg-[#ff0000] text-white"'
CSS_VAR_COLOR = 'className="bg-[var(--accent-danger)] text-[var(--text-primary)]"'
EMOJI_JSX = '<span>Settings \u2699\ufe0f</span>'
NO_EMOJI_JSX = '<span><Settings className="w-4 h-4" /> Settings</span>'
GOOD_TRANSITION = 'className="transition-colors duration-200"'
BAD_TRANSITION = 'className="transition-colors duration-500"'
LUCIDE_IMPORT = "import { Play, Settings } from 'lucide-react';"
NON_LUCIDE_IMPORT = "import { FaPlay } from 'react-icons/fa';"
RESPONSIVE_GRID = 'className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3"'
NON_RESPONSIVE_GRID = 'className="grid grid-cols-3"'


def test_check_cursor_pointer_on_click():
    assert checks.check_cursor_pointer_on_click(GOOD_BUTTON) == []
    issues = checks.check_cursor_pointer_on_click(BAD_BUTTON_NO_CURSOR)
    assert len(issues) == 1
    assert issues[0]["check_id"] == "cursor-pointer-on-click"


def test_check_hardcoded_colors():
    assert checks.check_hardcoded_colors(CSS_VAR_COLOR) == []
    issues = checks.check_hardcoded_colors(HARDCODED_COLOR)
    assert len(issues) == 1
    assert issues[0]["check_id"] == "hardcoded-hex-color"


def test_check_emoji_in_jsx():
    assert checks.check_emoji_in_jsx(NO_EMOJI_JSX) == []
    issues = checks.check_emoji_in_jsx(EMOJI_JSX)
    assert len(issues) == 1
    assert issues[0]["check_id"] == "emoji-in-jsx"


def test_check_aria_label_icon_button():
    assert checks.check_aria_label_icon_button(GOOD_BUTTON) == []
    issues = checks.check_aria_label_icon_button(BAD_BUTTON_NO_ARIA)
    assert len(issues) == 1


def test_check_transition_duration():
    assert checks.check_transition_duration(GOOD_TRANSITION) == []
    issues = checks.check_transition_duration(BAD_TRANSITION)
    assert len(issues) == 1
    assert issues[0]["check_id"] == "transition-duration-range"


def test_check_non_lucide_import():
    assert checks.check_non_lucide_import(LUCIDE_IMPORT) == []
    issues = checks.check_non_lucide_import(NON_LUCIDE_IMPORT)
    assert len(issues) == 1


def test_check_responsive_breakpoints():
    assert checks.check_responsive_breakpoints(RESPONSIVE_GRID) == []
    issues = checks.check_responsive_breakpoints(NON_RESPONSIVE_GRID)
    assert len(issues) == 1


def test_run_all_checks_returns_scored_result():
    content = f"""
    {LUCIDE_IMPORT}
    export default function Page() {{
      return (
        <div>
          {BAD_BUTTON_NO_CURSOR}
          {HARDCODED_COLOR}
        </div>
      );
    }}
    """
    result = checks.run_all_checks(content, "test/page.tsx", difficulty=0)
    assert "issues" in result
    assert "applicable" in result
    assert "passing" in result
    assert len(result["issues"]) >= 1
    assert any(issue["check_id"] == "aria-label-icon-button" for issue in result["issues"])
