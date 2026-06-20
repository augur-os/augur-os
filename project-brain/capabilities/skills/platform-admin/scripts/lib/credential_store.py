"""
Credential Store — Read/write credentials compatible with the dashboard.

Writes to the same locations as the TypeScript OAuth callback handler
(apps/dashboard/app/api/remote/auth/callback/[provider]/route.ts) so
that dashboard and CLI share credentials seamlessly.

Storage locations (relative to user data root):
  1. config/integrations/.oauth-keys.json  — actual API keys (chmod 0o600)
  2. config/integrations/remote_providers.yaml — provider configs (no actual keys)
  3. config/system/llm.yaml — LLM profile configs
"""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .provider_registry import ENV_VAR_MAP, PROVIDER_REGISTRY

# =============================================================================
# Credential Store
# =============================================================================


class CredentialStore:
    """Manages credential storage compatible with the Augur dashboard."""

    def __init__(self, data_root: Path | None = None) -> None:
        self.data_root = data_root or _resolve_data_root()

        # Storage paths matching the dashboard implementation
        self.keys_path = self.data_root / "config" / "integrations" / ".oauth-keys.json"
        self.providers_path = self.data_root / "config" / "integrations" / "remote_providers.yaml"
        self.llm_path = self.data_root / "config" / "system" / "llm.yaml"

    # ─────────────────────────────────────────────────────────────────────────
    # Key Storage (.oauth-keys.json)
    # ─────────────────────────────────────────────────────────────────────────

    def load_keys(self) -> dict[str, str]:
        """Load existing .oauth-keys.json or return empty dict."""
        if not self.keys_path.exists():
            return {}
        try:
            return json.loads(self.keys_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def store_key(self, provider_id: str, api_key: str) -> None:
        """
        Store an API key in .oauth-keys.json with chmod 0o600.

        Matches the storeApiKey() function in the dashboard callback route.
        """
        # Ensure directory exists
        self.keys_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing keys, add new one
        keys = self.load_keys()
        keys[provider_id] = api_key

        # Write with restricted permissions
        self.keys_path.write_text(
            json.dumps(keys, indent=2) + "\n",
            encoding="utf-8",
        )
        os.chmod(self.keys_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600

    def remove_key(self, provider_id: str) -> None:
        """Remove an API key from .oauth-keys.json."""
        keys = self.load_keys()
        keys.pop(provider_id, None)
        if keys:
            self.keys_path.write_text(
                json.dumps(keys, indent=2) + "\n",
                encoding="utf-8",
            )
            os.chmod(self.keys_path, stat.S_IRUSR | stat.S_IWUSR)
        elif self.keys_path.exists():
            self.keys_path.unlink()

    # ─────────────────────────────────────────────────────────────────────────
    # Provider Config (remote_providers.yaml)
    # ─────────────────────────────────────────────────────────────────────────

    def load_providers_config(self) -> dict[str, Any]:
        """Load remote_providers.yaml or return default structure."""
        if self.providers_path.exists():
            try:
                raw = yaml.safe_load(self.providers_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
            except (yaml.YAMLError, OSError):
                pass

        # Default config matching the dashboard schema
        return _default_providers_config()

    def update_remote_providers(
        self,
        provider_id: str,
        *,
        has_key: bool = True,
        is_oauth: bool = False,
    ) -> None:
        """
        Update remote_providers.yaml to mark a provider as configured.

        Matches the YAML schema written by the dashboard callback handler.
        """
        config = self.load_providers_config()

        if "providers" not in config:
            config["providers"] = {}

        env_var = ENV_VAR_MAP.get(provider_id, f"{provider_id.upper()}_API_KEY")
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

        provider_config: dict[str, Any] = config["providers"].get(provider_id, {})
        provider_config.update(
            {
                "id": provider_id,
                "enabled": True,
                "apiKeyEnv": env_var,
                "hasApiKey": has_key,
                "lastTested": now,
            }
        )

        # OAuth providers get a token reference (not the actual key)
        if is_oauth:
            provider_config["oauthToken"] = f"oauth:{provider_id}:{int(datetime.now(timezone.utc).timestamp() * 1000)}"

        config["providers"][provider_id] = provider_config

        # Ensure default sections exist
        if "security" not in config:
            config["security"] = _default_providers_config()["security"]
        if "budget" not in config:
            config["budget"] = _default_providers_config()["budget"]
        if "audit" not in config:
            config["audit"] = _default_providers_config()["audit"]

        # Write
        self.providers_path.parent.mkdir(parents=True, exist_ok=True)
        self.providers_path.write_text(
            yaml.dump(config, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # LLM Config (llm.yaml)
    # ─────────────────────────────────────────────────────────────────────────

    def load_llm_config(self) -> dict[str, Any]:
        """Load llm.yaml or return default structure."""
        if self.llm_path.exists():
            try:
                from src.config.system_config import llm_config_raw

                raw = llm_config_raw(self.llm_path)
                if isinstance(raw, dict):
                    return raw
            except (ValueError, OSError):
                pass
        return {"active_profile": "agentic_ide", "profiles": {}}

    def update_llm_yaml(self, provider_id: str) -> None:
        """
        Add or update an LLM profile in llm.yaml for the configured provider.

        Does NOT change active_profile unless no profile exists yet.
        """
        provider = PROVIDER_REGISTRY.get(provider_id)
        if not provider:
            return

        config = self.load_llm_config()
        if "profiles" not in config:
            config["profiles"] = {}

        # Determine profile name
        profile_name = "remote" if provider.auth_method in ("oauth", "manual") else "local"

        # Build profile data
        profile: dict[str, Any] = {
            "provider": "openai_compatible",
            "base_url": provider.base_url,
            "model": provider.default_model,
            "timeout_s": 60 if profile_name == "remote" else 300,
        }

        if provider.api_key_env:
            profile["api_key_env"] = provider.api_key_env
        elif provider_id == "ollama":
            profile["api_key"] = "ollama"

        # Only update if the profile doesn't exist or has no base_url
        existing = config["profiles"].get(profile_name, {})
        if not existing or not existing.get("base_url"):
            config["profiles"][profile_name] = profile
        else:
            # Update model if provider changed
            if existing.get("api_key_env") != profile.get("api_key_env"):
                config["profiles"][profile_name] = profile

        # If no active profile is set, default to the one we just configured
        if not config.get("active_profile"):
            config["active_profile"] = profile_name

        self.llm_path.parent.mkdir(parents=True, exist_ok=True)
        self.llm_path.write_text(
            yaml.dump(config, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Query
    # ─────────────────────────────────────────────────────────────────────────

    def get_configured_providers(self) -> list[str]:
        """Return list of provider IDs that have stored API keys."""
        return list(self.load_keys().keys())

    def is_configured(self, provider_id: str) -> bool:
        """Check if a provider has a stored API key."""
        if provider_id == "ollama":
            # Ollama doesn't need a key, check if it's in llm.yaml
            config = self.load_llm_config()
            local = config.get("profiles", {}).get("local", {})
            return local.get("base_url", "").startswith("http://localhost:11434")
        return provider_id in self.load_keys()


# =============================================================================
# Helpers
# =============================================================================


def _resolve_data_root() -> Path:
    """Resolve the user data root directory."""
    # Try the centralized path resolution first
    try:
        import sys

        # Add project root to path (5 parents up from scripts/lib/)
        project_root = str(Path(__file__).resolve().parents[5])
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.config.paths import get_project_root

        return get_project_root()
    except Exception:
        pass

    # Fallback: check environment variables
    value = os.environ.get("AUGUR_ROOT")
    if value:
        return Path(value)

    # Last resort: project_root/data
    project_root_path = Path(__file__).resolve().parents[5]
    return project_root_path / "data"


def _default_providers_config() -> dict[str, Any]:
    """Return the default remote_providers.yaml structure."""
    return {
        "providers": {
            pid: {
                "id": pid,
                "enabled": False,
                "apiKeyEnv": ENV_VAR_MAP.get(pid, ""),
            }
            for pid in ENV_VAR_MAP
        },
        "security": {
            "requireExplicitConsent": True,
            "warnOnPii": True,
            "blockOnSecrets": True,
            "sensitiveFolders": [],
        },
        "budget": {
            "dailyLimitUsd": 10,
            "monthlyLimitUsd": 100,
            "warnAtPercentage": 80,
        },
        "audit": {
            "logAllRequests": True,
            "logPrompts": False,
            "logResponses": False,
            "retentionDays": 30,
        },
    }
