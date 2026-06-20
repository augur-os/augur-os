"""Integration-contract tests for ADR-743 job ledger wiring."""
from __future__ import annotations

from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
SKILL_DIR = SCRIPTS_DIR.parent


def _source(name: str) -> str:
    return (SCRIPTS_DIR / name).read_text(encoding="utf-8")


def test_executor_integration_contract(tmp_path: Path, monkeypatch) -> None:
    """The shared ledger contract records one finished loop job."""
    import importlib.util
    import sys

    ledger_dir = SCRIPTS_DIR / "job_ledger"

    def load(module_name: str, file_name: str):
        spec = importlib.util.spec_from_file_location(module_name, ledger_dir / file_name)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    jr = load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    ledger = load("ledger", "ledger.py")
    jobs_ops = load("jobs_ops", "jobs_ops.py")

    with ledger.run(kind="loop", name="routine-vault", timeout_s=600) as job:
        job.phase("dispatch")

    assert jr.current_state(Path(job.job_dir)) == "complete"
    assert any(j["name"] == "routine-vault" for j in jobs_ops.list_jobs())


def test_package_imports_match_executor_import_style() -> None:
    """Executors import job_ledger as a package from the daemon scripts dir."""
    import importlib
    import sys

    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))

    ledger = importlib.import_module("job_ledger.ledger")
    jobs_ops = importlib.import_module("job_ledger.jobs_ops")
    supervisor = importlib.import_module("job_ledger.supervisor")
    retention = importlib.import_module("job_ledger.retention")
    assert callable(ledger.run)
    assert callable(jobs_ops.list_jobs)
    assert callable(supervisor.sweep)
    assert callable(retention.archive)


def test_executor_dispatch_points_are_wrapped_not_infinite_loops() -> None:
    adaptive = _source("adaptive_loop_executor.py")
    schedule = _source("schedule_executor.py")
    continuous = _source("continuous_executor.py")
    healer = _source("ai_self_healer.py")

    assert "with _job_ledger_run(\n                kind=\"loop\"," in adaptive
    assert "with _job_ledger_run(\n                    kind=\"loop\"," in adaptive
    assert "name=\"adaptive-continuous\"" in adaptive
    assert "with _job_ledger_run(\n                    kind=\"schedule\"," in schedule
    assert "with _job_ledger_run(\n                kind=\"continuous\"," in continuous
    assert "with _job_ledger_run(\n        kind=\"heal\"," in healer
    assert "with _job_ledger_run(\n                kind=\"heal\"," in healer


def test_daemon_mcp_and_heartbeat_surfaces_call_job_ledger() -> None:
    daemon_mcp = _source("mcp/__init__.py")
    unified = _source("unified_daemon.py")

    assert "scripts.job_ledger" in daemon_mcp
    assert "job_ledger_mcp.register_tools(mcp, mcp_tool_interceptor, metrics)" in daemon_mcp
    assert "job_ledger_mcp.register_subcommands(subparsers)" in daemon_mcp
    assert "def _job_ledger_sweep()" in unified
    assert "supervisor.sweep(config=cfg)" in unified
    assert "retention.archive(retention_days=cfg.get(\"retention_days\", 30))" in unified


def test_daemon_mcp_registers_job_tools_through_synthetic_plugin_loader() -> None:
    """Dashboard MCP loading removes scripts/ from sys.path; synthetic imports must still work."""
    from src.mcp.augur_shared import plugin_tools

    class FakeMCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, name: str, annotations=None):
            def decorator(func):
                self.names.append(name)
                return func

            return decorator

    class FakeMetrics:
        def track_tool(self, *_args, **_kwargs) -> None:
            return None

    module = plugin_tools._load_bundle_mcp_module(SKILL_DIR)
    fake_mcp = FakeMCP()

    module.register_tools(fake_mcp, lambda func: func, FakeMetrics())

    assert {"jobs-list", "jobs-detail", "jobs-submit", "jobs-cancel", "jobs-replay"} <= set(fake_mcp.names)
