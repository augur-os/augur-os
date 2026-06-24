"""`/a-loops all` reserved-verb + CLI dry-run/fail-fast behavior."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from routine_orchestrator import goal_ops
from routine_orchestrator.loop_name_resolver import resolve_loop_token

# The daemon conftest pre-loads the pip SDK ``mcp`` to prevent the daemon's
# scripts/mcp package from shadowing it.  Load the daemon module under a unique
# name and bind it to the local ``mcp`` variable so all assertions below read
# exactly as the brief specifies.
_REPO = next(
    (p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()),
    Path(__file__).resolve().parents[-1],
)
_MCP_INIT = _REPO / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "mcp" / "__init__.py"


def _load_daemon_mcp():
    module_name = "daemon_mcp_a_loops_all_cli"
    if module_name in sys.modules:
        return sys.modules[module_name]
    scripts = _MCP_INIT.parent.parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(module_name, _MCP_INIT)
    m = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = m
    spec.loader.exec_module(m)
    return m


mcp = _load_daemon_mcp()


def test_all_is_classified_as_a_verb():
    d = resolve_loop_token(
        "all",
        verbs=set(mcp._ROUTINE_VERBS),
        prompt_loops={"dream"},
        orchestrator_loops={"hardening"},
        goals={"harden"},
    )
    assert d.kind == "verb"


def test_all_is_registered_in_routine_verbs():
    assert "all" in mcp._ROUTINE_VERBS


def test_bare_all_token_is_not_rewritten():
    new_argv, msg = mcp._rewrite_loop_argv(["all", "--dry-run"])
    assert msg is None
    assert new_argv == ["all", "--dry-run"]   # verb passes through untouched


def test_aug_a_loops_all_dry_run_prints_plan(monkeypatch, capsys):
    monkeypatch.setattr(
        goal_ops, "op_fanout_plan",
        lambda **k: {"success": True, "loops_with_work": ["testing"], "safe_cap": 6},
    )
    args = SimpleNamespace(routine_verb="all", dry_run=True, cap=6,
                           include="", exclude="", max_iterations=8, loop_cap=6)
    rc = mcp._run_routine_cli(args, [])
    assert rc == 0
    assert "loops_with_work" in capsys.readouterr().out


def test_aug_a_loops_all_without_dry_run_fails_fast(monkeypatch, capsys):
    monkeypatch.setattr(goal_ops, "op_fanout_plan", lambda **k: {"success": True})
    args = SimpleNamespace(routine_verb="all", dry_run=False, cap=6,
                           include="", exclude="", max_iterations=8, loop_cap=6)
    rc = mcp._run_routine_cli(args, [])
    out = capsys.readouterr().out.lower()
    assert rc == 1
    assert "inline" in out and "session" in out


def test_aug_a_loops_all_forwards_scan_timeout(monkeypatch):
    mcp_mod = _load_daemon_mcp()
    from routine_orchestrator import goal_ops
    captured = {}
    def fake_plan(**k):
        captured.update(k); return {"success": True}
    monkeypatch.setattr(goal_ops, "op_fanout_plan", fake_plan)
    args = SimpleNamespace(routine_verb="all", dry_run=True, cap=6, include="",
                           exclude="", max_iterations=8, loop_cap=6, scan_timeout_seconds=2.0)
    rc = mcp_mod._run_routine_cli(args, [])
    assert captured["scan_timeout_seconds"] == 2.0
    assert rc == 0


def test_goal_fanout_plan_verb_returns_plan(monkeypatch, capsys):
    mcp_mod = _load_daemon_mcp()
    from routine_orchestrator import goal_ops
    monkeypatch.setattr(
        goal_ops, "op_fanout_plan",
        lambda **k: {"success": True, "loops_with_work": ["testing"]},
    )
    args = SimpleNamespace(
        routine_verb="goal-fanout-plan",
        scope="orchestrator",
        include="",
        exclude="",
        cap=6,
        scan_timeout_seconds=8.0,
        max_iterations=8,
        loop_cap=6,
    )
    rc = mcp_mod._run_routine_cli(args, [])
    assert rc == 0
    assert "loops_with_work" in capsys.readouterr().out


def test_goal_fanout_report_verb_writes_rollup(monkeypatch, capsys):
    mcp_mod = _load_daemon_mcp()
    from routine_orchestrator import goal_ops
    captured = {}

    def fake_report(**k):
        captured["results"] = k.get("results")
        return {"success": True, "report_md": "/x.md"}

    monkeypatch.setattr(goal_ops, "op_fanout_report", fake_report)
    args = SimpleNamespace(
        routine_verb="goal-fanout-report",
        results_json='[{"loop":"testing","verdict":"converged","branch":"b","residual":0}]',
        stamp="",
        runtime_dir=None,
    )
    rc = mcp_mod._run_routine_cli(args, [])
    assert rc == 0
    assert captured["results"] == [{"loop": "testing", "verdict": "converged", "branch": "b", "residual": 0}]
    assert "report_md" in capsys.readouterr().out


def test_all_verb_plan_carries_iteration_budgets(monkeypatch):
    mcp_mod = _load_daemon_mcp()
    from routine_orchestrator import goal_ops
    captured = {}

    def fake_plan(**k):
        captured.update(k)
        return {"success": True}

    monkeypatch.setattr(goal_ops, "op_fanout_plan", fake_plan)
    args = SimpleNamespace(
        routine_verb="all",
        dry_run=True,
        cap=6,
        include="",
        exclude="",
        max_iterations=3,
        loop_cap=2,
        scan_timeout_seconds=8.0,
    )
    rc = mcp_mod._run_routine_cli(args, [])
    assert rc == 0
    assert captured["max_iterations"] == 3
    assert captured["loop_cap"] == 2
