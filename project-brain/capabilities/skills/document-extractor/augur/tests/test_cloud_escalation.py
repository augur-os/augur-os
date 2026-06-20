from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_run_cloud_vision_ocr_uses_passive_agent_job(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import cloud_vision

    calls: list[dict] = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        result_path = Path(kwargs["env"]["AUGUR_PASSIVE_AGENT_RESULT"])
        result_path.write_text(
            json.dumps(
                {
                    "success": True,
                    "results": {
                        "0": "Cloud OCR text: Invoice total 1842.25 due 2026-05-20."
                    },
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="done", stderr="")

    monkeypatch.setattr(cloud_vision, "get_runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(
        cloud_vision,
        "_resolve_passive_agent_config",
        lambda: cloud_vision.PassiveAgentConfig(cli_id="claude"),
    )
    monkeypatch.setattr(cloud_vision, "_resolve_cli_path", lambda _cli: "claude.exe")
    monkeypatch.setattr(cloud_vision.subprocess, "run", fake_run)

    result = cloud_vision.run_cloud_vision_ocr(
        [
            {
                "request_id": "0",
                "image_b64": "ZmFrZQ==",
                "prompt": "Extract all visible text.",
            }
        ],
        reason="local OCR and local vision did not produce usable text",
    )

    assert result.success is True
    assert result.provider == "passive-agent:claude"
    assert result.model == "claude"
    assert "Invoice total" in result.results["0"]
    assert calls
    assert calls[0]["cmd"][:4] == ["claude.exe", "--print", "--output-format", "text"]
    assert calls[0]["kwargs"]["env"]["AUGUR_AGENT_SESSION"] == "1"
    assert Path(calls[0]["kwargs"]["env"]["AUGUR_PASSIVE_AGENT_REQUEST"]).exists()


def test_passive_agent_prefers_configured_default_client(monkeypatch) -> None:
    from types import SimpleNamespace

    from src.lib.extraction import cloud_vision
    from src.lib import agent_cli_config

    monkeypatch.setattr(
        agent_cli_config,
        "_resolve_client_routing",
        lambda _action_id: SimpleNamespace(
            client_id="codex",
            client_type="ide",
            source="global",
        ),
    )
    monkeypatch.setattr(
        agent_cli_config,
        "load_cli_agents",
        lambda: (
            Path("cli_agents.yaml"),
            {
                "claude": {"print_cmd": ["claude", "--print"]},
                "codex": {"print_cmd": ["codex", "exec", "--json"]},
            },
        ),
    )

    agent = cloud_vision._resolve_passive_agent_config()

    assert agent.cli_id == "codex"
    assert agent.command == ["codex", "exec", "--json"]
    assert agent.source == "global"
    assert agent.error is None


def test_passive_agent_implicit_default_uses_cli_registry_before_llm_config(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from src.lib.extraction import cloud_vision
    from src.lib import agent_cli_config

    monkeypatch.setattr(
        agent_cli_config,
        "_resolve_client_routing",
        lambda _action_id: SimpleNamespace(
            client_id="",
            client_type="ide",
            source="implicit",
        ),
    )
    monkeypatch.setattr(
        agent_cli_config,
        "load_cli_agents",
        lambda: (
            Path("cli_agents.yaml"),
            {"gemini": {"print_cmd": ["gemini", "--prompt"]}},
        ),
    )

    agent = cloud_vision._resolve_passive_agent_config()

    assert agent.cli_id == "gemini"
    assert agent.command == ["gemini", "--prompt"]
    assert agent.source == "cli_agents"


def test_agent_command_uses_configured_print_command(tmp_path: Path) -> None:
    from src.lib.extraction import cloud_vision

    command = cloud_vision._agent_command(
        "C:\\Tools\\codex.exe",
        "codex",
        "OCR prompt",
        tmp_path,
        configured_command=["codex", "exec", "--json"],
    )

    assert command == ["C:\\Tools\\codex.exe", "exec", "--json", "OCR prompt"]


def test_claude_stream_json_print_command_adds_verbose(tmp_path: Path) -> None:
    from src.lib.extraction import cloud_vision

    command = cloud_vision._agent_command(
        "C:\\Tools\\claude.exe",
        "claude",
        "OCR prompt",
        tmp_path,
        configured_command=["claude", "-p", "--output-format", "stream-json"],
    )

    assert "--verbose" in command


def test_extract_uses_passive_agent_when_cloud_allowed(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import extractor
    from src.lib.routing.engines import OcrResult

    image = tmp_path / "scan.png"
    image.write_bytes(b"not-a-real-image-but-request-builder-reads-bytes")

    monkeypatch.setattr(extractor, "_get_markitdown", lambda: (_ for _ in ()).throw(RuntimeError("no local text")))
    # Routing (agent-vision) returns cloud OCR text
    monkeypatch.setattr(
        extractor, "_routing_run_ocr",
        lambda *_args, **_kwargs: OcrResult(
            success=True,
            results={"0": "Cloud OCR text: Invoice total 1842.25 due 2026-05-20."},
            engine_id="agent-vision",
        ),
    )

    result = extractor.extract(str(image), max_tier=1, allow_cloud=True)

    assert result.success is True
    assert result.ocr_applied is True
    assert result.hardware_backend == "agent-vision"
    assert result.cloud_used is True
    assert "Invoice total" in result.markdown


def test_cloud_vision_rejects_no_text_answers(monkeypatch) -> None:
    from src.lib.extraction import cloud_vision

    monkeypatch.setattr(
        cloud_vision,
        "_run_passive_agent_job",
        lambda *_args, **_kwargs: cloud_vision.CloudVisionResult(
            success=True,
            results={"0": "The image contains no visible text."},
            provider="passive-agent:claude",
            model="claude",
        ),
    )

    result = cloud_vision.run_cloud_vision_ocr(
        [
            {
                "request_id": "0",
                "image_b64": "ZmFrZQ==",
                "prompt": "Extract all visible text.",
            }
        ],
        reason="local OCR and local vision did not produce usable text",
    )

    assert result.success is False
    assert result.provider == "passive-agent:claude"
    assert result.model == "claude"
    assert result.error == "cloud vision returned unusable OCR text for request 0"


def test_extract_blocks_cloud_when_not_allowed(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import extractor
    from src.lib.routing.engines import OcrResult

    image = tmp_path / "scan.png"
    image.write_bytes(b"not-a-real-image-but-request-builder-reads-bytes")

    captured_modes: list = []

    def _fake_run_ocr(_requests, *, mode=None):
        captured_modes.append(mode)
        return OcrResult(success=False, results={}, engine_id="ollama-glm-ocr", error="OCR unavailable")

    monkeypatch.setattr(extractor, "_get_markitdown", lambda: (_ for _ in ()).throw(RuntimeError("no local text")))
    monkeypatch.setattr(extractor, "_routing_run_ocr", _fake_run_ocr)

    result = extractor.extract(str(image), max_tier=1, allow_cloud=False)

    assert captured_modes == ["offline"], f"expected mode='offline' to block cloud, got {captured_modes}"
    assert result.cloud_used is False
    assert result.needs_llm is False
    assert result.success is False


def test_extract_blocks_ai_client_handoff_when_cloud_not_allowed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.extraction import extractor
    from src.lib.routing.engines import OcrResult

    image = tmp_path / "scan.png"
    image.write_bytes(b"scan")

    monkeypatch.setattr(extractor, "_get_markitdown", lambda: (_ for _ in ()).throw(RuntimeError("no local text")))
    # Routing returns OCR failure (not a handoff); allow_cloud=False is passed but routing decides
    monkeypatch.setattr(
        extractor, "_routing_run_ocr",
        lambda *_args, **_kwargs: OcrResult(success=False, results={}, engine_id="ollama-glm-ocr", error="OCR unavailable"),
    )

    result = extractor.extract(str(image), max_tier=1, allow_cloud=False)

    assert result.cloud_used is False
    assert result.needs_llm is False
    assert result.llm_requests is None


def test_extract_hands_off_to_ai_client_before_passive_agent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.extraction import extractor
    from src.lib.routing.engines import OcrResult

    image = tmp_path / "scan.png"
    image.write_bytes(b"scan")

    fake_reqs = [{"type": "ocr", "image_b64": "ZmFrZQ==", "prompt": "extract"}]
    monkeypatch.setattr(extractor, "_get_markitdown", lambda: (_ for _ in ()).throw(RuntimeError("no local text")))
    # Routing (agent-vision) returns a handoff so extractor returns needs_llm=True
    monkeypatch.setattr(
        extractor, "_routing_run_ocr",
        lambda *_args, **_kwargs: OcrResult(
            success=True, results={}, engine_id="agent-vision",
            needs_handoff=True, handoff_requests=fake_reqs,
        ),
    )

    result = extractor.extract(str(image), max_tier=1, allow_cloud=True)

    assert result.cloud_used is False
    assert result.needs_llm is True
    assert result.llm_requests
