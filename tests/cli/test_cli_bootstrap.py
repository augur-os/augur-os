"""Coverage tests for src.cli_bootstrap."""

import sys

from src.cli_bootstrap import (
    _get_user_dir,
    resolve_project_root,
    should_reexec_cli_from_project_root,
)


def test_cli_bootstrap_exports_expected_helpers():
    assert callable(resolve_project_root)
    assert _get_user_dir().name == ".augur"


def test_cli_bootstrap_reexecs_repo_source_running_under_global_python(
    tmp_path,
    monkeypatch,
):
    project_root = tmp_path / "Augur"
    repo_marker = project_root / "src" / "mcp" / "augur_shared"
    repo_marker.mkdir(parents=True)
    cli_file = project_root / "src" / "cli.py"
    cli_file.parent.mkdir(parents=True, exist_ok=True)
    cli_file.write_text("# cli\n", encoding="utf-8")
    project_python = project_root / ".venv" / "bin" / "python3"
    project_python.parent.mkdir(parents=True)
    project_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "executable", str(tmp_path / "pipx" / "bin" / "python"))

    assert should_reexec_cli_from_project_root(project_root, cli_file)
