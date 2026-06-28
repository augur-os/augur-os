"""Atomic operations for the inline-session routines goal catalog-loop (ADR-793).

The AI client (not a Python subprocess) drives the convergence loop and is the
Task invoker. These ops expose the ADR-755 spine — worktree, scan+mechanical,
verify+commit, escalate, status — as deterministic, JSON-returning steps the
client calls between spawning its own fix subagents. No LLM calls here.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
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


def _is_route_value(value: str) -> bool:
    """True if ``value`` is a dashboard ROUTE URL (e.g. ``/login``, ``/settings/ai``,
    ``/workspace/ai``) rather than a filesystem path.

    The page-health / testing loops emit findings keyed (under ``path``) on the
    HTTP route they probed, NOT a file on disk. Such a finding IS in-scope — a
    worktree subagent fixes the dashboard page that serves the route — so it must
    not be mistaken for an out-of-worktree filesystem path and dropped.

    It must be distinguished from a genuine out-of-repo filesystem path (a vault
    file like ``/Users/.../BRAIN.yaml`` or ``/private/var/Au-vault/skills/a``)
    which MUST stay droppable. Two signals a real filesystem path has and a route
    lacks: (1) a file extension, or (2) a top-level component that actually exists
    as a directory on disk. A route's leading segment (``/workspace``, ``/login``,
    ``/settings``) is not a real filesystem root, so it fails both checks.
    """
    if not value.startswith("/"):
        return False
    p = Path(value)
    if p.suffix:  # a file extension → filesystem path, not a route
        return False
    parts = p.parts  # ("/", "workspace", "ai")
    if len(parts) < 2:  # bare "/" is not a route
        return False
    try:
        if (Path(parts[0]) / parts[1]).exists():
            return False  # leading segment is a real fs root → treat as a path
    except OSError:
        return False
    return True


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

    ROUTE-URL values (e.g. ``/login``, ``/workspace/ai`` from page-health/testing
    scanners) are NOT filesystem paths and are ignored as path constraints — the
    finding stays in-scope so the worktree subagent fixes the page serving it. See
    ``_is_route_value``.
    """
    if not isinstance(finding, dict):
        return True
    root_r = root.resolve()
    paths = [
        finding[k] for k in _FINDING_PATH_KEYS
        if isinstance(finding.get(k), str) and finding[k]
        and not _is_route_value(finding[k])
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


def _default_orchestrator_loops() -> list[str]:
    """Tiered WORKTREE loops eligible for parallel fan-out: every declared loop
    except the inline-session prompt loops (dream, inbox-triage), the catalog
    driver (goal-loop), and ADR-818 in-place loops (isolation.mode: in-place).

    In-place loops (self-heal, observability, knowledge-enrichment, ...) act on
    the live vault/runtime/external state, which an isolated worktree cannot
    own — fanning them out only ever produced 0 verified commits and, worse,
    occasionally drove a harmful out-of-scope bucket (e.g. self-heal proposing
    to delete augur-core from the live Claude Desktop config). They are routed
    to the daemon instead and surfaced via op_fanout_plan's
    loops_with_out_of_scope_work."""
    try:
        from . import registry
    except ImportError:  # pragma: no cover
        from routine_orchestrator import registry  # type: ignore[no-redef]
    out: list[str] = []
    for r in registry.list_routines():
        if r.id == "goal-loop":
            continue
        if getattr(r, "execution", "") == "inline-session":
            continue
        if getattr(r, "isolation_mode", "worktree") == "in-place":
            continue
        out.append(r.id)
    return sorted(out)


def _in_place_orchestrator_loops() -> list[str]:
    """ADR-818 in-place loops (isolation.mode: in-place) — excluded from the
    /a-loops all worktree fan-out and handled by the daemon instead. Returned in
    the triage plan so they are visibly routed, not silently dropped (rule 8)."""
    try:
        try:
            from . import registry
        except ImportError:  # pragma: no cover
            from routine_orchestrator import registry  # type: ignore[no-redef]
        out = [
            r.id
            for r in registry.list_routines()
            if r.id != "goal-loop"
            and getattr(r, "execution", "") != "inline-session"
            and getattr(r, "isolation_mode", "worktree") == "in-place"
        ]
        return sorted(out)
    except Exception:  # pragma: no cover - triage must never crash on this
        return []


def _in_place_loop_surfaces() -> dict[str, str]:
    """{loop_id: execution_surface} for in-place loops, so /a-loops all knows
    which surface (guardrail policy) to pass to goal-run-inplace."""
    try:
        try:
            from . import registry
        except ImportError:  # pragma: no cover
            from routine_orchestrator import registry  # type: ignore[no-redef]
        return {
            r.id: getattr(r, "execution_surface", "mixed")
            for r in registry.list_routines()
            if r.id != "goal-loop"
            and getattr(r, "execution", "") != "inline-session"
            and getattr(r, "isolation_mode", "worktree") == "in-place"
        }
    except Exception:  # pragma: no cover - triage must never crash on this
        return {}


def _no_repo_commit(*_args: Any, **_kwargs: Any) -> None:
    """runtime-surface guardrail: never create a git commit. A runtime loop's
    own fix() performs external writes through sanctioned tools (self-heal ->
    configure_mcp / repair-mcp-configs), so there is nothing to commit to git."""
    return None


def _real_orchestrate_run(loop: str, **kwargs: Any) -> Any:
    try:
        from . import orchestrator
    except ImportError:  # pragma: no cover
        from routine_orchestrator import orchestrator  # type: ignore[no-redef]
    return orchestrator.orchestrate_run(loop, **kwargs)


def _real_vault_sync() -> dict[str, Any]:
    """Commit + pull(ff/merge, abort-on-conflict) + push the vault repo under the
    ADR-195 machine-local merge lock — the SAME coordination the daemon uses
    nightly (ADR-816 Alternative 3, ratified 2026-06-28). Conflict-safe and never
    forces. Best-effort: returns a result dict; never raises into op_run_inplace."""
    try:
        from src.config.paths import get_vault_dir, get_project_root
        from src.lib.vault_sync import vault_sync_run
    except Exception as exc:  # pragma: no cover
        return {"success": False, "message": f"vault sync unavailable: {exc}"}
    lock_script = (
        get_project_root()
        / "project-brain/capabilities/skills/platform-admin/scripts/merge_lock.py"
    )
    acquired = False
    if lock_script.is_file():
        rc = subprocess.run(  # noqa: S603
            [sys.executable, str(lock_script), "acquire", "--tool", "a-loops-inplace", "--wait", "30"],
            capture_output=True, text=True,
        ).returncode
        acquired = rc == 0
        if not acquired:
            return {"success": False, "message": "vault merge lock contended; skipped (try again)"}
    try:
        return vault_sync_run(get_vault_dir())
    finally:
        if acquired:
            subprocess.run(  # noqa: S603
                [sys.executable, str(lock_script), "release", "--tool", "a-loops-inplace"],
                capture_output=True, text=True, check=False,
            )


def op_run_inplace(
    *,
    loop: str,
    surface: str,
    difficulty: int = 1,
    project_root: str | Path | None = None,
    runtime_dir: str | Path | None = None,
    _orchestrate: Callable[..., Any] = _real_orchestrate_run,
    _vault_sync: Callable[[], dict[str, Any]] = _real_vault_sync,
) -> dict[str, Any]:
    """ADR-818 phase-2: drive a loop IN-PLACE against the live target (no
    worktree) via the daemon engine, with surface-tiered guardrails.

    Aggressive: difficulty>=1 auto-applies mechanical fixes. Surface policy:
      - repo:    code-repo commit (engine default).
      - runtime: auto-apply; NO git commit — external writes go through the
                 loop's own sanctioned tools (configure_mcp / repair-mcp).
      - vault:   auto-apply to vault files, then commit + pull + push the vault
                 repo via vault_sync under the ADR-195 machine-local merge lock
                 — the SAME coordination the daemon uses nightly (ADR-816
                 Alternative 3, ratified 2026-06-28). The CODE repo is never
                 touched (commit_runner=_no_repo_commit; vault command modules
                 set external_commit=True). Cross-machine collisions are handled
                 cheaply by vault_sync's conflict-safe pull/abort + push-retry,
                 not eliminated (the ADR-816 remote lease would do that).
      - mixed:   code-repo commit (per-finding repo/vault split is a future
                 refinement; today mixed loops stay worktree so this is unused).
    """
    surface = surface or "mixed"
    eff_difficulty = difficulty
    commit_runner: Callable[..., Any] | None = None
    if surface == "runtime":
        commit_runner = _no_repo_commit
        commit_policy = "external-tools (no git commit)"
    elif surface == "vault":
        # Never touch the CODE repo; vault mutations are committed/pushed by
        # vault_sync under the machine-local lock after the engine applies them.
        commit_runner = _no_repo_commit
        commit_policy = "vault: apply + vault_sync commit/push under machine-local lock"
    else:  # repo / mixed
        commit_policy = "code-repo commit"

    try:
        result = _orchestrate(
            loop,
            difficulty=eff_difficulty,
            project_root=str(project_root) if project_root is not None else None,
            runtime_dir=str(runtime_dir) if runtime_dir is not None else None,
            commit_runner=commit_runner,
        )
    except Exception as exc:  # pragma: no cover - surface as a failed result
        return {"success": False, "loop": loop, "surface": surface, "error": str(exc)}

    applied = len(getattr(result, "mechanical_applied", []) or [])
    escalated = len(getattr(result, "enqueued", []) or [])
    dispatched = len(getattr(result, "dispatched", []) or [])
    deferred = len(getattr(result, "deferred", []) or [])

    # Vault: after the engine applied fixes to vault files in place, commit + push
    # the vault repo under the machine-local merge lock (ADR-816 Alternative 3).
    vault_sync: dict[str, Any] | None = None
    if surface == "vault" and applied > 0:
        try:
            vault_sync = _vault_sync()
        except Exception as exc:  # pragma: no cover - never fail the run on sync
            vault_sync = {"success": False, "message": f"vault sync raised: {exc}"}

    return {
        "success": True,
        "loop": loop,
        "surface": surface,
        "difficulty": eff_difficulty,
        "commit_policy": commit_policy,
        "mechanical_applied": applied,
        "escalated": escalated,
        "dispatched": dispatched,
        "deferred": deferred,
        "did_work": applied > 0,
        "vault_sync": vault_sync,
        "gated_on": None,
    }


def _worktree_available(default: int = 9) -> int:
    """Worktree-registry headroom (MAX_WORKTREES - in-use). Falls back to a safe
    default if the registry script can't be loaded."""
    try:
        import importlib.util
        from src.config.paths import get_project_root
        wt = Path(get_project_root()) / "scripts" / "worktree_registry.py"
        spec = importlib.util.spec_from_file_location("worktree_registry_fanout", wt)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return int(mod.cmd_list().get("available", default))
    except Exception:
        return default


def op_worktree(*, goal_id: str, stamp: str, project_root: str | Path) -> dict[str, Any]:
    """Resolve the goal and create its isolated worktree off the current branch."""
    try:
        spec = goal_catalog.resolve_goal_or_loop(goal_id)
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


def op_fanout_plan(
    *,
    scope: str = "orchestrator",
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    cap: int = 6,
    project_root: str | Path | None = None,
    scan_timeout_seconds: float = 8.0,
    max_iterations: int = 8,
    loop_cap: int = 6,
    _scan: Callable[..., Any] = _real_scan,
    _orchestrator_loops: Callable[[], list[str]] | None = None,
    _headroom: Callable[[], int] | None = None,
) -> dict[str, Any]:
    """Deterministic scan-triage for `/a-loops all`. Runs each in-scope orchestrator
    loop's NON-MUTATING scanner against the current repo, counts findings, and
    returns the work set plus a worktree-clamped concurrency cap. No worktrees,
    no commits — safe to call from a bare CLI (`--dry-run`).

    Each loop scan is bounded by `scan_timeout_seconds` (via goal_suggest.assess /
    SIGALRM) so a single slow scanner (e.g. hardening's npm-audit) cannot stall the
    full triage. A timed-out loop is conservatively included in `loops_with_work`
    (it is NOT proven clean) and reported in `timed_out`; a crashed loop is likewise
    included and reported in `crashed`; `partial` is True when any loop timed out or
    crashed. The per-loop scan bound relies on SIGALRM and is only enforced on the
    POSIX main thread; off the main thread or on Windows the scan runs unbounded and
    `partial` may be False even if a scan overran.
    """
    root = Path(project_root) if project_root is not None else Path(".")
    if not math.isfinite(scan_timeout_seconds):
        scan_timeout_seconds = 8.0
    scan_timeout_seconds = max(0.5, scan_timeout_seconds)
    loops = (_orchestrator_loops or _default_orchestrator_loops)()
    inc = {s for s in (include or []) if s}
    exc = {s for s in (exclude or []) if s}
    if inc:
        loops = [lp for lp in loops if lp in inc]
    if exc:
        loops = [lp for lp in loops if lp not in exc]

    try:
        from . import goal_suggest
    except ImportError:  # pragma: no cover
        from routine_orchestrator import goal_suggest  # type: ignore[no-redef]
    findings_by_loop = goal_suggest.assess(
        loops, project_root=root, scan=_scan,
        per_loop_timeout_seconds=scan_timeout_seconds, mark_crashes=True,
    )

    def _marker(f: Any, key: str) -> bool:
        return isinstance(f, dict) and bool(f.get(key))

    # Pre-filter each loop's findings through the SAME worktree-scope predicate the
    # fix flow uses (root = project_root for triage), so per_loop_counts reflects
    # only worktree-actionable work. Findings the fan-out cannot action (vault /
    # runtime / external) are NOT silently dropped (rule 8): they are surfaced in
    # out_of_scope_counts / loops_with_out_of_scope_work for the separate in-place
    # execution surface. Sentinel markers (timed_out / crashed) are not real
    # findings and are excluded from both counts.
    per_loop_counts: dict[str, int] = {}
    out_of_scope_counts: dict[str, int] = {}
    timed_out: list[str] = []
    crashed: list[str] = []
    for lp in loops:
        data = findings_by_loop.get(lp, [])
        if any(_marker(f, goal_suggest.SENTINEL_TIMEOUT) for f in data):
            timed_out.append(lp)
        if any(_marker(f, goal_suggest.SENTINEL_CRASHED) for f in data):
            crashed.append(lp)
        in_scope = 0
        out_scope = 0
        for f in data:
            if _marker(f, goal_suggest.SENTINEL_TIMEOUT) or _marker(f, goal_suggest.SENTINEL_CRASHED):
                continue
            if _finding_in_worktree(f, root):
                in_scope += 1
            else:
                out_scope += 1
        per_loop_counts[lp] = in_scope
        if out_scope:
            out_of_scope_counts[lp] = out_scope
    timed_out = sorted(timed_out)
    crashed = sorted(crashed)
    incomplete = set(timed_out) | set(crashed)
    loops_with_work = sorted({lp for lp, n in per_loop_counts.items() if n > 0} | incomplete)
    loops_with_out_of_scope_work = sorted(out_of_scope_counts)
    # A loop with only out-of-scope findings is NOT clean — it has work the fan-out
    # cannot action — so it is excluded from skipped_clean (it rides
    # loops_with_out_of_scope_work instead).
    skipped_clean = sorted(
        lp for lp in per_loop_counts
        if per_loop_counts[lp] == 0 and lp not in incomplete and lp not in out_of_scope_counts
    )
    partial = bool(timed_out or crashed)
    headroom = (_headroom or _worktree_available)()
    safe_cap = max(0, min(cap, headroom))
    return {
        "success": True,
        "scope": scope,
        "loops_with_work": loops_with_work,
        "per_loop_counts": per_loop_counts,
        "out_of_scope_counts": out_of_scope_counts,
        "loops_with_out_of_scope_work": loops_with_out_of_scope_work,
        "skipped_clean": skipped_clean,
        "in_place_loops": _in_place_orchestrator_loops(),
        "in_place_surfaces": _in_place_loop_surfaces(),
        "timed_out": timed_out,
        "crashed": crashed,
        "partial": partial,
        "safe_cap": safe_cap,
        "worktree_headroom": headroom,
        "max_iterations": max_iterations,
        "loop_cap": loop_cap,
    }


def _real_inspect_worktree(entry: Any, *, stamp: str) -> dict[str, Any]:
    """Ground-truth reconstruction for a driver that never reported its verdict.

    Inspects the loop's `goal/<loop>-<stamp>` worktree and recovers what it can:
    branch presence, the count of verified-checkpoint commits (subjects starting
    ``goal:`` — exactly what op_record_bucket writes), and whether the tree is
    dirty. Returns ``{"exists": False}`` when the worktree is gone or cannot be
    located — the caller then marks the row ``unknown``. Defensive by design:
    never raises for an absent/odd worktree, only for unexpected git failures the
    caller's try/except still absorbs."""
    wt = entry.get("worktree_path") if isinstance(entry, dict) else None
    branch = entry.get("branch") if isinstance(entry, dict) else None
    if not wt and branch:
        wt = _worktree_path_for_branch(str(branch))
    if not wt:
        return {"exists": False}
    path = Path(wt)
    if not path.exists():
        return {"exists": False}

    def _git(*args: str) -> str:
        proc = subprocess.run(  # noqa: S603
            ["git", "-C", str(path), *args],
            capture_output=True, text=True,
        )
        return proc.stdout if proc.returncode == 0 else ""

    inside = _git("rev-parse", "--is-inside-work-tree").strip()
    if inside != "true":
        return {"exists": False}
    cur_branch = _git("branch", "--show-current").strip() or branch
    subjects = _git("log", "--format=%s", "-n", "500").splitlines()
    committed = sum(1 for s in subjects if s.startswith("goal:"))
    dirty = bool(_git("status", "--porcelain").strip())
    return {
        "exists": True,
        "branch": cur_branch,
        "committed_checkpoints": committed,
        "dirty": dirty,
    }


def _worktree_path_for_branch(branch: str) -> str | None:
    """Best-effort: locate the checked-out worktree path for a branch via
    `git worktree list --porcelain` from the current process cwd (sibling goal
    worktrees share the same repo). Returns None when not found."""
    proc = subprocess.run(  # noqa: S603
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    cur_path: str | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            cur_path = line[len("worktree "):].strip()
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            if ref == branch or ref == f"refs/heads/{branch}":
                return cur_path
    return None


def _needs_reconstruction(r: Any) -> bool:
    """A result row is unreported when it is null/non-dict, explicitly flagged
    ``unreported``, or carries no usable verdict."""
    if not isinstance(r, dict):
        return True
    if r.get("unreported"):
        return True
    return not r.get("verdict")


def _reconstruct_row(entry: Any, *, stamp: str, inspect: Callable[..., Any]) -> dict[str, Any]:
    """Build a best-effort row for a driver that never reported. Marks the verdict
    ``unreported (reconstructed)`` with whatever the worktree yields, or ``unknown``
    when the worktree is gone / inspection fails."""
    loop = entry.get("loop") if isinstance(entry, dict) else None
    branch = entry.get("branch") if isinstance(entry, dict) else None
    try:
        info = inspect(entry, stamp=stamp) or {}
    except Exception:  # noqa: BLE001 - reconstruction must never raise.
        info = {}
    if info.get("exists"):
        return {
            "loop": loop or "?",
            "verdict": "unreported (reconstructed)",
            "branch": info.get("branch") or branch,
            "residual": None,
            "committed_checkpoints": info.get("committed_checkpoints", 0),
            "dirty": info.get("dirty"),
            "reconstructed": True,
        }
    return {
        "loop": loop or "?",
        "verdict": "unknown",
        "branch": branch,
        "residual": None,
        "committed_checkpoints": None,
        "reconstructed": True,
    }


def _classify_result(r: dict[str, Any]) -> str:
    """Honest per-loop category for the rollup:

      - ``unfinished`` — stalled/exhausted/failed (residual escalated).
      - ``unreported`` — driver was silent (reconstructed or unknown).
      - ``no_op`` — converged/no_op but committed ZERO and had out-of-scope debt:
        the loop fixed nothing. NOT clean.
      - ``clean`` — converged with real commits, OR genuinely empty (nothing was
        ever out of scope). When ``committed_checkpoints`` is absent we cannot
        prove a no-op, so a bare ``converged`` stays clean (back-compat)."""
    verdict = r.get("verdict")
    if verdict in {"stalled", "exhausted", "failed"}:
        return "unfinished"
    if verdict in {"unknown", "unreported (reconstructed)"} or r.get("reconstructed"):
        return "unreported"
    committed = r.get("committed_checkpoints")
    out_of_scope = r.get("out_of_scope", 0) or 0
    if verdict == "no_op":
        return "no_op"
    if verdict == "converged":
        if committed is None:
            return "clean"  # back-compat: cannot prove a no-op
        if committed > 0:
            return "clean"
        return "no_op" if out_of_scope > 0 else "clean"
    return "unreported"  # missing/foreign verdict that slipped through


def op_fanout_report(
    *,
    results: list[dict[str, Any]],
    runtime_dir: str | Path | None = None,
    stamp: str = "",
    _inspect: Callable[..., Any] = _real_inspect_worktree,
) -> dict[str, Any]:
    """Write an honest rollup of a parallel `/a-loops all` run.

    Honesty (ADR-793, issues #5/#7):
      - Never reports ``all_clean`` unless EVERY loop is genuinely clean —
        converged WITH committed work, or genuinely empty. A loop that merely
        no-op'd (empty only because everything was out of scope, 0 commits) is
        NOT clean.
      - A driver that finished but returned nothing (null/incomplete/``unreported``)
        does not silently vanish: its verdict is RECONSTRUCTED from the worktree's
        ground truth (`goal/<loop>-<stamp>`: checkpoint commits, clean/dirty,
        branch present) and marked ``unreported (reconstructed)`` — or ``unknown``
        when the worktree is gone. ``all_clean`` is never True when any loop was
        unreported."""
    runtime = Path(runtime_dir) if runtime_dir is not None else _default_runtime_dir()
    out_dir = runtime / "a-loops-all"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Normalize: reconstruct any silent/incomplete driver result from ground truth
    # BEFORE classifying, so no loop is dropped or counted as success on silence.
    norm: list[dict[str, Any]] = []
    for r in results:
        if _needs_reconstruction(r):
            norm.append(_reconstruct_row(r, stamp=stamp, inspect=_inspect))
        else:
            norm.append(r)

    categories = [_classify_result(r) for r in norm]
    unfinished = [r for r, c in zip(norm, categories) if c == "unfinished"]
    no_op = [r for r, c in zip(norm, categories) if c == "no_op"]
    unreported = [r for r, c in zip(norm, categories) if c == "unreported"]
    clean = [r for r, c in zip(norm, categories) if c == "clean"]
    converged = [r for r in norm if r.get("verdict") == "converged"]
    did_work = [r for r in norm if (r.get("committed_checkpoints") or 0) > 0]
    branches = [r["branch"] for r in norm if r.get("branch")]
    all_clean = bool(norm) and len(clean) == len(norm)

    lines = ["# /a-loops all — rollup", ""]
    lines.append(f"- loops run: {len(norm)}")
    lines.append(f"- converged (clean): {len(clean)}")
    lines.append(f"- did work (committed checkpoints): {len(did_work)}")
    lines.append(f"- no-op (0 commits, out-of-scope only): {len(no_op)}")
    lines.append(f"- unfinished (stalled/exhausted/failed): {len(unfinished)}")
    lines.append(f"- unreported (reconstructed/unknown): {len(unreported)}")
    lines.append(f"- all_clean: {all_clean}")
    lines.append("")
    lines.append("| loop | verdict | did_work | committed | branch | residual |")
    lines.append("|---|---|---|---|---|---|")
    for r in norm:
        committed = r.get("committed_checkpoints")
        did = "yes" if (committed or 0) > 0 else ("no" if committed is not None else "?")
        committed_disp = "?" if committed is None else committed
        residual = r.get("residual")
        residual_disp = "?" if residual is None else residual
        lines.append(
            f"| {r.get('loop','?')} | {r.get('verdict','?')} | {did} | "
            f"{committed_disp} | {r.get('branch') or '—'} | {residual_disp} |"
        )
    if no_op:
        lines += ["", "> No-op loops committed nothing; their findings were all "
                  "out of scope and remain escalated, not resolved."]
    if unfinished:
        lines += ["", "> Residual findings were escalated; review branches before merge."]
    if unreported:
        lines += ["", "> Unreported loops were reconstructed from worktree state; "
                  "verify their branches manually before merge."]

    tag = stamp or "latest"
    md_path = out_dir / f"rollup-{tag}.md"
    json_path = out_dir / f"rollup-{tag}.json"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {"all_clean": all_clean, "converged": len(converged),
             "clean": len(clean), "did_work": len(did_work), "no_op": len(no_op),
             "unfinished": len(unfinished), "unreported": len(unreported),
             "results": norm},
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "success": True,
        "report_md": str(md_path),
        "report_json": str(json_path),
        "converged": len(converged),
        "clean": len(clean),
        "did_work": len(did_work),
        "no_op": len(no_op),
        "unfinished": len(unfinished),
        "unreported": len(unreported),
        "all_clean": all_clean,
        "branches": branches,
        "results": norm,
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
    """Stage all (tracked/untracked, NON-ignored) changes and commit; return the
    new HEAD SHA, or None when there was nothing committable.

    ``git add -A`` deliberately never stages gitignored files, so a fix that only
    touched generated/ignored artifacts stages nothing and ``git commit`` fails —
    returning None. That None is NOT proof the work was idle: op_record_bucket
    calls _real_detect_changes to tell "only ignored changed" (real but
    uncommittable) apart from "truly nothing changed". We do NOT force-add ignored
    artifacts (that would pollute the repo); honest reporting beats a fake commit.
    """
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


def _real_detect_changes(cwd: Path) -> str:
    """Classify the worktree state for honest commit reporting. Returns one of:

    - ``"tracked"``      — tracked/untracked NON-ignored changes exist; git can
                           stage and commit them (the normal path).
    - ``"ignored_only"`` — no committable changes, but gitignored/generated files
                           are present in the working tree (e.g. a regenerated
                           client-projection set). Real work with no commit
                           possible — do NOT fake a commit, report it honestly.
    - ``"none"``         — pristine: nothing changed at all (an honest idle).

    Only consulted when a commit produced nothing, to separate case (b) from (c).
    Presence-based: ``git status --porcelain --ignored`` lists ignored paths in
    the tree regardless of when they changed, so "ignored_only" means "no tracked
    work AND generated artifacts are present", which is the best signal available
    at checkpoint time without a pre-fix snapshot — far more honest than the old
    committed:False/idle conflation, while never polluting the repo.
    """
    porcelain = subprocess.run(  # noqa: S603
        ["git", "-C", str(cwd), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if porcelain.returncode != 0:
        return "none"  # not a git worktree (or git failed) — nothing to report
    if porcelain.stdout.strip():
        return "tracked"
    ignored = subprocess.run(  # noqa: S603
        ["git", "-C", str(cwd), "status", "--porcelain", "--ignored"],
        capture_output=True,
        text=True,
    )
    if any(line.startswith("!!") for line in ignored.stdout.splitlines()):
        return "ignored_only"
    return "none"


def _commit_outcome(
    commit: Callable[[Path, str], str | None],
    changes: Callable[[Path], str],
    cwd: Path,
    msg: str,
) -> tuple[str | None, bool, str | None]:
    """Attempt the commit and classify the result for op_record_bucket.

    Returns ``(commit_sha_or_None, applied, uncommittable_reason_or_None)``:
      - tracked changes committed     -> (sha, True, None)
      - only gitignored/generated     -> (None, True, "only gitignored/generated changes")
      - nothing changed (honest idle) -> (None, False, None)

    The injected ``commit`` runs first (preserving the existing seam/behavior):
    when it returns a SHA, tracked work was committed and detection is skipped.
    Detection is consulted ONLY when commit produced nothing, to tell real-but-
    uncommittable work apart from a no-op.
    """
    sha = commit(cwd, msg)
    if sha is not None:
        return sha, True, None
    if changes(cwd) == "ignored_only":
        return None, True, "only gitignored/generated changes"
    return None, False, None


def op_loop_status(
    *,
    prev_fingerprint: list[str],
    current_fingerprint: list[str],
    iterations: int,
    loop_cap: int,
    budget_remaining: int,
    committed_count: int | None = None,
    out_of_scope_count: int = 0,
) -> dict[str, Any]:
    """Report a stop verdict for the client's loop (converged/no_op/stalled/
    exhausted/continue). Mirrors run_loop_to_convergence; reports evidence, does
    not assert done.

    An empty ``current_fingerprint`` is necessary but NOT sufficient for genuine
    convergence: the fingerprint is also empty when every finding was filtered out
    as ``out_of_worktree`` and the loop fixed NOTHING. ``committed_count`` (verified
    checkpoints landed) and ``out_of_scope_count`` (findings dropped as foreign to
    the worktree) let this op distinguish:

      - ``converged`` — empty fingerprint AND either real work landed
        (committed_count > 0) OR nothing was ever out of scope (a genuinely clean
        scan). Also the back-compat verdict when ``committed_count`` is omitted.
      - ``no_op`` — empty fingerprint, ZERO commits, AND findings existed only
        out of scope (committed_count == 0 and out_of_scope_count > 0). The loop
        proved nothing; its out-of-scope debt is escalated, not resolved.

    ``committed_count`` defaults to None → legacy behavior (always ``converged`` on
    empty), so existing callers are unaffected. ``did_work`` is True/False when
    ``committed_count`` is known, else None (unknown)."""
    did_work = (committed_count > 0) if committed_count is not None else None
    if not current_fingerprint:
        if committed_count is not None and committed_count <= 0 and out_of_scope_count > 0:
            verdict = "no_op"
        else:
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
        "committed_count": committed_count,
        "out_of_scope_count": out_of_scope_count,
        "did_work": did_work,
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
    _changes: Callable[[Path], str] | None = None,
) -> dict[str, Any]:
    """Verify the worktree after a subagent applied a bucket fix; commit if green.

    No trust-ledger write is performed here — trust governs tiered auto-apply
    in the orchestrator's mechanical phase, not the inline goal session loop
    (YAGNI: the goal loop operates at a coarser checkpoint granularity and does
    not require per-command trust accounting at this stage).

    A bucket fix that only regenerated gitignored/generated files (observed:
    knowledge-enrichment rewriting client-projection files) cannot produce a
    commit — ``git add -A`` stages nothing. That is NOT idle: the result reports
    ``applied:True`` with ``uncommittable_reason:"only gitignored/generated
    changes"`` so the verified-checkpoint metric stops conflating real generated
    work with a no-op. ``applied:False`` is reserved for a truly pristine
    worktree. Tracked-change commits keep their existing (committed/verified)
    behavior unchanged.
    """
    verify = _verify if _verify is not None else _real_verify
    commit = _commit if _commit is not None else _real_commit
    changes = _changes if _changes is not None else _real_detect_changes
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
        sha, applied, reason = _commit_outcome(commit, changes, cwd, msg)
        out = {
            "success": True,
            "verify_passed": True,
            "verified": True,
            "committed": sha is not None,
            "commit": sha,
            "applied": applied,
        }
        if reason:
            out["uncommittable_reason"] = reason
        return out
    else:
        # No verify command — still commit to allow progress, but report honestly:
        # this checkpoint was NOT verified; do NOT claim verify_passed True.
        msg = f"goal: {loop} fix via {auto_command} (UNVERIFIED — no verify command)"
        sha, applied, reason = _commit_outcome(commit, changes, cwd, msg)
        out = {
            "success": True,
            "verify_passed": False,
            "verified": False,
            "committed": sha is not None,
            "commit": sha,
            "unverified": True,
            "applied": applied,
        }
        if reason:
            out["uncommittable_reason"] = reason
        return out
