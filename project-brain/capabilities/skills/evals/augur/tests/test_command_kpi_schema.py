from __future__ import annotations

from pathlib import Path

import pytest

from skills.evals.scripts import command_kpi_schema as schema


def test_scenario_requires_canonical_command() -> None:
    payload = {
        "_schema": "command.kpi.scenario.v1",
        "id": "bad",
        "command": "note",
        "client": "codex",
        "input_class": "thought",
        "input": "remember this",
        "assertions": {},
    }

    with pytest.raises(ValueError, match="canonical"):
        schema.CommandScenario.from_dict(payload)


def test_gate_pass_requires_zero_warns_and_failures() -> None:
    thresholds = schema.KPIThresholds()
    aggregate = {
        "total": 18,
        "pass_count": 17,
        "warn_count": 1,
        "fail_count": 0,
        "pass_rate": 17 / 18,
        "by_command": {
            "ask": {"total": 4, "pass": 4, "warn": 0, "fail": 0},
            "keep": {"total": 5, "pass": 5, "warn": 0, "fail": 0},
            "discover": {"total": 2, "pass": 2, "warn": 0, "fail": 0},
            "adr": {"total": 2, "pass": 2, "warn": 0, "fail": 0},
            "dev": {"total": 2, "pass": 2, "warn": 0, "fail": 0},
            "routines": {"total": 2, "pass": 2, "warn": 0, "fail": 0},
            "sweep": {"total": 1, "pass": 1, "warn": 0, "fail": 0},
        },
    }

    result = schema.evaluate_gate(aggregate, thresholds, consecutive_passes=3)

    assert result.passed is False
    assert any(issue["code"] == "warn_count_nonzero" for issue in result.issues)


def test_private_scenario_path_must_stay_under_documents(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside private"):
        schema.validate_private_scenario_path(
            Path("/tmp/public.yaml"),
            documents_dir=tmp_path,
        )
