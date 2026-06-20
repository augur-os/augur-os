"""Browse-index scanner metadata coverage (ADR-792 / browse demo bugs).

Verifies that the vault scanner persists each note's frontmatter ``title`` and
``tags`` (with a humanized slug title fallback) and that the ADR scanner writes
a ``title`` and never falls back to the bare slug as a description.

The real ``index_vault`` / ``index_adrs`` signatures write frontmatter entries
to disk (they return an int count, not a list), so this test reads the written
entries back via ``parse_frontmatter``.
"""

from pathlib import Path


from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.index._scanners_knowledge import index_adrs
from src.lib.index._scanners_structural import index_vault


def _read_entries(category_dir: Path) -> list[dict]:
    entries: list[dict] = []
    for entry_file in sorted(category_dir.rglob("*.md")):
        meta, _ = parse_frontmatter(entry_file)
        entries.append(meta)
    return entries


def test_vault_entry_carries_frontmatter_title_and_tags(tmp_path: Path):
    # index_vault(vault_dir, rag_dir, *, shared_vault_dir=None, root=None) -> int
    # It writes entries to rag_dir/vault/... and returns a count.
    vault_dir = tmp_path / "vault"
    notes = vault_dir / "notes"
    notes.mkdir(parents=True)
    (notes / "2026-05-30-demo-invoice-2.md").write_text(
        "---\ntitle: demo-invoice\nx-augur-note-type: file\ntags:\n- inbox\n- finance\n---\nbody\n"
    )
    rag_dir = tmp_path / "rag"

    count = index_vault(vault_dir, rag_dir, root=tmp_path)
    assert count >= 1

    entries = _read_entries(rag_dir / "vault")
    e = next(x for x in entries if x.get("name") == "2026-05-30-demo-invoice-2")

    assert e.get("title") == "demo-invoice"
    tags = e.get("metadata", {}).get("tags") or e.get("tags") or []
    assert "finance" in tags


def test_vault_entry_falls_back_to_humanized_slug_title(tmp_path: Path):
    vault_dir = tmp_path / "vault"
    notes = vault_dir / "notes"
    notes.mkdir(parents=True)
    # No frontmatter title -> humanized slug: the leading date is stripped but
    # "demo" is a topic (not a capture modality) so it is kept.
    (notes / "2026-05-30-demo-invoice-2.md").write_text("---\nx-augur-note-type: file\n---\nbody\n")
    rag_dir = tmp_path / "rag"

    index_vault(vault_dir, rag_dir, root=tmp_path)
    entries = _read_entries(rag_dir / "vault")
    e = next(x for x in entries if x.get("name") == "2026-05-30-demo-invoice-2")

    assert e.get("title") == "Demo Invoice 2"


def test_adr_entry_carries_title_and_no_slug_description(tmp_path: Path, monkeypatch):
    # index_adrs(root, rag_dir) -> int; reads via get_adr_dir()/scan_adrs().
    import src.lib.adr_utils as adr_utils

    decisions_dir = tmp_path / "adrs"
    decisions_dir.mkdir()

    monkeypatch.setattr(adr_utils, "get_adr_dir", lambda: decisions_dir)
    monkeypatch.setattr(
        adr_utils,
        "scan_adrs",
        lambda decisions_dir, **kwargs: [
            {
                "number": 792,
                "filename": "ADR-792-routines-goal-command.md",
                "title": "Routines goal command",
                "description": "",  # empty -> must NOT fall back to slug
                "status": "Accepted",
                "date": "2026-05-30",
                "hub": "dev",
                "tags": ["routines"],
                "related": [],
                "path": "",
                "archived": False,
            }
        ],
    )

    rag_dir = tmp_path / "rag"
    count = index_adrs(tmp_path, rag_dir)
    assert count == 1

    entries = _read_entries(rag_dir / "adrs")
    e = next(x for x in entries if x.get("name") == "ADR-792-routines-goal-command")

    # Title comes from frontmatter title.
    assert e.get("title") == "Routines goal command"
    # Description must never be the bare slug.
    assert e.get("description") != "ADR-792-routines-goal-command"


def test_adr_title_falls_back_to_humanized_slug(tmp_path: Path, monkeypatch):
    import src.lib.adr_utils as adr_utils

    decisions_dir = tmp_path / "adrs"
    decisions_dir.mkdir()

    monkeypatch.setattr(adr_utils, "get_adr_dir", lambda: decisions_dir)
    monkeypatch.setattr(
        adr_utils,
        "scan_adrs",
        lambda decisions_dir, **kwargs: [
            {
                "number": 100,
                "filename": "ADR-100-some-decision.md",
                "title": "",  # no title -> humanized slug
                "description": "A real decision summary",
                "status": "Implemented",
                "date": "2026-01-01",
                "hub": "dev",
                "tags": [],
                "related": [],
                "path": "",
                "archived": False,
            }
        ],
    )

    rag_dir = tmp_path / "rag"
    index_adrs(tmp_path, rag_dir)
    entries = _read_entries(rag_dir / "adrs")
    e = next(x for x in entries if x.get("name") == "ADR-100-some-decision")

    assert e.get("title") == "Adr 100 Some Decision"


# ---------------------------------------------------------------------------
# Memory-entry indexing (ADR-811 follow-up, rule 32)
# ---------------------------------------------------------------------------


def test_private_vault_memory_entry_indexed_with_memory_tag(tmp_path: Path):
    """Memory entries from the private vault (Au-vault/memory/entries/) ride the
    vault category and receive a 'memory' tag so Browse cards show the badge."""
    vault_dir = tmp_path / "vault"
    entries_dir = vault_dir / "memory" / "entries"
    entries_dir.mkdir(parents=True)
    (entries_dir / "sdlc-autonomy-aug-dev-build.md").write_text(
        "---\n"
        "title: sdlc-autonomy-aug-dev-build\n"
        "description: post-spec SDLC autonomy and aug dev build engine (ADR-810)\n"
        "brain_scope: project\n"
        "type: project\n"
        "status: active\n"
        "---\n"
        "Body text describing the SDLC autonomy pattern.\n"
    )
    rag_dir = tmp_path / "rag"

    count = index_vault(vault_dir, rag_dir, root=tmp_path)
    assert count >= 1

    entries = _read_entries(rag_dir / "vault")
    e = next(
        (x for x in entries if x.get("name") == "sdlc-autonomy-aug-dev-build"),
        None,
    )
    assert e is not None, "memory entry not indexed"
    assert e.get("title") == "sdlc-autonomy-aug-dev-build"
    assert e.get("description") == "post-spec SDLC autonomy and aug dev build engine (ADR-810)"
    tags = e.get("tags") or []
    assert "memory" in tags
    assert e.get("journey_category") == "memory"


def test_shared_brain_memory_entry_indexed_with_memory_tag(tmp_path: Path):
    """Memory entries from the project-brain (knowledge/memory/entries/) ride the
    vault category at shared scope and receive a 'memory' tag."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True)
    shared_vault_dir = tmp_path / "project-brain"
    entries_dir = shared_vault_dir / "knowledge" / "memory" / "entries"
    entries_dir.mkdir(parents=True)
    (entries_dir / "browse-pages-progressive-render-shipped.md").write_text(
        "---\n"
        "title: browse-pages-progressive-render-shipped\n"
        "description: Browse pages tab progressive render shipped (2026-06-11)\n"
        "brain_scope: project\n"
        "type: project\n"
        "status: active\n"
        "---\n"
        "Body text about the progressive render.\n"
    )
    rag_dir = tmp_path / "rag"

    count = index_vault(vault_dir, rag_dir, shared_vault_dir=shared_vault_dir, root=tmp_path)
    assert count >= 1

    entries = _read_entries(rag_dir / "vault")
    e = next(
        (x for x in entries if x.get("name") == "browse-pages-progressive-render-shipped"),
        None,
    )
    assert e is not None, "shared-scope memory entry not indexed"
    assert e.get("title") == "browse-pages-progressive-render-shipped"
    assert e.get("description") == "Browse pages tab progressive render shipped (2026-06-11)"
    tags = e.get("tags") or []
    assert "memory" in tags


def test_memory_index_files_are_skipped(tmp_path: Path):
    """README.md and MEMORY.md in the memory directory are regenerated metadata
    files — they must not appear as Browse cards."""
    vault_dir = tmp_path / "vault"
    entries_dir = vault_dir / "memory" / "entries"
    entries_dir.mkdir(parents=True)
    (vault_dir / "memory" / "README.md").write_text("---\ntitle: README\n---\nIndex.\n")
    (vault_dir / "memory" / "MEMORY.md").write_text("---\ntitle: MEMORY\n---\nSummary.\n")
    (entries_dir / "real-entry.md").write_text("---\ntitle: Real Entry\ndescription: a real memory card\n---\nBody.\n")
    rag_dir = tmp_path / "rag"

    index_vault(vault_dir, rag_dir, root=tmp_path)

    entries = _read_entries(rag_dir / "vault")
    names = {e.get("name") for e in entries}
    assert "real-entry" in names
    assert "README" not in names
    assert "MEMORY" not in names
