"""Unit tests for src._cli_commands — pure project-subcommand helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import src._cli_commands as cli_commands


def _ns(**kw) -> argparse.Namespace:
    return argparse.Namespace(**kw)


def test_project_output_format_prefers_explicit_format():
    args = _ns(format="json", json=False)
    assert cli_commands._project_output_format(args) == "json"


def test_project_output_format_json_flag_fallback():
    args = _ns(format=None, json=True)
    assert cli_commands._project_output_format(args) == "json"


def test_project_output_format_defaults_to_text():
    args = _ns(format=None, json=False)
    assert cli_commands._project_output_format(args) == "text"


def test_project_registry_path_none_when_unset():
    args = _ns(registry=None)
    assert cli_commands._project_registry_path(args) is None


def test_project_registry_path_expands_user(tmp_path):
    target = tmp_path / "registry.json"
    args = _ns(registry=str(target))
    resolved = cli_commands._project_registry_path(args)
    assert isinstance(resolved, Path)
    assert resolved == target


def test_print_project_payload_json(capsys):
    payload = {"message": "ok", "project_root": "/x", "brain_root": "/b", "status": "ready"}
    cli_commands._print_project_payload(payload, "json")
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed == payload


def test_print_project_payload_text(capsys):
    payload = {
        "message": "Project attached",
        "project_root": "/proj",
        "brain_root": "/brain",
        "status": "initialized",
        "brain_id": "project-x",
    }
    cli_commands._print_project_payload(payload, "text")
    out = capsys.readouterr().out
    assert "Project attached" in out
    assert "Project root: /proj" in out
    assert "Brain root: /brain" in out
    assert "Status: initialized" in out
    assert "Brain id: project-x" in out


def test_register_project_subcommands_status_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="project_cmd")
    cli_commands._register_project_subcommands(sub)

    args = parser.parse_args(["status"])
    assert args.project == "."
    assert args.registry is None
    assert args.format is None
    assert args.func is cli_commands._handle_project_status


def test_register_project_subcommands_init_sync_flag():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="project_cmd")
    cli_commands._register_project_subcommands(sub)

    args = parser.parse_args(["init", "--sync", "--project", "/tmp/p"])
    assert args.sync is True
    assert args.project == "/tmp/p"
    assert args.func is cli_commands._handle_project_init
