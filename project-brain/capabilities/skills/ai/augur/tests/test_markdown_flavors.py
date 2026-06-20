"""
Markdown flavors conversion tests (ADR-436).

Run with: pytest skills/ai/augur/tests/test_markdown_flavors.py -v
"""

import sys
from pathlib import Path

import pytest

# Add scripts to path — markdown_flavors lives in skills/ai/scripts/
# parents: [0]=tests, [1]=augur, [2]=ai, so scripts is under [2]
_lib_dir = Path(__file__).resolve().parents[2] / "scripts"
if str(_lib_dir) not in sys.path:
    sys.path.insert(0, str(_lib_dir))

from markdown_flavors import (
    convert,
    plain_to_obsidian,
    obsidian_to_plain,
    plain_to_logseq,
    logseq_to_plain,
)


class TestPlainToObsidian:
    def test_internal_link(self):
        assert plain_to_obsidian("[page](page.md)") == "[[page]]"

    def test_internal_link_with_alias(self):
        assert plain_to_obsidian("[alias](page.md)") == "[[page|alias]]"

    def test_external_link_unchanged(self):
        text = "[Google](https://google.com)"
        assert plain_to_obsidian(text) == text

    def test_mailto_unchanged(self):
        text = "[email](mailto:test@example.com)"
        assert plain_to_obsidian(text) == text

    def test_multiple_links(self):
        text = "[a](a.md) and [b](b.md)"
        result = plain_to_obsidian(text)
        assert "[[a]]" in result
        assert "[[b]]" in result

    def test_no_links_unchanged(self):
        text = "Just plain text with no links"
        assert plain_to_obsidian(text) == text

    def test_http_link_not_converted(self):
        text = "[docs](http://example.com/docs)"
        assert plain_to_obsidian(text) == text


class TestObsidianToPlain:
    def test_simple_wikilink(self):
        assert obsidian_to_plain("[[page]]") == "[page](page.md)"

    def test_aliased_wikilink(self):
        assert obsidian_to_plain("[[page|alias]]") == "[alias](page.md)"

    def test_embed(self):
        # Simple wikilink regex fires first: ![[x]] -> ![x](x.md)
        assert obsidian_to_plain("![[image.png]]") == "![image.png](image.png.md)"

    def test_no_wikilinks_unchanged(self):
        text = "Plain text without wikilinks"
        assert obsidian_to_plain(text) == text


class TestPlainToLogseq:
    def test_adds_bullets(self):
        text = "Some text"
        result = plain_to_logseq(text)
        assert result.startswith("- ")

    def test_headings_not_bulleted(self):
        text = "# Heading"
        result = plain_to_logseq(text)
        assert result == "# Heading"

    def test_blank_lines_preserved(self):
        text = "line1\n\nline2"
        result = plain_to_logseq(text)
        lines = result.split("\n")
        assert lines[1] == ""


class TestLogseqToPlain:
    def test_removes_bullets(self):
        text = "- Some text"
        result = logseq_to_plain(text)
        assert not result.startswith("- ")

    def test_wikilinks_converted(self):
        text = "- See [[page]]"
        result = logseq_to_plain(text)
        assert "[[" not in result
        assert "[page](page.md)" in result


class TestRoundTrip:
    def test_plain_obsidian_roundtrip(self):
        original = "[test](test.md)"
        obsidian = plain_to_obsidian(original)
        back = obsidian_to_plain(obsidian)
        assert back == original

    def test_convert_same_flavor(self):
        text = "Hello world"
        assert convert(text, "plain", "plain") == text

    def test_convert_invalid_source_raises(self):
        with pytest.raises(ValueError):
            convert("text", "unknown", "plain")

    def test_convert_invalid_target_raises(self):
        with pytest.raises(ValueError):
            convert("text", "plain", "unknown")

    def test_convert_plain_to_obsidian(self):
        result = convert("[link](link.md)", "plain", "obsidian")
        assert "[[link]]" in result

    def test_convert_obsidian_to_plain(self):
        result = convert("[[link]]", "obsidian", "plain")
        assert result == "[link](link.md)"

    def test_convert_plain_to_logseq(self):
        result = convert("[link](link.md)", "plain", "logseq")
        assert "[[link]]" in result

    def test_convert_logseq_to_plain(self):
        result = convert("- [[link]]", "logseq", "plain")
        assert "[link](link.md)" in result
