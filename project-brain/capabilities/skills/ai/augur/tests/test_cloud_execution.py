from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_load_cloud_profiles_has_four_primary_clients():
    from src.lib.ai.cloud_execution import load_cloud_profiles

    profiles = load_cloud_profiles(PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml")

    assert set(profiles) == {"codex", "claude", "gemini", "copilot"}
    assert profiles["copilot"].cloud.vendor_surface == "copilot-cloud-agent"
    assert profiles["copilot"].cloud.default_modes == ("read", "review", "plan")
    assert profiles["copilot"].cloud.mutation_modes == ("fix", "commit", "pr")


def test_status_reports_ready_for_review_when_workflow_and_secret_exist(tmp_path):
    from src.lib.ai.cloud_execution import classify_cloud_status, load_cloud_profiles

    workflow = tmp_path / ".github" / "workflows" / "claude.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Claude\n", encoding="utf-8")

    profiles = load_cloud_profiles(PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml")
    status = classify_cloud_status(
        profiles["claude"],
        repo_root=tmp_path,
        env={"CLAUDE_CODE_OAUTH_TOKEN": "present"},
        command_exists=lambda command: f"/usr/bin/{command}",
    )

    assert status.status == "ready"
    assert status.cloud_review_ready is True
    assert status.cloud_mutation_enabled is False
    assert "mutation mode requires explicit opt-in" in status.mutation_blockers


def test_status_reports_missing_secret_without_exposing_values(tmp_path):
    from src.lib.ai.cloud_execution import classify_cloud_status, load_cloud_profiles

    workflow = tmp_path / ".github" / "workflows" / "claude.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Claude\n", encoding="utf-8")

    profiles = load_cloud_profiles(PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml")
    status = classify_cloud_status(
        profiles["claude"],
        repo_root=tmp_path,
        env={},
        command_exists=lambda command: f"/usr/bin/{command}",
    )

    assert status.status == "missing-secret"
    assert status.cloud_review_ready is False
    assert status.blockers == ("missing secret: CLAUDE_CODE_OAUTH_TOKEN",)
    assert "present" not in repr(status)


def test_copilot_without_github_app_is_needs_github_app(tmp_path):
    from src.lib.ai.cloud_execution import classify_cloud_status, load_cloud_profiles

    profiles = load_cloud_profiles(PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml")
    status = classify_cloud_status(
        profiles["copilot"],
        repo_root=tmp_path,
        env={},
        command_exists=lambda command: "/opt/homebrew/bin/copilot" if command == "copilot" else None,
    )

    assert status.status == "needs-github-app"
    assert status.local_cli_present is True
    assert "needs app or connector: copilot_cloud_agent_enabled" in status.blockers


def test_explicit_mutation_opt_in_enables_mutation_when_review_is_ready(tmp_path):
    from src.lib.ai.cloud_execution import classify_cloud_status, load_cloud_profiles

    workflow = tmp_path / ".github" / "workflows" / "gemini.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Gemini\n", encoding="utf-8")

    profiles = load_cloud_profiles(PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml")
    status = classify_cloud_status(
        profiles["gemini"],
        repo_root=tmp_path,
        env={"GEMINI_API_KEY": "present"},
        command_exists=lambda command: f"/usr/bin/{command}",
        enabled_mutation_clients={"gemini"},
    )

    assert status.status == "ready"
    assert status.cloud_mutation_enabled is True
    assert status.mutation_blockers == ()


def test_load_cloud_profiles_rejects_non_mapping_cloud_section(tmp_path):
    from src.lib.ai.cloud_execution import load_cloud_profiles

    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        """
schema_version: 1
default_safe_modes: [read, review, plan]
mutation_modes: [fix, commit, pr]
clients:
  badclient:
    display_name: Bad Client
    local:
      cli: bad
      plugin_pack: bad
      mcp_client_id: bad
    cloud: not-a-map
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="badclient.*cloud"):
        load_cloud_profiles(profile_path)


def test_load_cloud_profiles_rejects_missing_required_core_fields(tmp_path):
    from src.lib.ai.cloud_execution import load_cloud_profiles

    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        """
schema_version: 1
default_safe_modes: [read, review, plan]
mutation_modes: [fix, commit, pr]
clients:
  badclient:
    display_name: Bad Client
    local:
      cli: bad
    cloud:
      vendor_surface: bad-cloud
      execution_kind: hosted
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="badclient.*local.plugin_pack"):
        load_cloud_profiles(profile_path)


def test_load_cloud_profiles_rejects_missing_required_cloud_readiness_lists(tmp_path):
    from src.lib.ai.cloud_execution import load_cloud_profiles

    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        """
schema_version: 1
default_safe_modes: [read, review, plan]
mutation_modes: [fix, commit, pr]
clients:
  badclient:
    display_name: Bad Client
    local:
      cli: bad
      plugin_pack: bad
      mcp_client_id: bad
      config_paths: []
    cloud:
      vendor_surface: bad-cloud
      execution_kind: hosted
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      required_apps: []
      enterprise_notes: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="badclient.*cloud.required_secrets"):
        load_cloud_profiles(profile_path)


def test_load_cloud_profiles_rejects_scalar_required_apps(tmp_path):
    from src.lib.ai.cloud_execution import load_cloud_profiles

    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        """
schema_version: 1
default_safe_modes: [read, review, plan]
mutation_modes: [fix, commit, pr]
clients:
  badclient:
    display_name: Bad Client
    local:
      cli: bad
      plugin_pack: bad
      mcp_client_id: bad
      config_paths: []
    cloud:
      vendor_surface: bad-cloud
      execution_kind: hosted
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      required_secrets: []
      required_apps: not-a-list
      enterprise_notes: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="badclient.*cloud.required_apps"):
        load_cloud_profiles(profile_path)


def test_load_cloud_profiles_rejects_malformed_trigger_values(tmp_path):
    from src.lib.ai.cloud_execution import load_cloud_profiles

    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        """
schema_version: 1
default_safe_modes: [read, review, plan]
mutation_modes: [fix, commit, pr]
clients:
  badclient:
    display_name: Bad Client
    local:
      cli: bad
      plugin_pack: bad
      mcp_client_id: bad
      config_paths: []
    cloud:
      vendor_surface: bad-cloud
      execution_kind: hosted
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      triggers:
        review: not-a-list
      required_secrets: []
      required_apps: []
      enterprise_notes: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="badclient.*triggers"):
        load_cloud_profiles(profile_path)


def test_load_cloud_profiles_rejects_string_enabled_value(tmp_path):
    from src.lib.ai.cloud_execution import load_cloud_profiles

    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        """
schema_version: 1
default_safe_modes: [read, review, plan]
mutation_modes: [fix, commit, pr]
clients:
  badclient:
    display_name: Bad Client
    enabled: "false"
    local:
      cli: bad
      plugin_pack: bad
      mcp_client_id: bad
      config_paths: []
    cloud:
      vendor_surface: bad-cloud
      execution_kind: hosted
      github_workflow: null
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      required_secrets: []
      required_apps: []
      enterprise_notes: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="badclient.*enabled"):
        load_cloud_profiles(profile_path)


def test_load_cloud_profiles_rejects_scalar_top_level_default_safe_modes(tmp_path):
    from src.lib.ai.cloud_execution import load_cloud_profiles

    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        """
schema_version: 1
default_safe_modes: read
mutation_modes: [fix, commit, pr]
clients: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="default_safe_modes"):
        load_cloud_profiles(profile_path)


def test_load_cloud_profiles_rejects_missing_top_level_mutation_modes(tmp_path):
    from src.lib.ai.cloud_execution import load_cloud_profiles

    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        """
schema_version: 1
default_safe_modes: [read, review, plan]
clients: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="mutation_modes"):
        load_cloud_profiles(profile_path)


def test_load_cloud_profiles_rejects_boolean_github_workflow(tmp_path):
    from src.lib.ai.cloud_execution import load_cloud_profiles

    profile_path = tmp_path / "cloud_execution.yaml"
    profile_path.write_text(
        """
schema_version: 1
default_safe_modes: [read, review, plan]
mutation_modes: [fix, commit, pr]
clients:
  badclient:
    display_name: Bad Client
    local:
      cli: bad
      plugin_pack: bad
      mcp_client_id: bad
      config_paths: []
    cloud:
      vendor_surface: bad-cloud
      execution_kind: hosted
      github_workflow: false
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      required_secrets: []
      required_apps: []
      enterprise_notes: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="badclient.*github_workflow"):
        load_cloud_profiles(profile_path)
