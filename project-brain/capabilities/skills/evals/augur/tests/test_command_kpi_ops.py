from __future__ import annotations

from src.lib.ops_protocol import OpsContext, ScanResult
from skills.evals.scripts import command_kpi_ops


def test_scan_returns_degraded_when_gate_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        command_kpi_ops.command_kpi_runner,
        "run_command_kpis",
        lambda **_: {
            "success": True,
            "scenario_count": 18,
            "gate": {"passed": False, "issues": [{"code": "warn_count_nonzero"}]},
        },
    )

    result = command_kpi_ops.scan(OpsContext(project_root=tmp_path, difficulty=1, dry_run=True))

    assert isinstance(result, ScanResult)
    assert result.severity == "warning"
    assert result.health == "degraded"
    assert result.issues[0]["code"] == "warn_count_nonzero"


def test_scan_returns_verified_when_gate_passes(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        command_kpi_ops.command_kpi_runner,
        "run_command_kpis",
        lambda **_: {
            "success": True,
            "summary": "18 command KPI scenarios run",
            "scenario_count": 18,
            "gate": {"passed": True, "issues": []},
        },
    )

    result = command_kpi_ops.scan(OpsContext(project_root=tmp_path, difficulty=1, dry_run=True))

    assert result.severity == "info"
    assert result.health == "verified"
    assert result.summary == "18 command KPI scenarios run"
