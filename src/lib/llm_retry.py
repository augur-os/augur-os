"""
LLM-Assisted Retry Utility (ADR-106).

Shared module for invoking an LLM CLI to diagnose retry failures.
Extracts resolve_cli() from ai_self_healer.py and adds structured
diagnosis + JSONL event logging.

This module intentionally avoids heavy imports to stay lightweight
in retry-critical paths. It resolves the project root via __file__.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess  # nosec B404
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Project root resolution (same pattern as self_heal_event.py — no circular imports)
# ---------------------------------------------------------------------------

_PROJECT_ROOT: Path | None = None


def _find_project_root() -> Path | None:
    """Walk up from this file to find the project root (contains src/ and config/)."""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "src").is_dir() and (current / "config").is_dir():
            _PROJECT_ROOT = current
            return _PROJECT_ROOT
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _load_unprotected_yaml_mapping(path: Path) -> dict:
    """Load a YAML mapping for non-protected config files."""

    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LLMRetryConfig:
    """Configuration for LLM-assisted retry, loaded from llm.yaml."""

    enabled: bool = True
    trigger_attempt: int = 3
    timeout_s: int = 90
    cli: str = "auto"
    mode: str = "diagnose"
    components: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Path | None = None) -> LLMRetryConfig:
        """Load config from config/system/llm.yaml → llm_retry section."""
        if config_path is None:
            root = _find_project_root()
            if root is None:
                return cls()
            config_path = root / "config" / "system" / "llm.yaml"

        if not config_path.exists():
            return cls()

        try:
            if config_path.name == "llm.yaml" and config_path.parent.name == "system":
                from src.config.system_config import llm_config_raw

                data = llm_config_raw(config_path)
            else:
                data = _load_unprotected_yaml_mapping(config_path)
            section = data.get("llm_retry", {})
            if not isinstance(section, dict):
                return cls()
            return cls(
                enabled=section.get("enabled", True),
                trigger_attempt=section.get("trigger_attempt", 3),
                timeout_s=section.get("timeout_s", 90),
                cli=section.get("cli", "auto"),
                mode=section.get("mode", "diagnose"),
                components=section.get("components", {}),
            )
        except Exception:
            return cls()

    def is_enabled_for(self, component: str) -> bool:
        """Check if LLM retry is enabled globally and for this component."""
        if not self.enabled:
            return False
        return self.components.get(component, False)


@dataclass
class RetryAttemptLog:
    """Record of a single retry attempt."""

    attempt: int
    error: str
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class LLMDiagnosis:
    """Structured diagnosis from the LLM."""

    root_cause: str = ""
    suggestion: str = ""
    should_retry: bool = True
    raw_response: str = ""


# ---------------------------------------------------------------------------
# CLI resolution (extracted from ai_self_healer.py:647-693)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Headless CLI invocation (data-driven from cli_headless_profiles.yaml)
# ---------------------------------------------------------------------------

_HEADLESS_PROFILES: dict | None = None

# Fallback profile when a CLI has no entry in cli_headless_profiles.yaml.
# Uses Claude Code style since it's the most common pattern.
_DEFAULT_PROFILE: dict = {
    "output_mode": "--print",
    "prompt_delivery": "flag",
    "prompt_flag": "-p",
    "param_flags": {
        "model": "--model",
        "max_turns": "--max-turns",
        "allowed_tools": "--allowedTools",
    },
    "boolean_flags": {
        "bypass_approvals": "--dangerously-skip-permissions",
        "no_session": "--no-session-persistence",
    },
}


def _load_headless_profiles() -> dict:
    """Load per-client headless invocation profiles from config/agents/."""
    global _HEADLESS_PROFILES
    if _HEADLESS_PROFILES is not None:
        return _HEADLESS_PROFILES

    root = _find_project_root()
    if root is None:
        _HEADLESS_PROFILES = {}
        return _HEADLESS_PROFILES

    profile_path = root / "config" / "agents" / "cli_headless_profiles.yaml"
    if not profile_path.exists():
        _HEADLESS_PROFILES = {}
        return _HEADLESS_PROFILES

    try:
        import yaml

        data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
        _HEADLESS_PROFILES = data.get("profiles", {})
    except Exception:
        _HEADLESS_PROFILES = {}

    return _HEADLESS_PROFILES


def _get_headless_profile(cli_path: str) -> dict:
    """Look up the headless profile for a CLI binary, falling back to defaults."""
    cli_name = Path(cli_path).stem
    profiles = _load_headless_profiles()
    return profiles.get(cli_name, _DEFAULT_PROFILE)


def _which(binary: str, search_path: str | None = None) -> str | None:
    """Resolve a CLI binary, optionally against a launchd-safe PATH."""
    return shutil.which(binary, path=search_path)


def build_headless_cmd(
    cli_path: str,
    prompt: str,
    *,
    model: str | None = None,
    max_turns: int | None = None,
    allowed_tools: str | None = None,
    bypass_approvals: bool = True,
    no_session: bool = True,
) -> list[str]:
    """Build a CLI command for headless (non-interactive) LLM invocation.

    Reads per-client profiles from config/agents/cli_headless_profiles.yaml.
    To add a new client, add a YAML entry — no code changes needed.
    """
    profile = _get_headless_profile(cli_path)
    cmd = [cli_path]

    # Subcommand (e.g. codex "exec", opencode "run")
    if profile.get("subcommand"):
        cmd.append(profile["subcommand"])

    # Output mode flag (e.g. claude "--print")
    if profile.get("output_mode"):
        cmd.append(profile["output_mode"])

    # Parameterized flags (model, max_turns, allowed_tools)
    param_flags = profile.get("param_flags", {})
    for name, value in [("model", model), ("max_turns", max_turns), ("allowed_tools", allowed_tools)]:
        if value is not None and name in param_flags:
            cmd.extend([param_flags[name], str(value)])

    # Boolean flags (bypass_approvals, no_session)
    bool_flags = profile.get("boolean_flags", {})
    for name, enabled in [("bypass_approvals", bypass_approvals), ("no_session", no_session)]:
        if enabled and name in bool_flags:
            cmd.append(bool_flags[name])

    # Prompt delivery
    if profile.get("prompt_delivery") == "positional":
        cmd.append(prompt)
    else:
        prompt_flag = profile.get("prompt_flag", "-p")
        cmd.extend([prompt_flag, prompt])

    return cmd


def build_sidecar_cmd(
    cli_path: str,
    prompt: str,
    *,
    model: str | None = None,
    allowed_tools: str | None = None,
    additional_dirs: list[str] | tuple[str, ...] | None = None,
    bypass_approvals: bool = True,
) -> list[str]:
    """Build CLI command for a persistent interactive sidecar session.

    Like build_headless_cmd() but omits --print/output_mode and --max-turns,
    producing a long-running interactive session where the AI can call tools
    in a loop. Used by AISidecarManager in the daemon.
    """
    profile = _get_headless_profile(cli_path)
    cmd = [cli_path]

    # Subcommand — use sidecar_subcommand override if defined in profile,
    # otherwise skip subcommand entirely (headless subcommands like codex "exec"
    # are inappropriate for interactive sessions)
    sidecar_sub = profile.get("sidecar_subcommand")
    if sidecar_sub:
        cmd.append(sidecar_sub)

    # NO output_mode — intentionally omitted for interactive session
    # NO max_turns — session runs indefinitely

    # Parameterized flags (model, allowed_tools only — no max_turns)
    param_flags = profile.get("param_flags", {})
    for name, value in [("model", model), ("allowed_tools", allowed_tools)]:
        if value is not None and name in param_flags:
            cmd.extend([param_flags[name], str(value)])
    if additional_dirs and "additional_dirs" in param_flags:
        cmd.append(param_flags["additional_dirs"])
        cmd.extend(str(path) for path in additional_dirs)

    # Boolean flags — bypass_approvals only, NOT no_session (session persists)
    bool_flags = profile.get("boolean_flags", {})
    if bypass_approvals and "bypass_approvals" in bool_flags:
        cmd.append(bool_flags["bypass_approvals"])

    # Prompt delivery. Sidecars are meant to be interactive, so default to a
    # positional prompt; for Claude, "-p" is print-and-exit mode.
    prompt_delivery = profile.get("sidecar_prompt_delivery", "positional")
    if prompt_delivery == "positional":
        cmd.append(prompt)
    else:
        prompt_flag = profile.get("sidecar_prompt_flag", profile.get("prompt_flag", "-p"))
        cmd.extend([prompt_flag, prompt])

    return cmd


def _resolve_cli_from_llm_config() -> str | None:
    """Try to resolve CLI command from llm.yaml task='retry_diagnosis' profile.

    Returns the command string if a 'command' provider profile is found, else None.
    Intentionally lightweight — catches all exceptions to stay safe in retry paths.
    """
    try:
        root = _find_project_root()
        if root is None:
            return None
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from src.lib.ai import load_llm_config, resolve_llm_profile

        config = load_llm_config()
        profile = resolve_llm_profile(config, task="retry_diagnosis")
        if profile.provider == "command" and profile.command:
            return profile.command.strip()
    except Exception:
        pass
    return None


def resolve_cli(cli_setting: str = "auto", *, search_path: str | None = None) -> Optional[str]:
    """Resolve which CLI binary to use for LLM calls.

    Resolution is purely config-driven:
    1. Explicit cli_setting (non-"auto") → shutil.which(cli_setting)
    2. llm.yaml task="retry_diagnosis" command profile (unified config)
    3. cli_agents.yaml → ordered list of known CLIs

    Raises RuntimeError if no CLI can be resolved from config.
    """
    if cli_setting != "auto":
        resolved = _which(cli_setting, search_path)
        if resolved:
            return resolved
        raise RuntimeError(
            f"Configured CLI '{cli_setting}' not found on PATH. "
            f"Install it or update vault config/ai/cli_agents.yaml."
        )

    # Check llm.yaml profiles first (unified config)
    llm_config_cmd = _resolve_cli_from_llm_config()
    if llm_config_cmd:
        first_token = llm_config_cmd.split()[0]
        resolved = _which(first_token, search_path)
        if resolved:
            return resolved

    root = _find_project_root()
    if root is None:
        raise RuntimeError(
            "Cannot resolve CLI: project root not found. "
            "Ensure resolve_cli is called from within the Augur project tree."
        )

    candidates = _get_cli_candidates()
    for candidate in candidates:
        resolved = _which(candidate, search_path)
        if resolved:
            return resolved

    raise RuntimeError(f"No CLI binary found. Searched: {candidates}. " f"Configure vault config/ai/cli_agents.yaml.")


# Cache for CLI candidates list (avoids re-reading YAML on every call)
_CLI_CANDIDATES: list[str] | None = None


def _get_cli_candidates() -> list[str]:
    """Read cli_agents.yaml to discover available CLI binaries.

    Returns binary names in cli_agents.yaml file order.
    Returns empty list if config is unreadable.
    """
    global _CLI_CANDIDATES
    if _CLI_CANDIDATES is not None:
        return _CLI_CANDIDATES

    root = _find_project_root()
    if root is None:
        _CLI_CANDIDATES = []
        return _CLI_CANDIDATES

    try:
        from src.lib.agent_cli_config import get_cli_candidate_ids

        _CLI_CANDIDATES = get_cli_candidate_ids(command_fields=("cmd",))
    except Exception:
        _CLI_CANDIDATES = []
    return _CLI_CANDIDATES


# ---------------------------------------------------------------------------
# LLM diagnosis
# ---------------------------------------------------------------------------

_DIAGNOSIS_PROMPT = """\
You are a systems reliability engineer. A component is failing repeatedly.

Component: {component}
Total attempts so far: {attempt_count}
Context: {context}

Previous attempt errors (most recent last):
{error_history}

Analyze the errors and respond with ONLY valid JSON (no markdown fences):
{{"root_cause": "one-line root cause", "suggestion": "actionable fix strategy", "should_retry": true_or_false}}

If the errors indicate a permanent/config issue, set should_retry to false.
If the errors are transient and a retry might succeed, set should_retry to true.
"""


def diagnose_with_llm(
    component: str,
    attempts: list[RetryAttemptLog],
    context: str = "",
    config: LLMRetryConfig | None = None,
) -> LLMDiagnosis:
    """Invoke CLI to diagnose retry failures. Returns LLMDiagnosis.

    Falls back to empty diagnosis on any error — never raises.
    """
    if config is None:
        config = LLMRetryConfig.load()

    if not config.is_enabled_for(component):
        return LLMDiagnosis()

    cli = resolve_cli(config.cli)
    if cli is None:
        return LLMDiagnosis(
            root_cause="no_cli",
            suggestion="No CLI binary found for LLM diagnosis",
            should_retry=True,
        )

    error_history = "\n".join(f"  Attempt {a.attempt}: {a.error}" for a in attempts)

    prompt = _DIAGNOSIS_PROMPT.format(
        component=component,
        attempt_count=len(attempts),
        context=context or "none",
        error_history=error_history or "  (no error details)",
    )

    try:
        cmd = build_headless_cmd(
            cli,
            prompt,
            max_turns=1,
            bypass_approvals=False,
            no_session=True,
        )
        result = subprocess.run(  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            timeout=config.timeout_s,
        )

        raw = result.stdout.strip()
        diagnosis = _parse_diagnosis(raw)
        log_retry_event(component, attempts, diagnosis)
        return diagnosis

    except subprocess.TimeoutExpired:
        return LLMDiagnosis(
            root_cause="timeout",
            suggestion=f"LLM diagnosis timed out after {config.timeout_s}s",
            should_retry=True,
        )
    except Exception:
        return LLMDiagnosis()


def _parse_diagnosis(raw: str) -> LLMDiagnosis:
    """Parse JSON from LLM response, tolerating markdown fences."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        return LLMDiagnosis(
            root_cause=str(data.get("root_cause", "")),
            suggestion=str(data.get("suggestion", "")),
            should_retry=bool(data.get("should_retry", True)),
            raw_response=raw,
        )
    except (json.JSONDecodeError, TypeError):
        return LLMDiagnosis(raw_response=raw)


# ---------------------------------------------------------------------------
# Event logging (JSONL — same pattern as self_heal_event.py)
# ---------------------------------------------------------------------------


def _get_event_file() -> Path | None:
    """Get path to llm_retry_events.jsonl, creating dirs if needed."""
    root = _find_project_root()
    if root is not None and str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        from src.config.paths import get_runtime_dir

        event_file = get_runtime_dir() / "llm_retry_events.jsonl"
    except Exception:
        if sys.platform == "darwin":
            event_file = Path.home() / "Library" / "Application Support" / "Augur" / "state" / "llm_retry_events.jsonl"
        else:
            event_file = (
                Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()
                / "augur"
                / "llm_retry_events.jsonl"
            )

    event_file.parent.mkdir(parents=True, exist_ok=True)
    return event_file


def log_retry_event(
    component: str,
    attempts: list[RetryAttemptLog],
    diagnosis: LLMDiagnosis,
) -> None:
    """Append a structured retry event to the JSONL log. Never raises."""
    try:
        event = {
            "timestamp": (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"),
            "component": component,
            "attempt_count": len(attempts),
            "attempts": [asdict(a) for a in attempts],
            "diagnosis": {
                "root_cause": diagnosis.root_cause,
                "suggestion": diagnosis.suggestion,
                "should_retry": diagnosis.should_retry,
            },
            "host": socket.gethostname(),
            "pid": os.getpid(),
        }

        event_file = _get_event_file()
        if event_file is None:
            print(f"[llm-retry] {json.dumps(event)}", file=sys.stderr, flush=True)
            return

        event_line = json.dumps(event, separators=(",", ":")) + "\n"

        with open(event_file, "a", encoding="utf-8") as dest:
            dest.write(event_line)

    except Exception as exc:
        try:
            print(
                f"[llm-retry] log failed: {exc} | component={component}",
                file=sys.stderr,
                flush=True,
            )
        except Exception:
            pass
