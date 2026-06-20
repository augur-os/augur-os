"""Tests for slug_policy — capture-name policy (naming spec 2026-06-12).

Import convention: pythonpath includes project-brain/capabilities so
``from skills.ingest.scripts.slug_policy import ...`` resolves correctly.
"""
from skills.ingest.scripts.slug_policy import capture_slug, unique_name


def test_caps_at_six_words_no_date():
    s = capture_slug("How I Took Karpathy's LLM Wiki and Built an AI-Powered Second Brain in Obsidian")
    assert s == "how-i-took-karpathy-s-llm"
    assert len(s) <= 40


def test_strips_url_noise():
    assert capture_slug("https://www.iana.org/help/example-domains") == "iana-org-help-example-domains"


def test_collision_suffix(tmp_path):
    (tmp_path / "foo.md").write_text("x", encoding="utf-8")
    assert unique_name(tmp_path, "foo") == "foo-2"
    assert unique_name(tmp_path, "bar") == "bar"


def test_collision_suffix_increments_past_existing(tmp_path):
    (tmp_path / "foo.md").write_text("x", encoding="utf-8")
    (tmp_path / "foo-2.md").write_text("x", encoding="utf-8")
    assert unique_name(tmp_path, "foo") == "foo-3"


def test_empty_title_returns_untitled():
    # "untitled" only when ZERO word tokens remain — punctuation-only,
    # underscore-only, or emoji-only inputs (unicode-aware split keeps
    # real scripts like Hebrew, so they never hit this branch)
    assert capture_slug("") == "untitled"
    assert capture_slug("   ") == "untitled"
    assert capture_slug("!!! ... ???") == "untitled"
    assert capture_slug("___") == "untitled"
    assert capture_slug("\U0001f525\U0001f525\U0001f525") == "untitled"  # fire emoji


def test_long_slug_capped_at_40_chars():
    s = capture_slug("a" * 50)
    assert len(s) <= 40


def test_url_scheme_only_stripped():
    # scheme tokens (http, https, www) are stripped; host + path kept
    assert capture_slug("https://example.com/some/path") == "example-com-some-path"


def test_mixed_case_lowercased():
    assert capture_slug("Hello World") == "hello-world"


def test_hebrew_title_keeps_meaning():
    # spec Hebrew policy: meaningful Hebrew names beat transliteration
    assert capture_slug("טופס הצטרפות לקופת גמל") == "טופס-הצטרפות-לקופת-גמל"


def test_mixed_hebrew_latin_title():
    assert capture_slug("מדריך Python למתחילים") == "מדריך-python-למתחילים"


def test_hebrew_cap_counts_characters_not_bytes():
    # 50 Hebrew chars = 100 UTF-8 bytes; the 40 cap must be per-character
    s = capture_slug("א" * 50)
    assert len(s) == 40


def test_emoji_only_title_falls_back_to_url_in_card_target_path(tmp_path):
    from skills.ingest.scripts.url_ingest import card_target_path

    target = card_target_path(
        tmp_path,
        "https://example.com/some/long/article-path",
        title="\U0001f525\U0001f525\U0001f525",
    )
    assert target.name == "example-com-some-long-article-path.md"
