---
action: ide-prompt-
description: Send a context-aware prompt to a specific IDE or CLI integration
dispatch: ide
---

<instructions>
You are sending a context-aware prompt to a specific IDE or CLI integration (e.g., Cursor, Claude Code, Codex, Windsurf). The action ID is dynamically suffixed with the integration name (e.g., ide-prompt-cursor, ide-prompt-claude_code). The prompt should be tailored to the capabilities and context of the target integration. Consider what MCP tools, chat features, or code execution capabilities the target integration supports, and craft your prompt accordingly. The recommended_agent field routes execution to the correct integration.
</instructions>

<task>
Deliver the user's prompt to the specified IDE or CLI integration. Adapt the message to the target tool's capabilities and return any response or confirmation from the integration.
</task>
