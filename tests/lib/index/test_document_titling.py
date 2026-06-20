from pathlib import Path


from src.lib.index import document_titling as dt


class FakeClient:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = 0

    def generate_text(self, *, prompt, system=None, model=None, temperature=None, max_tokens=None):
        self.calls += 1
        return self.reply


def test_needs_llm_title_truth_table():
    # stem-only title -> needs
    assert dt.needs_llm_title({"name": "L28", "title": "L28"}, "Real body text here that is long enough.")
    # missing title -> needs
    assert dt.needs_llm_title({"name": "doc"}, "Real body text here that is long enough.")
    # good title -> no
    assert not dt.needs_llm_title({"name": "L28", "title": "Pitch Deck Review"}, "body text long enough")
    # llm-sourced title -> no (idempotent)
    assert not dt.needs_llm_title({"name": "doc", "title": "x", "title_source": "llm"}, "body" * 50)
    # empty/short body -> no (nothing to title from)
    assert not dt.needs_llm_title({"name": "doc"}, "short")
    # reversed-Hebrew body -> no (re-OCR handles it first)
    assert not dt.needs_llm_title({"name": "doc"}, "ףינס ראב עבש ףינס ראב עבש " * 5)


def test_generate_title_sanitizes_and_accepts():
    client = FakeClient('"Investor Pitch Deck Review"\n')
    title = dt.generate_title("body about the pitch deck", "augur-deck-pc", client=client)
    assert title == "Investor Pitch Deck Review"


def test_generate_title_rejects_noise_and_stem_echo():
    assert dt.generate_title("body", "augur-deck-pc", client=FakeClient("augur-deck-pc")) is None
    assert dt.generate_title("body", "deck", client=FakeClient("<!-- comment -->")) is None
    assert dt.generate_title("body", "deck", client=FakeClient("I cannot help with that.")) is None
    assert dt.generate_title("body", "deck", client=FakeClient("")) is None


def _write_entry(path: Path, meta_lines: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{meta_lines}\n---\n\n{body}\n", encoding="utf-8")


def test_backfill_titles_writes_and_is_idempotent(tmp_path):
    rag = tmp_path / "rag"
    entry = rag / "documents" / "venture" / "deck.md"
    _write_entry(
        entry,
        "type: document\nname: augur-deck-pc\ntitle: augur-deck-pc\ndocument_title: augur-deck-pc",
        "This deck explains the local-first second brain platform vision in detail.",
    )
    client = FakeClient("Local-First Second Brain Platform")
    result = dt.backfill_llm_titles(rag, client=client)
    assert result["titled"] == 1

    from src.lib.frontmatter_utils import parse_frontmatter

    meta, _ = parse_frontmatter(entry)
    assert meta["title"] == "Local-First Second Brain Platform"
    assert meta["document_title"] == "Local-First Second Brain Platform"
    assert meta["title_source"] == "llm"

    # Second run: already llm-titled -> no new calls.
    calls_before = client.calls
    result2 = dt.backfill_llm_titles(rag, client=client)
    assert result2["titled"] == 0
    assert client.calls == calls_before


def test_sanitize_truncates_pipe_dumps_and_caps_words():
    from src.lib.index.document_titling import _sanitize_title

    assert _sanitize_title("Team Manager at Intel | AI Transformation | Embedded") == "Team Manager at Intel"
    long = " ".join(f"w{i}" for i in range(30))
    assert len(_sanitize_title(long).split()) == 12


def test_is_valid_title_rejects_questions():
    from src.lib.index.document_titling import _is_valid_title

    assert not _is_valid_title("האם יש לך תיאור מפורט יותר של התמונה?", "doc")
    assert not _is_valid_title("Can you describe this image?", "doc")
    assert _is_valid_title("Quarterly Revenue Report", "doc")


def test_generate_title_rejects_question(monkeypatch):
    from src.lib.index import document_titling as dt

    assert dt.generate_title("body", "doc", client=FakeClient("Do you have a description?")) is None
