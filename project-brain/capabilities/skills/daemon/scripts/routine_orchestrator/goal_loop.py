"""Bounded convergence controllers for routine goals."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from . import escalation_queue, goal_catalog
except ImportError:
    from routine_orchestrator import escalation_queue, goal_catalog  # type: ignore[no-redef]

OrchestrateFn = Callable[..., Any]
STOP_CONVERGED = "converged"
STOP_STALLED = "stalled"
STOP_EXHAUSTED = "exhausted"
STOP_ERRORED = "errored"


@dataclass
class GoalBudget:
    """Whole-run budget. Iterations are the hard termination guarantee."""

    max_iterations: int
    used: int = 0

    @property
    def exhausted(self) -> bool:
        return self.used >= self.max_iterations

    def tick(self) -> None:
        self.used += 1


@dataclass(frozen=True)
class LoopOutcome:
    """Terminal state for one general routine loop."""

    loop: str
    stop_reason: str
    iterations: int
    residual: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class GoalContext:
    """Inputs shared by all concrete goal steps."""

    project_root: Path
    runtime_dir: Path
    compound_proposal_json: Path | None = None


@dataclass(frozen=True)
class StepExecution:
    """Raw result from executing one concrete goal step."""

    step_id: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "command": list(self.command),
            "returncode": self.returncode,
            "success": self.success,
            "stdout_tail": _tail(self.stdout),
            "stderr_tail": _tail(self.stderr),
        }


@dataclass(frozen=True)
class GoalIteration:
    """One pass over all concrete checks for a goal."""

    index: int
    checks: list[StepExecution]
    fingerprint: str

    @property
    def ready(self) -> bool:
        return all(check.success for check in self.checks)

    def failed_checks(self) -> list[StepExecution]:
        return [check for check in self.checks if not check.success]

    def to_payload(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "ready": self.ready,
            "fingerprint": self.fingerprint,
            "checks": [check.to_payload() for check in self.checks],
        }


@dataclass(frozen=True)
class GoalRunResult:
    """Final result for a concrete routine goal run."""

    goal_id: str
    status: str
    iterations: int
    next_actions: list[str]
    report_json_path: Path
    report_markdown_path: Path
    iteration_records: list[GoalIteration] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "success": True,
            "goal_id": self.goal_id,
            "status": self.status,
            "iterations": self.iterations,
            "next_actions": list(self.next_actions),
            "report_json_path": str(self.report_json_path),
            "report_markdown_path": str(self.report_markdown_path),
            "iteration_records": [
                iteration.to_payload() for iteration in self.iteration_records
            ],
        }


CommandRunner = Callable[[goal_catalog.GoalStep, GoalContext], StepExecution]
RepairCallback = Callable[[GoalIteration], None]


@dataclass(frozen=True)
class WorktreeHandle:
    path: str
    branch: str


@dataclass(frozen=True)
class LoopGoalRunResult:
    goal_id: str
    branch: str
    worktree_path: str
    loop_outcomes: list[LoopOutcome]
    escalated_count: int

    @property
    def converged(self) -> bool:
        return all(outcome.stop_reason == STOP_CONVERGED for outcome in self.loop_outcomes)


def fingerprints(findings: list[dict[str, Any]]) -> frozenset[tuple[str, ...]]:
    """Order-independent identity of a finding set for stall detection."""
    keys = set()
    for finding in findings:
        keys.add(
            tuple(
                str(finding.get(key, ""))
                for key in ("auto_command", "loop", "detail", "title", "path")
            )
        )
    return frozenset(keys)


def run_loop_to_convergence(
    loop: str,
    *,
    orchestrate: OrchestrateFn,
    budget: GoalBudget,
    loop_cap: int,
    journal: Callable[[dict[str, Any]], None] | None = None,
    **orchestrate_kwargs: Any,
) -> LoopOutcome:
    """Iterate orchestrate_run for one loop until a terminal stop reason."""

    iterations = 0
    prev_fp: frozenset[tuple[str, ...]] | None = None
    last_findings: list[dict[str, Any]] = []

    while True:
        # Shared budget may already be drained by an earlier loop in the goal;
        # this can return exhausted with iterations == 0 (no orchestrate call made).
        if budget.exhausted or iterations >= loop_cap:
            return LoopOutcome(loop, STOP_EXHAUSTED, iterations, residual=last_findings)
        iterations += 1
        budget.tick()
        try:
            result = orchestrate(loop, **orchestrate_kwargs)
        except Exception as exc:  # noqa: BLE001 - one loop failure must not abort the goal.
            return LoopOutcome(
                loop,
                STOP_ERRORED,
                iterations,
                residual=last_findings,
                error=str(exc),
            )

        findings = list(getattr(result, "findings", []) or [])
        last_findings = findings
        if journal:
            journal({"loop": loop, "iteration": iterations, "finding_count": len(findings)})

        if not findings:
            return LoopOutcome(loop, STOP_CONVERGED, iterations, residual=[])
        fp = fingerprints(findings)
        if fp == prev_fp:
            return LoopOutcome(loop, STOP_STALLED, iterations, residual=findings)
        prev_fp = fp


def _default_escalate(finding: dict[str, Any], *, runtime_dir: Any = None) -> None:
    escalation_queue.enqueue(finding, runtime_dir=runtime_dir)


# TODO_CLEANUP(ADR-793): the routines goal path no longer calls run_goal_loops in
# production — the catalog-loop is now an inline-session routine driven by the AI
# client via the goal_ops atomic ops. Retained for its unit tests and any
# headless/in-process caller; remove if those drop it.
def run_goal_loops(
    goal_id: str,
    *,
    project_root: Path | str,
    stamp: str,
    orchestrate: OrchestrateFn,
    worktree_factory: Callable[..., Any],
    escalate: Callable[..., None] = _default_escalate,
    journal: Callable[[dict[str, Any]], None] | None = None,
    loop_cap: int = 6,
    max_iterations: int = 60,
) -> LoopGoalRunResult:
    """Resolve a catalog goal, isolate a worktree, drive loops, and escalate residuals."""

    spec = goal_catalog.resolve(goal_id)
    worktree = worktree_factory(goal_id=goal_id, stamp=stamp, project_root=project_root)
    budget = GoalBudget(max_iterations=max_iterations)

    outcomes: list[LoopOutcome] = []
    escalated = 0
    for loop in spec.loops:
        outcome = run_loop_to_convergence(
            loop,
            orchestrate=orchestrate,
            budget=budget,
            loop_cap=loop_cap,
            journal=journal,
            project_root=worktree.path,
        )
        outcomes.append(outcome)
        if outcome.stop_reason in (STOP_STALLED, STOP_EXHAUSTED, STOP_ERRORED):
            for finding in outcome.residual:
                escalate(finding)
                escalated += 1
            # For errored loops, residual is typically empty (the error occurred before findings
            # were produced). Escalate a structured marker so the failure is not silently lost —
            # it lands in the same queue the user inspects via `aug routine pending-escalations`.
            if outcome.stop_reason == STOP_ERRORED:
                marker: dict[str, Any] = {
                    "goal_loop_error": True,
                    "loop": outcome.loop,
                    "error": outcome.error,
                    "auto_command": "goal-loop-error",
                    "detail": f"loop {outcome.loop!r} errored: {outcome.error}",
                }
                escalate(marker)
                escalated += 1
        if journal:
            journal(
                {
                    "loop": loop,
                    "stop_reason": outcome.stop_reason,
                    "iterations": outcome.iterations,
                }
            )

    return LoopGoalRunResult(
        goal_id=goal_id,
        branch=worktree.branch,
        worktree_path=worktree.path,
        loop_outcomes=outcomes,
        escalated_count=escalated,
    )


def run_goal(
    goal_id: str,
    *,
    project_root: Path | str | None = None,
    runtime_dir: Path | str | None = None,
    max_iterations: int = 1,
    command_runner: CommandRunner | None = None,
    repair_callback: RepairCallback | None = None,
    compound_proposal_json: Path | str | None = None,
    skip_smoke: bool = False,
) -> GoalRunResult:
    """Run a concrete routine goal until ready, agent action is needed, or progress stalls."""

    if max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")

    goal = goal_catalog.get_goal(goal_id)
    root = Path(project_root) if project_root is not None else _default_project_root()
    runtime = Path(runtime_dir) if runtime_dir is not None else _default_runtime_dir()
    context = GoalContext(
        project_root=root,
        runtime_dir=runtime,
        compound_proposal_json=Path(compound_proposal_json)
        if compound_proposal_json is not None
        else None,
    )
    runner = command_runner or _subprocess_runner
    steps = list(goal_catalog.steps_for_goal(goal, skip_smoke=skip_smoke))

    records: list[GoalIteration] = []
    seen_fingerprints: set[str] = set()
    status = "needs_agent_action"

    for index in range(1, max_iterations + 1):
        checks = [runner(step, context) for step in steps]
        iteration = GoalIteration(
            index=index,
            checks=checks,
            fingerprint=_step_fingerprint(checks),
        )
        records.append(iteration)

        if iteration.ready:
            status = "ready"
            break

        if iteration.fingerprint in seen_fingerprints:
            status = "stalled"
            break
        seen_fingerprints.add(iteration.fingerprint)

        if repair_callback is None:
            status = "needs_agent_action"
            break

        if index >= max_iterations:
            status = "exhausted"
            break

        repair_callback(iteration)

    next_actions = [] if status == "ready" else _next_actions(goal.id, records[-1])
    report_json, report_md = _write_reports(
        goal=goal,
        status=status,
        records=records,
        next_actions=next_actions,
        runtime_dir=runtime,
    )
    return GoalRunResult(
        goal_id=goal.id,
        status=status,
        iterations=len(records),
        next_actions=next_actions,
        report_json_path=report_json,
        report_markdown_path=report_md,
        iteration_records=records,
    )


def list_goal_payloads() -> dict[str, Any]:
    """Return concrete goals for `aug routine goal` without an id."""

    goals = [goal_catalog.goal_payload(goal) for goal in goal_catalog.list_goals()]
    return {"success": True, "goals": goals, "count": len(goals)}


def _subprocess_runner(
    step: goal_catalog.GoalStep,
    context: GoalContext,
) -> StepExecution:
    command = _command_for_step(step, context)
    completed = subprocess.run(
        command,
        cwd=context.project_root,
        text=True,
        capture_output=True,
        timeout=900,
        check=False,
    )
    return StepExecution(
        step_id=step.id,
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _command_for_step(
    step: goal_catalog.GoalStep,
    context: GoalContext,
) -> list[str]:
    if step.kind == "demo_ready":
        return [
            sys.executable,
            "project-brain/capabilities/skills/ingest/scripts/demo_ready.py",
            "ready",
        ]
    if step.kind == "demo_smoke":
        return [
            sys.executable,
            "project-brain/capabilities/skills/ingest/scripts/demo_ready.py",
            "smoke",
        ]
    if step.kind == "compound_review":
        command = [
            sys.executable,
            "project-brain/capabilities/skills/platform-admin/scripts/dev_merge_demo_proof.py",
            "--com",
            "--skillify",
            "--compound-review",
        ]
        if context.compound_proposal_json is not None:
            command.extend(["--review-proposal-json", str(context.compound_proposal_json)])
        return command
    raise ValueError(f"unsupported goal step kind: {step.kind}")


def _next_actions(goal_id: str, iteration: GoalIteration) -> list[str]:
    actions: list[str] = []
    rerun = f"aug routine goal {goal_id} --max-iterations 1"
    for check in iteration.failed_checks():
        text = f"{check.stdout}\n{check.stderr}".lower()
        if check.step_id == "compound-review" and "proposal" in text:
            actions.append(
                "Create evidence-backed compound proposal JSON from the evidence artifact, "
                f"then rerun with `{rerun} --compound-proposal-json <path>`."
            )
        elif check.step_id == "compound-review":
            actions.append(
                "Fix the wiki, skillify, or compound-review proof blocker, "
                f"then rerun `{rerun}`."
            )
        elif check.step_id == "demo-readiness":
            actions.append(
                "Fix local/offline demo readiness failures from the readiness output, "
                f"then rerun `{rerun}`."
            )
        elif check.step_id == "demo-smoke":
            actions.append(
                "Repair the demo smoke flow or generated artifacts named in the smoke output, "
                f"then rerun `{rerun}`."
            )
        else:
            actions.append(f"Fix `{check.step_id}` and rerun `{rerun}`.")
    return actions


def _write_reports(
    *,
    goal: goal_catalog.GoalDefinition,
    status: str,
    records: list[GoalIteration],
    next_actions: list[str],
    runtime_dir: Path,
) -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = runtime_dir / "routine-goals" / goal.id
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"{stamp}.json"
    md_path = report_dir / f"{stamp}.md"

    payload = {
        "goal_id": goal.id,
        "title": goal.title,
        "status": status,
        "iterations": [record.to_payload() for record in records],
        "next_actions": next_actions,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        _render_markdown(goal=goal, status=status, records=records, next_actions=next_actions),
        encoding="utf-8",
    )
    return json_path, md_path


def _render_markdown(
    *,
    goal: goal_catalog.GoalDefinition,
    status: str,
    records: list[GoalIteration],
    next_actions: list[str],
) -> str:
    headline = f"Demo goal: {status}" if goal.id == "demo-readiness" else f"Goal: {status}"
    lines = [
        "---",
        "schema: augur.routine_goal_report.v1",
        f"goal_id: {goal.id}",
        f"status: {status}",
        "---",
        "",
        f"# {headline}",
        "",
        f"- Goal: {goal.title}",
        f"- Iterations: {len(records)}",
    ]
    for record in records:
        lines.append(f"- Iteration {record.index}: {'ready' if record.ready else 'blocked'}")
        for check in record.checks:
            state = "pass" if check.success else "fail"
            lines.append(f"  - {check.step_id}: {state} ({check.returncode})")
    if next_actions:
        lines.extend(["", "## Next actions"])
        lines.extend(f"- {action}" for action in next_actions)
    lines.append("")
    return "\n".join(lines)


def _step_fingerprint(checks: Iterable[StepExecution]) -> str:
    failed = [
        {
            "step_id": check.step_id,
            "returncode": check.returncode,
            "stdout_tail": _tail(check.stdout, limit=500),
            "stderr_tail": _tail(check.stderr, limit=500),
        }
        for check in checks
        if not check.success
    ]
    raw = json.dumps(failed, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _tail(value: str, *, limit: int = 1200) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _default_project_root() -> Path:
    try:
        from src.config.paths import get_project_root

        return Path(get_project_root())
    except Exception:
        return Path.cwd()


def _default_runtime_dir() -> Path:
    try:
        from src.config.paths import get_runtime_dir

        return Path(get_runtime_dir())
    except Exception:
        return Path.home() / "Library" / "Application Support" / "Augur" / "state"


def create_goal_worktree(*, goal_id: str, stamp: str, project_root: Path | str) -> WorktreeHandle:
    """Create goal/<id>-<stamp> as a worktree off the CURRENT branch (rule 33).

    Resolves the current worktree root (never assumes main) and registers the new
    worktree via scripts/worktree_registry.py.
    """
    root = Path(project_root).resolve()
    top = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    branch = f"goal/{goal_id}-{stamp}"
    wt_path = str(Path(top) / ".worktrees" / "goal" / f"{goal_id}-{stamp}")
    add = subprocess.run(
        ["git", "-C", top, "worktree", "add", "-b", branch, wt_path, "HEAD"],
        capture_output=True, text=True,
    )
    if add.returncode != 0:
        raise RuntimeError(
            f"git worktree add failed for {branch!r}: {add.stderr.strip() or add.stdout.strip()}"
        )
    _register_worktree(top, wt_path, f"goal-{goal_id}")
    _bootstrap_node_modules(top, wt_path)
    return WorktreeHandle(path=wt_path, branch=branch)


def _bootstrap_node_modules(repo_top: str, wt_path: str) -> None:
    """Link installed node deps from the source checkout into the goal worktree.

    A fresh ``git worktree`` has no ``node_modules`` (it is gitignored), so the
    code loops (testing, page-health) and the dashboard type-check verify fail
    with ``runner-missing`` (e.g. ``Cannot find package 'esbuild'``) — a setup
    artifact, not a real finding. The goal branch is created off the source
    checkout's HEAD, so its lockfile matches; symlinking the already-installed
    ``node_modules`` is correct and instant (no reinstall). Best-effort: a link
    failure never aborts the goal — the loop just reports runner-missing as before.
    """
    src_top = Path(repo_top)
    dst_top = Path(wt_path)
    listing = subprocess.run(
        ["git", "-C", repo_top, "ls-files", "*package.json"],
        capture_output=True, text=True, check=False,
    )
    if listing.returncode != 0:
        return
    pkg_dirs = {Path(line).parent for line in listing.stdout.splitlines() if line.strip()}
    for rel_dir in sorted(pkg_dirs):
        src_nm = src_top / rel_dir / "node_modules"
        dst_nm = dst_top / rel_dir / "node_modules"
        if not src_nm.is_dir() or dst_nm.exists():
            continue
        try:
            dst_nm.parent.mkdir(parents=True, exist_ok=True)
            dst_nm.symlink_to(src_nm.resolve(), target_is_directory=True)
        except OSError:
            continue


def _register_worktree(repo_top: str, wt_path: str, name: str) -> None:
    """Best-effort registry write; registration failure never aborts the goal."""
    registry = Path(repo_top) / "scripts" / "worktree_registry.py"
    if not registry.exists():
        return
    subprocess.run(
        ["python3", str(registry), "register", "--path", wt_path, "--name", name],
        capture_output=True, text=True, check=False,
    )
