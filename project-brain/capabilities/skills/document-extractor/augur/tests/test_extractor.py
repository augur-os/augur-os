"""Tests for the document-extractor core extractor module."""
import textwrap
import types
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from src.lib.extraction import extractor
from src.lib.extraction import ExtractionResult, extract, detect_available_tier, merge_llm_results
from src.lib.routing.engines import OcrResult  # D2: routing-backed OCR seam


# ---------------------------------------------------------------------------
# TestExtractionResult
# ---------------------------------------------------------------------------

class TestExtractionResult:
    def test_create_success_result(self):
        result = ExtractionResult(
            success=True,
            markdown="# Hello",
            title="Hello",
            tier_used=0,
            format="md",
            size_bytes=100,
            extraction_time=0.5,
            ocr_applied=False,
        )
        assert result.success is True
        assert result.markdown == "# Hello"
        assert result.title == "Hello"
        assert result.tier_used == 0
        assert result.format == "md"
        assert result.size_bytes == 100
        assert result.extraction_time == 0.5
        assert result.ocr_applied is False
        assert result.needs_llm is False
        assert result.llm_requests is None
        assert result.partial_markdown is None
        assert result.error is None

    def test_needs_llm_result(self):
        llm_requests = [{"type": "ocr", "image_b64": "abc123"}]
        result = ExtractionResult(
            success=True,
            markdown="",
            title="photo.png",
            tier_used=1,
            format="png",
            size_bytes=50000,
            extraction_time=0.1,
            ocr_applied=False,
            needs_llm=True,
            llm_requests=llm_requests,
        )
        assert result.needs_llm is True
        assert result.llm_requests == llm_requests
        assert len(result.llm_requests) == 1


# ---------------------------------------------------------------------------
# TestExtractTier0
# ---------------------------------------------------------------------------

class TestExtractTier0:
    def test_extract_plain_text(self, tmp_path: Path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello, world!")
        result = extract(str(f))
        assert result.success is True
        assert "Hello, world!" in result.markdown
        assert result.format == "txt"
        assert result.tier_used == 0

    def test_extract_markdown(self, tmp_path: Path):
        f = tmp_path / "doc.md"
        f.write_text("# Heading\n\nParagraph text.")
        result = extract(str(f))
        assert result.success is True
        assert "Heading" in result.markdown
        assert result.format == "md"

    def test_extract_csv(self, tmp_path: Path):
        f = tmp_path / "data.csv"
        f.write_text("name,age\nAlice,30\nBob,25\n")
        result = extract(str(f))
        assert result.success is True
        assert "Alice" in result.markdown
        assert result.format == "csv"

    def test_extract_html(self, tmp_path: Path):
        f = tmp_path / "page.html"
        f.write_text("<html><body><h1>Title</h1><p>Content</p></body></html>")
        result = extract(str(f))
        assert result.success is True
        assert "Title" in result.markdown
        assert result.format == "html"

    def test_extract_nonexistent_file(self):
        result = extract("/tmp/nonexistent_file_abc123.txt")
        assert result.success is False
        assert result.error is not None

    def test_extract_returns_size_and_time(self, tmp_path: Path):
        f = tmp_path / "sized.txt"
        f.write_text("Some content here for size check.")
        result = extract(str(f))
        assert result.success is True
        assert result.size_bytes > 0
        assert result.extraction_time >= 0

    def test_extract_image_tier0_no_content(self, tmp_path: Path):
        """A fake .png at tier 0 should produce minimal/empty markdown."""
        f = tmp_path / "fake.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        result = extract(str(f), max_tier=0)
        # At tier 0 with no OCR, image extraction yields empty or placeholder
        assert result.success is True
        assert result.tier_used == 0


class TestNeedAndComplexityEscalation:
    def test_scanned_pdf_escalates_to_llm_when_local_extraction_is_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        f = tmp_path / "scan.pdf"
        f.write_bytes(b"%PDF-1.7\n")

        class _Result:
            text_content = ""

        class _MarkItDown:
            def convert(self, _path: str):
                return _Result()

        fake_reqs = [{"type": "ocr", "image_b64": "page-1"}]

        monkeypatch.setattr(extractor, "_get_markitdown", lambda: _MarkItDown())
        monkeypatch.setattr(
            extractor,
            "_build_llm_ocr_requests",
            lambda *_args: ("[Image: page requires OCR]", fake_reqs),
        )
        # Routing returns a handoff (in-session AI client should process)
        monkeypatch.setattr(
            extractor,
            "_routing_run_ocr",
            lambda *_args, **_kwargs: OcrResult(
                success=True, results={}, engine_id="agent-vision",
                needs_handoff=True, handoff_requests=fake_reqs,
            ),
        )

        result = extract(str(f), max_tier=1, allow_cloud=True)

        assert result.success is True
        assert result.tier_used == 1
        assert result.needs_llm is True
        assert result.format == "pdf"
        assert result.partial_markdown == "[Image: page requires OCR]"
        assert result.llm_requests == fake_reqs

    def test_no_try_tesseract_helper(self):
        """The retired Tier 0.5 Tesseract helper is gone."""
        assert not hasattr(extractor, "_try_tesseract")

    def test_pdf_page_images_for_llm_crops_and_bounds_rendered_pages(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        source = tmp_path / "scan.pdf"
        source.write_bytes(b"%PDF-1.7\n")
        rendered = Image.new("RGB", (1400, 1000), "white")
        draw = ImageDraw.Draw(rendered)
        draw.rectangle((900, 700, 1300, 900), fill="black")

        fake_pdf2image = types.SimpleNamespace(
            convert_from_path=lambda *_args, **_kwargs: [rendered],
        )
        monkeypatch.setitem(extractor.sys.modules, "pdf2image", fake_pdf2image)

        [page] = extractor._pdf_page_images_for_llm(source, max_pages=1)
        processed = Image.open(BytesIO(page))

        assert max(processed.size) <= extractor.PDF_OCR_MAX_IMAGE_EDGE
        assert processed.width < rendered.width
        assert processed.height < rendered.height

    def test_empty_visual_source_goes_directly_to_tier1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        f = tmp_path / "messy.pdf"
        f.write_bytes(b"%PDF-1.7\n")
        calls = {"tier1": 0}

        class _Result:
            text_content = ""

        class _MarkItDown:
            def convert(self, _path: str):
                return _Result()

        monkeypatch.setattr(extractor, "_get_markitdown", lambda: _MarkItDown())
        monkeypatch.setattr(
            extractor,
            "_build_llm_ocr_requests",
            lambda *_args: ("[Image: page requires OCR]", [{"type": "ocr", "image_b64": "page-1", "prompt": "ocr"}]),
        )
        # Routing (ollama-glm-ocr) returns OCR text successfully
        monkeypatch.setattr(
            extractor, "_routing_run_ocr",
            lambda *_args, **_kwargs: OcrResult(success=True, results={"0": "OCR text from GLM."}, engine_id="ollama-glm-ocr"),
        )

        original = extractor._request_llm_ocr

        def wrapped_request(*args, **kwargs):
            calls["tier1"] += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(extractor, "_request_llm_ocr", wrapped_request)

        result = extract(str(f), max_tier=1, allow_cloud=True)

        assert result.success is True
        assert result.tier_used == 1
        assert calls["tier1"] == 1
        assert result.hardware_backend == "ollama-glm-ocr"

    def test_empty_image_fallback_escalates_to_glm_ocr(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        f = tmp_path / "scan.png"
        f.write_bytes(b"fake image bytes")

        class _MarkItDown:
            def convert(self, _path: str):
                raise RuntimeError("image conversion unsupported")

        monkeypatch.setattr(extractor, "_get_markitdown", lambda: _MarkItDown())
        monkeypatch.setattr(extractor, "_extract_without_markitdown", lambda *_args: "")
        monkeypatch.setattr(
            extractor, "_routing_run_ocr",
            lambda *_args, **_kwargs: OcrResult(success=True, results={"0": "OCR text from GLM."}, engine_id="ollama-glm-ocr"),
        )

        result = extract(str(f), max_tier=1, allow_cloud=False)

        assert result.success is True
        assert result.tier_used == 1
        assert result.hardware_backend == "ollama-glm-ocr"
        assert result.ocr_applied is True
        assert "OCR text from GLM" in result.markdown

    def test_failed_glm_ocr_does_not_return_empty_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        f = tmp_path / "scan.png"
        f.write_bytes(b"fake image bytes")

        class _Result:
            text_content = ""

        class _MarkItDown:
            def convert(self, _path: str):
                return _Result()

        monkeypatch.setattr(extractor, "_get_markitdown", lambda: _MarkItDown())
        # Routing layer reports OCR failure (engine failed)
        monkeypatch.setattr(
            extractor, "_routing_run_ocr",
            lambda *_args, **_kwargs: OcrResult(success=False, results={}, engine_id="ollama-glm-ocr", error="runner stopped"),
        )

        result = extract(str(f), max_tier=1, allow_cloud=False)

        assert result.success is False
        assert result.tier_used == 1
        assert result.hardware_backend == "ollama-glm-ocr"
        assert result.error is not None
        assert "runner stopped" in result.error

    def test_is_hebrew_language_hint_removed(self):
        """D2: _is_hebrew_language_hint has been deleted; no Hebrew special-case in extractor."""
        assert not hasattr(extractor, "_is_hebrew_language_hint")

    def test_run_ollama_ocr_removed_from_extractor(self):
        """_run_ollama_ocr moved to src.lib.routing.engines; extractor no longer owns it."""
        assert not hasattr(extractor, "_run_ollama_ocr")


# ---------------------------------------------------------------------------
# TestMergeLlmResults
# ---------------------------------------------------------------------------

class TestMergeLlmResults:
    def test_merge_replaces_placeholder(self):
        partial = textwrap.dedent("""\
            # Document
            Page 1 content.
            [Image: page requires OCR]
            Page 3 content.
        """)
        results = {"0": "OCR extracted text from page 2."}
        merged = merge_llm_results(partial, results)
        assert "[Image: page requires OCR]" not in merged
        assert "OCR extracted text from page 2." in merged

    def test_merge_with_no_results(self):
        original = "# Document\nSome content."
        merged = merge_llm_results(original, {})
        assert merged == original


# ---------------------------------------------------------------------------
# TestDetectAvailableTier
# ---------------------------------------------------------------------------

class TestDetectAvailableTier:
    def test_tier0_always_available(self):
        tier = detect_available_tier()
        assert tier >= 0
