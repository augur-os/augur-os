"""Tests for worktree preflight port resolution."""

from __future__ import annotations

# TODO_CLEANUP: This file is 1046 lines — consider splitting into smaller modules
import subprocess
import shutil
import sys
import types
from types import SimpleNamespace
from pathlib import Path

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
PROJECT_CAPABILITIES_DIR = PROJECT_ROOT / "project-brain" / "capabilities"
if PROJECT_CAPABILITIES_DIR.is_dir() and str(PROJECT_CAPABILITIES_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_CAPABILITIES_DIR))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import worktree_preflight  # noqa: E402


def test_resolve_ports_prefers_marker_values(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    ports = worktree_preflight._resolve_ports(
        tmp_path,
        {"dashboard_port": "3012", "mcp_port": "8092"},
        runtime_dir,
    )

    assert ports == {"dashboard_port": 3012, "mcp_port": 8092}


def test_resolve_ports_uses_registry_when_marker_missing(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    worktree_root = tmp_path / "wt"
    worktree_root.mkdir()

    (runtime_dir / "worktree_registry.yaml").write_text(
        "\n".join(
            [
                "worktrees:",
                f"  '{worktree_root.resolve()}':",
                "    name: \"adr-539\"",
                "    dashboard_port: 3004",
                "    mcp_port: 8084",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ports = worktree_preflight._resolve_ports(worktree_root, {}, runtime_dir)

    assert ports == {"dashboard_port": 3004, "mcp_port": 8084}


def test_dashboard_install_command_prefers_pnpm_lockfile(tmp_path: Path, monkeypatch):
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)
    (dashboard_dir / "package.json").write_text(
        '{"name":"dashboard","packageManager":"pnpm@10.32.1"}\n',
        encoding="utf-8",
    )
    (dashboard_dir / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")

    monkeypatch.setattr(
        worktree_preflight.shutil,
        "which",
        lambda tool: "/usr/bin/pnpm" if tool == "pnpm" else None,
    )

    assert worktree_preflight._dashboard_install_command(dashboard_dir) == ["/usr/bin/pnpm", "install"]


def test_dashboard_install_command_uses_resolved_windows_command(tmp_path: Path, monkeypatch):
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)
    (dashboard_dir / "package.json").write_text(
        '{"name":"dashboard","packageManager":"pnpm@10.32.1"}\n',
        encoding="utf-8",
    )
    (dashboard_dir / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")

    monkeypatch.setattr(
        worktree_preflight.shutil,
        "which",
        lambda tool: "C:/tools/pnpm.cmd" if tool == "pnpm" else None,
    )

    assert worktree_preflight._dashboard_install_command(dashboard_dir) == [
        "C:/tools/pnpm.cmd",
        "install",
    ]


def test_dashboard_install_command_falls_back_to_npm_without_pnpm(tmp_path: Path, monkeypatch):
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)
    (dashboard_dir / "package.json").write_text('{"name":"dashboard"}\n', encoding="utf-8")

    monkeypatch.setattr(worktree_preflight.shutil, "which", lambda _tool: None)

    assert worktree_preflight._dashboard_install_command(dashboard_dir) == [
        "npm",
        "install",
        "--no-fund",
        "--no-audit",
    ]


def test_resolve_python_path_prefers_windows_venv(tmp_path: Path, monkeypatch):
    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")

    monkeypatch.setattr("worktree_preflight._is_windows", lambda: True)
    monkeypatch.setattr(
        worktree_preflight.shutil,
        "which",
        lambda _tool: "C:/Users/test/AppData/Local/Microsoft/WindowsApps/python3.exe",
    )

    assert worktree_preflight._resolve_python_path(tmp_path) == venv_python


def test_resolve_python_path_prefers_explicit_augur_python(tmp_path: Path, monkeypatch):
    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    explicit_python = tmp_path / "external" / "python.exe"
    explicit_python.parent.mkdir()
    explicit_python.write_text("", encoding="utf-8")

    monkeypatch.setattr("worktree_preflight._is_windows", lambda: True)
    monkeypatch.setenv("AUGUR_PYTHON", str(explicit_python))

    assert worktree_preflight._resolve_python_path(tmp_path) == explicit_python


def test_resolve_python_path_ignores_windows_store_alias(tmp_path: Path, monkeypatch):
    fallback_python = tmp_path / "real-python.exe"
    fallback_python.write_text("", encoding="utf-8")

    monkeypatch.setattr("worktree_preflight._is_windows", lambda: True)
    monkeypatch.setattr(
        worktree_preflight.shutil,
        "which",
        lambda _tool: "C:/Users/test/AppData/Local/Microsoft/WindowsApps/python3.exe",
    )
    monkeypatch.setattr(worktree_preflight.sys, "executable", str(fallback_python))

    assert worktree_preflight._resolve_python_path(tmp_path) == fallback_python


def test_run_sync_bootstrap_uses_resolved_python_and_platform_pathsep(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "repo"
    project_root.mkdir()
    mcp_script = project_root / "scripts" / "generate-worktree-mcp.py"
    mcp_script.parent.mkdir()
    mcp_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    resolved_python = tmp_path / "python.exe"

    monkeypatch.setattr(worktree_preflight, "_resolve_python_path", lambda _root: resolved_python)

    calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_run(cmd, cwd=None, check=None, capture_output=None, text=None, env=None, **kwargs):
        calls.append((cmd, env))
        assert cwd == project_root
        assert env is not None
        assert str(project_root) in env["PYTHONPATH"].split(worktree_preflight.os.pathsep)
        assert str(project_root / "project-brain" / "capabilities") in env["PYTHONPATH"].split(
            worktree_preflight.os.pathsep
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(worktree_preflight.subprocess, "run", fake_run)

    ok = worktree_preflight._run_sync_bootstrap(
        project_root,
        repairs=[],
        incidents=[],
        owner_path=mcp_script,
        mcp_port=8099,
    )

    assert ok is True
    assert calls[0][0][:2] == [str(resolved_python), "-c"]
    assert calls[1][0][0] == str(resolved_python)


def test_infer_dev_hubs_from_paths_maps_chat_surface_to_brain():
    hubs = worktree_preflight._infer_dev_hubs_from_paths(
        {
            "apps/dashboard/features/components/chat/ChatInput.tsx",
            "apps/dashboard/components/chat/utils.ts",
            "apps/dashboard/app/api/chat/messages/route.ts",
            "apps/dashboard/scripts/start-dev.sh",
            "tests/dashboard/components/chat/chat-redesign-port.test.tsx",
        }
    )

    assert hubs == ["brain"]


def test_infer_dev_hubs_from_paths_aborts_for_unknown_dashboard_scope():
    hubs = worktree_preflight._infer_dev_hubs_from_paths(
        {
            "apps/dashboard/features/components/chat/ChatInput.tsx",
            "apps/dashboard/app/globals.css",
        }
    )

    assert hubs == []


def test_resolve_dev_hubs_prefers_marker_value(tmp_path: Path):
    dev_hubs = worktree_preflight._resolve_dev_hubs(
        tmp_path,
        tmp_path,
        {"dev_hubs": "brain,life"},
    )

    assert dev_hubs == "brain,life"


def _make_worktree_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    main_repo = tmp_path / "main"
    worktree_root = tmp_path / "worktree"

    for repo_root in (main_repo, worktree_root):
        (repo_root / "apps" / "dashboard" / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)

    (main_repo / ".venv" / "bin").mkdir(parents=True)
    (main_repo / ".venv" / "bin" / "python3").write_text("", encoding="utf-8")
    (main_repo / ".venv" / "bin" / "ruff").write_text("", encoding="utf-8")
    (main_repo / ".venv-test").mkdir()
    (worktree_root / "apps" / "dashboard" / "node_modules" / ".bin" / "next").write_text("", encoding="utf-8")
    (worktree_root / ".augur-worktree.yaml").write_text(
        f'worktree: "true"\nmain_repo: "{main_repo}"\n',
        encoding="utf-8",
    )

    sync_output = worktree_root / ".codex" / "prompts" / "bootstrap.md"
    return runtime_dir, main_repo, worktree_root, sync_output


def test_build_contract_repairs_missing_sync_outputs_for_worktrees(tmp_path: Path, monkeypatch):
    runtime_dir, _main_repo, worktree_root, sync_output = _make_worktree_fixture(tmp_path)
    mcp_script = worktree_root / "scripts" / "generate-worktree-mcp.py"
    mcp_script.parent.mkdir(parents=True)
    mcp_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(worktree_preflight, "_repo_local_sync_output_paths", lambda _root: [sync_output])

    call_order: list[str] = []

    def fake_ensure_symlink(*_args, **_kwargs):
        call_order.append("symlink")
        return True

    def fake_ensure_dashboard_dependencies(*_args, **_kwargs):
        call_order.append("dashboard")
        return True

    monkeypatch.setattr(worktree_preflight, "_ensure_symlink", fake_ensure_symlink)
    monkeypatch.setattr(
        worktree_preflight,
        "_ensure_dashboard_dependencies",
        fake_ensure_dashboard_dependencies,
    )

    def fake_run(cmd, cwd=None, check=None, capture_output=None, text=None, env=None, **kwargs):
        # Allow pnpm alignment probe to pass through without disturbing the call_order assertion.
        if len(cmd) >= 4 and cmd[1:4] == ["config", "get", "store-dir"]:
            return subprocess.CompletedProcess(cmd, 0, str(tmp_path), "")
        assert call_order == ["symlink", "symlink", "dashboard"]
        assert cwd == worktree_root
        if len(cmd) >= 2 and cmd[1] == "-c":
            assert env is not None
            assert env["AUGUR_SYNC_PROJECT_ROOT"] == str(worktree_root)
            sync_output.parent.mkdir(parents=True, exist_ok=True)
            sync_output.write_text("bootstrapped\n", encoding="utf-8")
        elif cmd[1].endswith("generate-worktree-mcp.py"):
            pass
        else:
            raise AssertionError(f"unexpected subprocess command: {cmd}")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(worktree_preflight.subprocess, "run", fake_run)

    report = worktree_preflight.build_contract(worktree_root, "worktree", repair=True)

    assert sync_output.exists()
    sync_repair = next(repair for repair in report["repairs_applied"] if repair["type"] == "sync")
    assert sync_repair["path"] == str(worktree_root)
    assert "do_vaults=False" in sync_repair["target"]
    assert any(repair["type"] == "mcp-config" for repair in report["repairs_applied"])
    assert not any(
        incident["fingerprint"] == "worktree/bootstrap/missing-sync-outputs"
        for incident in report["incidents_detected"]
    )


def test_build_contract_includes_worktree_instance_metadata(tmp_path: Path, monkeypatch):
    runtime_dir, main_repo, worktree_root, sync_output = _make_worktree_fixture(tmp_path)
    lifecycle_dir = runtime_dir / "daemon" / "dashboard" / "worktrees" / "task-2"
    build_lock_dir = runtime_dir / "locks" / "dashboard" / "worktrees" / "task-2"
    browser_artifact_dir = runtime_dir / "browser-verification" / "worktrees" / "task-2"

    import src.config.paths as config_paths
    import src.lib.dashboard_instance as dashboard_instance

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(
        dashboard_instance,
        "resolve_dashboard_instance",
        lambda project_root, runtime_dir=None, interactive=False: SimpleNamespace(
            instance_id="worktree:task-2",
            kind="worktree",
            main_repo=main_repo,
            dashboard_port=3055,
            mcp_port=8155,
            browser_mode="headless_only",
            heal_policy="validation_only",
            visibility_policy="no_visible_mutation",
            lifecycle_dir=lifecycle_dir,
            build_lock_dir=build_lock_dir,
            browser_artifact_dir=browser_artifact_dir,
        ),
    )
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(
        worktree_preflight,
        "_repo_local_sync_output_paths",
        lambda _root: [sync_output],
    )
    monkeypatch.setattr(worktree_preflight, "_ensure_symlink", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        worktree_preflight,
        "_ensure_dashboard_dependencies",
        lambda *_args, **_kwargs: True,
    )

    report = worktree_preflight.build_contract(worktree_root, "shell", repair=False)

    assert report["instance_id"] == "worktree:task-2"
    assert report["instance_kind"] == "worktree"
    assert report["browser_mode"] == "headless_only"
    assert report["heal_policy"] == "validation_only"
    assert report["visibility_policy"] == "no_visible_mutation"
    assert report["dashboard_port"] == 3055
    assert report["mcp_port"] == 8155
    assert report["lifecycle_dir"] == str(lifecycle_dir)
    assert report["build_lock_dir"] == str(build_lock_dir)
    assert report["browser_artifact_dir"] == str(browser_artifact_dir)


def test_build_contract_treats_isolated_as_non_main_for_safeguards(tmp_path: Path, monkeypatch):
    runtime_dir, main_repo, worktree_root, sync_output = _make_worktree_fixture(tmp_path)

    import src.config.paths as config_paths
    import src.lib.dashboard_instance as dashboard_instance

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(
        dashboard_instance,
        "resolve_dashboard_instance",
        lambda project_root, runtime_dir=None, interactive=False: SimpleNamespace(
            instance_id="isolated:task-2",
            kind="isolated",
            main_repo=main_repo,
            dashboard_port=3066,
            mcp_port=8166,
            browser_mode="headless_only",
            heal_policy="disabled",
            visibility_policy="no_visible_mutation",
            lifecycle_dir=runtime_dir / "daemon" / "dashboard" / "isolated" / "task-2",
            build_lock_dir=runtime_dir / "locks" / "dashboard" / "isolated" / "task-2",
            browser_artifact_dir=runtime_dir / "browser-verification" / "isolated" / "task-2",
        ),
    )
    monkeypatch.setattr(
        worktree_preflight,
        "_load_worktree_guard_module",
        lambda: (_ for _ in ()).throw(AssertionError("main guard should not run")),
    )
    dev_hub_calls: list[tuple[Path, Path, dict[str, str]]] = []

    def fake_resolve_dev_hubs(project_root, main_repo_arg, marker):
        dev_hub_calls.append((project_root, main_repo_arg, marker))
        return "brain"

    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", fake_resolve_dev_hubs)
    monkeypatch.setattr(
        worktree_preflight,
        "_repo_local_sync_output_paths",
        lambda _root: [sync_output],
    )
    monkeypatch.setattr(worktree_preflight, "_ensure_symlink", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        worktree_preflight,
        "_ensure_dashboard_dependencies",
        lambda *_args, **_kwargs: True,
    )

    report = worktree_preflight.build_contract(worktree_root, "shell", repair=False)

    assert report["worktree"] is False
    assert report["instance_kind"] == "isolated"
    assert report["dashboard_port"] == 3066
    assert report["mcp_port"] == 8166
    assert report["dev_hubs"] == "brain"
    assert dev_hub_calls == [
        (
            worktree_root.resolve(),
            main_repo,
            {"worktree": "true", "main_repo": str(main_repo)},
        )
    ]
    assert not any(check["name"] == "main_checkout_branch" for check in report["checks"])


def test_build_contract_reports_and_bootstraps_with_resolved_instance_ports(tmp_path: Path, monkeypatch):
    runtime_dir, main_repo, worktree_root, sync_output = _make_worktree_fixture(tmp_path)
    mcp_output = worktree_root / ".claude" / "mcp.json"
    mcp_script = worktree_root / "scripts" / "generate-worktree-mcp.py"
    mcp_script.parent.mkdir(parents=True)
    mcp_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (worktree_root / ".augur-worktree.yaml").write_text(
        (f'worktree: "true"\nmain_repo: "{main_repo}"\n' 'dashboard_port: "3004"\nmcp_port: "8084"\n'),
        encoding="utf-8",
    )

    import src.config.paths as config_paths
    import src.lib.dashboard_instance as dashboard_instance

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(
        dashboard_instance,
        "resolve_dashboard_instance",
        lambda project_root, runtime_dir=None, interactive=False: SimpleNamespace(
            instance_id="worktree:task-2",
            kind="worktree",
            main_repo=main_repo,
            dashboard_port=3777,
            mcp_port=8777,
            browser_mode="headless_only",
            heal_policy="validation_only",
            visibility_policy="no_visible_mutation",
            lifecycle_dir=runtime_dir / "daemon" / "dashboard" / "worktrees" / "task-2",
            build_lock_dir=runtime_dir / "locks" / "dashboard" / "worktrees" / "task-2",
            browser_artifact_dir=runtime_dir / "browser-verification" / "worktrees" / "task-2",
        ),
    )
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(
        worktree_preflight,
        "_repo_local_sync_output_paths",
        lambda _root: [sync_output, mcp_output],
    )
    monkeypatch.setattr(worktree_preflight, "_ensure_symlink", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        worktree_preflight,
        "_ensure_dashboard_dependencies",
        lambda *_args, **_kwargs: True,
    )

    def fake_run(cmd, cwd=None, check=None, capture_output=None, text=None, env=None, **kwargs):
        if len(cmd) >= 2 and cmd[1] == "-c":
            sync_output.parent.mkdir(parents=True, exist_ok=True)
            sync_output.write_text("bootstrapped\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        if cmd[1].endswith("generate-worktree-mcp.py"):
            assert "--mcp-port" in cmd
            assert cmd[cmd.index("--mcp-port") + 1] == "8777"
            mcp_output.parent.mkdir(parents=True, exist_ok=True)
            mcp_output.write_text('{"mcpServers": {}}\n', encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(worktree_preflight.subprocess, "run", fake_run)

    report = worktree_preflight.build_contract(worktree_root, "worktree", repair=True)

    assert report["dashboard_port"] == 3777
    assert report["mcp_port"] == 8777


def test_worktree_sync_bootstrap_targets_worktree_without_global_sync(tmp_path: Path, monkeypatch):
    runtime_dir, main_repo, worktree_root, sync_output = _make_worktree_fixture(tmp_path)
    mcp_output = worktree_root / ".claude" / "mcp.json"
    mcp_script = worktree_root / "scripts" / "generate-worktree-mcp.py"
    mcp_script.parent.mkdir(parents=True)
    mcp_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (worktree_root / ".augur-worktree.yaml").write_text(
        f'worktree: "true"\nmain_repo: "{main_repo}"\nmcp_port: "8099"\n',
        encoding="utf-8",
    )

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(
        worktree_preflight,
        "_repo_local_sync_output_paths",
        lambda _root: [sync_output, mcp_output],
    )

    def fake_ensure_symlink(target, source, *_args, **_kwargs):
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return True

    monkeypatch.setattr(worktree_preflight, "_ensure_symlink", fake_ensure_symlink)
    monkeypatch.setattr(
        worktree_preflight,
        "_ensure_dashboard_dependencies",
        lambda *_args, **_kwargs: True,
    )

    calls: list[tuple[list[str], Path | None, dict[str, str] | None]] = []

    def fake_run(cmd, cwd=None, check=None, capture_output=None, text=None, env=None, **kwargs):
        # Allow pnpm alignment probe through without polluting the recorded calls list.
        if len(cmd) >= 4 and cmd[1:4] == ["config", "get", "store-dir"]:
            return subprocess.CompletedProcess(cmd, 0, str(tmp_path), "")
        calls.append((cmd, cwd, env))
        if cmd[1:] == ["-m", "skills.ai.scripts.sync_agents", "sync", "all"]:
            main_output = main_repo / sync_output.relative_to(worktree_root)
            main_output.parent.mkdir(parents=True, exist_ok=True)
            main_output.write_text("wrong root\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        if len(cmd) >= 2 and cmd[1] == "-c":
            assert cwd == worktree_root
            assert env is not None
            assert env["AUGUR_SYNC_PROJECT_ROOT"] == str(worktree_root)
            assert env["AUGUR_SYNC_REPO_LOCAL_ONLY"] == "1"
            assert "do_vaults=False" in cmd[2]
            sync_output.parent.mkdir(parents=True, exist_ok=True)
            sync_output.write_text("bootstrapped\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        if cmd[1].endswith("generate-worktree-mcp.py"):
            assert cwd == worktree_root
            assert "--mcp-port" in cmd
            assert cmd[cmd.index("--mcp-port") + 1] == "8099"
            mcp_output.parent.mkdir(parents=True, exist_ok=True)
            mcp_output.write_text('{"mcpServers": {}}\n', encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        raise AssertionError(f"unexpected subprocess command: {cmd}")

    monkeypatch.setattr(worktree_preflight.subprocess, "run", fake_run)

    report = worktree_preflight.build_contract(worktree_root, "worktree", repair=True)

    assert sync_output.exists()
    assert mcp_output.exists()
    assert report["verify_passed"] is True
    assert not any(call[0][1:] == ["-m", "skills.ai.scripts.sync_agents", "sync", "all"] for call in calls)


def test_build_contract_records_incident_when_sync_bootstrap_fails(tmp_path: Path, monkeypatch):
    runtime_dir, _main_repo, worktree_root, _sync_output = _make_worktree_fixture(tmp_path)

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(worktree_preflight, "_repo_local_sync_output_paths", lambda _root: [_sync_output])

    def fake_run(cmd, cwd=None, check=None, capture_output=None, text=None, env=None, **kwargs):
        if len(cmd) >= 2 and cmd[1] == "-c":
            raise subprocess.CalledProcessError(
                2,
                cmd,
                stderr="sync exploded",
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(worktree_preflight.subprocess, "run", fake_run)

    report = worktree_preflight.build_contract(worktree_root, "worktree", repair=True)

    incident = next(
        item
        for item in report["incidents_detected"]
        if item["fingerprint"] == "worktree/bootstrap/missing-sync-outputs"
    )
    assert "sync exploded" in incident["message"]
    assert incident["safe_to_repair"] is False
    assert incident["repaired"] is False


def test_build_contract_skips_sync_bootstrap_for_non_worktree_profile(tmp_path: Path, monkeypatch):
    runtime_dir, _main_repo, worktree_root, _sync_output = _make_worktree_fixture(tmp_path)

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(worktree_preflight, "_repo_local_sync_output_paths", lambda _root: [_sync_output])

    calls: list[list[str]] = []

    def fake_run(cmd, cwd=None, check=None, capture_output=None, text=None, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(worktree_preflight.subprocess, "run", fake_run)

    report = worktree_preflight.build_contract(worktree_root, "shell", repair=True)

    assert not any(cmd[1:] == ["-m", "skills.ai.scripts.sync_agents", "sync", "all"] for cmd in calls)
    assert not any(repair["type"] == "sync" for repair in report["repairs_applied"])


def test_build_contract_treats_missing_shared_venv_test_as_optional(tmp_path: Path, monkeypatch):
    runtime_dir, main_repo, worktree_root, _sync_output = _make_worktree_fixture(tmp_path)
    shutil.rmtree(main_repo / ".venv-test")

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(worktree_preflight, "_repo_local_sync_output_paths", lambda _root: [])
    monkeypatch.setattr(
        worktree_preflight,
        "_ensure_dashboard_dependencies",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(worktree_preflight, "_check_pnpm_alignment", lambda _root: None)

    report = worktree_preflight.build_contract(worktree_root, "shell", repair=True)

    venv_test_check = next(item for item in report["checks"] if item["name"] == ".venv-test")
    assert venv_test_check["ok"] is True
    assert "optional source missing" in venv_test_check["details"]
    assert not any(
        incident["fingerprint"] == "worktree/bootstrap/missing-venv-test" for incident in report["incidents_detected"]
    )


def test_build_contract_checks_main_checkout_branch(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Codex"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "codex@example.com"], check=True)
    (repo / "README.md").write_text("root\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-b", "feature"], check=True)

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)

    report = worktree_preflight.build_contract(repo, "shell", repair=False)

    check = next(item for item in report["checks"] if item["name"] == "main_checkout_branch")
    assert check["ok"] is False
    assert "main checkout is on feature" in check["details"]
    assert report["verify_passed"] is False


def test_build_contract_allows_unborn_main_checkout(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True)

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)

    report = worktree_preflight.build_contract(repo, "shell", repair=False)

    check = next(item for item in report["checks"] if item["name"] == "main_checkout_branch")
    assert check["ok"] is True
    assert "branch=main" in check["details"]


def test_load_worktree_guard_module_uses_current_skill_layout():
    module_name = "platform_admin_worktree_guard"
    sys.modules.pop(module_name, None)

    module, error = worktree_preflight._load_worktree_guard_module()

    assert error is None
    assert module is not None
    assert hasattr(module, "check_main_checkout_branch")


def test_worktree_guard_path_fallback_stays_in_shared_vault(monkeypatch):
    monkeypatch.setattr(worktree_preflight.Path, "exists", lambda _path: False)

    guard_path = worktree_preflight._worktree_guard_path()

    assert guard_path.as_posix().endswith("project-brain/capabilities/skills/platform-admin/scripts/worktree_guard.py")


def test_load_worktree_guard_module_evicts_failed_partial_module(monkeypatch):
    module_name = "platform_admin_worktree_guard"
    sys.modules.pop(module_name, None)

    class FakeLoader:
        def exec_module(self, module):
            raise RuntimeError("boom")

    class FakeSpec:
        loader = FakeLoader()

    fake_module = types.ModuleType(module_name)
    monkeypatch.setattr(
        worktree_preflight.importlib.util,
        "spec_from_file_location",
        lambda *_args, **_kwargs: FakeSpec(),
    )
    monkeypatch.setattr(
        worktree_preflight.importlib.util,
        "module_from_spec",
        lambda _spec: fake_module,
    )

    module, error = worktree_preflight._load_worktree_guard_module()

    assert module is None
    assert error is not None
    assert "boom" in error
    assert module_name not in sys.modules


def test_build_contract_reports_guard_import_failure(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Codex"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "codex@example.com"], check=True)
    (repo / "README.md").write_text("root\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True)

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(
        worktree_preflight,
        "_load_worktree_guard_module",
        lambda: (None, "failed to import guard module /fake/path/worktree_guard.py: boom"),
    )

    report = worktree_preflight.build_contract(repo, "shell", repair=False)

    check = next(item for item in report["checks"] if item["name"] == "main_checkout_branch")
    assert check["ok"] is False
    assert "failed to import guard module" in check["details"]
    assert report["verify_passed"] is False


def test_build_contract_fails_worktree_verify_when_sync_outputs_missing(tmp_path: Path, monkeypatch):
    runtime_dir, _main_repo, worktree_root, sync_output = _make_worktree_fixture(tmp_path)
    missing_dir = worktree_root / ".github" / "instructions"

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(
        worktree_preflight,
        "_repo_local_sync_output_paths",
        lambda _root: [sync_output, missing_dir],
    )

    report = worktree_preflight.build_contract(worktree_root, "worktree", repair=False)

    sync_outputs_check = next(item for item in report["checks"] if item["name"] == "sync_outputs")
    assert sync_outputs_check["ok"] is False
    assert ".codex/prompts/bootstrap.md" in sync_outputs_check["details"]
    assert ".github/instructions" in sync_outputs_check["details"]
    assert report["verify_passed"] is False

    incident = next(
        item
        for item in report["incidents_detected"]
        if item["fingerprint"] == "worktree/bootstrap/missing-sync-outputs"
    )
    assert ".codex/prompts/bootstrap.md" in incident["message"]
    assert ".github/instructions" in incident["message"]
    assert incident["safe_to_repair"] is True
    assert incident["repaired"] is False


def test_build_contract_fails_worktree_verify_when_shared_ruff_is_missing(tmp_path: Path, monkeypatch):
    runtime_dir, main_repo, worktree_root, sync_output = _make_worktree_fixture(tmp_path)
    (main_repo / ".venv" / "bin" / "ruff").unlink()

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(worktree_preflight, "_repo_local_sync_output_paths", lambda _root: [sync_output])
    monkeypatch.setattr(worktree_preflight, "_ensure_symlink", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        worktree_preflight,
        "_ensure_dashboard_dependencies",
        lambda *_args, **_kwargs: True,
    )

    report = worktree_preflight.build_contract(worktree_root, "worktree", repair=False)

    ruff_check = next(item for item in report["checks"] if item["name"] == "ruff")
    assert ruff_check["ok"] is False
    assert ".venv" in ruff_check["details"]
    assert report["verify_passed"] is False


def test_repo_local_sync_output_paths_respects_adapter_enablement(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "repo"
    project_root.mkdir()

    class FakeAdapter:
        def __init__(self, name: str, managed_files: list[str]) -> None:
            self.adapter_name = name
            self._managed_files = managed_files

        def get_managed_files(self) -> list[str]:
            return self._managed_files

    adapters = [
        FakeAdapter("enabled", [".enabled/output.md"]),
        FakeAdapter("disabled", [".disabled/output.md"]),
    ]

    import skills.ai.scripts.sync_agents.engine as engine

    monkeypatch.setattr(engine, "_get_all_adapters", lambda: adapters)
    monkeypatch.setattr(engine, "_load_ide_integrations", lambda _root=None: {"integrations": {}})
    monkeypatch.setattr(engine, "_load_enabled_groups", lambda: None)
    monkeypatch.setattr(
        engine,
        "_is_adapter_active",
        lambda adapter, _config, _groups, selected_clients=None: adapter.adapter_name == "enabled",
    )

    paths = worktree_preflight._repo_local_sync_output_paths(project_root)

    assert paths == [project_root / ".enabled" / "output.md"]


def test_repo_local_sync_output_paths_excludes_optional_cleanup_surfaces(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "repo"
    project_root.mkdir()

    class FakeAdapter:
        adapter_name = "enabled"

        def get_managed_files(self) -> list[str]:
            return [
                ".codex/config.toml",
                ".codex/prompts/",
                ".gemini/memory/",
                ".gemini/topics/",
                ".gemini/workflows/",
                ".opencode/skills/",
            ]

    import skills.ai.scripts.sync_agents.engine as engine

    monkeypatch.setattr(engine, "_get_all_adapters", lambda: [FakeAdapter()])
    monkeypatch.setattr(engine, "_load_ide_integrations", lambda _root=None: {"integrations": {}})
    monkeypatch.setattr(engine, "_load_enabled_groups", lambda: None)
    monkeypatch.setattr(engine, "_is_adapter_active", lambda *_args, **_kwargs: True)

    paths = worktree_preflight._repo_local_sync_output_paths(project_root)

    assert paths == [project_root / ".codex" / "config.toml"]


def test_verify_worktree_sync_outputs_rejects_empty_managed_directory(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "repo"
    empty_dir = project_root / ".github" / "instructions"
    empty_dir.mkdir(parents=True)

    monkeypatch.setattr(
        worktree_preflight,
        "_repo_local_sync_output_paths",
        lambda _root: [empty_dir],
    )

    incidents: list[worktree_preflight.Incident] = []
    ok, details = worktree_preflight._verify_worktree_sync_outputs(
        project_root,
        incidents,
        project_root / "scripts" / "worktree_preflight.py",
    )

    assert ok is False
    assert ".github/instructions" in details
    assert incidents
    assert incidents[0].fingerprint == "worktree/bootstrap/missing-sync-outputs"


def test_check_pnpm_alignment_returns_misaligned_incident(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "wt"
    (project_root / "apps" / "dashboard" / "node_modules" / ".bin").mkdir(parents=True)
    (project_root / "apps" / "dashboard" / "node_modules" / ".bin" / "next").write_text("#!/bin/sh\nexit 0\n")

    import worktree_toolchain  # noqa: E402

    misaligned_incident = worktree_toolchain.Incident(
        fingerprint="worktree/toolchain/pnpm-store-misaligned",
        severity="high",
        message="pnpm store and projects directory live on different filesystem volume.",
        owner_path=str(project_root),
        safe_to_repair=False,
        repaired=False,
    )

    monkeypatch.setattr(worktree_toolchain, "verify_pnpm_alignment", lambda root: misaligned_incident)

    result = worktree_preflight._check_pnpm_alignment(project_root)
    assert result is not None
    assert result.fingerprint == "worktree/toolchain/pnpm-store-misaligned"


def test_check_pnpm_alignment_returns_none_when_aligned(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "wt"
    project_root.mkdir(parents=True)

    import worktree_toolchain  # noqa: E402

    monkeypatch.setattr(worktree_toolchain, "verify_pnpm_alignment", lambda root: None)

    result = worktree_preflight._check_pnpm_alignment(project_root)
    assert result is None


def test_ensure_dashboard_dependencies_uses_materializer(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "wt"
    (project_root / "apps" / "dashboard").mkdir(parents=True)
    # No node_modules — repair path will fire.

    import worktree_toolchain  # noqa: E402

    captured: dict = {}

    def fake_materialize(worktree_root, source_worktree):
        captured["worktree_root"] = worktree_root
        captured["source_worktree"] = source_worktree
        bin_dir = worktree_root / "apps" / "dashboard" / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "next").write_text("#!/bin/sh\nexit 0\n")
        return worktree_toolchain.MaterializeResult(
            method="clone",
            duration_ms=42,
            source_worktree=str(source_worktree) if source_worktree else None,
            clone_primitive="apfs",
            incidents=[],
        )

    monkeypatch.setattr(worktree_toolchain, "materialize_node_modules", fake_materialize)

    incidents: list = []
    repairs: list = []

    result = worktree_preflight._ensure_dashboard_dependencies(
        project_root,
        repairs,
        incidents,
        owner_path=project_root,
        repair=True,
    )

    assert result is True
    assert captured["worktree_root"] == project_root
    assert any(r.type == "cow-clone" for r in repairs)


def test_ensure_dashboard_dependencies_propagates_install_failure(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "wt"
    (project_root / "apps" / "dashboard").mkdir(parents=True)

    import worktree_toolchain  # noqa: E402

    fatal_incident = worktree_toolchain.Incident(
        fingerprint="worktree/toolchain/install-failed",
        severity="high",
        message="pnpm install failed: simulated",
        owner_path=str(project_root / "apps" / "dashboard"),
        safe_to_repair=False,
        repaired=False,
    )

    def failing_materialize(worktree_root, source_worktree):
        return worktree_toolchain.MaterializeResult(
            method="failed",
            duration_ms=10,
            source_worktree=None,
            clone_primitive=None,
            incidents=[fatal_incident],
        )

    monkeypatch.setattr(worktree_toolchain, "materialize_node_modules", failing_materialize)

    incidents: list = []
    repairs: list = []

    result = worktree_preflight._ensure_dashboard_dependencies(
        project_root,
        repairs,
        incidents,
        owner_path=project_root,
        repair=True,
    )

    assert result is False
    assert any(i.fingerprint == "worktree/toolchain/install-failed" for i in incidents)
