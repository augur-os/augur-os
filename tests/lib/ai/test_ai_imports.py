"""Smoke tests for the src.lib.ai public API."""

from __future__ import annotations


def test_public_api_importable():
    """All 7 documented public symbols importable from src.lib.ai."""
    from src.lib.ai import (  # noqa: F401
        LLMClient,
        LLMConfig,
        LLMProfile,
        create_llm_client,
        get_llm_client,
        load_llm_config,
        resolve_llm_profile,
    )


def test_public_api_origins():
    """Symbols originate in the right submodules."""
    from src.lib.ai import (
        LLMClient,
        LLMConfig,
        LLMProfile,
        create_llm_client,
        load_llm_config,
        resolve_llm_profile,
    )

    assert LLMClient.__module__ == "src.lib.ai.client"
    assert create_llm_client.__module__ == "src.lib.ai.client"
    assert LLMConfig.__module__ == "src.lib.ai.config"
    assert LLMProfile.__module__ == "src.lib.ai.config"
    assert load_llm_config.__module__ == "src.lib.ai.config"
    assert resolve_llm_profile.__module__ == "src.lib.ai.config"


def test_submodule_paths_reachable():
    """Submodule access works for callers that bypass __init__ re-exports."""
    from src.lib.ai import (  # noqa: F401
        cli_detect,
        discovery,
        ide_health,
        prompt_registry,
        schema,
        usage_tracker,
    )
