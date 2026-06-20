from __future__ import annotations

import json
import os
import shlex
import shutil
import urllib.error
import urllib.request
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, run as subprocess_run  # nosec B404
from typing import Any

from src.logging import get_entity_logger
from .config import LLMProfile

logger = get_entity_logger("llm")


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve command executable to absolute path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run_subprocess(command: list[str], **kwargs: Any) -> CompletedProcess[str]:
    """Run subprocess command with resolved executable path."""
    return subprocess_run(_resolve_command(command), **kwargs)  # nosec B603


def _strip_trailing_slash(url: str) -> str:
    return url[:-1] if url.endswith("/") else url


def _extract_json(text: str) -> Any:
    raw = text.strip()
    if not raw:
        raise ValueError("Empty response")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw[start : end + 1])

    raise ValueError("Failed to extract JSON from response")


class LLMClient:
    def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        raise NotImplementedError

    def generate_json(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        text = self.generate_text(
            prompt=prompt,
            system=system,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return _extract_json(text)

    def generate_with_vision(
        self,
        *,
        prompt: str,
        images: list[bytes | str],
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        raise NotImplementedError(f"{type(self).__name__} does not support vision")

    def generate_with_tools(
        self,
        *,
        prompt: str,
        tools: list[dict],
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        raise NotImplementedError(f"{type(self).__name__} does not support tool use")


@dataclass(frozen=True)
class OpenAICompatibleClient(LLMClient):
    base_url: str
    api_key: str | None
    default_model: str
    timeout_s: int = 60
    response_format_json: bool = False
    default_temperature: float = 0.2
    disable_thinking: bool = False

    def _headers(self) -> dict[str, str]:
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "Augur/0.1",
        }
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        return headers

    @property
    def _provider(self) -> str:
        url = self.base_url.lower()
        for name in ("glama", "groq", "openai", "anthropic", "deepseek", "openrouter"):
            if name in url:
                return name
        return "unknown"

    def _resolve_temperature(self, temperature: float | None) -> float:
        if temperature is not None:
            return float(temperature)
        return self.default_temperature

    def _track_usage(
        self,
        model: str,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        try:
            from .usage_tracker import get_usage_tracker

            tracker = get_usage_tracker()
            provider = self._provider
            cost = tracker.get_cost_estimate(provider, model, prompt_tokens, completion_tokens) if success else 0.0
            tracker.track_request(
                provider=provider,
                profile="default",
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost=cost,
                success=success,
                error=error,
            )
        except Exception as exc:
            logger.debug("Failed to record usage tracking: %s", exc)

    def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        effective_model = (model or self.default_model).strip()
        if not effective_model:
            raise RuntimeError("Missing model name for LLM request")

        messages: list[dict[str, str]] = []
        if system and system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "temperature": self._resolve_temperature(temperature),
        }
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        if self.response_format_json:
            payload["response_format"] = {"type": "json_object"}

        try:
            message, parsed = self._post_completion(payload, label="LLM")
        except RuntimeError as e:
            self._track_usage(effective_model, success=False, error=str(e)[:200])
            raise

        usage = parsed.get("usage", {})
        self._track_usage(
            effective_model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            success=True,
        )

        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("LLM response missing content")
        return content

    def _post_completion(self, payload: dict[str, Any], label: str = "LLM") -> tuple[dict, dict]:
        """POST to /chat/completions and return (message_dict, full_parsed_response).

        For Ollama with disable_thinking=True, falls back to the native /api/generate
        endpoint with think=false, since the OpenAI-compatible endpoint cannot disable
        thinking for models like Qwen 3.5.
        """
        if self.disable_thinking and "localhost:11434" in self.base_url:
            return self._post_ollama_native(payload, label)

        url = f"{_strip_trailing_slash(self.base_url)}/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # nosec B310
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = ""
            raise RuntimeError(f"{label} request failed ({e.code}): {body.strip() or e}") from e
        except Exception as e:
            raise RuntimeError(f"{label} request failed: {e}") from e

        parsed = json.loads(raw)
        choices = parsed.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError(f"{label} response missing choices[]")
        message = (choices[0] or {}).get("message")
        if not isinstance(message, dict):
            raise RuntimeError(f"{label} response missing message")

        # Thinking models (e.g. Qwen 3.5 via Ollama) put output in 'reasoning'
        # with empty 'content'. Use reasoning as content — callers that need
        # clean output should strip/post-process.
        if not message.get("content") and message.get("reasoning"):
            message["content"] = message["reasoning"]

        return message, parsed

    def _post_ollama_native(self, payload: dict[str, Any], label: str) -> tuple[dict, dict]:
        """Fallback to Ollama native /api/generate with think=false."""
        base = _strip_trailing_slash(self.base_url)
        # Strip /v1 suffix to get the Ollama base URL
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base}/api/generate"

        # Convert chat-completions payload to native format
        prompt_parts = []
        for msg in payload.get("messages", []):
            if msg.get("role") == "system":
                prompt_parts.append(msg["content"])
            elif msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    prompt_parts.append(content)
                elif isinstance(content, list):
                    prompt_parts.extend(block["text"] for block in content if block.get("type") == "text")

        native_payload: dict[str, Any] = {
            "model": payload.get("model", self.default_model),
            "prompt": "\n\n".join(prompt_parts),
            "stream": False,
            "think": False,
            "options": {},
        }
        if "max_tokens" in payload:
            native_payload["options"]["num_predict"] = payload["max_tokens"]
        if "temperature" in payload:
            native_payload["options"]["temperature"] = payload["temperature"]

        req = urllib.request.Request(
            url,
            data=json.dumps(native_payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # nosec B310
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = ""
            raise RuntimeError(f"{label} request failed ({e.code}): {body.strip() or e}") from e
        except Exception as e:
            raise RuntimeError(f"{label} request failed: {e}") from e

        parsed = json.loads(raw)
        content = parsed.get("response", "")
        message = {"role": "assistant", "content": content}
        return message, parsed

    def generate_with_vision(
        self,
        *,
        prompt: str,
        images: list[bytes | str],
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        import base64 as _base64

        effective_model = (model or self.default_model).strip()
        if not effective_model:
            raise RuntimeError("Missing model name for LLM request")

        messages: list[dict] = []
        if system and system.strip():
            messages.append({"role": "system", "content": system.strip()})

        content: list[dict] = [{"type": "text", "text": prompt}]
        for img in images:
            if isinstance(img, bytes):
                b64 = _base64.b64encode(img).decode("utf-8")
                img_url = f"data:image/png;base64,{b64}"
            else:
                img_url = img
            content.append({"type": "image_url", "image_url": {"url": img_url}})
        messages.append({"role": "user", "content": content})

        payload: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "temperature": self._resolve_temperature(temperature),
        }
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)

        message, _ = self._post_completion(payload, label="LLM vision")
        response_content = message.get("content")
        if not isinstance(response_content, str):
            raise RuntimeError("LLM vision response missing content")
        return response_content

    def generate_with_tools(
        self,
        *,
        prompt: str,
        tools: list[dict],
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        effective_model = (model or self.default_model).strip()
        if not effective_model:
            raise RuntimeError("Missing model name for LLM request")

        messages: list[dict] = []
        if system and system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "tools": tools,
            "temperature": self._resolve_temperature(temperature),
        }
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)

        message, _ = self._post_completion(payload, label="LLM tool")

        response_content: str | None = message.get("content")
        raw_tool_calls = message.get("tool_calls") or []
        tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            arguments_raw = fn.get("arguments", "{}")
            try:
                arguments = json.loads(arguments_raw)
            except (json.JSONDecodeError, TypeError):
                arguments = {}
            tool_calls.append({"name": name, "arguments": arguments})

        return {"content": response_content, "tool_calls": tool_calls}


@dataclass(frozen=True)
class CommandLLMClient(LLMClient):
    command: str
    timeout_s: int = 180

    def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        if not self.command.strip():
            raise RuntimeError("Command LLM provider: empty command")

        full_prompt = prompt
        if system and system.strip():
            full_prompt = f"{system.strip()}\n\n{prompt}"

        args = shlex.split(self.command)
        completed = _run_subprocess(
            args,
            input=full_prompt,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_s,
            env=os.environ.copy(),
        )
        if completed.returncode != 0:
            stderr_msg = (completed.stderr or completed.stdout or "").strip() or f"Command failed: {self.command}"
            raise RuntimeError(f"LLM command failed ({completed.returncode}): {stderr_msg}")
        return completed.stdout


@dataclass(frozen=True)
class BridgedIdeClient(LLMClient):
    """
    Client for 'Agentic IDE' mode (Mode 3).

    Uses `ide_bridge` to paste the prompt directly into the active IDE (Cursor, VSCode, etc).
    Also saves a backup file for reference.
    """

    profile: LLMProfile

    def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        """
        Sends the prompt to the active IDE.
        """
        # 1. format prompt
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_prompt = ""
        if system:
            full_prompt += f"## System Instruction\n\n{system}\n\n"
        full_prompt += f"## User Prompt\n\n{prompt}\n"

        # 2. Save backup (optional but good for history)
        filepath = None
        try:
            from src.config.paths import get_cache_dir

            prompts_dir = get_cache_dir() / "ide-bridge" / "prompts"
            prompts_dir.mkdir(parents=True, exist_ok=True)
            filename = f"context_builder_{timestamp}.md"
            filepath = prompts_dir / filename
            filepath.write_text(full_prompt, encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save prompt backup: %s", e)

        # 3. Send to IDE Bridge
        try:
            from ..scripts import ide_bridge
            from .usage_tracker import get_usage_tracker

            # Use 'effective_model' to pick IDE?
            # Ideally config.model might be "Cursor" or "VSCode"
            target_ide = self.profile.model if self.profile.model else None
            if target_ide == "ide-model":
                target_ide = None  # Auto-detect

            # Enforce Chat Line Limit Rule (User request: expects only ~3 lines)
            # If prompt is too long, send a summary pointing to the file
            content_to_send = full_prompt
            lines = full_prompt.splitlines()
            CLI_LINE_LIMIT = 5  # 3 lines text + 2 lines path/padding

            if len(lines) > CLI_LINE_LIMIT:
                file_ref = str(filepath) if filepath else "(backup unavailable)"
                content_to_send = f"Instructions generated ({len(lines)} lines)\n" f"Full context saved to: {file_ref}"

            result = ide_bridge.send_prompt(content_to_send, ide_name=target_ide)
            success = result.get("success", False)
            error = result.get("error") if not success else None

            # 4. Centralized Logging
            try:
                tracker = get_usage_tracker()
                tracker.track_request(
                    provider="agentic_ide",
                    profile=self.profile.name,
                    model=target_ide or "auto-detect",
                    prompt_tokens=len(full_prompt) // 4,  # Rough estimate
                    completion_tokens=0,
                    cost=0.0,
                    success=success,
                    error=error,
                    prompt_text=full_prompt,
                    response_text="[Sent to IDE]",
                )
            except Exception as e:
                logger.warning("Tracking failed: %s", e)

            if success:
                return f"✅ Prompt sent to IDE ({result.get('app_name', 'Unknown')}). Check your editor window."
            else:
                return f"❌ Failed to send to IDE: {error or 'Unknown error'}"

        except ImportError:
            return "❌ Error: plugins.platform.skills.platform.scripts.ide_bridge not found."
        except Exception as e:
            return f"❌ Error invoking IDE bridge: {e}"


_PROVIDER_IDS_BY_API_KEY_ENV = {
    "GLAMA_API_KEY": "glama",
    "OPENROUTER_API_KEY": "openrouter",
    "ANTHROPIC_API_KEY": "anthropic",
    "OPENAI_API_KEY": "openai",
    "GOOGLE_AI_API_KEY": "gemini",
    "GROQ_API_KEY": "groq",
    "TOGETHER_API_KEY": "together",
    "CUSTOM_LLM_API_KEY": "custom",
}


def _provider_ids_for_api_key_env(api_key_env: str | None) -> list[str]:
    env_name = (api_key_env or "").strip().upper()
    if not env_name:
        return []

    provider_ids: list[str] = []
    mapped = _PROVIDER_IDS_BY_API_KEY_ENV.get(env_name)
    if mapped:
        provider_ids.append(mapped)

    if env_name.endswith("_API_KEY"):
        derived = env_name[: -len("_API_KEY")].lower()
        if derived and derived not in provider_ids:
            provider_ids.append(derived)

    return provider_ids


def _load_stored_provider_key(profile: LLMProfile) -> str | None:
    provider_ids = _provider_ids_for_api_key_env(profile.api_key_env)
    if not provider_ids:
        return None

    try:
        from src.config.paths import get_project_root

        keys_path = Path(get_project_root()) / "config" / "integrations" / ".oauth-keys.json"
        raw = json.loads(keys_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.debug("Failed to load stored provider credentials: %s", exc)
        return None

    if not isinstance(raw, dict):
        return None

    for provider_id in provider_ids:
        value = raw.get(provider_id)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def _resolve_api_key(profile: LLMProfile) -> str | None:
    override = os.environ.get("AUGUR_LLM_API_KEY")
    if isinstance(override, str) and override.strip():
        return override.strip()

    if profile.api_key_env and profile.api_key_env.strip():
        v = os.environ.get(profile.api_key_env.strip())
        if isinstance(v, str) and v.strip():
            return v.strip()

    stored = _load_stored_provider_key(profile)
    if stored:
        return stored

    if profile.api_key and profile.api_key.strip():
        return profile.api_key.strip()

    return None


def create_llm_client(profile: LLMProfile) -> LLMClient:
    if profile.provider == "agentic_ide":
        return BridgedIdeClient(profile)

    if profile.provider == "command":
        if not profile.command or not profile.command.strip():
            raise RuntimeError(f"LLM profile '{profile.name}' is command-based but missing `command`")
        return CommandLLMClient(command=profile.command.strip(), timeout_s=profile.timeout_s)

    base_url = (profile.base_url or "").strip()
    model = (profile.model or "").strip()
    if not base_url:
        raise RuntimeError(f"LLM profile '{profile.name}' missing base_url")
    if not model:
        raise RuntimeError(f"LLM profile '{profile.name}' missing model")
    api_key = _resolve_api_key(profile)
    if profile.api_key_env and not api_key:
        raise RuntimeError(
            f"LLM profile '{profile.name}' requires {profile.api_key_env}, but no key was found in the "
            "environment or config/integrations/.oauth-keys.json."
        )

    return OpenAICompatibleClient(
        base_url=base_url,
        api_key=api_key,
        default_model=model,
        timeout_s=profile.timeout_s,
        response_format_json=profile.response_format_json,
        default_temperature=profile.temperature if profile.temperature is not None else 0.2,
        disable_thinking=profile.disable_thinking,
    )
