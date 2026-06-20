"""Tests for d2 safe auto-fixes."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_fix_missing_cursor_pointer():
    from fixers import fix_cursor_pointer
    content = '<button onClick={() => doThing()} className="px-4 py-2">'
    fixed = fix_cursor_pointer(content)
    assert "cursor-pointer" in fixed
    assert 'className="cursor-pointer px-4 py-2"' in fixed


def test_fix_cursor_pointer_already_present():
    from fixers import fix_cursor_pointer
    content = '<button onClick={() => doThing()} className="cursor-pointer px-4">'
    fixed = fix_cursor_pointer(content)
    assert fixed == content  # no change


def test_fix_transition_duration():
    from fixers import fix_transition_duration
    content = 'className="transition-colors duration-500"'
    fixed = fix_transition_duration(content)
    assert "duration-200" in fixed


def test_fix_transition_duration_valid():
    from fixers import fix_transition_duration
    content = 'className="transition-colors duration-200"'
    fixed = fix_transition_duration(content)
    assert fixed == content  # no change


def test_apply_safe_fixes_returns_changes():
    from fixers import apply_safe_fixes
    content = """
    <button onClick={() => doThing()} className="px-4 py-2 transition-all duration-500">
      <Play className="w-4 h-4" />
    </button>
    """
    fixed, changes = apply_safe_fixes(content, "test/page.tsx")
    assert len(changes) >= 1
    assert "cursor-pointer" in fixed
    assert "duration-200" in fixed
