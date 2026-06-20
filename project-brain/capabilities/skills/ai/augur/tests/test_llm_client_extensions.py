"""Tests for generate_with_vision and generate_with_tools on LLMClient and OpenAICompatibleClient."""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
AI_BRIDGE_AUGUR = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(AI_BRIDGE_AUGUR) not in sys.path:
    sys.path.insert(0, str(AI_BRIDGE_AUGUR))

from src.lib.ai.client import (  # noqa: E402
    LLMClient,
    CommandLLMClient,
    OpenAICompatibleClient,
    create_llm_client,
)
from src.lib.ai.config import LLMProfile  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_openai_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url="https://api.example.com/v1",
        api_key="test-key",
        default_model="gpt-4o",
    )


def _mock_urlopen_response(content: str) -> MagicMock:
    """Return a context-manager mock whose .read() returns the given JSON string."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"choices": [{"message": {"content": content, "tool_calls": None}}]}
    ).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _mock_tool_response(content: str | None, tool_calls: list[dict]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": content,
                        "tool_calls": tool_calls,
                    }
                }
            ]
        }
    ).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Stored provider credentials
# ---------------------------------------------------------------------------


class TestStoredProviderCredentials:
    def _profile(self) -> LLMProfile:
        return LLMProfile(
            name="vision-cloud",
            provider="openai_compatible",
            base_url="https://glama.ai/api/gateway/openai/v1",
            api_key_env="GLAMA_API_KEY",
            model="anthropic/claude-sonnet-4",
        )

    def test_create_llm_client_uses_stored_oauth_key_when_env_missing(
        self, tmp_path, monkeypatch
    ):
        keys_path = tmp_path / "config" / "integrations" / ".oauth-keys.json"
        keys_path.parent.mkdir(parents=True)
        keys_path.write_text(json.dumps({"glama": "stored-glama-key"}), encoding="utf-8")

        monkeypatch.setattr("src.config.paths.get_project_root", lambda: tmp_path)
        monkeypatch.delenv("AUGUR_LLM_API_KEY", raising=False)
        monkeypatch.delenv("GLAMA_API_KEY", raising=False)

        client = create_llm_client(self._profile())

        assert isinstance(client, OpenAICompatibleClient)
        assert client.api_key == "stored-glama-key"

    def test_create_llm_client_prefers_env_key_over_stored_oauth_key(
        self, tmp_path, monkeypatch
    ):
        keys_path = tmp_path / "config" / "integrations" / ".oauth-keys.json"
        keys_path.parent.mkdir(parents=True)
        keys_path.write_text(json.dumps({"glama": "stored-glama-key"}), encoding="utf-8")

        monkeypatch.setattr("src.config.paths.get_project_root", lambda: tmp_path)
        monkeypatch.delenv("AUGUR_LLM_API_KEY", raising=False)
        monkeypatch.setenv("GLAMA_API_KEY", "env-glama-key")

        client = create_llm_client(self._profile())

        assert isinstance(client, OpenAICompatibleClient)
        assert client.api_key == "env-glama-key"

    def test_create_llm_client_fails_fast_when_configured_key_is_missing(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr("src.config.paths.get_project_root", lambda: tmp_path)
        monkeypatch.delenv("AUGUR_LLM_API_KEY", raising=False)
        monkeypatch.delenv("GLAMA_API_KEY", raising=False)

        try:
            create_llm_client(self._profile())
            assert False, "Expected missing configured API key to fail fast"
        except RuntimeError as exc:
            message = str(exc)

        assert "GLAMA_API_KEY" in message
        assert ".oauth-keys.json" in message


class TestOpenAICompatibleClientHeaders:
    def test_headers_include_user_agent_for_cloud_gateways(self):
        client = _make_openai_client()
        headers = {key.lower(): value for key, value in client._headers().items()}

        assert headers["accept"] == "application/json"
        assert headers["content-type"] == "application/json"
        assert headers["user-agent"].startswith("Augur/")
        assert headers["authorization"] == "Bearer test-key"


# ---------------------------------------------------------------------------
# Task 1 — Base class raises NotImplementedError
# ---------------------------------------------------------------------------


class TestBaseClassNotImplemented:
    def test_llmclient_generate_with_vision_raises(self):
        client = LLMClient()
        try:
            client.generate_with_vision(prompt="describe", images=[b"bytes"])
            assert False, "Expected NotImplementedError"
        except NotImplementedError as e:
            assert "vision" in str(e).lower()

    def test_llmclient_generate_with_tools_raises(self):
        client = LLMClient()
        try:
            client.generate_with_tools(prompt="use tool", tools=[{"name": "t"}])
            assert False, "Expected NotImplementedError"
        except NotImplementedError as e:
            assert "tool" in str(e).lower()

    def test_command_client_generate_with_vision_raises(self):
        client = CommandLLMClient(command="echo hi")
        try:
            client.generate_with_vision(prompt="describe", images=[b"bytes"])
            assert False, "Expected NotImplementedError"
        except NotImplementedError as e:
            assert "vision" in str(e).lower()

    def test_command_client_generate_with_tools_raises(self):
        client = CommandLLMClient(command="echo hi")
        try:
            client.generate_with_tools(prompt="use tool", tools=[{"name": "t"}])
            assert False, "Expected NotImplementedError"
        except NotImplementedError as e:
            assert "tool" in str(e).lower()


# ---------------------------------------------------------------------------
# Task 2 — OpenAICompatibleClient.generate_with_vision
# ---------------------------------------------------------------------------


class TestOpenAICompatibleClientVision:
    def test_with_bytes_image_base64_encoded(self):
        client = _make_openai_client()
        image_bytes = b"\x89PNG\r\n\x1a\n"  # PNG header bytes

        captured_payload: dict = {}

        def fake_urlopen(req, timeout=None):
            captured_payload.update(json.loads(req.data.decode("utf-8")))
            return _mock_urlopen_response("I see a PNG")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.generate_with_vision(prompt="describe this", images=[image_bytes])

        assert result == "I see a PNG"
        messages = captured_payload["messages"]
        user_msg = next(m for m in messages if m["role"] == "user")
        content = user_msg["content"]
        # Should be a list with text + image_url
        assert isinstance(content, list)
        text_block = next(b for b in content if b.get("type") == "text")
        assert text_block["text"] == "describe this"
        image_block = next(b for b in content if b.get("type") == "image_url")
        expected_b64 = base64.b64encode(image_bytes).decode("utf-8")
        assert image_block["image_url"]["url"] == f"data:image/png;base64,{expected_b64}"

    def test_with_url_string_image(self):
        client = _make_openai_client()
        url = "https://example.com/image.png"

        captured_payload: dict = {}

        def fake_urlopen(req, timeout=None):
            captured_payload.update(json.loads(req.data.decode("utf-8")))
            return _mock_urlopen_response("I see an image")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.generate_with_vision(prompt="what is this?", images=[url])

        assert result == "I see an image"
        messages = captured_payload["messages"]
        user_msg = next(m for m in messages if m["role"] == "user")
        content = user_msg["content"]
        image_block = next(b for b in content if b.get("type") == "image_url")
        assert image_block["image_url"]["url"] == url

    def test_with_system_prompt(self):
        client = _make_openai_client()

        captured_payload: dict = {}

        def fake_urlopen(req, timeout=None):
            captured_payload.update(json.loads(req.data.decode("utf-8")))
            return _mock_urlopen_response("answered")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client.generate_with_vision(
                prompt="describe",
                images=["https://example.com/img.png"],
                system="You are a visual analyst.",
            )

        messages = captured_payload["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a visual analyst."

    def test_with_multiple_images(self):
        client = _make_openai_client()
        images = [b"\x89PNG", "https://example.com/b.png"]

        captured_payload: dict = {}

        def fake_urlopen(req, timeout=None):
            captured_payload.update(json.loads(req.data.decode("utf-8")))
            return _mock_urlopen_response("two images")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.generate_with_vision(prompt="compare", images=images)

        assert result == "two images"
        messages = captured_payload["messages"]
        user_msg = next(m for m in messages if m["role"] == "user")
        content = user_msg["content"]
        image_blocks = [b for b in content if b.get("type") == "image_url"]
        assert len(image_blocks) == 2
        # First is bytes → base64
        expected_b64 = base64.b64encode(b"\x89PNG").decode("utf-8")
        assert image_blocks[0]["image_url"]["url"] == f"data:image/png;base64,{expected_b64}"
        # Second is URL passthrough
        assert image_blocks[1]["image_url"]["url"] == "https://example.com/b.png"


# ---------------------------------------------------------------------------
# Task 3 — OpenAICompatibleClient.generate_with_tools
# ---------------------------------------------------------------------------


class TestOpenAICompatibleClientTools:
    def _sample_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather",
                    "parameters": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                    },
                },
            }
        ]

    def test_returns_tool_calls(self):
        client = _make_openai_client()
        raw_tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"location": "NYC"}'},
            }
        ]
        with patch("urllib.request.urlopen", return_value=_mock_tool_response(None, raw_tool_calls)):
            result = client.generate_with_tools(
                prompt="What is the weather?", tools=self._sample_tools()
            )

        assert result["content"] is None
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "get_weather"
        assert result["tool_calls"][0]["arguments"] == {"location": "NYC"}

    def test_returns_both_content_and_tool_calls(self):
        client = _make_openai_client()
        raw_tool_calls = [
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"location": "LA"}'},
            }
        ]
        with patch("urllib.request.urlopen", return_value=_mock_tool_response("Here is the weather:", raw_tool_calls)):
            result = client.generate_with_tools(
                prompt="Give me weather for LA", tools=self._sample_tools()
            )

        assert result["content"] == "Here is the weather:"
        assert result["tool_calls"][0]["name"] == "get_weather"

    def test_tools_key_in_request_payload(self):
        client = _make_openai_client()
        tools = self._sample_tools()

        captured_payload: dict = {}

        def fake_urlopen(req, timeout=None):
            captured_payload.update(json.loads(req.data.decode("utf-8")))
            return _mock_tool_response(None, [])

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client.generate_with_tools(prompt="use tools", tools=tools)

        assert "tools" in captured_payload
        assert captured_payload["tools"] == tools

    def test_handles_response_with_no_tool_calls(self):
        client = _make_openai_client()
        with patch("urllib.request.urlopen", return_value=_mock_tool_response("Just text, no tools.", None)):
            result = client.generate_with_tools(
                prompt="Hello", tools=self._sample_tools()
            )

        assert result["content"] == "Just text, no tools."
        assert result["tool_calls"] == []

    def test_system_prompt_included_in_payload(self):
        client = _make_openai_client()
        captured_payload: dict = {}

        def fake_urlopen(req, timeout=None):
            captured_payload.update(json.loads(req.data.decode("utf-8")))
            return _mock_tool_response(None, [])

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client.generate_with_tools(
                prompt="use tools",
                tools=self._sample_tools(),
                system="You are a helpful assistant.",
            )

        messages = captured_payload["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."
