from __future__ import annotations

from pathlib import Path

from src.lib.index._scanners_knowledge import index_skills

SYNC_AGENTS_MARKER = (
    "<!--\n"
    "⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY\n"
    "Source: project-brain/capabilities/skills/augur-core/commands/ask.md\n"
    "Generator: project-brain/capabilities/skills/ai/scripts/sync_agents/\n"
    "-->\n"
)


def _write_skill(skill_dir: Path, name: str, body_prefix: str = "") -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill {name}\n---\n{body_prefix}# {name}\n",
        encoding="utf-8",
    )


def _indexed_names(rag_dir: Path) -> set[str]:
    return {path.stem for path in (rag_dir / "skills").rglob("*.md")}


def test_sync_agents_command_exports_are_excluded(tmp_path: Path) -> None:
    root = tmp_path
    _write_skill(root / "project-brain" / "capabilities" / "skills" / "ingest", "ingest")
    # Autosync export of an Augur COMMAND (no canonical skill dir named 'ask'):
    _write_skill(root / ".codex" / "skills" / "ask", "ask", body_prefix=SYNC_AGENTS_MARKER)

    index_skills(root, root / "rag")

    names = _indexed_names(root / "rag")
    assert "ingest" in names
    assert "ask" not in names


def test_canonical_skill_with_marker_is_never_excluded(tmp_path: Path) -> None:
    root = tmp_path
    # A canonical skill must be structurally unreachable by the marker check:
    # the origin guard in _is_duplicate_generated_skill returns False for
    # canonical origins before the sync_agents marker is ever inspected.
    _write_skill(
        root / "project-brain" / "capabilities" / "skills" / "ingest",
        "ingest",
        body_prefix=SYNC_AGENTS_MARKER,
    )

    index_skills(root, root / "rag")

    assert "ingest" in _indexed_names(root / "rag")


def test_genuine_client_skill_without_marker_is_kept(tmp_path: Path) -> None:
    root = tmp_path
    _write_skill(root / "project-brain" / "capabilities" / "skills" / "ingest", "ingest")
    # A genuinely user-installed client skill — must stay browsable:
    _write_skill(root / ".codex" / "skills" / "defuddle", "defuddle")

    index_skills(root, root / "rag")

    names = _indexed_names(root / "rag")
    assert "defuddle" in names
