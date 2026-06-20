"""Base adapter for Python SDK-based agents (Claude SDK, Swarm, etc.)."""

from __future__ import annotations

import importlib.util
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


class PythonSDKAdapter(BaseAdapter):
    """
    Base class for Python SDK-based agents.

    Provides context injection via structured JSON.
    Subclasses must implement SDK package detection and code generation.
    """

    def __init__(self, ide_name: str, sdk_package: str):
        """
        Initialize Python SDK adapter.

        Args:
            ide_name: Name of the SDK/agent (e.g., "claude_sdk", "swarm")
            sdk_package: Python package to check for (e.g., "anthropic", "swarm")
        """
        super().__init__(ide_name)
        self.sdk_package = sdk_package

    @abstractmethod
    def get_sdk_version(self) -> Optional[str]:
        """
        Get installed SDK version.

        Returns:
            Version string or None if not installed
        """
        raise NotImplementedError

    @abstractmethod
    def generate_code(self, intent: Intent) -> str:
        """
        Generate Python code for the intent.

        Args:
            intent: The intent to translate

        Returns:
            Python code as string
        """
        raise NotImplementedError

    def detect(self) -> dict[str, Any]:
        """Detect if this Python SDK is available."""
        installed = False
        running = False
        path = None
        error = None
        version = None

        try:
            # Check if package is importable
            spec = importlib.util.find_spec(self.sdk_package)
            if spec is not None:
                installed = True
                if spec.origin:
                    path = str(spec.origin)

                # Try to get version
                try:
                    version = self.get_sdk_version()
                except Exception:
                    pass

                # SDK is "running" if it's installed and importable
                running = True

        except Exception as e:
            error = str(e)

        return {"installed": installed, "running": running, "path": path, "error": error, "version": version}

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Python SDK agents typically configure via environment variables."""
        return {
            "success": True,
            "changed": False,
            "config_paths": [],
            "backup_paths": [],
            "error": None,
            "summary": f"{self.ide_name} SDK configures via environment variables (ANTHROPIC_API_KEY, etc.)",
        }

    def health_check(self) -> dict[str, Any]:
        """Run health checks for Python SDK integration."""
        checks: dict[str, tuple[bool | None, str]] = {}
        overall_healthy = True
        status = "healthy"
        error = None

        detection = self.detect()

        # Check 1: Config present (environment variables)
        # For now, just check if SDK is installed
        checks["config_present"] = (True, "SDK configures via environment variables")

        # Check 2: Connectivity (SDK availability)
        if detection.get("installed"):
            version_info = f" (v{detection['version']})" if detection.get('version') else ""
            checks["connectivity"] = (True, f"{self.sdk_package} SDK is installed{version_info}")
        else:
            checks["connectivity"] = (False, f"{self.sdk_package} SDK not found in Python environment")
            overall_healthy = False

        # Check 3: Tool discovery (not applicable for SDK)
        checks["tool_list"] = (None, "Not applicable for SDK")

        # Check 4: End-to-end
        try:
            test_intent = Intent(action="ping", params={})
            output = self.render_intent(test_intent)
            if output and output.content:
                checks["end_to_end"] = (True, "Can generate SDK code")
            else:
                checks["end_to_end"] = (False, "Failed to generate SDK code")
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

    def inject_context(self, intent: Intent, context: AugurContext) -> Intent:
        """
        Inject Augur context into intent as structured JSON.

        Args:
            intent: The original intent
            context: AugurContext with sprint, slash commands, etc.

        Returns:
            Modified intent with context injected into params
        """
        # Convert context to dict
        context_dict = context.to_dict()

        # Create new intent with context in params
        enhanced_params = intent.params.copy()
        enhanced_params["augur_context"] = context_dict
        enhanced_params["_context_injected"] = True

        return Intent(action=intent.action, params=enhanced_params, context=intent.context, workspace=intent.workspace)

    def render_intent(self, intent: Intent) -> AdapterOutput:
        """
        Translate intent to Python SDK code.

        Args:
            intent: The intent to translate

        Returns:
            AdapterOutput with SDK_CALL type
        """
        # Generate Python code
        code = self.generate_code(intent)

        # Build markdown documentation
        content = f"""# {self.ide_name.replace('_', ' ').title()} SDK Code

Run this Python code:

```python
{code}
```

## Action
`{intent.action}`

## Parameters
{chr(10).join(f"- `{k}`: {v}" for k, v in intent.params.items() if not k.startswith("_")) if intent.params else "None"}

## SDK Package
`{self.sdk_package}`

## Workspace
{intent.workspace or "Not specified"}
"""

        return AdapterOutput(
            output_type=AdapterOutputType.SDK_CALL,
            content=content,
            metadata={"code": code, "action": intent.action, "sdk_package": self.sdk_package},
        )

    def get_execution_mode(self) -> str:
        """Get primary execution mode."""
        return "sdk"

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
            agent_type="sdk",
            has_sprint_context=True,  # All Augur agents get context
            has_slash_commands=True,
            has_factory_insights=True,
            has_rag_access=True,  # SDK agents can integrate with RAG
            can_execute_code=True,
            specializations=["data_analysis", "automation", "integration"],
            health_status=health_status,
            execution_mode=self.get_execution_mode(),
            supported_fallbacks=self.get_supported_fallbacks(),
        )
