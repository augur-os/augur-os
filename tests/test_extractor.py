"""Auto-generated importability test for extractor."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_extractor_importable():
    """Verify that extractor can be imported without errors."""
    import src.lib.extraction.extractor

    assert src.lib.extraction.extractor is not None


def test_extract_image_delegates_ocr_to_routing(monkeypatch, tmp_path):
    import src.lib.extraction.extractor as extractor
    from src.lib.routing.engines import OcrResult

    captured = {}

    def fake_run_ocr(requests, *, mode=None, os_name=None):
        captured["requests"] = requests
        return OcrResult(success=True, results={"0": "ROUTED TEXT"}, engine_id="ollama-glm-ocr")

    monkeypatch.setattr(extractor, "_routing_run_ocr", fake_run_ocr)

    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)  # minimal bytes; markitdown yields no text
    result = extractor.extract(str(img), max_tier=1, allow_cloud=True)

    assert "ROUTED TEXT" in result.markdown
    assert result.ocr_applied is True
    assert captured["requests"]  # routing was actually called


def test_extract_no_longer_special_cases_hebrew(monkeypatch, tmp_path):
    # D2: language_hint="he" must NOT short-circuit to a hebrew-cloud-required error.
    import src.lib.extraction.extractor as extractor
    from src.lib.routing.engines import OcrResult

    monkeypatch.setattr(
        extractor,
        "_routing_run_ocr",
        lambda requests, *, mode=None, os_name=None: OcrResult(True, {"0": "shalom"}, "ollama-glm-ocr"),
    )
    img = tmp_path / "he.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    result = extractor.extract(str(img), max_tier=1, allow_cloud=False, language_hint="he")
    assert result.hardware_backend != "hebrew-cloud-required"
