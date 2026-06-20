from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])


def test_cloud_status_script_outputs_all_primary_clients():
    result = subprocess.run(
        [
            sys.executable,
            "project-brain/capabilities/skills/onboard/scripts/cloud_status.py",
            "--repo-root",
            str(PROJECT_ROOT),
            "--no-env",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "Client" in result.stdout
    assert "Codex" in result.stdout
    assert "Claude" in result.stdout
    assert "Gemini" in result.stdout
    assert "Copilot" in result.stdout
    assert "Write" in result.stdout
    assert "disabled" in result.stdout


def test_invalid_profiles_file_returns_nonzero_with_error(tmp_path):
    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text("clients: []\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "project-brain/capabilities/skills/onboard/scripts/cloud_status.py",
            "--profiles",
            str(profile_path),
            "--no-env",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "Cloud status error:" in result.stderr


def test_client_filter_outputs_only_requested_client():
    result = subprocess.run(
        [
            sys.executable,
            "project-brain/capabilities/skills/onboard/scripts/cloud_status.py",
            "--repo-root",
            str(PROJECT_ROOT),
            "--no-env",
            "--client",
            "copilot",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "GitHub Copilot" in result.stdout
    assert "OpenAI Codex" not in result.stdout
    assert "Claude Code" not in result.stdout
    assert "Gemini" not in result.stdout


def test_unknown_client_returns_usage_error():
    result = subprocess.run(
        [
            sys.executable,
            "project-brain/capabilities/skills/onboard/scripts/cloud_status.py",
            "--no-env",
            "--client",
            "nope",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert "unknown cloud client: nope" in result.stderr


def test_write_mode_enables_selected_ready_client(tmp_path):
    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        _single_client_profile(
            client_id="gemini",
            display_name="Gemini",
            cli="gemini",
            github_workflow=None,
            required_secrets=[],
            required_apps=[],
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "project-brain/capabilities/skills/onboard/scripts/cloud_status.py",
            "--repo-root",
            str(tmp_path),
            "--profiles",
            str(profile_path),
            "--no-env",
            "--mode",
            "write",
            "--client",
            "gemini",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "Gemini" in result.stdout
    assert "enabled" in result.stdout
    assert "ready" in result.stdout


def test_secret_values_are_not_printed(tmp_path, monkeypatch):
    secret_value = "do-not-print-this-secret-value"
    monkeypatch.setenv("GEMINI_API_KEY", secret_value)
    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        _single_client_profile(
            client_id="gemini",
            display_name="Gemini",
            cli="gemini",
            github_workflow=None,
            required_secrets=["GEMINI_API_KEY"],
            required_apps=[],
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "project-brain/capabilities/skills/onboard/scripts/cloud_status.py",
            "--repo-root",
            str(tmp_path),
            "--profiles",
            str(profile_path),
            "--client",
            "gemini",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert secret_value not in result.stdout
    assert secret_value not in result.stderr


def _single_client_profile(
    *,
    client_id: str,
    display_name: str,
    cli: str,
    github_workflow: str | None,
    required_secrets: list[str],
    required_apps: list[str],
) -> str:
    workflow_value = "null" if github_workflow is None else github_workflow
    return dedent(
        f"""
        schema_version: 1
        default_safe_modes: [read, review, plan]
        mutation_modes: [fix, commit, pr]
        clients:
          {client_id}:
            display_name: {display_name}
            local:
              cli: {cli}
              plugin_pack: {client_id}
              mcp_client_id: {client_id}
              config_paths: []
            cloud:
              vendor_surface: {client_id}-cloud
              execution_kind: hosted
              github_workflow: {workflow_value}
              default_modes: [read, review, plan]
              mutation_modes: [fix, commit, pr]
              triggers: {{}}
              required_secrets: {required_secrets}
              required_apps: {required_apps}
              enterprise_notes: []
        """
    )
