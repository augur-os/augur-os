from src.lib.index.rtl_repair import hebrew_reversal_ratio, is_reversed_document


def test_flags_reversed_hebrew():
    # "סניף באר שבע" extracted in visual order -> each word reversed.
    reversed_text = "ףינס ראב עבש\nףינס ANH"
    assert hebrew_reversal_ratio(reversed_text) > 0.3
    assert is_reversed_document(reversed_text) is True


def test_does_not_flag_correct_hebrew():
    correct = "תוספות לרשימת תכולה\nשם: סניקוב גור\nכלל פנסיה וגמל בע\"מ"
    assert hebrew_reversal_ratio(correct) == 0.0
    assert is_reversed_document(correct) is False


def test_ignores_non_hebrew():
    assert hebrew_reversal_ratio("The Complete Guide to Skills") == 0.0
    assert is_reversed_document("Investor Deck 2026") is False


def test_empty_text_is_not_reversed():
    assert hebrew_reversal_ratio("") == 0.0
    assert is_reversed_document("") is False


def _write(path, meta_lines, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{meta_lines}\n---\n\n{body}\n", encoding="utf-8")


def test_reocr_repairs_reversed_doc(tmp_path, monkeypatch):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import rtl_repair

    rag = tmp_path / "rag"
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    entry = rag / "documents" / "finance" / "doc.md"
    _write(
        entry,
        f"type: document\nname: doc\nsource_path: {pdf}\ntitle: ףינס ראב עבש\ndocument_title: ףינס ראב עבש",
        "ףינס ראב עבש\nףינס ראב עבש ANH",
    )

    def fake_ocr(path, *, client=None, max_pages=20, dpi=200):
        return {"text": "סניף באר שבע\nמרכז שירות לקוחות", "method": "vision-ocr-glm", "pages": 1}

    monkeypatch.setattr(rtl_repair, "_infer_title", lambda *a, **k: "סניף באר שבע", raising=False)
    monkeypatch.setattr("src.lib.index.ocr_extractor.extract_text_via_vision_ocr", fake_ocr)

    result = rtl_repair.reocr_reversed_documents(rag)
    assert result["repaired"] == 1
    meta, body = parse_frontmatter(entry)
    assert "סניף" in body
    assert meta["document_extraction_method"] == "vision-ocr-glm"


def test_reocr_keeps_original_when_ocr_still_reversed(tmp_path, monkeypatch):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import rtl_repair

    rag = tmp_path / "rag"
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    entry = rag / "documents" / "x" / "doc.md"
    _write(entry, f"type: document\nname: doc\nsource_path: {pdf}", "ףינס ראב עבש ףינס ראב עבש")

    monkeypatch.setattr(
        "src.lib.index.ocr_extractor.extract_text_via_vision_ocr",
        lambda path, **k: {"text": "ףינס ראב עבש ףינס", "method": "vision-ocr-glm", "pages": 1},
    )
    result = rtl_repair.reocr_reversed_documents(rag)
    assert result["failed"] == 1
    assert result["repaired"] == 0
    _, body = parse_frontmatter(entry)
    assert body.strip().startswith("ףינס")  # unchanged
