"""Unified error pattern registry for self-heal scanner and classifier (ADR-185).

Single source of truth for all error patterns. The scanner uses patterns for
log matching, the classifier uses them for pre-classification, and the router
uses shell_fix for deterministic auto-fixes.

Previously, patterns were split across:
- SHELL_ACTIONS in classifier.py (auto-fix recipes)
- SEVERITY_TIERS in classifier.py (pre-classification)
These are now unified into a single PATTERNS list with derived views.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Constants ────────────────────────────────────────────────────────────────

MAX_NEW_LINES_PER_FILE = 100
"""Maximum new lines to process per file per scan cycle."""

MAX_MESSAGE_LENGTH = 300
"""Truncation limit for error messages stored in findings."""

WATERMARK_FILENAME = "self_heal_watermarks.json"
"""Filename for watermark state (stored under RUNTIME_DIR)."""


# ── ErrorPattern dataclass ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ErrorPattern:
    """A single error pattern with classification and optional auto-fix.

    Attributes:
        regex: Compiled regex to match against log lines.
        tier: Priority tier — "dismiss", "transient", or "actionable".
              Evaluated in order: dismiss first, then transient, then actionable.
        severity: Classification severity — "transient", "low", "medium", "high", "critical".
        category: Error category — "runtime", "integration", "infrastructure", "ux", "performance".
        shell_fix: Optional shell command for deterministic auto-fix (no LLM needed).
        fix_description: Human-readable description of the fix (for shell_fix).
        description: What this pattern detects (for documentation).
    """
    regex: re.Pattern
    tier: str
    severity: str
    category: str
    shell_fix: Optional[list[str]] = field(default=None, repr=False)
    fix_description: str = ""
    description: str = ""


# ── Unified pattern registry ────────────────────────────────────────────────
# All patterns in one list. Tier evaluation order (dismiss → transient →
# actionable) is enforced by get_tier_patterns(), not by list position.

PATTERNS: list[ErrorPattern] = [
    # ═══════════════════════════════════════════════════════════════════════
    # DISMISS TIER — INFO-level, mock clients, HMR noise, permissions.
    # Not errors. Skip immediately.
    # ═══════════════════════════════════════════════════════════════════════

    ErrorPattern(
        regex=re.compile(r"\(INFO\)\s*$"),
        tier="dismiss", severity="transient", category="runtime",
        description="INFO-level log messages",
    ),
    ErrorPattern(
        regex=re.compile(r"LLM (?:evaluation|ranking) failed.*\(WARNING\)\s*$"),
        tier="dismiss", severity="transient", category="runtime",
        description="WARNING-level LLM retry/fallback from memory search",
    ),
    ErrorPattern(
        regex=re.compile(r"(?:Transient )?API error.*retrying.*\(WARNING\)\s*$"),
        tier="dismiss", severity="transient", category="runtime",
        description="Transient API retry warning",
    ),
    ErrorPattern(
        regex=re.compile(r"API error.*after \d+ attempts.*\(WARNING\)\s*$"),
        tier="dismiss", severity="transient", category="runtime",
        description="API error after retries warning",
    ),
    ErrorPattern(
        regex=re.compile(r"\[MagicMock\]", re.IGNORECASE),
        tier="dismiss", severity="transient", category="runtime",
        description="MagicMock client errors — test double, not a code bug",
    ),
    ErrorPattern(
        regex=re.compile(r"os error 2\b|rg:.*No such file", re.IGNORECASE),
        tier="dismiss", severity="transient", category="runtime",
        description="Ripgrep / OS-level file access errors",
    ),
    ErrorPattern(
        regex=re.compile(r"HMR.*failed|Fast Refresh|hot.*reload.*error", re.IGNORECASE),
        tier="dismiss", severity="transient", category="runtime",
        description="HMR / hot reload noise",
    ),
    ErrorPattern(
        regex=re.compile(r"No link element found for chunk.*\.css", re.IGNORECASE),
        tier="dismiss", severity="transient", category="runtime",
        description="Turbopack HMR CSS chunk hash rotation",
    ),
    ErrorPattern(
        regex=re.compile(r"Failed to fetch RSC payload", re.IGNORECASE),
        tier="dismiss", severity="transient", category="runtime",
        description="Next.js RSC payload fetch miss during HMR recompile",
    ),
    ErrorPattern(
        regex=re.compile(r"next.*warning|experimental.*feature|deprecat", re.IGNORECASE),
        tier="dismiss", severity="low", category="ux",
        description="Next.js build warnings, not code bugs",
    ),
    ErrorPattern(
        regex=re.compile(r"unexpected argument list|EPERM|permission denied", re.IGNORECASE),
        tier="dismiss", severity="transient", category="runtime",
        description="Filesystem permission errors — user must fix",
    ),

    # ═══════════════════════════════════════════════════════════════════════
    # TRANSIENT TIER — Turbopack cache, network, port conflicts, resource health.
    # Runtime state, not code bugs, but worth tracking.
    # ═══════════════════════════════════════════════════════════════════════

    ErrorPattern(
        regex=re.compile(
            r"TurbopackInternalError|Turbopack.*panic|Turbopack.*corrupted"
            r"|Unable to open static sorted file"
            r"|Next\.js.*package not found"
            r"|ENOENT.*(?:prerender|app-paths|build)-manifest",
            re.IGNORECASE,
        ),
        tier="transient", severity="transient", category="runtime",
        shell_fix=[
            "bash", "-c",
            "rm -rf apps/dashboard/.next/dev apps/dashboard/.next/cache "
            "&& PROJ=$(python3 -c \"import yaml; print(yaml.safe_load(open('project.yaml')).get('name','Augur').lower())\" 2>/dev/null || echo augur) && launchctl kickstart -k gui/$(id -u)/com.${PROJ}.dashboard 2>/dev/null; true",
        ],
        fix_description="Clear corrupted Turbopack dev cache and restart dashboard",
        description="Turbopack cache corruption",
    ),
    ErrorPattern(
        regex=re.compile(
            r"already running|PID conflict|lock file|port.*in use|address already in use",
            re.IGNORECASE,
        ),
        tier="transient", severity="transient", category="runtime",
        description="Process/port conflicts — runtime state",
    ),
    ErrorPattern(
        regex=re.compile(
            r"network timeout|DNS resolution|ConnectionRefused|ConnectionReset",
            re.IGNORECASE,
        ),
        tier="transient", severity="transient", category="runtime",
        description="Network issues — transient",
    ),
    ErrorPattern(
        regex=re.compile(r"resource:turbopack_cache_bloat"),
        tier="transient", severity="high", category="performance",
        shell_fix=["bash", "-c", "rm -rf apps/dashboard/.next"],
        fix_description="Clear bloated .next cache directory",
        description="Turbopack cache bloat resource health finding",
    ),
    ErrorPattern(
        regex=re.compile(r"resource:next_dev_cpu_thrash"),
        tier="transient", severity="medium", category="performance",
        description="Next.js dev server CPU thrash",
    ),
    ErrorPattern(
        regex=re.compile(r"resource:next_dev_memory_bloat"),
        tier="transient", severity="medium", category="performance",
        description="Next.js dev server memory bloat",
    ),

    # Shell-fix-only: Next.js package not found — matches transient Turbopack regex
    # but has its own distinct fix command (pnpm install vs cache clear).
    ErrorPattern(
        regex=re.compile(r"Next\.js.*package not found|Cannot find module.*next", re.IGNORECASE),
        tier="transient", severity="transient", category="runtime",
        shell_fix=["bash", "-c", "cd apps/dashboard && rm -rf .next node_modules/.cache && pnpm install"],
        fix_description="Reinstall Next.js dependencies and clear cache",
        description="Next.js package not found — stale node_modules",
    ),

    # Shell-fix-only: broken node_modules symlinks (ERR_MODULE_NOT_FOUND / Cannot find package).
    # pnpm uses symlinks that break when the store is pruned or node_modules is partially deleted.
    ErrorPattern(
        regex=re.compile(
            r"ERR_MODULE_NOT_FOUND|Cannot find package|broken symbolic link.*node_modules",
            re.IGNORECASE,
        ),
        tier="transient", severity="high", category="infrastructure",
        shell_fix=["bash", "-c", "cd apps/dashboard && pnpm install"],
        fix_description="Reinstall pnpm dependencies to fix broken node_modules symlinks",
        description="Broken pnpm symlinks — ERR_MODULE_NOT_FOUND in dashboard build",
    ),

    # Shell-fix-only: Failed to restore task data (Turbopack SST corruption variant)
    ErrorPattern(
        regex=re.compile(r"Failed to restore task data.*corrupted", re.IGNORECASE),
        tier="transient", severity="transient", category="runtime",
        shell_fix=[
            "bash", "-c",
            "rm -rf apps/dashboard/.next/dev apps/dashboard/.next/cache "
            "&& PROJ=$(python3 -c \"import yaml; print(yaml.safe_load(open('project.yaml')).get('name','Augur').lower())\" 2>/dev/null || echo augur) && launchctl kickstart -k gui/$(id -u)/com.${PROJ}.dashboard 2>/dev/null; true",
        ],
        fix_description="Clear corrupted Turbopack dev cache and restart dashboard",
        description="Turbopack SST file corruption variant",
    ),

    # ═══════════════════════════════════════════════════════════════════════
    # ACTIONABLE TIER — Real bugs that need fixing.
    # FileNotFoundError, ModuleNotFoundError, TypeError, crashes, MCP errors.
    # ═══════════════════════════════════════════════════════════════════════

    ErrorPattern(
        regex=re.compile(r"FileNotFoundError|ENOENT", re.IGNORECASE),
        tier="actionable", severity="high", category="integration",
        description="Python FileNotFoundError / ENOENT in code",
    ),
    ErrorPattern(
        regex=re.compile(r"mcp_runtime:project_python_missing", re.IGNORECASE),
        tier="actionable", severity="high", category="infrastructure",
        shell_fix=["uv", "sync"],
        fix_description="Recreate the project virtualenv used by MCP clients",
        description="Missing generated project Python runtime for MCP clients",
    ),
    ErrorPattern(
        regex=re.compile(r"No such file or directory", re.IGNORECASE),
        tier="actionable", severity="high", category="integration",
        description="Missing files in non-Python contexts",
    ),
    ErrorPattern(
        regex=re.compile(r"ModuleNotFoundError|ImportError.*No module named", re.IGNORECASE),
        tier="actionable", severity="high", category="integration",
        description="Missing Python modules",
    ),
    ErrorPattern(
        regex=re.compile(
            r"CRITICAL.*crash|unhandled.*exception|SystemExit|segfault",
            re.IGNORECASE,
        ),
        tier="actionable", severity="critical", category="runtime",
        description="Unhandled exceptions crashing a service",
    ),
    ErrorPattern(
        regex=re.compile(r"TypeError:|AttributeError:|KeyError:", re.IGNORECASE),
        tier="actionable", severity="high", category="integration",
        description="TypeError / AttributeError / KeyError — code bugs",
    ),
    ErrorPattern(
        regex=re.compile(r"Unknown tool:|tool not found|tool.*not registered", re.IGNORECASE),
        tier="actionable", severity="medium", category="integration",
        description="MCP tool registration / schema errors",
    ),
    ErrorPattern(
        regex=re.compile(
            r"validation error for.*Arguments|pydantic.*validation_error",
            re.IGNORECASE,
        ),
        tier="actionable", severity="medium", category="integration",
        description="Pydantic validation errors from API routes",
    ),
]


# ── Derived views ────────────────────────────────────────────────────────────


def get_tier_patterns(tier: str) -> list[ErrorPattern]:
    """Return patterns for a specific tier (dismiss/transient/actionable)."""
    return [p for p in PATTERNS if p.tier == tier]


def get_shell_actions() -> list[ErrorPattern]:
    """Return patterns that have deterministic shell fixes."""
    return [p for p in PATTERNS if p.shell_fix is not None]


def get_severity_hints() -> list[tuple[re.Pattern, str, str]]:
    """Backwards-compatible flat list for external callers.

    Returns (regex, severity, category) tuples in tier order.
    """
    result: list[tuple[re.Pattern, str, str]] = []
    for tier in ("dismiss", "transient", "actionable"):
        for p in get_tier_patterns(tier):
            result.append((p.regex, p.severity, p.category))
    return result
