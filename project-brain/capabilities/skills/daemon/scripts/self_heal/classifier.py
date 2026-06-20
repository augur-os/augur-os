"""Severity classification — rule-based (pre_classify) and LLM-based (classify_issue).

Pattern data is sourced from self_heal.patterns (ADR-185 unified registry).
"""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import os
import re
import shutil
from typing import Optional, TYPE_CHECKING

try:
    from self_heal.patterns import PATTERNS, get_tier_patterns, get_shell_actions, get_severity_hints
except ImportError:
    from .patterns import PATTERNS, get_tier_patterns, get_shell_actions, get_severity_hints

if TYPE_CHECKING:
    from ai_self_healer import RegistryEntry


# ── Backwards-compatible re-exports ─────────────────────────────────────────
# External callers that import SEVERITY_TIERS, SHELL_ACTIONS, or SEVERITY_HINTS
# from this module continue to work. The source of truth is now patterns.py.

SEVERITY_TIERS: dict[str, list[tuple[re.Pattern, str, str]]] = {
    tier: [(p.regex, p.severity, p.category) for p in get_tier_patterns(tier)]
    for tier in ("dismiss", "transient", "actionable")
}

SHELL_ACTIONS: list[tuple[re.Pattern, list[str], str]] = [
    (p.regex, p.shell_fix, p.fix_description)
    for p in get_shell_actions()
]

SEVERITY_HINTS: list[tuple[re.Pattern, str, str]] = get_severity_hints()


def match_shell_action(entry: "RegistryEntry") -> Optional[tuple[list[str], str]]:
    """Check if an issue can be fixed by a shell command. Returns (cmd, description) or None."""
    text = f"{entry.message} {entry.stack_trace or ''}"
    for p in get_shell_actions():
        if p.regex.search(text):
            return p.shell_fix, p.fix_description
    return None


def pre_classify(entry: "RegistryEntry") -> Optional[dict]:
    """Fast pattern-based classification before LLM. Returns dict or None.

    Evaluates tiers in order: dismiss -> transient -> actionable.
    First match from the earliest tier wins, which prevents rule-ordering
    bugs where a generic actionable pattern shadows a specific dismiss pattern.
    """
    text = f"{entry.message} {entry.stack_trace or ''}"
    for tier_name in ("dismiss", "transient", "actionable"):
        for p in get_tier_patterns(tier_name):
            if p.regex.search(text):
                return {
                    "severity": p.severity,
                    "category": p.category,
                    "summary": f"Pattern match ({tier_name}): {p.regex.pattern[:60]}",
                    "likely_file": entry.file,
                    "suggested_approach": "Investigate the error and apply minimal fix",
                }
    return None


CLASSIFY_PROMPT = """You are a runtime error classifier for the Augur system.
Given the following error context, classify its severity.

Error: {message}
Source file: {file}
Stack trace: {stack_trace}
Occurrences: {occurrences}

Classify as one of:
- CRITICAL: System is down or data loss imminent. Immediate fix required.
- HIGH: Feature is broken, user-visible impact. Fix within minutes. FileNotFoundError, ModuleNotFoundError, and broken import paths are HIGH — they indicate code/config bugs, not transient issues.
- MEDIUM: Degraded functionality, workaround exists. Fix during next maintenance.
- LOW: Cosmetic, warning, or minor. Track as TODO.
- TRANSIENT: Runtime-state issue with NO code fix. Examples: PID lock conflicts, port already in use, stale process, network timeout, temporary file missing, service restart resolved it. These issues resolve themselves or require operator action, not code changes.

IMPORTANT: If the error is about a lock file, PID conflict, "already running", port in use, network timeout, DNS resolution, or other runtime-state issues — classify as TRANSIENT. Do NOT classify runtime-state issues as CRITICAL or HIGH.
IMPORTANT: FileNotFoundError, ModuleNotFoundError, and missing script paths are NOT transient — they are HIGH severity code/config bugs that need fixing.

Respond with ONLY valid JSON (no markdown fences):
{{"severity": "critical|high|medium|low|transient", "category": "integration|ux|performance|data|security|runtime", "summary": "one-line description", "likely_file": "path/to/suspected/file.py", "suggested_approach": "brief fix strategy"}}"""


def resolve_cli(config: dict) -> Optional[str]:
    """Resolve which CLI binary to use for LLM calls.

    Delegates to the src/lib llm_retry module (ADR-106).
    """
    from src.lib.llm_retry import resolve_cli as _canonical_resolve_cli

    llm_conf = config.get("llm", {})
    cli_name = llm_conf.get("cli", "auto")
    try:
        resolved = _canonical_resolve_cli(cli_name)
    except RuntimeError as exc:
        _get_logger().warning(f"CLI resolution failed: {exc}")
        if cli_name == "auto":
            for candidate in ("claude", "kimi", "codex"):
                fallback = shutil.which(candidate)
                if fallback:
                    _get_logger().info(f"CLI fallback resolved: {fallback}")
                    return fallback
        return None

    if resolved:
        _get_logger().info(f"CLI resolved: {resolved}")
    else:
        _get_logger().warning("No CLI binary found — fixes will be deferred to TODO markers")
    return resolved


def classify_issue(
    entry: "RegistryEntry",
    config: dict,
    cli_path: Optional[str] = None,
) -> Optional[dict]:
    """Send error to LLM for severity classification. Returns parsed JSON or None."""
    # Import here to get the current PROJECT_ROOT from the main module
    import ai_self_healer as _healer

    if cli_path is None:
        # Look up through _healer so tests can patch ai_self_healer.resolve_cli
        cli_path = _healer.resolve_cli(config)

    if not cli_path:
        _get_logger().warning("No LLM CLI available, skipping classification")
        return None

    from src.lib.llm_retry import build_headless_cmd

    llm_conf = config.get("llm", {})
    classify_model = llm_conf.get("classify_model", "haiku")
    timeout = llm_conf.get("classify_timeout_s", 30)

    prompt = CLASSIFY_PROMPT.format(
        message=entry.message[:500],
        file=entry.file,
        stack_trace=entry.stack_trace or "N/A",
        occurrences=entry.occurrences,
    )

    try:
        cmd = build_headless_cmd(
            cli_path, prompt,
            model=classify_model,
            max_turns=1,
            bypass_approvals=True,
        )
        # Clear CLAUDECODE env var to prevent nested session blocking
        classify_env = os.environ.copy()
        classify_env.pop("CLAUDECODE", None)
        classify_env.pop("CLAUDE_CODE", None)
        # Use _healer.subprocess so tests can patch ai_self_healer.subprocess.run
        result = _healer.subprocess.run(  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_healer.PROJECT_ROOT),
            env=classify_env,
        )

        if result.returncode != 0:
            _get_logger().warning(f"Classification CLI failed: {result.stderr[:200]}")
            return None

        return _parse_llm_json(result.stdout)

    except _healer.subprocess.TimeoutExpired:
        _get_logger().warning("Classification timed out")
        return None
    except Exception as e:
        _get_logger().warning(f"Classification error: {e}")
        return None


def _parse_llm_json(output: str) -> Optional[dict]:
    """Extract JSON object from LLM output (may contain extra text)."""
    # Try direct parse first
    try:
        return json.loads(output.strip())
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding any JSON object
    match = re.search(r"\{[^{}]*\}", output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _get_logger():
    """Lazy import logger from main module to avoid circular imports."""
    import ai_self_healer as _healer
    return _healer.logger
