"""
System Operations tool implementations.

These tools handle system-level operations like opening files/URLs,
listing services, recording voice, and document import.
"""

import asyncio
import importlib.util
import json
import os
import platform
import shutil
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired  # nosec
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.logging import get_entity_logger
from src.mcp.augur_shared.safe_subprocess import safe_run as subprocess_run  # nosec

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp")


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve command executable to absolute path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run_command(command: list[str], **kwargs: Any) -> CompletedProcess[str]:
    """Run subprocess command with resolved executable path."""
    return subprocess_run(_resolve_command(command), **kwargs)  # nosec


# Lazy import to avoid circular dependencies
def _get_data_dir() -> Path:
    """Get project root from centralized config."""
    from src.mcp.augur_shared.config import get_project_root

    return get_project_root()


def _load_module_from_path(module_name: str, script_path: Path) -> Any:
    """Load a Python module from disk with a real sys.modules registration."""
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module spec for {script_path}")

    existing = sys.modules.get(module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if existing is not None:
            sys.modules[module_name] = existing
        else:
            sys.modules.pop(module_name, None)
        raise
    return module


# =============================================================================
# Pydantic Input Models
# =============================================================================


class ApplyImportInput(BaseModel):
    """Input for apply-import tool."""

    model_config = ConfigDict(extra="forbid")
    file_path: str = Field(..., description="Path to file to import")
    destination: str = Field(..., description="Destination path in data repo")
    metadata: dict | None = Field(None, description="Additional metadata for import")


class OpenClientRuntimeInput(BaseModel):
    """Input for open-client-runtime-folder tool."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    client_id: str = Field(
        ...,
        alias="clientId",
        description="Client id (e.g. codex, claude-code, gemini)",
    )


def _resolve_client_runtime_dir(client_id: str) -> Path:
    """Resolve the runtime/config root for a supported external client."""
    from src.config.paths import get_client_runtime_dir

    client_map = {
        "claudeCode": "claude-code",
        "claudeDesktop": "claude-desktop",
        "cursor": "cursor",
        "codex": "codex",
        "gemini": "gemini",
        "opencode": "opencode",
        "antigravity": "antigravity",
    }
    normalized = client_map.get(client_id, client_id)
    return get_client_runtime_dir(normalized)


def _repair_mcp_configs(repo_root: Path) -> dict[str, Any]:
    """Regenerate managed MCP client configs for the current canonical repo root."""
    configure_script = repo_root / "scripts" / "configure_mcp.py"
    if not configure_script.exists():
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Missing configure script: {configure_script}",
            "returncode": 1,
        }

    result = subprocess_run(  # nosec B603
        [sys.executable, str(configure_script), "--auto", "--verbose"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env={**dict(os.environ), "PYTHONPATH": str(repo_root)},
    )
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def _permission_record(
    *,
    permission_id: str,
    name: str,
    status: str,
    description: str,
    category: str,
    instructions: str,
    detail: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": permission_id,
        "name": name,
        "status": status,
        "description": description,
        "category": category,
        "instructions": instructions,
    }
    if detail:
        record["detail"] = detail
    return record


def _external_tool_permission(
    *,
    permission_id: str,
    name: str,
    command: str,
    description: str,
    install_instructions: str,
) -> dict[str, Any]:
    executable = shutil.which(command)
    if executable:
        return _permission_record(
            permission_id=permission_id,
            name=name,
            status="granted",
            description=description,
            category="dependencies",
            instructions=f"Available at {executable}",
            detail=executable,
        )
    return _permission_record(
        permission_id=permission_id,
        name=name,
        status="not_configured",
        description=description,
        category="dependencies",
        instructions=install_instructions,
    )


def _configured_email_drop_source_count() -> int:
    """Return configured Brain Inbox mail-drop sources without importing skill code."""
    try:
        from src.config.paths import get_runtime_dir

        sources_path = get_runtime_dir() / "brain" / "inbox" / "email_drop_sources.json"
        if not sources_path.is_file():
            return 0
        raw = json.loads(sources_path.read_text(encoding="utf-8"))
    except Exception:
        return 0

    if not isinstance(raw, list):
        return 0
    return sum(1 for item in raw if isinstance(item, dict) and item.get("enabled", True))


def _system_permissions_payload() -> dict[str, Any]:
    platform_id = sys.platform
    permissions: list[dict[str, Any]] = []

    if platform_id == "darwin":
        permissions.extend(
            [
                _permission_record(
                    permission_id="screen_recording",
                    name="Screen Recording",
                    status="unknown",
                    description="Required when Augur records or inspects screen content.",
                    category="macos_system",
                    instructions=(
                        "Open System Settings > Privacy & Security > Screen Recording and enable the terminal "
                        "or app that launches Augur."
                    ),
                ),
                _permission_record(
                    permission_id="microphone",
                    name="Microphone",
                    status="unknown",
                    description="Required for voice capture and local meeting/audio ingestion.",
                    category="macos_system",
                    instructions=(
                        "Open System Settings > Privacy & Security > Microphone and enable the terminal or app "
                        "that launches Augur."
                    ),
                ),
                _permission_record(
                    permission_id="accessibility",
                    name="Accessibility",
                    status="unknown",
                    description="Required for client automation that focuses apps or sends keystrokes.",
                    category="macos_system",
                    instructions=(
                        "Open System Settings > Privacy & Security > Accessibility and enable the terminal "
                        "or app that launches Augur."
                    ),
                ),
                _permission_record(
                    permission_id="calendar",
                    name="Calendar",
                    status="unknown",
                    description="Required for local calendar integrations and schedule-aware workflows.",
                    category="email_calendar",
                    instructions=(
                        "Open System Settings > Privacy & Security > Calendars and enable the terminal or app "
                        "that launches Augur."
                    ),
                ),
                _permission_record(
                    permission_id="apple_mail",
                    name="Apple Mail Automation",
                    status="unknown",
                    description="Required when Augur imports messages from Apple Mail automation flows.",
                    category="email_calendar",
                    instructions=(
                        "Open System Settings > Privacy & Security > Automation and allow the launching app "
                        "to control Mail."
                    ),
                ),
                _permission_record(
                    permission_id="apple_notes",
                    name="Apple Notes Automation",
                    status="unknown",
                    description="Required when Augur reads or routes Apple Notes content.",
                    category="email_calendar",
                    instructions=(
                        "Open System Settings > Privacy & Security > Automation and allow the launching app "
                        "to control Notes."
                    ),
                ),
            ]
        )
    elif platform_id == "win32":
        permissions.extend(
            [
                _permission_record(
                    permission_id="microphone",
                    name="Microphone",
                    status="unknown",
                    description="Required for voice capture and local meeting/audio ingestion.",
                    category="windows_system",
                    instructions=(
                        "Open Settings > Privacy & security > Microphone and allow desktop apps to access "
                        "the microphone."
                    ),
                ),
                _permission_record(
                    permission_id="camera",
                    name="Camera",
                    status="unknown",
                    description="Required for workflows that capture camera input.",
                    category="windows_system",
                    instructions=(
                        "Open Settings > Privacy & security > Camera and allow desktop apps to access " "the camera."
                    ),
                ),
                _permission_record(
                    permission_id="location",
                    name="Location",
                    status="unknown",
                    description="Used by location-aware personal workflows when enabled.",
                    category="windows_system",
                    instructions="Open Settings > Privacy & security > Location and enable access for desktop apps.",
                ),
                _permission_record(
                    permission_id="calendar",
                    name="Calendar",
                    status="unknown",
                    description="Required for local calendar integrations and schedule-aware workflows.",
                    category="windows_system",
                    instructions=(
                        "Open Settings > Privacy & security > Calendar and enable access for the calendar "
                        "provider Augur uses."
                    ),
                ),
                _permission_record(
                    permission_id="notifications",
                    name="Notifications",
                    status="unknown",
                    description="Required for desktop reminders and local workflow notifications.",
                    category="windows_system",
                    instructions=(
                        "Open Settings > System > Notifications and allow notifications for the app that "
                        "launches Augur."
                    ),
                ),
            ]
        )

    email_source_count = _configured_email_drop_source_count()
    permissions.append(
        _permission_record(
            permission_id="email_imap",
            name="Mail Drop Sources",
            status="granted" if email_source_count else "not_configured",
            description=(
                f"{email_source_count} enabled Brain Inbox mail-drop source(s)."
                if email_source_count
                else "No Brain Inbox mail-drop folder is configured yet."
            ),
            category="email_calendar",
            instructions="Add a mail-drop folder from Brain Inbox so saved emails can be scanned and consumed.",
            detail=str(email_source_count),
        )
    )

    permissions.extend(
        [
            _external_tool_permission(
                permission_id="tesseract",
                name="Tesseract OCR",
                command="tesseract",
                description="Used for local OCR on scanned documents and images.",
                install_instructions="Install Tesseract OCR, then restart the Augur dashboard process.",
            ),
            _external_tool_permission(
                permission_id="ffmpeg",
                name="FFmpeg",
                command="ffmpeg",
                description="Used for local audio and video extraction workflows.",
                install_instructions="Install FFmpeg, then restart the Augur dashboard process.",
            ),
            _external_tool_permission(
                permission_id="ollama",
                name="Ollama",
                command="ollama",
                description="Used for local model backends and airplane mode workflows.",
                install_instructions=(
                    "Install Ollama from https://ollama.com/download, then run `ollama serve` or `ollama launch`."
                ),
            ),
        ]
    )

    return {
        "ok": True,
        "platform": platform_id,
        "permissions": permissions,
        "checked_at": datetime.now().isoformat(),
    }


# =============================================================================
# Tool Registration
# =============================================================================


def register_system_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register System Operations tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="list-services",
        annotations=tool_annotations(
            {
                "title": "List Running Services",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_services_tool(status_filter: str | None = None) -> str:
        """List running Augur services.

        Args:
            status_filter: Filter by status (running/stopped)

        Returns:
            str: JSON with services list
        """
        metrics.track_tool("list_services")

        try:
            import platform

            import psutil

            services = []

            # Check for processes using psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    # Broaden detection keywords
                    if any(kw in cmdline.lower() for kw in ['augur', 'mcp', 'exo']):
                        services.append(
                            {
                                "name": proc.info['name'],
                                "pid": proc.info['pid'],
                                "status": "running",
                                "cmdline": cmdline[:100],
                            }
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # macOS specific: Check LaunchAgents via launchctl
            if platform.system() == "Darwin":
                try:
                    # Look for com.augur. services
                    result = _run_command(['launchctl', 'list'], capture_output=True, text=True)
                    if result.returncode == 0:
                        for line in result.stdout.splitlines():
                            if 'com.augur' in line:
                                parts = line.split()
                                if len(parts) >= 3:
                                    pid_val, _, label = parts[0], parts[1], parts[2]
                                    is_running = pid_val != '-'

                                    # If already in psutil list, we might want to skip or update
                                    # For launch agents, we prioritize the launchctl status
                                    services.append(
                                        {
                                            "name": label,
                                            "pid": int(pid_val) if is_running else None,
                                            "status": "running" if is_running else "stopped",
                                            "cmdline": f"LaunchAgent: {label}",
                                        }
                                    )
                except Exception as e:
                    logger.warning(f"Failed to check launchctl: {e}")

            if status_filter:
                services = [s for s in services if s['status'] == status_filter]

            return json.dumps({"services": services}, indent=2)
        except Exception as e:
            logger.error(f"Failed to list services: {e}")
            return json.dumps({"success": False, "error": str(e), "services": []})

    @mcp.tool(
        name="check-system-permissions",
        annotations=tool_annotations(
            {
                "title": "Check System Permissions",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def check_system_permissions_tool() -> str:
        """Return permission and dependency status for the Settings permissions tab."""
        metrics.track_tool("check_system_permissions")
        try:
            payload = await asyncio.to_thread(_system_permissions_payload)
            return json.dumps(payload, indent=2)
        except Exception as e:
            logger.error("Failed to check system permissions: %s", e)
            return json.dumps({"ok": False, "error": str(e), "permissions": []})

    @mcp.tool(
        name="repair-mcp-configs",
        annotations=tool_annotations(
            {
                "title": "Repair MCP Configs",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def repair_mcp_configs_tool() -> str:
        """Regenerate IDE/client MCP configs so they point at the current Augur root."""
        metrics.track_tool("repair_mcp_configs")
        result = await asyncio.to_thread(_repair_mcp_configs, _get_data_dir())
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="analyze-import",
        annotations=tool_annotations(
            {
                "title": "Analyze Document for Import",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def analyze_import_tool(
        file_path: str = "",
        import_type: str | None = None,
        # Dashboard aliases
        project_id: str | None = None,
        source_type: str | None = None,
        url: str | None = None,
    ) -> str:
        """Analyze document before importing to data repo.

        Args:
            file_path: Path to file to analyze (alias: project_id for RAG sources)
            import_type: Type of import (auto-detect if None; alias: source_type)
            project_id: Dashboard alias for file_path (RAG project ID)
            source_type: Dashboard alias for import_type
            url: GitHub URL for URL-based imports

        Returns:
            str: JSON with analysis
        """
        metrics.track_tool("analyze_import")

        # Resolve dashboard aliases
        if not file_path and project_id:
            file_path = project_id
        if not import_type and source_type:
            import_type = source_type

        try:
            file_path_obj = Path(file_path)

            if not file_path_obj.exists():
                return json.dumps({"success": False, "error": f"File not found: {file_path}"})

            analysis = {
                "type": file_path_obj.suffix[1:] if file_path_obj.suffix else "unknown",
                "size": file_path_obj.stat().st_size,
                "name": file_path_obj.name,
                "suggested_dest": f"knowledge/imports/{file_path_obj.name}",
                "metadata": {"import_date": datetime.now().isoformat(), "original_path": str(file_path_obj)},
            }

            return json.dumps(analysis, indent=2)
        except Exception as e:
            logger.error(f"Failed to analyze import: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="apply-import",
        annotations=tool_annotations(
            {
                "title": "Apply Document Import",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def apply_import_tool(params: ApplyImportInput) -> str:
        """Import document to data repo.

        Args:
            params: ApplyImportInput with file_path, destination, and optional metadata

        Returns:
            str: JSON with import result
        """
        metrics.track_tool("apply_import")

        try:
            source = Path(params.file_path)
            dest_dir = _get_data_dir() / params.destination
            dest_dir.mkdir(parents=True, exist_ok=True)

            dest_file = dest_dir / source.name
            shutil.copy2(source, dest_file)

            result = {"success": True, "destination": str(dest_file), "metadata": params.metadata or {}}

            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Failed to apply import: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="system-open",
        annotations=tool_annotations(
            {
                "title": "Open File or URL",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def system_open_tool(
        target: str = "",
        target_type: str = "auto",
        app: str | None = None,
        # Dashboard alias
        path: str | None = None,
    ) -> str:
        """Open file or URL using system default application.

        Args:
            target: File path or URL to open (alias: path)
            target_type: Type of target ('file', 'url', 'auto')
            app: Optional application name to open with (macOS only, e.g. "iA Writer")
            path: Dashboard alias for target

        Returns:
            str: JSON with operation result
        """
        metrics.track_tool("system_open")

        # Resolve dashboard alias
        if not target and path:
            target = path

        if not target:
            return json.dumps({"success": False, "error": "target or path is required"})

        try:
            # Determine target type
            if target_type == "auto":
                if target.startswith(("http://", "https://", "mailto:", "tel:")):
                    target_type = "url"
                else:
                    target_type = "file"

            # Validate file paths
            if target_type == "file":
                target_path = Path(target)
                if not target_path.exists():
                    return json.dumps({"success": False, "error": f"File not found: {target}"})
                target = str(target_path.absolute())

            # Platform-specific open command
            system = platform.system()
            if system == "Darwin":  # macOS
                cmd = ["open"]
                if app:
                    cmd.extend(["-a", app])
                cmd.append(target)
            elif system == "Linux":
                cmd = ["xdg-open", target]
            elif system == "Windows":
                cmd = ["start", "", target]
            else:
                return json.dumps({"success": False, "error": f"Unsupported platform: {system}"})

            logger.info(f"Opening {target_type}: {target}")

            result = await asyncio.to_thread(_run_command, cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                return json.dumps({"success": True, "target": target, "type": target_type})
            else:
                error_msg = result.stderr.strip() or "Failed to open"
                return json.dumps({"success": False, "error": error_msg})

        except TimeoutExpired:
            return json.dumps({"success": False, "error": "Open command timed out (5s)"})
        except Exception as e:
            logger.error(f"Failed to open {target}: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="open-client-runtime-folder",
        annotations=tool_annotations(
            {
                "title": "Open Client Runtime Folder",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def open_client_runtime_folder_tool(params: OpenClientRuntimeInput) -> str:
        """Open a supported client's runtime/config root in the system file manager."""
        metrics.track_tool("open_client_runtime_folder")

        try:
            runtime_dir = _resolve_client_runtime_dir(params.client_id)
            if not runtime_dir.exists():
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Runtime folder not found: {runtime_dir}",
                        "clientId": params.client_id,
                    }
                )

            target = str(runtime_dir.absolute())
            system = platform.system()
            if system == "Darwin":
                cmd = ["open", target]
            elif system == "Linux":
                cmd = ["xdg-open", target]
            elif system == "Windows":
                cmd = ["start", "", target]
            else:
                return json.dumps({"success": False, "error": f"Unsupported platform: {system}"})

            result = await asyncio.to_thread(_run_command, cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return json.dumps(
                    {
                        "success": True,
                        "clientId": params.client_id,
                        "path": target,
                    }
                )
            error_msg = result.stderr.strip() or "Failed to open runtime folder"
            return json.dumps(
                {
                    "success": False,
                    "clientId": params.client_id,
                    "path": target,
                    "error": error_msg,
                }
            )
        except TimeoutExpired:
            return json.dumps({"success": False, "error": "Open command timed out (5s)"})
        except Exception as e:
            logger.error(f"Failed to open client runtime folder for {params.client_id}: {e}")
            return json.dumps({"success": False, "error": str(e), "clientId": params.client_id})

    @mcp.tool(
        name="system-open-file",
        annotations=tool_annotations(
            {
                "title": "Open File in System File Manager",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def system_open_file_tool(
        file_path: str = "",
        # Dashboard aliases
        path: str | None = None,
        line_number: int | None = None,
    ) -> str:
        """Open file in system file manager (Finder/Explorer).

        Args:
            file_path: Path to file to reveal in file manager (alias: path)
            path: Dashboard alias for file_path
            line_number: Optional line number (unused by file manager, accepted for compatibility)

        Returns:
            str: JSON with operation result
        """
        metrics.track_tool("system_open_file")

        # Resolve dashboard alias
        if not file_path and path:
            file_path = path

        if not file_path:
            return json.dumps({"success": False, "error": "file_path or path is required"})

        try:
            target_path = Path(file_path)
            if not target_path.exists():
                return json.dumps({"success": False, "error": f"File not found: {file_path}"})

            target = str(target_path.absolute())

            # Platform-specific reveal command
            system = platform.system()
            if system == "Darwin":  # macOS
                cmd = ["open", "-R", target]
            elif system == "Linux":
                # Open parent directory
                cmd = ["xdg-open", str(target_path.parent)]
            elif system == "Windows":
                cmd = ["explorer", "/select,", target]
            else:
                return json.dumps({"success": False, "error": f"Unsupported platform: {system}"})

            logger.info(f"Opening file in file manager: {target}")

            result = await asyncio.to_thread(_run_command, cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                return json.dumps({"success": True, "file": target})
            else:
                error_msg = result.stderr.strip() or "Failed to open file manager"
                return json.dumps({"success": False, "error": error_msg})

        except TimeoutExpired:
            return json.dumps({"success": False, "error": "File manager command timed out (5s)"})
        except Exception as e:
            logger.error(f"Failed to open file {file_path}: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="service-status",
        annotations=tool_annotations(
            {
                "title": "External Service Availability",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def service_status_tool(skill: str | None = None) -> str:
        """Check availability of external services (MCP servers, CLI tools, apps).

        Reads the external service registry and checks each service's health.
        Optionally filter to services used by a specific skill.

        Args:
            skill: Optional skill name to filter services (e.g., 'career')

        Returns:
            str: JSON with per-service status and summary
        """
        metrics.track_tool("service_status")

        try:
            project_root = _get_data_dir()
            script_path = project_root / ".claude" / "skills" / "daemon" / "scripts" / "service_availability.py"

            if not script_path.exists():
                return json.dumps(
                    {
                        "error": "service_availability.py not found",
                        "services": [],
                        "summary": {"total": 0, "connected": 0, "disconnected": 0, "unknown": 0},
                    }
                )

            mod = _load_module_from_path("service_availability", script_path)

            result = await asyncio.to_thread(mod.get_service_status, skill_name=skill)
            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"Failed to check service status: {e}")
            return json.dumps(
                {
                    "error": str(e),
                    "services": [],
                    "summary": {"total": 0, "connected": 0, "disconnected": 0, "unknown": 0},
                }
            )


__all__ = ["register_system_tools"]
