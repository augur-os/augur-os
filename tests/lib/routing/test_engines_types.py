from src.lib.routing.engines import ChatLaunchSpec, EngineAvailability, OcrResult


def test_ocr_result_defaults():
    r = OcrResult(success=True, results={"0": "hi"}, engine_id="ollama-glm-ocr")
    assert r.error is None
    assert r.needs_handoff is False
    assert r.handoff_requests is None


def test_engine_availability_defaults():
    a = EngineAvailability(available=False, engine_id="gemini-transcribe")
    assert a.detail == ""
    assert a.setup_hint is None


def test_chat_launch_spec_defaults():
    s = ChatLaunchSpec(engine_id="ollama-llm", use_local_ollama=True)
    assert s.ready is True
    assert s.launch_argv is None
    assert s.model is None
