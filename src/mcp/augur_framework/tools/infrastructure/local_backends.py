"""
Local backend detection and status reporting.

Detects local LLM backends (Ollama) and reports readiness for offline/local mode.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from src.lib.extraction import detect_extraction_capabilities
from src.mcp.augur_shared.safe_subprocess import safe_run


class GetLocalBackendStatusInput(BaseModel):
    """Input for get-local-backend-status. No required fields."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


class ListOllamaIntegrationsInput(BaseModel):
    """Input for list-ollama-integrations. No required fields."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


class GetAirplaneLaunchOverridesInput(BaseModel):
    """Input for get-airplane-launch-overrides."""

    agent_id: str = Field(
        ...,
        description="The cliId for the agent (e.g. 'claude').",
    )

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


class ToggleAirplaneModeInput(BaseModel):
    """Input for toggle-airplane-mode.

    Actions:
        on     — enable airplane mode (forced)
        off    — disable airplane mode
        toggle — flip current state
        status — return current state + connectivity
    """

    action: str = Field(
        default="toggle",
        description='One of: "on", "off", "toggle", "status"',
    )

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


class ResolveClientInput(BaseModel):
    """Input for resolve-client."""

    action_id: str = Field(..., description="Action ID to resolve client for")
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


class SetClientOverrideInput(BaseModel):
    """Input for set-client-override."""

    action_id: str = Field(..., description="Action ID to set override for")
    client_id: str | None = Field(default=None, description="Client ID to route to")
    clear: bool = Field(default=False, description="Clear the override for this action")
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


# ── Defaults ────────────────────────────────────────────────────────────

_LOCAL_BACKEND_DEFAULTS: dict[str, Any] = {
    "model": "qwen3.5:9b",
    "agent": "claude",
    "context_length": 32768,
    "agent_models": {
        "codex": "augur-codex-qwen2.5-coder:7b-4k",
    },
}

_AIRPLANE_MODE_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "forced": False,
    "auto_detect": True,
    "fallback_tools": [],
}

_INTEGRATIONS_CACHE: dict[str, Any] = {
    "binary": None,
    "value": None,
    "fetched_at": 0.0,
}
_INTEGRATIONS_TTL_S = 60.0
_INTEGRATION_LINE_RE = re.compile(r"^\s+([a-z][a-z0-9_-]*)\s+\S")


# ── Helpers ─────────────────────────────────────────────────────────────


def _get_preferences_path() -> Path:
    """Get the path to preferences.yaml."""
    from src.mcp.augur_shared.config import get_preferences_path

    return get_preferences_path()


def _load_local_prefs() -> dict[str, Any]:
    """Load local_backends and airplane_mode sections from preferences.yaml."""
    from src.config.preferences import get_preferences_path, load_preferences

    path = _get_preferences_path()
    return load_preferences() if path == get_preferences_path() else load_preferences(path=path, migrate_legacy=False)


def _load_ollama_config(prefs: dict[str, Any]) -> dict[str, Any]:
    """Merge Ollama local-backend preferences without losing nested defaults."""
    local_backends_prefs = prefs.get("local_backends", {})
    ollama_cfg = {}
    if isinstance(local_backends_prefs, dict):
        raw_ollama_cfg = local_backends_prefs.get("ollama", {})
        if isinstance(raw_ollama_cfg, dict):
            ollama_cfg = raw_ollama_cfg

    config = {**_LOCAL_BACKEND_DEFAULTS, **ollama_cfg}

    default_agent_models = _LOCAL_BACKEND_DEFAULTS.get("agent_models", {})
    configured_agent_models = ollama_cfg.get("agent_models", {})
    merged_agent_models: dict[str, Any] = {}
    if isinstance(default_agent_models, dict):
        merged_agent_models.update(default_agent_models)
    if isinstance(configured_agent_models, dict):
        merged_agent_models.update(configured_agent_models)
    config["agent_models"] = merged_agent_models
    return config


def _setup_hint(reason: str, *, model: str | None = None) -> str:
    """Return platform-aware setup guidance for airplane launch readiness."""
    is_windows = sys.platform == "win32"

    if reason == "binary_missing":
        if is_windows:
            return "Install Ollama from https://ollama.com/download/windows " "or run: winget install Ollama.Ollama"
        return "Install Ollama: brew install ollama"

    if reason == "ollama_not_running":
        if is_windows:
            return "Open the Ollama app from Start menu, " "or run in PowerShell: ollama serve"
        return "Start Ollama: ollama serve"

    if reason == "model_missing":
        configured_model = model or "the configured model"
        if is_windows:
            return f"Pull the model in PowerShell: ollama pull {configured_model}"
        return f"Pull the model: ollama pull {configured_model}"

    return "Check Ollama setup and try again."


def _launch_unavailable_hint() -> str:
    """Return guidance for Ollama versions without integration launch support."""
    if sys.platform == "win32":
        return "Reinstall Ollama from https://ollama.com/download/windows"
    return "Update Ollama: brew upgrade ollama"


def _candidate_exists(path: str) -> bool:
    """Wrapped for monkey-patching in tests."""
    return Path(path).exists()


def _platform_candidates() -> list[str]:
    """Return Ollama binary candidate paths in priority order for current platform."""
    if sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        programfiles = os.environ.get("PROGRAMFILES", "")
        userprofile = os.environ.get("USERPROFILE", "")
        out: list[str] = []
        if localappdata:
            out.append(str(Path(localappdata) / "Programs" / "Ollama" / "ollama.exe"))
        if programfiles:
            out.append(str(Path(programfiles) / "Ollama" / "ollama.exe"))
        if userprofile:
            out.append(str(Path(userprofile) / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"))
        return out

    home = Path.home()
    return [
        "/opt/homebrew/bin/ollama",
        "/usr/local/bin/ollama",
        str(home / ".local" / "bin" / "ollama"),
    ]


def _resolve_ollama_binary() -> str | None:
    """Find ollama binary via PATH first, then platform-specific candidates."""
    found = shutil.which("ollama")
    if found:
        return found
    for candidate in _platform_candidates():
        if _candidate_exists(candidate):
            return candidate
    return None


def _detect_ollama() -> dict[str, Any]:
    """Detect Ollama installation, version, server status, and available models.

    Returns dict with: installed, version, binary, server_running, models.
    """
    result: dict[str, Any] = {
        "installed": False,
        "version": None,
        "binary": None,
        "server_running": False,
        "models": [],
    }

    # Check if binary exists
    binary = _resolve_ollama_binary()
    if not binary:
        return result

    result["installed"] = True
    result["binary"] = binary

    # Get version
    try:
        proc = safe_run(
            [binary, "--version"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            # Output format: "ollama version is 0.6.2" or similar
            version_text = proc.stdout.strip()
            # Extract version number from the output
            parts = version_text.split()
            if parts:
                result["version"] = parts[-1]
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Check server status and get model list via 'ollama list'
    try:
        proc = safe_run(
            [binary, "list"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            result["server_running"] = True
            # Parse output: skip header line, split columns: NAME, ID, SIZE, MODIFIED
            lines = proc.stdout.strip().splitlines()
            if len(lines) > 1:
                for line in lines[1:]:
                    cols = line.split()
                    if len(cols) >= 4:
                        # SIZE can be "5.5 GB" (two tokens), so we need to handle that
                        # NAME is cols[0], ID is cols[1], then SIZE is cols[2] + cols[3],
                        # and MODIFIED is the rest
                        name = cols[0]
                        model_id = cols[1]
                        size = f"{cols[2]} {cols[3]}" if len(cols) > 3 else cols[2]
                        modified = " ".join(cols[4:]) if len(cols) > 4 else ""
                        result["models"].append(
                            {
                                "name": name,
                                "id": model_id,
                                "size": size,
                                "modified": modified,
                            }
                        )
        else:
            # Non-zero return code means server is likely not running
            result["server_running"] = False
    except (subprocess.TimeoutExpired, OSError):
        result["server_running"] = False

    return result


def _build_extraction_status() -> dict[str, Any]:
    try:
        inventory = detect_extraction_capabilities(
            probe_timeout_s=1,
            probe_vision_models=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ocr_engine": "glm-ocr",
            "ocr_engine_available": False,
            "asr_engine": "openvino-whisper" if sys.platform != "darwin" else "faster-whisper",
            "transcription_ready": False,
            "error": str(exc),
        }

    ollama = inventory.get("ollama", {})
    openvino = inventory.get("openvino", {})
    return {
        "ocr_engine": "glm-ocr",
        "ocr_engine_available": bool(ollama.get("glm_ocr_available")),
        "asr_engine": "openvino-whisper" if sys.platform != "darwin" else "faster-whisper",
        "asr_device": openvino.get("live_device"),
        "openvino_devices": openvino.get("devices", ["NPU", "GPU", "CPU"]),
        "transcription_ready": bool(inventory.get("transcription_ready")),
        "transcription_model": inventory.get("transcription_model"),
        "prereqs": inventory.get("extraction_prereqs", {}),
    }


def _reset_integrations_cache() -> None:
    """Clear the Ollama integrations cache for tests."""
    _INTEGRATIONS_CACHE["binary"] = None
    _INTEGRATIONS_CACHE["value"] = None
    _INTEGRATIONS_CACHE["fetched_at"] = 0.0


def _parse_integrations_help(stdout: str) -> list[str]:
    """Parse canonical integration ids from `ollama launch --help` output."""
    lines = stdout.splitlines()
    started = False
    integrations: list[str] = []

    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()

        if lowered.startswith("supported integrations"):
            started = True
            continue

        if not started:
            continue

        if not stripped:
            if integrations:
                break
            continue

        if lowered.startswith("example"):
            break

        match = _INTEGRATION_LINE_RE.match(line)
        if match:
            integrations.append(match.group(1))

    return integrations


def _integration_launch_args(agent_id: str) -> list[str]:
    """Return extra CLI args passed after the `ollama launch --` separator."""
    if agent_id == "codex":
        return ["--oss", "--local-provider", "ollama"]
    return []


def _model_for_agent(config: dict[str, Any], agent_id: str) -> str:
    """Return the Ollama model that should back a specific native agent."""
    agent_models = config.get("agent_models")
    if isinstance(agent_models, dict):
        value = agent_models.get(agent_id)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(config["model"])


# ── Implementation ──────────────────────────────────────────────────────


async def get_local_backend_status_impl(params: GetLocalBackendStatusInput) -> str:
    """Get local backend status including Ollama detection and airplane mode.

    Returns JSON with ollama, airplane_mode, and launch_command sections.
    """
    prefs = _load_local_prefs()

    # Merge local_backends config with defaults
    config = _load_ollama_config(prefs)

    # Merge airplane_mode config with defaults
    airplane_prefs = prefs.get("airplane_mode", {})
    airplane_mode = {**_AIRPLANE_MODE_DEFAULTS, **airplane_prefs}

    # Detect Ollama
    ollama = _detect_ollama()

    # Compute server readiness first; chat launch readiness may be stricter
    # because large local models can exceed the current machine's memory headroom.
    server_ready = ollama["installed"] and ollama["server_running"] and len(ollama["models"]) > 0

    configured_model = config["model"]
    configured_agent = config["agent"]
    launch_model = _model_for_agent(config, str(configured_agent))
    has_configured_model = any(m["name"] == configured_model for m in ollama["models"])
    launch_ready = server_ready
    launch_setup_hint = None
    launch_error = None
    if server_ready:
        from src.lib.routing.engines import build_ollama_launch_spec

        launch_spec = build_ollama_launch_spec(str(configured_agent))
        launch_ready = bool(launch_spec.ready)
        launch_setup_hint = launch_spec.setup_hint
        launch_error = launch_spec.error

    result = {
        "ollama": {
            "installed": ollama["installed"],
            "version": ollama["version"],
            "binary": ollama["binary"],
            "server_running": ollama["server_running"],
            "models": ollama["models"],
            "configured_model": configured_model,
            "configured_agent": configured_agent,
            "has_configured_model": has_configured_model,
            "server_ready": server_ready,
            "launch_ready": launch_ready,
            "launch_setup_hint": launch_setup_hint,
            "launch_error": launch_error,
            "ready": server_ready and launch_ready,
        },
        "airplane_mode": airplane_mode,
        "launch_command": (
            f"ollama launch {configured_agent} --model {launch_model}" if server_ready and launch_ready else None
        ),
        "extraction": _build_extraction_status(),
    }

    # Lazy: routing.engines imports local_backends at call time; a top-level import would cycle.
    from src.lib.routing.engines import OCR_ENGINES, TRANSCRIPT_ENGINES
    from src.lib.routing.matrix import engine_id_for

    def _avail(activity: str, engine_id: str) -> bool:
        if activity == "chat" and engine_id == "ollama-llm":
            return bool(launch_ready)
        if activity == "chat" and engine_id == "agent-chat":
            return True
        registry = OCR_ENGINES if activity == "ocr" else TRANSCRIPT_ENGINES if activity == "transcript" else {}
        engine = registry.get(engine_id)
        if engine is None:
            return False
        try:
            return bool(engine.available().available)
        except Exception:
            return False

    routing: dict[str, Any] = {}
    for activity in ("chat", "ocr", "transcript"):
        routing[activity] = {}
        for mode in ("regular", "offline"):
            try:
                eid = engine_id_for(activity, mode)
            except Exception:
                eid = None
            routing[activity][mode] = {"engine": eid, "available": _avail(activity, eid) if eid else False}
    result["routing"] = routing

    return json.dumps(result, indent=2)


async def list_ollama_integrations_impl(
    params: ListOllamaIntegrationsInput,
) -> str:
    """Return canonical agent integrations supported by `ollama launch`."""
    now = time.monotonic()
    binary = _resolve_ollama_binary()
    cached = _INTEGRATIONS_CACHE["value"]

    if (
        cached is not None
        and _INTEGRATIONS_CACHE["binary"] == binary
        and (now - _INTEGRATIONS_CACHE["fetched_at"]) < _INTEGRATIONS_TTL_S
    ):
        return json.dumps({"integrations": cached}, indent=2)

    integrations: list[str] = []
    if binary:
        try:
            result = safe_run(
                [binary, "launch", "--help"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None

        if result is not None and result.returncode == 0:
            integrations = _parse_integrations_help(result.stdout)

    _INTEGRATIONS_CACHE["binary"] = binary
    _INTEGRATIONS_CACHE["value"] = integrations
    _INTEGRATIONS_CACHE["fetched_at"] = now
    return json.dumps({"integrations": integrations}, indent=2)


async def get_airplane_launch_overrides_impl(
    params: GetAirplaneLaunchOverridesInput,
) -> str:
    """Return Ollama launch argv for an airplane-mode agent (no smoke probing)."""
    # Lazy: routing.engines imports local_backends at call time; a top-level import would cycle.
    from src.lib.routing.engines import build_ollama_launch_spec

    spec = build_ollama_launch_spec(params.agent_id)
    if not spec.ready:
        # Collapsed reason "ollama_not_ready"; actionable detail rides in setup_hint.
        # Verified: the dashboard cli/airplane route passes reason through and renders
        # setup_hint (no switch on granular reason), and /settings/security loads clean.
        return json.dumps(
            {"ready": False, "reason": "ollama_not_ready", "setup_hint": spec.setup_hint},
            indent=2,
        )
    return json.dumps(
        {
            "ready": True,
            "integration_id": params.agent_id,
            "model": spec.model,
            "launch_argv": spec.launch_argv,
        },
        indent=2,
    )


# ── Airplane-mode helpers ──────────────────────────────────────────────


def _save_prefs_key(key: str, value: Any) -> dict[str, Any]:
    """Load preferences.yaml, update one top-level key, and save back.

    Returns the full prefs dict after the write.
    """
    from src.config.preferences import save_preferences

    path = _get_preferences_path()
    prefs = _load_local_prefs()
    prefs[key] = value

    save_preferences(prefs, path=path)

    return prefs


# ── Toggle airplane mode ───────────────────────────────────────────────


async def toggle_airplane_mode_impl(params: ToggleAirplaneModeInput) -> str:
    """Toggle, enable, disable, or query airplane mode.

    Returns JSON with airplane_mode state and (for status) connectivity info.
    """
    from src.mcp.augur_framework.tools.infrastructure.connectivity import check_connectivity

    prefs = _load_local_prefs()
    airplane = {**_AIRPLANE_MODE_DEFAULTS, **prefs.get("airplane_mode", {})}

    action = params.action.lower()

    if action == "on":
        airplane["enabled"] = True
        airplane["forced"] = True
        _save_prefs_key("airplane_mode", airplane)
    elif action == "off":
        airplane["enabled"] = False
        airplane["forced"] = False
        _save_prefs_key("airplane_mode", airplane)
    elif action == "toggle":
        airplane["enabled"] = not airplane["enabled"]
        airplane["forced"] = airplane["enabled"]
        _save_prefs_key("airplane_mode", airplane)
    elif action == "status":
        pass  # read-only, no save
    else:
        return json.dumps(
            {"error": f"Unknown action: {action!r}. Use on/off/toggle/status."},
            indent=2,
        )

    result: dict[str, Any] = {"airplane_mode": airplane}

    if action == "status":
        result["connectivity"] = check_connectivity()

    return json.dumps(result, indent=2)


# ── Client routing ────────────────────────────────────────────────────


async def resolve_client_impl(params: ResolveClientInput) -> str:
    """Resolve which AI client should handle the given action."""
    from src.mcp.augur_framework.tools.infrastructure.client_resolver import ClientResolver

    resolver = ClientResolver()
    result = resolver.resolve(params.action_id)
    return json.dumps(result.to_dict(), indent=2)


async def set_client_override_impl(params: SetClientOverrideInput) -> str:
    """Set or clear a per-action client override."""
    from src.mcp.augur_framework.tools.infrastructure.client_resolver import ClientResolver

    resolver = ClientResolver()
    if params.clear:
        existed = resolver.clear_override(params.action_id)
        return json.dumps(
            {
                "success": True,
                "action": "cleared" if existed else "no_override_existed",
                "action_id": params.action_id,
            },
            indent=2,
        )
    if not params.client_id:
        return json.dumps({"success": False, "error": "client_id required when not clearing"}, indent=2)
    resolver.set_override(params.action_id, params.client_id)
    return json.dumps(
        {
            "success": True,
            "action": "set",
            "action_id": params.action_id,
            "client_id": params.client_id,
        },
        indent=2,
    )


async def list_available_clients_impl() -> str:
    """List available AI clients from the integrations registry."""
    import yaml as _yaml
    from src.mcp.augur_shared.config import get_project_root

    integrations_path = get_project_root() / "config" / "agents" / "ide_integrations.yaml"
    clients: list[dict[str, Any]] = []

    if integrations_path.exists():
        try:
            with open(integrations_path, encoding="utf-8") as f:
                data = _yaml.safe_load(f) or {}
            for key, entry in data.get("integrations", {}).items():
                installed = entry.get("installed", False)
                if not installed:
                    continue
                client_type = "local" if key == "ollama" else "ide"
                clients.append(
                    {
                        "client_id": key,
                        "client_type": client_type,
                        "installed": True,
                        "enabled": entry.get("enabled", False),
                    }
                )
        except Exception:
            pass

    # Always include Ollama if not already present
    if not any(c["client_id"] == "ollama" for c in clients):
        ollama = _detect_ollama()
        clients.append(
            {
                "client_id": "ollama",
                "client_type": "local",
                "installed": ollama["installed"],
                "healthy": ollama["server_running"],
            }
        )

    return json.dumps({"clients": clients, "count": len(clients)}, indent=2)


__all__ = [
    "GetLocalBackendStatusInput",
    "ListOllamaIntegrationsInput",
    "GetAirplaneLaunchOverridesInput",
    "ToggleAirplaneModeInput",
    "ResolveClientInput",
    "SetClientOverrideInput",
    "get_local_backend_status_impl",
    "list_ollama_integrations_impl",
    "get_airplane_launch_overrides_impl",
    "toggle_airplane_mode_impl",
    "resolve_client_impl",
    "set_client_override_impl",
    "list_available_clients_impl",
    "_reset_integrations_cache",
]
