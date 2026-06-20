import json
from types import SimpleNamespace

from src.lib.routing import engines, resolver

REQS = [{"type": "ocr", "request_id": "0", "image_b64": "QQ==", "prompt": "p"}]


def test_ollama_glm_ocr_returns_results(monkeypatch):
    monkeypatch.setattr(engines, "_run_ollama_ocr", lambda b64, prompt: "HELLO")
    eng = engines.OCR_ENGINES["ollama-glm-ocr"]
    out = eng.run(REQS)
    assert out.success is True
    assert out.results == {"0": "HELLO"}
    assert out.engine_id == "ollama-glm-ocr"


def test_ollama_glm_ocr_empty_text_is_failure(monkeypatch):
    monkeypatch.setattr(engines, "_run_ollama_ocr", lambda b64, prompt: "")
    out = engines.OCR_ENGINES["ollama-glm-ocr"].run(REQS)
    assert out.success is False
    assert out.error


def test_ollama_glm_ocr_caps_context_for_memory_safety(monkeypatch):
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"response": "OCR text"}'

    def fake_urlopen(req, *, timeout):
        captured["timeout"] = timeout
        captured["payload"] = json.loads(req.data.decode())
        return Response()

    monkeypatch.setattr(
        engines,
        "get_local_ocr_settings",
        lambda: SimpleNamespace(
            model="glm-ocr",
            generate_url="http://localhost:11434/api/generate",
            timeout_s=7,
        ),
    )
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert engines._run_ollama_ocr("QQ==", "read this") == "OCR text"

    payload = captured["payload"]
    assert payload["options"]["num_ctx"] == 4096
    assert payload["options"]["num_predict"] == 1024
    assert payload["keep_alive"] == "0"
    assert captured["timeout"] == 7


def test_agent_vision_handoff_in_client_context(monkeypatch):
    monkeypatch.setattr(engines, "_is_ai_client_context", lambda: True)
    out = engines.OCR_ENGINES["agent-vision"].run(REQS)
    assert out.needs_handoff is True
    assert out.handoff_requests == REQS
    assert out.engine_id == "agent-vision"


def test_agent_vision_passive_agent_when_not_in_client(monkeypatch):
    from src.lib.extraction.cloud_vision import CloudVisionResult

    monkeypatch.setattr(engines, "_is_ai_client_context", lambda: False)
    monkeypatch.setattr(
        engines,
        "_run_cloud_vision_ocr",
        lambda reqs, reason: CloudVisionResult(True, {"0": "CLOUD"}, "passive-agent:claude", "claude"),
    )
    out = engines.OCR_ENGINES["agent-vision"].run(REQS)
    assert out.success is True
    assert out.results == {"0": "CLOUD"}


def test_run_ocr_uses_offline_engine_when_mode_offline(monkeypatch):
    monkeypatch.setattr(engines, "_run_ollama_ocr", lambda b64, prompt: "OFFLINE")
    out = resolver.run_ocr(REQS, mode="offline", os_name="win32")
    assert out.success is True
    assert out.engine_id == "ollama-glm-ocr"
    assert out.results == {"0": "OFFLINE"}
