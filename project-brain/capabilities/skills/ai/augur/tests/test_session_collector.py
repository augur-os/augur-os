"""Tests for the session log signal collector."""

import sys
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts" / "ops" / "agent_digest")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import pytest

from collect_session_signals import (
    extract_corrections,
    infer_directive,
)


def test_extract_no_correction():
    lines = ["Great, I'll implement that now.", "Let me read the file."]
    corrections = extract_corrections(lines)
    assert len(corrections) == 0


def test_extract_dont_correction():
    lines = ["no don't mock the database, use real integration tests"]
    corrections = extract_corrections(lines)
    assert len(corrections) == 1
    assert "mock" in corrections[0].lower()


def test_extract_stop_correction():
    lines = ["stop adding emojis to the commit messages"]
    corrections = extract_corrections(lines)
    assert len(corrections) == 1


def test_extract_wrong_correction():
    lines = ["that's wrong, the file should not import fs directly"]
    corrections = extract_corrections(lines)
    assert len(corrections) == 1


def test_extract_no_as_negation():
    lines = ["no, don't use fallbacks here"]
    corrections = extract_corrections(lines)
    assert len(corrections) == 1


def test_extract_skips_false_positive():
    lines = ["yes that's fine, no issues there"]
    corrections = extract_corrections(lines)
    assert len(corrections) == 0


def test_infer_directive_emoji():
    text = "stop adding emojis to the commit messages"
    directive_map = {
        "no_emojis": {"label": "NO emojis", "sources": [], "description": "Unless user explicitly requests them."},
        "no_fs_in_dashboard": {"label": "NO fs/spawn in dashboard", "sources": [], "description": "All data via MCP."},
    }
    result = infer_directive(text, directive_map)
    assert result == "no_emojis"


def test_infer_directive_unknown():
    text = "don't use that library"
    directive_map = {
        "no_emojis": {"label": "NO emojis", "sources": [], "description": "Unless user explicitly requests them."},
    }
    result = infer_directive(text, directive_map)
    assert result is None
