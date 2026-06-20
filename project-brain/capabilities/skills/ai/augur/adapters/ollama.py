"""Adapter for Ollama - Local LLM server."""

from __future__ import annotations

import shutil
from datetime import datetime
from typing import Any, Optional
from .base import BaseAdapter
from src.lib.ai.ide_intent import Intent, AdapterOutput, AdapterOutputType


class OllamaAdapter(BaseAdapter):
    """Adapter for Ollama local LLM server."""

    def __init__(self):
        super().__init__("ollama")
        self.api_url = "http://localhost:11434"

    def detect(self) -> dict[str, Any]:
        """Detect if Ollama is installed and running."""
        import os

        installed = False
        running = False
        path = None
        error = None
        models = []

        # Check common installation paths
        home = os.path.expanduser("~")
        common_paths = [
            "/usr/local/bin/ollama",
            "/opt/homebrew/bin/ollama",
            os.path.join(home, ".local", "bin", "ollama"),
        ]

        try:
            resolved = shutil.which("ollama")
            if resolved:
                installed = True
                path = resolved
            else:
                for check_path in common_paths:
                    if os.path.isfile(check_path) and os.access(check_path, os.X_OK):
                        installed = True
                        path = check_path
                        break

            # Check if server is running by hitting the API
            if installed:
                import urllib.request
                import json

                try:
                    req = urllib.request.Request(f"{self.api_url}/api/tags", method="GET")
                    with urllib.request.urlopen(req, timeout=5) as response:  # nosec B310
                        data = json.loads(response.read().decode())
                        running = True
                        models = [m.get("name") for m in data.get("models", [])]
                except Exception:
                    running = False

        except Exception as e:
            error = str(e)

        return {
            "installed": installed,
            "running": running,
            "path": path,
            "error": error,
            "models": models,
        }

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Check Ollama configuration and running status."""
        detection = self.detect()

        if not detection.get("installed"):
            return {
                "success": False,
                "changed": False,
                "error": "Ollama not found. Install via: brew install ollama",
                "summary": "Ollama CLI not installed.",
            }

        if not detection.get("running"):
            return {
                "success": False,
                "changed": False,
                "error": "Ollama server not running. Start with: ollama serve",
                "summary": "Ollama is installed but the server is not running.",
            }

        models = detection.get("models", [])
        if not models:
            return {
                "success": True,
                "changed": False,
                "summary": "Ollama is running but no models are installed. Run: ollama pull llama3.2",
            }

        return {
            "success": True,
            "changed": False,
            "summary": f"Ollama is running with {len(models)} model(s): {', '.join(models[:3])}",
        }

    def health_check(self) -> dict[str, Any]:
        """Run health checks for Ollama."""
        checks: dict[str, tuple[bool | None, str]] = {}
        overall_healthy = True
        status = "healthy"
        error = None

        detection = self.detect()

        # Check 1: Installation
        if detection.get("installed"):
            checks["config_present"] = (True, f"Ollama installed at {detection.get('path')}")
        else:
            checks["config_present"] = (False, "Ollama not installed")
            overall_healthy = False

        # Check 2: Server running
        if detection.get("running"):
            checks["connectivity"] = (True, f"Server responding at {self.api_url}")
        else:
            checks["connectivity"] = (False, "Server not running")
            overall_healthy = False

        # Check 3: Models available
        models = detection.get("models", [])
        if models:
            checks["tool_list"] = (True, f"{len(models)} model(s) available")
        else:
            checks["tool_list"] = (False, "No models installed")
            # Not a blocker, just a warning

        # Check 4: End-to-end (try listing models)
        if detection.get("running"):
            checks["end_to_end"] = (True, "API responsive")
        else:
            checks["end_to_end"] = (False, "Cannot reach API")
            overall_healthy = False

        if not overall_healthy:
            status = "not_configured" if not detection.get("installed") else "degraded"

        return {
            "healthy": overall_healthy,
            "status": status,
            "checks": checks,
            "last_check": datetime.now().isoformat(),
            "error": error,
            "details": {
                "models": models,
                "api_url": self.api_url,
            },
        }

    def render_intent(self, intent: Intent) -> AdapterOutput:
        """
        Translate intent to Ollama API call format.

        Args:
            intent: The intent to translate

        Returns:
            AdapterOutput with API_CALL type
        """
        action = intent.action
        params = intent.params

        if action in ("chat", "ask", "generate"):
            model = params.get("model", "llama3.2")
            prompt = params.get("prompt", "")

            content = f"""# Ollama API Call

**Model**: `{model}`

**Prompt**:
```
{prompt}
```

**API Endpoint**: `POST {self.api_url}/api/generate`

**Request Body**:
```json
{{
    "model": "{model}",
    "prompt": "{prompt}"
}}
```
"""
        else:
            content = f"""# Ollama CLI Command

```bash
ollama {action} {' '.join(f'{v}' for v in params.values())}
```
"""

        return AdapterOutput(
            output_type=AdapterOutputType.MCP_CALL,
            content=content,
            metadata={"api_url": self.api_url, "action": action},
        )

    def get_execution_mode(self) -> str:
        """Get primary execution mode."""
        return "api"

    def get_supported_fallbacks(self) -> list[str]:
        """Get supported fallback modes."""
        return ["cli"]

    def get_launch_command(
        self,
        agent: str = "claude",
        model: str = "qwen3.5:9b",
        extra_args: list[str] | None = None,
    ) -> list[str]:
        """Build the ollama launch command for a given agent and model.

        Args:
            agent: Agent integration name (claude, codex, opencode, etc.)
            model: Ollama model name
            extra_args: Additional args passed after -- to the agent CLI

        Returns:
            Command as a list of strings suitable for subprocess.
        """
        cmd = ["ollama", "launch", agent, "--model", model]
        if extra_args:
            cmd.append("--")
            cmd.extend(extra_args)
        return cmd

    def get_capabilities(self):
        """
        Get agent capabilities for routing.

        Returns:
            AgentCapabilities object
        """
        from src.lib.ai.agent_capabilities import AgentCapabilities

        health = self.health_check()
        health_status = health.get("status", "unknown")

        return AgentCapabilities(
            agent_name=self.ide_name,
            agent_type="local_llm",
            has_sprint_context=False,
            has_slash_commands=False,
            has_factory_insights=False,
            can_execute_code=False,
            can_modify_files=False,
            specializations=["text_generation", "local_inference", "privacy"],
            health_status=health_status,
            execution_mode=self.get_execution_mode(),
            supported_fallbacks=self.get_supported_fallbacks(),
        )
