"""Unit tests for the leaf helper module ``skills_common``.

Exercises the pure/deterministic helpers used by the skill-discovery tool
implementations: generated-doc detection, source-line extraction, and the
generated-header stripper. Filesystem-only inputs use ``Path`` objects under
``tmp_path``; no real vault/repo files are touched.
"""

from __future__ import annotations

from pathlib import Path

from src.mcp.augur_core.tools.core import skills_common
from src.mcp.augur_core.tools.core.skills_common import (
    GENERATED_CLIENT_DIRS,
    GENERATED_DOC_MARKER,
    _generated_source_path,
    _is_generated_skill_doc,
    _resolve_skill_note_brain_id,
    _strip_generated_header,
)


def test_is_generated_skill_doc_by_client_dir():
    """A path inside a generated client dir is always treated as generated."""
    for client_dir in GENERATED_CLIENT_DIRS:
        md = Path("/repo") / client_dir / "skills" / "foo" / "SKILL.md"
        assert _is_generated_skill_doc(md, "plain content with no marker") is True


def test_is_generated_skill_doc_by_marker_in_content():
    """A non-client path is generated only when the marker is in the head."""
    md = Path("/repo/project-brain/capabilities/skills/foo/SKILL.md")
    content = f"<!-- {GENERATED_DOC_MARKER} -->\n# Foo\n"
    assert _is_generated_skill_doc(md, content) is True


def test_is_generated_skill_doc_authored_source_is_false():
    """A hand-authored doc with no marker and no client dir is not generated."""
    md = Path("/repo/project-brain/capabilities/skills/foo/SKILL.md")
    assert _is_generated_skill_doc(md, "# Foo\nReal authored content.\n") is False


def test_is_generated_skill_doc_marker_only_in_head_window():
    """The marker is only honored within the first 2048 chars of content."""
    md = Path("/repo/project-brain/capabilities/skills/foo/SKILL.md")
    far_content = ("x" * 3000) + GENERATED_DOC_MARKER
    assert _is_generated_skill_doc(md, far_content) is False


def test_generated_source_path_extracts_value():
    """The ``Source:`` line value is returned, trimmed."""
    content = "<!-- header -->\nSource:   skills/foo/SKILL.md   \n# Foo\n"
    assert _generated_source_path(content) == "skills/foo/SKILL.md"


def test_generated_source_path_missing_returns_none():
    """No ``Source:`` line yields None."""
    assert _generated_source_path("# Foo\nNo source line here.\n") is None


def test_strip_generated_header_removes_marker_comment():
    """A leading generated-marker HTML comment is stripped, body preserved."""
    markdown = f"<!-- {GENERATED_DOC_MARKER}\nSource: x -->\n\n# Real Title\nBody"
    result = _strip_generated_header(markdown)
    assert result.startswith("# Real Title")
    assert GENERATED_DOC_MARKER not in result


def test_strip_generated_header_keeps_non_marker_comment():
    """A leading comment without the marker is left intact (only outer-stripped)."""
    markdown = "<!-- ordinary comment -->\n# Title"
    result = _strip_generated_header(markdown)
    assert result == "<!-- ordinary comment -->\n# Title"


def test_strip_generated_header_no_comment_just_strips():
    """Plain markdown without a comment is returned stripped of surrounding ws."""
    assert _strip_generated_header("\n\n# Title\nBody\n\n") == "# Title\nBody"


def test_strip_generated_header_unterminated_comment():
    """An unterminated comment (no ``-->``) returns the stripped original."""
    markdown = "<!-- never closes\n# Title"
    assert _strip_generated_header(markdown) == "<!-- never closes\n# Title"


def test_resolve_skill_note_brain_id_is_best_effort(tmp_path: Path):
    """The brain-id resolver never raises; it returns a str or None."""
    md = tmp_path / "note.md"
    md.write_text("# note", encoding="utf-8")
    result = _resolve_skill_note_brain_id(md)
    assert result is None or isinstance(result, str)


def test_module_constants_present():
    """Module-level constants are wired and have the expected shape."""
    assert isinstance(skills_common.GENERATED_DOC_MARKER, str)
    assert ".claude" in skills_common.GENERATED_CLIENT_DIRS
    assert ".gemini" in skills_common.GENERATED_CLIENT_DIRS
