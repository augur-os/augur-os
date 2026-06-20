"""Regression tests for the cross-platform agent hook runner."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOOK_RUNNER = PROJECT_ROOT / "scripts" / "hooks" / "run-hook.mjs"


def run_hook(
    name: str,
    payload: dict,
    tmp_path: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for hook runner tests")

    env = {"AUGUR_RUNTIME_DIR": str(tmp_path), **dict(os.environ)}
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        [node, str(HOOK_RUNNER), name],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=PROJECT_ROOT,
        env=env,
        timeout=10,
        check=False,
    )


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def test_dashboard_shortcut_blocker_denies_dev_server_shortcuts(tmp_path: Path) -> None:
    result = run_hook(
        "dashboard-shortcut-blocker",
        {"tool_input": {"command": "cd apps/dashboard; pnpm dev"}},
        tmp_path,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    output = data["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert "/dev-build" in output["permissionDecisionReason"]


def test_check_skill_structure_warns_for_legacy_skill_manifest(tmp_path: Path) -> None:
    result = run_hook(
        "check-skill-structure",
        {"tool_input": {"file_path": "skills/example/augur/version.yaml"}},
        tmp_path,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["continue"] is True
    assert "version.yaml replaced" in data["systemMessage"]


def test_session_wiki_flag_uses_platform_runtime_dir(tmp_path: Path) -> None:
    result = run_hook("session-wiki-flag", {}, tmp_path)

    assert result.returncode == 0
    flag = tmp_path / "wiki" / "needs-update.flag"
    assert flag.exists()
    assert flag.read_text(encoding="utf-8").strip()


def test_vault_autocommit_is_silent_and_cross_platform(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    git(vault, "init", "-b", "main")
    git(vault, "config", "user.email", "test@example.com")
    git(vault, "config", "user.name", "Test User")
    note = vault / "note.md"
    note.write_text("before\n", encoding="utf-8")
    git(vault, "add", "note.md")
    git(vault, "commit", "-m", "initial")

    note.write_text("after\n", encoding="utf-8")
    result = run_hook("vault-autocommit", {}, tmp_path, {"AUGUR_VAULT": str(vault)})

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert git(vault, "status", "--short") == ""
    assert git(vault, "log", "-1", "--pretty=%s").startswith("vault: auto-commit ")
