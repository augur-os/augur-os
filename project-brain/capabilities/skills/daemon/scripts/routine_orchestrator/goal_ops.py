"""Atomic operations for the inline-session routines goal catalog-loop (ADR-793).

The AI client (not a Python subprocess) drives the convergence loop and is the
Task invoker. These ops expose the ADR-755 spine — worktree, scan+mechanical,
verify+commit, escalate, status — as deterministic, JSON-returning steps the
client calls between spawning its own fix subagents. No LLM calls here.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

try:
    from . import goal_catalog, goal_loop
except ImportError:  # pragma: no cover
    from routine_orchestrator import goal_catalog, goal_loop  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Default helpers — lazily import the real primitives so tests can override.
# ---------------------------------------------------------------------------


# Loops whose changes a project TS/build type-check meaningfully validates. The
# project verify command (cd apps/dashboard && npx tsc --noEmit) is sourced ONLY
# for these — for non-code hygiene loops (skill-standards, vault hygiene, …) the
# dashboard type-check validates nothing the fix touched and a pre-existing TS
# error elsewhere would falsely block a hygiene commit, so we return "" (honest
# unverified) instead. page-health touches dashboard pages, so the check applies.
_VERIFY_CODE_LOOPS = frozenset({"testing", "code-quality", "ui-quality", "page-health"})


def _is_deterministic_finding(finding: dict) -> bool:
    """A finding is deterministically fixable (run via op_run_maintenance, NOT an
    LLM fix subagent) when it is a maintenance action OR a missing/stale generated
    artifact whose fix is to RUN A GENERATOR (e.g. auto-test-webmcp regenerating
    the block registry). Both have an owning command fix(); both belong on the
    deterministic ``maintenance`` path, not in semantic ``buckets``."""
    return (
        isinstance(finding, dict)
        and (
            finding.get("kind") == "maintenance"
            or finding.get("root_cause_type") == "generated_artifact"
        )
    )


# Keys under which loop scanners record the path a finding targets. Different
# scanners use different keys: auto-vault-hygiene/auto-coverage-check use ``file``;
# auto-security-audit uses ``path``; ``primary_file`` is the planner-facing alias.
_FINDING_PATH_KEYS = ("file", "primary_file", "path")


def _finding_display_path(finding: dict) -> str:
    """First path-like value recorded on a finding (for surfacing samples)."""
    if not isinstance(finding, dict):
        return ""
    for k in _FINDING_PATH_KEYS:
        v = finding.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def _finding_in_worktree(finding: dict, root: Path) -> bool:
    """True if the finding targets a path inside the goal worktree.

    A goal worktree isolates work to the code repo. Several loop scanners resolve
    the user's vault/documents (or the main checkout / plugin cache) via path
    helpers and emit findings OUTSIDE the worktree:
      - auto-vault-hygiene: vault-relative ``file`` (``voice-memos/x.m4a``) or a
        bare vault/brain root file (``BRAIN.yaml``, ``IDENTITY.md``);
      - auto-security-audit: an absolute ``path`` into the vault, the main
        checkout, or ~/.claude plugin cache (it never scans the goal worktree).
    Bucketing those for a worktree subagent is pointless, and — worse — letting
    them reach the mutating mechanical-fix phase would relocate/modify USER DATA
    outside the isolated checkout. Findings with no path are kept (treated
    in-scope) so non-file findings still flow normally.
    """
    if not isinstance(finding, dict):
        return True
    root_r = root.resolve()
    paths = [
        finding[k] for k in _FINDING_PATH_KEYS
        if isinstance(finding.get(k), str) and finding[k]
    ]
    if not paths:
        return True
    for fp in paths:
        candidate = Path(fp)
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root_r)
        except (ValueError, OSError):
            return False  # absolute/relative path escapes the worktree
        if resolved.exists():
            continue
        # A not-yet-created file is in-scope only when it lives in an existing
        # SUBdirectory of the worktree (a generated artifact the fix will write).
        # A bare name whose parent IS the worktree root (e.g. vault brain files
        # BRAIN.yaml / IDENTITY.md) is foreign — reject it.
        if resolved.parent.exists() and resolved.parent != root_r:
            continue
        return False
    return True


def _real_scan(loop: str, *, commands: Any = None, **kw: Any) -> list[dict[str, Any]]:
    try:
        from . import scan_phase
    except ImportError:
        from routine_orchestrator import scan_phase  # type: ignore[no-redef]
    return scan_phase.scan_loop(loop, commands=commands, **kw)


def _real_mechanical(findings: list[dict[str, Any]], **kw: Any) -> Any:
    try:
        from . import fix_phase_mechanical
    except ImportError:
        from routine_orchestrator import fix_phase_mechanical  # type: ignore[no-redef]
    return fix_phase_mechanical.apply_mechanical_fixes(findings, **kw)


def _real_plan(findings: list[dict[str, Any]], **kw: Any) -> Any:
    try:
        from . import bucket_planner
    except ImportError:
        from routine_orchestrator import bucket_planner  # type: ignore[no-redef]
    return bucket_planner.plan_dispatch(findings, **kw)


def _real_verify_command(root: Path) -> str:
    """Resolve the project-level verify command the goal gate should run.

    Reuses fix_phase_mechanical._project_verify_command (reads
    config/system/adaptive_loops.yaml -> engine.verify_command) so the goal
    checkpoint verifies against the same project check the orchestrator uses.
    Returns "" when no project verify command is configured — the honest empty
    fallback (op_record_bucket then marks the checkpoint unverified)."""
    try:
        from . import fix_phase_mechanical
    except ImportError:
        from routine_orchestrator import fix_phase_mechanical  # type: ignore[no-redef]
    return fix_phase_mechanical._project_verify_command(root) or ""


def _default_runtime_dir() -> Path:
    """Lazily import get_runtime_dir so unit tests that inject helpers never
    depend on the real src.config.paths resolver being available."""
    from src.config.paths import get_runtime_dir

    return Path(get_runtime_dir())


def op_worktree(*, goal_id: str, stamp: str, project_root: str | Path) -> dict[str, Any]:
    """Resolve the goal and create its isolated worktree off the current branch."""
    try:
        spec = goal_catalog.resolve(goal_id)
    except goal_catalog.UnknownGoalError as exc:
        return {"success": False, "error": str(exc)}
    handle = goal_loop.create_goal_worktree(
        goal_id=goal_id, stamp=stamp, project_root=project_root
    )
    return {
        "success": True,
        "goal_id": goal_id,
        "loops": list(spec.loops),
        "worktree_path": handle.path,
        "branch": handle.branch,
    }


def op_scan_loop(
    *,
    loop: str,
    worktree_path: str,
    budget_used: int,
    max_iterations: int,
    difficulty: int = 0,
    runtime_dir: str | Path | None = None,
    _scan: Callable[..., Any] = _real_scan,
    _mechanical: Callable[..., Any] = _real_mechanical,
    _plan: Callable[..., Any] = _real_plan,
    _build_prompt: Callable[..., str] | None = None,
    _subagent_type: Callable[[Any], str] | None = None,
    _allowed_tools: Callable[[Any], list[str]] | None = None,
    _verify_cmd: Callable[[Path], str] = _real_verify_command,
) -> dict[str, Any]:
    """Scan one loop in the worktree, apply mechanical fixes, return semantic
    buckets (each with a prebuilt subagent prompt), a deterministic
    ``maintenance`` list, residual fingerprint, and remaining whole-run budget.
    The CLIENT spawns subagents for the buckets.

    The ``maintenance`` list covers deterministic findings — both
    kind=="maintenance" (reindex/rebuild) AND root_cause_type=="generated_artifact"
    (run a generator, e.g. regenerate the block registry). Both have an owning
    command fix() and are run via op_run_maintenance (goal-run-maintenance), NOT
    an LLM fix subagent.
    """
    try:
        from . import subagent_dispatch as _sd
        from . import scan_phase as _scan_phase
    except ImportError:
        from routine_orchestrator import subagent_dispatch as _sd  # type: ignore[no-redef]
        from routine_orchestrator import scan_phase as _scan_phase  # type: ignore[no-redef]

    root = Path(worktree_path)

    # Fix 1: trust state_dir lives in the real runtime dir (outside the repo),
    # mirroring orchestrator.py's pattern: runtime / "adaptive".
    runtime = Path(runtime_dir) if runtime_dir is not None else _default_runtime_dir()
    state_dir = runtime / "adaptive"

    # Fix 2: resolve commands ONCE and pass to both scan and mechanical phases.
    resolved_commands = _scan_phase.discover_loop_commands(loop, root)

    # Fix 3: build name→command lookup so the default prompt builder receives
    # the command OBJECT (not the raw name string), matching orchestrator.py.
    # ScanCommand.name is the lookup key (verified from scan_phase.py).
    command_lookup = {
        str(getattr(cmd, "name", "") or ""): cmd for cmd in resolved_commands
    }

    # Resolve default prompt/type/tools builders from real primitives.
    if _build_prompt is None:

        def _build_prompt(b: Any, ac: Any, **_k: Any) -> str:
            try:
                from . import budget as _budget_mod
            except ImportError:
                from routine_orchestrator import budget as _budget_mod  # type: ignore[no-redef]
            bud = _budget_mod.Budget.default(loop, kind="llm", project_root=root)
            return _sd._task_prompt(b, ac, bud, verify_command=None)

    if _subagent_type is None:
        _subagent_type = _sd._subagent_type

    if _allowed_tools is None:
        _allowed_tools = _sd._allowed_tools

    # Scan phase (dry-run, no mutation) — pass resolved commands to avoid a
    # second discovery call inside scan_loop.
    scanned = list(_scan(loop, project_root=root, difficulty=difficulty, commands=resolved_commands))

    # Worktree-scope partition (ADR-793 isolation): drop findings outside the
    # goal worktree BEFORE the mutating mechanical phase, so vault/documents
    # findings (auto-vault-hygiene, auto-security-audit) never mutate user data
    # outside the isolated checkout and never get bucketed for a worktree
    # subagent. Out-of-scope findings are surfaced (count + sample), not dropped:
    # they remain in the escalation queue for a vault-scoped flow to handle.
    findings = [f for f in scanned if _finding_in_worktree(f, root)]
    out_of_scope = [f for f in scanned if not _finding_in_worktree(f, root)]

    # Mechanical fix phase (mutating). Pass the same resolved_commands and the
    # runtime-based state_dir (outside the worktree, never staged by git add -A).
    mech = _mechanical(
        findings,
        commands=resolved_commands,
        project_root=root,
        state_dir=state_dir,
        difficulty=difficulty,
    )

    deferred = list(getattr(mech, "deferred", []) or [])

    # Bucket plan phase — config=None is valid (plan_dispatch accepts Mapping | None).
    plan = _plan(deferred, loop_name=loop, config=None, project_root=root)

    buckets_out: list[dict[str, Any]] = []
    maintenance_out: list[dict[str, Any]] = []
    for b in getattr(plan, "buckets", []) or []:
        # Fix 3: resolve command OBJECT from lookup; fall back to raw name string
        # if not found so the output field stays correct regardless.
        raw_name = b.auto_command
        ac = command_lookup.get(raw_name, raw_name)
        bucket_findings = list(getattr(b, "findings", []) or [])

        # Deterministic partition: a bucket routes to ``maintenance`` if ANY
        # finding is deterministically fixable — either kind=="maintenance"
        # (reindex/rebuild) OR root_cause_type=="generated_artifact" (run a
        # generator). Buckets group by auto_command+file so they are normally
        # homogeneous; ANY-routing is the safe choice. These are deterministic
        # command fix() runs — the CLIENT runs them via op_run_maintenance, NOT
        # an LLM fix subagent. We therefore emit NO prompt/subagent_type/
        # allowed_tools for them.
        if any(_is_deterministic_finding(f) for f in bucket_findings):
            maintenance_out.append(
                {
                    "auto_command": raw_name,
                    "primary_file": getattr(b, "primary_file", None),
                    "finding_count": len(bucket_findings),
                    "findings": bucket_findings,
                }
            )
            continue

        buckets_out.append(
            {
                "auto_command": raw_name,
                "primary_file": getattr(b, "primary_file", None),
                "finding_count": len(bucket_findings),
                "prompt": _build_prompt(b, ac),
                "subagent_type": _subagent_type(ac),
                "allowed_tools": list(_allowed_tools(ac)),
            }
        )

    # Residual fingerprint: all findings still in buckets + design-gated.
    residual: list[dict[str, Any]] = [
        f for b in getattr(plan, "buckets", []) or [] for f in getattr(b, "findings", [])
    ]
    residual += list(getattr(plan, "design_gate_findings", []) or [])
    fp = sorted("|".join(x) for x in goal_loop.fingerprints(residual))

    # verify_command: the project-level check lives in adaptive_loops.yaml
    # engine.verify_command. We source it via _verify_cmd (default
    # _real_verify_command -> fix_phase_mechanical._project_verify_command) so the
    # goal gate actually verifies — but ONLY for code loops (_VERIFY_CODE_LOOPS).
    # For non-code hygiene loops the dashboard type-check validates nothing the fix
    # touched, so we return "" (honest unverified). The client passes this to
    # goal-record-bucket; an empty string means op_record_bucket marks the
    # checkpoint honestly unverified.
    verify_command = _verify_cmd(root) if loop in _VERIFY_CODE_LOOPS else ""
    return {
        "success": True,
        "loop": loop,
        "mechanical_applied": len(getattr(mech, "applied", []) or []),
        "mechanical_failed": len(getattr(mech, "failed", []) or []),
        "buckets": buckets_out,
        "maintenance": maintenance_out,
        "out_of_worktree": len(out_of_scope),
        "out_of_worktree_sample": [
            _finding_display_path(f) for f in out_of_scope[:5] if isinstance(f, dict)
        ],
        "residual_fingerprint": fp,
        "converged_candidate": not residual,
        "budget_remaining": max(0, max_iterations - budget_used),
        "verify_command": verify_command,
    }


def _real_discover_loop_commands(loop: str, root: Path) -> list[Any]:
    """Resolve the loop's auto-commands the same way op_scan_loop does."""
    try:
        from . import scan_phase as _scan_phase
    except ImportError:
        from routine_orchestrator import scan_phase as _scan_phase  # type: ignore[no-redef]
    return _scan_phase.discover_loop_commands(loop, root)


def _real_maintenance_ctx(worktree_path: str) -> Any:
    """Build a non-dry-run OpsContext for the maintenance fix() call, mirroring
    how fix_phase_mechanical constructs its context."""
    from src.lib.ops_protocol import OpsContext

    return OpsContext(project_root=Path(worktree_path), dry_run=False)


def op_run_maintenance(
    *,
    loop: str,
    worktree_path: str,
    auto_command: str,
    findings: list[dict[str, Any]],
    _resolve: Callable[..., Any] | None = None,
    _ctx: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Deterministically apply a maintenance finding by invoking the owning
    command's fix(). No LLM. Builds a minimal OpsContext sufficient for
    maintenance fixes (reindex/rebuild) — not a full mirror of
    fix_phase_mechanical's context (no config/loop_config/session/difficulty).

    Maintenance findings (kind=="maintenance", e.g. reindex/project-index
    rebuilds) are deterministic command actions, NOT semantic work for a fix
    subagent. op_scan_loop partitions them out of ``buckets`` into
    ``maintenance``; the client calls this op for each maintenance item.
    """
    resolve = _resolve if _resolve is not None else _real_discover_loop_commands
    build_ctx = _ctx if _ctx is not None else _real_maintenance_ctx

    root = Path(worktree_path)
    entries = resolve(loop, root)
    lookup = {str(getattr(e, "name", "") or ""): e for e in entries}
    entry = lookup.get(auto_command)
    if entry is None or not callable(getattr(getattr(entry, "module", None), "fix", None)):
        return {
            "success": False,
            "error": f"no fix() for {auto_command}",
            "applied": 0,
        }

    ctx = build_ctx(worktree_path)
    try:
        fix_result = entry.module.fix(ctx, findings)
    except Exception as exc:  # noqa: BLE001 - never raise; report the failure.
        return {"success": False, "error": str(exc), "applied": 0}

    # Extract changed files defensively — FixResult exposes ``changes``.
    changed = (
        getattr(fix_result, "changes", None)
        or getattr(fix_result, "changed_files", None)
        or getattr(fix_result, "changed", None)
        or []
    )
    summary = getattr(fix_result, "summary", None)
    # Honesty: tie success + applied to the fix's own success signal. A fix
    # returning FixResult(success=False) must NOT report applied>0 / success True.
    # Default True only when the attribute is absent (FixResult has .success).
    fix_ok = bool(getattr(fix_result, "success", True))
    return {
        "success": fix_ok,
        "auto_command": auto_command,
        "applied": len(findings) if fix_ok else 0,
        "changed_files": list(changed),
        "fix_summary": summary if summary is not None else str(fix_result),
    }


# ---------------------------------------------------------------------------
# op_record_bucket helpers
# ---------------------------------------------------------------------------


def _real_verify(cmd: str, cwd: Path) -> bool:
    """Verify gate for op_record_bucket.

    Reuses fix_phase_mechanical._default_verify_runner so shell dispatch,
    list-form commands, and callable verify commands all share one code path.
    A minimal OpsContext (project_root only) satisfies the runner's interface.
    """
    if not cmd:
        return True
    try:
        from . import fix_phase_mechanical as _fpm
    except ImportError:
        from routine_orchestrator import fix_phase_mechanical as _fpm  # type: ignore[no-redef]
    from src.lib.ops_protocol import OpsContext

    ctx = OpsContext(project_root=cwd)
    return _fpm._default_verify_runner(
        verify_command=cmd,
        ctx=ctx,
        changed_files=[],
        finding={},
        command_entry=None,
    )


def _real_commit(cwd: Path, msg: str) -> str | None:
    """Stage all changes and commit; return the new HEAD SHA or None on failure."""
    subprocess.run(["git", "-C", str(cwd), "add", "-A"], check=False)  # noqa: S603
    proc = subprocess.run(  # noqa: S603
        ["git", "-C", str(cwd), "commit", "-m", msg],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    rev = subprocess.run(  # noqa: S603
        ["git", "-C", str(cwd), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return rev.stdout.strip() or None


def op_loop_status(
    *,
    prev_fingerprint: list[str],
    current_fingerprint: list[str],
    iterations: int,
    loop_cap: int,
    budget_remaining: int,
) -> dict[str, Any]:
    """Report a stop verdict for the client's loop (converged/stalled/exhausted/
    continue). Mirrors run_loop_to_convergence; reports evidence, does not assert done."""
    if not current_fingerprint:
        verdict = "converged"
    elif iterations >= loop_cap or budget_remaining <= 0:
        verdict = "exhausted"
    elif set(current_fingerprint) == set(prev_fingerprint):
        verdict = "stalled"
    else:
        verdict = "continue"
    return {
        "success": True, "verdict": verdict, "iterations": iterations,
        "loop_cap": loop_cap, "budget_remaining": budget_remaining,
        "residual_count": len(current_fingerprint),
    }


def op_escalate(
    *,
    findings: list[dict[str, Any]],
    runtime_dir: str | None = None,
) -> dict[str, Any]:
    """Enqueue residual findings the loop could not resolve (nothing is lost)."""
    from . import escalation_queue
    n = 0
    for f in findings:
        escalation_queue.enqueue(f, runtime_dir=runtime_dir)
        n += 1
    return {"success": True, "escalated": n}


def op_drain_backlog(
    *,
    loops: list[str],
    runtime_dir: str | None = None,
) -> dict[str, Any]:
    """Dequeue the existing NoSessionAvailable backlog, filtered to this goal's loops,
    so the inline-session prompt processes it BEFORE scanning fresh findings (ADR-792
    motivation).

    NOTE: dequeue REMOVES stale entries but RETAINS fresh ones — the client MUST:
    (1) call op_consume_finding(entry_id) for each finding it RESOLVES, so resolved
        entries are cleared and do not re-surface for 14 days;
    (2) leave unresolved findings in place (they persist) or re-escalate via
        op_escalate if additional context is needed.
    So nothing is lost AND resolved entries get cleared.
    """
    from . import escalation_queue
    entries = escalation_queue.dequeue(runtime_dir=runtime_dir)
    loopset = set(loops)
    items: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    total = 0
    for entry in entries:
        finding = entry.get("finding") if isinstance(entry, dict) else None
        if not (isinstance(finding, dict) and (not loopset or finding.get("loop") in loopset)):
            continue
        total += 1
        record = {"id": entry.get("id"), "finding": finding}
        dead = _dead_path(finding)
        if dead is not None:
            # Dead-path entries point at removed worktrees — unactionable. Surface
            # them (with id) so the client can call goal-consume-finding to clear
            # them. We do NOT auto-consume here (that mutates the shared queue).
            stale.append({**record, "reason": f"dead-path: {dead}"})
        else:
            items.append(record)
    return {
        "success": True,
        "pending_count": len(items),  # ACTIONABLE count
        "findings": [it["finding"] for it in items],  # actionable only; back-compat shape
        "entries": items,  # actionable [{"id": <entry-id>, "finding": {...}}, ...]
        "stale": stale,  # NEW: dead-path entries [{"id", "finding", "reason"}, ...]
        "stale_count": len(stale),
        "total_drained": total,  # actionable + stale in scope
    }


def _dead_path(finding: dict[str, Any]) -> str | None:
    """Return the dead-path string if the finding's `path` is an ABSOLUTE path that
    no longer exists on disk (e.g. inside a removed worktree), else None. A missing
    path, a relative path, or an existing path is actionable (returns None)."""
    p = finding.get("path")
    if not isinstance(p, str) or not p:
        return None
    path = Path(p)
    if path.is_absolute() and not path.exists():
        return p
    return None


def op_consume_finding(
    *,
    entry_id: str,
    runtime_dir: str | None = None,
) -> dict[str, Any]:
    """Remove ONE resolved backlog entry by id so it does not re-surface.

    The inline-session prompt calls this after it successfully resolves a drained
    finding (vs. op_escalate for ones it could not resolve).
    """
    from . import escalation_queue
    removed = escalation_queue.complete(entry_id, runtime_dir=runtime_dir)
    return {"success": True, "entry_id": entry_id, "removed": bool(removed)}


def op_record_bucket(
    *,
    worktree_path: str,
    loop: str,
    auto_command: str,
    verify_command: str | None = None,
    _verify: Callable[[str, Path], bool] | None = None,
    _commit: Callable[[Path, str], str | None] | None = None,
) -> dict[str, Any]:
    """Verify the worktree after a subagent applied a bucket fix; commit if green.

    No trust-ledger write is performed here — trust governs tiered auto-apply
    in the orchestrator's mechanical phase, not the inline goal session loop
    (YAGNI: the goal loop operates at a coarser checkpoint granularity and does
    not require per-command trust accounting at this stage).
    """
    verify = _verify if _verify is not None else _real_verify
    commit = _commit if _commit is not None else _real_commit
    cwd = Path(worktree_path)
    cmd = (verify_command or "").strip()

    if cmd:
        # A real verify command was supplied — run it and be honest about the result.
        passed = verify(cmd, cwd)
        if not passed:
            return {
                "success": True,
                "verify_passed": False,
                "verified": False,
                "committed": False,
                "commit": None,
            }
        msg = f"goal: {loop} fix via {auto_command} (verified checkpoint)"
        sha = commit(cwd, msg)
        return {
            "success": True,
            "verify_passed": True,
            "verified": True,
            "committed": sha is not None,
            "commit": sha,
        }
    else:
        # No verify command — still commit to allow progress, but report honestly:
        # this checkpoint was NOT verified; do NOT claim verify_passed True.
        msg = f"goal: {loop} fix via {auto_command} (UNVERIFIED — no verify command)"
        sha = commit(cwd, msg)
        return {
            "success": True,
            "verify_passed": False,
            "verified": False,
            "committed": sha is not None,
            "commit": sha,
            "unverified": True,
        }
