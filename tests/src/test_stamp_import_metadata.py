"""Tests for stamp_import_metadata in frontmatter_utils."""

import tempfile
from pathlib import Path
from src.lib.frontmatter_utils import parse_frontmatter


def test_stamp_import_metadata_adds_fields():
    from src.lib.frontmatter_utils import stamp_import_metadata

    with tempfile.TemporaryDirectory() as td:
        skill_path = Path(td)
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("---\nname: test-skill\ndescription: A test\n---\n\nBody content.\n")
        stamp_import_metadata(skill_path, "github", "https://github.com/user/repo", "1.2.0")
        fm, body = parse_frontmatter(skill_md)
        assert fm["x-augur-source"] == "github"
        assert fm["x-augur-source-url"] == "https://github.com/user/repo"
        assert fm["x-augur-source-version"] == "1.2.0"
        assert "x-augur-imported-at" in fm
        assert "Body content." in body


def test_stamp_import_metadata_preserves_existing():
    from src.lib.frontmatter_utils import stamp_import_metadata

    with tempfile.TemporaryDirectory() as td:
        skill_path = Path(td)
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("---\nname: test-skill\nx-augur-type: command\n---\n\nBody.\n")
        stamp_import_metadata(skill_path, "skills-sh", "https://skills.sh/test", "0.1.0")
        fm, _ = parse_frontmatter(skill_md)
        assert fm["name"] == "test-skill"
        assert fm["x-augur-type"] == "command"
        assert fm["x-augur-source"] == "skills-sh"
