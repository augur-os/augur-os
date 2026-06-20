import importlib.util
import json
import sys
from pathlib import Path

from src.lib.dashboard_instance import resolve_dashboard_instance

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_PATH = (
    PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "dashboard_lifecycle.py"
)


def load_lifecycle():
    scripts_dir = str(LIFECYCLE_PATH.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("dashboard_lifecycle_test", LIFECYCLE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_lifecycle_state_is_scoped_by_instance(tmp_path, monkeypatch):
    lifecycle = load_lifecycle()
    runtime = tmp_path / "runtime"
    repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    repo.mkdir()
    worktree.mkdir()
    (worktree / ".augur-worktree.yaml").write_text(
        f"worktree: true\nname: adr-737\nmain_repo: {repo}\ndashboard_port: 3007\nmcp_port: 8087\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lifecycle, "get_runtime_dir", lambda: runtime)

    main = resolve_dashboard_instance(repo, runtime_dir=runtime)
    wt = resolve_dashboard_instance(worktree, runtime_dir=runtime)

    lifecycle.log_event("dashboard_monitor", "recovery_success", "main ok", instance=main)
    lifecycle.record_crash("dashboard_monitor", "worktree broke", instance=wt)

    assert lifecycle.get_state(instance=main)["state"] == "healthy"
    assert lifecycle.get_state(instance=wt)["state"] == "crashed"
    assert (runtime / "daemon" / "dashboard" / "main" / "state.json").exists()
    assert (runtime / "daemon" / "dashboard" / "worktrees" / "adr-737" / "state.json").exists()
    assert not (runtime / "daemon" / "dashboard_state.json").exists()


def test_worktree_get_state_ignores_legacy_main_state(tmp_path, monkeypatch):
    lifecycle = load_lifecycle()
    runtime = tmp_path / "runtime"
    repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    repo.mkdir()
    worktree.mkdir()
    (worktree / ".augur-worktree.yaml").write_text(
        f"worktree: true\nname: adr-737\nmain_repo: {repo}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lifecycle, "get_runtime_dir", lambda: runtime)

    legacy_state = runtime / "daemon" / "dashboard_state.json"
    legacy_state.parent.mkdir(parents=True)
    legacy_state.write_text(
        json.dumps(
            {
                **lifecycle.DEFAULT_STATE,
                "state": "healthy",
                "healthy_since": "2026-05-13T10:00:00",
                "consecutive_healthy_polls": 2,
            }
        ),
        encoding="utf-8",
    )
    wt = resolve_dashboard_instance(worktree, runtime_dir=runtime)

    state = lifecycle.get_state(instance=wt)

    assert state == lifecycle.DEFAULT_STATE
    assert legacy_state.exists()
    assert not (runtime / "daemon" / "dashboard" / "worktrees" / "adr-737" / "state.json").exists()


def test_worktree_get_state_ignores_newer_legacy_main_state(tmp_path, monkeypatch):
    lifecycle = load_lifecycle()
    runtime = tmp_path / "runtime"
    repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    repo.mkdir()
    worktree.mkdir()
    (worktree / ".augur-worktree.yaml").write_text(
        f"worktree: true\nname: adr-737\nmain_repo: {repo}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lifecycle, "get_runtime_dir", lambda: runtime)

    wt = resolve_dashboard_instance(worktree, runtime_dir=runtime)
    scoped_state = runtime / "daemon" / "dashboard" / "worktrees" / "adr-737" / "state.json"
    scoped_state.parent.mkdir(parents=True)
    scoped_state.write_text(
        json.dumps(
            {
                **lifecycle.DEFAULT_STATE,
                "state": "crashed",
                "last_crash_at": "2026-05-13T09:00:00",
            }
        ),
        encoding="utf-8",
    )
    legacy_state = runtime / "daemon" / "dashboard_state.json"
    legacy_state.parent.mkdir(parents=True, exist_ok=True)
    legacy_state.write_text(
        json.dumps(
            {
                **lifecycle.DEFAULT_STATE,
                "state": "healthy",
                "healthy_since": "2026-05-13T10:00:00",
                "consecutive_healthy_polls": 2,
            }
        ),
        encoding="utf-8",
    )

    state = lifecycle.get_state(instance=wt)

    assert state["state"] == "crashed"
    assert legacy_state.exists()
    assert scoped_state.exists()


def test_default_resolution_climbs_from_checkout_subdirectory(tmp_path, monkeypatch):
    lifecycle = load_lifecycle()
    runtime = tmp_path / "runtime"
    repo = tmp_path / "Augur"
    dashboard_dir = repo / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)
    (repo / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    monkeypatch.setattr(lifecycle, "get_runtime_dir", lambda: runtime)
    monkeypatch.chdir(dashboard_dir)

    state = lifecycle.get_state()
    lifecycle._init_state_if_missing()

    assert state == lifecycle.DEFAULT_STATE
    assert (runtime / "daemon" / "dashboard" / "main" / "state.json").exists()
    assert not (runtime / "daemon" / "dashboard_state.json").exists()


def test_default_resolution_from_registered_worktree_subdir_keeps_worktree_state(tmp_path, monkeypatch):
    lifecycle = load_lifecycle()
    runtime = tmp_path / "runtime"
    repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-task-3"
    dashboard_dir = worktree / "apps" / "dashboard"
    repo.mkdir()
    dashboard_dir.mkdir(parents=True)
    (repo / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree / ".augur-worktree.yaml").write_text(
        f"worktree: true\nname: task-3\nmain_repo: {repo.resolve()}\n",
        encoding="utf-8",
    )
    (runtime / "worktree_registry.yaml").parent.mkdir(parents=True)
    (runtime / "worktree_registry.yaml").write_text(
        "\n".join(
            [
                "worktrees:",
                f"  '{worktree.resolve()}':",
                "    name: task-3",
                f"    main_repo: '{repo.resolve()}'",
                "    dashboard_port: 3007",
                "",
            ]
        ),
        encoding="utf-8",
    )
    legacy_state = runtime / "daemon" / "dashboard_state.json"
    legacy_state.parent.mkdir(parents=True)
    legacy_state.write_text(
        json.dumps(
            {
                **lifecycle.DEFAULT_STATE,
                "state": "healthy",
                "healthy_since": "2026-05-13T10:00:00",
                "consecutive_healthy_polls": 2,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(lifecycle, "get_runtime_dir", lambda: runtime)
    monkeypatch.chdir(dashboard_dir)

    lifecycle._init_state_if_missing()
    state = lifecycle.get_state()

    assert state == lifecycle.DEFAULT_STATE
    assert (runtime / "daemon" / "dashboard" / "worktrees" / "task-3" / "state.json").exists()
    assert not (runtime / "daemon" / "dashboard" / "main" / "state.json").exists()
    assert legacy_state.exists()


def test_lifecycle_gate_lock_is_scoped_by_instance(tmp_path, monkeypatch):
    lifecycle = load_lifecycle()
    runtime = tmp_path / "runtime"
    repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    repo.mkdir()
    worktree.mkdir()
    (worktree / ".augur-worktree.yaml").write_text(
        f"worktree: true\nname: adr-737\nmain_repo: {repo}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lifecycle, "get_runtime_dir", lambda: runtime)

    main = resolve_dashboard_instance(repo, runtime_dir=runtime)
    wt = resolve_dashboard_instance(worktree, runtime_dir=runtime)

    assert (
        lifecycle.request_action(
            "build_lock",
            "restart",
            "main restart",
            instance=main,
        )["decision"]
        == "granted"
    )
    assert (
        lifecycle.request_action(
            "build_lock",
            "restart",
            "worktree restart",
            instance=wt,
        )["decision"]
        == "granted"
    )

    assert (runtime / "daemon" / "dashboard" / "main" / "gate.lock").exists()
    assert (runtime / "daemon" / "dashboard" / "worktrees" / "adr-737" / "gate.lock").exists()
    assert not (runtime / "daemon" / "dashboard_gate.lock").exists()


def test_mutating_cli_without_resolvable_instance_fails_closed(tmp_path, monkeypatch, capsys):
    lifecycle = load_lifecycle()
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(lifecycle, "get_runtime_dir", lambda: runtime)
    monkeypatch.chdir(tmp_path)

    exit_code = lifecycle.main(
        [
            "request-action",
            "--actor",
            "build_lock",
            "--action",
            "restart",
            "--reason",
            "test",
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "could not resolve dashboard instance" in captured.out.lower()


def test_state_cli_reads_target_project_root(tmp_path, monkeypatch, capsys):
    lifecycle = load_lifecycle()
    runtime = tmp_path / "runtime"
    repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    repo.mkdir()
    worktree.mkdir()
    (worktree / ".augur-worktree.yaml").write_text(
        f"worktree: true\nname: adr-737\nmain_repo: {repo}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lifecycle, "get_runtime_dir", lambda: runtime)

    lifecycle.log_event("dashboard_monitor", "recovery_success", "worktree ok", project_root=worktree)

    exit_code = lifecycle.main(["state", "--project-root", str(worktree)])

    assert exit_code == 0
    state = json_from_stdout(capsys.readouterr().out)
    assert state["state"] == "healthy"
    assert (runtime / "daemon" / "dashboard" / "worktrees" / "adr-737" / "state.json").exists()


def json_from_stdout(stdout: str) -> dict:
    return json.loads(stdout)
