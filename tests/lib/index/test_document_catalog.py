from __future__ import annotations

from src.lib.index import document_catalog
from src.lib.index.document_catalog import (
    DocumentCatalogEntry,
    load_document_catalog,
    lookup_catalog_entry,
)


def test_load_document_catalog_reads_summary_body(tmp_path):
    project_root = tmp_path / "project"
    entry_path = project_root / "project-brain" / "knowledge" / "documents" / "project-y-drive" / "architecture.md"
    entry_path.parent.mkdir(parents=True)
    entry_path.write_text(
        "---\n"
        "remote_id: google-drive:file:def456\n"
        "canonical_document_id: project-y:architecture\n"
        "source_id: project-y-drive\n"
        "source_relative_path: folders/architecture.md\n"
        "provider: google-drive\n"
        "attached_brain_ids: project-y, personal, project-y\n"
        "title: Architecture Overview\n"
        "summary_status: auto\n"
        "summary_generated_from_revision: drive-revision-41\n"
        "remote_revision: drive-revision-42\n"
        "remote_modified_at: 2026-06-07T08:00:00Z\n"
        "---\n"
        "\n"
        "Short catalog summary.\n"
        "\n",
        encoding="utf-8",
    )

    catalog = load_document_catalog(project_root)

    expected = DocumentCatalogEntry(
        remote_id="google-drive:file:def456",
        canonical_document_id="project-y:architecture",
        source_id="project-y-drive",
        source_relative_path="folders/architecture.md",
        provider="google-drive",
        attached_brain_ids=("project-y", "personal"),
        title="Architecture Overview",
        summary="Short catalog summary.",
        summary_status="auto",
        summary_generated_from_revision="drive-revision-41",
        remote_revision="drive-revision-42",
        remote_modified_at="2026-06-07T08:00:00Z",
        path=entry_path,
    )
    assert catalog["google-drive:file:def456"] == expected
    assert catalog["project-y:architecture"] == expected
    assert catalog["source-path:project-y-drive:folders/architecture.md"] == expected


def test_lookup_catalog_entry_matches_remote_canonical_or_source_path(tmp_path):
    project_root = tmp_path / "project"
    entry_path = project_root / "project-brain" / "knowledge" / "documents" / "project-y-drive" / "deck.md"
    entry_path.parent.mkdir(parents=True)
    entry_path.write_text(
        "---\n"
        "remote_id: google-drive:file:deck\n"
        "canonical_document_id: project-y:deck\n"
        "source_id: project-y-drive\n"
        "source_relative_path: deck.md\n"
        "title: Investor Deck\n"
        "---\n"
        "Investor deck summary.\n",
        encoding="utf-8",
    )

    catalog = load_document_catalog(project_root)

    assert (
        lookup_catalog_entry(
            catalog,
            remote_id="google-drive:file:deck",
            canonical_document_id="",
            source_id="",
            source_relative_path="",
        )
        == catalog["google-drive:file:deck"]
    )
    assert (
        lookup_catalog_entry(
            catalog,
            remote_id="",
            canonical_document_id="project-y:deck",
            source_id="",
            source_relative_path="",
        )
        == catalog["project-y:deck"]
    )
    assert (
        lookup_catalog_entry(
            catalog,
            remote_id="",
            canonical_document_id="",
            source_id="project-y-drive",
            source_relative_path="deck.md",
        )
        == catalog["source-path:project-y-drive:deck.md"]
    )
    assert (
        lookup_catalog_entry(
            catalog,
            remote_id="",
            canonical_document_id="missing",
            source_id="project-y-drive",
            source_relative_path="missing.md",
        )
        is None
    )


def test_lookup_catalog_entry_preserves_loaded_remote_canonical_collision_priority(
    tmp_path,
):
    project_root = tmp_path / "project"
    catalog_root = project_root / "project-brain" / "knowledge" / "documents"
    catalog_root.mkdir(parents=True)
    remote_path = catalog_root / "a-remote.md"
    remote_path.write_text(
        "---\n"
        "remote_id: google-drive:file:shared\n"
        "canonical_document_id: project-y:remote-shared\n"
        "title: Remote Shared\n"
        "---\n"
        "Remote shared summary.\n",
        encoding="utf-8",
    )
    canonical_path = catalog_root / "b-canonical.md"
    canonical_path.write_text(
        "---\n"
        "canonical_document_id: google-drive:file:shared\n"
        "title: Canonical Shared\n"
        "---\n"
        "Canonical shared summary.\n",
        encoding="utf-8",
    )

    catalog = load_document_catalog(project_root)

    remote_match = lookup_catalog_entry(
        catalog,
        remote_id="google-drive:file:shared",
        canonical_document_id="google-drive:file:shared",
        source_id="",
        source_relative_path="",
    )
    canonical_match = lookup_catalog_entry(
        catalog,
        remote_id="",
        canonical_document_id="google-drive:file:shared",
        source_id="",
        source_relative_path="",
    )

    assert remote_match is not None
    assert remote_match.path == remote_path
    assert catalog["google-drive:file:shared"].path == remote_path
    assert canonical_match is not None
    assert canonical_match.path == canonical_path


def test_load_document_catalog_returns_empty_when_catalog_root_is_missing(tmp_path):
    assert load_document_catalog(tmp_path / "project") == {}


def test_load_document_catalog_skips_malformed_and_unkeyed_markdown(tmp_path):
    catalog_root = tmp_path / "project" / "project-brain" / "knowledge" / "documents"
    catalog_root.mkdir(parents=True)
    (catalog_root / "malformed.md").write_text(
        "---\n" "remote_id: [unterminated\n" "---\n" "Malformed summary.\n",
        encoding="utf-8",
    )
    (catalog_root / "unkeyed.md").write_text(
        "---\n" "title: No Lookup Keys\n" "---\n" "No useful identity.\n",
        encoding="utf-8",
    )

    assert load_document_catalog(tmp_path / "project") == {}


def test_load_document_catalog_skips_parse_exception_and_loads_valid_file(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    catalog_root = project_root / "project-brain" / "knowledge" / "documents"
    catalog_root.mkdir(parents=True)
    broken_path = catalog_root / "broken.md"
    broken_path.write_text(
        "---\n"
        "remote_id: google-drive:file:broken\n"
        "title: Broken Catalog Entry\n"
        "---\n"
        "This entry should be skipped when parsing fails.\n",
        encoding="utf-8",
    )
    valid_path = catalog_root / "valid.md"
    valid_path.write_text(
        "---\n"
        "remote_id: google-drive:file:valid\n"
        "title: Valid Catalog Entry\n"
        "---\n"
        "This entry should still load.\n",
        encoding="utf-8",
    )
    original_parse_frontmatter = document_catalog.parse_frontmatter

    def fail_for_broken_file(path):
        if path == broken_path:
            raise RuntimeError("simulated catalog read failure")
        return original_parse_frontmatter(path)

    monkeypatch.setattr(document_catalog, "parse_frontmatter", fail_for_broken_file)

    catalog = load_document_catalog(project_root)

    assert set(catalog) == {"google-drive:file:valid"}
    assert catalog["google-drive:file:valid"].path == valid_path
    assert catalog["google-drive:file:valid"].summary == "This entry should still load."


def test_lookup_catalog_entry_prefers_remote_then_canonical_then_source_path(
    tmp_path,
):
    remote_entry = _catalog_entry(tmp_path, "remote", remote_id="google-drive:file:remote")
    canonical_entry = _catalog_entry(
        tmp_path,
        "canonical",
        canonical_document_id="project-y:canonical",
    )
    source_entry = _catalog_entry(
        tmp_path,
        "source",
        source_id="project-y-drive",
        source_relative_path="reports/source.md",
    )
    catalog = {
        "google-drive:file:remote": remote_entry,
        "project-y:canonical": canonical_entry,
        "source-path:project-y-drive:reports/source.md": source_entry,
    }

    assert (
        lookup_catalog_entry(
            catalog,
            remote_id="google-drive:file:remote",
            canonical_document_id="project-y:canonical",
            source_id="project-y-drive",
            source_relative_path="reports/source.md",
        )
        is remote_entry
    )
    assert (
        lookup_catalog_entry(
            catalog,
            remote_id="",
            canonical_document_id="project-y:canonical",
            source_id="project-y-drive",
            source_relative_path="reports/source.md",
        )
        is canonical_entry
    )


def test_load_document_catalog_uses_title_fallback_from_file_stem(tmp_path):
    project_root = tmp_path / "project"
    entry_path = project_root / "project-brain" / "knowledge" / "documents" / "project-y-drive" / "strategy-roadmap.md"
    entry_path.parent.mkdir(parents=True)
    entry_path.write_text(
        "---\n"
        "source_id: project-y-drive\n"
        "source_relative_path: strategy-roadmap.md\n"
        "---\n"
        "Roadmap summary.\n",
        encoding="utf-8",
    )

    catalog = load_document_catalog(project_root)

    assert catalog["source-path:project-y-drive:strategy-roadmap.md"].title == "Strategy Roadmap"


def _catalog_entry(
    tmp_path,
    name: str,
    *,
    remote_id: str = "",
    canonical_document_id: str = "",
    source_id: str = "",
    source_relative_path: str = "",
) -> DocumentCatalogEntry:
    return DocumentCatalogEntry(
        remote_id=remote_id,
        canonical_document_id=canonical_document_id,
        source_id=source_id,
        source_relative_path=source_relative_path,
        provider="",
        attached_brain_ids=(),
        title=name.title(),
        summary=f"{name} summary",
        summary_status="",
        summary_generated_from_revision="",
        remote_revision="",
        remote_modified_at="",
        path=tmp_path / f"{name}.md",
    )
