from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "windows_one_click.py"
)


def load_windows_one_click():
    spec = importlib.util.spec_from_file_location(
        "windows_one_click",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_state_path_prefers_localappdata(monkeypatch, tmp_path):
    local_app_data = tmp_path / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    module = load_windows_one_click()

    assert module.bootstrap_state_path() == (
        local_app_data / "Augur" / "setup" / "bootstrap-state.json"
    )


def test_ready_report_requires_all_core_checks():
    module = load_windows_one_click()
    checks = {key: True for key in module.CORE_CHECKS}

    report = module.classify_readiness(checks)

    assert report["state"] == "Ready"
    assert (
        report["summary"]
        == "Augur is installed, vault is connected, indexes are built, Codex is connected, daemon is running, dashboard verified."
    )


def test_missing_codex_auth_reports_needs_sign_in():
    module = load_windows_one_click()
    checks = {
        "codex_installed": True,
        "codex_authenticated": False,
    }

    report = module.classify_readiness(checks)

    assert report["state"] == "Needs sign-in"
    assert "codex login" in report["next_action"]


def test_state_round_trip_writes_json(tmp_path):
    module = load_windows_one_click()
    state_path = tmp_path / "bootstrap-state.json"
    payload = {
        "codex_installed": True,
        "codex_authenticated": False,
        "setup_phase": "codex",
    }

    module.write_bootstrap_state(payload, state_path)

    assert json.loads(state_path.read_text(encoding="utf-8")) == payload
    assert module.read_bootstrap_state(state_path) == payload


def test_simple_yaml_fallback_handles_nested_vault_config(tmp_path):
    module = load_windows_one_click()
    path = tmp_path / "vault.yaml"
    path.write_text(
        "vault:\n"
        "  path: ./vault\n"
        "  remote: ''\n"
        "  git:\n"
        "    auto_commit: true\n"
        "    branch: main\n",
        encoding="utf-8",
    )

    data = module._read_simple_yaml_file(path)
    data["vault"]["remote"] = "https://example.test/vault.git"
    module._write_yaml_file(path, data)
    reparsed = module._read_yaml_file(path)

    assert data["vault"]["path"] == "./vault"
    assert data["vault"]["git"]["auto_commit"] is True
    assert reparsed["vault"]["remote"] == "https://example.test/vault.git"


def test_invalid_state_json_reports_read_error_and_blocks_status(tmp_path):
    module = load_windows_one_click()
    state_path = tmp_path / "bootstrap-state.json"
    state_path.write_text("{not-json", encoding="utf-8")

    state = module.read_bootstrap_state(state_path)
    checks = {key: bool(state.get(key)) for key in module.CORE_CHECKS}
    report = module.classify_readiness(checks)

    assert state["state_read_error"].startswith("invalid bootstrap state JSON:")
    assert str(state_path) in state["state_read_error"]
    assert report["state"] == "Blocked"


def test_run_dependencies_uses_uv_and_dashboard_pnpm(tmp_path):
    module = load_windows_one_click()
    calls = []

    def fake_run(command, cwd, timeout, env=None):
        calls.append((command, Path(cwd), timeout, env))
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    with patch.object(module, "run_checked", side_effect=fake_run):
        result = module.run_dependencies(tmp_path)

    assert result is True
    assert calls[0][0] == [
        "uv",
        "sync",
        "--group",
        "dev",
        "--extra",
        "windows",
        "--python",
        module.sys.executable,
    ]
    assert calls[0][1] == tmp_path
    assert calls[1][0] == ["corepack", "enable"]
    assert calls[1][1] == tmp_path / "apps" / "dashboard"
    assert calls[2][0] == ["corepack", "pnpm", "install"]
    assert calls[2][1] == tmp_path / "apps" / "dashboard"
    assert calls[0][3]["PYTHONUTF8"] == "1"
    assert calls[0][3]["PYTHONIOENCODING"] == "utf-8"


def test_ensure_corepack_pnpm_falls_back_when_enable_needs_admin(tmp_path):
    module = load_windows_one_click()
    calls = []

    def fake_run(command, cwd, timeout=600, env=None):
        calls.append(command)
        if command == ["corepack", "enable"]:
            raise subprocess.CalledProcessError(1, command, stderr="EPERM")
        return CompletedProcess(command, 0, stdout="10.33.2", stderr="")

    with patch.object(module, "run_checked", side_effect=fake_run):
        result = module.ensure_corepack_pnpm(tmp_path)

    assert result is True
    assert calls == [
        ["corepack", "enable"],
        ["corepack", "pnpm", "--version"],
    ]


def test_ensure_vault_ready_blocks_noninteractive_missing_git(tmp_path):
    module = load_windows_one_click()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "project.yaml").write_text(
        "name: test\npaths:\n  vault: ./vault\n",
        encoding="utf-8",
    )
    vault = repo_root / "vault"
    (vault / "memory").mkdir(parents=True)

    result = module.ensure_vault_ready(repo_root, prompt_for_vault=False)

    assert result["ok"] is False
    assert "not a git repo" in result["detail"]
    assert "--init-local-vault" in result["detail"]


def test_ensure_vault_ready_initializes_local_vault_and_persists_config(tmp_path):
    module = load_windows_one_click()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "config" / "system").mkdir(parents=True)
    (repo_root / "project.yaml").write_text(
        "name: test\npaths:\n  vault: ./vault\n",
        encoding="utf-8",
    )
    (repo_root / "config" / "system" / "vault.yaml").write_text(
        "vault:\n  path: ./vault\n  remote: ''\n",
        encoding="utf-8",
    )
    calls = []

    def fake_run(command, cwd, timeout=600, env=None):
        calls.append((command, Path(cwd)))
        if command[:4] == ["git", "-C", str(repo_root / "vault"), "init"]:
            (repo_root / "vault" / ".git").mkdir(parents=True, exist_ok=True)
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    with patch.object(module, "run_checked", side_effect=fake_run):
        result = module.ensure_vault_ready(
            repo_root,
            vault_repo="https://example.test/vault.git",
            init_local_vault=True,
            prompt_for_vault=False,
        )

    assert result["ok"] is True
    assert (repo_root / "vault" / "memory").is_dir()
    assert (repo_root / "vault" / ".augur-vault").is_file()
    assert any(command[:4] == ["git", "-C", str(repo_root / "vault"), "init"] for command, _ in calls)
    assert "https://example.test/vault.git" in (
        repo_root / "config" / "system" / "vault.yaml"
    ).read_text(encoding="utf-8")


def test_run_indexes_uses_project_python_and_explicit_vault(tmp_path):
    module = load_windows_one_click()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    venv_python = repo_root / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    vault = tmp_path / "vault"
    calls = []

    def fake_run(command, cwd, timeout=600, env=None):
        calls.append((command, Path(cwd), timeout, env))
        return CompletedProcess(command, 0, stdout="Indexed 3 entries\n", stderr="")

    with patch.object(module, "run_checked", side_effect=fake_run):
        result = module.run_indexes(repo_root, vault)

    assert result["ok"] is True
    command, cwd, timeout, env = calls[0]
    assert command[0] == str(venv_python)
    assert command[1].endswith("unified_indexer.py")
    assert "--vault-dir" in command
    assert str(vault) in command
    assert cwd == repo_root
    assert timeout == 1800
    assert env["AUGUR_VAULT"] == str(vault)


def test_verify_codex_rejects_runtime_config_issues(tmp_path):
    module = load_windows_one_click()
    with patch.object(
        module,
        "codex_runtime_config_issues",
        return_value=["missing MCP server augur-core"],
    ):
        result = module.verify_codex(tmp_path)

    assert result["ok"] is False
    assert "missing MCP server augur-core" in result["detail"]


def test_codex_auth_uses_login_status_without_model_call():
    module = load_windows_one_click()
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, stdout="Logged in using ChatGPT", stderr="")

    with patch.object(module.subprocess, "run", side_effect=fake_run):
        assert module.is_codex_authenticated() is True

    assert calls == [["codex", "login", "status"]]


def test_codex_auth_falls_back_for_older_cli_without_status():
    module = load_windows_one_click()
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command == ["codex", "login", "status"]:
            return CompletedProcess(command, 2, stdout="", stderr="unknown command")
        return CompletedProcess(command, 0, stdout="AUGUR_AUTH_OK", stderr="")

    with patch.object(module.subprocess, "run", side_effect=fake_run):
        assert module.is_codex_authenticated() is True

    assert calls == [
        ["codex", "login", "status"],
        ["codex", "exec", "Respond exactly with AUGUR_AUTH_OK."],
    ]


def test_verify_daemon_accepts_running_daemon(tmp_path):
    module = load_windows_one_click()
    with patch.object(
        module, "collect_windows_daemon_status", return_value={"daemon": "running"}
    ):
        result = module.verify_daemon(tmp_path)

    assert result == {"ok": True, "detail": "daemon=running"}


def test_verify_daemon_rejects_registered_but_stopped_daemon(tmp_path):
    module = load_windows_one_click()
    with patch.object(
        module, "collect_windows_daemon_status", return_value={"daemon": "installed"}
    ):
        result = module.verify_daemon(tmp_path)

    assert result == {"ok": False, "detail": "daemon=installed"}


def test_verify_dashboard_runs_playwright_smoke(tmp_path):
    module = load_windows_one_click()
    calls = []
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)

    def fake_run(command, cwd, timeout):
        calls.append((command, Path(cwd), timeout))
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    with patch.object(module, "run_checked", side_effect=fake_run):
        result = module.verify_dashboard(tmp_path)

    assert result == {"ok": True, "detail": "dashboard browser smoke passed"}
    assert calls == [
        (
            ["corepack", "pnpm", "run", "prebuild"],
            dashboard_dir,
            600,
        ),
        (
            [
                "corepack",
                "pnpm",
                "exec",
                "playwright",
                "test",
                "windows-onboarding-smoke.spec.ts",
                "--config",
                "playwright.windows-onboarding.config.ts",
                "--project=chromium",
                "--reporter=line",
            ],
            dashboard_dir,
            180,
        )
    ]


def test_verify_dashboard_rejects_mcp_tool_load_failures(tmp_path):
    module = load_windows_one_click()
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)

    def fake_run(command, cwd, timeout):
        if command == ["corepack", "pnpm", "run", "prebuild"]:
            return CompletedProcess(command, 0, stdout="ok", stderr="")
        return CompletedProcess(
            command,
            0,
            stdout="[MCPBridge] Server warning: WARNING: Failed to load MCP tools from life/finance: No module named 'augur_mcp'",
            stderr="",
        )

    with patch.object(module, "run_checked", side_effect=fake_run):
        result = module.verify_dashboard(tmp_path)

    assert result["ok"] is False
    assert "dashboard MCP backend failure" in result["detail"]
    assert "Failed to load MCP tools" in result["detail"]


def test_run_setup_stops_at_codex_sign_in(tmp_path):
    module = load_windows_one_click()
    (tmp_path / "project.yaml").write_text("name: test\n", encoding="utf-8")
    with patch.object(module, "is_codex_installed", return_value=True), patch.object(
        module, "is_codex_authenticated", return_value=False
    ):
        report = module.run_setup(tmp_path)

    assert report["state"] == "Needs sign-in"
    assert report["checks"]["codex_installed"] is True
    assert report["checks"]["codex_authenticated"] is False


def test_run_setup_blocks_without_repo_root_before_side_effects(tmp_path):
    module = load_windows_one_click()
    captured_states = []
    with patch.object(module, "is_codex_installed", return_value=True), patch.object(
        module, "is_codex_authenticated", return_value=True
    ), patch.object(module, "run_dependencies") as run_dependencies, patch.object(
        module, "write_bootstrap_state", side_effect=captured_states.append
    ):
        report = module.run_setup(tmp_path)

    run_dependencies.assert_not_called()
    assert report["state"] == "Blocked"
    assert report["checks"]["repo_ready"] is False
    assert "project.yaml" in report["detail"]
    assert captured_states


def test_run_setup_records_dependency_failure_without_traceback(tmp_path):
    module = load_windows_one_click()
    (tmp_path / "project.yaml").write_text("name: test\n", encoding="utf-8")
    captured_states = []
    dependency_error = subprocess.CalledProcessError(
        1,
        ["uv"],
        output="out",
        stderr="dep failed",
    )

    with patch.object(module, "is_codex_installed", return_value=True), patch.object(
        module, "is_codex_authenticated", return_value=True
    ), patch.object(
        module, "run_dependencies", side_effect=dependency_error
    ), patch.object(
        module, "write_bootstrap_state", side_effect=captured_states.append
    ):
        report = module.run_setup(tmp_path)

    assert report["state"] == "Blocked"
    assert report["checks"]["dependencies_ready"] is False
    assert "dep failed" in report["detail"]
    assert captured_states
    assert captured_states[-1]["dependencies_ready"] is False


def test_run_setup_blocks_when_vault_is_not_ready(tmp_path):
    module = load_windows_one_click()
    (tmp_path / "project.yaml").write_text("name: test\n", encoding="utf-8")
    captured_states = []

    with patch.object(module, "is_codex_installed", return_value=True), patch.object(
        module, "is_codex_authenticated", return_value=True
    ), patch.object(module, "run_dependencies", return_value=True), patch.object(
        module,
        "ensure_vault_ready",
        return_value={"ok": False, "detail": "vault missing git", "path": str(tmp_path / "vault")},
    ), patch.object(module, "sync_codex") as sync_codex, patch.object(
        module, "write_bootstrap_state", side_effect=captured_states.append
    ):
        report = module.run_setup(tmp_path, prompt_for_vault=False)

    sync_codex.assert_not_called()
    assert report["state"] == "Blocked"
    assert report["checks"]["vault_ready"] is False
    assert "vault setup required: vault missing git" in report["detail"]
    assert captured_states


def test_run_setup_blocks_and_persists_failed_dashboard_smoke(tmp_path):
    module = load_windows_one_click()
    (tmp_path / "project.yaml").write_text("name: test\n", encoding="utf-8")
    captured_states = []

    with patch.object(module, "is_codex_installed", return_value=True), patch.object(
        module, "is_codex_authenticated", return_value=True
    ), patch.object(module, "run_dependencies", return_value=True), patch.object(
        module,
        "ensure_vault_ready",
        return_value={"ok": True, "detail": "vault ok", "path": str(tmp_path / "vault")},
    ), patch.object(
        module, "sync_codex"
    ), patch.object(
        module,
        "verify_codex",
        return_value={"ok": True, "detail": "codex runtime config is current"},
    ), patch.object(
        module,
        "run_indexes",
        return_value={"ok": True, "detail": "indexes ok"},
    ), patch.object(
        module, "install_or_heal_daemon"
    ), patch.object(
        module, "verify_daemon", return_value={"ok": True, "detail": "daemon=running"}
    ), patch.object(
        module,
        "verify_dashboard",
        return_value={"ok": False, "detail": "playwright smoke failed"},
    ), patch.object(
        module, "write_bootstrap_state", side_effect=captured_states.append
    ):
        report = module.run_setup(tmp_path)

    assert report["state"] == "Blocked"
    assert report["checks"]["dashboard_verified"] is False
    assert "dashboard verification failed: playwright smoke failed" in report["detail"]
    assert captured_states
    assert captured_states[-1]["dashboard_verified"] is False


@pytest.mark.parametrize(
    ("error", "expected_detail"),
    [
        (subprocess.TimeoutExpired(["uv"], timeout=30), "timed out"),
        (FileNotFoundError("missing executable"), "missing executable"),
    ],
)
def test_command_error_detail_formats_expected_failures(error, expected_detail):
    module = load_windows_one_click()

    assert expected_detail in module._command_error_detail(error)
