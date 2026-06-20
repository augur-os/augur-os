"""
Provider Verifier — Test API key connectivity for each provider.

Makes a minimal API call to confirm the key is valid and the provider
is reachable. Returns (success, message) for each provider.
"""

from __future__ import annotations

import requests

# =============================================================================
# Public API
# =============================================================================


def verify_provider(provider_id: str, api_key: str = "") -> tuple[bool, str]:
    """
    Test an API key by making a minimal request to the provider.

    Returns (success, message).
    """
    verifier = _VERIFIERS.get(provider_id)
    if not verifier:
        return False, f"No verifier for provider: {provider_id}"

    try:
        return verifier(api_key)
    except requests.Timeout:
        return False, "Request timed out (30s)"
    except requests.ConnectionError:
        return False, "Connection failed — check your internet connection"
    except Exception as e:
        return False, f"Unexpected error: {e}"


# =============================================================================
# Provider-Specific Verifiers
# =============================================================================


def _verify_openai_compatible(api_key: str, base_url: str, name: str) -> tuple[bool, str]:
    """Verify an OpenAI-compatible provider by listing models."""
    resp = requests.get(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    if resp.ok:
        data = resp.json()
        model_count = len(data.get("data", []))
        return True, f"{name} connected ({model_count} models available)"
    return False, f"{name} returned HTTP {resp.status_code}"


def _verify_glama(api_key: str) -> tuple[bool, str]:
    return _verify_openai_compatible(api_key, "https://glama.ai/api/gateway/openai/v1", "Glama")


def _verify_openrouter(api_key: str) -> tuple[bool, str]:
    """OpenRouter has a dedicated auth check endpoint."""
    resp = requests.get(
        "https://openrouter.ai/api/v1/auth/key",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    if resp.ok:
        data = resp.json()
        label = data.get("data", {}).get("label", "")
        return True, f"OpenRouter connected{f' ({label})' if label else ''}"
    return False, f"OpenRouter returned HTTP {resp.status_code}"


def _verify_anthropic(api_key: str) -> tuple[bool, str]:
    """Anthropic uses x-api-key header and a messages endpoint."""
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "Hi"}],
        },
        timeout=30,
    )
    if resp.ok:
        return True, "Anthropic connected (Claude available)"
    if resp.status_code == 401:
        return False, "Invalid API key"
    if resp.status_code == 429:
        # Rate limited but key is valid
        return True, "Anthropic connected (rate limited — key is valid)"
    return False, f"Anthropic returned HTTP {resp.status_code}"


def _verify_openai(api_key: str) -> tuple[bool, str]:
    return _verify_openai_compatible(api_key, "https://api.openai.com/v1", "OpenAI")


def _verify_gemini(api_key: str) -> tuple[bool, str]:
    """Gemini uses API key as query parameter."""
    resp = requests.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": api_key},
        timeout=30,
    )
    if resp.ok:
        data = resp.json()
        model_count = len(data.get("models", []))
        return True, f"Google Gemini connected ({model_count} models available)"
    if resp.status_code == 400:
        return False, "Invalid API key"
    return False, f"Google Gemini returned HTTP {resp.status_code}"


def _verify_groq(api_key: str) -> tuple[bool, str]:
    return _verify_openai_compatible(api_key, "https://api.groq.com/openai/v1", "Groq")


def _verify_together(api_key: str) -> tuple[bool, str]:
    return _verify_openai_compatible(api_key, "https://api.together.xyz/v1", "Together.ai")


def _verify_custom(api_key: str) -> tuple[bool, str]:
    """Custom providers can't be verified without a base URL."""
    return True, "Custom provider — key stored (cannot verify without base URL)"


def _verify_ollama(_api_key: str = "") -> tuple[bool, str]:
    """Check if Ollama is running and list models."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.ok:
            data = resp.json()
            models = [m.get("name", "?") for m in data.get("models", [])]
            if models:
                return True, f"Ollama running ({len(models)} models: {', '.join(models[:3])})"
            return True, "Ollama running (no models installed)"
        return False, f"Ollama returned HTTP {resp.status_code}"
    except requests.ConnectionError:
        return False, "Ollama not running — start with: ollama serve"
    except requests.Timeout:
        return False, "Ollama not responding (timeout)"


# =============================================================================
# Verifier Registry
# =============================================================================

_VERIFIERS: dict[str, object] = {
    "glama": _verify_glama,
    "openrouter": _verify_openrouter,
    "anthropic": _verify_anthropic,
    "openai": _verify_openai,
    "gemini": _verify_gemini,
    "groq": _verify_groq,
    "together": _verify_together,
    "custom": _verify_custom,
    "ollama": _verify_ollama,
}
