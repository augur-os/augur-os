"""Tests for document-extractor MCP tool implementation functions."""
import importlib
import importlib.util
import json
import sys
from pathlib import Path


_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_mcp_pkg_dir = Path(__file__).resolve().parents[2] / "scripts" / "mcp"
_mcp_pkg_name = "document_extractor_test_mcp"
if _mcp_pkg_name not in sys.modules:
    _pkg_spec = importlib.util.spec_from_file_location(
        _mcp_pkg_name,
        _mcp_pkg_dir / "__init__.py",
        submodule_search_locations=[str(_mcp_pkg_dir)],
    )
    assert _pkg_spec is not None and _pkg_spec.loader is not None
    _pkg_module = importlib.util.module_from_spec(_pkg_spec)
    sys.modules[_mcp_pkg_name] = _pkg_module
    _pkg_spec.loader.exec_module(_pkg_module)

_tools_extract = importlib.import_module(f"{_mcp_pkg_name}.tools_extract")
extract_document_impl = _tools_extract.extract_document_impl
submit_result_impl = _tools_extract.submit_result_impl
extract_batch_impl = _tools_extract.extract_batch_impl
get_extraction_status_impl = _tools_extract.get_extraction_status_impl


# ---------------------------------------------------------------------------
# TestExtractDocument
# ---------------------------------------------------------------------------

class TestExtractDocument:
    def test_extract_text_file(self, tmp_path: Path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello, world!")
        result = extract_document_impl(str(f))
        assert result["success"] is True
        assert "Hello, world!" in result["markdown"]
        assert result["format"] == "txt"

    def test_extract_nonexistent(self):
        result = extract_document_impl("/tmp/nonexistent_abc_xyz_123.txt")
        assert result["success"] is False
        assert "error" in result

    def test_extract_csv(self, tmp_path: Path):
        f = tmp_path / "data.csv"
        f.write_text("name,age\nAlice,30\nBob,25\n")
        result = extract_document_impl(str(f))
        assert result["success"] is True
        assert result["format"] == "csv"
        assert "Alice" in result["markdown"]

    def test_includes_metadata(self, tmp_path: Path):
        f = tmp_path / "meta.txt"
        f.write_text("metadata test content")
        result = extract_document_impl(str(f), include_metadata=True)
        assert result["success"] is True
        assert "size_bytes" in result
        assert result["size_bytes"] > 0
        assert "extraction_time" in result
        assert result["extraction_time"] >= 0

    def test_excludes_metadata_when_disabled(self, tmp_path: Path):
        f = tmp_path / "nometa.txt"
        f.write_text("no metadata test")
        result = extract_document_impl(str(f), include_metadata=False)
        assert result["success"] is True
        assert "size_bytes" not in result
        assert "extraction_time" not in result

    def test_extract_document_passes_cloud_policy(self, monkeypatch, tmp_path: Path):
        f = tmp_path / "scan.png"
        f.write_bytes(b"scan")
        calls: dict[str, object] = {}

        def fake_extract(path, max_tier=1, **kwargs):
            calls["path"] = path
            calls["max_tier"] = max_tier
            calls.update(kwargs)
            return _tools_extract.ExtractionResult(
                success=True,
                markdown="",
                title="scan",
                tier_used=0,
                format="png",
                size_bytes=4,
                extraction_time=0.1,
                ocr_applied=False,
            )

        monkeypatch.setattr(
            _tools_extract,
            "get_extraction_policy",
            lambda: {
                "airplane_mode_enabled": True,
                "cloud_escalation_allowed": False,
            },
            raising=False,
        )
        monkeypatch.setattr(_tools_extract, "extract", fake_extract)

        result = extract_document_impl(str(f))

        assert result["success"] is True
        assert calls["allow_cloud"] is False


# ---------------------------------------------------------------------------
# TestSubmitResult
# ---------------------------------------------------------------------------

class TestSubmitResult:
    def test_submit_returns_merged(self, tmp_path: Path):
        # First extract a file so there's context
        f = tmp_path / "img.txt"
        f.write_text("[Image: page requires OCR]")
        result = submit_result_impl(
            request_id="req-001",
            result_text="Extracted OCR text here",
            source_path=str(f),
        )
        assert result["success"] is True
        assert "merged_markdown" in result


# ---------------------------------------------------------------------------
# TestExtractBatch
# ---------------------------------------------------------------------------

class TestExtractBatch:
    def test_batch_multiple(self, tmp_path: Path):
        f1 = tmp_path / "one.txt"
        f1.write_text("File one content.")
        f2 = tmp_path / "two.txt"
        f2.write_text("File two content.")
        paths = json.dumps([str(f1), str(f2)])
        result = extract_batch_impl(paths)
        assert result["success"] is True
        assert result["summary"]["total"] == 2
        assert result["summary"]["completed"] == 2
        assert len(result["results"]) == 2

    def test_batch_with_missing(self, tmp_path: Path):
        f1 = tmp_path / "real.txt"
        f1.write_text("Real file content.")
        paths = json.dumps([str(f1), "/tmp/missing_batch_xyz_999.txt"])
        result = extract_batch_impl(paths)
        # Partial success — at least one completed
        assert result["summary"]["total"] == 2
        assert result["summary"]["completed"] >= 1
        assert result["summary"]["failed"] >= 1


# ---------------------------------------------------------------------------
# TestGetExtractionStatus
# ---------------------------------------------------------------------------

class TestGetExtractionStatus:
    def test_returns_format_info(self):
        result = get_extraction_status_impl()
        assert "formats" in result
        formats = result["formats"]
        # Should report on key document formats
        assert "pdf_text" in formats
        assert "docx" in formats
        assert "csv" in formats
        assert "text" in formats

    def test_markitdown_version_present(self):
        result = get_extraction_status_impl()
        assert "markitdown_version" in result
        assert result["markitdown_version"] is not None

    def test_reports_dependency_and_capability_status(self):
        result = get_extraction_status_impl()

        assert "dependencies" in result
        assert "capabilities" in result
        assert "pymupdf" in result["dependencies"]
        assert "markitdown_ocr" not in result["dependencies"]
        assert "baseline_document_stack_ready" in result["capabilities"]
        assert "text_pdf_extraction_ready" in result["capabilities"]
        assert "ocr_enhancement_ready" not in result["capabilities"]

    def test_reports_ai_pc_policy_fields(self):
        result = get_extraction_status_impl()

        assert "ai_pc" in result
        assert "airplane_mode" in result
        assert "cloud_escalation_allowed" in result["airplane_mode"]
        assert "local_agent_ready" in result
        assert "transcription_ready" in result

    def test_surfaces_glm_ocr_and_prereqs(self, monkeypatch):
        fake_inventory = {
            "platform": "Windows",
            "ollama": {
                "installed": True,
                "binary": "C:/Users/test/AppData/Local/Programs/Ollama/ollama.exe",
                "models": ["glm-ocr:latest", "qwen3:8b"],
                "vision_models": [],
                "glm_ocr_available": True,
            },
            "openvino_ready": True,
            "openvino_genai_ready": True,
            "openvino": {"devices": ["NPU", "GPU", "CPU"], "live_device": "NPU"},
            "transcription_ready": True,
            "transcription_model": "/cache/whisper-large-v3-int8-ov",
            "local_agent_ready": True,
            "extraction_prereqs": {
                "transformers_version": "4.52.4",
                "transformers_ok": True,
                "npu_driver_version": "32.0.100.3104",
                "npu_driver_ok": True,
            },
            "packages": {},
            "commands": {},
            "policy": {
                "airplane_mode_enabled": False,
                "cloud_escalation_allowed": True,
                "local_agent_escalation_allowed": True,
            },
        }
        monkeypatch.setattr(_tools_extract, "detect_extraction_capabilities", lambda **_kwargs: fake_inventory)
        monkeypatch.setattr(_tools_extract.sys, "platform", "win32")

        payload = get_extraction_status_impl()

        assert payload["ocr_engine"] == "glm-ocr"
        assert payload["ocr_engine_available"] is True
        assert payload["os_default_chain"]["ocr"] == ["ollama-glm-ocr", "passive-agent-vision"]
        assert payload["os_default_chain"]["transcription"] == ["openvino-whisper"]
        assert payload["prereqs"]["transformers_ok"] is True
        assert payload["openvino"]["live_device"] == "NPU"

    def test_audio_format_requires_transcription_readiness(self, monkeypatch):
        fake_inventory = {
            "platform": "Windows",
            "ollama": {
                "installed": True,
                "binary": "C:/Users/test/AppData/Local/Programs/Ollama/ollama.exe",
                "models": ["glm-ocr:latest"],
                "vision_models": [],
                "glm_ocr_available": True,
            },
            "openvino_ready": False,
            "openvino_genai_ready": False,
            "openvino": {"devices": ["NPU", "GPU", "CPU"], "live_device": None},
            "transcription_ready": False,
            "transcription_model": None,
            "local_agent_ready": True,
            "extraction_prereqs": {},
            "packages": {},
            "commands": {},
            "policy": {
                "airplane_mode_enabled": False,
                "cloud_escalation_allowed": True,
                "local_agent_escalation_allowed": True,
            },
        }

        def fake_package_version(name: str) -> str | None:
            return "1.0.0" if name in {"markitdown", "pymupdf"} else None

        monkeypatch.setattr(_tools_extract, "detect_extraction_capabilities", lambda **_kwargs: fake_inventory)
        monkeypatch.setattr(_tools_extract, "package_version", fake_package_version)

        payload = get_extraction_status_impl()

        assert payload["formats"]["audio"] is False
