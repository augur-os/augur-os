from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_build_run_envelope_has_required_schema_fields(monkeypatch, tmp_path: Path) -> None:
    from skills.evals.scripts import command_records as mod

    monkeypatch.setattr(mod, "get_documents_dir", lambda: tmp_path / "docs")
    monkeypatch.setattr(
        mod,
        "get_documents_machine_dir",
        lambda name: tmp_path / "docs" / "_augur" / name,
    )
    envelope = mod.build_run_envelope(
        command="keep",
        client="codex",
        input_class="local-file",
        chosen_route="local-file",
        phases=[{"name": "route", "status": "success", "duration_ms": 7}],
        outputs={"path": "/tmp/out.md"},
        duration_ms=42,
        quality_flags=[],
        warnings=[],
        private_artifact_refs=["documents://evals/commands/runs/x.jsonl"],
        started_at="2026-05-23T12:00:00Z",
    )

    assert envelope["_schema"] == "command.run.v1"
    assert envelope["command"] == "keep"
    assert envelope["client"] == "codex"
    assert envelope["requires_human_review"] is True
    assert envelope["quality_flags"] == []
    assert envelope["warnings"] == []
    assert envelope["duration_ms"] == 42


def test_write_run_envelope_uses_private_documents_root(monkeypatch, tmp_path: Path) -> None:
    from skills.evals.scripts import command_records as mod

    monkeypatch.setattr(mod, "get_documents_dir", lambda: tmp_path / "docs")
    monkeypatch.setattr(
        mod,
        "get_documents_machine_dir",
        lambda name: tmp_path / "docs" / "_augur" / name,
    )
    envelope = mod.build_run_envelope(
        command="ask",
        client="claude",
        input_class="question",
        chosen_route="reflect-context",
        duration_ms=100,
        started_at="2026-05-23T12:00:00Z",
    )

    path = mod.write_run_envelope(envelope, run_id="run-a")

    assert path == tmp_path / "docs" / "_augur" / "evals" / "commands" / "runs" / "2026-05-23.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows == [envelope | {"run_id": "run-a"}]


def test_write_run_envelope_rejects_unsafe_started_at(monkeypatch, tmp_path: Path) -> None:
    from skills.evals.scripts import command_records as mod

    docs = tmp_path / "docs"
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        mod,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )
    envelope = mod.build_run_envelope(
        command="ask",
        client="claude",
        input_class="question",
        chosen_route="reflect-context",
        started_at="../escape",
    )

    with pytest.raises(ValueError):
        mod.write_run_envelope(envelope, run_id="run-a")

    assert not (tmp_path / "escape.jsonl").exists()
    assert not (docs / "_augur" / "evals" / "commands" / "runs").exists()


def test_write_run_envelope_rejects_bad_started_at_date(monkeypatch, tmp_path: Path) -> None:
    from skills.evals.scripts import command_records as mod

    monkeypatch.setattr(mod, "get_documents_dir", lambda: tmp_path / "docs")
    monkeypatch.setattr(
        mod,
        "get_documents_machine_dir",
        lambda name: tmp_path / "docs" / "_augur" / name,
    )
    envelope = mod.build_run_envelope(
        command="ask",
        client="claude",
        input_class="question",
        chosen_route="reflect-context",
        started_at="2026-99-99T12:00:00Z",
    )

    with pytest.raises(ValueError):
        mod.write_run_envelope(envelope, run_id="run-a")


def test_write_run_envelope_rejects_symlinked_runs_root(monkeypatch, tmp_path: Path) -> None:
    from skills.evals.scripts import command_records as mod

    docs = tmp_path / "docs"
    outside = tmp_path / "outside"
    outside.mkdir()
    runs_parent = docs / "_augur" / "evals" / "commands"
    runs_parent.mkdir(parents=True)
    try:
        (runs_parent / "runs").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        mod,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )
    envelope = mod.build_run_envelope(
        command="ask",
        client="claude",
        input_class="question",
        chosen_route="reflect-context",
        started_at="2026-05-23T12:00:00Z",
    )

    with pytest.raises(ValueError):
        mod.write_run_envelope(envelope, run_id="run-a")

    assert not (outside / "2026-05-23.jsonl").exists()


def test_write_run_envelope_rejects_symlinked_evals_root(monkeypatch, tmp_path: Path) -> None:
    from skills.evals.scripts import command_records as mod

    docs = tmp_path / "docs"
    outside = tmp_path / "outside"
    outside.mkdir()
    docs.mkdir()
    try:
        (docs / "_augur" / "evals").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        mod,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )
    envelope = mod.build_run_envelope(
        command="ask",
        client="claude",
        input_class="question",
        chosen_route="reflect-context",
        started_at="2026-05-23T12:00:00Z",
    )

    with pytest.raises(ValueError):
        mod.write_run_envelope(envelope, run_id="run-a")

    assert not (outside / "commands" / "runs" / "2026-05-23.jsonl").exists()


def test_parse_human_scorecard_and_aggregate(tmp_path: Path) -> None:
    from skills.evals.scripts import command_records as mod

    scorecard = tmp_path / "scorecard.md"
    scorecard.write_text(
        "---\n"
        "_schema: command.scorecard.v1\n"
        "run_id: run-a\n"
        "command: keep\n"
        "reviewer: human\n"
        "content_quality: pass\n"
        "source_grounding: pass\n"
        "ux_observability: warn\n"
        "routing_correctness: fail\n"
        "duration_rating: slow\n"
        "reviewed_at: 2026-05-23T12:05:00Z\n"
        "---\n"
        "Routing selected an unrelated cloud destination.\n",
        encoding="utf-8",
    )

    parsed = mod.read_scorecard(scorecard)
    assert parsed["run_id"] == "run-a"
    assert parsed["scores"]["routing_correctness"] == "fail"
    assert parsed["notes"] == "Routing selected an unrelated cloud destination.\n"

    aggregate = mod.aggregate_scorecards([parsed])
    assert aggregate["total"] == 1
    assert aggregate["pass_count"] == 0
    assert aggregate["warn_count"] == 1
    assert aggregate["fail_count"] == 1
    assert aggregate["by_command"]["keep"]["total"] == 1


def test_read_scorecard_normalizes_human_edited_ratings(tmp_path: Path) -> None:
    from skills.evals.scripts import command_records as mod

    scorecard = tmp_path / "scorecard.md"
    scorecard.write_text(
        "---\n"
        "_schema: command.scorecard.v1\n"
        "run_id: run-b\n"
        "command: ask\n"
        "reviewer: human\n"
        "content_quality: ' Warn '\n"
        "source_grounding: PASS\n"
        "ux_observability: not_applicable\n"
        "routing_correctness: fail\n"
        "duration_rating: acceptable\n"
        "reviewed_at: 2026-05-23T12:05:00Z\n"
        "---\n"
        "Normalized ratings.\n",
        encoding="utf-8",
    )

    parsed = mod.read_scorecard(scorecard)

    assert parsed["scores"]["content_quality"] == "warn"
    assert parsed["scores"]["source_grounding"] == "pass"


def test_write_aggregate_report_rejects_unsafe_run_id(tmp_path: Path, monkeypatch) -> None:
    from skills.evals.scripts import command_records as mod

    monkeypatch.setattr(mod, "get_documents_dir", lambda: tmp_path / "docs")
    monkeypatch.setattr(
        mod,
        "get_documents_machine_dir",
        lambda name: tmp_path / "docs" / "_augur" / name,
    )

    with pytest.raises(ValueError):
        mod.write_aggregate_report([], run_id="../escape")

    assert not (tmp_path / "escape.json").exists()


def test_aggregate_scorecards_exposes_rollup_and_dimension_counts() -> None:
    from skills.evals.scripts import command_records as mod

    scorecards = [
        {
            "command": "keep",
            "scores": {
                "content_quality": "pass",
                "source_grounding": "pass",
                "ux_observability": "pass",
                "routing_correctness": "pass",
            },
        },
        {
            "command": "keep",
            "scores": {
                "content_quality": "warn",
                "source_grounding": "pass",
                "ux_observability": "pass",
                "routing_correctness": "pass",
            },
        },
        {
            "command": "ask",
            "scores": {
                "content_quality": "pass",
                "source_grounding": "warn",
                "ux_observability": "pass",
                "routing_correctness": "fail",
            },
        },
    ]

    aggregate = mod.aggregate_scorecards(scorecards)

    assert aggregate["pass_count"] == 1
    assert aggregate["warn_count"] == 2
    assert aggregate["fail_count"] == 1
    assert aggregate["card_rollup"] == {"pass": 1, "warn": 1, "fail": 1}
    assert aggregate["dimension_counts"]["pass"] == 9
    assert aggregate["dimension_counts"]["warn"] == 2
    assert aggregate["dimension_counts"]["fail"] == 1
    assert aggregate["count_semantics"]["card_rollup"] == "mutually exclusive card severity"
