"""Base adapter for CLI-based code agents (Claude Code, Juls, Codex, etc.)."""

from __future__ import annotations

import shutil
import subprocess
import time
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from .base import BaseAdapter
from src.lib.ai.ide_intent import Intent, AdapterOutput, AdapterOutputType

# Import context types
import sys

project_root = Path(__file__).resolve().parents[3]
package_src = project_root / "src" / "mcp"
if str(package_src) not in sys.path:
    sys.path.insert(0, str(package_src))

if TYPE_CHECKING:
    from src.mcp.augur_shared.context_injector import AugurContext
else:
    AugurContext = Any  # type: ignore[misc, assignment]


class CliAgentAdapter(BaseAdapter):
    """
    Base class for terminal CLI agents.

    Provides context injection via markdown prompt prefixes.
    Subclasses must implement CLI command detection and rendering.
    """

    def __init__(self, ide_name: str, cli_command: str):
        """
        Initialize CLI agent adapter.

        Args:
            ide_name: Name of the IDE/agent (e.g., "claude_code", "juls")
            cli_command: Command to check for (e.g., "claude", "juls")
        """
        super().__init__(ide_name)
        self.cli_command = cli_command

    @abstractmethod
    def get_action_map(self) -> dict[str, str]:
        """
        Get mapping of intent actions to CLI commands.

        Returns:
            Dict mapping action names to CLI command strings.
            Example: {"create_skill": "create-skill", "analyze": "analyze"}
        """
        raise NotImplementedError

    @abstractmethod
    def get_live_test_commands(self) -> dict[str, list[str]]:
        """Return CLI commands for each live test level.

        Keys: "version", "auth", "mcp_list", "prompt"
        Values: list of CLI args (without the base command).
        Example: {"version": ["--version"], "auth": ["info"], "mcp_list": ["mcp", "list"], "prompt": ["-p", "echo test"]}
        """
        raise NotImplementedError

    def detect(self) -> dict[str, Any]:
        """Detect if this CLI agent is available."""
        import os

        installed = False
        running = False
        path = None
        error = None

        # Common installation paths to check (in addition to PATH)
        home = os.path.expanduser("~")
        common_paths = [
            os.path.join(home, ".local", "bin", self.cli_command),
            os.path.join(home, ".npm-global", "bin", self.cli_command),
            os.path.join(home, "bin", self.cli_command),
            f"/usr/local/bin/{self.cli_command}",
            f"/opt/homebrew/bin/{self.cli_command}",
        ]

        try:
            resolved = shutil.which(self.cli_command)
            if resolved:
                installed = True
                path = resolved
                running = True
            else:
                # Check common installation paths
                for check_path in common_paths:
                    if os.path.isfile(check_path) and os.access(check_path, os.X_OK):
                        installed = True
                        path = check_path
                        running = True
                        break

        except Exception as e:
            error = str(e)

        return {"installed": installed, "running": running, "path": path, "error": error}

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """CLI agents typically don't require config files."""
        return {
            "success": True,
            "changed": False,
            "config_paths": [],
            "backup_paths": [],
            "error": None,
            "summary": f"{self.ide_name} CLI doesn't require configuration files",
        }

    def health_check(self) -> dict[str, Any]:
        """Run health checks for CLI agent integration."""
        checks: dict[str, tuple[bool | None, str]] = {}
        overall_healthy = True
        status = "healthy"
        error = None

        detection = self.detect()

        # Check 1: Config present (not applicable)
        checks["config_present"] = (True, "No config required for CLI")

        # Check 2: Connectivity (CLI availability)
        if detection.get("installed"):
            checks["connectivity"] = (True, f"{self.cli_command} CLI is installed")
        else:
            checks["connectivity"] = (False, f"{self.cli_command} CLI not found in PATH")
            overall_healthy = False

        # Check 3: Tool discovery (not applicable for CLI)
        checks["tool_list"] = (None, "Not applicable for CLI")

        # Check 4: End-to-end
        try:
            test_intent = Intent(action="help", params={})
            output = self.render_intent(test_intent)
            if output and output.content:
                checks["end_to_end"] = (True, "Can generate CLI commands")
            else:
                checks["end_to_end"] = (False, "Failed to generate CLI commands")
                overall_healthy = False
        except Exception as e:
            checks["end_to_end"] = (False, f"End-to-end check failed: {e}")
            overall_healthy = False

        if not overall_healthy:
            status = "not_configured" if not detection.get("installed") else "degraded"

        return {
            "healthy": overall_healthy,
            "status": status,
            "checks": checks,
            "last_check": datetime.now().isoformat(),
            "error": error,
        }

    def live_test(self, level: int = 4) -> dict:
        """Run graduated live test probes against the CLI agent.

        Levels:
            0 (binary): Check binary exists and get version.
            1 (auth): Run auth/identity command, check return code.
            2 (mcp_handshake): Run MCP list command, parse tool count.
            3 (tool_invocation): Extended MCP check (same as level 2 + flag).
            4 (round_trip): Run a prompt and verify non-empty output.

        Args:
            level: Maximum test level to run (0-4). Default 4 (all levels).

        Returns:
            Structured result dict with per-level outcomes.
        """
        level = max(0, min(4, level))
        start_total = time.monotonic()

        commands = self.get_live_test_commands()
        binary_path = shutil.which(self.cli_command)

        level_defs = [
            ("0_binary", "version", 3),
            ("1_auth", "auth", 5),
            ("2_mcp_handshake", "mcp_list", 10),
            ("3_tool_invocation", "mcp_list", 10),
            ("4_round_trip", "prompt", 60),
        ]

        levels: dict[str, dict] = {}
        failed = False

        for i, (level_key, cmd_key, timeout_s) in enumerate(level_defs):
            if i > level:
                break

            if failed:
                levels[level_key] = {
                    "pass": False,
                    "skipped": True,
                    "duration_ms": 0,
                    "details": {"reason": "prior level failed"},
                }
                continue

            cmd_args = commands.get(cmd_key, [])
            if not cmd_args:
                levels[level_key] = {
                    "pass": None,
                    "skipped": True,
                    "duration_ms": 0,
                    "details": {"reason": "no command configured"},
                }
                continue

            # Level 0 special: also check binary path
            if i == 0:
                if not binary_path:
                    levels[level_key] = {
                        "pass": False,
                        "duration_ms": 0,
                        "details": {"error": f"{self.cli_command} not found in PATH", "binary_path": None},
                    }
                    failed = True
                    continue

            start = time.monotonic()
            try:
                result = subprocess.run(
                    [self.cli_command] + cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
                elapsed_ms = int((time.monotonic() - start) * 1000)

                details: dict[str, Any] = {
                    "return_code": result.returncode,
                    "stdout_length": len(result.stdout),
                }

                if i == 0:
                    # Parse version from stdout
                    version = result.stdout.strip().split("\n")[0] if result.stdout.strip() else None
                    details["version"] = version
                    details["binary_path"] = binary_path
                    passed = result.returncode == 0

                elif i == 1:
                    passed = result.returncode == 0

                elif i in (2, 3):
                    passed = result.returncode == 0
                    # Try to parse tool count from output
                    stdout = result.stdout.strip()
                    tool_count = None
                    for line in stdout.split("\n"):
                        line_stripped = line.strip()
                        # Heuristic: look for numbers that might be tool counts
                        if line_stripped.isdigit():
                            tool_count = int(line_stripped)
                            break
                    details["tool_count"] = tool_count
                    if i == 3:
                        details["extended_check"] = True

                elif i == 4:
                    passed = result.returncode == 0 and len(result.stdout.strip()) > 0
                    if result.stdout.strip():
                        # Include first 200 chars of output
                        details["output_preview"] = result.stdout.strip()[:200]

                else:
                    passed = result.returncode == 0

                if result.stderr.strip():
                    details["stderr_preview"] = result.stderr.strip()[:200]

                levels[level_key] = {"pass": passed, "duration_ms": elapsed_ms, "details": details}
                if not passed:
                    failed = True

            except FileNotFoundError:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                levels[level_key] = {
                    "pass": False,
                    "duration_ms": elapsed_ms,
                    "details": {"error": f"{self.cli_command} binary not found"},
                }
                failed = True

            except subprocess.TimeoutExpired:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                levels[level_key] = {
                    "pass": False,
                    "duration_ms": elapsed_ms,
                    "details": {"error": f"timeout after {timeout_s}s"},
                }
                failed = True

            except Exception as e:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                levels[level_key] = {
                    "pass": False,
                    "duration_ms": elapsed_ms,
                    "details": {"error": str(e)},
                }
                failed = True

        total_ms = int((time.monotonic() - start_total) * 1000)

        # Determine overall status
        passes = [v.get("pass") for v in levels.values() if v.get("pass") is not None]
        if not passes:
            overall = "fail"
        elif all(passes):
            overall = "pass"
        elif any(passes):
            overall = "partial"
        else:
            overall = "fail"

        return {
            "agent": self.ide_name,
            "cli_command": self.cli_command,
            "timestamp": datetime.now().isoformat(),
            "overall": overall,
            "max_level": level,
            "duration_ms": total_ms,
            "levels": levels,
        }

    def inject_context(self, intent: Intent, context: AugurContext) -> Intent:
        """
        Inject Augur context into intent as markdown prompt prefix.

        Args:
            intent: The original intent
            context: AugurContext with sprint, slash commands, etc.

        Returns:
            Modified intent with context injected into params
        """
        # Convert context to markdown
        context_md = context.to_prompt()

        # Get existing prompt or create one
        existing_prompt = intent.params.get("prompt", "")

        # Inject context at the beginning
        enhanced_prompt = f"""{context_md}

---

## Task

{existing_prompt}
"""

        # Create new intent with enhanced prompt
        enhanced_params = intent.params.copy()
        enhanced_params["prompt"] = enhanced_prompt
        enhanced_params["_context_injected"] = True

        return Intent(action=intent.action, params=enhanced_params, context=intent.context, workspace=intent.workspace)

    def render_intent(self, intent: Intent) -> AdapterOutput:
        """
        Translate intent to CLI command format.

        Args:
            intent: The intent to translate

        Returns:
            AdapterOutput with CLI_COMMAND type
        """
        action_map = self.get_action_map()
        cmd_action = action_map.get(intent.action, intent.action)

        # Build command line arguments
        params_str = " ".join(
            f"--{k}={v}" for k, v in intent.params.items() if not k.startswith("_")  # Skip internal params
        )

        command = f"{self.cli_command} {cmd_action} {params_str}".strip()

        # Build markdown documentation
        content = f"""# {self.ide_name.replace('_', ' ').title()} CLI Command

Run this command in your terminal:

```bash
{command}
```

## Action
`{intent.action}`

## Parameters
{chr(10).join(f"- `{k}`: {v}" for k, v in intent.params.items() if not k.startswith("_")) if intent.params else "None"}

## Workspace
{intent.workspace or "Not specified"}
"""

        return AdapterOutput(
            output_type=AdapterOutputType.CLI_COMMAND,
            content=content,
            metadata={"command": command, "action": intent.action, "cli_tool": self.cli_command},
        )

    def get_execution_mode(self) -> str:
        """Get primary execution mode."""
        return "cli"

    def get_supported_fallbacks(self) -> list[str]:
        """Get supported fallback modes."""
        return ["chat_prompt"]  # Can always fall back to generating a chat prompt

    def get_capabilities(self):
        """
        Get agent capabilities for routing.

        Returns:
            AgentCapabilities object
        """
        # Import here to avoid circular dependency
        from src.lib.ai.agent_capabilities import AgentCapabilities

        # Get health status
        health = self.health_check()
        health_status = health.get("status", "unknown")

        return AgentCapabilities(
            agent_name=self.ide_name,
            agent_type="cli",
            has_sprint_context=True,  # All Augur agents get context
            has_slash_commands=True,
            has_factory_insights=True,
            can_execute_code=True,
            can_modify_files=True,
            specializations=["debugging", "code_generation", "testing"],
            health_status=health_status,
            execution_mode=self.get_execution_mode(),
            supported_fallbacks=self.get_supported_fallbacks(),
        )
