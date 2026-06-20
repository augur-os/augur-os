"""
Airplane Mode Toggle MCP Tool Contract Tests.

User Need: Enable/disable airplane mode to control offline behavior.

Run with: uv run pytest tests/packages/augur-mcp/tools/test_airplane_mode.py -v
"""

import asyncio
import json

import pytest
import yaml

from src.mcp.augur_framework.tools.infrastructure.local_backends import (
    GetAirplaneLaunchOverridesInput,
    GetLocalBackendStatusInput,
    ToggleAirplaneModeInput,
    get_airplane_launch_overrides_impl,
    get_local_backend_status_impl,
    toggle_airplane_mode_impl,
)


def test_status_reports_routing_matrix(monkeypatch):
    from src.mcp.augur_framework.tools.infrastructure import local_backends as lb

    out = json.loads(asyncio.run(lb.get_local_backend_status_impl(lb.GetLocalBackendStatusInput())))
    routing = out["routing"]
    # Every activity present with both modes mapped to an engine id.
    assert routing["ocr"]["offline"]["engine"] == "ollama-glm-ocr"
    assert routing["transcript"]["regular"]["engine"] == "gemini-transcribe"
    assert routing["chat"]["offline"]["engine"] == "ollama-llm"
    assert "available" in routing["ocr"]["offline"]


def test_airplane_overrides_have_no_smoke_probe(monkeypatch):
    # The probe functions are deleted; overrides come from build_ollama_launch_spec.
    from src.mcp.augur_framework.tools.infrastructure import local_backends as lb

    assert not hasattr(lb, "_probe_agent_local_turn")
    assert not hasattr(lb, "_run_codex_local_turn_probe")


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create isolated config directory with preferences.yaml."""
    config_dir = tmp_path / "config-data"
    config_dir.mkdir()

    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.local_backends._get_preferences_path",
        lambda: config_dir / "preferences.yaml",
    )

    return config_dir


@pytest.fixture
def mock_connectivity_online(monkeypatch):
    """Mock connectivity check as online."""
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.connectivity.check_connectivity",
        lambda: {
            "online": True,
            "host": "api.anthropic.com",
            "checked_at": "2026-03-28T00:00:00+00:00",
        },
    )


@pytest.fixture
def mock_connectivity_offline(monkeypatch):
    """Mock connectivity check as offline."""
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.connectivity.check_connectivity",
        lambda: {
            "online": False,
            "host": "api.anthropic.com",
            "checked_at": "2026-03-28T00:00:00+00:00",
        },
    )


@pytest.fixture
def prefs_airplane_off(temp_config_dir):
    """Create preferences.yaml with airplane_mode disabled."""
    prefs = {
        "airplane_mode": {
            "enabled": False,
            "forced": False,
            "auto_detect": True,
            "fallback_tools": [],
        },
    }
    prefs_file = temp_config_dir / "preferences.yaml"
    prefs_file.write_text(yaml.dump(prefs))
    return prefs_file


@pytest.fixture
def prefs_airplane_on(temp_config_dir):
    """Create preferences.yaml with airplane_mode enabled."""
    prefs = {
        "airplane_mode": {
            "enabled": True,
            "forced": True,
            "auto_detect": True,
            "fallback_tools": [],
        },
    }
    prefs_file = temp_config_dir / "preferences.yaml"
    prefs_file.write_text(yaml.dump(prefs))
    return prefs_file


@pytest.mark.contract
class TestToggleAirplaneModeContract:
    """
    User Need: Toggle airplane mode on/off for offline operation.

    Acceptance Criteria:
    1. "on" sets enabled=True, forced=True, persists to prefs
    2. "off" sets enabled=False, forced=False, persists to prefs
    3. "toggle" flips enabled, sets forced=enabled, persists
    4. "status" returns current state + connectivity check
    5. Unknown action returns error
    """

    def test_enable_airplane_mode(self, temp_config_dir):
        """Action 'on' enables airplane mode and persists."""
        params = ToggleAirplaneModeInput(action="on")
        result = _run(toggle_airplane_mode_impl(params))

        data = json.loads(result)
        assert data["airplane_mode"]["enabled"] is True
        assert data["airplane_mode"]["forced"] is True

        prefs_file = temp_config_dir / "preferences.yaml"
        assert prefs_file.exists()
        saved = yaml.safe_load(prefs_file.read_text())
        assert saved["airplane_mode"]["enabled"] is True
        assert saved["airplane_mode"]["forced"] is True

    def test_disable_airplane_mode(self, prefs_airplane_on):
        """Action 'off' disables airplane mode and persists."""
        params = ToggleAirplaneModeInput(action="off")
        result = _run(toggle_airplane_mode_impl(params))

        data = json.loads(result)
        assert data["airplane_mode"]["enabled"] is False
        assert data["airplane_mode"]["forced"] is False

        saved = yaml.safe_load(prefs_airplane_on.read_text())
        assert saved["airplane_mode"]["enabled"] is False
        assert saved["airplane_mode"]["forced"] is False

    def test_toggle_from_off_to_on(self, prefs_airplane_off):
        """Action 'toggle' flips from disabled to enabled."""
        params = ToggleAirplaneModeInput(action="toggle")
        result = _run(toggle_airplane_mode_impl(params))

        data = json.loads(result)
        assert data["airplane_mode"]["enabled"] is True
        assert data["airplane_mode"]["forced"] is True

        saved = yaml.safe_load(prefs_airplane_off.read_text())
        assert saved["airplane_mode"]["enabled"] is True

    def test_toggle_from_on_to_off(self, prefs_airplane_on):
        """Action 'toggle' flips from enabled to disabled."""
        params = ToggleAirplaneModeInput(action="toggle")
        result = _run(toggle_airplane_mode_impl(params))

        data = json.loads(result)
        assert data["airplane_mode"]["enabled"] is False
        assert data["airplane_mode"]["forced"] is False

    def test_status_returns_airplane_mode_and_connectivity(self, prefs_airplane_off, mock_connectivity_online):
        """Action 'status' returns airplane_mode state + connectivity info."""
        params = ToggleAirplaneModeInput(action="status")
        result = _run(toggle_airplane_mode_impl(params))

        data = json.loads(result)
        assert "airplane_mode" in data
        assert "connectivity" in data
        assert data["airplane_mode"]["enabled"] is False
        assert data["connectivity"]["online"] is True

    def test_status_offline(self, prefs_airplane_on, mock_connectivity_offline):
        """Status with offline connectivity shows correct state."""
        params = ToggleAirplaneModeInput(action="status")
        result = _run(toggle_airplane_mode_impl(params))

        data = json.loads(result)
        assert data["airplane_mode"]["enabled"] is True
        assert data["connectivity"]["online"] is False

    def test_unknown_action_returns_error(self, temp_config_dir):
        """Unknown action returns an error message."""
        params = ToggleAirplaneModeInput(action="invalid")
        result = _run(toggle_airplane_mode_impl(params))

        data = json.loads(result)
        assert "error" in data
        assert "invalid" in data["error"]

    def test_defaults_when_no_prefs_file(self, temp_config_dir):
        """Toggling without a prefs file uses defaults and creates the file."""
        params = ToggleAirplaneModeInput(action="on")
        result = _run(toggle_airplane_mode_impl(params))

        data = json.loads(result)
        assert data["airplane_mode"]["enabled"] is True
        assert data["airplane_mode"]["auto_detect"] is True

        prefs_file = temp_config_dir / "preferences.yaml"
        assert prefs_file.exists()


class TestToggleAirplaneModeInput:
    """Verify the Pydantic model defaults and validation."""

    def test_default_action_is_toggle(self):
        params = ToggleAirplaneModeInput()
        assert params.action == "toggle"

    def test_accepts_valid_actions(self):
        for action in ("on", "off", "toggle", "status"):
            params = ToggleAirplaneModeInput(action=action)
            assert params.action == action


class TestLocalBackendStatus:
    """Verify local backend status stays lightweight enough for dashboard polling."""

    def test_status_uses_lightweight_extraction_inventory(
        self,
        temp_config_dir,
        monkeypatch,
    ):
        prefs_file = temp_config_dir / "preferences.yaml"
        prefs_file.write_text(yaml.dump({"local_backends": {"ollama": {"model": "llama3.2:3b", "agent": "claude"}}}))

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.local_backends._detect_ollama",
            lambda: {
                "installed": True,
                "version": "0.24.0",
                "binary": "ollama",
                "server_running": True,
                "models": [
                    {
                        "name": "llama3.2:3b",
                        "id": "abc123",
                        "size": "2 GB",
                        "modified": "today",
                    }
                ],
            },
        )

        detect_calls = []

        def fake_detect_extraction_capabilities(**kwargs):
            detect_calls.append(kwargs)
            return {
                "ollama": {"glm_ocr_available": True},
                "openvino": {"devices": ["NPU", "GPU", "CPU"], "live_device": "GPU"},
                "transcription_ready": True,
                "transcription_model": "whisper-large-v3-int8-ov",
                "extraction_prereqs": {},
            }

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.local_backends.detect_extraction_capabilities",
            fake_detect_extraction_capabilities,
        )
        from src.lib.routing import engines

        monkeypatch.setattr(
            engines,
            "_available_memory_bytes",
            lambda: 16 * 1024**3,
            raising=False,
        )

        result = _run(get_local_backend_status_impl(GetLocalBackendStatusInput()))

        data = json.loads(result)
        assert data["ollama"]["ready"] is True
        assert data["extraction"]["ocr_engine_available"] is True
        assert detect_calls == [{"probe_timeout_s": 1, "probe_vision_models": False}]

    def test_status_marks_launch_not_ready_without_memory_headroom(
        self,
        temp_config_dir,
        monkeypatch,
    ):
        prefs_file = temp_config_dir / "preferences.yaml"
        prefs_file.write_text(yaml.dump({"local_backends": {"ollama": {"agent": "claude", "model": "qwen3.5:latest"}}}))

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.local_backends._detect_ollama",
            lambda: {
                "installed": True,
                "version": "0.24.0",
                "binary": "ollama",
                "server_running": True,
                "models": [
                    {
                        "name": "qwen3.5:latest",
                        "id": "qwen",
                        "size": "6.6 GB",
                        "modified": "today",
                    }
                ],
            },
        )
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.local_backends._build_extraction_status",
            lambda: {"transcription_ready": True},
        )
        from src.lib.routing import engines

        monkeypatch.setattr(
            engines,
            "_available_memory_bytes",
            lambda: 5 * 1024**3,
            raising=False,
        )

        result = _run(get_local_backend_status_impl(GetLocalBackendStatusInput()))

        data = json.loads(result)
        assert data["ollama"]["server_ready"] is True
        assert data["ollama"]["ready"] is False
        assert data["ollama"]["launch_ready"] is False
        assert "free memory" in data["ollama"]["launch_setup_hint"]
        assert data["launch_command"] is None
        assert data["routing"]["chat"]["offline"]["available"] is False


class TestAirplaneLaunchOverrides:
    """Verify airplane-mode launch overrides delegate to build_ollama_launch_spec."""

    def test_launch_spec_blocks_model_without_memory_headroom(
        self,
        temp_config_dir,
        monkeypatch,
    ):
        """build_ollama_launch_spec refuses memory-risky local chat launches."""
        from src.lib.routing import engines

        prefs_file = temp_config_dir / "preferences.yaml"
        prefs_file.write_text(yaml.dump({"local_backends": {"ollama": {"agent": "claude", "model": "qwen3.5:latest"}}}))

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.local_backends._detect_ollama",
            lambda: {
                "installed": True,
                "version": "0.24.0",
                "binary": "ollama",
                "server_running": True,
                "models": [
                    {
                        "name": "qwen3.5:latest",
                        "id": "qwen",
                        "size": "6.6 GB",
                        "modified": "today",
                    }
                ],
            },
        )
        monkeypatch.setattr(
            engines,
            "_available_memory_bytes",
            lambda: 5 * 1024**3,
            raising=False,
        )

        spec = engines.build_ollama_launch_spec("claude")

        assert spec.ready is False
        assert spec.model == "qwen3.5:latest"
        assert "free memory" in (spec.setup_hint or "")
        assert spec.launch_argv is None

    def test_status_launch_command_uses_agent_specific_model(
        self,
        temp_config_dir,
        monkeypatch,
    ):
        """get_local_backend_status_impl still reports agent-specific launch_command."""
        prefs_file = temp_config_dir / "preferences.yaml"
        prefs_file.write_text(
            yaml.dump(
                {
                    "local_backends": {
                        "ollama": {
                            "agent": "codex",
                            "model": "llama3.2:3b",
                            "agent_models": {
                                "codex": "augur-codex-qwen2.5-coder:7b-4k",
                            },
                        }
                    }
                }
            )
        )

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.local_backends._detect_ollama",
            lambda: {
                "installed": True,
                "version": "0.24.0",
                "binary": "ollama",
                "server_running": True,
                "models": [
                    {
                        "name": "augur-codex-qwen2.5-coder:7b-4k",
                        "id": "codex",
                        "size": "4.7 GB",
                        "modified": "today",
                    }
                ],
            },
        )
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.local_backends._build_extraction_status",
            lambda: {"transcription_ready": True},
        )
        from src.lib.routing import engines

        monkeypatch.setattr(
            engines,
            "_available_memory_bytes",
            lambda: 16 * 1024**3,
            raising=False,
        )

        result = _run(get_local_backend_status_impl(GetLocalBackendStatusInput()))

        data = json.loads(result)
        assert data["launch_command"] == ("ollama launch codex --model augur-codex-qwen2.5-coder:7b-4k")

    def test_codex_uses_agent_specific_model_when_configured(
        self,
        temp_config_dir,
        monkeypatch,
    ):
        """get_airplane_launch_overrides_impl returns correct codex model and argv."""
        from src.lib.routing.engines import ChatLaunchSpec

        monkeypatch.setattr(
            "src.lib.routing.engines.build_ollama_launch_spec",
            lambda agent_id: ChatLaunchSpec(
                engine_id="ollama-llm",
                use_local_ollama=True,
                model="augur-codex-qwen2.5-coder:7b-4k",
                launch_argv=[
                    "ollama",
                    "launch",
                    "codex",
                    "--model",
                    "augur-codex-qwen2.5-coder:7b-4k",
                    "--",
                    "--oss",
                    "--local-provider",
                    "ollama",
                ],
                ready=True,
            ),
        )

        result = _run(get_airplane_launch_overrides_impl(GetAirplaneLaunchOverridesInput(agent_id="codex")))

        data = json.loads(result)
        assert data["ready"] is True
        assert data["model"] == "augur-codex-qwen2.5-coder:7b-4k"
        assert data["launch_argv"] == [
            "ollama",
            "launch",
            "codex",
            "--model",
            "augur-codex-qwen2.5-coder:7b-4k",
            "--",
            "--oss",
            "--local-provider",
            "ollama",
        ]

    def test_codex_default_agent_model_survives_partial_agent_model_overrides(
        self,
        temp_config_dir,
        monkeypatch,
    ):
        """build_ollama_launch_spec default model is used when no codex override."""
        from src.lib.routing.engines import ChatLaunchSpec

        monkeypatch.setattr(
            "src.lib.routing.engines.build_ollama_launch_spec",
            lambda agent_id: ChatLaunchSpec(
                engine_id="ollama-llm",
                use_local_ollama=True,
                model="augur-codex-qwen2.5-coder:7b-4k",
                launch_argv=[
                    "ollama",
                    "launch",
                    "codex",
                    "--model",
                    "augur-codex-qwen2.5-coder:7b-4k",
                    "--",
                    "--oss",
                    "--local-provider",
                    "ollama",
                ],
                ready=True,
            ),
        )

        result = _run(get_airplane_launch_overrides_impl(GetAirplaneLaunchOverridesInput(agent_id="codex")))

        data = json.loads(result)
        assert data["ready"] is True
        assert data["model"] == "augur-codex-qwen2.5-coder:7b-4k"

    def test_not_ready_returns_ollama_not_ready_reason(
        self,
        monkeypatch,
    ):
        """When spec.ready is False, reason is 'ollama_not_ready' with setup_hint."""
        from src.lib.routing.engines import ChatLaunchSpec

        monkeypatch.setattr(
            "src.lib.routing.engines.build_ollama_launch_spec",
            lambda agent_id: ChatLaunchSpec(
                engine_id="ollama-llm",
                use_local_ollama=True,
                ready=False,
                setup_hint="Install Ollama from https://ollama.com/download/windows or run: winget install Ollama.Ollama",
            ),
        )

        result = _run(get_airplane_launch_overrides_impl(GetAirplaneLaunchOverridesInput(agent_id="claude")))

        data = json.loads(result)
        assert data["ready"] is False
        assert data["reason"] == "ollama_not_ready"
        assert "setup_hint" in data

    def test_responsive_configured_model_allows_agent_launch(
        self,
        temp_config_dir,
        monkeypatch,
    ):
        """Ready spec produces ready=True with integration_id, model, launch_argv."""
        from src.lib.routing.engines import ChatLaunchSpec

        monkeypatch.setattr(
            "src.lib.routing.engines.build_ollama_launch_spec",
            lambda agent_id: ChatLaunchSpec(
                engine_id="ollama-llm",
                use_local_ollama=True,
                model="llama3.2:3b",
                launch_argv=["ollama", "launch", "claude", "--model", "llama3.2:3b", "--"],
                ready=True,
            ),
        )

        result = _run(get_airplane_launch_overrides_impl(GetAirplaneLaunchOverridesInput(agent_id="claude")))

        data = json.loads(result)
        assert data["ready"] is True
        assert data["model"] == "llama3.2:3b"
        assert data["launch_argv"] == [
            "ollama",
            "launch",
            "claude",
            "--model",
            "llama3.2:3b",
            "--",
        ]
        assert data["integration_id"] == "claude"
