from pathlib import Path

from src.lib.index import unified_search


def test_active_search_excludes_vault_drafts_archive_and_legacy_drafts(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    documents = tmp_path / "documents"
    files = {
        vault / "notes/active.md": "needle active note\n",
        vault / "drafts/staging/draft.md": "needle draft\n",
        vault / "archive/career/old.md": "needle archived\n",
        vault / "_drafts/staging/legacy.md": "needle legacy draft\n",
        vault / "notes/project/drafts/active.md": "needle nested vault draft\n",
        vault / "notes/project/archive/active.md": "needle nested vault archive\n",
        documents / "drafts/client/proposal.md": "needle document draft\n",
        documents / "archive/research/old.md": "needle document archive\n",
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True)
        path.write_text(content, encoding="utf-8")

    hits = unified_search._collect_active_search_hits(
        "needle",
        [vault, documents],
        max_hits=20,
        vault_dir=vault,
    )
    hit_files = {Path(hit["file"]).relative_to(tmp_path).as_posix() for hit in hits}

    assert "vault/notes/active.md" in hit_files
    assert "vault/drafts/staging/draft.md" not in hit_files
    assert "vault/archive/career/old.md" not in hit_files
    assert "vault/_drafts/staging/legacy.md" not in hit_files
    assert "vault/notes/project/drafts/active.md" in hit_files
    assert "vault/notes/project/archive/active.md" in hit_files
    assert "documents/drafts/client/proposal.md" in hit_files
    assert "documents/archive/research/old.md" in hit_files


def test_fallback_fulltext_excludes_inactive_generated_vault_entries(tmp_path: Path) -> None:
    source = tmp_path / "source"
    rag = tmp_path / "rag"
    files = {
        rag / "vault/drafts/staging/draft.md": "fallbackneedle generated draft\n",
        rag / "vault/archive/career/old.md": "fallbackneedle generated archive\n",
        rag / "vault/_drafts/staging/legacy.md": "fallbackneedle generated legacy draft\n",
        rag / "vault/notes/project/drafts/active.md": "fallbackneedle generated nested draft\n",
        rag / "vault/notes/project/archive/active.md": "fallbackneedle generated nested archive\n",
        rag / "documents/archive/research.md": "fallbackneedle generated document archive\n",
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True)
        path.write_text(content, encoding="utf-8")
    source.mkdir()

    results = unified_search._raw_iterative_search("fallbackneedle", [source], [], [rag])
    hits = [hit for group in results for hit in group["hits"]]
    hit_files = {Path(hit["file"]).relative_to(tmp_path).as_posix() for hit in hits}

    assert "rag/vault/drafts/staging/draft.md" not in hit_files
    assert "rag/vault/archive/career/old.md" not in hit_files
    assert "rag/vault/_drafts/staging/legacy.md" not in hit_files
    assert "rag/vault/notes/project/drafts/active.md" in hit_files
    assert "rag/vault/notes/project/archive/active.md" in hit_files
    assert "rag/documents/archive/research.md" in hit_files


def test_fallback_fulltext_prefilters_inactive_generated_vault_entries_before_hit_cap(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    rag = tmp_path / "rag"
    source.mkdir()
    rag.mkdir()

    inactive_hits = [
        {
            "file": str(rag / "vault" / "drafts" / "bulk" / f"{index:03}.md"),
            "line": "1",
            "content": "capneedle inactive generated draft",
        }
        for index in range(120)
    ]
    active_hits = [
        {
            "file": str(rag / "vault" / "notes" / "project" / "drafts" / "active.md"),
            "line": "1",
            "content": "capneedle active generated content",
        },
        {
            "file": str(rag / "documents" / "archive" / "research.md"),
            "line": "1",
            "content": "capneedle active generated content",
        },
    ]

    def fake_collect_rg_hits(pattern, globs, directories, max_hits=100):
        if directories != [rag] or pattern != "capneedle":
            return []
        if "symbols.yaml" in globs or "*_index.md" in globs or "index.md" in globs:
            return []
        if "!vault/drafts/**" in globs:
            return active_hits[:max_hits]
        return inactive_hits[:max_hits]

    monkeypatch.setattr(unified_search, "_collect_rg_hits", fake_collect_rg_hits)

    results = unified_search._raw_iterative_search("capneedle", [source], [], [rag])
    hits = [hit for group in results for hit in group["hits"]]
    hit_files = {Path(hit["file"]).relative_to(tmp_path).as_posix() for hit in hits}

    assert not any(path.startswith("rag/vault/drafts/bulk/") for path in hit_files)
    assert "rag/vault/notes/project/drafts/active.md" in hit_files
    assert "rag/documents/archive/research.md" in hit_files


def test_symbol_and_index_search_exclude_inactive_generated_vault_entries(tmp_path: Path) -> None:
    source = tmp_path / "source"
    rag = tmp_path / "rag"
    files = {
        rag / "vault/drafts/staging/index.md": "phaseleak inactive draft index\n",
        rag / "vault/archive/old/index.md": "phaseleak inactive archive index\n",
        rag / "vault/_drafts/staging/symbols.yaml": "phaseleak inactive legacy symbols\n",
        rag / "vault/notes/project/drafts/index.md": "phaseleak active nested index\n",
        rag / "documents/archive/index.md": "phaseleak active document index\n",
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    source.mkdir()

    results = unified_search._raw_iterative_search("phaseleak", [source], [], [rag])
    hits = [hit for group in results for hit in group["hits"]]
    hit_files = {Path(hit["file"]).relative_to(tmp_path).as_posix() for hit in hits}

    assert "rag/vault/drafts/staging/index.md" not in hit_files
    assert "rag/vault/archive/old/index.md" not in hit_files
    assert "rag/vault/_drafts/staging/symbols.yaml" not in hit_files
    assert "rag/vault/notes/project/drafts/index.md" in hit_files
    assert "rag/documents/archive/index.md" in hit_files


def test_active_search_excludes_rag_internal_meta_before_hit_cap(tmp_path: Path) -> None:
    rag = tmp_path / "rag"
    files = {
        rag / "_meta" / "bm25_chunk_map.json": "augur angel deck v20 " * 20,
        rag / "_meta" / "checksums" / "documents.yaml": "augur angel deck v20 checksum\n",
        rag
        / "documents"
        / "venture-augur"
        / "augur-angel-deck-v20.md": (
            "---\n" "name: augur-angel-deck-v20\n" "---\n" "Augur angel deck v20 slide content\n"
        ),
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    hits = unified_search._collect_active_search_hits(
        "augur|angel|deck|v20",
        [rag],
        max_hits=2,
        rag_dirs=[rag],
    )
    hit_files = {Path(hit["file"]).relative_to(tmp_path).as_posix() for hit in hits}

    assert "rag/documents/venture-augur/augur-angel-deck-v20.md" in hit_files
    assert not any(path.startswith("rag/_meta/") for path in hit_files)
