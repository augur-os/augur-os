from routine_orchestrator import goal_ops


def test_op_worktree_returns_handle(monkeypatch):
    from routine_orchestrator import goal_loop

    class _H:
        path = "/tmp/wt"; branch = "goal/clean-x"
    monkeypatch.setattr(goal_loop, "create_goal_worktree", lambda **k: _H())
    out = goal_ops.op_worktree(goal_id="clean", stamp="x", project_root=".")
    assert out["success"] is True
    assert out["worktree_path"] == "/tmp/wt"
    assert out["branch"] == "goal/clean-x"
    assert out["goal_id"] == "clean"
    assert isinstance(out["loops"], list) and out["loops"]   # ordered loop plan present


def test_op_worktree_unknown_goal_errors():
    out = goal_ops.op_worktree(goal_id="nope", stamp="x", project_root=".")
    assert out["success"] is False
    assert "unknown goal" in out["error"].lower()


def test_op_scan_loop_returns_buckets_and_fingerprint():
    from routine_orchestrator import goal_ops as go
    _findings = [{"auto_command": "auto-skill-md", "detail": "x", "loop": "skill-standards"}]

    class _Mech:
        applied = [{"action": "fixed"}]
        deferred = _findings
        failed = []

    class _Bucket:
        auto_command = "auto-skill-md"
        primary_file = "skills/x"
        findings = _findings

    class _Plan:
        buckets = [_Bucket()]
        design_gate_findings = []

    out = go.op_scan_loop(
        loop="skill-standards", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: _findings,
        _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda b, ac, **k: "FIX PROMPT",
        _subagent_type=lambda ac: "general-purpose",
        _allowed_tools=lambda ac: ["Read", "Edit"],
    )
    assert out["success"] is True
    assert out["mechanical_applied"] == 1
    assert len(out["buckets"]) == 1
    b = out["buckets"][0]
    assert b["prompt"] == "FIX PROMPT"
    assert b["subagent_type"] == "general-purpose"
    assert b["allowed_tools"] == ["Read", "Edit"]
    assert out["residual_fingerprint"]
    assert out["budget_remaining"] == 8


def test_op_scan_loop_clean_loop_has_no_buckets():
    from routine_orchestrator import goal_ops as go

    class _Mech:
        applied = []; deferred = []; failed = []

    class _Plan:
        buckets = []; design_gate_findings = []

    out = go.op_scan_loop(
        loop="testing", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: [], _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda *a, **k: "", _subagent_type=lambda ac: "x", _allowed_tools=lambda ac: [],
    )
    assert out["buckets"] == []
    assert out["residual_fingerprint"] == []
    assert out["converged_candidate"] is True


def test_op_scan_loop_budget_remaining_decrements():
    from routine_orchestrator import goal_ops as go

    class _Mech:
        applied = []; deferred = []; failed = []
    class _Plan:
        buckets = []; design_gate_findings = []
    out = go.op_scan_loop(
        loop="x", worktree_path="/tmp/wt", budget_used=3, max_iterations=8,
        _scan=lambda loop, **k: [], _mechanical=lambda f, **k: _Mech(), _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda *a, **k: "", _subagent_type=lambda ac: "x", _allowed_tools=lambda ac: [],
    )
    assert out["budget_remaining"] == 5


def test_op_scan_loop_mechanical_failed_count():
    """mechanical_failed count reflects the failed list from the mechanical phase."""
    from routine_orchestrator import goal_ops as go

    class _Mech:
        applied = []
        deferred = []
        failed = [{"action": "fix-a", "error": "timeout"}, {"action": "fix-b", "error": "clash"}]

    class _Plan:
        buckets = []
        design_gate_findings = []

    out = go.op_scan_loop(
        loop="skill-standards", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: [],
        _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda *a, **k: "",
        _subagent_type=lambda ac: "x",
        _allowed_tools=lambda ac: [],
    )
    assert out["mechanical_failed"] == 2
    assert out["converged_candidate"] is True


def test_op_scan_loop_returns_verify_command_key():
    """op_scan_loop always returns 'verify_command' for shape stability. When the
    injected resolver yields '' (no project verify available), the key is '' —
    the honest empty fallback (kept meaningful by injecting the empty resolver).
    Uses a code loop so the resolver is actually consulted."""
    from routine_orchestrator import goal_ops as go

    class _Mech:
        applied = []; deferred = []; failed = []

    class _Plan:
        buckets = []; design_gate_findings = []

    out = go.op_scan_loop(
        loop="code-quality", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: [],
        _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda *a, **k: "",
        _subagent_type=lambda ac: "x",
        _allowed_tools=lambda ac: [],
        _verify_cmd=lambda root: "",
    )
    assert "verify_command" in out
    assert out["verify_command"] == ""


def test_op_scan_loop_sources_verify_command_from_resolver():
    """op_scan_loop returns the verify command produced by the injected resolver,
    proving the gate is sourced (not hardcoded '') FOR A CODE LOOP. The real
    default resolver reads the project's adaptive_loops.yaml engine.verify_command."""
    from routine_orchestrator import goal_ops as go

    class _Mech:
        applied = []; deferred = []; failed = []

    class _Plan:
        buckets = []; design_gate_findings = []

    out = go.op_scan_loop(
        loop="code-quality", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: [],
        _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda *a, **k: "",
        _subagent_type=lambda ac: "x",
        _allowed_tools=lambda ac: [],
        _verify_cmd=lambda root: "VERIFY CMD",
    )
    assert out["verify_command"] == "VERIFY CMD"


def test_op_scan_loop_verify_command_empty_resolver_is_honest():
    """When the resolver returns '' (no project verify command available),
    op_scan_loop returns verify_command '' — the honest empty fallback so the
    record-bucket op marks the checkpoint unverified rather than faking a pass.
    Uses a code loop so the resolver is actually consulted."""
    from routine_orchestrator import goal_ops as go

    class _Mech:
        applied = []; deferred = []; failed = []

    class _Plan:
        buckets = []; design_gate_findings = []

    out = go.op_scan_loop(
        loop="code-quality", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: [],
        _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda *a, **k: "",
        _subagent_type=lambda ac: "x",
        _allowed_tools=lambda ac: [],
        _verify_cmd=lambda root: "",
    )
    assert out["verify_command"] == ""


def test_op_scan_loop_sources_verify_only_for_code_loops():
    """Fix 1: the project verify command is sourced ONLY for code loops. A code
    loop (code-quality) returns the injected verify command; a hygiene loop
    (skill-standards) returns '' with the SAME injected resolver — the dashboard
    type-check is irrelevant/wasteful for non-code hygiene fixes."""
    from routine_orchestrator import goal_ops as go

    class _Mech:
        applied = []; deferred = []; failed = []

    class _Plan:
        buckets = []; design_gate_findings = []

    def _run(loop):
        return go.op_scan_loop(
            loop=loop, worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
            _scan=lambda loop, **k: [],
            _mechanical=lambda f, **k: _Mech(),
            _plan=lambda f, **k: _Plan(),
            _build_prompt=lambda *a, **k: "",
            _subagent_type=lambda ac: "x",
            _allowed_tools=lambda ac: [],
            _verify_cmd=lambda root: "VCMD",
        )

    # code loop => sourced
    assert _run("code-quality")["verify_command"] == "VCMD"
    # hygiene loop => NOT sourced (honest unverified), same resolver
    assert _run("skill-standards")["verify_command"] == ""


def test_op_scan_loop_drops_out_of_worktree_findings(tmp_path):
    """ADR-793 isolation: findings outside the goal worktree (vault/documents)
    must NOT reach the mutating mechanical phase or get bucketed — they would
    relocate/modify user data outside the isolated checkout. They are surfaced
    via out_of_worktree (count + sample), not silently dropped."""
    from routine_orchestrator import goal_ops as go

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("x = 1\n")
    in_scope = {"auto_command": "auto-coverage-check", "file": "src/x.py", "loop": "code-quality"}
    # auto-security-audit records its target under 'path' (absolute, outside wt).
    audit_abs = {"auto_command": "auto-security-audit", "path": "/private/var/Au-vault/skills/a", "loop": "hardening"}
    # auto-vault-hygiene binary eviction: vault-relative 'file'.
    vault_rel = {"auto_command": "auto-vault-hygiene", "file": "voice-memos/a.m4a", "loop": "hardening"}
    # auto-vault-hygiene brain file: a BARE name whose parent is the wt root.
    brain_file = {"auto_command": "auto-vault-hygiene", "file": "BRAIN.yaml", "loop": "hardening"}
    scanned = [in_scope, audit_abs, vault_rel, brain_file]

    seen: dict = {}

    def _mech_spy(findings, **_k):
        seen["findings"] = list(findings)

        class _M:
            applied = []; deferred = []; failed = []
        return _M()

    class _Plan:
        buckets = []; design_gate_findings = []

    out = go.op_scan_loop(
        loop="code-quality", worktree_path=str(tmp_path), budget_used=0, max_iterations=4,
        _scan=lambda loop, **k: scanned,
        _mechanical=_mech_spy,
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda *a, **k: "",
        _subagent_type=lambda ac: "x",
        _allowed_tools=lambda ac: [],
        _verify_cmd=lambda root: "",
    )

    # The mutating mechanical phase only ever saw the in-worktree finding;
    # the absolute-'path' audit finding, the vault-relative file, and the bare
    # brain-root file are all filtered out.
    assert seen["findings"] == [in_scope]
    assert out["out_of_worktree"] == 3
    joined = " ".join(out["out_of_worktree_sample"])
    assert "Au-vault" in joined and "voice-memos" in joined and "BRAIN.yaml" in joined


def test_verify_code_loops_set_membership():
    """Fix 1: the code-loop allowlist is the loops whose changes a TS/build check
    meaningfully validates."""
    from routine_orchestrator import goal_ops as go

    assert "code-quality" in go._VERIFY_CODE_LOOPS
    assert "testing" in go._VERIFY_CODE_LOOPS
    assert "ui-quality" in go._VERIFY_CODE_LOOPS
    assert "page-health" in go._VERIFY_CODE_LOOPS
    # hygiene loops are NOT code loops
    assert "skill-standards" not in go._VERIFY_CODE_LOOPS


def test_op_scan_loop_design_gate_findings_in_residual():
    """design_gate_findings are included in residual_fingerprint and block convergence."""
    from routine_orchestrator import goal_ops as go

    _dg_findings = [
        {"auto_command": "auto-skill-md", "detail": "needs design review", "loop": "skill-standards"},
    ]

    class _Mech:
        applied = []
        deferred = []
        failed = []

    class _Plan:
        buckets = []
        design_gate_findings = _dg_findings

    out = go.op_scan_loop(
        loop="skill-standards", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: [],
        _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda *a, **k: "",
        _subagent_type=lambda ac: "x",
        _allowed_tools=lambda ac: [],
    )
    assert out["residual_fingerprint"]  # non-empty
    assert out["converged_candidate"] is False


def test_op_record_bucket_commits_when_verify_passes():
    from routine_orchestrator import goal_ops as go
    calls = {}
    out = go.op_record_bucket(
        worktree_path="/tmp/wt", loop="skill-standards", auto_command="auto-skill-md",
        verify_command="echo ok",
        _verify=lambda cmd, cwd: True,
        _commit=lambda cwd, msg: calls.setdefault("sha", "abc123") or "abc123",
    )
    assert out["success"] is True
    assert out["verify_passed"] is True
    assert out["verified"] is True
    assert out["committed"] is True
    assert out["commit"] == "abc123"
    assert "unverified" not in out


def test_op_record_bucket_no_commit_when_verify_fails():
    from routine_orchestrator import goal_ops as go
    committed = {"called": False}
    def _commit(cwd, msg):
        committed["called"] = True
        return "SHOULD-NOT-HAPPEN"
    out = go.op_record_bucket(
        worktree_path="/tmp/wt", loop="x", auto_command="y", verify_command="false",
        _verify=lambda cmd, cwd: False, _commit=_commit,
    )
    assert out["success"] is True
    assert out["verify_passed"] is False
    assert out["verified"] is False
    assert out["committed"] is False
    assert out["commit"] is None
    assert committed["called"] is False   # commit never attempted on red


def test_op_record_bucket_empty_verify_is_honest():
    """Empty verify command => NOT reported as verified; still commits for progress."""
    from routine_orchestrator import goal_ops as go
    commit_msgs = []
    out = go.op_record_bucket(
        worktree_path="/tmp/wt", loop="x", auto_command="y", verify_command="",
        _verify=None,  # _verify must NOT be called for empty cmd path
        _commit=lambda cwd, msg: commit_msgs.append(msg) or "sha1",
    )
    # empty/no verify command => HONEST: not verified, but still committed
    assert out["verify_passed"] is False
    assert out["verified"] is False
    assert out["unverified"] is True
    assert out["committed"] is True
    assert out["commit"] == "sha1"
    # commit message must flag it as unverified
    assert commit_msgs and "UNVERIFIED" in commit_msgs[0]


def test_op_record_bucket_none_verify_command_is_honest():
    """None verify_command behaves identically to empty string — honest, unverified."""
    from routine_orchestrator import goal_ops as go
    out = go.op_record_bucket(
        worktree_path="/tmp/wt", loop="x", auto_command="y", verify_command=None,
        _verify=None,
        _commit=lambda cwd, msg: "sha2",
    )
    assert out["verify_passed"] is False
    assert out["verified"] is False
    assert out["unverified"] is True
    assert out["committed"] is True


def _init_git_repo(repo):
    import subprocess
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    return subprocess


def test_op_record_bucket_ignored_only_reports_applied_not_idle(tmp_path):
    """Issue #4: a fix that only touches gitignored/generated files cannot commit
    (git add -A stages nothing) but the work IS real. op_record_bucket must report
    applied-but-uncommittable, NOT idle (committed:False indistinguishable from a
    no-op). Integration: real git repo, real _commit, real change detection."""
    from routine_orchestrator import goal_ops as go
    repo = tmp_path / "wt"
    sp = _init_git_repo(repo)
    (repo / ".gitignore").write_text("generated/\n")
    sp.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    sp.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    # the fix regenerated an ignored (generated) projection file
    gen = repo / "generated"
    gen.mkdir()
    (gen / "projection.json").write_text("{}")

    out = go.op_record_bucket(
        worktree_path=str(repo), loop="knowledge-enrichment",
        auto_command="auto-regen", verify_command="",
    )
    assert out["success"] is True
    assert out["committed"] is False
    assert out["commit"] is None
    assert out["applied"] is True
    assert out["uncommittable_reason"] == "only gitignored/generated changes"
    # HARD: nothing was force-added — the ignored file must remain untracked.
    status = sp.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True, text=True,
    )
    assert "projection.json" not in status.stdout  # not staged/tracked


def test_op_record_bucket_truly_idle_reports_not_applied(tmp_path):
    """A pristine worktree with no changes at all => applied:False (honest idle),
    distinct from the ignored-only case."""
    from routine_orchestrator import goal_ops as go
    repo = tmp_path / "wt"
    sp = _init_git_repo(repo)
    (repo / "f.txt").write_text("x")
    sp.run(["git", "-C", str(repo), "add", "-A"], check=True)
    sp.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)

    out = go.op_record_bucket(
        worktree_path=str(repo), loop="x", auto_command="y", verify_command="",
    )
    assert out["committed"] is False
    assert out["commit"] is None
    assert out["applied"] is False
    assert "uncommittable_reason" not in out


def test_op_record_bucket_tracked_changes_still_commit(tmp_path):
    """Backward-compat: real tracked changes commit normally and report applied."""
    from routine_orchestrator import goal_ops as go
    repo = tmp_path / "wt"
    sp = _init_git_repo(repo)
    (repo / "f.txt").write_text("x")
    sp.run(["git", "-C", str(repo), "add", "-A"], check=True)
    sp.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    (repo / "f.txt").write_text("changed")

    out = go.op_record_bucket(
        worktree_path=str(repo), loop="x", auto_command="y", verify_command="",
    )
    assert out["committed"] is True
    assert out["commit"]
    assert out["applied"] is True
    assert "uncommittable_reason" not in out


def test_op_record_bucket_ignored_only_via_injected_seams():
    """Verified path: verify passes but git produces no commit (only ignored files
    changed). Detection seam classifies it ignored_only -> applied, uncommittable.
    Uses the injection seams so it is deterministic without a real repo."""
    from routine_orchestrator import goal_ops as go
    out = go.op_record_bucket(
        worktree_path="/tmp/wt", loop="knowledge-enrichment", auto_command="auto-regen",
        verify_command="echo ok",
        _verify=lambda cmd, cwd: True,
        _commit=lambda cwd, msg: None,        # git add -A staged nothing -> no commit
        _changes=lambda cwd: "ignored_only",
    )
    assert out["verify_passed"] is True
    assert out["verified"] is True
    assert out["committed"] is False
    assert out["commit"] is None
    assert out["applied"] is True
    assert out["uncommittable_reason"] == "only gitignored/generated changes"


def test_op_record_bucket_no_change_via_injected_seams():
    """Verified path, commit produced nothing, detection says 'none' => idle."""
    from routine_orchestrator import goal_ops as go
    out = go.op_record_bucket(
        worktree_path="/tmp/wt", loop="x", auto_command="y", verify_command="echo ok",
        _verify=lambda cmd, cwd: True,
        _commit=lambda cwd, msg: None,
        _changes=lambda cwd: "none",
    )
    assert out["committed"] is False
    assert out["applied"] is False
    assert "uncommittable_reason" not in out


def test_real_detect_changes_classifies_worktree(tmp_path):
    """_real_detect_changes distinguishes tracked / ignored_only / none."""
    from routine_orchestrator import goal_ops as go
    repo = tmp_path / "wt"
    sp = _init_git_repo(repo)
    (repo / ".gitignore").write_text("generated/\n")
    sp.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    sp.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    assert go._real_detect_changes(repo) == "none"
    gen = repo / "generated"
    gen.mkdir()
    (gen / "p.json").write_text("{}")
    assert go._real_detect_changes(repo) == "ignored_only"
    (repo / "tracked.txt").write_text("hi")  # an untracked, NON-ignored file
    assert go._real_detect_changes(repo) == "tracked"


def test_op_loop_status_verdicts():
    from routine_orchestrator import goal_ops as go
    # converged: empty current residual
    assert go.op_loop_status(prev_fingerprint=["a"], current_fingerprint=[],
                             iterations=2, loop_cap=6, budget_remaining=4)["verdict"] == "converged"
    # stalled: identical non-empty fingerprints
    assert go.op_loop_status(prev_fingerprint=["a"], current_fingerprint=["a"],
                             iterations=2, loop_cap=6, budget_remaining=4)["verdict"] == "stalled"
    # exhausted: cap hit, still residual
    assert go.op_loop_status(prev_fingerprint=["a"], current_fingerprint=["b"],
                             iterations=6, loop_cap=6, budget_remaining=4)["verdict"] == "exhausted"
    # exhausted: budget hit, still residual
    assert go.op_loop_status(prev_fingerprint=["a"], current_fingerprint=["b"],
                             iterations=2, loop_cap=6, budget_remaining=0)["verdict"] == "exhausted"
    # continue: progress made, budget left
    assert go.op_loop_status(prev_fingerprint=["a"], current_fingerprint=["b"],
                             iterations=2, loop_cap=6, budget_remaining=4)["verdict"] == "continue"


def test_op_loop_status_reports_evidence():
    from routine_orchestrator import goal_ops as go
    out = go.op_loop_status(prev_fingerprint=[], current_fingerprint=["a", "b"],
                           iterations=3, loop_cap=6, budget_remaining=2)
    assert out["success"] is True
    assert out["iterations"] == 3 and out["loop_cap"] == 6
    assert out["budget_remaining"] == 2
    assert out["residual_count"] == 2


def test_op_escalate_enqueues(monkeypatch):
    from routine_orchestrator import goal_ops as go, escalation_queue
    seen = []
    monkeypatch.setattr(escalation_queue, "enqueue", lambda f, **k: seen.append(f) or {"id": "1"})
    out = go.op_escalate(findings=[{"detail": "d", "loop": "x"}], runtime_dir="/tmp/rt")
    assert out["success"] is True
    assert out["escalated"] == 1
    assert seen and seen[0]["detail"] == "d"


def test_op_escalate_empty_is_noop(monkeypatch):
    from routine_orchestrator import goal_ops as go, escalation_queue
    monkeypatch.setattr(escalation_queue, "enqueue", lambda f, **k: (_ for _ in ()).throw(AssertionError("should not enqueue")))
    out = go.op_escalate(findings=[], runtime_dir="/tmp/rt")
    assert out["success"] is True and out["escalated"] == 0


def test_op_drain_backlog_returns_pending(monkeypatch):
    from routine_orchestrator import goal_ops as go, escalation_queue
    monkeypatch.setattr(escalation_queue, "dequeue",
                        lambda **k: [{"id": "entry-1", "finding": {"detail": "old", "loop": "skill-standards"}}])
    out = go.op_drain_backlog(loops=["skill-standards"], runtime_dir="/tmp/rt")
    assert out["success"] is True
    assert out["pending_count"] == 1
    assert out["findings"][0]["detail"] == "old"
    assert out["entries"][0]["id"] == "entry-1"
    assert out["entries"][0]["finding"]["detail"] == "old"


def test_op_drain_backlog_filters_to_goal_loops(monkeypatch):
    from routine_orchestrator import goal_ops as go, escalation_queue
    monkeypatch.setattr(escalation_queue, "dequeue", lambda **k: [
        {"id": "entry-keep", "finding": {"detail": "keep", "loop": "skill-standards"}},
        {"id": "entry-drop", "finding": {"detail": "drop", "loop": "some-other-loop"}},
    ])
    out = go.op_drain_backlog(loops=["skill-standards"], runtime_dir="/tmp/rt")
    details = [f["detail"] for f in out["findings"]]
    assert "keep" in details and "drop" not in details
    assert len(out["entries"]) == 1
    assert out["entries"][0]["id"] == "entry-keep"


def test_op_drain_backlog_empty_loops_returns_all(monkeypatch):
    from routine_orchestrator import goal_ops as go, escalation_queue
    monkeypatch.setattr(escalation_queue, "dequeue", lambda **k: [
        {"id": "e1", "finding": {"detail": "a", "loop": "x"}},
        {"id": "e2", "finding": {"detail": "b", "loop": "y"}},
    ])
    out = go.op_drain_backlog(loops=[], runtime_dir="/tmp/rt")
    assert out["pending_count"] == 2   # empty loopset => no filter (drain everything)
    assert len(out["entries"]) == 2


def test_op_drain_backlog_partitions_dead_path_entries(monkeypatch, tmp_path):
    """Fix 2: a backlog entry whose finding.path is a non-existent ABSOLUTE path
    (e.g. inside a removed worktree) lands in `stale` with its id — NOT in
    `findings` — so the client can consume it. An entry with an existing path or
    no path stays actionable."""
    from routine_orchestrator import goal_ops as go, escalation_queue

    dead = "/Users/nobody/.worktrees/gone/skills/x/SKILL.md"
    alive = tmp_path / "real.md"
    alive.write_text("ok")

    monkeypatch.setattr(escalation_queue, "dequeue", lambda **k: [
        {"id": "dead-1", "finding": {"detail": "stale", "loop": "skill-standards", "path": dead}},
        {"id": "alive-1", "finding": {"detail": "live", "loop": "skill-standards", "path": str(alive)}},
        {"id": "nopath-1", "finding": {"detail": "nopath", "loop": "skill-standards"}},
    ])
    out = go.op_drain_backlog(loops=["skill-standards"], runtime_dir="/tmp/rt")

    # Actionable findings exclude the dead-path entry.
    actionable_details = [f["detail"] for f in out["findings"]]
    assert "live" in actionable_details
    assert "nopath" in actionable_details
    assert "stale" not in actionable_details
    assert out["pending_count"] == 2  # actionable count only

    # Stale list surfaces the dead-path entry with its id and a reason.
    assert out["stale_count"] == 1
    assert len(out["stale"]) == 1
    stale = out["stale"][0]
    assert stale["id"] == "dead-1"
    assert stale["finding"]["detail"] == "stale"
    assert dead in stale["reason"]
    assert stale["reason"].startswith("dead-path:")

    # total_drained covers everything in scope.
    assert out["total_drained"] == 3
    # Actionable entries exclude the stale one.
    assert {e["id"] for e in out["entries"]} == {"alive-1", "nopath-1"}


def test_op_drain_backlog_relative_path_is_actionable(monkeypatch):
    """Fix 2: a RELATIVE path (even if it does not exist) is NOT treated as a
    dead-path — only absolute non-existent paths are stale."""
    from routine_orchestrator import goal_ops as go, escalation_queue

    monkeypatch.setattr(escalation_queue, "dequeue", lambda **k: [
        {"id": "rel-1", "finding": {"detail": "rel", "loop": "x", "path": "skills/x/SKILL.md"}},
    ])
    out = go.op_drain_backlog(loops=[], runtime_dir="/tmp/rt")
    assert [f["detail"] for f in out["findings"]] == ["rel"]
    assert out["stale_count"] == 0
    assert out["stale"] == []


def test_op_drain_backlog_no_path_stays_actionable(monkeypatch):
    """Existing drain entries (no `path`) remain actionable and never land in stale."""
    from routine_orchestrator import goal_ops as go, escalation_queue
    monkeypatch.setattr(escalation_queue, "dequeue",
                        lambda **k: [{"id": "entry-1", "finding": {"detail": "old", "loop": "skill-standards"}}])
    out = go.op_drain_backlog(loops=["skill-standards"], runtime_dir="/tmp/rt")
    assert out["pending_count"] == 1
    assert out["findings"][0]["detail"] == "old"
    assert out["stale"] == []
    assert out["stale_count"] == 0


def test_op_consume_finding_removes_entry(monkeypatch):
    from routine_orchestrator import goal_ops as go, escalation_queue
    seen = {}
    monkeypatch.setattr(
        escalation_queue,
        "complete",
        lambda entry_id, **k: seen.update({"entry_id": entry_id, "kwargs": k}) or True,
    )
    out = go.op_consume_finding(entry_id="abc", runtime_dir="/tmp/rt")
    assert out["success"] is True
    assert out["entry_id"] == "abc"
    assert out["removed"] is True
    assert seen["entry_id"] == "abc"
    assert seen["kwargs"].get("runtime_dir") == "/tmp/rt"


def test_op_consume_finding_not_found(monkeypatch):
    from routine_orchestrator import goal_ops as go, escalation_queue
    monkeypatch.setattr(
        escalation_queue,
        "complete",
        lambda entry_id, **k: False,
    )
    out = go.op_consume_finding(entry_id="missing", runtime_dir="/tmp/rt")
    assert out["success"] is True
    assert out["entry_id"] == "missing"
    assert out["removed"] is False


# ---------------------------------------------------------------------------
# Part A: op_scan_loop partitions maintenance findings out of buckets
# ---------------------------------------------------------------------------


def test_op_scan_loop_partitions_maintenance_from_buckets():
    """A bucket whose findings are kind=='maintenance' lands under 'maintenance',
    a semantic bucket lands under 'buckets'; residual_fingerprint covers BOTH."""
    from routine_orchestrator import goal_ops as go

    _maint_findings = [
        {"auto_command": "ln", "kind": "maintenance", "detail": "rebuild",
         "loop": "knowledge-enrichment"},
    ]
    _sem_findings = [
        {"auto_command": "auto-skill-md", "detail": "semantic",
         "loop": "knowledge-enrichment"},
    ]

    class _MaintBucket:
        auto_command = "ln"
        primary_file = "rag/manifest.yaml"
        findings = _maint_findings

    class _SemBucket:
        auto_command = "auto-skill-md"
        primary_file = "skills/x"
        findings = _sem_findings

    class _Mech:
        applied = []
        deferred = _maint_findings + _sem_findings
        failed = []

    class _Plan:
        buckets = [_MaintBucket(), _SemBucket()]
        design_gate_findings = []

    out = go.op_scan_loop(
        loop="knowledge-enrichment", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: _maint_findings + _sem_findings,
        _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda b, ac, **k: "SEMANTIC PROMPT",
        _subagent_type=lambda ac: "general-purpose",
        _allowed_tools=lambda ac: ["Read", "Edit"],
    )
    assert out["success"] is True
    # Semantic bucket only in buckets.
    assert len(out["buckets"]) == 1
    assert out["buckets"][0]["auto_command"] == "auto-skill-md"
    assert out["buckets"][0]["prompt"] == "SEMANTIC PROMPT"
    # Maintenance bucket partitioned out.
    assert len(out["maintenance"]) == 1
    m = out["maintenance"][0]
    assert m["auto_command"] == "ln"
    assert m["primary_file"] == "rag/manifest.yaml"
    assert m["finding_count"] == 1
    assert m["findings"] == _maint_findings  # raw findings for op_run_maintenance
    # Maintenance items carry no LLM dispatch fields.
    assert "prompt" not in m
    assert "subagent_type" not in m
    # Residual covers BOTH semantic and maintenance findings.
    assert out["residual_fingerprint"]
    fp = set(out["residual_fingerprint"])
    sem_fp = set("|".join(x) for x in go.goal_loop.fingerprints(_sem_findings))
    maint_fp = set("|".join(x) for x in go.goal_loop.fingerprints(_maint_findings))
    assert sem_fp <= fp
    assert maint_fp <= fp
    # Any remaining work (semantic OR maintenance) => not converged.
    assert out["converged_candidate"] is False


def test_op_scan_loop_mixed_kind_bucket_routes_to_maintenance():
    """A bucket with ANY maintenance finding routes the WHOLE bucket to maintenance."""
    from routine_orchestrator import goal_ops as go

    _mixed = [
        {"auto_command": "ln", "kind": "maintenance", "detail": "a", "loop": "l"},
        {"auto_command": "ln", "detail": "b", "loop": "l"},
    ]

    class _Bucket:
        auto_command = "ln"
        primary_file = "f"
        findings = _mixed

    class _Mech:
        applied = []; deferred = _mixed; failed = []

    class _Plan:
        buckets = [_Bucket()]; design_gate_findings = []

    out = go.op_scan_loop(
        loop="l", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: _mixed,
        _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda *a, **k: "P", _subagent_type=lambda ac: "x", _allowed_tools=lambda ac: [],
    )
    assert out["buckets"] == []
    assert len(out["maintenance"]) == 1
    assert out["maintenance"][0]["finding_count"] == 2


def test_op_scan_loop_no_maintenance_key_always_present():
    """maintenance key is always present (empty) for shape stability."""
    from routine_orchestrator import goal_ops as go

    class _Mech:
        applied = []; deferred = []; failed = []

    class _Plan:
        buckets = []; design_gate_findings = []

    out = go.op_scan_loop(
        loop="x", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: [], _mechanical=lambda f, **k: _Mech(), _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda *a, **k: "", _subagent_type=lambda ac: "x", _allowed_tools=lambda ac: [],
    )
    assert out["maintenance"] == []
    assert out["buckets"] == []


# ---------------------------------------------------------------------------
# Part A (broadened): generated_artifact findings route to deterministic
# maintenance, the same as kind=="maintenance".
# ---------------------------------------------------------------------------


def test_is_deterministic_finding_predicate():
    """The partition predicate routes maintenance + generated_artifact findings
    deterministically; everything else stays semantic."""
    from routine_orchestrator import goal_ops as go

    # maintenance kind => deterministic
    assert go._is_deterministic_finding({"kind": "maintenance"}) is True
    # generated_artifact root cause => deterministic (even when kind is actionable)
    assert go._is_deterministic_finding(
        {"kind": "actionable", "root_cause_type": "generated_artifact"}
    ) is True
    # neither => semantic (not deterministic)
    assert go._is_deterministic_finding(
        {"kind": "actionable", "root_cause_type": "logic_error"}
    ) is False
    # non-dict guards
    assert go._is_deterministic_finding("not a dict") is False  # type: ignore[arg-type]


def test_op_scan_loop_generated_artifact_routes_to_maintenance():
    """A bucket whose finding has root_cause_type=='generated_artifact'
    (kind != maintenance) routes to 'maintenance', NOT 'buckets' — its fix is
    to RUN A GENERATOR (deterministic), handled by op_run_maintenance."""
    from routine_orchestrator import goal_ops as go

    _gen_findings = [
        {"auto_command": "auto-test-webmcp", "kind": "actionable",
         "root_cause_type": "generated_artifact",
         "detail": "Block registry not generated", "loop": "testing"},
    ]
    _sem_findings = [
        {"auto_command": "auto-skill-md", "kind": "actionable",
         "detail": "semantic", "loop": "testing"},
    ]

    class _GenBucket:
        auto_command = "auto-test-webmcp"
        primary_file = "apps/dashboard/block-registry.ts"
        findings = _gen_findings

    class _SemBucket:
        auto_command = "auto-skill-md"
        primary_file = "skills/x"
        findings = _sem_findings

    class _Mech:
        applied = []
        deferred = _gen_findings + _sem_findings
        failed = []

    class _Plan:
        buckets = [_GenBucket(), _SemBucket()]
        design_gate_findings = []

    out = go.op_scan_loop(
        loop="testing", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: _gen_findings + _sem_findings,
        _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda b, ac, **k: "SEMANTIC PROMPT",
        _subagent_type=lambda ac: "general-purpose",
        _allowed_tools=lambda ac: ["Read", "Edit"],
    )
    assert out["success"] is True
    # generated_artifact bucket partitioned into maintenance.
    assert len(out["maintenance"]) == 1
    m = out["maintenance"][0]
    assert m["auto_command"] == "auto-test-webmcp"
    assert m["findings"] == _gen_findings  # raw findings for op_run_maintenance
    assert "prompt" not in m
    assert "subagent_type" not in m
    # Only the semantic bucket remains in buckets.
    assert len(out["buckets"]) == 1
    assert out["buckets"][0]["auto_command"] == "auto-skill-md"
    assert out["buckets"][0]["prompt"] == "SEMANTIC PROMPT"


def test_op_scan_loop_normal_semantic_finding_stays_in_buckets():
    """A normal semantic finding (actionable, no generated_artifact) stays in
    'buckets' for an LLM fix subagent — NOT routed to maintenance."""
    from routine_orchestrator import goal_ops as go

    _sem_findings = [
        {"auto_command": "auto-skill-md", "kind": "actionable",
         "root_cause_type": "logic_error", "detail": "semantic", "loop": "testing"},
    ]

    class _SemBucket:
        auto_command = "auto-skill-md"
        primary_file = "skills/x"
        findings = _sem_findings

    class _Mech:
        applied = []; deferred = _sem_findings; failed = []

    class _Plan:
        buckets = [_SemBucket()]; design_gate_findings = []

    out = go.op_scan_loop(
        loop="testing", worktree_path="/tmp/wt", budget_used=0, max_iterations=8,
        _scan=lambda loop, **k: _sem_findings,
        _mechanical=lambda f, **k: _Mech(),
        _plan=lambda f, **k: _Plan(),
        _build_prompt=lambda b, ac, **k: "SEMANTIC PROMPT",
        _subagent_type=lambda ac: "general-purpose",
        _allowed_tools=lambda ac: ["Read", "Edit"],
    )
    assert out["maintenance"] == []
    assert len(out["buckets"]) == 1
    assert out["buckets"][0]["auto_command"] == "auto-skill-md"
    assert out["buckets"][0]["prompt"] == "SEMANTIC PROMPT"


# ---------------------------------------------------------------------------
# Part B: op_run_maintenance — deterministic fix() dispatch, no LLM
# ---------------------------------------------------------------------------


def test_op_run_maintenance_invokes_command_fix():
    from routine_orchestrator import goal_ops as go

    calls = {}

    class _FakeFixResult:
        success = True
        changes = ["rag/manifest.yaml"]
        summary = "rebuilt index"

    class _Module:
        @staticmethod
        def fix(ctx, findings):
            calls["ctx"] = ctx
            calls["findings"] = findings
            return _FakeFixResult()

    class _Entry:
        name = "ln"
        module = _Module()

    findings = [{"auto_command": "ln", "kind": "maintenance", "detail": "rebuild"}]
    out = go.op_run_maintenance(
        loop="knowledge-enrichment",
        worktree_path="/tmp/wt",
        auto_command="ln",
        findings=findings,
        _resolve=lambda loop, root: [_Entry()],
    )
    assert out["success"] is True
    assert out["auto_command"] == "ln"
    assert out["applied"] == 1
    assert out["changed_files"] == ["rag/manifest.yaml"]
    assert out["fix_summary"] == "rebuilt index"
    # fix() received our findings and a non-dry-run ctx.
    assert calls["findings"] == findings
    assert calls["ctx"].dry_run is False


def test_op_run_maintenance_fix_failure_reports_honestly():
    """A fix returning success=False must NOT report applied>0 / success True,
    yet still surfaces changed_files / fix_summary (no raise)."""
    from routine_orchestrator import goal_ops as go

    class _FailFixResult:
        success = False
        changes = ["rag/manifest.yaml"]
        summary = "reindex failed: lock held"

    class _Module:
        @staticmethod
        def fix(ctx, findings):
            return _FailFixResult()

    class _Entry:
        name = "ln"
        module = _Module()

    findings = [
        {"auto_command": "ln", "kind": "maintenance", "detail": "a"},
        {"auto_command": "ln", "kind": "maintenance", "detail": "b"},
    ]
    out = go.op_run_maintenance(
        loop="knowledge-enrichment",
        worktree_path="/tmp/wt",
        auto_command="ln",
        findings=findings,
        _resolve=lambda loop, root: [_Entry()],
    )
    assert out["success"] is False
    assert out["applied"] == 0  # fix failed → nothing claimed handled
    assert out["auto_command"] == "ln"
    assert out["changed_files"] == ["rag/manifest.yaml"]  # real effect signal preserved
    assert out["fix_summary"] == "reindex failed: lock held"


def test_op_run_maintenance_unknown_command():
    from routine_orchestrator import goal_ops as go

    class _Entry:
        name = "other"
        module = object()

    out = go.op_run_maintenance(
        loop="l", worktree_path="/tmp/wt", auto_command="ln", findings=[{}],
        _resolve=lambda loop, root: [_Entry()],
    )
    assert out["success"] is False
    assert "ln" in out["error"]
    assert out["applied"] == 0


def test_op_run_maintenance_no_fix_callable():
    from routine_orchestrator import goal_ops as go

    class _ModuleNoFix:
        pass

    class _Entry:
        name = "ln"
        module = _ModuleNoFix()

    out = go.op_run_maintenance(
        loop="l", worktree_path="/tmp/wt", auto_command="ln", findings=[{}],
        _resolve=lambda loop, root: [_Entry()],
    )
    assert out["success"] is False
    assert "ln" in out["error"]
    assert out["applied"] == 0


def test_op_run_maintenance_fix_raises_is_captured():
    from routine_orchestrator import goal_ops as go

    class _Module:
        @staticmethod
        def fix(ctx, findings):
            raise RuntimeError("indexer blew up")

    class _Entry:
        name = "ln"
        module = _Module()

    out = go.op_run_maintenance(
        loop="l", worktree_path="/tmp/wt", auto_command="ln", findings=[{}],
        _resolve=lambda loop, root: [_Entry()],
    )
    assert out["success"] is False
    assert "indexer blew up" in out["error"]
    assert out["applied"] == 0


def test_op_run_maintenance_uses_injected_ctx_builder():
    from routine_orchestrator import goal_ops as go

    seen = {}

    class _FakeFixResult:
        success = True
        changes = []
        summary = "ok"

    class _Module:
        @staticmethod
        def fix(ctx, findings):
            seen["ctx"] = ctx
            return _FakeFixResult()

    class _Entry:
        name = "ln"
        module = _Module()

    sentinel_ctx = object()
    out = go.op_run_maintenance(
        loop="l", worktree_path="/tmp/wt", auto_command="ln", findings=[{}],
        _resolve=lambda loop, root: [_Entry()],
        _ctx=lambda worktree_path: sentinel_ctx,
    )
    assert out["success"] is True
    assert seen["ctx"] is sentinel_ctx


def test_op_fanout_plan_triages_only_loops_with_findings():
    from routine_orchestrator import goal_ops as go
    scans = {"testing": [{"x": 1}, {"x": 2}], "code-quality": [], "hardening": [{"x": 1}]}
    out = go.op_fanout_plan(
        cap=6,
        project_root=".",
        _scan=lambda loop, **k: scans[loop],
        _orchestrator_loops=lambda: ["testing", "code-quality", "hardening"],
        _headroom=lambda: 8,
    )
    assert out["success"] is True
    assert out["loops_with_work"] == ["hardening", "testing"]   # sorted, >0 only
    assert out["skipped_clean"] == ["code-quality"]
    assert out["per_loop_counts"] == {"testing": 2, "code-quality": 0, "hardening": 1}
    assert out["safe_cap"] == 6
    assert out["worktree_headroom"] == 8
    assert out["partial"] is False
    assert out["timed_out"] == []
    assert out["crashed"] == []
    # iteration budgets echo through to callers
    assert out["max_iterations"] == 8
    assert out["loop_cap"] == 6


def test_op_fanout_plan_echoes_explicit_iteration_budgets():
    from routine_orchestrator import goal_ops as go
    out = go.op_fanout_plan(
        cap=4, project_root=".",
        max_iterations=12, loop_cap=3,
        _scan=lambda loop, **k: [{"x": 1}],
        _orchestrator_loops=lambda: ["testing"],
        _headroom=lambda: 9,
    )
    assert out["max_iterations"] == 12
    assert out["loop_cap"] == 3


def test_op_fanout_plan_safe_cap_zero_when_registry_full():
    from routine_orchestrator import goal_ops as go
    out = go.op_fanout_plan(
        cap=6, project_root=".",
        _scan=lambda loop, **k: [{"x": 1}],
        _orchestrator_loops=lambda: ["testing"],
        _headroom=lambda: 0,
    )
    assert out["safe_cap"] == 0


def test_op_fanout_plan_clamps_cap_to_headroom():
    from routine_orchestrator import goal_ops as go
    out = go.op_fanout_plan(
        cap=6, project_root=".",
        _scan=lambda loop, **k: [{"x": 1}],
        _orchestrator_loops=lambda: ["a", "b"],
        _headroom=lambda: 2,
    )
    assert out["safe_cap"] == 2          # min(6, 2)


def test_op_fanout_plan_honors_include_and_exclude():
    from routine_orchestrator import goal_ops as go
    base = lambda: ["testing", "code-quality", "hardening"]
    inc = go.op_fanout_plan(
        cap=4, project_root=".", include=["testing"],
        _scan=lambda loop, **k: [{"x": 1}], _orchestrator_loops=base, _headroom=lambda: 9,
    )
    assert set(inc["per_loop_counts"]) == {"testing"}
    assert inc["loops_with_work"] == ["testing"]
    exc = go.op_fanout_plan(
        cap=4, project_root=".", exclude=["testing", "hardening"],
        _scan=lambda loop, **k: [{"x": 1}], _orchestrator_loops=base, _headroom=lambda: 9,
    )
    assert set(exc["per_loop_counts"]) == {"code-quality"}
    assert "testing" not in exc["loops_with_work"]
    assert "hardening" not in exc["loops_with_work"]


def test_default_orchestrator_loops_excludes_prompt_and_driver():
    from routine_orchestrator import goal_ops as go
    loops = go._default_orchestrator_loops()
    assert "goal-loop" not in loops           # catalog driver excluded
    assert "dream" not in loops               # inline-session prompt excluded
    assert "inbox-triage" not in loops        # inline-session prompt excluded
    assert "hardening" in loops and "testing" in loops


def test_op_fanout_report_is_honest_about_unfinished(tmp_path):
    from routine_orchestrator import goal_ops as go
    results = [
        {"loop": "testing", "verdict": "converged", "branch": "goal/testing-x", "residual": 0},
        {"loop": "hardening", "verdict": "stalled", "branch": "goal/hardening-x", "residual": 3},
    ]
    out = go.op_fanout_report(results=results, runtime_dir=str(tmp_path), stamp="t1")
    assert out["success"] is True
    assert out["all_clean"] is False          # a loop stalled
    assert out["converged"] == 1 and out["unfinished"] == 1
    assert out["branches"] == ["goal/testing-x", "goal/hardening-x"]
    md = (tmp_path / "a-loops-all" / "rollup-t1.md").read_text(encoding="utf-8")
    assert "stalled" in md and "goal/hardening-x" in md


def test_op_fanout_report_all_clean_only_when_all_converged(tmp_path):
    from routine_orchestrator import goal_ops as go
    results = [{"loop": "testing", "verdict": "converged", "branch": "goal/testing-x", "residual": 0}]
    out = go.op_fanout_report(results=results, runtime_dir=str(tmp_path), stamp="t2")
    assert out["all_clean"] is True


def test_op_fanout_plan_classifies_timed_out_loops_as_partial():
    from routine_orchestrator import goal_ops as go
    def fake_scan(loop, **k):
        if loop == "hardening":
            return [{"goal_suggest_timeout": True, "detail": "scan timed out"}]
        return [{"x": 1}] if loop == "testing" else []
    out = go.op_fanout_plan(
        cap=6, project_root=".",
        _scan=fake_scan,
        _orchestrator_loops=lambda: ["testing", "hardening", "ui-quality"],
        _headroom=lambda: 8,
    )
    assert out["partial"] is True
    assert out["timed_out"] == ["hardening"]
    assert out["crashed"] == []
    assert "hardening" in out["loops_with_work"]   # timed-out → conservatively fanned out
    assert "testing" in out["loops_with_work"]
    assert out["skipped_clean"] == ["ui-quality"]
    assert out["per_loop_counts"]["hardening"] == 0   # marker excluded from real count
    assert out["safe_cap"] == 6


def test_op_fanout_plan_classifies_crashed_loops_as_partial():
    from routine_orchestrator import goal_ops as go
    def fake_scan(loop, **k):
        if loop == "code-quality":
            raise RuntimeError("scanner boom")
        return [{"x": 1}] if loop == "testing" else []
    out = go.op_fanout_plan(
        cap=6, project_root=".", _scan=fake_scan,
        _orchestrator_loops=lambda: ["testing", "code-quality", "ui-quality"],
        _headroom=lambda: 8,
    )
    assert out["partial"] is True
    assert out["crashed"] == ["code-quality"]
    assert out["timed_out"] == []
    assert "code-quality" in out["loops_with_work"]   # crashed → conservatively fanned out
    assert "testing" in out["loops_with_work"]
    assert out["skipped_clean"] == ["ui-quality"]
    assert out["per_loop_counts"]["code-quality"] == 0   # crash marker excluded from real count


def test_op_fanout_plan_normalizes_nonfinite_timeout():
    from routine_orchestrator import goal_ops as go
    out = go.op_fanout_plan(
        cap=4, project_root=".", scan_timeout_seconds=float("nan"),
        _scan=lambda loop, **k: [{"x": 1}],
        _orchestrator_loops=lambda: ["testing"], _headroom=lambda: 9,
    )
    assert out["success"] is True
    assert out["loops_with_work"] == ["testing"]
    assert out["partial"] is False
    assert out["crashed"] == []


def test_assess_degrades_without_sigalrm(monkeypatch):
    import signal as _sig
    from routine_orchestrator import goal_suggest
    monkeypatch.delattr(_sig, "SIGALRM", raising=False)
    out = goal_suggest.assess(
        ["x"], project_root=".",
        scan=lambda loop, **k: [{"a": 1}],
        per_loop_timeout_seconds=5.0,
    )
    assert out["x"] == [{"a": 1}]   # scan ran unbounded, no AttributeError


def test_op_fanout_report_empty_results(tmp_path):
    from routine_orchestrator import goal_ops as go
    out = go.op_fanout_report(results=[], runtime_dir=str(tmp_path), stamp="e")
    assert out["success"] is True
    assert out["all_clean"] is False   # empty run is not clean
    assert out["converged"] == 0
    assert out["unfinished"] == 0
    md = (tmp_path / "a-loops-all" / "rollup-e.md").read_text(encoding="utf-8")
    assert "loops run: 0" in md


# ---------------------------------------------------------------------------
# Issue #2 — route-keyed findings are not filesystem paths and stay in-scope,
# while genuine out-of-repo filesystem paths stay out-of-scope.
# ---------------------------------------------------------------------------


def test_finding_in_worktree_keeps_route_url_findings(tmp_path):
    """page-health / testing scanners emit findings keyed on a ROUTE URL (e.g.
    ``path: "/login"`` or ``path: "/workspace/ai"``). A route URL is NOT a
    filesystem path — Path("/login") is absolute and outside the worktree, but the
    finding is in-scope (a worktree subagent fixes the page that serves the route).
    """
    from routine_orchestrator import goal_ops as go

    for route in ("/login", "/settings/ai", "/workspace/ai", "/browse"):
        finding = {"auto_command": "auto-test-dashboard", "path": route, "loop": "testing"}
        assert go._finding_in_worktree(finding, tmp_path) is True, route


def test_finding_in_worktree_still_drops_vault_and_abs_paths(tmp_path):
    """The route relaxation must NOT weaken the genuine isolation protection:
    bare vault/brain files and absolute paths into real out-of-repo filesystem
    roots (vault, ~/.claude) stay OUT of scope so the mechanical phase never
    mutates user data outside the worktree."""
    from pathlib import Path
    from routine_orchestrator import goal_ops as go

    # Bare vault/brain root files (relative, parent IS the worktree root).
    for name in ("BRAIN.yaml", "IDENTITY.md"):
        assert go._finding_in_worktree({"file": name, "loop": "hardening"}, tmp_path) is False, name

    # Vault-relative binary (relative path under a non-existent worktree subdir).
    assert go._finding_in_worktree({"file": "voice-memos/a.m4a", "loop": "hardening"}, tmp_path) is False

    # Absolute path under a REAL out-of-repo filesystem root (home dir): a real
    # vault file the scanner found. Top-level component exists on disk, so it is a
    # filesystem path (not a route) and must stay dropped.
    abs_vault = str(Path.home() / "Au-vault" / "BRAIN.yaml")
    assert go._finding_in_worktree({"path": abs_vault, "loop": "hardening"}, tmp_path) is False


def test_finding_in_worktree_route_with_real_vault_path_still_dropped(tmp_path):
    """A finding carrying BOTH a route AND a genuine out-of-repo filesystem path is
    still dropped — the real foreign path is the binding constraint."""
    from pathlib import Path
    from routine_orchestrator import goal_ops as go

    finding = {
        "path": "/workspace/ai",                       # route (would be in-scope alone)
        "file": str(Path.home() / "Au-vault" / "x.md"),  # real foreign fs path
        "loop": "testing",
    }
    assert go._finding_in_worktree(finding, tmp_path) is False


# ---------------------------------------------------------------------------
# Issue #1 — op_fanout_plan triage counts only worktree-actionable findings and
# surfaces (does not silently drop) out-of-scope work.
# ---------------------------------------------------------------------------


def test_op_fanout_plan_separates_out_of_scope_from_loops_with_work(tmp_path):
    """Triage must filter each loop's findings through the same worktree-scope
    predicate the fix flow uses. A loop whose findings are ALL out-of-worktree
    lands in out_of_scope (surfaced, not dropped), NOT loops_with_work; a loop with
    in-worktree findings still lands in loops_with_work."""
    from pathlib import Path
    from routine_orchestrator import goal_ops as go

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("x = 1\n")
    in_scope = {"file": "src/x.py", "loop": "code-quality"}
    foreign_a = {"path": str(Path.home() / "Au-vault" / "a.md"), "loop": "hardening"}
    foreign_b = {"file": "BRAIN.yaml", "loop": "hardening"}

    scans = {
        "code-quality": [in_scope],
        "hardening": [foreign_a, foreign_b],   # all out-of-worktree
        "ui-quality": [],                      # genuinely clean
    }
    out = go.op_fanout_plan(
        cap=6, project_root=str(tmp_path),
        _scan=lambda loop, **k: scans[loop],
        _orchestrator_loops=lambda: ["code-quality", "hardening", "ui-quality"],
        _headroom=lambda: 8,
    )
    # in-scope counting only
    assert out["per_loop_counts"] == {"code-quality": 1, "hardening": 0, "ui-quality": 0}
    # the all-foreign loop is NOT actionable by the fan-out
    assert out["loops_with_work"] == ["code-quality"]
    # but its work is surfaced honestly (rule 8), not silently dropped
    assert out["out_of_scope_counts"] == {"hardening": 2}
    assert out["loops_with_out_of_scope_work"] == ["hardening"]
    # a loop with only out-of-scope work is NOT "clean"
    assert out["skipped_clean"] == ["ui-quality"]


def test_op_fanout_plan_keeps_route_findings_in_loops_with_work(tmp_path):
    """A testing/page-health loop emitting route-URL findings must be counted as
    actionable work (the regression that lost 14 testing findings)."""
    from routine_orchestrator import goal_ops as go

    route_findings = [
        {"path": "/login", "loop": "testing"},
        {"path": "/settings/ai", "loop": "testing"},
    ]
    out = go.op_fanout_plan(
        cap=6, project_root=str(tmp_path),
        _scan=lambda loop, **k: route_findings if loop == "testing" else [],
        _orchestrator_loops=lambda: ["testing", "ui-quality"],
        _headroom=lambda: 8,
    )
    assert out["per_loop_counts"]["testing"] == 2
    assert "testing" in out["loops_with_work"]
    assert out.get("out_of_scope_counts", {}).get("testing", 0) == 0
# ISSUE #5: "converged" must not conflate real work with all-out-of-scope no-op
# ---------------------------------------------------------------------------


def test_op_loop_status_no_op_when_zero_commits_and_out_of_scope():
    # Empty fingerprint ONLY because every finding was filtered out_of_worktree
    # and nothing was committed → distinct no_op verdict, NOT converged.
    out = goal_ops.op_loop_status(
        prev_fingerprint=["a"], current_fingerprint=[],
        iterations=1, loop_cap=6, budget_remaining=4,
        committed_count=0, out_of_scope_count=3,
    )
    assert out["verdict"] == "no_op"
    assert out["committed_count"] == 0
    assert out["out_of_scope_count"] == 3
    assert out["did_work"] is False


def test_op_loop_status_converged_when_committed_work():
    # Empty fingerprint AND real verified checkpoints landed → genuinely converged.
    out = goal_ops.op_loop_status(
        prev_fingerprint=["a"], current_fingerprint=[],
        iterations=2, loop_cap=6, budget_remaining=4,
        committed_count=2, out_of_scope_count=0,
    )
    assert out["verdict"] == "converged"
    assert out["did_work"] is True


def test_op_loop_status_converged_when_genuinely_clean():
    # Empty fingerprint, nothing committed, but nothing was ever out of scope
    # (a genuinely clean scan) → converged, not no_op.
    out = goal_ops.op_loop_status(
        prev_fingerprint=[], current_fingerprint=[],
        iterations=1, loop_cap=6, budget_remaining=4,
        committed_count=0, out_of_scope_count=0,
    )
    assert out["verdict"] == "converged"
    assert out["did_work"] is False


def test_op_loop_status_backward_compatible_default():
    # No committed/out_of_scope info supplied → preserve legacy converged verdict.
    out = goal_ops.op_loop_status(
        prev_fingerprint=["a"], current_fingerprint=[],
        iterations=1, loop_cap=6, budget_remaining=4,
    )
    assert out["verdict"] == "converged"
    assert out["committed_count"] is None
    assert out["did_work"] is None   # unknown


def test_op_fanout_report_no_op_is_not_clean(tmp_path):
    from routine_orchestrator import goal_ops as go
    results = [
        {"loop": "testing", "verdict": "converged", "branch": "goal/testing-x",
         "residual": 0, "committed_checkpoints": 3},
        {"loop": "vault", "verdict": "no_op", "branch": "goal/vault-x",
         "residual": 0, "committed_checkpoints": 0, "out_of_scope": 4},
    ]
    out = go.op_fanout_report(results=results, runtime_dir=str(tmp_path), stamp="n1")
    assert out["all_clean"] is False           # a loop merely no-op'd
    assert out["no_op"] == 1
    assert out["did_work"] == 1
    md = (tmp_path / "a-loops-all" / "rollup-n1.md").read_text(encoding="utf-8")
    assert "no_op" in md
    assert "committed" in md.lower() and "did_work" in md.lower()


def test_op_fanout_report_converged_zero_commit_out_of_scope_treated_no_op(tmp_path):
    from routine_orchestrator import goal_ops as go
    # Driver reported "converged" but committed nothing and had out-of-scope debt:
    # defensively reclassify as no-op — must not count as clean.
    results = [
        {"loop": "vault", "verdict": "converged", "branch": "goal/vault-x",
         "residual": 0, "committed_checkpoints": 0, "out_of_scope": 5},
    ]
    out = go.op_fanout_report(results=results, runtime_dir=str(tmp_path), stamp="n2")
    assert out["all_clean"] is False
    assert out["no_op"] == 1


def test_op_fanout_report_genuinely_clean_zero_commit_is_clean(tmp_path):
    from routine_orchestrator import goal_ops as go
    # Converged, 0 commits, but nothing was out of scope → genuinely clean.
    results = [
        {"loop": "testing", "verdict": "converged", "branch": "goal/testing-x",
         "residual": 0, "committed_checkpoints": 0, "out_of_scope": 0},
    ]
    out = go.op_fanout_report(results=results, runtime_dir=str(tmp_path), stamp="n3")
    assert out["all_clean"] is True
    assert out["no_op"] == 0


# ---------------------------------------------------------------------------
# ISSUE #7: silent drivers — reconstruct verdict from worktree ground truth
# ---------------------------------------------------------------------------


def test_op_fanout_report_reconstructs_unreported_via_seam(tmp_path):
    from routine_orchestrator import goal_ops as go

    def fake_inspect(entry, *, stamp):
        return {"exists": True, "branch": "goal/build-x",
                "committed_checkpoints": 2, "dirty": False}

    results = [
        {"loop": "testing", "verdict": "converged", "branch": "goal/testing-x",
         "residual": 0, "committed_checkpoints": 1},
        {"loop": "build", "unreported": True, "branch": "goal/build-x"},
    ]
    out = go.op_fanout_report(results=results, runtime_dir=str(tmp_path),
                              stamp="r1", _inspect=fake_inspect)
    assert out["all_clean"] is False          # an unreported loop existed
    assert out["unreported"] == 1
    row = [r for r in out["results"] if r.get("loop") == "build"][0]
    assert row["verdict"] == "unreported (reconstructed)"
    assert row["committed_checkpoints"] == 2
    md = (tmp_path / "a-loops-all" / "rollup-r1.md").read_text(encoding="utf-8")
    assert "reconstructed" in md


def test_op_fanout_report_reconstructs_none_entry(tmp_path):
    from routine_orchestrator import goal_ops as go

    def fake_inspect(entry, *, stamp):
        return {"exists": True, "branch": "goal/?-x",
                "committed_checkpoints": 0, "dirty": True}

    results = [
        {"loop": "testing", "verdict": "converged", "committed_checkpoints": 1},
        None,   # a driver returned nothing at all
    ]
    out = go.op_fanout_report(results=results, runtime_dir=str(tmp_path),
                              stamp="r2", _inspect=fake_inspect)
    assert out["all_clean"] is False
    assert out["unreported"] == 1


def test_op_fanout_report_reconstruct_missing_worktree_is_unknown(tmp_path):
    from routine_orchestrator import goal_ops as go

    def fake_inspect(entry, *, stamp):
        return {"exists": False}

    results = [{"loop": "build", "unreported": True, "branch": "goal/build-x"}]
    out = go.op_fanout_report(results=results, runtime_dir=str(tmp_path),
                              stamp="r3", _inspect=fake_inspect)
    assert out["all_clean"] is False
    row = out["results"][0]
    assert row["verdict"] == "unknown"


def test_op_fanout_report_reconstruct_inspect_raises_is_unknown(tmp_path):
    from routine_orchestrator import goal_ops as go

    def boom_inspect(entry, *, stamp):
        raise RuntimeError("worktree gone")

    results = [{"loop": "build", "unreported": True}]
    out = go.op_fanout_report(results=results, runtime_dir=str(tmp_path),
                              stamp="r4", _inspect=boom_inspect)
    assert out["all_clean"] is False
    assert out["results"][0]["verdict"] == "unknown"


def test_real_inspect_worktree_counts_checkpoint_commits(tmp_path):
    """Exercise the default git-backed inspector against a real tmp repo."""
    import subprocess
    from routine_orchestrator import goal_ops as go
    repo = tmp_path / "wt"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True,
                       capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (repo / "a.txt").write_text("1", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base commit")
    (repo / "b.txt").write_text("2", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "goal: testing fix via auto-x (verified checkpoint)")

    info = go._real_inspect_worktree({"worktree_path": str(repo)}, stamp="x")
    assert info["exists"] is True
    assert info["committed_checkpoints"] == 1   # one "goal:" checkpoint commit
    assert info["dirty"] is False


# ---------------------------------------------------------------------------
# ADR-818 phase 2 — op_run_inplace surface-tiered guardrails (seam-mocked; no
# live mutation).
# ---------------------------------------------------------------------------


class _FakeOrchestrateResult:
    def __init__(self, applied=0, enqueued=0):
        self.mechanical_applied = [object()] * applied
        self.enqueued = [object()] * enqueued
        self.dispatched = []
        self.deferred = []


def _capture_orchestrate(rec, *, applied=0, enqueued=0):
    def _fake(loop, **kw):
        rec.clear()
        rec["loop"] = loop
        rec.update(kw)
        return _FakeOrchestrateResult(applied=applied, enqueued=enqueued)
    return _fake


def test_op_run_inplace_runtime_auto_applies_without_git_commit():
    """runtime surface auto-applies (difficulty preserved) but installs the
    no-git-commit guardrail (self-heal writes via sanctioned tools)."""
    rec = {}
    out = goal_ops.op_run_inplace(
        loop="self-heal", surface="runtime", difficulty=1,
        _orchestrate=_capture_orchestrate(rec, applied=2),
    )
    assert rec["difficulty"] == 1  # aggressive auto-apply preserved
    assert rec["commit_runner"] is goal_ops._no_repo_commit
    assert out["commit_policy"].startswith("external-tools")
    assert out["mechanical_applied"] == 2 and out["did_work"] is True
    assert out["gated_on"] is None


def test_op_run_inplace_vault_aggressive_then_syncs_under_lock():
    """ADR-816 Alternative 3 (ratified 2026-06-28): vault surface auto-applies
    aggressively (difficulty preserved, NEVER touches the code repo) and, when
    fixes landed, commits+pushes the vault via vault_sync under the lock."""
    rec = {}
    synced = {"n": 0}

    def _fake_sync():
        synced["n"] += 1
        return {"success": True, "committed": 4, "pushed": 4}

    out = goal_ops.op_run_inplace(
        loop="knowledge-enrichment", surface="vault", difficulty=1,
        _orchestrate=_capture_orchestrate(rec, applied=4),
        _vault_sync=_fake_sync,
    )
    assert rec["difficulty"] == 1, "vault now auto-applies aggressively (gate lifted)"
    assert rec["commit_runner"] is goal_ops._no_repo_commit, "code repo must never be committed"
    assert out["gated_on"] is None
    assert synced["n"] == 1, "vault_sync must run after vault fixes are applied"
    assert out["vault_sync"] == {"success": True, "committed": 4, "pushed": 4}


def test_op_run_inplace_vault_skips_sync_when_nothing_applied():
    """No vault fixes applied -> no vault commit/push (don't sync an unchanged vault)."""
    rec = {}
    synced = {"n": 0}
    out = goal_ops.op_run_inplace(
        loop="knowledge-enrichment", surface="vault", difficulty=1,
        _orchestrate=_capture_orchestrate(rec, applied=0, enqueued=3),
        _vault_sync=lambda: synced.__setitem__("n", synced["n"] + 1) or {},
    )
    assert synced["n"] == 0, "must not commit/push when nothing changed"
    assert out["vault_sync"] is None
    assert out["escalated"] == 3


def test_op_run_inplace_repo_uses_engine_default_commit():
    """repo surface keeps the engine default (code-repo) commit policy."""
    rec = {}
    out = goal_ops.op_run_inplace(
        loop="code-quality", surface="repo", difficulty=1,
        _orchestrate=_capture_orchestrate(rec),
    )
    assert rec["commit_runner"] is None  # engine default code-repo commit
    assert out["commit_policy"] == "code-repo commit"
    assert rec["difficulty"] == 1
