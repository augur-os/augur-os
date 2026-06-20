from __future__ import annotations

import json
from pathlib import Path

import yaml

from skills.evals.scripts import command_kpi_runner as runner


def _write_pack(path: Path, scenarios: list[dict]) -> Path:
    path.write_text(
        yaml.safe_dump(
            {"_schema": "command.kpi.pack.v1", "run_id": "pack-run", "scenarios": scenarios},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _scenario(command: str, scenario_id: str, **overrides: object) -> dict:
    payload = {
        "_schema": "command.kpi.scenario.v1",
        "id": scenario_id,
        "command": command,
        "client": "engine",
        "input_class": "test",
        "input": "",
        "assertions": {},
    }
    payload.update(overrides)
    return payload


def test_keep_local_file_writes_private_envelope_and_auto_scorecard(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    local_file = tmp_path / "source.md"
    local_file.write_text("# Local\n\nKeep this local.\n", encoding="utf-8")
    scenario_path = _write_pack(
        tmp_path / "scenarios.yaml",
        [
            _scenario(
                "keep",
                "keep-local",
                input_class="local-file",
                input=str(local_file),
                private_refs=[str(local_file)],
                assertions={"expected_route": "local-file", "forbidden_routes": ["google-drive", "gdrive", "cloud"]},
                max_duration_ms=10000,
            )
        ],
    )
    monkeypatch.setattr(runner.command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        runner.command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    result = runner.run_command_kpis(scenario_path=scenario_path, run_id="test-run")

    assert result["success"] is True
    assert result["scenario_count"] == 1
    assert result["aggregate"]["pass_count"] == 1
    run_rows = [
        json.loads(line)
        for path in (docs / "_augur/evals/commands/runs").glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert run_rows[0]["command"] == "keep"
    assert run_rows[0]["chosen_route"] == "local-file"
    scorecard = (docs / "_augur/evals/commands/scorecards/test-run-keep-local.md").read_text(encoding="utf-8")
    assert "reviewer: auto" in scorecard
    assert "routing_correctness: pass" in scorecard


def test_ask_weak_context_scores_content_quality_pass(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    scenario_path = _write_pack(
        tmp_path / "scenarios.yaml",
        [
            _scenario(
                "ask",
                "ask-weak",
                input_class="weak-context",
                input="Answer without sources.",
                assertions={"expected_answer_mode": "weak-context", "forbidden_claims": ["confirmed"]},
                max_duration_ms=10000,
            )
        ],
    )
    monkeypatch.setattr(runner.command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        runner.command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    result = runner.run_command_kpis(scenario_path=scenario_path, run_id="test-run")

    assert result["aggregate"]["pass_count"] == 1
    scorecard = (docs / "_augur/evals/commands/scorecards/test-run-ask-weak.md").read_text(encoding="utf-8")
    assert "content_quality: pass" in scorecard
    assert "source_grounding: pass" in scorecard


def test_duration_above_threshold_fails_ux_observability(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    source = tmp_path / "source.md"
    source.write_text("slow fixture", encoding="utf-8")
    scenario_path = _write_pack(
        tmp_path / "scenarios.yaml",
        [
            _scenario(
                "keep",
                "slow-keep",
                input_class="local-file",
                input=str(source),
                assertions={"expected_route": "local-file"},
                max_duration_ms=-1,
            )
        ],
    )
    monkeypatch.setattr(runner.command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        runner.command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    result = runner.run_command_kpis(scenario_path=scenario_path, run_id="test-run")

    assert result["aggregate"]["fail_count"] == 1
    scorecard = (docs / "_augur/evals/commands/scorecards/test-run-slow-keep.md").read_text(encoding="utf-8")
    assert "ux_observability: fail" in scorecard


def test_gate_uses_state_last_run_report_not_lexicographic_latest(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    reports = docs / "_augur" / "evals" / "commands" / "reports"
    reports.mkdir(parents=True)
    stale_report = {
        "_schema": "command.aggregate.v1",
        "total": 0,
        "pass_count": 0,
        "warn_count": 0,
        "fail_count": 0,
        "pass_rate": 0.0,
        "by_command": {},
    }
    good_by_command = {
        "ask": {"total": 4, "pass": 4, "warn": 0, "fail": 0},
        "keep": {"total": 5, "pass": 5, "warn": 0, "fail": 0},
        "discover": {"total": 2, "pass": 2, "warn": 0, "fail": 0},
        "adr": {"total": 2, "pass": 2, "warn": 0, "fail": 0},
        "dev": {"total": 2, "pass": 2, "warn": 0, "fail": 0},
        "routines": {"total": 2, "pass": 2, "warn": 0, "fail": 0},
        "sweep": {"total": 2, "pass": 2, "warn": 0, "fail": 0},
    }
    good_report = {
        "_schema": "command.aggregate.v1",
        "total": 19,
        "pass_count": 19,
        "warn_count": 0,
        "fail_count": 0,
        "pass_rate": 1.0,
        "by_command": good_by_command,
    }
    (reports / "demo-kpi-loop-3-aggregate.json").write_text(json.dumps(good_report), encoding="utf-8")
    (reports / "zzz-stale-aggregate.json").write_text(json.dumps(stale_report), encoding="utf-8")
    (reports / "command-kpi-state.json").write_text(
        json.dumps({"consecutive_passes": 3, "last_run_id": "demo-kpi-loop-3"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner.command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        runner.command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    result = runner.evaluate_latest_gate(required_consecutive_passes=3)

    assert result["success"] is True
    assert result["report_path"].endswith("demo-kpi-loop-3-aggregate.json")


def test_scoped_command_run_filters_scenarios_without_touching_gate_state(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    source = tmp_path / "source.md"
    source.write_text("# Keep\n\nLocal source.", encoding="utf-8")
    scenario_path = _write_pack(
        tmp_path / "scenarios.yaml",
        [
            _scenario(
                "keep",
                "keep-local",
                input_class="local-file",
                input=str(source),
                assertions={"expected_route": "local-file"},
                max_duration_ms=10000,
            ),
            _scenario(
                "ask",
                "ask-weak",
                input_class="weak-context",
                input="Answer without sources.",
                assertions={"expected_answer_mode": "weak-context"},
                max_duration_ms=10000,
            ),
        ],
    )
    reports = docs / "_augur" / "evals" / "commands" / "reports"
    reports.mkdir(parents=True)
    state_path = reports / "command-kpi-state.json"
    state_path.write_text(
        json.dumps({"consecutive_passes": 3, "last_run_id": "full-green"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner.command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        runner.command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    result = runner.run_command_kpis(
        scenario_path=scenario_path,
        run_id="scoped-keep",
        command_filter="keep",
    )

    assert result["success"] is True
    assert result["scoped"] is True
    assert result["command_filter"] == "keep"
    assert result["scenario_count"] == 1
    assert result["aggregate"]["by_command"] == {
        "keep": {"total": 1, "pass": 1, "warn": 0, "fail": 0}
    }
    assert result["gate"] == {
        "passed": True,
        "issues": [],
        "scoped": True,
        "message": "Scoped command run; full KPI gate state was not updated.",
    }
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "consecutive_passes": 3,
        "last_run_id": "full-green",
    }
    details = json.loads(Path(result["details_path"]).read_text(encoding="utf-8"))
    assert [item["command"] for item in details["details"]] == ["keep"]


def test_scoped_command_run_rejects_unknown_command(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    scenario_path = _write_pack(
        tmp_path / "scenarios.yaml",
        [_scenario("keep", "keep-local", assertions={"expected_route": "local-file"})],
    )
    monkeypatch.setattr(runner.command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        runner.command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    try:
        runner.run_command_kpis(
            scenario_path=scenario_path,
            run_id="bad-filter",
            command_filter="gemini",
        )
    except ValueError as exc:
        assert "unknown command filter" in str(exc)
    else:
        raise AssertionError("expected unknown command filter to fail")


def test_command_kpi_report_reads_latest_aggregate_and_summarizes_details(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    reports = docs / "_augur" / "evals" / "commands" / "reports"
    reports.mkdir(parents=True)
    aggregate = {
        "_schema": "command.aggregate.v1",
        "total": 2,
        "pass_count": 1,
        "warn_count": 0,
        "fail_count": 1,
        "pass_rate": 0.5,
        "by_command": {
            "keep": {"total": 1, "pass": 1, "warn": 0, "fail": 0},
            "ask": {"total": 1, "pass": 0, "warn": 0, "fail": 1},
        },
    }
    details = {
        "run_id": "report-run",
        "details": [
            {"scenario": "keep-local", "command": "keep", "duration_ms": 25, "scores": {"routing_correctness": "pass"}},
            {"scenario": "ask-weak", "command": "ask", "duration_ms": 250, "scores": {"content_quality": "fail"}},
        ],
    }
    (reports / "report-run-aggregate.json").write_text(json.dumps(aggregate), encoding="utf-8")
    (reports / "report-run-details.json").write_text(json.dumps(details), encoding="utf-8")
    (reports / "command-kpi-state.json").write_text(
        json.dumps({"consecutive_passes": 0, "last_run_id": "report-run"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner.command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        runner.command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    report = runner.command_kpi_report()

    assert report["success"] is True
    assert report["run_id"] == "report-run"
    assert report["scenario_count"] == 2
    assert report["pass_rate"] == 0.5
    assert report["slowest_scenario"] == {
        "scenario": "ask-weak",
        "command": "ask",
        "duration_ms": 250,
    }
    assert report["failing_scenarios"] == [
        {
            "scenario": "ask-weak",
            "command": "ask",
            "failed_dimensions": ["content_quality"],
        }
    ]
