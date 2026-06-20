"""Tests for launch metadata in skill discovery."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from src.plugins.skill_discovery import (
    SkillRecord,
    _discover_all_skills_impl,
    _skill_record_to_metadata,
    invalidate_discovery_cache,
)


def _write_skill_md(skill_dir: Path, name: str, extra_fm: str = "") -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\n" f"name: {name}\n" f"description: test skill\n" f"{extra_fm}" f"---\n\n" f"Skill body.\n"
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _write_flat_skill(
    skill_dir: Path,
    name: str,
    extra_fm: str = "",
    ext: str = ".mdc",
) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\n" f"name: {name}\n" f"description: test skill\n" f"{extra_fm}" f"---\n\n" f"Skill body.\n"
    (skill_dir / f"{name}{ext}").write_text(content, encoding="utf-8")


def test_skill_record_exposes_launch_fields():
    record = SkillRecord(
        name="launch-skill",
        description="test skill",
        path=Path("/tmp/launch-skill"),
        author="bundled",
        hub="dev",
        visibility="",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        config={},
        agent=None,
        skill_type="",
        tags=(),
        tier=0,
        group="productivity",
        release="r2",
        category="launch",
        requires_platform=True,
    )

    assert record.group == "productivity"
    assert record.release == "r2"
    assert record.category == "launch"
    assert record.requires_platform is True


def test_discover_all_skills_parses_launch_frontmatter_fields():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill_dir = root / "project-brain" / "capabilities" / "skills" / "launch-skill"
        _write_skill_md(
            skill_dir,
            "launch-skill",
            extra_fm=(
                "x-augur-group: productivity\n"
                "x-augur-release: r2\n"
                "x-augur-category: launch\n"
                "x-augur-requires-platform: true\n"
            ),
        )

        with (
            patch("src.plugins.skill_discovery.get_project_root", return_value=root),
            patch(
                "src.plugins.skill_discovery.get_managed_skill_source_dirs",
                return_value=[root / "project-brain" / "capabilities" / "skills"],
            ),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value={}),
        ):
            invalidate_discovery_cache()
            records = _discover_all_skills_impl(tiers=(0,))

    record = next(r for r in records if r.name == "launch-skill")
    assert record.group == "productivity"
    assert record.release == "r2"
    assert record.category == "launch"
    assert record.requires_platform is True


def test_discover_all_skills_parses_launch_frontmatter_fields_from_flat_client_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        prompts_dir = root / ".cursor" / "rules"
        _write_flat_skill(
            prompts_dir,
            "launch-flat",
            extra_fm=(
                "x-augur-group: productivity\n"
                "x-augur-release: r2\n"
                "x-augur-category: launch\n"
                "x-augur-requires-platform: true\n"
            ),
        )

        with (
            patch(
                "src.plugins.skill_discovery.get_skills_dir",
                return_value=root / "project-brain" / "capabilities" / "skills",
            ),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch(
                "src.plugins.skill_discovery._get_client_skill_dirs",
                return_value={"cursor-local": prompts_dir},
            ),
        ):
            invalidate_discovery_cache()
            records = _discover_all_skills_impl(tiers=(2,))

    record = next(r for r in records if r.name == "launch-flat")
    assert record.group == "productivity"
    assert record.release == "r2"
    assert record.category == "launch"
    assert record.requires_platform is True


def test_discover_all_skills_allows_missing_release_frontmatter_during_migration():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill_dir = root / "project-brain" / "capabilities" / "skills" / "launch-skill"
        _write_skill_md(
            skill_dir,
            "launch-skill",
            extra_fm="x-augur-group: productivity\n",
        )

        with (
            patch("src.plugins.skill_discovery.get_project_root", return_value=root),
            patch(
                "src.plugins.skill_discovery.get_managed_skill_source_dirs",
                return_value=[root / "project-brain" / "capabilities" / "skills"],
            ),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value={}),
        ):
            invalidate_discovery_cache()
            records = _discover_all_skills_impl(tiers=(0,))

    record = next(r for r in records if r.name == "launch-skill")
    assert record.group == "productivity"
    assert record.release is None


def test_discover_all_skills_rejects_invalid_explicit_release_value():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill_dir = root / "project-brain" / "capabilities" / "skills" / "launch-skill"
        _write_skill_md(
            skill_dir,
            "launch-skill",
            extra_fm="x-augur-release: ga\n",
        )

        with (
            patch("src.plugins.skill_discovery.get_project_root", return_value=root),
            patch(
                "src.plugins.skill_discovery.get_managed_skill_source_dirs",
                return_value=[root / "project-brain" / "capabilities" / "skills"],
            ),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value={}),
        ):
            invalidate_discovery_cache()
            try:
                _discover_all_skills_impl(tiers=(0,))
            except ValueError as exc:
                assert "ga" in str(exc)
            else:
                raise AssertionError("Expected ValueError for invalid x-augur-release")


def test_legacy_metadata_conversion_preserves_launch_fields():
    record = SkillRecord(
        name="launch-skill",
        description="test skill",
        path=Path("/tmp/launch-skill"),
        author="bundled",
        hub="dev",
        visibility="",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        config={},
        agent=None,
        skill_type="",
        tags=(),
        tier=0,
        group="productivity",
        release="r2",
        category="launch",
        requires_platform=True,
    )

    metadata = _skill_record_to_metadata(record)

    assert metadata.group == "productivity"
    assert metadata.release == "r2"
    assert metadata.category == "launch"
    assert metadata.requires_platform is True
