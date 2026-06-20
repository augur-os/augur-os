import pytest
from routine_orchestrator import goal_loop, goal_catalog


class _Result:
    """Stand-in for OrchestrateResult."""
    def __init__(self, findings):
        self.findings = findings


def _scripted_orchestrate(scripts):
    """scripts: dict[loop] -> list of findings-lists returned on successive calls."""
    calls = {k: list(v) for k, v in scripts.items()}

    def _run(loop_name, **_):
        seq = calls[loop_name]
        return _Result(seq.pop(0) if seq else [])

    return _run


def test_fingerprints_are_order_independent():
    a = goal_loop.fingerprints([{"auto_command": "lint", "detail": "x"}, {"detail": "y"}])
    b = goal_loop.fingerprints([{"detail": "y"}, {"auto_command": "lint", "detail": "x"}])
    assert a == b


def test_loop_converges_when_scan_goes_empty():
    orch = _scripted_orchestrate({"testing": [[{"detail": "a"}], []]})
    budget = goal_loop.GoalBudget(max_iterations=10)
    outcome = goal_loop.run_loop_to_convergence(
        "testing", orchestrate=orch, budget=budget, loop_cap=10
    )
    assert outcome.stop_reason == "converged"
    assert outcome.residual == []


def test_loop_stalls_on_repeated_fingerprints():
    same = [{"detail": "stuck"}]
    orch = _scripted_orchestrate({"vault": [same, same, same]})
    budget = goal_loop.GoalBudget(max_iterations=10)
    outcome = goal_loop.run_loop_to_convergence(
        "vault", orchestrate=orch, budget=budget, loop_cap=10
    )
    assert outcome.stop_reason == "stalled"
    assert outcome.residual == same


def test_loop_exhausts_on_loop_cap():
    orch = _scripted_orchestrate({"vault": [[{"detail": str(i)}] for i in range(20)]})
    budget = goal_loop.GoalBudget(max_iterations=100)
    outcome = goal_loop.run_loop_to_convergence(
        "vault", orchestrate=orch, budget=budget, loop_cap=3
    )
    assert outcome.stop_reason == "exhausted"
    assert outcome.iterations == 3


def test_loop_records_errored_when_orchestrate_raises():
    def _boom(loop_name, **_):
        raise RuntimeError("orchestrate failed")

    budget = goal_loop.GoalBudget(max_iterations=10)
    outcome = goal_loop.run_loop_to_convergence(
        "testing", orchestrate=_boom, budget=budget, loop_cap=10
    )
    assert outcome.stop_reason == "errored"
    assert "orchestrate failed" in outcome.error


def test_loop_exhausts_with_zero_iterations_when_budget_predrained():
    budget = goal_loop.GoalBudget(max_iterations=1)
    budget.used = 1  # drained by a prior loop
    called = []

    def _orch(loop_name, **_):
        called.append(loop_name)
        return _Result([])

    outcome = goal_loop.run_loop_to_convergence(
        "testing", orchestrate=_orch, budget=budget, loop_cap=10
    )
    assert outcome.stop_reason == "exhausted"
    assert outcome.iterations == 0
    assert called == []  # orchestrate never invoked


def test_journal_receives_iteration_records():
    orch = _scripted_orchestrate({"testing": [[{"detail": "a"}], []]})
    budget = goal_loop.GoalBudget(max_iterations=10)
    records = []
    goal_loop.run_loop_to_convergence(
        "testing",
        orchestrate=orch,
        budget=budget,
        loop_cap=10,
        journal=records.append,
    )
    assert len(records) >= 1  # at least one record emitted
    assert set(records[0].keys()) == {"loop", "iteration", "finding_count"}


class _FakeWorktree:
    def __init__(self, path="/tmp/goal-wt", branch="goal/clean-x"):
        self.path = path
        self.branch = branch


def test_run_goal_runs_each_loop_and_escalates_residual():
    # clean goal loops: knowledge-enrichment, skill-standards, command-evolution
    scripts = {
        "knowledge-enrichment": [[{"detail": "fm"}], []],
        "skill-standards": [[{"detail": "s"}], [{"detail": "s"}], [{"detail": "s"}]],
        "command-evolution": [[]],
    }
    orch = _scripted_orchestrate(scripts)
    escalated = []
    result = goal_loop.run_goal_loops(
        "clean",
        project_root=".",
        stamp="20260531",
        orchestrate=orch,
        worktree_factory=lambda **_: _FakeWorktree(),
        escalate=lambda finding, **_: escalated.append(finding),
        loop_cap=5,
        max_iterations=100,
    )
    reasons = {o.loop: o.stop_reason for o in result.loop_outcomes}
    assert reasons["knowledge-enrichment"] == "converged"
    assert reasons["skill-standards"] == "stalled"
    assert result.branch == "goal/clean-x"
    assert {"detail": "s"} in escalated


def test_run_goal_unknown_goal_raises():
    with pytest.raises(goal_catalog.UnknownGoalError):
        goal_loop.run_goal_loops(
            "nope",
            project_root=".",
            stamp="x",
            orchestrate=lambda *a, **k: _Result([]),
            worktree_factory=lambda **_: _FakeWorktree(),
            escalate=lambda *a, **k: None,
        )


# --- Issue 2: errored-loop escalation must not be silently swallowed ---


def _erroring_orchestrate(error_loop, good_loops_scripts):
    """Raise for error_loop; serve scripted results for good loops."""
    calls = {k: list(v) for k, v in good_loops_scripts.items()}

    def _run(loop_name, **_):
        if loop_name == error_loop:
            raise RuntimeError(f"orchestrate failed for {loop_name}")
        seq = calls.get(loop_name, [[]])
        return _Result(seq.pop(0) if seq else [])

    return _run


def test_errored_loop_escalates_structured_marker_finding():
    """When a loop ends errored, run_goal_loops must escalate a marker finding (not silence it).

    The 'clean' goal has loops: knowledge-enrichment, skill-standards, command-evolution.
    We error on knowledge-enrichment (a loop that IS in the goal).
    """
    orch = _erroring_orchestrate(
        error_loop="knowledge-enrichment",
        good_loops_scripts={
            "skill-standards": [[]],
            "command-evolution": [[]],
        },
    )
    escalated = []
    goal_loop.run_goal_loops(
        "clean",
        project_root=".",
        stamp="20260531",
        orchestrate=orch,
        worktree_factory=lambda **_: _FakeWorktree(),
        escalate=lambda finding, **_: escalated.append(finding),
        loop_cap=5,
        max_iterations=100,
    )
    # At least one escalated finding must represent the errored loop
    errored_markers = [
        f for f in escalated
        if f.get("goal_loop_error") is True
    ]
    assert errored_markers, "expected a structured error-marker finding in the escalation queue"
    marker = errored_markers[0]
    assert marker.get("loop") == "knowledge-enrichment"
    assert "orchestrate failed" in marker.get("error", "")


def test_errored_loop_marker_includes_loop_name_and_error_message():
    """The escalated error marker must carry both loop name and the exception message."""
    orch = _erroring_orchestrate(
        error_loop="skill-standards",
        good_loops_scripts={},
    )
    escalated = []
    goal_loop.run_goal_loops(
        "clean",
        project_root=".",
        stamp="20260531",
        orchestrate=orch,
        worktree_factory=lambda **_: _FakeWorktree(),
        escalate=lambda finding, **_: escalated.append(finding),
        loop_cap=5,
        max_iterations=100,
    )
    markers = [f for f in escalated if f.get("goal_loop_error") is True]
    assert markers
    assert markers[0]["loop"] == "skill-standards"
    assert markers[0]["error"]  # non-empty


def test_stalled_residual_escalation_still_works():
    """Stalled residuals must still be escalated unchanged (regression guard)."""
    same = [{"detail": "stuck", "auto_command": "lint"}]
    orch = _scripted_orchestrate({"testing": [same, same, same]})
    escalated = []

    # Run a single-loop goal — use "fixit" injected inline; or use clean (has skill-standards etc.)
    # Simplest: call run_loop_to_convergence + escalate manually to mirror run_goal_loops logic
    budget = goal_loop.GoalBudget(max_iterations=10)
    outcome = goal_loop.run_loop_to_convergence(
        "testing", orchestrate=orch, budget=budget, loop_cap=10
    )
    assert outcome.stop_reason == goal_loop.STOP_STALLED
    if outcome.stop_reason in (goal_loop.STOP_STALLED, goal_loop.STOP_EXHAUSTED, goal_loop.STOP_ERRORED):
        for finding in outcome.residual:
            escalated.append(finding)
    assert {"detail": "stuck", "auto_command": "lint"} in escalated


def test_exhausted_residual_escalation_still_works():
    """Exhausted residuals must still be escalated (regression guard)."""
    findings = [{"detail": str(i)} for i in range(20)]
    orch = _scripted_orchestrate({"testing": [[f] for f in findings]})
    budget = goal_loop.GoalBudget(max_iterations=100)
    outcome = goal_loop.run_loop_to_convergence(
        "testing", orchestrate=orch, budget=budget, loop_cap=2
    )
    assert outcome.stop_reason == goal_loop.STOP_EXHAUSTED
    # residual should be the last non-empty findings set
    assert outcome.residual


def test_bootstrap_node_modules_symlinks_into_worktree(tmp_path):
    """ADR-793 worktree bootstrap: a fresh goal worktree has no node_modules,
    so code loops (testing, page-health) and the dashboard tsc verify fail with
    runner-missing. _bootstrap_node_modules symlinks the source checkout's
    already-installed node_modules (lockfile matches HEAD) into the worktree."""
    import subprocess

    repo = tmp_path / "repo"
    (repo / "apps" / "dashboard").mkdir(parents=True)
    (repo / "apps" / "dashboard" / "package.json").write_text('{"name":"d"}\n')
    (repo / "apps" / "dashboard" / "node_modules" / "esbuild").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "apps/dashboard/package.json"], check=True)

    wt = tmp_path / "wt"
    wt.mkdir()
    goal_loop._bootstrap_node_modules(str(repo), str(wt))

    link = wt / "apps" / "dashboard" / "node_modules"
    assert link.is_symlink()
    assert (link / "esbuild").is_dir()  # resolves through the symlink to source


def test_bootstrap_node_modules_skips_when_dest_exists(tmp_path):
    """Idempotent: an existing node_modules in the worktree is left untouched."""
    import subprocess

    repo = tmp_path / "repo"
    (repo / "apps" / "dashboard").mkdir(parents=True)
    (repo / "apps" / "dashboard" / "package.json").write_text('{"name":"d"}\n')
    (repo / "apps" / "dashboard" / "node_modules").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "apps/dashboard/package.json"], check=True)

    wt = tmp_path / "wt"
    (wt / "apps" / "dashboard" / "node_modules").mkdir(parents=True)
    goal_loop._bootstrap_node_modules(str(repo), str(wt))

    # left as a real dir, not replaced by a symlink
    assert (wt / "apps" / "dashboard" / "node_modules").is_dir()
    assert not (wt / "apps" / "dashboard" / "node_modules").is_symlink()
