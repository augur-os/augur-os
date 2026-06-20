"""Tests for vault frontmatter system fields and relationship discovery."""

from __future__ import annotations

from pathlib import Path
import subprocess

from src.lib.frontmatter_utils import write_frontmatter


def test_system_field_partition_preserves_relative_order() -> None:
    from src.lib.frontmatter_utils import is_system_field, split_system_user

    metadata = {
        "title": "User note",
        "_checksum": "abc123",
        "status": "draft",
        "_source_path": "sources/web/example.md",
    }

    system, user = split_system_user(metadata)

    assert is_system_field("_checksum") is True
    assert is_system_field("x-augur-hub") is False
    assert list(system) == ["_checksum", "_source_path"]
    assert list(user) == ["title", "status"]


def test_merge_system_user_never_clobbers_user_fields(tmp_path: Path) -> None:
    from src.lib.frontmatter_utils import merge_system_user, parse_frontmatter

    merged = merge_system_user(
        {"_checksum": "new", "status": "system-status"},
        {"title": "Roadmap", "status": "active", "_checksum": "user-attempt"},
    )

    assert list(merged) == ["title", "status", "_checksum"]
    assert merged["status"] == "active"
    assert merged["_checksum"] == "new"

    note = tmp_path / "note.md"
    write_frontmatter(note, merged, "# Roadmap\n")
    parsed, body = parse_frontmatter(note)

    assert list(parsed) == ["title", "status", "_checksum"]
    assert parsed == merged
    assert body.lstrip("\n") == "# Roadmap\n"


def test_extract_relationships_scans_any_wikilink_bearing_field() -> None:
    from src.lib.frontmatter_utils import extract_relationships

    relationships = extract_relationships(
        {
            "status": "active",
            "mentors": "[[Ada Lovelace|Ada]] and [[Grace Hopper]]",
            "arbitrary_field": ["plain", "[[Augur]]", "[[Augur]]"],
            "nested": {
                "owner": "[[Gur Sannikov]]",
                "empty": 42,
                "notes": ["See [[Local First]]"],
            },
        }
    )

    assert relationships == {
        "mentors": ["Ada Lovelace", "Grace Hopper"],
        "arbitrary_field": ["Augur"],
        "nested.owner": ["Gur Sannikov"],
        "nested.notes": ["Local First"],
    }


def test_extract_relationships_handles_empty_and_non_string_values() -> None:
    from src.lib.frontmatter_utils import extract_relationships

    assert extract_relationships({}) == {}
    assert extract_relationships({"count": 1, "flags": [True, None], "data": {"x": 2}}) == {}


def test_parse_frontmatter_exposes_temporary_system_field_aliases(tmp_path: Path) -> None:
    from src.lib.frontmatter_utils import parse_frontmatter

    note = tmp_path / "concept.md"
    write_frontmatter(
        note,
        {
            "title": "Concept",
            "_page_type": "concept",
            "_sources": ["source:a"],
            "_source_fingerprint": "abc123",
        },
        "# Concept\n",
    )

    meta, _body = parse_frontmatter(note)

    assert meta["_page_type"] == "concept"
    assert meta["page_type"] == "concept"
    assert meta["sources"] == ["source:a"]
    assert meta["source_fingerprint"] == "abc123"


def test_write_vault_frontmatter_routes_system_metadata_through_merge(tmp_path: Path) -> None:
    from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter

    note = tmp_path / "concept.md"
    write_frontmatter(
        note,
        {"title": "User title", "status": "draft", "source_fingerprint": "old"},
        "# Concept\n",
    )

    write_vault_frontmatter(
        note,
        {"title": "Generated title", "source_fingerprint": "new", "page_type": "concept"},
        "# Concept\n",
    )

    raw = note.read_text(encoding="utf-8")
    assert "\nsource_fingerprint:" not in raw
    assert "_source_fingerprint: new" in raw
    assert "_page_type: concept" in raw
    meta, _body = parse_frontmatter(note)
    assert meta["title"] == "Generated title"
    assert meta["status"] == "draft"
    assert meta["_source_fingerprint"] == "new"
    assert meta["source_fingerprint"] == "new"


def test_relationship_index_discovers_frontmatter_relationships_without_field_allowlist(tmp_path: Path) -> None:
    from src.lib.relationship_index import RelationshipIndex

    vault = tmp_path / "vault"
    write_frontmatter(
        vault / "projects" / "augur.md",
        {
            "title": "Augur",
            "mentors": ["[[Ada Lovelace|Ada]]", "[[Grace Hopper]]"],
            "key_people": "[[Gur Sannikov]]",
        },
        "# Augur\n",
    )
    write_frontmatter(
        vault / "notes" / "local-first.md",
        {"title": "Local First", "custom_relation": "[[Augur]]"},
        "# Local First\n",
    )

    index = RelationshipIndex.build(vault)

    augur_path = vault / "projects" / "augur.md"
    assert index.relationships_for(augur_path) == {
        "mentors": ["Ada Lovelace", "Grace Hopper"],
        "key_people": ["Gur Sannikov"],
    }
    assert index.targets_for(augur_path, field="mentors") == ["Ada Lovelace", "Grace Hopper"]
    assert index.sources_for("Augur") == [vault / "notes" / "local-first.md"]


def test_relationship_index_uses_git_head_cache_key_when_vault_is_repo(tmp_path: Path) -> None:
    from src.lib.relationship_index import RelationshipIndex

    vault = tmp_path / "vault"
    write_frontmatter(vault / "note.md", {"related": "[[Target]]"}, "Body\n")
    subprocess.run(["git", "init", "-b", "main"], cwd=vault, check=True, capture_output=True)
    subprocess.run(["git", "add", "note.md"], cwd=vault, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Augur Test",
            "-c",
            "user.email=augur@example.test",
            "commit",
            "-m",
            "seed vault",
        ],
        cwd=vault,
        check=True,
        capture_output=True,
    )

    index = RelationshipIndex.build(vault)

    assert index.cache_key.startswith("git:")
