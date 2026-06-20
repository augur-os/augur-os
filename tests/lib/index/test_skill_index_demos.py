"""Skill demos surface in skills-index metadata (ADR-813, rule 32).

A skill that ships a ``demos/`` directory with markdown runbooks gets a
``demos`` metadata field on its skills-index entry: a flat list of
``"Title|relative/path"`` strings (the flat-string-list shape mirrors
``client_sources`` so the value survives the frontmatter round-trip and the
browse-index metadata flattener).
"""

from __future__ import annotations

from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.index._scanners_knowledge import index_skills


def _write_skill(skill_dir: Path, name: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill {name}\n---\n# {name}\n",
        encoding="utf-8",
    )


def _entry_meta(rag_dir: Path, name: str) -> dict:
    matches = [path for path in (rag_dir / "skills").rglob(f"{name}.md")]
    assert matches, f"no index entry written for skill {name!r}"
    meta, _ = parse_frontmatter(matches[0])
    return meta


def test_skill_with_demos_gets_demos_metadata(tmp_path: Path) -> None:
    root = tmp_path
    skill_dir = root / "project-brain" / "capabilities" / "skills" / "ingest"
    _write_skill(skill_dir, "ingest")
    demos_dir = skill_dir / "demos"
    demos_dir.mkdir()
    (demos_dir / "README.md").write_text("# demos index\n", encoding="utf-8")
    (demos_dir / "demo_02_offload_transcription.md").write_text("# runbook\n", encoding="utf-8")
    (demos_dir / "demo_01_wiki_cross_agent.md").write_text(
        "---\ntitle: Wiki cross-agent ask\n---\n# runbook\n", encoding="utf-8"
    )

    index_skills(root, root / "rag")

    meta = _entry_meta(root / "rag", "ingest")
    assert meta["demos"] == [
        "Wiki cross-agent ask|project-brain/capabilities/skills/ingest/demos/demo_01_wiki_cross_agent.md",
        "Offload Transcription|project-brain/capabilities/skills/ingest/demos/demo_02_offload_transcription.md",
    ]


def test_skill_without_demos_has_no_demos_field(tmp_path: Path) -> None:
    root = tmp_path
    _write_skill(root / "project-brain" / "capabilities" / "skills" / "knowledge", "knowledge")

    index_skills(root, root / "rag")

    meta = _entry_meta(root / "rag", "knowledge")
    assert "demos" not in meta
