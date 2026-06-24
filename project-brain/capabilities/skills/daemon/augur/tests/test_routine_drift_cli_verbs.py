"""Tests for `aug a-loops adopt` and `aug a-loops push` CLI verbs."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

# Resolve the project root portably — walk up from this file to the git/pyproject root.
_PROJECT_ROOT = next(
    (
        p
        for p in Path(__file__).resolve().parents
        if (p / "pyproject.toml").exists() and (p / ".git").exists()
    ),
    Path(__file__).resolve().parents[4],
)


def test_adopt_verb_dispatches_adopt_cloud_impl_with_routine_id() -> None:
    result = subprocess.run(
        ["scripts/augur", "routine", "adopt", "codex:does-not-exist"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode != 0, "missing id should surface as failure"
    start = result.stdout.find("{")
    payload = json.loads(result.stdout[start:])
    assert payload["success"] is False
    assert "not found" in payload["error"].lower()


def test_push_verb_dispatches_push_local_impl_with_routine_id() -> None:
    result = subprocess.run(
        ["scripts/augur", "routine", "push", "codex:does-not-exist"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode != 0
    start = result.stdout.find("{")
    payload = json.loads(result.stdout[start:])
    assert payload["success"] is False
