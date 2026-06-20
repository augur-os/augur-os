from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from argparse import Namespace
from pathlib import Path

PROJECT_ROOT = next(
    (
        p
        for p in Path(__file__).resolve().parents
        if (p / "pyproject.toml").exists() and (p / ".git").exists()
    ),
    Path(__file__).resolve().parents[-1],
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _record_args(**overrides: object) -> Namespace:
    values = {
        "command": "keep",
        "client": "codex",
        "input_class": "local-file",
        "chosen_route": "local-file",
        "duration_ms": 25,
        "phases": '[{"name":"route","status":"success","duration_ms":5}]',
        "quality_flags": "[]",
        "warnings": "[]",
        "outputs": '{"path":"/tmp/out.md"}',
        "run_id": "run-1",
    }
    values.update(overrides)
    return Namespace(**values)


def test_command_record_cli_writes_private_envelope(monkeypatch, tmp_path: Path) -> None:
    import command_records
    import eval_ops

    monkeypatch.setattr(command_records, "get_documents_dir", lambda: tmp_path / "docs")
    monkeypatch.setattr(
        command_records,
        "get_documents_machine_dir",
        lambda name: tmp_path / "docs" / "_augur" / name,
    )
    args = _record_args(outputs='{"path":"/tmp/private-output.md","secret":"token"}')

    result = eval_ops.cmd_command_record(args)

    assert result["success"] is True
    assert result["run_id"] == "run-1"
    assert result["command"] == "keep"
    assert result["client"] == "codex"
    assert "envelope" not in result
    assert "private-output" not in json.dumps(result)
    assert "secret" not in json.dumps(result)
    path = Path(result["path"])
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["run_id"] == "run-1"
    assert row["command"] == "keep"
    assert row["chosen_route"] == "local-file"
    assert row["outputs"]["secret"] == "token"


def test_command_record_cli_rejects_non_object_phases(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    import command_records
    import eval_ops

    docs = tmp_path / "docs"
    monkeypatch.setattr(command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    exit_code = eval_ops.run_cli("command-record", _record_args(phases='"bad"'))

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert "--phases" in output["error"]
    assert not (docs / "evals" / "commands" / "runs").exists()


def test_command_record_cli_rejects_non_object_outputs(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    import command_records
    import eval_ops

    docs = tmp_path / "docs"
    monkeypatch.setattr(command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    exit_code = eval_ops.run_cli("command-record", _record_args(outputs="[]"))

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert "--outputs" in output["error"]
    assert not (docs / "evals" / "commands" / "runs").exists()


def test_command_record_cli_rejects_non_string_quality_flags(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    import command_records
    import eval_ops

    docs = tmp_path / "docs"
    monkeypatch.setattr(command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    exit_code = eval_ops.run_cli(
        "command-record",
        _record_args(quality_flags='["ok", {"bad": true}]'),
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert "--quality-flags" in output["error"]
    assert not (docs / "evals" / "commands" / "runs").exists()


def test_eval_cli_rejects_unknown_remaining_args(monkeypatch, tmp_path: Path, capsys) -> None:
    import command_records
    from skills.evals.scripts import mcp as eval_mcp

    docs = tmp_path / "docs"
    monkeypatch.setattr(command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    exit_code = eval_mcp._run_eval_cli(
        _record_args(eval_verb="command-record"),
        ["--quality-flag", "typo"],
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert output == {
        "error": "unknown arguments",
        "unknown_args": ["--quality-flag", "typo"],
    }
    assert not (docs / "evals" / "commands" / "runs").exists()


def test_eval_parser_rejects_abbreviated_command_record_flags(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    import command_records
    from skills.evals.scripts import mcp as eval_mcp

    docs = tmp_path / "docs"
    monkeypatch.setattr(command_records, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        command_records,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand")
    eval_mcp.register_subcommands(subparsers)

    args, remaining = parser.parse_known_args(
        [
            "eval",
            "command-record",
            "--command",
            "keep",
            "--client",
            "codex",
            "--input-class",
            "local-file",
            "--chosen-route",
            "local-file",
            "--quality-flag",
            '["bad"]',
        ]
    )
    exit_code = args.func(args, remaining)

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert output == {
        "error": "unknown arguments",
        "unknown_args": ["--quality-flag", '["bad"]'],
    }
    assert not (docs / "evals" / "commands" / "runs").exists()


def test_command_aggregate_cli_reads_scorecards(monkeypatch, tmp_path: Path) -> None:
    import command_records
    import eval_ops

    score_dir = tmp_path / "docs" / "_augur" / "evals" / "commands" / "scorecards"
    score_dir.mkdir(parents=True)
    (score_dir / "run-1.md").write_text(
        "---\n"
        "_schema: command.scorecard.v1\n"
        "run_id: run-1\n"
        "command: ask\n"
        "reviewer: human\n"
        "content_quality: pass\n"
        "source_grounding: warn\n"
        "ux_observability: pass\n"
        "routing_correctness: pass\n"
        "duration_rating: acceptable\n"
        "reviewed_at: 2026-05-23T00:00:00Z\n"
        "---\n"
        "Needs stronger source citation.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(command_records, "get_documents_dir", lambda: tmp_path / "docs")
    monkeypatch.setattr(
        command_records,
        "get_documents_machine_dir",
        lambda name: tmp_path / "docs" / "_augur" / name,
    )

    result = eval_ops.cmd_command_aggregate(Namespace(run_id="aggregate-1"))

    assert result["success"] is True
    assert result["aggregate"]["total"] == 1
    assert result["aggregate"]["warn_count"] == 1
    assert Path(result["report_path"]).name == "aggregate-1.json"


def test_command_kpi_verbs_are_registered() -> None:
    from skills.evals.scripts import mcp as eval_mcp

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand")
    eval_mcp.register_subcommands(subparsers)

    for verb in ("command-kpi-bootstrap", "command-kpi-run", "command-kpi-gate", "command-kpi-report"):
        parsed, remaining = parser.parse_known_args(["eval", verb])
        assert parsed.eval_verb == verb
        assert remaining == []


def test_command_kpi_run_parser_accepts_command_filter() -> None:
    from skills.evals.scripts import mcp as eval_mcp

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand")
    eval_mcp.register_subcommands(subparsers)

    parsed, remaining = parser.parse_known_args(["eval", "command-kpi-run", "--command", "keep"])

    assert parsed.eval_verb == "command-kpi-run"
    assert parsed.command == "keep"
    assert remaining == []


def test_command_kpi_report_cli_delegates_to_runner(monkeypatch) -> None:
    import command_kpi_runner
    import eval_ops

    calls = []

    def fake_report(*, run_id=None):
        calls.append(run_id)
        return {"success": True, "run_id": run_id or "latest"}

    monkeypatch.setattr(command_kpi_runner, "command_kpi_report", fake_report)

    result = eval_ops.cmd_command_kpi_report(Namespace(run_id="demo-run"))

    assert result == {"success": True, "run_id": "demo-run"}
    assert calls == ["demo-run"]
