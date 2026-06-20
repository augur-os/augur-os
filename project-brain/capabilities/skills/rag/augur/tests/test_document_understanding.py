"""Tests for canonical document understanding routing.

These tests verify the router contract and summary/insight shaping without
depending on real OCR or document parsing.
"""
from __future__ import annotations


def test_understand_document_prefers_pymupdf_for_text_pdf(monkeypatch, tmp_path):
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    from src.lib.index import document_understanding

    monkeypatch.setattr(
        document_understanding,
        "_extract_text_pdf",
        lambda path: {
            "body": "The Complete Guide to Building Skills for Claude",
            "title": "The Complete Guide to Building Skills for Claude",
            "method": "pymupdf",
            "ocr_applied": False,
        },
    )
    monkeypatch.setattr(document_understanding, "_extract_via_document_extractor", lambda path: None)

    result = document_understanding.understand_document(pdf)

    assert result["title"] == "The Complete Guide to Building Skills for Claude"
    assert result["extraction_method"] == "pymupdf"
    assert result["document_kind"] == "pdf"
    assert result["body"].startswith("The Complete Guide")


def test_understand_document_returns_summary_and_key_insights_for_pdf(monkeypatch, tmp_path):
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    from src.lib.index import document_understanding

    monkeypatch.setattr(
        document_understanding,
        "_extract_text_pdf",
        lambda path: {
            "body": (
                "The Complete Guide to Building Skills for Claude\n\n"
                "A skill is a set of instructions packaged as a folder.\n"
                "Skills are the knowledge layer on top of MCP.\n"
                "Progressive disclosure minimizes token usage.\n"
            ),
            "title": "The Complete Guide to Building Skills for Claude",
            "method": "pymupdf",
            "ocr_applied": False,
        },
    )
    monkeypatch.setattr(document_understanding, "_extract_via_document_extractor", lambda path: None)

    result = document_understanding.understand_document(pdf)

    assert "knowledge layer on top of MCP" in result["summary"]
    assert any("Progressive disclosure" in item for item in result["key_insights"])
    assert result["understanding_version"]


def test_infer_title_uses_frontmatter_title():
    from src.lib.index.document_understanding import _infer_title

    text = (
        "---\ntitle: L28 — Pitch Deck Review\ntype: transcript\n---\n\n"
        "# Some Heading\n\nbody text"
    )
    assert _infer_title(text, fallback="L28") == "L28 — Pitch Deck Review"


def test_infer_title_uses_first_h1_when_no_frontmatter_title():
    from src.lib.index.document_understanding import _infer_title

    text = "# My Real Heading\n\nSome body text here."
    assert _infer_title(text, fallback="my-file") == "My Real Heading"


def test_infer_title_skips_frontmatter_block_for_meaningful_line():
    from src.lib.index.document_understanding import _infer_title

    text = "---\ntype: note\nstatus: draft\n---\n\nThe first real sentence of the note."
    assert _infer_title(text, fallback="note") == "The first real sentence of the note."


def test_understand_document_uses_markdown_title_not_stem(tmp_path):
    """A markdown file's frontmatter/H1 title beats the bare filename stem."""
    from src.lib.index import document_understanding

    md = tmp_path / "L28.md"
    md.write_text(
        "---\ntitle: L28 — Pitch Deck Review (recording)\ntype: transcript\n---\n\n"
        "# L28 — Pitch Deck Review (recording)\n\nThe pitch covered the roadmap.",
        encoding="utf-8",
    )

    result = document_understanding.understand_document(md)

    assert result["title"] == "L28 — Pitch Deck Review (recording)"


def test_infer_title_skips_html_comment_artifacts():
    from src.lib.index.document_understanding import _infer_title

    # MarkItDown emits slide markers as HTML comments; never use them as a title.
    text = "<!-- Slide number: 1 -->\n\nAugur — The Local-First Second Brain\n\nMore."
    assert _infer_title(text, fallback="deck") == "Augur — The Local-First Second Brain"


def test_is_noise_title_flags_markup():
    from src.lib.index.document_understanding import is_noise_title

    assert is_noise_title("<!-- Slide number: 1 -->")
    assert is_noise_title("---")
    assert is_noise_title("| col | col |")
    assert not is_noise_title("Investor Deck")


def test_is_noise_title_flags_boilerplate_and_garbage():
    from src.lib.index.document_understanding import is_noise_title

    assert is_noise_title("©2019 Baruch Deutsch. All Rights Reserved.")
    assert is_noise_title("(*294589)")
    assert is_noise_title('î"òá ïìéç - òåöéáå ãåáéò')  # Latin-1 mojibake
    # Legitimate titles (including all-caps and Hebrew) are kept.
    assert not is_noise_title("ANDREJ KARPATHY PATTERN")
    assert not is_noise_title("The Complete Guide to Building Skills")
    assert not is_noise_title("דוח שנתי ביטוח חיים")


def test_understand_document_uses_text_fallback_when_extractor_unavailable(monkeypatch, tmp_path):
    text_file = tmp_path / "notes.txt"
    text_file.write_text("Invoice\n\nSubmit reimbursement by Friday.", encoding="utf-8")

    from src.lib.index import document_understanding

    monkeypatch.setattr(document_understanding, "_extract_via_document_extractor", lambda path: None)

    result = document_understanding.understand_document(text_file)

    assert result["body"].startswith("Invoice")
    assert result["extraction_method"] == "text-like"
    assert result["action_candidates"] == ["Submit reimbursement by Friday."]


def test_understand_document_marks_llm_assisted_tier(monkeypatch, tmp_path):
    text_file = tmp_path / "scan.txt"
    text_file.write_text("Scan", encoding="utf-8")

    from src.lib.index import document_understanding

    monkeypatch.setattr(
        document_understanding,
        "_extract_via_document_extractor",
        lambda path: {
            "body": "Review scanned paperwork before Friday.",
            "title": "Scan",
            "method": "document-extractor:1",
            "ocr_applied": True,
            "llm_assisted": True,
        },
    )

    result = document_understanding.understand_document(text_file)

    assert result["llm_assisted"] is True
    assert result["visual_structure_used"] is True


def test_understand_document_flags_long_low_signal_text(monkeypatch, tmp_path):
    text_file = tmp_path / "noise.txt"
    text_file.write_text("fallback", encoding="utf-8")

    from src.lib.index import document_understanding

    monkeypatch.setattr(
        document_understanding,
        "_extract_via_document_extractor",
        lambda path: {
            "body": "@@@ ### !!! ??? " * 20,
            "title": "Noise",
            "method": "document-extractor:0",
            "ocr_applied": False,
            "llm_assisted": False,
        },
    )

    result = document_understanding.understand_document(text_file)

    assert result["extraction_confidence"] == "low"
    assert result["low_signal_warnings"] == ["high_symbol_ratio"]
