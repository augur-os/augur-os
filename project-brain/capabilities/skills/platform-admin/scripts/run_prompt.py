"""
Run Prompt Script (ADR-137 agent-inline pattern)

Loads a registered prompt, renders variables, and returns the assembled
messages for the calling agent to execute inline.

Two modes:
  --dry-run (default): Output rendered messages as JSON (agent executes inline)
  --mode context:      Same as --dry-run (explicit agent-inline mode)

The calling IDE agent IS the LLM — this script only does template rendering.
"""

import sys
import json
import argparse
from pathlib import Path

# Add project root to sys.path
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.lib.ai.prompt_registry import registry  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Render a registered prompt for agent-inline execution (ADR-137)")
    parser.add_argument("prompt_id", help="The ID of the prompt to render (e.g., 'dashboard.inbox.summarize')")
    parser.add_argument("--variables", help="JSON string of template variables", default="{}")
    # Keep --dry-run for backward compat, but it's now the default behavior
    parser.add_argument("--dry-run", action="store_true", help="(Default) Output rendered messages without LLM execution")

    args = parser.parse_args()

    try:
        variables = json.loads(args.variables)

        # Render the prompt template with variables
        messages, config = registry.render_prompt(args.prompt_id, variables)

        # Output the rendered prompt for agent-inline execution
        output = {
            "status": "rendered",
            "prompt_id": args.prompt_id,
            "model_config": config.model_dump(),
            "messages": messages,
            "instructions": (
                "Execute these messages inline. You are the LLM — "
                "process the messages and return the response."
            ),
        }
        sys.stdout.write(f"{json.dumps(output, indent=2)}\n")

    except Exception as e:
        sys.stderr.write(f"{json.dumps({'status': 'error', 'error': str(e)})}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
