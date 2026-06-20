"""Regression tests for dashboard dev-server startup hardening."""

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys

from src.config.paths import get_project_root

START_DEV = get_project_root() / "apps" / "dashboard" / "scripts" / "start-dev.sh"
START_DEV_MJS = get_project_root() / "apps" / "dashboard" / "scripts" / "start-dev.mjs"
BUILD_SH = get_project_root() / "apps" / "dashboard" / "scripts" / "build.sh"
BUILD_MJS = get_project_root() / "apps" / "dashboard" / "scripts" / "build.mjs"
BUILD_LOCK_MJS = get_project_root() / "apps" / "dashboard" / "scripts" / "build-lock.mjs"
BUILD_LOCK_SH = get_project_root() / "apps" / "dashboard" / "scripts" / "build-lock.sh"
REBUILD_PLUGINS = get_project_root() / "apps" / "dashboard" / "scripts" / "rebuild-plugins.ts"
MONITOR_PROCESS = (
    get_project_root() / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "monitor" / "process.py"
)
CLEANUP_PROCESSES = (
    get_project_root() / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "cleanup_processes.py"
)


def _start_dev_text() -> str:
    return START_DEV.read_text(encoding="utf-8")


def _start_dev_mjs_text() -> str:
    return START_DEV_MJS.read_text(encoding="utf-8")


def _build_sh_text() -> str:
    return BUILD_SH.read_text(encoding="utf-8")


def _build_mjs_text() -> str:
    return BUILD_MJS.read_text(encoding="utf-8")


def _copy_build_lock_fixture(tmp_path):
    root = tmp_path / "Augur"
    script_dir = root / "apps" / "dashboard" / "scripts"
    script_dir.mkdir(parents=True)
    shutil.copy2(BUILD_LOCK_MJS, script_dir / "build-lock.mjs")
    (root / "scripts").mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    env = os.environ.copy()
    env["AUGUR_PYTHON"] = sys.executable
    env["AUGUR_RUNTIME"] = str(runtime)
    env["BUILD_LOCK_TIMEOUT_MS"] = "1000"
    return root, script_dir / "build-lock.mjs", runtime, env


def _write_instance_resolver(root, body: str) -> None:
    (root / "scripts" / "dashboard_instance.py").write_text(body, encoding="utf-8")


def _run_build_lock(script_path, env):
    return subprocess.run(
        ["node", str(script_path), "node", "-e", "process.exit(0)"],
        cwd=script_path.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _load_cleanup_processes(monkeypatch):
    monkeypatch.syspath_prepend(str(CLEANUP_PROCESSES.parent))
    spec = importlib.util.spec_from_file_location("cleanup_processes_under_test", CLEANUP_PROCESSES)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_windows_start_dev_runs_next_directly_to_preserve_cli_flags():
    text = _start_dev_mjs_text()

    assert "resolveNextCommand()" in text
    assert '"dev", "--turbopack", "--port", dashboardPort' in text
    assert '"exec", "next", "dev", "--turbopack", "--port", dashboardPort' not in text


def test_windows_start_dev_prefers_explicit_augur_python_override():
    text = _start_dev_mjs_text()

    assert text.index("process.env.AUGUR_PYTHON") < text.index(
        'path.join(projectRoot, ".venv", "Scripts", "python.exe")'
    )


def test_windows_start_dev_generates_block_registry_before_tabs():
    text = _start_dev_mjs_text()

    assert "scripts/dist/generate-block-registry.mjs" in text
    assert text.index("scripts/dist/generate-block-registry.mjs") < text.index("scripts/dist/generate-tab-registry.mjs")


def test_windows_start_dev_uses_next_js_bin_without_shell_warning():
    text = _start_dev_mjs_text()

    assert '"next", "dist", "bin", "next"' in text
    assert "return { command: process.execPath, args: [packageBin], shell: false }" in text
    assert "return { command: localCmd, args: [], shell: true }" not in text


def test_windows_start_dev_exports_instance_metadata_env_vars():
    text = _start_dev_mjs_text()

    assert "applyInstanceEnv(env, preflight)" in text
    assert 'const instanceKind = preflight.instance_kind || (preflight.worktree ? "worktree" : "main")' in text
    assert "const defaults = instanceDefaults(instanceKind)" in text
    assert "env.AUGUR_INSTANCE_ID = instanceId" in text
    assert "env.AUGUR_INSTANCE_KIND = instanceKind" in text
    assert "env.AUGUR_BROWSER_MODE = browserMode" in text
    assert "env.AUGUR_HEAL_POLICY = healPolicy" in text
    assert "env.AUGUR_VISIBILITY_POLICY = visibilityPolicy" in text
    assert "env.NEXT_PUBLIC_AUGUR_INSTANCE_ID = instanceId" in text
    assert "env.NEXT_PUBLIC_AUGUR_INSTANCE_KIND = instanceKind" in text
    assert "env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = visibilityPolicy" in text
    assert '"headless_only"' in text
    assert '"validation_only"' in text
    assert '"disabled"' in text
    assert '"no_visible_mutation"' in text


def test_start_dev_forwards_interactive_flag_to_preflight():
    """ADR-737: AUGUR_INTERACTIVE=1 must propagate as --interactive to the
    preflight CLI so the resolver returns browser_mode=isolated_visible."""
    text = _start_dev_mjs_text()

    assert 'env.AUGUR_INTERACTIVE === "1"' in text
    assert 'preflightArgs.push("--interactive")' in text


def test_start_dev_sh_forwards_interactive_flag_to_preflight():
    """ADR-737: bash variant of the same env var contract."""
    text = START_DEV.read_text(encoding="utf-8")

    assert 'AUGUR_INTERACTIVE:-0' in text
    assert "PREFLIGHT_ARGS+=(--interactive)" in text


def test_posix_active_error_watcher_detaches_from_tty_stdin():
    text = _start_dev_text()

    assert 'python3 "$SCRIPT_DIR/watch_error_streams.py" < /dev/null &' in text


def test_windows_active_error_watcher_detaches_from_stdin():
    text = _start_dev_mjs_text()

    assert "scripts/watch_error_streams.py" in text
    assert 'stdio: ["ignore", "inherit", "inherit"]' in text


def test_windows_start_dev_resolves_dashboard_port_from_instance_kind():
    text = _start_dev_mjs_text()

    assert "export function resolveDashboardPort(preflight)" in text
    assert "const dashboardPort = resolveDashboardPort(preflight)" in text
    assert 'if (instanceKind === "main")' in text
    assert 'return "3000"' in text
    assert 'instanceKind === "worktree" || instanceKind === "isolated"' in text
    assert 'port !== "3000"' in text
    assert "requires an allocated dashboard_port other than 3000" in text
    assert "preflight.worktree ? String(preflight.dashboard_port" not in text
    assert 'const dashboardPort = worktreePort || "3000"' not in text


def test_posix_start_dev_exports_instance_metadata_env_vars():
    text = _start_dev_text()

    assert "AUGUR_INSTANCE_ID" in text
    assert "AUGUR_INSTANCE_KIND" in text
    assert "AUGUR_BROWSER_MODE" in text
    assert "AUGUR_HEAL_POLICY" in text
    assert "AUGUR_VISIBILITY_POLICY" in text
    assert "NEXT_PUBLIC_AUGUR_INSTANCE_ID" in text
    assert "NEXT_PUBLIC_AUGUR_INSTANCE_KIND" in text
    assert "NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY" in text
    assert "headless_only" in text
    assert "validation_only" in text
    assert "disabled" in text
    assert "no_visible_mutation" in text


def test_posix_start_dev_resolves_dashboard_port_from_instance_kind():
    text = _start_dev_text()

    assert "INSTANCE_KIND=" in text
    assert 'if [ "$INSTANCE_KIND" = "main" ]; then' in text
    assert 'DASHBOARD_PORT="3000"' in text
    assert '[ "$INSTANCE_KIND" = "worktree" ] || [ "$INSTANCE_KIND" = "isolated" ]' in text
    assert 'DASHBOARD_PORT="$ALLOCATED_DASHBOARD_PORT"' in text
    assert "requires an allocated dashboard_port other than 3000" in text
    assert 'data.get("worktree")' not in text
    assert 'DASHBOARD_PORT="${WORKTREE_PORT:-3000}"' not in text


def test_posix_start_dev_uses_instance_scoped_worktree_cache_namespace():
    text = _start_dev_text()

    assert "CACHE_INSTANCE_SLUG=" in text
    assert 'dashboard-worktree-$CACHE_INSTANCE_SLUG' in text
    assert 'dashboard-worktree-$WORKTREE_PORT' not in text


def test_resolve_dashboard_port_rejects_isolated_main_port():
    script = f"""
import {{ resolveDashboardPort }} from {START_DEV_MJS.as_uri()!r};

const checks = [
  resolveDashboardPort({{ instance_kind: "main", dashboard_port: 3010 }}) === "3000",
  resolveDashboardPort({{ instance_kind: "worktree", dashboard_port: 3011 }}) === "3011",
  resolveDashboardPort({{ instance_kind: "isolated", dashboard_port: 3012 }}) === "3012",
];

let blocked = false;
try {{
  resolveDashboardPort({{ instance_kind: "isolated", dashboard_port: 3000 }});
}} catch (error) {{
  blocked = String(error.message).includes("other than 3000");
}}

if (!blocked || checks.includes(false)) {{
  process.exit(1);
}}
"""

    subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=START_DEV_MJS.parent,
        check=True,
    )


def test_apply_instance_env_defaults_main_worktree_and_isolated_instances():
    script = f"""
import {{ applyInstanceEnv }} from {START_DEV_MJS.as_uri()!r};

const cases = [
  [
    "main",
    {{ instance_kind: "main" }},
    {{
      AUGUR_INSTANCE_ID: "main",
      AUGUR_INSTANCE_KIND: "main",
      AUGUR_BROWSER_MODE: "visible_allowed",
      AUGUR_HEAL_POLICY: "enabled",
      AUGUR_VISIBILITY_POLICY: "visible_allowed",
    }},
  ],
  [
    "worktree",
    {{ instance_kind: "worktree", instance_id: "worktree:task-2" }},
    {{
      AUGUR_INSTANCE_ID: "worktree:task-2",
      AUGUR_INSTANCE_KIND: "worktree",
      AUGUR_BROWSER_MODE: "headless_only",
      AUGUR_HEAL_POLICY: "validation_only",
      AUGUR_VISIBILITY_POLICY: "no_visible_mutation",
    }},
  ],
  [
    "isolated",
    {{ instance_kind: "isolated", instance_id: "isolated:task-2" }},
    {{
      AUGUR_INSTANCE_ID: "isolated:task-2",
      AUGUR_INSTANCE_KIND: "isolated",
      AUGUR_BROWSER_MODE: "headless_only",
      AUGUR_HEAL_POLICY: "disabled",
      AUGUR_VISIBILITY_POLICY: "no_visible_mutation",
    }},
  ],
];

for (const [name, preflight, expected] of cases) {{
  const env = {{}};
  applyInstanceEnv(env, preflight);
  for (const [key, value] of Object.entries(expected)) {{
    if (env[key] !== value) {{
      console.error(`${{name}} ${{key}} expected ${{value}} but got ${{env[key]}}`);
      process.exit(1);
    }}
  }}
  if (env.NEXT_PUBLIC_AUGUR_INSTANCE_ID !== expected.AUGUR_INSTANCE_ID) {{
    console.error(`${{name}} NEXT_PUBLIC_AUGUR_INSTANCE_ID mismatch`);
    process.exit(1);
  }}
  if (env.NEXT_PUBLIC_AUGUR_INSTANCE_KIND !== expected.AUGUR_INSTANCE_KIND) {{
    console.error(`${{name}} NEXT_PUBLIC_AUGUR_INSTANCE_KIND mismatch`);
    process.exit(1);
  }}
  if (env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY !== expected.AUGUR_VISIBILITY_POLICY) {{
    console.error(`${{name}} NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY mismatch`);
    process.exit(1);
  }}
}}
"""

    subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=START_DEV_MJS.parent,
        check=True,
    )


def test_dashboard_build_scripts_have_windows_node_entrypoints():
    assert BUILD_MJS.exists()
    assert BUILD_LOCK_MJS.exists()


def test_windows_build_entrypoints_include_local_skill_dirs():
    build_text = BUILD_MJS.read_text(encoding="utf-8")
    lock_text = BUILD_LOCK_MJS.read_text(encoding="utf-8")

    assert "AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS" in build_text
    assert '"run", "ensure-generated"' in build_text
    assert build_text.index("stopExistingDashboardProcesses()") < build_text.index("removeBuildArtifacts()")
    assert "$cmd.Contains($dashboard)" not in build_text
    assert "AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS" in lock_text


def test_posix_build_refreshes_generated_artifacts_before_next_build():
    build_text = BUILD_SH.read_text(encoding="utf-8")

    assert "pnpm run ensure-generated" in build_text
    assert build_text.index("pnpm run ensure-generated") < build_text.index("pnpm exec next build")


def test_posix_build_pins_augur_root_to_script_checkout():
    build_text = BUILD_SH.read_text(encoding="utf-8")

    assert 'export AUGUR_ROOT="$PROJECT_ROOT"' in build_text
    assert 'AUGUR_ROOT="${AUGUR_ROOT:-$PROJECT_ROOT}"' not in build_text


def test_windows_build_pins_augur_root_to_script_checkout():
    build_text = BUILD_MJS.read_text(encoding="utf-8")

    assert "AUGUR_ROOT: projectRoot" in build_text
    assert "AUGUR_ROOT: process.env.AUGUR_ROOT || projectRoot" not in build_text


def test_direct_dashboard_rebuild_keeps_local_skill_dirs_enabled():
    text = REBUILD_PLUGINS.read_text(encoding="utf-8")

    assert "AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS" in text
    assert 'process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS || "1"' in text


def test_windows_build_lock_releases_lifecycle_ownership():
    lock_text = BUILD_LOCK_MJS.read_text(encoding="utf-8")

    assert "readLifecycleState(python, instance)" in lock_text
    assert "lifecycleActionFor(lifecycleBeforeGate)" in lock_text
    assert "let buildSucceeded = false" in lock_text
    assert "buildSucceeded = exitCode === 0" in lock_text
    assert "restoreLifecycleState(python, lifecycleBeforeGate, instance, buildSucceeded)" in lock_text
    assert "dashboard_lifecycle.release_build_lock_state(" in lock_text
    assert 'restored["state"] = "crashed"' not in lock_text


def test_posix_build_lock_releases_lifecycle_ownership():
    lock_text = BUILD_LOCK_SH.read_text(encoding="utf-8")

    assert "from __future__ import annotations" in lock_text
    assert lock_text.index("from __future__ import annotations") < lock_text.index("def _preferred_project_python")
    assert "def _ensure_project_python(project_root: Path) -> None:" in lock_text
    assert 'project_root / ".venv" / "bin" / "python3"' in lock_text
    assert "os.execv(str(preferred)" in lock_text
    assert lock_text.index("_ensure_project_python(project_root)") < lock_text.index(
        "from src.config.paths import get_runtime_dir"
    )
    assert "def _lifecycle_action_for(previous_state) -> str:" in lock_text
    assert 'previous_state.get("state") == "healthy"' in lock_text
    assert 'return "rebuild"' in lock_text
    assert "previous_lifecycle_state = dashboard_lifecycle.get_state(instance_id=instance_id)" in lock_text
    assert "lifecycle_action = _lifecycle_action_for(previous_lifecycle_state)" in lock_text
    assert "dashboard_lifecycle.request_action" in lock_text
    assert '"build_lock",\n            lifecycle_action,' in lock_text
    assert "_restore_lifecycle_state(" in lock_text
    assert "exit_code = result.returncode" in lock_text
    assert "succeeded=exit_code == 0" in lock_text
    assert "dashboard_lifecycle.release_build_lock_state(" in lock_text
    assert 'restored["state"] = "crashed"' not in lock_text


def test_build_lock_uses_scoped_instance_lock_and_lifecycle_target():
    text = BUILD_LOCK_MJS.read_text(encoding="utf-8")

    assert "resolveDashboardInstance(python)" in text
    assert "instance.build_lock_dir" in text
    assert '"--instance", instance.instance_id' in text
    assert "dashboard_build.lock" in text


def test_posix_build_lock_uses_scoped_instance_lock_and_lifecycle_target():
    text = BUILD_LOCK_SH.read_text(encoding="utf-8")

    assert "resolve_dashboard_instance(root_dir, runtime_dir=runtime_dir)" in text
    assert "lock_dir = instance.build_lock_dir" in text
    assert "instance_id = instance.instance_id" in text
    assert "instance_id=instance_id" in text
    assert '"project-brain" / "capabilities" / "skills" / "daemon" / "scripts"' in text
    assert '".claude" / "skills" / "daemon" / "scripts"' not in text
    assert "def _is_clearly_main_checkout" in text
    assert "if not _is_clearly_main_checkout(root_dir):" in text
    assert "Refusing to use main dashboard build lock fallback" in text
    assert 'Path(state_dir) / "locks" / "dashboard" / "main"' in text
    assert 'lock_dir = Path(state_dir) / "locks"\n' not in text


def test_posix_build_lock_fallback_is_guarded_by_main_checkout_probe():
    tree = ast.parse(BUILD_LOCK_SH.read_text(encoding="utf-8"))
    guarded = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for child in node.body:
            if not isinstance(child, ast.If):
                continue
            test = child.test
            if (
                isinstance(test, ast.UnaryOp)
                and isinstance(test.op, ast.Not)
                and isinstance(test.operand, ast.Call)
                and isinstance(test.operand.func, ast.Name)
                and test.operand.func.id == "_is_clearly_main_checkout"
            ):
                guarded = True
    assert guarded


def test_build_lock_does_not_fallback_to_main_when_worktree_resolver_fails(tmp_path):
    root, script_path, _runtime, env = _copy_build_lock_fixture(tmp_path)
    (root / ".augur-worktree.yaml").write_text("worktree: true\nname: task-4\n", encoding="utf-8")
    _write_instance_resolver(
        root,
        "import sys\n" "print('resolver exploded', file=sys.stderr)\n" "raise SystemExit(7)\n",
    )

    result = _run_build_lock(script_path, env)

    assert result.returncode != 0
    assert "Unable to resolve dashboard instance" in result.stderr
    assert "Refusing to use main dashboard build lock fallback" in result.stderr
    assert "Build lock acquired" not in result.stdout


def test_build_lock_rejects_worktree_instance_without_lock_dir(tmp_path):
    root, script_path, _runtime, env = _copy_build_lock_fixture(tmp_path)
    (root / ".augur-worktree.yaml").write_text("worktree: true\nname: task-4\n", encoding="utf-8")
    _write_instance_resolver(
        root,
        "import json\n" "print(json.dumps({'instance_id': 'worktree:task-4'}))\n",
    )

    result = _run_build_lock(script_path, env)

    assert result.returncode != 0
    assert "invalid instance metadata" in result.stderr
    assert "Refusing to use main dashboard build lock fallback" in result.stderr
    assert "Build lock acquired" not in result.stdout


def test_build_lock_clears_corrupt_meta_as_stale(tmp_path):
    root, script_path, runtime, env = _copy_build_lock_fixture(tmp_path)
    lock_dir = runtime / "locks" / "dashboard" / "main"
    lock_dir.mkdir(parents=True)
    (lock_dir / "dashboard_build.lock").write_text("", encoding="utf-8")
    (lock_dir / "dashboard_build.lock.meta").write_text("{", encoding="utf-8")
    env["FAKE_BUILD_LOCK_DIR"] = str(lock_dir)
    _write_instance_resolver(
        root,
        "import json\n"
        "import os\n"
        "print(json.dumps({\n"
        "    'instance_id': 'main',\n"
        "    'build_lock_dir': os.environ['FAKE_BUILD_LOCK_DIR'],\n"
        "}))\n",
    )

    result = _run_build_lock(script_path, env)

    assert result.returncode == 0, result.stderr
    assert "Build lock acquired" in result.stdout
    assert not (lock_dir / "dashboard_build.lock").exists()
    assert not (lock_dir / "dashboard_build.lock.meta").exists()


def test_production_monitor_and_cleanup_target_main_lifecycle_instance():
    monitor_text = MONITOR_PROCESS.read_text(encoding="utf-8")
    cleanup_text = CLEANUP_PROCESSES.read_text(encoding="utf-8")

    assert 'dashboard_lifecycle.get_state(instance_id="main")' in monitor_text
    assert 'dashboard_lifecycle.record_healthy_poll(instance_id="main")' in monitor_text
    assert 'dashboard_lifecycle.record_crash("dashboard_monitor", "process gone", instance_id="main")' in monitor_text
    assert 'dashboard_lifecycle.is_crash_loop(instance_id="main")' in monitor_text
    assert '"dashboard_monitor", "restart", "auto-recovery", instance_id="main"' in monitor_text
    assert '"recovery_success"' in monitor_text
    assert '"recovery_failed"' in monitor_text
    assert monitor_text.count('instance_id="main"') >= 10
    assert "instance_id=\"main\"" in cleanup_text


def test_cleanup_processes_checks_scoped_main_build_lock_meta(tmp_path, monkeypatch):
    cleanup = _load_cleanup_processes(monkeypatch)
    runtime = tmp_path / "runtime"
    scoped_meta = runtime / "locks" / "dashboard" / "main" / "dashboard_build.lock.meta"
    scoped_meta.parent.mkdir(parents=True)
    scoped_meta.write_text(json.dumps({"pid": 4242}), encoding="utf-8")
    monkeypatch.setattr(cleanup, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(cleanup, "is_pid_alive", lambda pid: str(pid) == "4242")

    assert cleanup._get_build_lock_holder_pid() == "4242"


def test_cleanup_processes_checks_scoped_main_flock_meta(tmp_path, monkeypatch):
    cleanup = _load_cleanup_processes(monkeypatch)
    runtime = tmp_path / "runtime"
    scoped_meta = runtime / "locks" / "dashboard" / "main" / "dashboard_build.flock.meta"
    scoped_meta.parent.mkdir(parents=True)
    scoped_meta.write_text(json.dumps({"pid": 4243}), encoding="utf-8")
    monkeypatch.setattr(cleanup, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(cleanup, "is_pid_alive", lambda pid: str(pid) == "4243")

    assert cleanup._get_build_lock_holder_pid() == "4243"


def test_cleanup_processes_checks_legacy_node_build_lock_meta(tmp_path, monkeypatch):
    cleanup = _load_cleanup_processes(monkeypatch)
    runtime = tmp_path / "runtime"
    legacy_meta = runtime / "locks" / "dashboard_build.lock.meta"
    legacy_meta.parent.mkdir(parents=True)
    legacy_meta.write_text(json.dumps({"pid": 4244}), encoding="utf-8")
    monkeypatch.setattr(cleanup, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(cleanup, "is_pid_alive", lambda pid: str(pid) == "4244")

    assert cleanup._get_build_lock_holder_pid() == "4244"


def test_cleanup_processes_checks_legacy_flock_build_lock_meta(tmp_path, monkeypatch):
    cleanup = _load_cleanup_processes(monkeypatch)
    runtime = tmp_path / "runtime"
    legacy_meta = runtime / "locks" / "dashboard_build.flock.meta"
    legacy_meta.parent.mkdir(parents=True)
    legacy_meta.write_text(json.dumps({"pid": 4245}), encoding="utf-8")
    monkeypatch.setattr(cleanup, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(cleanup, "is_pid_alive", lambda pid: str(pid) == "4245")

    assert cleanup._get_build_lock_holder_pid() == "4245"


def test_cleanup_processes_uses_windows_tree_kill_for_process_groups():
    cleanup_text = CLEANUP_PROCESSES.read_text(encoding="utf-8")

    assert "def kill_process_tree" in cleanup_text
    assert "def _windows_dashboard_tree_root_pid" in cleanup_text
    assert '["taskkill", "/F", "/T", "/PID", pid]' in cleanup_text
    assert "if IS_WINDOWS:\n        return kill_process_tree(_windows_dashboard_tree_root_pid(pid))" in cleanup_text


def test_cleanup_processes_tree_kills_dashboard_parent_on_windows(monkeypatch):
    cleanup = _load_cleanup_processes(monkeypatch)
    records = {
        "20": {
            "ProcessId": 20,
            "ParentProcessId": 10,
            "Name": "node",
            "CommandLine": "next-server --port 3000",
        },
        "10": {
            "ProcessId": 10,
            "ParentProcessId": 1,
            "Name": "node",
            "CommandLine": "node next" + " dev --turbopack --port 3000",
        },
        "1": {
            "ProcessId": 1,
            "ParentProcessId": 0,
            "Name": "WindowsTerminal",
            "CommandLine": "wt.exe",
        },
    }
    killed: list[str] = []

    def fake_run_command(command, timeout=10):
        command_text = " ".join(str(part) for part in command)
        for pid, record in records.items():
            if f"ProcessId = {pid}" in command_text:
                return json.dumps(record)
        return ""

    def fake_run_resolved(command, **_kwargs):
        killed.append(str(command[-1]))
        return None

    monkeypatch.setattr(cleanup, "IS_WINDOWS", True)
    monkeypatch.setattr(cleanup, "run_command", fake_run_command)
    monkeypatch.setattr(cleanup, "_run_command", fake_run_resolved)
    monkeypatch.setattr(cleanup, "is_pid_alive", lambda pid: str(pid) not in killed)
    monkeypatch.setattr(cleanup.time, "sleep", lambda _seconds: None)

    assert cleanup.kill_process_group("20") is True
    assert killed == ["10"]


def test_windows_build_retries_required_server_files_turbopack_race():
    text = _build_mjs_text()

    assert "required-server-files\\.json" in text


def test_dashboard_build_retries_pages_manifest_turbopack_race():
    assert "server/pages-manifest" in _build_sh_text()
    assert "server[/\\\\]pages-manifest\\.json" in _build_mjs_text()


def test_dashboard_build_retries_turbopack_workstore_prerender_invariant():
    text = _build_sh_text()

    assert "Expected workStore to be initialized" in text
    assert "Export encountered an error on /_global-error/page" in text
    assert "Detected Turbopack prerender invariant" in text


def test_windows_build_retries_turbopack_workstore_prerender_invariant():
    text = _build_mjs_text()

    assert "Expected workStore to be initialized" in text
    assert "Export encountered an error on /_global-error/page" in text
    assert "Detected Turbopack prerender invariant" in text


def test_windows_build_webpack_retry_passes_only_build_args():
    text = _build_mjs_text()

    assert 'runBuild(pnpm, ["--webpack"])' in text
    assert 'runBuild(pnpm, env, ["--webpack"])' not in text


def test_start_dev_clears_unparsable_turbopack_server_chunks():
    text = _start_dev_text()

    assert "MODULE_UNPARSABLE" in text
    assert "Turbopack server cache corrupted" in text


def test_start_dev_uses_worktree_heap_floor_above_next_restart_threshold():
    text = _start_dev_text()

    assert 'WORKTREE_NODE_OLD_SPACE_MB="${AUGUR_WORKTREE_NODE_OLD_SPACE_MB:-16384}"' in text
    assert 'if [ -n "$WORKTREE_PORT" ] && [ "$NODE_OLD_SPACE_MB" -lt "$WORKTREE_NODE_OLD_SPACE_MB" ]; then' in text


def test_build_sh_removes_broken_tsbuildinfo_symlink_before_next_build():
    text = _build_sh_text()

    assert 'TSBUILDINFO_PATH="$DASHBOARD_DIR/tsconfig.tsbuildinfo"' in text
    assert 'if [ -L "$TSBUILDINFO_PATH" ] && [ ! -e "$TSBUILDINFO_PATH" ]; then' in text
    assert 'rm -f "$TSBUILDINFO_PATH"' in text
