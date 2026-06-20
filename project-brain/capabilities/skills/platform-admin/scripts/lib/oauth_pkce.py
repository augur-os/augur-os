"""
OAuth PKCE Utilities — Python mirror of apps/dashboard/lib/remote/oauth.ts

Implements Proof Key for Code Exchange (PKCE) for secure OAuth flows.
Used by Glama and OpenRouter for one-click authentication.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import requests

# =============================================================================
# PKCE Generation
# =============================================================================

_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


def generate_code_verifier(length: int = 64) -> str:
    """
    Generate a cryptographically random code verifier.

    Must be between 43-128 characters, using unreserved URI characters.
    Mirrors generateCodeVerifier() in oauth.ts.
    """
    random_bytes = secrets.token_bytes(length)
    return "".join(_CHARSET[b % len(_CHARSET)] for b in random_bytes)


def generate_code_challenge(verifier: str) -> str:
    """
    Generate a code challenge from the verifier using S256 method.

    SHA-256 hash, then base64url encode (no padding).
    Mirrors generateCodeChallenge() in oauth.ts.
    """
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    # base64url encode without padding — matches the TS implementation
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_state() -> str:
    """
    Generate a random state parameter for CSRF protection.

    32 random bytes, hex-encoded (64 hex chars).
    Mirrors generateState() in oauth.ts.
    """
    return secrets.token_hex(32)


# =============================================================================
# Authorization URL
# =============================================================================

# OAuth configuration per provider
_OAUTH_CONFIG = {
    "glama": {
        "authorize_url": "https://glama.ai/oauth/authorize",
        "exchange_url": "https://glama.ai/api/gateway/v1/auth/exchange-code",
        "key_field": "apiKey",
    },
    "openrouter": {
        "authorize_url": "https://openrouter.ai/auth",
        "exchange_url": "https://openrouter.ai/api/v1/auth/keys",
        "key_field": "key",
    },
}


def build_authorization_url(
    provider: str,
    code_challenge: str,
    state: str,
    callback_url: str,
) -> str:
    """
    Build the OAuth authorization URL for a provider.

    Mirrors buildAuthorizationUrl() in oauth.ts.
    """
    config = _OAUTH_CONFIG.get(provider)
    if not config:
        raise ValueError(f"OAuth not supported for provider: {provider}")

    params = {
        "callback_url": callback_url,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return f"{config['authorize_url']}?{urlencode(params)}"


# =============================================================================
# Code Exchange
# =============================================================================


def exchange_code(
    provider: str,
    code: str,
    code_verifier: str,
) -> tuple[str | None, str | None]:
    """
    Exchange an authorization code for an API key.

    Returns (api_key, None) on success or (None, error_message) on failure.
    Mirrors exchangeCodeGlama() and exchangeCodeOpenRouter() in oauth.ts.
    """
    config = _OAUTH_CONFIG.get(provider)
    if not config:
        return None, f"OAuth not supported for provider: {provider}"

    try:
        response = requests.post(
            config["exchange_url"],
            json={
                "code": code,
                "code_verifier": code_verifier,
                "code_challenge_method": "S256",
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if not response.ok:
            try:
                data = response.json()
                error_msg = data.get("error", {})
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", f"HTTP {response.status_code}")
                return None, str(error_msg)
            except Exception:
                return None, f"HTTP {response.status_code}"

        data = response.json()
        api_key = data.get(config["key_field"])
        if not api_key:
            return None, "No API key in response"

        return api_key, None

    except requests.Timeout:
        return None, "Request timed out"
    except requests.ConnectionError:
        return None, "Connection failed — check your internet connection"
    except Exception as e:
        return None, str(e)
