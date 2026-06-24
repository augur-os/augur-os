"""Client-aware subagent dispatch for ADR-755 routine orchestration."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from src.lib.ops_protocol import OpsContext, SessionContext

try:
    from .budget import Budget
    from .bucket_planner import FindingBucket
    from .session_detect import get_subagent_surface
except ImportError:
    from routine_orchestrator.budget import Budget  # type: ignore[no-redef]
    from routine_orchestrator.bucket_planner import FindingBucket  # type: ignore[no-redef]
    from routine_orchestrator.session_detect import get_subagent_surface  # type: ignore[no-redef]


CLIENT_SUBAGENT_MAP: dict[str, str] = {
    "routine-codebase": "general-purpose",
    "routine-vault": "general-purpose",
    "routine-security": "security-reviewer",
}

TaskInvoker = Callable[..., Any]
InlineRunner = Callable[..., Any]

# TODO_CLEANUP(ADR-793): the routines goal path no longer uses the Python Task invoker — the inline-session client is the invoker. Retained for tiered/headless dispatch and tests; remove if those paths drop it.
_TASK_INVOKER: TaskInvoker | None = None

# Minimum toolset a fix subagent needs to read, edit, write, search, and verify.
# Used as the fallback when a command declares no allowed_tools (or an empty list),
# because an empty grant makes the dispatched subagent completely toothless.
DEFAULT_FIX_TOOLS: tuple[str, ...] = ("Read", "Edit", "Write", "Bash", "Grep", "Glob")


class NoSessionAvailable(RuntimeError):
    """Raised when semantic dispatch is attempted outside a client session."""


class BudgetExceeded(RuntimeError):
    """Raised when a bucket dispatch has no remaining budget."""


@dataclass(frozen=True)
class DispatchResult:
    """Structured outcome from a client subagent or degraded inline dispatch."""

    status: str
    commit_hash: str | None = None
    diagnostic: str = ""
    budget_consumed: int = 0
    raw_result: Any = None


def dispatch_available(
    session_context: SessionContext,
    *,
    task_invoker: TaskInvoker | None = None,
) -> bool:
    """Return True when the detected surface can actually dispatch a bucket now.

    Surface detection (``session_detect``) only proves a client *environment*
    (e.g. ``CLAUDECODE=1`` plus a ``claude`` binary on PATH). It does not prove
    a usable in-process invoker exists. A headless ``aug a-loops run`` subprocess
    inherits that environment but has no Task tool, so the claude-code surface is
    detected while ``_TASK_INVOKER`` stays ``None``. Callers must gate the
    dispatch-vs-escalate decision on this (not on surface presence alone) so the
    no-invoker case escalates to the queue instead of raising NoSessionAvailable.
    """
    surface = get_subagent_surface(session_context)
    if surface is None:
        return False
    if surface == "claude-code":
        return (task_invoker or _TASK_INVOKER) is not None
    if surface in {"codex", "degraded-inline"}:
        return True
    # gemini and any unsupported surface cannot dispatch in production -> escalate.
    return False


def dispatch_bucket(
    bucket: FindingBucket,
    auto_command: Any,
    session_context: SessionContext,
    budget: Budget,
    *,
    project_root: Path | str | None = None,
    verify_command: str | None = None,
    task_invoker: TaskInvoker | None = None,
    inline_runner: InlineRunner | None = None,
) -> DispatchResult:
    """Dispatch one semantic bucket through the active client's subagent surface."""
    if not budget.check_remaining():
        raise BudgetExceeded("subagent budget exhausted before dispatch")

    surface = get_subagent_surface(session_context)
    if surface is None:
        raise NoSessionAvailable("no session subagent surface available")

    if surface == "claude-code":
        return _dispatch_claude_code(
            bucket,
            auto_command,
            session_context,
            budget,
            verify_command=verify_command,
            task_invoker=task_invoker,
        )

    if surface == "codex":
        return _dispatch_codex_exec(
            bucket,
            auto_command,
            session_context,
            budget,
            project_root=project_root,
            verify_command=verify_command,
        )

    if surface == "gemini":
        raise NotImplementedError(
            f"{surface} subagent dispatch requires follow-up validation before production use"
        )

    if surface == "degraded-inline":
        return _dispatch_degraded_inline(
            bucket,
            auto_command,
            session_context,
            budget,
            project_root=project_root,
            inline_runner=inline_runner,
        )

    raise NoSessionAvailable(f"unsupported subagent surface: {surface}")


# TODO_CLEANUP(ADR-793): the routines goal path no longer uses the Python Task invoker — the inline-session client is the invoker. Retained for tiered/headless dispatch and tests; remove if those paths drop it.
def _dispatch_claude_code(
    bucket: FindingBucket,
    auto_command: Any,
    session_context: SessionContext,
    budget: Budget,
    *,
    verify_command: str | None,
    task_invoker: TaskInvoker | None,
) -> DispatchResult:
    invoker = task_invoker or _TASK_INVOKER
    if invoker is None:
        raise NoSessionAvailable("claude-code Task invoker is not installed")

    budget.consume()
    result = invoker(
        description=_task_description(bucket, auto_command),
        prompt=_task_prompt(bucket, auto_command, budget, verify_command=verify_command),
        subagent_type=_subagent_type(auto_command),
        allowed_tools=_allowed_tools(auto_command),
        session=session_context,
    )
    return _parse_dispatch_result(result, budget_consumed=1)


def _dispatch_degraded_inline(
    bucket: FindingBucket,
    auto_command: Any,
    session_context: SessionContext,
    budget: Budget,
    *,
    project_root: Path | str | None,
    inline_runner: InlineRunner | None,
) -> DispatchResult:
    budget.consume()
    if inline_runner is not None:
        result = inline_runner(
            bucket=bucket,
            auto_command=auto_command,
            session=session_context,
        )
        return _parse_dispatch_result(result, budget_consumed=1)

    module = getattr(auto_command, "module", auto_command)
    fix = getattr(module, "fix", None)
    if not callable(fix):
        return DispatchResult(
            status="failed",
            diagnostic="auto-command has no inline fix callable",
            budget_consumed=1,
        )

    ctx = OpsContext(
        project_root=Path(project_root) if project_root is not None else Path.cwd(),
        dry_run=False,
        session=session_context,
        config=dict(getattr(auto_command, "config", {}) or {}),
    )
    fix_result = fix(ctx, bucket.findings)
    status = "success" if bool(getattr(fix_result, "success", False)) else "failed"
    diagnostic = str(getattr(fix_result, "summary", "") or "")
    commit_hash = getattr(fix_result, "commit_hash", None)
    return DispatchResult(
        status=status,
        commit_hash=str(commit_hash) if commit_hash else None,
        diagnostic=diagnostic,
        budget_consumed=1,
        raw_result=fix_result,
    )


def _dispatch_codex_exec(
    bucket: FindingBucket,
    auto_command: Any,
    session_context: SessionContext,
    budget: Budget,
    *,
    project_root: Path | str | None,
    verify_command: str | None,
) -> DispatchResult:
    cli_path = session_context.cli_path
    if not cli_path:
        raise NoSessionAvailable("codex CLI path is not available for headless dispatch")

    budget.consume()
    root = Path(project_root) if project_root is not None else Path.cwd()
    prompt = _task_prompt(bucket, auto_command, budget, verify_command=verify_command)
    output_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            prefix="routine-codex-dispatch-",
            suffix=".txt",
            delete=False,
        ) as handle:
            output_path = Path(handle.name)

        cmd = [
            cli_path,
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--ephemeral",
            "-C",
            str(root),
            "-o",
            str(output_path),
            prompt,
        ]
        env = os.environ.copy()
        env["CLAUDECODE"] = ""
        env["CLAUDE_CODE"] = ""

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=session_context.timeout,
            cwd=str(root),
            env=env,
            stdin=subprocess.DEVNULL,
        )

        raw_output = ""
        if output_path.exists():
            raw_output = output_path.read_text(encoding="utf-8").strip()
        if not raw_output:
            raw_output = result.stdout.strip()

        if result.returncode != 0:
            diagnostic = (
                result.stderr.strip()
                or raw_output
                or result.stdout.strip()
                or f"codex exec failed with exit {result.returncode}"
            )
            return DispatchResult(
                status="failed",
                diagnostic=diagnostic,
                budget_consumed=1,
                raw_result={
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            )

        if not raw_output:
            return DispatchResult(
                status="failed",
                diagnostic="codex exec produced no final message",
                budget_consumed=1,
                raw_result={
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            )

        return _parse_dispatch_result(raw_output, budget_consumed=1)
    finally:
        if output_path is not None:
            output_path.unlink(missing_ok=True)


def _parse_dispatch_result(result: Any, *, budget_consumed: int) -> DispatchResult:
    payload = _coerce_result_payload(result)
    status = str(payload.get("status") or "failed")
    commit_hash = payload.get("commit_hash")
    diagnostic = str(payload.get("diagnostic") or payload.get("summary") or "")
    return DispatchResult(
        status=status,
        commit_hash=str(commit_hash) if commit_hash else None,
        diagnostic=diagnostic,
        budget_consumed=budget_consumed,
        raw_result=result,
    )


def _coerce_result_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, Mapping):
        return dict(result)
    if isinstance(result, str):
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            return {"status": "failed", "diagnostic": result}
        return payload if isinstance(payload, dict) else {"status": "failed", "diagnostic": result}
    return {
        "status": "success" if bool(getattr(result, "success", False)) else "failed",
        "commit_hash": getattr(result, "commit_hash", None),
        "diagnostic": getattr(result, "diagnostic", None) or getattr(result, "summary", ""),
    }


def _task_description(bucket: FindingBucket, auto_command: Any) -> str:
    return f"{_command_name(auto_command)}: fix {len(bucket.findings)} finding(s)"


def _task_prompt(
    bucket: FindingBucket,
    auto_command: Any,
    budget: Budget,
    *,
    verify_command: str | None,
) -> str:
    payload = {
        "auto_command": _command_name(auto_command),
        "description": _command_description(auto_command),
        "primary_file": bucket.primary_file,
        "findings": bucket.findings,
        "allowed_tools": _allowed_tools(auto_command),
        "budget": {
            "max_turns": budget.max_turns,
            "soft_timeout_s": budget.soft_timeout_s,
            "remaining_turns": max(0, budget.max_turns - budget.consumed_turns),
        },
        "verify_command": verify_command or "",
        "return_json_schema": {
            "status": "success|failed",
            "commit_hash": "str|null",
            "diagnostic": "str",
        },
    }
    return (
        "Apply the fix described by this auto-command bucket. "
        "Use only the allowed tools, verify before reporting success, and return JSON only.\n"
        + json.dumps(payload, indent=2, sort_keys=True)
    )


def _subagent_type(auto_command: Any) -> str:
    owner = str(
        getattr(auto_command, "owner_skill", "")
        or getattr(auto_command, "skill", "")
        or getattr(auto_command, "skill_name", "")
        or _config_value(auto_command, "owner_skill")
        or _config_value(auto_command, "skill")
    )
    return CLIENT_SUBAGENT_MAP.get(owner, "general-purpose")


def _allowed_tools(auto_command: Any) -> list[str]:
    module = getattr(auto_command, "module", auto_command)
    value = (
        getattr(auto_command, "allowed_tools", None)
        or getattr(module, "ALLOWED_TOOLS", None)
        or getattr(module, "allowed_tools", None)
        or _config_value(auto_command, "allowed_tools")
    )
    if value is None:
        tools: list[str] = []
    elif isinstance(value, str):
        tools = [item.strip() for item in value.split(",") if item.strip()]
    else:
        tools = [str(item) for item in value]
    # A fix subagent with no tools cannot read, edit, or verify anything.
    # Fall back to the standard fix toolset when a command declares nothing (None)
    # or an explicitly empty list — the auto-commands the routines goal loop dispatches
    # to declare no allowed_tools, so an empty grant would make them toothless.
    # Commands that declare a non-empty list still win (declared tools are honored exactly).
    return tools or list(DEFAULT_FIX_TOOLS)


def _command_description(auto_command: Any) -> str:
    module = getattr(auto_command, "module", auto_command)
    return str(
        getattr(auto_command, "description", "")
        or getattr(module, "description", "")
        or _config_value(auto_command, "description")
        or ""
    )


def _command_name(auto_command: Any) -> str:
    module = getattr(auto_command, "module", auto_command)
    return str(getattr(auto_command, "name", "") or getattr(module, "name", "auto-command"))


def _config_value(auto_command: Any, key: str) -> Any:
    config = getattr(auto_command, "config", {}) or {}
    return config.get(key) if isinstance(config, Mapping) else None


__all__ = [
    "BudgetExceeded",
    "CLIENT_SUBAGENT_MAP",
    "DEFAULT_FIX_TOOLS",
    "DispatchResult",
    "NoSessionAvailable",
    "dispatch_available",
    "dispatch_bucket",
]
