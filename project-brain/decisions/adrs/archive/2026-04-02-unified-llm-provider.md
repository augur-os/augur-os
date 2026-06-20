# Unified LLM Provider Abstraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route all LLM generation calls through the existing `LLMClient` abstraction with task-based profile routing, so a single config change (`llm.yaml`) controls local vs remote for all components.

**Architecture:** Extend `LLMClient` with `generate_with_vision()` and `generate_with_tools()` methods implemented on `OpenAICompatibleClient`. Migrate 5 bypass components to use `create_llm_client()` + profile resolution. Add airplane mode override at the `resolve_llm_profile()` layer.

**Tech Stack:** Python, OpenAI-compatible `/chat/completions` protocol, `urllib.request`, YAML config

---

### Task 1: Extend `LLMClient` Base Class with Vision and Tools

**Files:**
- Modify: `skills/ai/augur/lib/client.py:65-93`
- Test: `skills/ai/augur/tests/test_llm_client_extensions.py` (create)

- [ ] **Step 1: Write tests for new base class methods**

Create `skills/ai/augur/tests/test_llm_client_extensions.py`:

```python
"""Tests for LLMClient vision and tools extensions."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from skills.ai.augur.lib.client import (
    LLMClient,
    CommandLLMClient,
)


class TestLLMClientBaseVision:
    def test_base_class_raises_not_implemented(self):
        client = LLMClient()
        with pytest.raises(NotImplementedError, match="LLMClient does not support vision"):
            client.generate_with_vision(prompt="describe", images=[b"\x89PNG"])

    def test_command_client_raises_not_implemented(self):
        client = CommandLLMClient(command="echo test")
        with pytest.raises(NotImplementedError, match="CommandLLMClient does not support vision"):
            client.generate_with_vision(prompt="describe", images=[b"\x89PNG"])


class TestLLMClientBaseTools:
    def test_base_class_raises_not_implemented(self):
        client = LLMClient()
        with pytest.raises(NotImplementedError, match="LLMClient does not support tool use"):
            client.generate_with_tools(prompt="call search", tools=[{"type": "function", "function": {"name": "search"}}])

    def test_command_client_raises_not_implemented(self):
        client = CommandLLMClient(command="echo test")
        with pytest.raises(NotImplementedError, match="CommandLLMClient does not support tool use"):
            client.generate_with_tools(prompt="call search", tools=[{"type": "function", "function": {"name": "search"}}])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_client_extensions.py -v`
Expected: FAIL — `generate_with_vision` and `generate_with_tools` don't exist on `LLMClient`

- [ ] **Step 3: Add vision and tools methods to LLMClient base class**

In `skills/ai/augur/lib/client.py`, add these methods to the `LLMClient` class (after `generate_json`, around line 93):

```python
    def generate_with_vision(
        self,
        *,
        prompt: str,
        images: list[bytes | str],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
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
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict:
        raise NotImplementedError(f"{type(self).__name__} does not support tool use")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_client_extensions.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ai/augur/lib/client.py skills/ai/augur/tests/test_llm_client_extensions.py
git commit -m "feat(llm): add generate_with_vision and generate_with_tools to LLMClient base"
```

---

### Task 2: Implement Vision on `OpenAICompatibleClient`

**Files:**
- Modify: `skills/ai/augur/lib/client.py:97-272` (OpenAICompatibleClient)
- Modify: `skills/ai/augur/tests/test_llm_client_extensions.py`

- [ ] **Step 1: Write tests for vision on OpenAICompatibleClient**

Append to `skills/ai/augur/tests/test_llm_client_extensions.py`:

```python
import json
from unittest.mock import patch, MagicMock
import base64


class TestOpenAICompatibleVision:
    def _make_client(self):
        from skills.ai.augur.lib.client import OpenAICompatibleClient
        return OpenAICompatibleClient(
            base_url="http://localhost:11434/v1",
            api_key=None,
            default_model="llava-llama3",
        )

    def _mock_response(self, content_text: str) -> bytes:
        return json.dumps({
            "choices": [{"message": {"content": content_text}}]
        }).encode("utf-8")

    def test_vision_with_bytes_image(self):
        client = self._make_client()
        fake_image = b"\x89PNG\r\n\x1a\nfakedata"

        mock_resp = MagicMock()
        mock_resp.read.return_value = self._mock_response("A cat sitting on a mat")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            result = client.generate_with_vision(prompt="What is this?", images=[fake_image])

        assert result == "A cat sitting on a mat"
        # Verify the request payload
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        user_msg = payload["messages"][-1]
        assert user_msg["role"] == "user"
        assert user_msg["content"][0] == {"type": "text", "text": "What is this?"}
        assert user_msg["content"][1]["type"] == "image_url"
        b64 = base64.b64encode(fake_image).decode("ascii")
        assert user_msg["content"][1]["image_url"]["url"] == f"data:image/png;base64,{b64}"

    def test_vision_with_url_image(self):
        client = self._make_client()
        image_url = "https://example.com/image.png"

        mock_resp = MagicMock()
        mock_resp.read.return_value = self._mock_response("A dog")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.generate_with_vision(prompt="Describe", images=[image_url])

        assert result == "A dog"

    def test_vision_with_system_prompt(self):
        client = self._make_client()

        mock_resp = MagicMock()
        mock_resp.read.return_value = self._mock_response("OCR result")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            client.generate_with_vision(
                prompt="Extract text", images=[b"img"],
                system="You are an OCR engine",
            )

        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["messages"][0] == {"role": "system", "content": "You are an OCR engine"}

    def test_vision_with_multiple_images(self):
        client = self._make_client()

        mock_resp = MagicMock()
        mock_resp.read.return_value = self._mock_response("Two images")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            client.generate_with_vision(
                prompt="Compare", images=[b"img1", "https://example.com/img2.png"],
            )

        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        content = payload["messages"][-1]["content"]
        assert len(content) == 3  # 1 text + 2 images
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_client_extensions.py::TestOpenAICompatibleVision -v`
Expected: FAIL — `OpenAICompatibleClient` inherits base `NotImplementedError`

- [ ] **Step 3: Implement generate_with_vision on OpenAICompatibleClient**

Add this method to the `OpenAICompatibleClient` class in `skills/ai/augur/lib/client.py` (after `generate_text`, before the class ends):

```python
    def generate_with_vision(
        self,
        *,
        prompt: str,
        images: list[bytes | str],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        import base64 as _b64

        url = f"{_strip_trailing_slash(self.base_url)}/chat/completions"
        effective_model = (model or self.default_model).strip()
        if not effective_model:
            raise RuntimeError("Missing model name for LLM request")

        messages: list[dict[str, Any]] = []
        if system and system.strip():
            messages.append({"role": "system", "content": system.strip()})

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images:
            if isinstance(img, bytes):
                b64 = _b64.b64encode(img).decode("ascii")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })
            else:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": img},
                })

        messages.append({"role": "user", "content": content})

        payload: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "temperature": (
                float(temperature)
                if temperature != 0.2
                else (self.default_temperature if self.default_temperature is not None else 0.2)
            ),
        }
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)

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
                pass
            raise RuntimeError(f"LLM vision request failed ({e.code}): {body.strip() or e}") from e
        except Exception as e:
            raise RuntimeError(f"LLM vision request failed: {e}") from e

        parsed = json.loads(raw)
        choices = parsed.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("LLM response missing choices[]")
        message = (choices[0] or {}).get("message")
        if not isinstance(message, dict):
            raise RuntimeError("LLM response missing message")
        content_text = message.get("content")
        if not isinstance(content_text, str):
            raise RuntimeError("LLM response missing content")
        return content_text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_client_extensions.py::TestOpenAICompatibleVision -v`
Expected: All 4 vision tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ai/augur/lib/client.py skills/ai/augur/tests/test_llm_client_extensions.py
git commit -m "feat(llm): implement generate_with_vision on OpenAICompatibleClient"
```

---

### Task 3: Implement Tools on `OpenAICompatibleClient`

**Files:**
- Modify: `skills/ai/augur/lib/client.py:97-272` (OpenAICompatibleClient)
- Modify: `skills/ai/augur/tests/test_llm_client_extensions.py`

- [ ] **Step 1: Write tests for tools on OpenAICompatibleClient**

Append to `skills/ai/augur/tests/test_llm_client_extensions.py`:

```python
class TestOpenAICompatibleTools:
    def _make_client(self):
        from skills.ai.augur.lib.client import OpenAICompatibleClient
        return OpenAICompatibleClient(
            base_url="http://localhost:11434/v1",
            api_key=None,
            default_model="qwen3.5:9b",
        )

    def _mock_tool_response(self, content: str | None, tool_calls: list[dict]) -> bytes:
        msg: dict[str, Any] = {}
        if content is not None:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = [
                {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                }
                for i, tc in enumerate(tool_calls)
            ]
        return json.dumps({"choices": [{"message": msg}]}).encode("utf-8")

    def test_tools_returns_tool_calls(self):
        client = self._make_client()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_knowledge",
                    "description": "Search the knowledge base",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            }
        ]

        mock_resp = MagicMock()
        mock_resp.read.return_value = self._mock_tool_response(
            content=None,
            tool_calls=[{"name": "search_knowledge", "arguments": {"query": "RAG indexing"}}],
        )
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.generate_with_tools(prompt="Search for RAG", tools=tools)

        assert result["content"] is None
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "search_knowledge"
        assert result["tool_calls"][0]["arguments"] == {"query": "RAG indexing"}

    def test_tools_with_text_and_tool_calls(self):
        client = self._make_client()
        tools = [{"type": "function", "function": {"name": "read_resource", "parameters": {}}}]

        mock_resp = MagicMock()
        mock_resp.read.return_value = self._mock_tool_response(
            content="I'll search for that.",
            tool_calls=[{"name": "read_resource", "arguments": {"uri": "docs/README.md"}}],
        )
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.generate_with_tools(prompt="Read the readme", tools=tools)

        assert result["content"] == "I'll search for that."
        assert len(result["tool_calls"]) == 1

    def test_tools_payload_includes_tools_key(self):
        client = self._make_client()
        tools = [{"type": "function", "function": {"name": "test_tool", "parameters": {}}}]

        mock_resp = MagicMock()
        mock_resp.read.return_value = self._mock_tool_response(content="ok", tool_calls=[])
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            client.generate_with_tools(prompt="test", tools=tools)

        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["tools"] == tools

    def test_tools_no_tool_calls_in_response(self):
        client = self._make_client()
        tools = [{"type": "function", "function": {"name": "noop", "parameters": {}}}]

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "No tools needed"}}]
        }).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.generate_with_tools(prompt="hello", tools=tools)

        assert result["content"] == "No tools needed"
        assert result["tool_calls"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_client_extensions.py::TestOpenAICompatibleTools -v`
Expected: FAIL — `OpenAICompatibleClient` inherits base `NotImplementedError`

- [ ] **Step 3: Implement generate_with_tools on OpenAICompatibleClient**

Add this method to `OpenAICompatibleClient` in `skills/ai/augur/lib/client.py` (after `generate_with_vision`):

```python
    def generate_with_tools(
        self,
        *,
        prompt: str,
        tools: list[dict],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict:
        url = f"{_strip_trailing_slash(self.base_url)}/chat/completions"
        effective_model = (model or self.default_model).strip()
        if not effective_model:
            raise RuntimeError("Missing model name for LLM request")

        messages: list[dict[str, Any]] = []
        if system and system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "tools": tools,
            "temperature": (
                float(temperature)
                if temperature != 0.2
                else (self.default_temperature if self.default_temperature is not None else 0.2)
            ),
        }
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)

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
                pass
            raise RuntimeError(f"LLM tools request failed ({e.code}): {body.strip() or e}") from e
        except Exception as e:
            raise RuntimeError(f"LLM tools request failed: {e}") from e

        parsed = json.loads(raw)
        choices = parsed.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("LLM response missing choices[]")
        message = (choices[0] or {}).get("message", {})

        content = message.get("content")
        raw_tool_calls = message.get("tool_calls", [])

        tool_calls = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            arguments_str = func.get("arguments", "{}")
            try:
                arguments = json.loads(arguments_str)
            except (json.JSONDecodeError, TypeError):
                arguments = {}
            tool_calls.append({"name": name, "arguments": arguments})

        return {"content": content, "tool_calls": tool_calls}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_client_extensions.py::TestOpenAICompatibleTools -v`
Expected: All 4 tools tests PASS

- [ ] **Step 5: Run all extension tests together**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_client_extensions.py -v`
Expected: All 12 tests PASS

- [ ] **Step 6: Commit**

```bash
git add skills/ai/augur/lib/client.py skills/ai/augur/tests/test_llm_client_extensions.py
git commit -m "feat(llm): implement generate_with_tools on OpenAICompatibleClient"
```

---

### Task 4: Add Airplane Mode Override to `resolve_llm_profile`

**Files:**
- Modify: `skills/ai/augur/lib/config.py:204-272`
- Test: `skills/ai/augur/tests/test_llm_config_airplane.py` (create)

- [ ] **Step 1: Write tests for airplane mode override**

Create `skills/ai/augur/tests/test_llm_config_airplane.py`:

```python
"""Tests for airplane mode override in resolve_llm_profile."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from skills.ai.augur.lib.config import LLMConfig, LLMProfile, resolve_llm_profile


def _make_config() -> LLMConfig:
    return LLMConfig(
        active_profile="remote",
        profiles={
            "local": LLMProfile(name="local", provider="openai_compatible", base_url="http://localhost:11434/v1", model="qwen3.5:9b"),
            "remote": LLMProfile(name="remote", provider="openai_compatible", base_url="https://api.groq.com/openai/v1", model="llama-3.3-70b"),
        },
        tasks={"contextualizer": "remote"},
    )


class TestAirplaneModeOverride:
    def test_airplane_off_uses_normal_resolution(self):
        config = _make_config()
        with patch("skills.ai.augur.lib.config._is_airplane_mode", return_value=False):
            profile = resolve_llm_profile(config, task="contextualizer")
        assert profile.name == "remote"

    def test_airplane_on_forces_local_profile(self):
        config = _make_config()
        with patch("skills.ai.augur.lib.config._is_airplane_mode", return_value=True):
            profile = resolve_llm_profile(config)
        assert profile.name == "local"

    def test_airplane_on_overrides_task_routing(self):
        config = _make_config()
        with patch("skills.ai.augur.lib.config._is_airplane_mode", return_value=True):
            profile = resolve_llm_profile(config, task="contextualizer")
        assert profile.name == "local"

    def test_explicit_name_overrides_airplane(self):
        config = _make_config()
        with patch("skills.ai.augur.lib.config._is_airplane_mode", return_value=True):
            profile = resolve_llm_profile(config, name="remote")
        assert profile.name == "remote"

    def test_airplane_on_no_local_profile_falls_through(self):
        config = LLMConfig(
            active_profile="remote",
            profiles={
                "remote": LLMProfile(name="remote", provider="openai_compatible", base_url="https://api.groq.com", model="m"),
            },
        )
        with patch("skills.ai.augur.lib.config._is_airplane_mode", return_value=True):
            profile = resolve_llm_profile(config)
        assert profile.name == "remote"

    def test_airplane_env_var(self):
        config = _make_config()
        with patch.dict(os.environ, {"AUGUR_AIRPLANE_MODE": "1"}):
            profile = resolve_llm_profile(config)
        assert profile.name == "local"

    def test_airplane_env_var_off(self):
        config = _make_config()
        env = {k: v for k, v in os.environ.items() if k != "AUGUR_AIRPLANE_MODE"}
        with patch.dict(os.environ, env, clear=True):
            profile = resolve_llm_profile(config)
        assert profile.name == "remote"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_config_airplane.py -v`
Expected: FAIL — `_is_airplane_mode` doesn't exist

- [ ] **Step 3: Implement airplane mode check and override**

In `skills/ai/augur/lib/config.py`, add the `_is_airplane_mode()` function (before `resolve_llm_profile`, around line 200):

```python
def _is_airplane_mode() -> bool:
    """Check if airplane mode is active.

    Checks (in order):
    1. AUGUR_AIRPLANE_MODE env var ("1", "true", "yes")
    2. preferences.yaml airplane_mode.enabled
    """
    env_val = os.environ.get("AUGUR_AIRPLANE_MODE", "").strip().lower()
    if env_val in ("1", "true", "yes"):
        return True

    try:
        from src.config.paths import get_config_dir
        import yaml

        prefs_path = get_config_dir() / "preferences.yaml"
        if prefs_path.exists():
            data = yaml.safe_load(prefs_path.read_text(encoding="utf-8")) or {}
            airplane = data.get("airplane_mode", {})
            if isinstance(airplane, dict) and airplane.get("enabled"):
                return True
    except Exception:
        pass

    return False
```

Then modify `resolve_llm_profile` to add the airplane override after the explicit name check (line ~223, after the `if name and name in config.profiles` block):

```python
    # 1. Explicit name takes precedence
    if name and name in config.profiles:
        return config.profiles[name]

    # 1.5 Airplane mode override (before task/context resolution)
    if _is_airplane_mode():
        local = config.profiles.get("local")
        if local:
            return local

    # Resolve active profile name based on context
    candidate_name = config.active_profile
    # ... rest unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_config_airplane.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Run existing config tests to check for regressions**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/ -v`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add skills/ai/augur/lib/config.py skills/ai/augur/tests/test_llm_config_airplane.py
git commit -m "feat(llm): add airplane mode override to resolve_llm_profile"
```

---

### Task 5: Migrate Contextualizer to `LLMClient`

**Files:**
- Modify: `skills/rag/scripts/contextualizer.py`
- Modify: `skills/rag/augur/tests/test_contextualizer.py` (if exists, else create)

- [ ] **Step 1: Write tests for migrated Contextualizer**

Create `skills/rag/augur/tests/test_contextualizer_llm.py`:

```python
"""Tests for Contextualizer using LLMClient abstraction."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.rag.scripts.contextualizer import Contextualizer


class TestContextualizerWithLLMClient:
    def test_uses_injected_client(self):
        mock_client = MagicMock()
        mock_client.generate_text.return_value = "This chunk covers RAG indexing."

        ctx = Contextualizer(client=mock_client)
        result = ctx.generate_context("full document text", "chunk about RAG")

        assert result == "This chunk covers RAG indexing."
        mock_client.generate_text.assert_called_once()

    def test_returns_empty_on_client_failure(self):
        mock_client = MagicMock()
        mock_client.generate_text.side_effect = RuntimeError("connection refused")

        ctx = Contextualizer(client=mock_client)
        result = ctx.generate_context("doc", "chunk")

        assert result == ""

    def test_returns_empty_when_no_client(self):
        ctx = Contextualizer(client=None)
        result = ctx.generate_context("doc", "chunk")
        assert result == ""

    def test_auto_resolves_client_from_config(self):
        mock_client = MagicMock()
        mock_client.generate_text.return_value = "context"

        with patch("skills.rag.scripts.contextualizer.load_llm_config") as mock_load, \
             patch("skills.rag.scripts.contextualizer.resolve_llm_profile") as mock_resolve, \
             patch("skills.rag.scripts.contextualizer.create_llm_client", return_value=mock_client):
            ctx = Contextualizer()
            result = ctx.generate_context("doc", "chunk")

        assert result == "context"
        mock_resolve.assert_called_once()
        # Verify task="contextualizer" was passed
        call_kwargs = mock_resolve.call_args
        assert call_kwargs[1].get("task") == "contextualizer" or call_kwargs.kwargs.get("task") == "contextualizer"

    def test_enrich_chunks_uses_cache(self):
        mock_client = MagicMock()
        mock_client.generate_text.return_value = "context for chunk"

        ctx = Contextualizer(client=mock_client)
        chunks = [
            {"text": "same content"},
            {"text": "same content"},  # duplicate — should hit cache
        ]
        ctx.enrich_chunks("doc", chunks)

        assert mock_client.generate_text.call_count == 1
        assert chunks[0]["context"] == "context for chunk"
        assert chunks[1]["context"] == "context for chunk"

    def test_max_tokens_passed_to_client(self):
        mock_client = MagicMock()
        mock_client.generate_text.return_value = "short"

        ctx = Contextualizer(client=mock_client, max_context_tokens=50)
        ctx.generate_context("doc", "chunk")

        call_kwargs = mock_client.generate_text.call_args[1]
        assert call_kwargs["max_tokens"] == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_contextualizer_llm.py -v`
Expected: FAIL — Contextualizer constructor doesn't accept `client` parameter

- [ ] **Step 3: Rewrite Contextualizer to use LLMClient**

Replace the full content of `skills/rag/scripts/contextualizer.py`:

```python
"""
Contextualizer — generates contextual prefixes for RAG chunks via LLMClient.

Uses the unified LLM provider abstraction (skills/ai/augur/lib/) with
task="contextualizer" for profile routing. Implements:
- Checksum-based caching (md5 of chunk_text) to skip unchanged chunks
- Circuit breaker: 3 failures opens, 300s cooldown
- Graceful degradation: returns empty string on LLM failure
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from skills.rag.scripts._circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
<document>
{document_text}
</document>

Here is a chunk from that document:
<chunk>
{chunk_text}
</chunk>

Write a short (1-2 sentence) context that situates this chunk within the document.
Include: what document/skill this is from, what section, and what the chunk specifically covers.
Do not repeat the chunk content. Only provide the context sentence(s)."""


_llm_cb = CircuitBreaker(threshold=3, cooldown=300.0)


def _resolve_client():
    """Auto-resolve LLMClient from config with task='contextualizer'."""
    try:
        from skills.ai.augur.lib import load_llm_config, resolve_llm_profile, create_llm_client

        config = load_llm_config()
        profile = resolve_llm_profile(config, task="contextualizer")
        return create_llm_client(profile)
    except Exception as exc:
        logger.warning("Failed to resolve LLM client for contextualizer: %s", exc)
        return None


# Lazy imports for type checking
try:
    from skills.ai.augur.lib.client import LLMClient as _LLMClient
except ImportError:
    _LLMClient = None  # type: ignore[assignment,misc]


class Contextualizer:
    """Generate contextual prefixes for RAG chunks via LLMClient."""

    def __init__(
        self,
        client=None,
        max_doc_chars: int = 3000,
        max_context_tokens: int = 100,
    ):
        self._client = client if client is not None else _resolve_client()
        self.max_doc_chars = max_doc_chars
        self.max_context_tokens = max_context_tokens
        self._cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def generate_context(self, document_text: str, chunk_text: str) -> str:
        """Generate 1-2 sentence context. Returns empty string on failure."""
        if self._client is None:
            return ""
        if _llm_cb.is_open:
            logger.debug("Contextualizer circuit breaker open — skipping LLM call")
            return ""

        prompt = _PROMPT_TEMPLATE.format(
            document_text=document_text[: self.max_doc_chars],
            chunk_text=chunk_text,
        )

        try:
            context = self._client.generate_text(
                prompt=prompt,
                max_tokens=self.max_context_tokens,
                temperature=0.1,
            )
            _llm_cb.record_success()
            return context.strip()
        except Exception as exc:
            logger.warning("Contextualizer LLM error: %s", exc)
            _llm_cb.record_failure()
            return ""

    # ------------------------------------------------------------------
    # Batch enrichment
    # ------------------------------------------------------------------

    def enrich_chunks(self, document_text: str, chunks: list[dict]) -> list[dict]:
        """Add 'context' key to each chunk dict. Returns same list (mutates in place)."""
        for chunk in chunks:
            chunk_text = chunk.get("text", "")
            checksum = hashlib.md5(chunk_text.encode("utf-8")).hexdigest()

            if checksum in self._cache:
                chunk["context"] = self._cache[checksum]
            else:
                context = self.generate_context(document_text, chunk_text)
                self._cache[checksum] = context
                chunk["context"] = context

        return chunks

    # ------------------------------------------------------------------
    # Cache persistence
    # ------------------------------------------------------------------

    def _default_cache_path(self) -> Path:
        from src.config.paths import get_runtime_dir

        return get_runtime_dir() / "adaptive" / "rag_context_cache.json"

    def save_cache(self, path: Optional[Path] = None) -> None:
        """Write self._cache dict as JSON to the cache file."""
        cache_path = Path(path) if path else self._default_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")
        logger.debug("Contextualizer cache saved to %s (%d entries)", cache_path, len(self._cache))

    def load_cache(self, path: Optional[Path] = None) -> None:
        """Read cache JSON back into self._cache."""
        cache_path = Path(path) if path else self._default_cache_path()
        if not cache_path.exists():
            logger.debug("No cache file at %s — starting fresh", cache_path)
            return
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._cache.update(data)
                logger.debug("Contextualizer cache loaded from %s (%d entries)", cache_path, len(data))
        except Exception as exc:
            logger.warning("Failed to load contextualizer cache from %s: %s", cache_path, exc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_contextualizer_llm.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Run existing RAG tests for regressions**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
git add skills/rag/scripts/contextualizer.py skills/rag/augur/tests/test_contextualizer_llm.py
git commit -m "refactor(rag): migrate Contextualizer from httpx/Ollama to LLMClient"
```

---

### Task 6: Migrate Document Extractor to `LLMClient`

**Files:**
- Modify: `skills/document-extractor/scripts/ollama_client.py` (rewrite)
- Modify: `skills/document-extractor/scripts/mcp/tools_extract.py:30` (update import)
- Modify: `skills/document-extractor/scripts/extractor.py:26` (remove unused import)
- Test: `skills/document-extractor/augur/tests/test_ollama_client.py` (rewrite)

- [ ] **Step 1: Write tests for the new vision client module**

Rewrite `skills/document-extractor/augur/tests/test_ollama_client.py`:

```python
"""Tests for document extractor LLM vision client."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestGetVisionClient:
    def test_returns_client_from_config(self):
        mock_client = MagicMock()

        with patch("ollama_client.load_llm_config") as mock_load, \
             patch("ollama_client.resolve_llm_profile") as mock_resolve, \
             patch("ollama_client.create_llm_client", return_value=mock_client):
            from ollama_client import get_vision_client
            result = get_vision_client()

        assert result is mock_client
        mock_resolve.assert_called_once()
        call_kwargs = mock_resolve.call_args[1] if mock_resolve.call_args[1] else {}
        assert call_kwargs.get("task") == "document_ocr"

    def test_returns_none_on_config_failure(self):
        with patch("ollama_client.load_llm_config", side_effect=RuntimeError("no config")):
            from ollama_client import get_vision_client
            result = get_vision_client()

        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/document-extractor/augur/tests/test_ollama_client.py -v`
Expected: FAIL — current module has different interface

- [ ] **Step 3: Rewrite ollama_client.py to use LLMClient**

Replace `skills/document-extractor/scripts/ollama_client.py`:

```python
"""LLM vision client for document extraction — uses unified LLM provider."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from skills.ai.augur.lib import load_llm_config, resolve_llm_profile, create_llm_client
except ImportError:
    load_llm_config = None  # type: ignore[assignment]
    resolve_llm_profile = None  # type: ignore[assignment]
    create_llm_client = None  # type: ignore[assignment]


def get_vision_client():
    """Resolve an LLMClient for document OCR via the unified config.

    Returns an LLMClient instance or None if config resolution fails.
    The caller should use client.generate_with_vision() for image inputs.
    """
    if load_llm_config is None:
        logger.warning("LLM config module not available for document extraction")
        return None

    try:
        config = load_llm_config()
        profile = resolve_llm_profile(config, task="document_ocr")
        return create_llm_client(profile)
    except Exception as exc:
        logger.warning("Failed to resolve vision LLM client: %s", exc)
        return None
```

- [ ] **Step 4: Update tools_extract.py import**

In `skills/document-extractor/scripts/mcp/tools_extract.py`, change line 30 from:
```python
from ollama_client import is_ollama_running, get_default_vision_model
```
to:
```python
from ollama_client import get_vision_client
```

Then update the code that uses `is_ollama_running` and `get_default_vision_model` to use `get_vision_client()` instead. Where the old code checked `is_ollama_running()`, check `get_vision_client() is not None`.

- [ ] **Step 5: Remove unused import from extractor.py**

In `skills/document-extractor/scripts/extractor.py`, remove line 26:
```python
from src.lib.llm_cli import get_llm_cli_config
```
This import is never used in the file.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/document-extractor/augur/tests/test_ollama_client.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add skills/document-extractor/scripts/ollama_client.py skills/document-extractor/scripts/mcp/tools_extract.py skills/document-extractor/scripts/extractor.py skills/document-extractor/augur/tests/test_ollama_client.py
git commit -m "refactor(doc-extractor): migrate from direct Ollama/OpenAI SDK to LLMClient"
```

---

### Task 7: Migrate Action Evals to `LLMClient`

**Files:**
- Modify: `skills/advisor/scripts/analytics/run_action_evals.py`

- [ ] **Step 1: Write tests for migrated action evals**

Create `skills/advisor/augur/tests/test_action_evals_llm.py`:

```python
"""Tests for action evals using LLMClient."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestActionEvalRunnerLLMClient:
    def test_uses_generate_with_tools(self):
        mock_client = MagicMock()
        mock_client.generate_with_tools.return_value = {
            "content": None,
            "tool_calls": [{"name": "search_knowledge", "arguments": {"query": "test"}}],
        }

        with patch("skills.advisor.scripts.analytics.run_action_evals.load_llm_config"), \
             patch("skills.advisor.scripts.analytics.run_action_evals.resolve_llm_profile"), \
             patch("skills.advisor.scripts.analytics.run_action_evals.create_llm_client", return_value=mock_client):
            from skills.advisor.scripts.analytics.run_action_evals import ActionEvalRunner
            # Patch _load_config to avoid needing the YAML file
            with patch.object(ActionEvalRunner, "_load_config", return_value={"buttons": []}):
                runner = ActionEvalRunner()

        assert runner.client is mock_client

    def test_tool_schema_is_openai_format(self):
        """Verify _get_mock_tools returns OpenAI-format tool schemas."""
        with patch("skills.advisor.scripts.analytics.run_action_evals.load_llm_config"), \
             patch("skills.advisor.scripts.analytics.run_action_evals.resolve_llm_profile"), \
             patch("skills.advisor.scripts.analytics.run_action_evals.create_llm_client", return_value=MagicMock()):
            from skills.advisor.scripts.analytics.run_action_evals import ActionEvalRunner
            with patch.object(ActionEvalRunner, "_load_config", return_value={"buttons": []}):
                runner = ActionEvalRunner()

        tools = runner._get_mock_tools()
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/advisor/augur/tests/test_action_evals_llm.py -v`
Expected: FAIL — current code uses `import anthropic`

- [ ] **Step 3: Rewrite ActionEvalRunner to use LLMClient**

In `skills/advisor/scripts/analytics/run_action_evals.py`, make these changes:

Remove the anthropic import block (lines 29-33):
```python
# DELETE:
try:
    import anthropic
except ImportError:
    _out("Error: 'anthropic' package not found. Please run: pip install anthropic")
    sys.exit(1)
```

Replace with:
```python
try:
    from skills.ai.augur.lib import load_llm_config, resolve_llm_profile, create_llm_client
except ImportError:
    _out("Error: 'skills.ai.augur.lib' not importable. Check PYTHONPATH.")
    sys.exit(1)
```

Rewrite `ActionEvalRunner.__init__` (lines 41-49):
```python
class ActionEvalRunner:
    def __init__(self):
        try:
            config = load_llm_config()
            profile = resolve_llm_profile(config, task="action_evals")
            self.client = create_llm_client(profile)
        except Exception as e:
            _out(f"Warning: Failed to initialize LLM client: {e}")
            self.client = None
        self.config = self._load_config()
```

Rewrite `_get_mock_tools` to use OpenAI-format tool schemas (lines 106-136):
```python
    def _get_mock_tools(self) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_resource",
                    "description": "Read a resource content by URI",
                    "parameters": {
                        "type": "object",
                        "properties": {"uri": {"type": "string", "description": "The URI of the resource"}},
                        "required": ["uri"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run a shell command",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string", "description": "Command to run"}},
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_knowledge",
                    "description": "Search the knowledge base",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "Search query"}},
                        "required": ["query"],
                    },
                },
            },
        ]
```

Rewrite `run_eval` LLM call and response parsing (lines 158-180):
```python
        # 2. Call LLM
        if not self.client:
            _out("  ⚠️ Skipping API call (No LLM client). Assuming pass for structural check.")
            return True

        try:
            result = self.client.generate_with_tools(
                prompt=eval_case["input"],
                tools=self._get_mock_tools(),
                system=system_prompt,
                max_tokens=1024,
                temperature=0.2,
            )
        except Exception as e:
            _out(f"  ❌ API Call Failed: {e}")
            return False

        # 3. Analyze Response
        actual_tools = result.get("tool_calls", [])
```

Update the verification loop (lines 198-221) — `actual_tools` entries now have `name` and `arguments` keys directly (not `block.name` and `block.input`):
```python
        for exp in expected:
            tool_name = exp["tool"]
            args_contains = exp.get("args_contains", {})

            match = False
            for act in actual_tools:
                if act["name"] == tool_name:
                    args_match = True
                    for k, v in args_contains.items():
                        if k not in act["arguments"] or v not in str(act["arguments"][k]):
                            args_match = False
                            break
                    if args_match:
                        match = True
                        break

            if match:
                _out(f"  ✅ Triggered tool '{tool_name}' with correct args.")
            else:
                _out(f"  ❌ Failed to trigger tool '{tool_name}' with args containing {args_contains}")
                _out(f"     Actual calls: {actual_tools}")
                all_passed = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/advisor/augur/tests/test_action_evals_llm.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/advisor/scripts/analytics/run_action_evals.py skills/advisor/augur/tests/test_action_evals_llm.py
git commit -m "refactor(advisor): migrate action evals from Anthropic SDK to LLMClient"
```

---

### Task 8: Migrate File Manager Autoloop and Deprecate `llm_cli.py`

**Files:**
- Modify: `skills/file-manager/scripts/autoloop.py:37,309`
- Delete: `src/lib/llm_cli.py`
- Delete: `tests/test_llm_cli.py`

- [ ] **Step 1: Update file-manager autoloop to use LLMClient**

In `skills/file-manager/scripts/autoloop.py`, replace line 37:
```python
from src.lib.llm_cli import spawn_cli_prompt
```
with:
```python
from skills.ai.augur.lib import load_llm_config, resolve_llm_profile, create_llm_client
```

Replace the function that calls `spawn_cli_prompt` (around line 300-314). Find the call at line 309:
```python
    output = spawn_cli_prompt(prompt)
```
Replace with:
```python
    output = None
    try:
        config = load_llm_config()
        profile = resolve_llm_profile(config, task="file_summarization")
        client = create_llm_client(profile)
        output = client.generate_text(prompt=prompt)
    except Exception:
        pass
```

- [ ] **Step 2: Verify no other files import from llm_cli**

Run: `cd ~/Projects/Augur && grep -rn "from src.lib.llm_cli\|import llm_cli" --include='*.py' | grep -v test_llm_cli.py | grep -v llm_cli.py`
Expected: Only the file-manager autoloop line (which you just changed) and the extractor.py line (which was removed in Task 6)

- [ ] **Step 3: Delete llm_cli.py and its test**

```bash
rm src/lib/llm_cli.py tests/test_llm_cli.py
```

- [ ] **Step 4: Run file-manager tests (if any)**

Run: `cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/ -v 2>/dev/null || echo "No tests found"`

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/autoloop.py
git rm src/lib/llm_cli.py tests/test_llm_cli.py
git commit -m "refactor: deprecate llm_cli.py, migrate file-manager to LLMClient"
```

---

### Task 9: Update LLM Retry `resolve_cli()` to Read from `llm.yaml`

**Files:**
- Modify: `src/lib/llm_retry.py:286-343`

- [ ] **Step 1: Write test for updated resolve_cli**

Create `tests/test_llm_retry_config.py`:

```python
"""Tests for llm_retry resolve_cli reading from llm.yaml profiles."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.llm_retry import resolve_cli


class TestResolveCLIFromProfiles:
    def test_explicit_cli_setting_still_works(self):
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            result = resolve_cli("claude")
        assert result == "/usr/local/bin/claude"

    def test_auto_resolves_from_llm_yaml(self):
        mock_profile = MagicMock()
        mock_profile.provider = "command"
        mock_profile.command = "claude --print"

        with patch("src.lib.llm_retry._resolve_cli_from_llm_config", return_value="claude --print"):
            with patch("shutil.which", return_value="/usr/local/bin/claude"):
                result = resolve_cli("auto")
        assert result is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest tests/test_llm_retry_config.py -v`
Expected: FAIL — `_resolve_cli_from_llm_config` doesn't exist

- [ ] **Step 3: Add `_resolve_cli_from_llm_config` helper**

In `src/lib/llm_retry.py`, add a new helper function before `resolve_cli` (around line 285):

```python
def _resolve_cli_from_llm_config() -> str | None:
    """Try to resolve CLI command from llm.yaml task='retry_diagnosis' profile.

    Returns the command string if a 'command' provider profile is found, else None.
    Intentionally lightweight — catches all exceptions to stay safe in retry paths.
    """
    try:
        root = _find_project_root()
        if root is None:
            return None
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from skills.ai.augur.lib import load_llm_config, resolve_llm_profile
        config = load_llm_config()
        profile = resolve_llm_profile(config, task="retry_diagnosis")
        if profile.provider == "command" and profile.command:
            return profile.command.strip()
    except Exception:
        pass
    return None
```

Then in `resolve_cli`, add this as the first check in the `auto` path (after line 296, inside the `if cli_setting != "auto"` else branch). Insert before the existing llm.yaml read:

```python
    # Check llm.yaml profiles first (unified config)
    llm_config_cmd = _resolve_cli_from_llm_config()
    if llm_config_cmd:
        first_token = llm_config_cmd.split()[0]
        resolved = shutil.which(first_token)
        if resolved:
            return resolved
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest tests/test_llm_retry_config.py -v`
Expected: PASS

- [ ] **Step 5: Run existing llm_retry tests**

Run: `cd ~/Projects/Augur && python -m pytest tests/ -k "llm_retry" -v 2>/dev/null || echo "No existing tests"`

- [ ] **Step 6: Commit**

```bash
git add src/lib/llm_retry.py tests/test_llm_retry_config.py
git commit -m "refactor(llm-retry): resolve CLI from llm.yaml unified config"
```

---

### Task 10: Add Default Task Entries to `llm.yaml`

**Files:**
- Modify: `config/system/llm.yaml` (or `config/defaults/config/system/llm.yaml`)

- [ ] **Step 1: Check current llm.yaml content**

Read the existing `config/system/llm.yaml` to see what's already there.

- [ ] **Step 2: Add task routing entries**

Add a `tasks:` section to the system llm.yaml if not present:

```yaml
tasks:
  contextualizer: local
  search_ranking: remote
  search_eval: remote
  iterative_search: remote
  document_ocr: vision-local
  action_evals: remote
  file_summarization: local
  retry_diagnosis: local
  cli_fallback: local
```

Ensure `profiles:` includes at minimum `local` and `remote` entries. If they don't exist, add sensible defaults:

```yaml
profiles:
  local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: qwen3.5:9b
  remote:
    provider: openai_compatible
    base_url: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
    model: llama-3.3-70b
  vision-local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: llava-llama3
```

- [ ] **Step 3: Commit**

```bash
git add config/system/llm.yaml
git commit -m "config(llm): add task routing entries for all migrated components"
```

---

### Task 11: Final Invariant Verification

**Files:** None (verification only)

- [ ] **Step 1: Verify no direct LLM HTTP calls outside ai/augur/lib**

Run: `cd ~/Projects/Augur && grep -rn 'httpx.post.*api/generate\|httpx.post.*chat/completions\|urllib.request.*chat/completions' --include='*.py' | grep -v 'skills/ai/augur/lib/' | grep -v test`
Expected: No results (contextualizer's old `httpx.post` is gone)

- [ ] **Step 2: Verify no anthropic/openai SDK imports for generation**

Run: `cd ~/Projects/Augur && grep -rn 'import anthropic\|from anthropic\|from openai import' --include='*.py' | grep -v test | grep -v 'adapters/' | grep -v '__pycache__'`
Expected: Only adapter files (health checks, not generation) — no results from `run_action_evals.py` or `ollama_client.py`

- [ ] **Step 3: Verify llm_cli.py is fully removed**

Run: `cd ~/Projects/Augur && grep -rn 'from src.lib.llm_cli\|import llm_cli' --include='*.py'`
Expected: No results

- [ ] **Step 4: Run full test suite**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/ skills/rag/augur/tests/ skills/document-extractor/augur/tests/ skills/advisor/augur/tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit verification result as a note (optional)**

No code changes. If all checks pass, the migration is complete.
