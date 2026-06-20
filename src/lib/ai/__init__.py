"""Shared LLM utilities (provider-agnostic, local-first).

Migrated from project-brain/capabilities/skills/ai/augur/lib/ in Track 1 of the cross-client bundle
architecture migration. The ai bundle's adapter surface
(project-brain/capabilities/skills/ai/augur/adapters/) and CLI tools (project-brain/capabilities/skills/ai/scripts/) remain in
the bundle — this library hosts the provider-agnostic LLM client + IDE
integration code.

The core contract is: Augur calls an OpenAI-compatible HTTP API (or a local
command) using profiles configured under the user data repo.

Public API:
    LLMConfig, LLMProfile, load_llm_config, resolve_llm_profile
        Profile/config types and loaders.

    LLMClient, create_llm_client
        Provider-agnostic client.

    get_llm_client(task, context=None)
        Convenience: resolve a profile by task name and return a ready client.
"""

from __future__ import annotations

from src.lib.ai.client import LLMClient, create_llm_client
from src.lib.ai.config import (
    LLMConfig,
    LLMProfile,
    load_llm_config,
    resolve_llm_profile,
)


def get_llm_client(task: str, *, context: str | None = None) -> LLMClient:
    """Convenience: resolve a profile by task name and return a ready client."""
    config = load_llm_config()
    profile = resolve_llm_profile(config, task=task, context=context)
    return create_llm_client(profile)


__all__ = [
    "LLMClient",
    "LLMConfig",
    "LLMProfile",
    "create_llm_client",
    "get_llm_client",
    "load_llm_config",
    "resolve_llm_profile",
]
