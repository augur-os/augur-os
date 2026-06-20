"""Claude Python SDK adapter."""

from __future__ import annotations

from typing import Any, Optional

from .python_sdk_base import PythonSDKAdapter
from src.lib.ai.ide_intent import Intent


class ClaudeSDKAdapter(PythonSDKAdapter):
    """Adapter for Anthropic Claude Python SDK."""

    def __init__(self):
        super().__init__("claude_sdk", "anthropic")

    def get_sdk_version(self) -> Optional[str]:
        """Get installed Anthropic SDK version."""
        try:
            import anthropic

            return anthropic.__version__
        except (ImportError, AttributeError):
            return None

    def generate_code(self, intent: Intent) -> str:
        """
        Generate Python code using Anthropic SDK.

        Args:
            intent: The intent to translate

        Returns:
            Python code as string
        """
        action = intent.action
        params = intent.params

        # Get context if injected
        context = params.get("augur_context")
        prompt = params.get("prompt", "")

        # Build system message with context
        system_message = ""
        if context:
            system_message = f"""You are an AI assistant with access to Augur context.

User: {context.get('preferences', {}).get('name', 'Unknown')}
Active Sprint: {context.get('preferences', {}).get('custom', {}).get('active_sprint', 'None')}

Use this context to provide personalized, context-aware responses.
"""

        # Generate code based on action
        if action == "chat" or action == "ask":
            return self._generate_chat_code(prompt, system_message, params)
        elif action in ["edit", "generate_code", "create_skill"]:
            return self._generate_edit_code(prompt, system_message, params)
        else:
            # Default: simple chat
            return self._generate_chat_code(prompt, system_message, params)

    def _generate_chat_code(self, prompt: str, system: str, params: dict[str, Any]) -> str:
        """Generate code for chat/ask actions."""
        model = params.get("model", "claude-sonnet-4-5-20250929")
        max_tokens = params.get("max_tokens", 4096)

        code = f'''#!/usr/bin/env python3
"""Generated Claude SDK code for chat interaction."""

import os
import sys
from anthropic import Anthropic

# Initialize client
client = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

# System message
system = """{system}"""

# User prompt
prompt = """{prompt}"""

# Create message
response = client.messages.create(
    model="{model}",
    max_tokens={max_tokens},
    system=system,
    messages=[
        {{"role": "user", "content": prompt}}
    ]
)

# Print response
sys.stdout.write(response.content[0].text + "\\n")
'''
        return code

    def _generate_edit_code(self, prompt: str, system: str, params: dict[str, Any]) -> str:
        """Generate code for edit/generation actions."""
        model = params.get("model", "claude-sonnet-4-5-20250929")
        max_tokens = params.get("max_tokens", 8192)
        workspace = params.get("workspace", ".")

        code = f'''#!/usr/bin/env python3
"""Generated Claude SDK code for file editing."""

import os
import sys
from anthropic import Anthropic
from pathlib import Path

# Initialize client
client = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

# System message with file editing capabilities
system = """{system}

You can edit files by providing the file path and content.
Workspace: {workspace}
"""

# User prompt
prompt = """{prompt}"""

# Create message with extended thinking
response = client.messages.create(
    model="{model}",
    max_tokens={max_tokens},
    system=system,
    messages=[
        {{"role": "user", "content": prompt}}
    ]
)

# Print response
sys.stdout.write("=== Claude Response ===\\n")
sys.stdout.write(response.content[0].text + "\\n")
sys.stdout.write("\\n=== Usage ===\\n")
sys.stdout.write(f"Input tokens: {{response.usage.input_tokens}}\\n")
sys.stdout.write(f"Output tokens: {{response.usage.output_tokens}}\\n")
'''
        return code

    def get_execution_mode(self) -> str:
        """Get primary execution mode."""
        return "sdk"

    def get_supported_fallbacks(self) -> list[str]:
        """Get supported fallback modes."""
        return ["chat_prompt", "cli"]
