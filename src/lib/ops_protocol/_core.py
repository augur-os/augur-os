"""
ops_protocol._core — Core data models, Protocol, and shared helpers.

ScanResult, SessionContext, FixResult, OpsCapabilities, OpsExecutionDecision,
OpsContext, OpsCommand protocol, issue helpers, write_report, evolution_gap,
report_only_fix.

Internal use by the ops_protocol package; do not import directly from outside.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum  # noqa: F401 – Enum re-exported via __init__
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from src.config.paths import get_runtime_dir
from src.logging import get_entity_logger

logger = get_entity_logger("lib.ops_protocol._core")

Severity = Literal["info", "warning", "error"]
ScanHealth = Literal["verified", "degraded", "broken"]
SupportedPlatform = Literal["cross_platform", "windows", "macos", "linux"]
WindowsFixMode = Literal["auto_fix", "report_only", "unsupported"]
_SUPPORTED_PLATFORMS = {"cross_platform", "windows", "macos", "linux"}
_WINDOWS_FIX_MODES = {"auto_fix", "report_only", "unsupported"}
IssueKind = Literal[
    "clean",
    "actionable",
    "maintenance",
    "environment",
    "external",
    "scanner-defect",
    "manual",
    "broken",
]
RootCauseType = Literal[
    "repo_bug",
    "scanner_bug",
    "env_runtime",
    "external_dependency",
    "generated_artifact",
    "manual_debt",
    "unknown",
]


@dataclass
class ScanResult:
    """Result of scanning for issues."""

    issues: list[dict] = field(default_factory=list)
    summary: str = ""
    severity: Severity = "info"
    health: ScanHealth = "verified"
    items_scanned: int | None = None
    run_fix_on_clean: bool = False


FixType = Literal["code-fix", "report", "sync", "auto"]


@dataclass
class SessionContext:
    """Runtime environment capabilities — detected by engine at startup."""

    has_tool_access: bool = False  # True = running in agent session (Claude Code, Codex, Gemini)
    has_llm: bool = False  # True = an LLM CLI is available on PATH
    cli_path: str = ""  # Resolved CLI path (empty if none found)
    cli_name: str = ""  # CLI identity: "claude", "gemini", "codex", etc.
    max_turns: int = 20  # From engine config
    timeout: int = 600  # From engine config (seconds)


@dataclass
class FixResult:
    """Result of fixing discovered issues."""

    success: bool = True
    actions: list[dict] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    summary: str = ""
    fix_type: FixType = (
        "auto"  # "code-fix"=real fix, "report"=scan artifact, "sync"=data sync, "auto"=infer from changes
    )


@dataclass(frozen=True)
class OpsCapabilities:
    """Platform and mutation capabilities declared by a scan-fix module."""

    platforms: tuple[SupportedPlatform, ...] = ("cross_platform",)
    windows_fix_mode: WindowsFixMode = "auto_fix"
    skip_reason: str = ""


@dataclass(frozen=True)
class OpsExecutionDecision:
    """Resolved execution behavior for the current platform."""

    run_scan: bool
    allow_fix: bool
    outcome: str
    fix_mode: WindowsFixMode
    skip_reason: str = ""


@dataclass
class OpsContext:
    """Context passed to every scan/fix call."""

    project_root: Path = field(default_factory=lambda: Path.cwd())
    difficulty: int = 0  # 0-4, passed by orchestrator (ignored by CLI)
    dry_run: bool = False  # True = scan only, never fix
    verbose: bool = False  # True = detailed output for CLI
    evolve: bool = False  # ADR-417: True = request self-improvement mode (evolve reports, difficulty bumps)
    config: dict = field(default_factory=dict)  # Per-module config from skill metadata loop config
    loop_config: dict = field(default_factory=dict)  # Engine-level loop config from adaptive_loops.yaml
    shared_snapshot: dict = field(default_factory=dict)  # Optional Phase 3 repo/runtime inventory
    session: SessionContext = field(default_factory=SessionContext)  # Runtime LLM capabilities
    client: str | None = None  # AI client override: "ollama" for --local, None for default


DifficultySpec = dict[int, str]  # {0: "surface check", 1: "content check", ...}


def declare_ops_capabilities(
    *,
    platforms: tuple[SupportedPlatform, ...] = ("cross_platform",),
    windows_fix_mode: WindowsFixMode = "auto_fix",
    skip_reason: str = "",
) -> OpsCapabilities:
    """Helper for scan-fix modules to declare supported platforms."""
    return OpsCapabilities(
        platforms=platforms,
        windows_fix_mode=windows_fix_mode,
        skip_reason=skip_reason,
    )


def coerce_ops_capabilities(capabilities: OpsCapabilities | None) -> OpsCapabilities:
    """Validate module-declared capabilities at the module boundary."""
    if capabilities is None:
        return declare_ops_capabilities()
    if isinstance(capabilities, OpsCapabilities):
        if not isinstance(capabilities.platforms, tuple):
            raise TypeError("OPS_CAPABILITIES.platforms must be a tuple of supported platform names")
        if not capabilities.platforms:
            raise TypeError("OPS_CAPABILITIES.platforms must be non-empty")
        invalid_platforms = [p for p in capabilities.platforms if p not in _SUPPORTED_PLATFORMS]
        if invalid_platforms:
            raise TypeError(
                "OPS_CAPABILITIES.platforms contains unsupported values: " + ", ".join(sorted(invalid_platforms))
            )
        if capabilities.windows_fix_mode not in _WINDOWS_FIX_MODES:
            raise TypeError("OPS_CAPABILITIES.windows_fix_mode must be one of " + ", ".join(sorted(_WINDOWS_FIX_MODES)))
        if not isinstance(capabilities.skip_reason, str):
            raise TypeError("OPS_CAPABILITIES.skip_reason must be a string")
        return capabilities
    raise TypeError(f"OPS_CAPABILITIES must be an OpsCapabilities instance, got {type(capabilities).__name__}")


def _normalize_platform_name(platform_name: str) -> str:
    normalized = platform_name.lower()
    if normalized.startswith(("win", "cygwin", "msys")):
        return "windows"
    if normalized.startswith("darwin"):
        return "macos"
    if normalized.startswith("linux"):
        return "linux"
    return normalized


def resolve_ops_execution(
    capabilities: OpsCapabilities | None,
    *,
    platform_name: str,
    allow_fix: bool,
) -> OpsExecutionDecision:
    """Resolve whether a module should scan/fix on the current platform."""
    caps = coerce_ops_capabilities(capabilities)
    platform = _normalize_platform_name(platform_name)
    supported = "cross_platform" in caps.platforms or platform in caps.platforms

    if not supported:
        return OpsExecutionDecision(
            run_scan=False,
            allow_fix=False,
            outcome="skipped_unsupported",
            fix_mode="unsupported",
            skip_reason=caps.skip_reason,
        )

    if platform == "windows":
        if caps.windows_fix_mode == "unsupported":
            return OpsExecutionDecision(
                run_scan=False,
                allow_fix=False,
                outcome="skipped_unsupported",
                fix_mode="unsupported",
                skip_reason=caps.skip_reason,
            )
        if caps.windows_fix_mode == "report_only":
            return OpsExecutionDecision(
                run_scan=True,
                allow_fix=False,
                outcome="report-only",
                fix_mode="report_only",
                skip_reason=caps.skip_reason,
            )

    return OpsExecutionDecision(
        run_scan=True,
        allow_fix=allow_fix,
        outcome="ran",
        fix_mode="auto_fix",
        skip_reason=caps.skip_reason,
    )


def issue_fingerprint(
    category: str,
    kind: IssueKind = "actionable",
    path: str = "",
    detail: str = "",
) -> str:
    """Generate a stable fingerprint for recurring issue tracking."""
    normalized_path = str(path).strip().lower()
    normalized_detail = " ".join(str(detail).strip().lower().split())
    payload = f"{category}:{kind}:{normalized_path}:{normalized_detail}"
    return hashlib.sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def make_issue(
    *,
    category: str,
    detail: str,
    path: str = "",
    kind: IssueKind = "actionable",
    root_cause_type: RootCauseType = "unknown",
    fixability: str = "unknown",
    fingerprint: str | None = None,
    **extra: object,
) -> dict:
    """Create an issue dict with Phase 1 metadata."""
    issue = {
        "category": category,
        "kind": kind,
        "root_cause_type": root_cause_type,
        "fixability": fixability,
        "detail": detail,
        "path": path,
    }
    issue["fingerprint"] = fingerprint or issue_fingerprint(
        category=category,
        kind=kind,
        path=path,
        detail=detail,
    )
    issue.update(extra)
    return issue


@runtime_checkable
class OpsCommand(Protocol):
    """Protocol that every auto-* command module must implement."""

    name: str

    def scan(self, ctx: OpsContext) -> ScanResult: ...
    def fix(self, ctx: OpsContext, issues: list[dict]) -> FixResult: ...


def validate_ops_module(module: object) -> bool:
    """Check if a module has the required scan/fix functions for OpsCommand protocol."""
    has_name = hasattr(module, "name") and isinstance(getattr(module, "name"), str)
    has_scan = callable(getattr(module, "scan", None))
    has_fix = callable(getattr(module, "fix", None))
    return has_name and has_scan and has_fix


def write_report(ctx: OpsContext, filename: str, data: dict) -> Path:
    """Write a JSON report to the external runtime state reports directory."""
    report_dirs = [
        get_runtime_dir() / "reports",
    ]
    last_error: OSError | None = None
    for report_dir in report_dirs:
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / filename
            report_path.write_text(json.dumps(data, indent=2))
            return report_path
        except OSError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise OSError("No writable report directory available")


def clear_report(filename: str) -> None:
    """Remove a stale JSON report from the external runtime state reports directory."""
    report_path = get_runtime_dir() / "reports" / filename
    try:
        report_path.unlink()
    except FileNotFoundError:
        return


def evolution_gap(detail: str, category: str = "evolution") -> dict:
    """Create an evolution gap issue."""
    return make_issue(
        category=category,
        detail=detail,
        kind="maintenance",
        root_cause_type="manual_debt",
        fixability="manual",
    )


def report_only_fix(
    ctx: OpsContext,
    report_name: str,
    issues: list[dict],
    noun: str = "issue",
) -> FixResult:
    """Standard fix() for observation-only verticals that just write a report."""
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} {noun}(s)")
    report_path = write_report(ctx, report_name, {"issues": issues})
    return FixResult(
        success=True,
        actions=[{"report": str(report_path)}],
        summary=f"{noun.capitalize()} report written with {len(issues)} {noun}(s)",
    )


def make_test_ctx(tmp_path: Path, **overrides: object) -> OpsContext:
    """Create an OpsContext for tests. Shared factory to avoid duplication."""
    defaults: dict = {"project_root": tmp_path, "difficulty": 0, "dry_run": False}
    defaults.update(overrides)
    return OpsContext(**defaults)
