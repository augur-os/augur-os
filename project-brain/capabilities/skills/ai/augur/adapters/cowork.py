"""Claude Cowork adapter.

Cowork is Anthropic's agentic desktop tool built into Claude Desktop.
It runs inside Claude Desktop but targets non-developer knowledge workers
through a GUI interface.

Detection: Reuses Claude Desktop process check but adds Cowork-specific
distinction via the Claude Desktop config feature flags.

Dispatch: Writes prompt files to state/cowork-dispatch/ directory.
Cowork's folder instructions include a rule to check this directory
for pending tasks on startup.
"""

from __future__ import annotations

import json as _json
import os
import platform
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, check_output  # nosec B404
from typing import Any, Optional

from src.config.paths import get_client_runtime_dir

from .base import BaseAdapter
from src.lib.ai.ide_intent import Intent, AdapterOutput, AdapterOutputType


# Dispatch directory relative to the canonical state root.
COWORK_DISPATCH_SUBDIR = "cowork-dispatch"


class CoworkAdapter(BaseAdapter):
    """Adapter for Claude Cowork (agentic desktop tool inside Claude Desktop)."""

    def __init__(self):
        super().__init__("cowork")

    def _get_claude_config_path(self) -> Path:
        """Get the Claude Desktop config.json path for the current platform."""
        home = Path.home()
        if platform.system() == "Darwin":
            return home / "Library" / "Application Support" / "Claude" / "config.json"
        elif platform.system() == "Windows":
            app_data = Path(os.environ.get("APPDATA", ""))
            return app_data / "Claude" / "config.json"
        else:
            # Linux: follow XDG convention
            config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
            return config_home / "Claude" / "config.json"

    def _get_claude_desktop_config_path(self) -> Path:
        """Get the Claude Desktop MCP config path."""
        return get_client_runtime_dir("claude-desktop") / "claude_desktop_config.json"

    def _is_claude_desktop_installed(self) -> tuple[bool, str | None]:
        """Check if Claude Desktop is installed. Returns (installed, path)."""
        if platform.system() == "Darwin":
            app_path = Path("/Applications/Claude.app")
            if app_path.exists():
                return True, str(app_path)
        elif platform.system() == "Windows":
            app_data = Path(os.environ.get("LOCALAPPDATA", ""))
            claude_exe = app_data / "Programs" / "Claude" / "Claude.exe"
            if claude_exe.exists():
                return True, str(claude_exe)
        return False, None

    def _is_claude_desktop_running(self) -> bool:
        """Check if Claude Desktop process is running."""
        try:
            if platform.system() == "Darwin":
                output = check_output(  # nosec B603 B607
                    ["ps", "-ax", "-o", "comm="], text=True, encoding="utf-8"
                )
                return any(
                    line.strip().endswith("/Contents/MacOS/Claude")
                    for line in output.splitlines()
                )
            elif platform.system() == "Windows":
                output = check_output(  # nosec B603 B607
                    ["tasklist", "/FI", "IMAGENAME eq Claude.exe", "/NH"],
                    text=True,
                    stderr=DEVNULL,
                )
                return "Claude.exe" in output
        except Exception:
            pass
        return False

    def _has_cowork_feature(self) -> bool:
        """Check if the Cowork feature flag is set in Claude Desktop config.

        Cowork is distinguished from plain Claude Desktop by checking for
        the 'cowork' or 'agent' feature flag in Claude's config.json.
        Falls back to True if Claude Desktop is installed (Cowork launched
        bundled with Claude Desktop >= Jan 2026).
        """
        config_path = self._get_claude_config_path()
        if not config_path.exists():
            # If config doesn't exist but Claude Desktop is installed,
            # assume Cowork is available (bundled since Jan 2026)
            installed, _ = self._is_claude_desktop_installed()
            return installed

        try:
            config = _json.loads(config_path.read_text(encoding="utf-8"))
            # Check for explicit Cowork feature flags
            features = config.get("features", {})
            if isinstance(features, dict):
                if features.get("cowork") or features.get("agentic") or features.get("agent"):
                    return True
            # Also check top-level flags
            if config.get("cowork_enabled") or config.get("agenticMode"):
                return True
            # Cowork is bundled with Claude Desktop >= Jan 2026 — if config exists,
            # assume available unless explicitly disabled
            if not config.get("cowork_disabled", False):
                return True
        except Exception:
            pass

        return False

    def _find_project_root(self) -> Path:
        """Find the Augur project root by walking up from this file."""
        current = Path(__file__).resolve().parent
        while current != current.parent:
            if (current / ".git").exists() or (current / "pyproject.toml").exists():
                return current
            current = current.parent
        return Path.cwd()

    def _get_dispatch_dir(self) -> Path:
        """Get the state cowork-dispatch directory."""
        try:
            # Try to use the project's runtime path utilities
            from src.config.paths import get_runtime_dir  # type: ignore[import]
            return get_runtime_dir() / COWORK_DISPATCH_SUBDIR
        except ImportError:
            runtime_dir = os.environ.get("AUGUR_STATE") or os.environ.get("AUGUR_RUNTIME")
            if runtime_dir:
                return Path(runtime_dir) / COWORK_DISPATCH_SUBDIR
            if sys.platform == "darwin":
                return Path.home() / "Library" / "Application Support" / "Augur" / "state" / COWORK_DISPATCH_SUBDIR
            return Path.home() / ".local" / "state" / "augur" / COWORK_DISPATCH_SUBDIR

    def detect(self) -> dict[str, Any]:
        """Detect if Cowork is available (Claude Desktop installed + Cowork feature)."""
        installed = False
        running = False
        cowork_available = False
        path = None
        error = None

        try:
            installed, path = self._is_claude_desktop_installed()
            if installed:
                running = self._is_claude_desktop_running()
                cowork_available = self._has_cowork_feature()
        except Exception as e:
            error = str(e)

        return {
            "installed": installed and cowork_available,
            "running": running,
            "path": path,
            "cowork_available": cowork_available,
            "error": error,
        }

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Ensure the cowork-dispatch directory exists.

        Creates state/cowork-dispatch/ which Cowork monitors for pending tasks.
        Also validates that Claude Desktop MCP config includes Augur.
        """
        dispatch_dir = self._get_dispatch_dir()
        try:
            dispatch_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {
                "success": False,
                "changed": False,
                "config_paths": [],
                "error": f"Failed to create dispatch directory: {e}",
                "summary": f"Could not create Cowork dispatch dir at: {dispatch_dir}",
            }

        # Check MCP config
        mcp_config_path = self._get_claude_desktop_config_path()
        mcp_configured = False
        if mcp_config_path.exists():
            try:
                config = _json.loads(mcp_config_path.read_text(encoding="utf-8"))
                mcp_configured = "augur" in config.get("mcpServers", {})
            except Exception:
                pass

        return {
            "success": True,
            "changed": True,
            "config_paths": [str(dispatch_dir)],
            "dispatch_dir": str(dispatch_dir),
            "mcp_configured": mcp_configured,
            "summary": f"Cowork dispatch directory ready at: {dispatch_dir}",
        }

    def dispatch(self, prompt: str, task_id: Optional[str] = None) -> dict[str, Any]:
        """Write a prompt file to the Cowork dispatch directory.

        Cowork's folder instructions include a rule to check state/cowork-dispatch/
        for pending tasks on startup. Each task is a JSON file with the prompt.

        Args:
            prompt: The task prompt to dispatch to Cowork
            task_id: Optional task identifier (auto-generated if not provided)

        Returns:
            dict with keys: success, task_id, task_file, error
        """
        if task_id is None:
            task_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        dispatch_dir = self._get_dispatch_dir()
        try:
            dispatch_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {
                "success": False,
                "task_id": task_id,
                "task_file": None,
                "error": f"Cannot create dispatch directory: {e}",
            }

        task_file = dispatch_dir / f"task_{task_id}.json"
        task_data = {
            "task_id": task_id,
            "created_at": datetime.now().isoformat(),
            "status": "pending",
            "prompt": prompt,
        }

        try:
            task_file.write_text(
                _json.dumps(task_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            return {
                "success": True,
                "task_id": task_id,
                "task_file": str(task_file),
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "task_id": task_id,
                "task_file": str(task_file),
                "error": f"Failed to write task file: {e}",
            }

    def health_check(self) -> dict[str, Any]:
        """Run health checks for Cowork."""
        detection = self.detect()
        config_status = self.ensure_config()

        dispatch_dir_ok = config_status.get("success", False)
        healthy = detection["installed"] and dispatch_dir_ok

        if healthy:
            status = "healthy"
        elif detection["installed"]:
            status = "not_configured"
        else:
            status = "not_found"

        return {
            "healthy": healthy,
            "status": status,
            "checks": {
                "installed": (
                    detection["installed"],
                    "Claude Desktop with Cowork installed" if detection["installed"] else "Cowork not available",
                ),
                "running": (
                    detection["running"],
                    "Running" if detection["running"] else "Not running",
                ),
                "cowork_feature": (
                    detection.get("cowork_available", False),
                    "Cowork feature available" if detection.get("cowork_available") else "Cowork feature not detected",
                ),
                "dispatch_dir": (
                    dispatch_dir_ok,
                    config_status.get("summary", ""),
                ),
            },
            "last_check": datetime.now().isoformat(),
        }

    def render_intent(self, intent: Intent) -> AdapterOutput:
        """Dispatch intent prompt to Cowork via file-based dispatch."""
        prompt = intent.params.get("prompt", "")
        result = self.dispatch(prompt)

        return AdapterOutput(
            output_type=AdapterOutputType.CHAT_PROMPT,
            content=prompt,
            metadata={
                "ide": "cowork",
                "action": intent.action,
                "dispatch_result": result,
            },
        )

    def get_execution_mode(self) -> str:
        return "file_dispatch"

    def get_supported_fallbacks(self) -> list[str]:
        return ["chat_prompt", "file_dispatch"]
