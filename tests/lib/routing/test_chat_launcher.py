from src.lib.routing import engines, resolver


def test_regular_chat_uses_active_client():
    spec = resolver.resolve_chat("claude", mode="regular")
    assert spec.engine_id == "agent-chat"
    assert spec.use_local_ollama is False
    assert spec.launch_argv is None


def test_offline_chat_builds_ollama_launch(monkeypatch):
    monkeypatch.setattr(
        engines,
        "build_ollama_launch_spec",
        lambda agent_id: engines.ChatLaunchSpec(
            engine_id="ollama-llm",
            use_local_ollama=True,
            launch_argv=["ollama", "launch", "claude", "--model", "m", "--"],
            model="m",
            ready=True,
        ),
    )
    spec = resolver.resolve_chat("claude", mode="offline")
    assert spec.engine_id == "ollama-llm"
    assert spec.use_local_ollama is True
    assert spec.launch_argv[:2] == ["ollama", "launch"]


def test_offline_chat_not_ready_when_ollama_missing(monkeypatch):
    monkeypatch.setattr(
        engines,
        "build_ollama_launch_spec",
        lambda agent_id: engines.ChatLaunchSpec(
            engine_id="ollama-llm",
            use_local_ollama=True,
            ready=False,
            setup_hint="Install Ollama from https://ollama.com/download/windows",
        ),
    )
    spec = resolver.resolve_chat("claude", mode="offline")
    assert spec.ready is False
    assert spec.setup_hint
