from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_leads_with_fast_launch_folder_inventory() -> None:
    readme = _read("README.md")
    working = readme.split("## Working Locally", 1)[1].split("## Release Staging", 1)[0]

    fast_launch_pos = working.index("Fast launch from a desktop AI client:")
    fallback_pos = working.index("Shell fallback for contributors who want the full repo-first workspace:")
    manual_clone_pos = working.index(
        "Manual clone remains useful for contributors who want direct control over bootstrap:"
    )

    assert fast_launch_pos < fallback_pos < manual_clone_pos
    assert "choose the folder you want augur to initialize" in working.lower()
    assert "aug init --project <folder>" in working
    assert "uv run aug init --project <folder>" in working
    assert "project-brain/config/inventory/ai-artifacts.json" in working
    assert "After dependency sync, use the managed dev workflow" in working
    assert "run `uv run aug init --project .`" in working
    assert "pnpm --filter dashboard dev" not in working


def test_public_copy_uses_launch_week_promise_and_project_question() -> None:
    paths = [
        "README.md",
        "docs/getting-started.md",
        "docs/user-guide.md",
        "docs/guides/installation-windows.md",
    ]

    for path in paths:
        text = _read(path)
        assert "Get to know your AI setup, build your local second brain, and talk with your projects." in text
        assert "Which folder should I initialize?" in text
        assert "Ask Augur about this project" in text


def test_create_augur_copy_points_to_folder_init_inventory() -> None:
    readme = _read("packages/create-augur/README.md")
    index = _read("packages/create-augur/index.js")

    assert "fallback" in readme.lower()
    assert "aug init --project" in readme
    assert "AI artifact inventory" in index
    assert "aug init --project" in index
    assert "uv run aug init --project" in readme
    assert "uv run aug init --project" in index
    assert "managed dev workflow" in index
    assert "pnpm --filter dashboard dev" not in index


def test_windows_installer_completion_leads_with_fast_launch_before_dashboard() -> None:
    text = _read("scripts/install.ps1")
    completion = text.split("function Show-Completion", 1)[1].split("# ═", 1)[0]

    fast_launch_pos = completion.index("Fast launch next step")
    contributor_pos = completion.index("Contributor validation")

    assert fast_launch_pos < contributor_pos
    assert "uv run aug init --project <folder>" in completion
    assert "AI artifact inventory" in completion
    assert "pnpm --filter dashboard dev" not in completion
    assert "$INSTALL_DIR\\project-brain\\capabilities\\skills\\" in completion
    assert "$INSTALL_DIR\\skills\\" not in completion


def test_posix_installer_completion_leads_with_fast_launch_before_generic_steps() -> None:
    text = _read("scripts/install.sh")
    completion = text.split('print_success "Environment ready."', 1)[1].split("# ═", 1)[0]

    fast_launch_pos = completion.index("Fast launch next step: choose a folder and run:")
    next_steps_pos = completion.index("Next steps:")
    uv_guidance_pos = completion.index("uv run <command>")

    assert fast_launch_pos < next_steps_pos
    assert fast_launch_pos < uv_guidance_pos
    assert "uv run aug init --project <folder>" in completion
    assert "AI artifact inventory" in completion
    assert "Try: /ask, /search, or /save" not in completion
    assert "Ask Augur about this project" in completion


def test_create_augur_readme_distinguishes_fast_launch_and_shell_fallback() -> None:
    text = _read("packages/create-augur/README.md")

    assert "shell fallback" in text
    assert "desktop-chat install prompt" in text
    assert "aug init --project <folder>" in text
    assert "uv run aug init --project <folder>" in text
    assert "AI artifact inventory" in text
    assert "full repo-first workspace" in text
    assert "installs Python and Node dependencies" in text


def test_create_augur_help_names_supported_setup() -> None:
    package_json = json.loads(_read("packages/create-augur/package.json"))
    bin_target = package_json["bin"]["create-augur"]
    assert bin_target == "./index.js"

    result = subprocess.run(
        ["npm", "--prefix", "packages/create-augur", "exec", "--", "create-augur", "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Creates a repo-first full Augur workspace" in result.stdout
    assert "Shell fallback for the fast-launch install prompt" in result.stdout
    assert "uv run aug init --project <folder>" in result.stdout


def test_create_augur_initializes_fresh_repo_on_main_branch() -> None:
    text = _read("packages/create-augur/index.js")

    assert "run('git', ['init', '-b', 'main']" in text


def test_create_augur_scaffolds_vault_skill_roots_for_new_users() -> None:
    text = _read("packages/create-augur/index.js")

    assert "function ensureExternalDirs(name)" in text
    assert "path.join(vaultDir, 'skills')" in text
    assert "path.join(vaultDir, 'drafts', 'staging')" in text
    assert "'.augur-vault'" in text
    assert "ensureExternalDirs(name)" in text


def test_getting_started_leads_with_fast_launch_not_repo_first() -> None:
    text = _read("docs/getting-started.md")

    fast_launch_pos = text.index("## Fast Launch")
    contributor_pos = text.index("## Contributor Full Workspace")

    assert fast_launch_pos < contributor_pos
    assert "desktop AI chat" in text
    assert "choose a folder" in text.lower()
    assert "aug init --project <folder>" in text
    assert "uv run aug init --project <folder>" in text
    assert "read-only AI artifact inventory" in text
    assert "current source-of-truth workflow is repo-first" not in text
    assert "## Clone The Repo" not in text
    assert "## Run The Dashboard" not in text


def test_user_guide_first_use_points_to_fast_launch() -> None:
    text = _read("docs/user-guide.md")
    first_use = text.split("## What To Use First", 1)[1].split("## Good Starting Points", 1)[0]

    assert "desktop AI chat" in first_use
    assert "choose a folder" in first_use.lower()
    assert "aug init --project <folder>" in first_use
    assert "uv run aug init --project <folder>" in first_use
    assert "read-only AI artifact inventory" in first_use
    assert "repo-first workflow and the dashboard" not in first_use


def test_windows_install_guide_leads_with_fast_launch_inventory() -> None:
    text = _read("docs/guides/installation-windows.md")
    installation = text.split("## Installation", 1)[1].split("### Direct PowerShell bootstrap", 1)[0]
    structure = text.split("## Directory Structure", 1)[1].split("## Troubleshooting", 1)[0]
    question_pos = installation.index("Which folder should I initialize?")
    bootstrap_pos = installation.index("windows-one-click-bootstrap.ps1")

    assert "desktop AI chat" in installation
    assert "choose a folder" in installation.lower()
    assert question_pos < bootstrap_pos
    assert "aug init --project <folder>" in installation
    assert "uv run aug init --project <folder>" in installation
    assert "read-only AI artifact inventory" in installation
    assert "repo-first setup in [../getting-started.md]" not in installation
    assert "project-brain\\capabilities\\skills\\" in structure
    assert "├── skills\\" not in structure


def test_public_contributor_dashboard_copy_uses_managed_dev_workflow() -> None:
    paths = [
        "CONTRIBUTING.md",
        "docs/developer-guide.md",
        "project-brain/capabilities/skills/onboard/references/mode-default.md",
    ]

    for path in paths:
        text = _read(path)
        assert "pnpm --filter dashboard dev" not in text
        assert "managed dev workflow" in text or "/dev-build" in text
