"""
IDE Integration tool implementations.

Core infrastructure tools for IDE communication and status.

NOTE: The following tools have been moved to skills (ADR-012):
- generate-ide-instructions → apps/dashboard/scripts/skill-scripts/mcp/ (was skills/mcp-app-factory)
"""

# TODO_CLEANUP: This file is 932 lines — consider splitting into smaller modules

import asyncio
import json
import re
import subprocess  # nosec B404
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from pydantic import BaseModel, ConfigDict, Field
from src.config.paths import get_project_brain_skills_dir, get_python_executable
from src.lib.agent_cli_config import (
    build_agent_command,
    resolve_agent_cli_config,
    resolve_cli_path,
)
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.logging import get_entity_logger
from src.mcp.augur_shared.safe_subprocess import safe_run

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp")

# Project root for path resolution
PROJECT_ROOT = Path(__file__).resolve().parents[4]
SKILLS_DIR = get_project_brain_skills_dir(PROJECT_ROOT)
AI_SCRIPTS_DIR = SKILLS_DIR / "ai" / "scripts"


# =============================================================================
# Pydantic Input Models
# =============================================================================


class IdeIntegrationsInput(BaseModel):
    """Input for ide-integrations tool."""

    model_config = ConfigDict(extra="forbid")
    action: str = Field("list", description="Action: list, status, configure")
    ide: str | None = Field(None, description="IDE to target: cursor, vscode, windsurf")


class ClientTestInput(BaseModel):
    """Input for client-test tool."""

    model_config = ConfigDict(extra="forbid")
    agent: str = Field("all", description="Agent to test (e.g., kimi, claude, opencode) or 'all'")
    level: int = Field(4, description="Max test level 0-4 (0=binary, 1=auth, 2=mcp, 3=tool, 4=round-trip)")
    quick: bool = Field(False, description="Quick mode: levels 0-2 only, no LLM API calls")


class IdeLifecycleInput(BaseModel):
    """Input for ide-lifecycle tool."""

    model_config = ConfigDict(extra="forbid")
    action: str = Field(..., description="Action: enable, disable, detect")
    ide: str | None = Field(
        None, description="IDE adapter key (e.g. 'cursor', 'claude_code'). Required for enable/disable."
    )


# =============================================================================
# Tool Registration
# =============================================================================


def register_ide_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register IDE Integration tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="send-ide-prompt",
        annotations=tool_annotations(
            {
                "title": "Send Prompt to IDE",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def send_ide_prompt_tool(prompt: str, context: dict | None = None) -> str:
        """Send prompt to IDE for LLM processing.

        Sends prompt to connected IDE (VS Code, Cursor, Claude Code) for AI processing.
        Used for action buttons that trigger AI workflows.

        Args:
            prompt: Prompt to send to IDE
            context: Optional additional context

        Returns:
            str: JSON with send result {success, message, ide, prompt_id}
        """
        metrics.track_tool("send_ide_prompt")

        try:
            ide_bridge_script = AI_SCRIPTS_DIR / "ide_bridge.py"
            if not ide_bridge_script.exists():
                return json.dumps({"success": False, "error": f"IDE bridge script not found: {ide_bridge_script}"})

            # Build command args
            cmd = [
                str(get_python_executable()),
                str(ide_bridge_script),
                "--json",
                "--action",
                "prompt",
                "--content",
                prompt,
            ]

            # Add IDE preference from context if provided
            if context and isinstance(context, dict) and context.get("ide"):
                cmd.extend(["--ide", context["ide"]])

            logger.info(f"Sending prompt to IDE: {prompt[:50]}...")

            # Run blocking subprocess in a thread
            result = await asyncio.to_thread(
                safe_run, cmd, cwd=SKILLS_DIR.parent, capture_output=True, text=True, timeout=20, encoding="utf-8"
            )

            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout.strip())
                    return json.dumps(response, indent=2)
                except json.JSONDecodeError:
                    return json.dumps(
                        {
                            "success": True,
                            "message": result.stdout.strip() or "Prompt sent to IDE",
                            "output": result.stdout.strip(),
                        }
                    )
            else:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                logger.error(f"IDE bridge failed: {error_msg}")
                return json.dumps({"success": False, "error": error_msg})

        except subprocess.TimeoutExpired:
            logger.error("IDE bridge timed out after 10s")
            return json.dumps({"success": False, "error": "IDE bridge timed out (10s)"})
        except Exception as e:
            logger.error(f"Failed to send IDE prompt: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="run-oneshot-cli",
        annotations=tool_annotations(
            {
                "title": "Run Oneshot CLI",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def run_oneshot_cli_tool(prompt: str, timeout_s: int = 60) -> str:
        """Execute a prompt via the configured default CLI in headless mode.

        Reads runtime client_routing.default_client via ClientResolver, then
        resolves the command from vault config/ai/cli_agents.yaml.
        Used for oneshot action dispatch (non-interactive AI calls).

        Args:
            prompt: Prompt to execute
            timeout_s: Timeout in seconds (default 60)

        Returns:
            str: JSON with {success, output} or {success, error}
        """
        metrics.track_tool("run_oneshot_cli")

        try:
            agent = resolve_agent_cli_config(
                "run-oneshot-cli",
                command_fields=("oneshot_cmd", "print_cmd"),
            )
            if agent.error:
                return json.dumps({"success": False, "error": agent.error})

            cli_name = agent.cli_id
            command_cli = agent.command[0] if agent.command else cli_name
            cli_path = resolve_cli_path(command_cli)
            if not cli_path:
                return json.dumps({"success": False, "error": f"CLI '{command_cli}' not found"})

            cmd = build_agent_command(
                cli_path,
                cli_name,
                prompt,
                configured_command=agent.command,
                job_dir=PROJECT_ROOT,
            )

            logger.info("Running oneshot CLI: %s (prompt: %d chars, timeout: %ds)", cli_name, len(prompt), timeout_s)

            env = None
            if agent.env:
                import os  # noqa: PLC0415

                env = os.environ.copy()
                env.update(agent.env)

            result = await asyncio.to_thread(
                safe_run,
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                encoding="utf-8",
                env=env,
            )

            output = result.stdout.strip()
            if result.returncode == 0:
                return json.dumps({"success": True, "output": output or "Completed (no output)"})
            else:
                error_msg = result.stderr.strip() or output or "CLI exited with non-zero status"
                logger.error("Oneshot CLI failed (exit %d): %s", result.returncode, error_msg[:200])
                return json.dumps({"success": False, "error": error_msg, "output": output})

        except subprocess.TimeoutExpired:
            logger.error("Oneshot CLI timed out after %ds", timeout_s)
            return json.dumps({"success": False, "error": f"CLI timed out after {timeout_s}s"})
        except Exception as e:
            logger.error("Oneshot CLI error: %s", e)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-ide-history",
        annotations=tool_annotations(
            {
                "title": "Get IDE Prompt History",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_ide_history_tool(limit: int = 10) -> str:
        """Get recent IDE prompt history.

        Args:
            limit: Maximum number of history items to return

        Returns:
            str: JSON with history items
        """
        metrics.track_tool("get_ide_history")

        try:
            ide_bridge_script = AI_SCRIPTS_DIR / "ide_bridge.py"
            if not ide_bridge_script.exists():
                return json.dumps({"success": False, "error": f"IDE bridge script not found: {ide_bridge_script}"})

            # Note: ide_bridge.py doesn't support --limit, so we limit in Python after getting results
            cmd = [str(get_python_executable()), str(ide_bridge_script), "--json", "--action", "history"]

            logger.info(f"Getting IDE history (will limit to {limit} items)")

            # Run blocking subprocess in a thread
            result = await asyncio.to_thread(
                safe_run, cmd, cwd=SKILLS_DIR.parent, capture_output=True, text=True, timeout=20, encoding="utf-8"
            )

            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout.strip())
                    # Apply limit to history items in Python
                    if "history" in response and isinstance(response["history"], list):
                        response["history"] = response["history"][:limit]
                    return json.dumps(response, indent=2)
                except json.JSONDecodeError:
                    return json.dumps(
                        {"success": True, "history": [], "message": result.stdout.strip() or "No history"}
                    )
            else:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                logger.error(f"IDE history failed: {error_msg}")
                return json.dumps({"success": False, "error": error_msg})

        except subprocess.TimeoutExpired:
            logger.error("IDE history timed out after 10s")
            return json.dumps({"success": False, "error": "IDE history timed out (10s)"})
        except Exception as e:
            logger.error(f"Failed to get IDE history: {e}")
            return json.dumps({"success": False, "error": str(e)})

    class _IdeStatusCache(TypedDict):
        timestamp: float
        data: str | None

    # Cache for IDE status
    _ide_status_cache: _IdeStatusCache = {"timestamp": 0.0, "data": None}

    _KNOWN_INTEGRATION_KEYS = {
        "antigravity",
        "claude_code",
        "claude_desktop",
        "cline",
        "codex",
        "copilot",
        "cowork",
        "cursor",
        "gemini",
        "juls",
        "kimi",
        "ollama",
        "opencode",
        "windsurf",
        "claude_sdk",
    }

    def _canonical_integration_key(raw_name: str | None) -> str | None:
        if not raw_name:
            return None
        normalized = raw_name.strip().lower()
        normalized = re.sub(r"[\s\-]+", "_", normalized)
        if normalized in _KNOWN_INTEGRATION_KEYS:
            return normalized
        return None

    def _detect_running_integrations_via_processes() -> set[str]:
        """Best-effort process scan to detect running GUI apps and CLI tools."""
        detected: set[str] = set()

        try:
            result = safe_run(
                ["ps", "-ax", "-o", "command="],
                capture_output=True,
                text=True,
                timeout=4,
                encoding="utf-8",
            )
            if result.returncode != 0:
                return detected

            for command in result.stdout.splitlines():
                line = command.lower().strip()

                # Desktop apps
                if "/applications/claude.app/" in line:
                    detected.add("claude_desktop")
                if "/applications/antigravity.app/" in line:
                    detected.add("antigravity")
                if "/applications/codex.app/" in line or "codex app-server" in line:
                    detected.add("codex")
                if "/applications/cursor.app/" in line:
                    detected.add("cursor")

                # CLI binaries (avoid app bundle helper noise where possible)
                if re.search(r"(^|[ /])claude([ /]|$)", line) and "claude.app" not in line:
                    detected.add("claude_code")
                if re.search(r"(^|[ /])codex([ /]|$)", line):
                    detected.add("codex")
                if re.search(r"(^|[ /])gemini([ /]|$)", line):
                    detected.add("gemini")
                if re.search(r"(^|[ /])opencode([ /]|$)", line):
                    detected.add("opencode")
                if re.search(r"(^|[ /])kimi([ /]|$)", line):
                    detected.add("kimi")
                if re.search(r"(^|[ /])cline([ /]|$)", line):
                    detected.add("cline")

        except Exception as e:
            logger.debug(f"Process-based IDE/CLI detection skipped: {e}")

        return detected

    @mcp.tool(
        name="get-ide-status",
        annotations=tool_annotations(
            {
                "title": "Get IDE Connection Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_ide_status_tool() -> str:
        """Get current IDE connection status.

        Returns:
            str: JSON with IDE status (connected, ide_name, version, etc.)
        """
        metrics.track_tool("get_ide_status")

        # Check cache (15s TTL)
        now = datetime.now().timestamp()
        cache_data = _ide_status_cache["data"]
        if cache_data and (now - _ide_status_cache["timestamp"] < 15):
            return cache_data

        try:
            # Optimization: Use ctypes to check processes directly
            # This avoids subprocess overhead entirely and is much faster (~400ms vs ~1.6s+)
            import ctypes
            import platform
            from ctypes import wintypes

            connected = False
            ide_name = None
            response_data: dict[str, Any] = {"success": True, "active_ide": None, "available_ides": []}

            if platform.system() == "Windows":
                # Define constants and structures for ToolHelp32
                TH32CS_SNAPPROCESS = 0x00000002

                class PROCESSENTRY32(ctypes.Structure):
                    _fields_ = [
                        ("dwSize", wintypes.DWORD),
                        ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", wintypes.DWORD),
                        ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", wintypes.LONG),
                        ("dwFlags", wintypes.DWORD),
                        ("szExeFile", ctypes.c_char * 260),
                    ]

                try:
                    windll = getattr(ctypes, "windll", None)
                    if windll is None:
                        raise AttributeError("ctypes.windll is unavailable on this platform")
                    kernel32 = windll.kernel32
                    hProcessSnap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)

                    if hProcessSnap != -1:
                        pe32 = PROCESSENTRY32()
                        pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)

                        ide_map = {
                            "cursor.exe": "cursor",
                            "code.exe": "vscode",
                            "claude.exe": "claude",
                            "antigravity.exe": "antigravity",
                        }

                        if kernel32.Process32First(hProcessSnap, ctypes.byref(pe32)):
                            while True:
                                exe_name = pe32.szExeFile.decode("utf-8", "ignore").lower()

                                # Check against our map
                                for proc_name, name in ide_map.items():
                                    if proc_name in exe_name:
                                        connected = True
                                        ide_name = name
                                        if name == "antigravity":  # Prioritize Antigravity
                                            break

                                if connected and ide_name == "antigravity":
                                    break

                                if not kernel32.Process32Next(hProcessSnap, ctypes.byref(pe32)):
                                    break

                        kernel32.CloseHandle(hProcessSnap)
                except Exception as e:
                    logger.error(f"ctypes process check failed: {e}")
                    # Fallback to empty if ctypes fails
                    pass

                if connected:
                    response_data = {"success": True, "active_ide": ide_name, "available_ides": [ide_name]}

            else:
                # Fallback to ide_bridge.py for non-Windows or complex logic
                ide_bridge_script = AI_SCRIPTS_DIR / "ide_bridge.py"
                cmd = [str(get_python_executable()), str(ide_bridge_script), "--json", "--action", "status"]

                result = await asyncio.to_thread(
                    safe_run,
                    cmd,
                    cwd=SKILLS_DIR.parent,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding="utf-8",
                )

                if result.returncode == 0:
                    response_data = json.loads(result.stdout.strip())
                else:
                    response_data = {"success": True, "active_ide": None, "available_ides": []}

            if not isinstance(response_data, dict):
                response_data = {"success": True, "active_ide": None, "available_ides": []}

            # Parse legacy status names into canonical integration keys.
            running_keys: set[str] = set()
            active_candidate = response_data.get("active_ide")
            if isinstance(active_candidate, str):
                key = _canonical_integration_key(active_candidate)
                if key:
                    running_keys.add(key)

            available_candidates = response_data.get("available_ides")
            if isinstance(available_candidates, list):
                for candidate in available_candidates:
                    if isinstance(candidate, str):
                        key = _canonical_integration_key(candidate)
                        if key:
                            running_keys.add(key)

            # Augment with process scan so CLI processes are reflected in status.
            running_keys.update(await asyncio.to_thread(_detect_running_integrations_via_processes))

            available_ides = response_data.get("available_ides")
            available_names = (
                [item for item in available_ides if isinstance(item, str)] if isinstance(available_ides, list) else []
            )
            for key in sorted(running_keys):
                if key not in available_names:
                    available_names.append(key)

            active_ide = response_data.get("active_ide")
            if not isinstance(active_ide, str) or not active_ide:
                active_ide = available_names[0] if available_names else None

            response_data["success"] = bool(response_data.get("success", True))
            response_data["active_ide"] = active_ide
            response_data["available_ides"] = available_names

            json_response = json.dumps(response_data, indent=2)

            # Cache result
            _ide_status_cache["timestamp"] = now
            _ide_status_cache["data"] = json_response

            return json_response

        except subprocess.TimeoutExpired:
            logger.error("IDE status timed out after 10s")
            return json.dumps(
                {"success": False, "connected": False, "error": "IDE status timed out (10s)", "statusCode": 408}
            )
        except Exception as e:
            logger.error(f"Failed to get IDE status: {e}")
            return json.dumps({"success": False, "connected": False, "error": str(e), "statusCode": 500})

    @mcp.tool(
        name="ide-integrations",
        annotations=tool_annotations(
            {
                "title": "IDE Integrations",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def ide_integrations(params: IdeIntegrationsInput) -> str:
        """Manage IDE integrations and configurations.

        Lists available IDEs, checks integration status, and helps configure
        MCP connections for different development environments.

        Args:
            params: IdeIntegrationsInput with action and optional IDE target

        Returns:
            str: JSON with IDE integration information
        """
        metrics.track_tool("ide_integrations")

        try:
            # Common IDE config locations
            home = Path.home()
            ide_configs: dict[str, dict[str, Any]] = {
                "cursor": {
                    "config_path": home / ".cursor" / "mcp.json",
                    "name": "Cursor",
                    "supports_mcp": True,
                },
                "vscode": {
                    "config_path": home / ".vscode" / "settings.json",
                    "name": "VS Code",
                    "supports_mcp": False,  # Not directly
                },
                "windsurf": {
                    "config_path": home / ".windsurf" / "mcp.json",
                    "name": "Windsurf",
                    "supports_mcp": True,
                },
                "claude_desktop": {
                    "config_path": home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
                    "name": "Claude Desktop",
                    "supports_mcp": True,
                },
                "antigravity": {
                    "config_path": home / ".gemini" / "antigravity" / "mcp_config.json",
                    "name": "Antigravity",
                    "supports_mcp": True,
                },
            }

            if params.action == "list":
                ides = []
                for ide_id, config in ide_configs.items():
                    config_path = config.get("config_path")
                    config_exists = isinstance(config_path, Path) and config_path.exists()
                    ides.append(
                        {
                            "id": ide_id,
                            "name": config["name"],
                            "supports_mcp": config["supports_mcp"],
                            "config_exists": config_exists,
                        }
                    )
                return json.dumps({"ides": ides}, indent=2)

            elif params.action == "status":
                if params.ide and params.ide in ide_configs:
                    config = ide_configs[params.ide]
                    config_path = config.get("config_path")
                    config_exists = isinstance(config_path, Path) and config_path.exists()
                    mcp_configured = False

                    if config_exists and config["supports_mcp"] and isinstance(config_path, Path):
                        try:
                            content = json.loads(config_path.read_text())
                            mcp_configured = "mcpServers" in content and "augur" in content.get("mcpServers", {})
                        except Exception as e:
                            logger.warning(f"Unable to parse IDE config {config_path}: {e}")

                    return json.dumps(
                        {
                            "ide": params.ide,
                            "name": config["name"],
                            "config_exists": config_exists,
                            "mcp_configured": mcp_configured,
                            "config_path": str(config_path) if isinstance(config_path, Path) else "",
                        },
                        indent=2,
                    )
                else:
                    # Return all statuses
                    statuses = []
                    for ide_id, config in ide_configs.items():
                        config_path = config.get("config_path")
                        config_exists = isinstance(config_path, Path) and config_path.exists()
                        statuses.append(
                            {
                                "ide": ide_id,
                                "name": config["name"],
                                "config_exists": config_exists,
                            }
                        )
                    return json.dumps({"statuses": statuses}, indent=2)

            else:
                return json.dumps(
                    {
                        "error": f"Unknown action: {params.action}",
                        "valid_actions": ["list", "status", "configure"],
                    },
                    indent=2,
                )

        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                },
                indent=2,
            )

    @mcp.tool(
        name="client-test",
        annotations=tool_annotations(
            {
                "title": "CLI Agent Live Test",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def client_test_tool(params: ClientTestInput) -> str:
        """Run live end-to-end test against CLI agents.

        Tests CLI agents with graduated probes: binary check, auth validation,
        MCP handshake, tool invocation, and full round-trip prompt execution.

        Args:
            params: ClientTestInput with agent name, level, and quick mode flag

        Returns:
            str: JSON with test results per agent and per level
        """
        metrics.track_tool("client_test")

        try:
            script = AI_SCRIPTS_DIR / "client_live_test.py"
            if not script.exists():
                return json.dumps({"success": False, "error": f"Script not found: {script}"})

            cmd = [str(get_python_executable()), str(script), "--json"]

            if params.agent == "all":
                cmd.append("--all")
            else:
                cmd.extend(["--agent", params.agent])

            cmd.extend(["--level", str(params.level)])

            if params.quick:
                cmd.append("--quick")

            logger.info(f"Running client test: agent={params.agent}, level={params.level}, quick={params.quick}")

            result = await asyncio.to_thread(
                safe_run,
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
            )

            if result.returncode == 0 or result.stdout.strip():
                try:
                    response = json.loads(result.stdout.strip())
                    return json.dumps(response, indent=2)
                except json.JSONDecodeError:
                    return json.dumps(
                        {
                            "success": True,
                            "output": result.stdout.strip(),
                        }
                    )
            else:
                error_msg = result.stderr.strip() or "Unknown error"
                return json.dumps({"success": False, "error": error_msg})

        except subprocess.TimeoutExpired:
            return json.dumps({"success": False, "error": "Client test timed out (120s)"})
        except Exception as e:
            logger.error(f"Client test failed: {e}")
            return json.dumps({"success": False, "error": str(e)})

    # ── IDE Lifecycle helpers ────────────────────────────────────

    def _get_all_adapters():
        """Load all sync_agents adapters for lifecycle operations."""
        import importlib  # noqa: PLC0415

        scripts_dir = str(AI_SCRIPTS_DIR)
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        adapter_modules = {
            "claude_code": "ClaudeCodeAdapter",
            "claude_desktop": "ClaudeDesktopAdapter",
            "cursor": "CursorAdapter",
            "windsurf": "WindsurfAdapter",
            "cline": "ClineAdapter",
            "copilot": "CopilotAdapter",
            "gemini": "GeminiAdapter",
            "opencode": "OpenCodeAdapter",
            "kimi": "KimiAdapter",
            "antigravity": "AntigravityAdapter",
            "codex": "CodexAdapter",
        }

        adapters = []
        for mod_name, cls_name in adapter_modules.items():
            try:
                mod = importlib.import_module(f"sync_agents.adapters.{mod_name}")
                cls = getattr(mod, cls_name)
                adapters.append(cls())
            except Exception as e:
                logger.warning(f"Failed to load adapter {mod_name}: {e}")
        return adapters

    # ── IDE Lifecycle tool ───────────────────────────────────────

    @mcp.tool(
        name="ide-lifecycle",
        annotations=tool_annotations(
            {
                "title": "IDE Lifecycle Management",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def ide_lifecycle_tool(params: IdeLifecycleInput) -> str:
        """Manage IDE integration lifecycle: enable, disable, or detect installations.

        Actions:
        - detect: Scan filesystem for installed IDEs, update config
        - enable: Enable an IDE adapter for sync
        - disable: Disable an IDE adapter and clean up generated files

        Args:
            params: IdeLifecycleInput with action and optional IDE key

        Returns:
            str: JSON with operation results
        """
        metrics.track_tool("ide_lifecycle")

        ide_config_path = PROJECT_ROOT / "config" / "agents" / "ide_integrations.yaml"

        try:
            import yaml as pyyaml  # noqa: PLC0415
        except ImportError:
            return json.dumps({"success": False, "error": "PyYAML not available"})

        def _load_config():
            if not ide_config_path.exists():
                return {"integrations": {}, "schema_version": 1}
            with open(ide_config_path, encoding="utf-8") as f:
                return pyyaml.safe_load(f) or {"integrations": {}, "schema_version": 1}

        def _save_config(config):
            ide_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(ide_config_path, "w", encoding="utf-8") as f:
                pyyaml.dump(config, f, default_flow_style=False, sort_keys=False)

        if params.action == "list":
            # Return all integrations from YAML config (no filesystem scan)
            config = _load_config()
            integrations = config.get("integrations", {})
            return json.dumps({"success": True, "action": "list", "integrations": integrations}, indent=2)

        elif params.action == "detect":
            adapters = _get_all_adapters()
            config = _load_config()
            results = {}
            for adapter in adapters:
                name = adapter.adapter_name
                installed = adapter.detect_installed()
                managed = adapter.get_managed_files()
                if name not in config["integrations"]:
                    config["integrations"][name] = {"enabled": True}
                config["integrations"][name]["installed"] = installed
                config["integrations"][name]["managed_files"] = managed
                results[name] = {"installed": installed, "managed_files": managed}
            _save_config(config)
            return json.dumps({"success": True, "action": "detect", "results": results}, indent=2)

        elif params.action == "enable":
            if not params.ide:
                return json.dumps({"success": False, "error": "IDE key required for enable"})
            config = _load_config()
            if params.ide not in config["integrations"]:
                config["integrations"][params.ide] = {}
            config["integrations"][params.ide]["enabled"] = True
            _save_config(config)
            return json.dumps(
                {
                    "success": True,
                    "action": "enable",
                    "ide": params.ide,
                    "message": f"Enabled {params.ide}. Run /sync-agents to regenerate config files.",
                },
                indent=2,
            )

        elif params.action == "disable":
            if not params.ide:
                return json.dumps({"success": False, "error": "IDE key required for disable"})
            config = _load_config()
            if params.ide not in config["integrations"]:
                config["integrations"][params.ide] = {}
            config["integrations"][params.ide]["enabled"] = False
            _save_config(config)

            # Find and run cleanup on matching adapter
            deleted = []
            adapters = _get_all_adapters()
            for adapter in adapters:
                if adapter.adapter_name == params.ide:
                    deleted = adapter.cleanup()
                    break

            return json.dumps(
                {
                    "success": True,
                    "action": "disable",
                    "ide": params.ide,
                    "deleted_files": deleted,
                    "message": f"Disabled {params.ide}. {len(deleted)} file(s) cleaned up.",
                },
                indent=2,
            )

        else:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Unknown action: {params.action}. Valid: enable, disable, detect",
                }
            )


__all__ = ["register_ide_tools"]
