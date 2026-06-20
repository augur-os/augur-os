from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import src.cli
from src.cli import _handle_project_init, _handle_project_status


def test_project_status_outputs_json_for_uninitialized_folder(tmp_path: Path, capsys) -> None:
    args = Namespace(
        project=str(tmp_path / "repo"),
        registry=str(tmp_path / "registry.yaml"),
        format="json",
    )

    assert _handle_project_status(args, []) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_initialized"
    assert payload["initialized"] is False
    assert payload["can_init"] is True


def test_project_init_is_inventory_only_by_default(tmp_path: Path, capsys) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Existing vendor instructions\n", encoding="utf-8")
    args = Namespace(
        project=str(project),
        registry=str(tmp_path / "registry.yaml"),
        format="json",
        sync=False,
    )

    assert _handle_project_init(args, []) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "initialized"
    assert payload["sync_returncode"] is None
    assert payload["inventory_count"] >= 1
    assert payload["inventory_path"].endswith("project-brain/config/inventory/ai-artifacts.json")
    assert payload["launch_journey"]["success_moment"] == "inventory_proof"
    assert payload["launch_journey"]["write_boundary"]["inventory_only"] is True
    assert payload["launch_journey"]["primary_next_action"]["label"] == "Ask Augur about this project"
    assert payload["launch_journey"]["primary_next_action"]["retention"] == "answer_only"
    assert payload["launch_context"]["success"] is True
    assert payload["launch_context"]["context"]["brain_id"] == payload["brain_id"]
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == "# Existing vendor instructions\n"


def test_project_init_text_output_reports_first_value_and_next_action(tmp_path: Path, capsys) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Existing instructions\n", encoding="utf-8")
    args = Namespace(
        project=str(project),
        registry=str(tmp_path / "registry.yaml"),
        format="text",
        sync=False,
    )

    assert _handle_project_init(args, []) == 0

    output = capsys.readouterr().out
    assert "First value: AI artifact inventory" in output
    assert "Existing vendor files: read-only inventory" in output
    assert "Ask Augur about this project" in output
    assert "Answer only; do not save or retain" in output


def test_project_init_text_output_reports_sync_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Existing instructions\n", encoding="utf-8")
    monkeypatch.setattr(
        "src.lib.brain_init._sync_client_projections",
        lambda project_root: 23,
    )
    args = Namespace(
        project=str(project),
        registry=str(tmp_path / "registry.yaml"),
        format="text",
        sync=True,
    )

    assert _handle_project_init(args, []) == 23

    output = capsys.readouterr().out
    assert "First value: AI artifact inventory" in output
    assert "requested generated AI-client projections" in output
    assert "Projection sync exit code: 23" in output


def _run_main_project_status(
    monkeypatch,
    tmp_path: Path,
    capsys,
    *argv: str,
) -> dict[str, object]:
    project = tmp_path / "repo"
    registry = tmp_path / "registry.yaml"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "aug",
            *argv,
            "--project",
            str(project),
            "--registry",
            str(registry),
        ],
    )

    assert src.cli.main() == 0

    return json.loads(capsys.readouterr().out)


def test_main_project_status_subcommand_format_json(tmp_path: Path, monkeypatch, capsys) -> None:
    payload = _run_main_project_status(monkeypatch, tmp_path, capsys, "project", "status", "--format", "json")

    assert payload["status"] == "not_initialized"


def test_main_project_status_top_level_format_json(tmp_path: Path, monkeypatch, capsys) -> None:
    payload = _run_main_project_status(monkeypatch, tmp_path, capsys, "--format", "json", "project", "status")

    assert payload["status"] == "not_initialized"


def test_main_project_status_top_level_json_flag(tmp_path: Path, monkeypatch, capsys) -> None:
    payload = _run_main_project_status(monkeypatch, tmp_path, capsys, "--json", "project", "status")

    assert payload["status"] == "not_initialized"
