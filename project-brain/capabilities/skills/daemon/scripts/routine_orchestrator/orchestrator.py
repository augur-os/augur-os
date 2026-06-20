"""Top-level coordinator for ADR-755 routine orchestration."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Iterator, Mapping

try:
    from . import budget, bucket_planner, escalation_queue, fix_phase_mechanical
    from . import scan_phase, session_detect, subagent_dispatch
    from .trust import TrustLedger
except ImportError:
    from routine_orchestrator import (  # type: ignore[no-redef]
        budget,
        bucket_planner,
        escalation_queue,
        fix_phase_mechanical,
        scan_phase,
        session_detect,
        subagent_dispatch,
    )
    from routine_orchestrator.trust import TrustLedger  # type: ignore[no-redef]


EventSink = Callable[[dict[str, Any]], None] | list[dict[str, Any]] | None


@dataclass(frozen=True)
class OrchestrateResult:
    """Summary of one orchestrator run."""

    loop_name: str
    findings: list[dict[str, Any]]
    mechanical_applied: list[Any] = field(default_factory=list)
    mechanical_failed: list[Any] = field(default_factory=list)
    deferred: list[dict[str, Any]] = field(default_factory=list)
    design_gate_findings: list[dict[str, Any]] = field(default_factory=list)
    dispatched: list[subagent_dispatch.DispatchResult] = field(default_factory=list)
    enqueued: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "findings": len(self.findings),
            "mechanical_applied": len(self.mechanical_applied),
            "mechanical_failed": len(self.mechanical_failed),
            "deferred": len(self.deferred),
            "design_gate_findings": len(self.design_gate_findings),
            "dispatched": len(self.dispatched),
            "enqueued": len(self.enqueued),
        }


def orchestrate_run(
    loop_name: str,
    *,
    project_root: Path | str | None = None,
    runtime_dir: Path | str | None = None,
    state_dir: Path | str | None = None,
    commands: Iterable[Any] | Mapping[str, Any] | None = None,
    trust_config: dict[str, Any] | None = None,
    session: Any | None = None,
    task_invoker: subagent_dispatch.TaskInvoker | None = None,
    verify_runner: fix_phase_mechanical.VerifyRunner | None = None,
    commit_runner: fix_phase_mechanical.CommitRunner | None = None,
    event_sink: EventSink = None,
    difficulty: int = 0,
    loop_config: dict[str, Any] | None = None,
    shared_snapshot: dict[str, Any] | None = None,
    client: str | None = None,
    verify_command: str | None = None,
) -> OrchestrateResult:
    """Run scan, mechanical fixes, semantic dispatch/escalation, and design deferral."""
    root = Path(project_root) if project_root is not None else _find_project_root()
    runtime = Path(runtime_dir) if runtime_dir is not None else _default_runtime_dir()
    trust_state_dir = Path(state_dir) if state_dir is not None else runtime / "adaptive"
    session_ctx = session or session_detect.detect()
    resolved_commands = _resolve_command_entries(loop_name, root, commands)
    command_lookup = _commands_by_name(resolved_commands)
    local_events: list[dict[str, Any]] = []

    with _ledger_run(
        loop_name,
        timeout_s=getattr(session_ctx, "timeout", None),
        runtime_dir=runtime,
    ) as job:
        pending_entries, stale_pending_entries = _partition_pending_entries(
            escalation_queue.dequeue(runtime_dir=runtime),
            loop_name=loop_name,
            command_lookup=command_lookup,
            project_root=root,
        )
        for stale_entry in stale_pending_entries:
            escalation_queue.complete(str(stale_entry.get("id", "")), runtime_dir=runtime)
        pending_findings = [
            dict(entry.get("finding", {}))
            for entry in pending_entries
            if isinstance(entry.get("finding"), dict)
        ]

        _phase(job, event_sink, local_events, "scan")
        findings = scan_phase.scan_loop(
            loop_name,
            project_root=root,
            commands=resolved_commands,
            session=session_ctx,
            difficulty=difficulty,
            loop_config=loop_config,
            shared_snapshot=shared_snapshot,
            client=client,
        )
        all_findings = _merge_findings(pending_findings, findings)

        _phase(job, event_sink, local_events, "mechanical")
        mechanical = fix_phase_mechanical.apply_mechanical_fixes(
            all_findings,
            commands=resolved_commands,
            project_root=root,
            state_dir=trust_state_dir,
            trust_config=trust_config,
            verify_command=verify_command,
            verify_runner=verify_runner,
            commit_runner=commit_runner,
            difficulty=difficulty,
            loop_config=loop_config,
            shared_snapshot=shared_snapshot,
            client=client,
        )

        _phase(job, event_sink, local_events, "bucket")
        bucket_plan = bucket_planner.plan_dispatch(
            mechanical.deferred,
            loop_name=loop_name,
            config=_planner_config(trust_config),
            project_root=root,
        )

        dispatched: list[subagent_dispatch.DispatchResult] = []
        enqueued: list[dict[str, Any]] = []

        if bucket_plan.buckets:
            if not subagent_dispatch.dispatch_available(
                session_ctx, task_invoker=task_invoker
            ):
                _phase(job, event_sink, local_events, "escalate")
                pending_keys = {_finding_key(finding) for finding in pending_findings}
                for finding in _bucket_findings(bucket_plan.buckets):
                    if _finding_key(finding) in pending_keys:
                        continue
                    enqueued.append(
                        escalation_queue.enqueue(
                            _scoped_finding(finding, project_root=root),
                            runtime_dir=runtime,
                        )
                    )
            else:
                _phase(job, event_sink, local_events, "dispatch")
                for finding_bucket in bucket_plan.buckets:
                    command = command_lookup[finding_bucket.auto_command]
                    dispatch_budget = budget.Budget.default(
                        loop_name,
                        kind="llm",
                        project_root=root,
                    )
                    dispatch_result = subagent_dispatch.dispatch_bucket(
                        finding_bucket,
                        command,
                        session_ctx,
                        dispatch_budget,
                        project_root=root,
                        verify_command=verify_command,
                        task_invoker=task_invoker,
                    )
                    dispatched.append(dispatch_result)
                    _record_dispatch_trust(
                        trust_state_dir,
                        trust_config,
                        command_lookup,
                        loop_name,
                        finding_bucket.auto_command,
                        dispatch_result,
                    )
                    if dispatch_result.status == "success":
                        _complete_pending_for_bucket(
                            pending_entries,
                            finding_bucket,
                            runtime,
                        )

        _phase(job, event_sink, local_events, "complete")
        return OrchestrateResult(
            loop_name=loop_name,
            findings=all_findings,
            mechanical_applied=mechanical.applied,
            mechanical_failed=mechanical.failed,
            deferred=mechanical.deferred,
            design_gate_findings=bucket_plan.design_gate_findings,
            dispatched=dispatched,
            enqueued=enqueued,
            events=local_events,
        )


def fix_one_command(
    loop_name: str,
    *,
    command: Any,
    findings: Iterable[dict[str, Any]],
    project_root: Path | str | None = None,
    runtime_dir: Path | str | None = None,
    state_dir: Path | str | None = None,
    trust_config: dict[str, Any] | None = None,
    session: Any | None = None,
    task_invoker: subagent_dispatch.TaskInvoker | None = None,
    verify_runner: fix_phase_mechanical.VerifyRunner | None = None,
    commit_runner: fix_phase_mechanical.CommitRunner | None = None,
    event_sink: EventSink = None,
    difficulty: int = 0,
    loop_config: dict[str, Any] | None = None,
    shared_snapshot: dict[str, Any] | None = None,
    client: str | None = None,
    verify_command: str | None = None,
) -> OrchestrateResult:
    """Run the orchestrator fix phases for one already-scanned command."""
    root = Path(project_root) if project_root is not None else _find_project_root()
    runtime = Path(runtime_dir) if runtime_dir is not None else _default_runtime_dir()
    trust_state_dir = Path(state_dir) if state_dir is not None else runtime / "adaptive"
    session_ctx = session or session_detect.detect(trust_config)
    resolved_commands = _resolve_command_entries(loop_name, root, [command])
    if not resolved_commands:
        resolved_commands = [command]
    command_lookup = _commands_by_name(resolved_commands)
    trust_state_config = _trust_config_for_commands(
        trust_config,
        command_lookup,
        loop_name,
    )
    command_name = str(getattr(command, "name", ""))
    local_events: list[dict[str, Any]] = []
    current_findings = [dict(finding) for finding in findings]

    for finding in current_findings:
        finding.setdefault("auto_command", command_name)
        finding.setdefault("loop", loop_name)

    with _ledger_run(
        loop_name,
        timeout_s=getattr(session_ctx, "timeout", None),
        runtime_dir=runtime,
    ) as job:
        _phase(job, event_sink, local_events, "mechanical")
        mechanical = fix_phase_mechanical.apply_mechanical_fixes(
            current_findings,
            commands=resolved_commands,
            project_root=root,
            state_dir=trust_state_dir,
            trust_config=trust_state_config,
            verify_command=verify_command,
            verify_runner=verify_runner,
            commit_runner=commit_runner,
            difficulty=difficulty,
            loop_config=loop_config,
            shared_snapshot=shared_snapshot,
            client=client,
        )

        _phase(job, event_sink, local_events, "bucket")
        bucket_plan = bucket_planner.plan_dispatch(
            mechanical.deferred,
            loop_name=loop_name,
            config=_planner_config(trust_state_config),
            project_root=root,
        )

        dispatched: list[subagent_dispatch.DispatchResult] = []
        enqueued: list[dict[str, Any]] = []

        if bucket_plan.buckets:
            if not subagent_dispatch.dispatch_available(
                session_ctx, task_invoker=task_invoker
            ):
                _phase(job, event_sink, local_events, "escalate")
                pending_entries = escalation_queue.load(runtime_dir=runtime)
                pending_keys = {
                    _finding_key(entry.get("finding", {}))
                    for entry in pending_entries
                    if isinstance(entry.get("finding"), dict)
                }
                for finding in _bucket_findings(bucket_plan.buckets):
                    if _finding_key(finding) in pending_keys:
                        continue
                    enqueued.append(
                        escalation_queue.enqueue(
                            _scoped_finding(finding, project_root=root),
                            runtime_dir=runtime,
                        )
                    )
            else:
                _phase(job, event_sink, local_events, "dispatch")
                for finding_bucket in bucket_plan.buckets:
                    dispatch_command = command_lookup[finding_bucket.auto_command]
                    dispatch_budget = budget.Budget.default(
                        loop_name,
                        kind="llm",
                        project_root=root,
                    )
                    dispatch_result = subagent_dispatch.dispatch_bucket(
                        finding_bucket,
                        dispatch_command,
                        session_ctx,
                        dispatch_budget,
                        project_root=root,
                        verify_command=verify_command,
                        task_invoker=task_invoker,
                    )
                    dispatched.append(dispatch_result)
                    _record_dispatch_trust(
                        trust_state_dir,
                        trust_state_config,
                        command_lookup,
                        loop_name,
                        finding_bucket.auto_command,
                        dispatch_result,
                    )

        _phase(job, event_sink, local_events, "complete")
        return OrchestrateResult(
            loop_name=loop_name,
            findings=current_findings,
            mechanical_applied=mechanical.applied,
            mechanical_failed=mechanical.failed,
            deferred=mechanical.deferred,
            design_gate_findings=bucket_plan.design_gate_findings,
            dispatched=dispatched,
            enqueued=enqueued,
            events=local_events,
        )


def scan_only(
    loop_name: str,
    *,
    project_root: Path | str | None = None,
    runtime_dir: Path | str | None = None,
    state_dir: Path | str | None = None,
    commands: Iterable[Any] | Mapping[str, Any] | None = None,
    trust_config: dict[str, Any] | None = None,
    verify_runner: fix_phase_mechanical.VerifyRunner | None = None,
    commit_runner: fix_phase_mechanical.CommitRunner | None = None,
    event_sink: EventSink = None,
    difficulty: int = 0,
    loop_config: dict[str, Any] | None = None,
    shared_snapshot: dict[str, Any] | None = None,
    client: str | None = None,
    verify_command: str | None = None,
) -> OrchestrateResult:
    """Run scan plus mechanical fixes without semantic dispatch or queue writes."""
    no_session = session_detect.OrchestratorSessionContext(has_llm=False, subagent_surface=None)
    root = Path(project_root) if project_root is not None else _find_project_root()
    runtime = Path(runtime_dir) if runtime_dir is not None else _default_runtime_dir()
    trust_state_dir = Path(state_dir) if state_dir is not None else runtime / "adaptive"
    resolved_commands = _resolve_command_entries(loop_name, root, commands)
    local_events: list[dict[str, Any]] = []

    with _ledger_run(loop_name, timeout_s=None, runtime_dir=runtime) as job:
        _phase(job, event_sink, local_events, "scan")
        findings = scan_phase.scan_loop(
            loop_name,
            project_root=root,
            commands=resolved_commands,
            session=no_session,
            difficulty=difficulty,
            loop_config=loop_config,
            shared_snapshot=shared_snapshot,
            client=client,
        )
        _phase(job, event_sink, local_events, "mechanical")
        mechanical = fix_phase_mechanical.apply_mechanical_fixes(
            findings,
            commands=resolved_commands,
            project_root=root,
            state_dir=trust_state_dir,
            trust_config=trust_config,
            verify_command=verify_command,
            verify_runner=verify_runner,
            commit_runner=commit_runner,
            difficulty=difficulty,
            loop_config=loop_config,
            shared_snapshot=shared_snapshot,
            client=client,
        )
        _phase(job, event_sink, local_events, "complete")
        return OrchestrateResult(
            loop_name=loop_name,
            findings=findings,
            mechanical_applied=mechanical.applied,
            mechanical_failed=mechanical.failed,
            deferred=mechanical.deferred,
            events=local_events,
        )


def _record_dispatch_trust(
    state_dir: Path,
    trust_config: dict[str, Any] | None,
    commands: Mapping[str, Any],
    loop_name: str,
    command_name: str,
    dispatch_result: subagent_dispatch.DispatchResult,
) -> None:
    ledger = TrustLedger(trust_config or _build_trust_config(commands, loop_name), state_dir=state_dir)
    if dispatch_result.status == "success":
        ledger.record_success(loop_name, command_name)
    else:
        ledger.record_failure(loop_name, command_name)


def _build_trust_config(commands: Mapping[str, Any], loop_name: str) -> dict[str, Any]:
    return {
        "loops": {
            loop_name: {
                "enabled": True,
                "trigger": "manual",
                "budget": max(1, len(commands)),
                "budget_growth_rate": 1,
                "categories": {
                    name: {
                        "enabled": True,
                        "trust": 0.0,
                        "tier": int(getattr(command, "tier", 0) or 0),
                    }
                    for name, command in commands.items()
                },
            }
        }
    }


def _trust_config_for_commands(
    trust_config: dict[str, Any] | None,
    commands: Mapping[str, Any],
    loop_name: str,
) -> dict[str, Any]:
    if not isinstance(trust_config, dict):
        return _build_trust_config(commands, loop_name)
    loops = trust_config.get("loops")
    if not isinstance(loops, dict):
        return _build_trust_config(commands, loop_name)
    loop_cfg = loops.get(loop_name)
    if not isinstance(loop_cfg, dict):
        return _build_trust_config(commands, loop_name)
    categories = loop_cfg.get("categories", {})
    if not isinstance(categories, dict):
        return _build_trust_config(commands, loop_name)
    if all(name in categories for name in commands):
        return trust_config
    return _build_trust_config(commands, loop_name)


def _commands_by_name(commands: Iterable[Any] | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(commands, Mapping):
        values = commands.values()
    else:
        values = commands
    return {
        str(getattr(command, "name", "") or getattr(getattr(command, "module", None), "name", "")): command
        for command in values
    }


def _resolve_command_entries(
    loop_name: str,
    project_root: Path,
    commands: Iterable[Any] | Mapping[str, Any] | None,
) -> list[Any]:
    if commands is None:
        return scan_phase.discover_loop_commands(loop_name, project_root)
    if isinstance(commands, Mapping):
        return list(commands.values())
    return list(commands)


def _partition_pending_entries(
    pending_entries: Iterable[dict[str, Any]],
    *,
    loop_name: str,
    command_lookup: Mapping[str, Any],
    project_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    relevant: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    known_commands = set(command_lookup)
    for entry in pending_entries:
        finding = entry.get("finding")
        if not isinstance(finding, dict):
            continue
        scope = _pending_scope(finding, project_root=project_root)
        if scope == "stale":
            stale.append(entry)
            continue
        if scope == "foreign":
            continue
        finding_loop = str(finding.get("loop", "") or "")
        auto_command = str(finding.get("auto_command", "") or "")
        if finding_loop and finding_loop != loop_name:
            continue
        if auto_command and auto_command not in known_commands:
            continue
        if finding_loop == loop_name or auto_command in known_commands:
            relevant.append(entry)
    return relevant, stale


def _bucket_findings(buckets: Iterable[bucket_planner.FindingBucket]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for finding_bucket in buckets:
        findings.extend(finding_bucket.findings)
    return findings


def _merge_findings(
    pending_findings: Iterable[dict[str, Any]],
    scanned_findings: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for finding in [*pending_findings, *scanned_findings]:
        key = _finding_key(finding)
        if key in seen:
            continue
        seen.add(key)
        merged.append(finding)
    return merged


def _finding_key(finding: Mapping[str, Any]) -> tuple[str, str, str]:
    auto_command = str(finding.get("auto_command", ""))
    path = str(
        finding.get("primary_file")
        or finding.get("path")
        or finding.get("file_path")
        or finding.get("file")
        or ""
    )
    detail = str(finding.get("detail") or finding.get("message") or finding.get("kind") or "")
    return (auto_command, path, detail)


def _complete_pending_for_bucket(
    pending_entries: Iterable[dict[str, Any]],
    finding_bucket: bucket_planner.FindingBucket,
    runtime_dir: Path,
) -> None:
    bucket_keys = {_finding_key(finding) for finding in finding_bucket.findings}
    for entry in pending_entries:
        finding = entry.get("finding")
        if not isinstance(finding, dict):
            continue
        if _finding_key(finding) in bucket_keys:
            escalation_queue.complete(str(entry.get("id", "")), runtime_dir=runtime_dir)


def _scoped_finding(finding: Mapping[str, Any], *, project_root: Path) -> dict[str, Any]:
    scoped = dict(finding)
    scoped.setdefault("project_root", str(project_root.resolve()))
    return scoped


def _pending_scope(
    finding: Mapping[str, Any],
    *,
    project_root: Path,
) -> str:
    current_root = project_root.resolve()
    scoped_root = _coerce_absolute_path(finding.get("project_root"))
    if scoped_root is not None and scoped_root != current_root:
        return "foreign"

    saw_foreign_worktree = False
    for ref in _finding_worktree_refs(finding):
        if _path_is_within(ref, current_root):
            if not ref.exists():
                return "stale"
            continue
        if not ref.exists():
            return "stale"
        saw_foreign_worktree = True
    return "foreign" if saw_foreign_worktree else "current"


def _finding_worktree_refs(finding: Mapping[str, Any]) -> list[Path]:
    refs: list[Path] = []
    for key in ("primary_file", "path", "file_path", "file", "project_root"):
        ref = _coerce_absolute_path(finding.get(key))
        if ref is not None and ".worktrees" in ref.parts:
            refs.append(ref)
    for key in ("detail", "error", "message"):
        text = finding.get(key)
        if not isinstance(text, str):
            continue
        for token in re.findall(r"/[^\s\"'`]+", text):
            ref = _coerce_absolute_path(token.rstrip(".,:;)]}"))
            if ref is not None and ".worktrees" in ref.parts:
                refs.append(ref)
    return refs


def _coerce_absolute_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.startswith("/"):
        return None
    return Path(value).expanduser().resolve(strict=False)


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _planner_config(trust_config: dict[str, Any] | None) -> dict[str, Any] | None:
    return trust_config if isinstance(trust_config, dict) and "loops" in trust_config else None


def _phase(job: Any, event_sink: EventSink, local_events: list[dict[str, Any]], phase: str) -> None:
    event = {"phase": phase}
    local_events.append(event)
    if event_sink is not None:
        if isinstance(event_sink, list):
            event_sink.append(event)
        else:
            event_sink(event)
    if hasattr(job, "phase"):
        job.phase(phase)


@contextmanager
def _ledger_run(
    loop_name: str,
    *,
    timeout_s: int | None,
    runtime_dir: Path | None = None,
) -> Iterator[Any]:
    try:
        import sys

        scripts_dir = Path(__file__).resolve().parents[1]
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        if runtime_dir is not None:
            from job_ledger import job_record

            job_record.jobs_dir = lambda: _jobs_dir(runtime_dir)  # type: ignore[assignment]
        from job_ledger.ledger import run as ledger_run
    except Exception:
        yield _NullLedgerJob()
        return
    with ledger_run(
        kind="routine-orchestrator",
        name=f"routine:{loop_name}",
        args={"loop": loop_name},
        timeout_s=timeout_s,
        submitter="routine-orchestrator",
    ) as job:
        yield job


def _jobs_dir(runtime_dir: Path) -> Path:
    jobs = runtime_dir / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    return jobs


class _NullLedgerJob:
    def phase(self, name: str) -> None:
        del name


def _default_runtime_dir() -> Path:
    from src.config.paths import get_runtime_dir

    return Path(get_runtime_dir())


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in (current.parent, *current.parents):
        if (parent / "src").is_dir() and (parent / "config").is_dir():
            return parent
    return Path.cwd()


__all__ = ["OrchestrateResult", "fix_one_command", "orchestrate_run", "scan_only"]
