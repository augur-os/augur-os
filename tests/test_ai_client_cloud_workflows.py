from __future__ import annotations

import json
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_gemini_workflow_is_review_first():
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "gemini.yml").read_text(encoding="utf-8"))

    assert workflow["name"] == "Gemini Review"
    assert "pull_request" in workflow[True]
    assert "issue_comment" in workflow[True]
    permissions = workflow["permissions"]
    assert permissions["contents"] == "read"
    assert permissions["pull-requests"] == "write"
    assert permissions["issues"] == "write"
    assert "push" not in workflow[True]


def test_gemini_workflow_checks_out_reviewed_pr_ref():
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "gemini.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["gemini-review"]["steps"]
    checkout = next(step for step in steps if step["uses"] == "actions/checkout@v4")

    assert checkout["with"]["ref"] == "${{ steps.pr.outputs.ref }}"


def test_gemini_workflow_passes_pr_number_to_action():
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "gemini.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["gemini-review"]["steps"]
    gemini = next(step for step in steps if step["uses"] == "google-github-actions/run-gemini-cli@v0")

    assert gemini["id"] == "gemini"
    assert gemini["with"]["github_pr_number"] == "${{ steps.pr.outputs.number }}"


def test_gemini_workflow_uses_read_only_tool_settings():
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "gemini.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["gemini-review"]["steps"]
    gemini = next(step for step in steps if step["uses"] == "google-github-actions/run-gemini-cli@v0")
    settings = json.loads(gemini["with"]["settings"])

    assert "coreTools" not in settings
    assert settings["tools"]["core"] == ["read_file", "grep_search", "glob", "list_directory"]


def test_gemini_workflow_posts_review_summary_to_pr():
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "gemini.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["gemini-review"]["steps"]
    comment = next(step for step in steps if step.get("name") == "Publish Gemini review comment")

    assert comment["uses"] == "actions/github-script@v7"
    assert comment["env"]["PR_NUMBER"] == "${{ steps.pr.outputs.number }}"
    assert comment["env"]["GEMINI_SUMMARY"] == "${{ steps.gemini.outputs.summary }}"
    assert comment["env"]["GEMINI_ERROR"] == "${{ steps.gemini.outputs.error }}"
    script = comment["with"]["script"]
    assert "github.rest.issues.createComment" in script
    assert "process.env.PR_NUMBER" in script
    assert "Gemini Review" in script


def test_cloud_profile_points_to_existing_workflows():
    profile = yaml.safe_load((PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml").read_text(encoding="utf-8"))
    clients = profile["clients"]

    for client in ("codex", "claude", "gemini"):
        workflow = clients[client]["cloud"]["github_workflow"]
        assert (PROJECT_ROOT / workflow).exists(), f"{client} workflow missing: {workflow}"


def test_cloud_profile_keeps_mutation_out_of_default_modes():
    profile = yaml.safe_load((PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml").read_text(encoding="utf-8"))
    mutation = set(profile["mutation_modes"])

    for client_id, client in profile["clients"].items():
        default_modes = set(client["cloud"]["default_modes"])
        assert not default_modes & mutation, client_id
