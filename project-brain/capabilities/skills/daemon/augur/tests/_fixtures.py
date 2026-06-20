"""Shared fixtures for ADR-755 routine orchestrator tests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TOY_LOOP_NAME = "toy-loop"
TOY_LOOP_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "toy_loop"


def build_toy_loop() -> dict[str, Any]:
    """Build a small three-command loop definition for orchestrator tests."""
    categories = {
        "auto-mech": {
            "enabled": True,
            "trust": 0.8,
            "tier": 0,
            "module": "auto_mech",
            "path": str(TOY_LOOP_FIXTURE_DIR / "auto_mech.py"),
        },
        "auto-semantic": {
            "enabled": True,
            "trust": 0.6,
            "tier": 1,
            "module": "auto_semantic",
            "path": str(TOY_LOOP_FIXTURE_DIR / "auto_semantic.py"),
        },
        "auto-struct": {
            "enabled": True,
            "trust": 0.4,
            "tier": 2,
            "module": "auto_struct",
            "path": str(TOY_LOOP_FIXTURE_DIR / "auto_struct.py"),
        },
    }
    return {
        "name": TOY_LOOP_NAME,
        "fixture_dir": TOY_LOOP_FIXTURE_DIR,
        "modules": [category["module"] for category in categories.values()],
        "config": {
            "loops": {
                TOY_LOOP_NAME: {
                    "enabled": True,
                    "trigger": "manual",
                    "budget": 3,
                    "budget_growth_rate": 1,
                    "categories": categories,
                },
            },
        },
    }


def build_fixture_runtime_dir(tmp_path: Path) -> Path:
    """Create and return an isolated runtime directory for orchestrator tests."""
    runtime_dir = tmp_path / "runtime"
    (runtime_dir / "adaptive").mkdir(parents=True, exist_ok=True)
    return runtime_dir


def build_trust_state_file(tmp_path: Path) -> Path:
    """Create a toy trust_state.json under the fixture runtime directory."""
    runtime_dir = build_fixture_runtime_dir(tmp_path)
    state_file = runtime_dir / "adaptive" / "trust_state.json"
    state_file.write_text(
        json.dumps(
            {
                "loops": {
                    TOY_LOOP_NAME: {
                        "budget": 3,
                        "budget_remaining": 3,
                        "cycle_count": 0,
                        "categories": {
                            "auto-mech": {"enabled": True, "trust": 0.8, "tier": 0},
                            "auto-semantic": {"enabled": True, "trust": 0.6, "tier": 1},
                            "auto-struct": {"enabled": True, "trust": 0.4, "tier": 2},
                        },
                    },
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return state_file
