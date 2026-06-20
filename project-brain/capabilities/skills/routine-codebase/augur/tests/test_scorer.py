"""Tests for page scoring and registry persistence."""
from __future__ import annotations

import sys
from pathlib import Path

import json
import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_compute_page_score_weighted():
    from scorer import compute_page_score
    dimension_scores = {
        "accessibility": 80.0,      # weight 0.30 → 24.0
        "interaction": 60.0,        # weight 0.25 → 15.0
        "design_system": 100.0,     # weight 0.25 → 25.0
        "responsiveness": 50.0,     # weight 0.20 → 10.0
    }
    score = compute_page_score(dimension_scores)
    assert score == pytest.approx(74.0, abs=0.1)


def test_compute_page_score_missing_dimension():
    """Pages missing a dimension should not be penalized."""
    from scorer import compute_page_score
    dimension_scores = {
        "accessibility": 80.0,
        "interaction": 60.0,
        # design_system and responsiveness absent (no applicable checks)
    }
    score = compute_page_score(dimension_scores)
    # Only accessibility (0.30) and interaction (0.25) apply
    # Renormalized: acc=0.30/0.55=0.545, int=0.25/0.55=0.454
    # Score: 80*0.545 + 60*0.454 = 43.6 + 27.3 = 70.9
    assert score == pytest.approx(70.9, abs=0.5)


def test_load_and_save_registry(tmp_path):
    from scorer import load_registry, save_registry
    registry_path = tmp_path / "page-scores.json"

    # Empty on first load
    reg = load_registry(registry_path)
    assert reg == {}

    # Save and reload
    reg["life/home-automation/scenes"] = {
        "score": 72,
        "last_audit": "2026-03-24",
        "issues": {"d0": 3, "d1": 1},
        "check_counts": {"applicable": 18, "passing": 13},
    }
    save_registry(reg, registry_path)
    reg2 = load_registry(registry_path)
    assert reg2["life/home-automation/scenes"]["score"] == 72


def test_priority_sort():
    from scorer import priority_sort
    pages = {
        "a": {"score": 50, "last_audit": "2026-03-20"},
        "b": {"score": 30, "last_audit": "2026-03-22"},
        "c": {"score": 0, "last_audit": None},  # never audited
        "d": {"score": 80, "last_audit": "2026-03-24"},
    }
    sorted_pages = priority_sort(pages)
    # Never audited first, then lowest score
    assert sorted_pages[0] == "c"
    assert sorted_pages[1] == "b"
    assert sorted_pages[2] == "a"
    assert sorted_pages[3] == "d"
