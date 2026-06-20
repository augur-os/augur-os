"""Tests for the /flag command executor."""

import json
from pathlib import Path
import pytest

import sys
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts" / "ops" / "agent_digest")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from flag import build_event, parse_flag_args


def test_parse_simple_flag():
    args = parse_flag_args('"agent added to centralized config again"')
    assert args["description"] == "agent added to centralized config again"
    assert args["rule"] is None
    assert args["adr"] is None


def test_parse_with_rule():
    args = parse_flag_args('"used emoji" --rule no_emojis')
    assert args["description"] == "used emoji"
    assert args["rule"] == "no_emojis"


def test_parse_with_adr():
    args = parse_flag_args('"centralized config" --adr ADR-163')
    assert args["description"] == "centralized config"
    assert args["adr"] == "ADR-163"


def test_build_event_with_rule():
    event = build_event("used emoji", rule="no_emojis")
    assert event["source"] == "manual"
    assert event["type"] == "flag"
    assert event["rule"] == "no_emojis"
    assert event["priority"] == "boost"
    assert "ts" in event


def test_build_event_with_adr():
    event = build_event("centralized config", adr="ADR-163")
    assert event["rule"] == "ADR-163"


def test_build_event_no_mapping():
    event = build_event("something unmapped")
    assert event["rule"] == "manual:something unmapped"


def test_build_event_with_inferred_directive():
    directive_map = {
        "no_emojis": {"label": "NO emojis", "sources": [], "description": "Unless user explicitly requests them."},
    }
    event = build_event("stop adding emojis", directive_map=directive_map)
    assert event["rule"] == "no_emojis"
