"""
Provider Registry — Python mirror of apps/dashboard/lib/remote/providers.ts

Single source of truth for provider definitions used by the CLI OAuth wizard.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderDefinition:
    """Mirrors the TypeScript ProviderDefinition interface."""

    id: str
    name: str
    description: str
    auth_method: str  # 'oauth' | 'manual' | 'local'
    base_url: str
    default_model: str
    api_key_env: str
    oauth_url: str | None = None
    website_url: str | None = None


# =============================================================================
# Provider Definitions
# =============================================================================

PROVIDER_REGISTRY: dict[str, ProviderDefinition] = {
    "glama": ProviderDefinition(
        id="glama",
        name="Glama",
        description="Zero markup gateway with OAuth",
        auth_method="oauth",
        base_url="https://glama.ai/api/gateway/openai/v1",
        oauth_url="https://glama.ai/oauth/authorize",
        default_model="anthropic/claude-sonnet-4",
        api_key_env="GLAMA_API_KEY",
        website_url="https://glama.ai",
    ),
    "openrouter": ProviderDefinition(
        id="openrouter",
        name="OpenRouter",
        description="Multi-provider gateway with OAuth (5.5% fee)",
        auth_method="oauth",
        base_url="https://openrouter.ai/api/v1",
        oauth_url="https://openrouter.ai/auth",
        default_model="anthropic/claude-sonnet-4",
        api_key_env="OPENROUTER_API_KEY",
        website_url="https://openrouter.ai",
    ),
    "anthropic": ProviderDefinition(
        id="anthropic",
        name="Anthropic",
        description="Direct access to Claude models",
        auth_method="manual",
        base_url="https://api.anthropic.com/v1",
        default_model="claude-sonnet-4-20250514",
        api_key_env="ANTHROPIC_API_KEY",
        website_url="https://console.anthropic.com",
    ),
    "openai": ProviderDefinition(
        id="openai",
        name="OpenAI",
        description="GPT models including GPT-4o and o1",
        auth_method="manual",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
        api_key_env="OPENAI_API_KEY",
        website_url="https://platform.openai.com",
    ),
    "gemini": ProviderDefinition(
        id="gemini",
        name="Google Gemini",
        description="Multimodal models from Google",
        auth_method="manual",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-pro",
        api_key_env="GOOGLE_AI_API_KEY",
        website_url="https://aistudio.google.com",
    ),
    "groq": ProviderDefinition(
        id="groq",
        name="Groq",
        description="Ultra-fast inference with custom LPU hardware",
        auth_method="manual",
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        website_url="https://console.groq.com",
    ),
    "together": ProviderDefinition(
        id="together",
        name="Together.ai",
        description="Open-source models with competitive pricing",
        auth_method="manual",
        base_url="https://api.together.xyz/v1",
        default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        api_key_env="TOGETHER_API_KEY",
        website_url="https://api.together.ai",
    ),
    "custom": ProviderDefinition(
        id="custom",
        name="Custom Provider",
        description="Your own OpenAI-compatible endpoint",
        auth_method="manual",
        base_url="",
        default_model="",
        api_key_env="CUSTOM_LLM_API_KEY",
    ),
    "ollama": ProviderDefinition(
        id="ollama",
        name="Ollama (Local)",
        description="Run models locally — no API key needed",
        auth_method="local",
        base_url="http://localhost:11434/v1",
        default_model="llama3.2:3b-instruct-q8_0",
        api_key_env="",
        website_url="https://ollama.ai",
    ),
}

# Matches getEnvVarName() in callback/[provider]/route.ts line 196
ENV_VAR_MAP: dict[str, str] = {
    "glama": "GLAMA_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_AI_API_KEY",
    "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
    "custom": "CUSTOM_LLM_API_KEY",
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_provider(provider_id: str) -> ProviderDefinition | None:
    """Get a provider by ID."""
    return PROVIDER_REGISTRY.get(provider_id)


def get_oauth_providers() -> list[ProviderDefinition]:
    """Return providers that support OAuth."""
    return [p for p in PROVIDER_REGISTRY.values() if p.auth_method == "oauth"]


def get_manual_providers() -> list[ProviderDefinition]:
    """Return providers that require manual API key entry."""
    return [p for p in PROVIDER_REGISTRY.values() if p.auth_method == "manual"]


def get_local_providers() -> list[ProviderDefinition]:
    """Return local LLM providers."""
    return [p for p in PROVIDER_REGISTRY.values() if p.auth_method == "local"]


def get_all_provider_ids() -> list[str]:
    """Return all provider IDs in menu order."""
    return list(PROVIDER_REGISTRY.keys())
