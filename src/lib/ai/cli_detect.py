"""CLI auto-detection for LLM dispatch.

Detects the user's preferred CLI binary for subprocess-based LLM calls.
Used by load_llm_config() to inject a synthetic 'cli' profile.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from src.logging import get_entity_logger

logger = get_entity_logger("lib.ai.cli_detect")

_CLI_COMMANDS: dict[str, str] = {
    "claude": "{path} --print",
    "codex": "{path} exec",
    "ollama": "{path} run {model}",
}

_DEFAULT_OLLAMA_MODEL = "qwen3.5:latest"


def detect_cli() -> str | None:
    """Find the best available CLI binary for LLM dispatch.

    Priority:
    1. cli_agents.yaml ordered list
    2. shutil.which() on each candidate

    Returns absolute path to CLI binary, or None if nothing found.
    Never raises.
    """
    try:
        for candidate in _get_candidate_clis():
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
    except Exception as exc:
        logger.debug("CLI detection failed: %s", exc)

    return None


def cli_command(cli_path: str, *, model: str | None = None) -> str:
    """Build a bare command string for the given CLI binary.

    Returns e.g. '/usr/local/bin/claude --print' or '/usr/local/bin/ollama run qwen3.5:latest'.
    """
    name = Path(cli_path).stem
    template = _CLI_COMMANDS.get(name)
    if template is None:
        return cli_path

    effective_model = model or _DEFAULT_OLLAMA_MODEL
    return template.format(path=cli_path, model=effective_model)


def _get_candidate_clis() -> list[str]:
    """Read ordered CLI list from cli_agents.yaml."""
    try:
        from src.lib.agent_cli_config import get_cli_candidate_ids

        return get_cli_candidate_ids(command_fields=("cmd",))
    except Exception:
        return []
