from pathlib import Path
import pytest


def test_read_index_entry_parses_frontmatter(tmp_path):
    """Read a pointer index entry and return metadata dict."""
    from src.lib.index.index_reader import read_index_entry

    entry = tmp_path / "skills" / "career-ops" / "career-ops.md"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        "---\n"
        "type: skill\n"
        "hub: career\n"
        "name: career-ops\n"
        "source_path: skills/career-ops/SKILL.md\n"
        "description: Job pipeline tracking\n"
        "---\n"
    )

    result = read_index_entry(entry)
    assert result["type"] == "skill"
    assert result["hub"] == "career"
    assert result["source_path"] == "skills/career-ops/SKILL.md"
    assert result["_index_path"] == str(entry)


def test_read_index_entry_extracts_wikilink_relationships_from_any_field(tmp_path):
    """Any wikilink-bearing field contributes relationship targets."""
    from src.lib.index.index_reader import read_index_entry

    entry = tmp_path / "skills" / "career-ops" / "career-ops.md"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        "---\n"
        "type: skill\n"
        "hub: career\n"
        "name: career-ops\n"
        "source_path: skills/career-ops/SKILL.md\n"
        "mentors: '[[Ada Lovelace|Ada]] and [[Grace Hopper]]'\n"
        "arbitrary:\n"
        "  - '[[Augur]]'\n"
        "---\n"
    )

    result = read_index_entry(entry)
    assert result["relationships"] == {
        "mentors": ["Ada Lovelace", "Grace Hopper"],
        "arbitrary": ["Augur"],
    }
    assert result["relationship_targets"] == ["Ada Lovelace", "Grace Hopper", "Augur"]


def test_list_category_entries(tmp_path):
    """List all index entries in a category directory."""
    from src.lib.index.index_reader import list_category_entries

    cat_dir = tmp_path / "skills"
    (cat_dir / "career").mkdir(parents=True)
    (cat_dir / "career" / "career.md").write_text(
        "---\ntype: skill\nhub: career\nname: career\n"
        "source_path: x\ndescription: desc\n---\n"
    )
    (cat_dir / "career" / "growth.md").write_text(
        "---\ntype: skill\nhub: career\nname: growth\n"
        "source_path: y\ndescription: desc2\n---\n"
    )

    results = list_category_entries(cat_dir)
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert names == {"career", "growth"}


def test_list_category_entries_with_hub_filter(tmp_path):
    """Filter entries by hub."""
    from src.lib.index.index_reader import list_category_entries

    cat_dir = tmp_path / "skills"
    (cat_dir / "career").mkdir(parents=True)
    (cat_dir / "career" / "career.md").write_text(
        "---\ntype: skill\nhub: career\nname: career\n"
        "source_path: x\ndescription: desc\n---\n"
    )
    (cat_dir / "ai").mkdir(parents=True)
    (cat_dir / "ai" / "rag.md").write_text(
        "---\ntype: skill\nhub: ai\nname: rag\n"
        "source_path: y\ndescription: desc2\n---\n"
    )

    results = list_category_entries(cat_dir, hub="career")
    assert len(results) == 1
    assert results[0]["name"] == "career"


def test_null_hub_maps_to_system(tmp_path):
    """Entries with hub: null should report hub as 'system'."""
    from src.lib.index.index_reader import read_index_entry

    entry = tmp_path / "adrs" / "adr-004.md"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        "---\ntype: adr\nhub: null\nname: adr-004\n"
        "source_path: dev/adrs/ADR-004.md\n---\n"
    )

    result = read_index_entry(entry)
    assert result["hub"] == "system"


def test_read_index_entry_drops_legacy_wiki_compile_fields_after_reindex(tmp_path):
    from src.lib.index.index_reader import read_index_entry
    from src.lib.index.unified_indexer import reindex_all
    from src.lib.index import _scanners_knowledge
    from src.lib.frontmatter_utils import parse_frontmatter

    skill_dir = tmp_path / "plugins" / "brain" / "skills" / "ideas"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: ideas\n"
        "description: Ideas skill\n"
        "hub: brain\n"
        "x-augur-hub: brain\n"
        "---\n"
        "# Ideas\n\n"
        "Current body that should generate a new checksum.\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    entry = rag_dir / "skills" / "brain" / "ideas.md"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        "---\n"
        "type: skill\n"
        "hub: brain\n"
        "name: ideas\n"
        "source_path: plugins/brain/skills/ideas/SKILL.md\n"
        "checksum: old-checksum\n"
        "wiki_compile_status: compiled\n"
        "wiki_compiled_checksum: abc123\n"
        "wiki_compiled_at: 2026-04-14T09:00:00+00:00\n"
        "wiki_targets:\n"
        "  - startup-ideas\n"
        "manual_related:\n"
        "  - vault/career/notes.md\n"
        "---\n",
        encoding="utf-8",
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            _scanners_knowledge,
            "_discover_skill_dirs",
            lambda _root: [("brain", skill_dir)],
        )
        reindex_all(tmp_path, rag_dir, vault_dir=None)

    rewritten_entry = next((rag_dir / "skills").rglob("ideas.md"))
    result = read_index_entry(rewritten_entry)
    assert "wiki_compile_status" not in result
    assert "wiki_compiled_checksum" not in result
    assert "wiki_compiled_at" not in result
    assert "wiki_targets" not in result
    assert result["manual_related"] == ["vault/career/notes.md"]


def test_write_entry_drops_legacy_wiki_compile_metadata(tmp_path):
    from src.lib.index._indexer_helpers import _write_entry
    from src.lib.frontmatter_utils import parse_frontmatter

    entry = tmp_path / "skills" / "brain" / "ideas.md"
    entry.parent.mkdir(parents=True)

    _write_entry(
        entry,
        {
            "type": "skill",
            "hub": "brain",
            "name": "ideas",
            "source_path": "plugins/brain/skills/ideas/SKILL.md",
            "checksum": "new-checksum",
            "manual_related": ["vault/career/notes.md"],
            "wiki_compile_status": "compiled",
            "wiki_compiled_checksum": "abc123",
            "wiki_compiled_at": "2026-04-14T09:00:00+00:00",
            "wiki_targets": ["startup-ideas"],
        },
        "fresh body",
    )

    meta, body = parse_frontmatter(entry)
    assert meta["manual_related"] == ["vault/career/notes.md"]
    assert "wiki_compile_status" not in meta
    assert "wiki_compiled_checksum" not in meta
    assert "wiki_compiled_at" not in meta
    assert "wiki_targets" not in meta
    assert body.strip() == "fresh body"
