"""
Tests for UnifiedSearcher — single entry point for cross-scope knowledge search.

Module: skills/knowledge/scripts/mcp/memory/unified_search.py
"""

import os
from unittest.mock import patch

import pytest

from src.lib.frontmatter_utils import write_frontmatter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_paths(tmp_path):
    """Patch path helpers to use tmp_path."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()

    patches = [
        patch(
            "src.lib.knowledge.unified_search.get_memory_dir",
            return_value=memory_dir,
        ),
        patch(
            "src.lib.knowledge.unified_search.get_project_root",
            return_value=project_root,
        ),
        patch(
            "src.lib.knowledge.unified_search.get_rag_dir",
            return_value=rag_dir,
        ),
        patch(
            "src.lib.knowledge.unified_search.get_own_data_dir",
            side_effect=ValueError("not configured"),
        ),
        patch(
            "src.lib.adr_utils.get_adr_dir",
            return_value=adr_dir,
        ),
    ]
    for p in patches:
        p.start()
    yield {
        "memory_dir": memory_dir,
        "project_root": project_root,
        "rag_dir": rag_dir,
        "adr_dir": adr_dir,
    }
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# Scope validation
# ---------------------------------------------------------------------------


def test_read_frontmatter_refreshes_when_file_mtime_changes(tmp_path):
    from src.lib.knowledge import unified_search

    card = tmp_path / "workflow.md"
    card.write_text("---\ntitle: Demo 01\n---\n\nBody\n", encoding="utf-8")
    os.utime(card, ns=(1, 1))

    assert unified_search._read_frontmatter(str(card))["title"] == "Demo 01"

    card.write_text("---\ntitle: Workflow Example 01\n---\n\nBody\n", encoding="utf-8")
    os.utime(card, ns=(2, 2))

    assert unified_search._read_frontmatter(str(card))["title"] == "Workflow Example 01"


class TestUnifiedSearcherInit:
    """Tests for UnifiedSearcher initialization and scope validation."""

    def test_default_scopes_include_all(self, mock_paths):
        from src.lib.knowledge.unified_search import (
            VALID_SCOPES,
            UnifiedSearcher,
        )

        searcher = UnifiedSearcher()
        assert set(searcher._default_scopes) == VALID_SCOPES

    def test_custom_scopes_accepted(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        searcher = UnifiedSearcher(scopes=["memory", "skills"])
        assert set(searcher._default_scopes) == {"memory", "skills"}

    def test_invalid_scope_raises_value_error(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        with pytest.raises(ValueError, match="Invalid scope"):
            UnifiedSearcher(scopes=["memory", "nonexistent"])

    def test_empty_scope_list_accepted(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        searcher = UnifiedSearcher(scopes=[])
        assert searcher._default_scopes == []


# ---------------------------------------------------------------------------
# Scope path resolution
# ---------------------------------------------------------------------------


class TestScopePaths:
    """Tests for _get_scope_paths returning correct directories per scope."""

    def test_memory_scope_returns_memory_dir(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        searcher = UnifiedSearcher(scopes=["memory"])
        paths = searcher._get_scope_paths("memory")
        assert paths == [mock_paths["memory_dir"]]

    def test_memory_scope_empty_when_missing(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        mock_paths["memory_dir"].rmdir()
        searcher = UnifiedSearcher(scopes=["memory"])
        paths = searcher._get_scope_paths("memory")
        assert paths == []

    def test_decisions_scope_resolves_to_docs_dir(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        searcher = UnifiedSearcher(scopes=["decisions"])
        paths = searcher._get_scope_paths("decisions")
        assert paths == [mock_paths["adr_dir"]]

    def test_skills_scope_finds_skill_md_parents(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        skills_dir = mock_paths["project_root"] / "project-brain" / "capabilities" / "skills"
        skill_dir = skills_dir / "knowledge"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Knowledge Skill\n")

        searcher = UnifiedSearcher(scopes=["skills"])
        paths = searcher._get_scope_paths("skills")
        assert len(paths) == 1
        assert paths[0] == skill_dir


# ---------------------------------------------------------------------------
# Search delegation
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for the search() method delegating to RAG iterative_search."""

    def test_search_returns_empty_when_rag_unavailable(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        searcher = UnifiedSearcher(scopes=["memory"])
        with patch(
            "src.lib.knowledge.unified_search.UnifiedSearcher.search",
            wraps=searcher.search,
        ):
            results = searcher.search("test query")
        # With RAG import failing, results should be empty list
        assert isinstance(results, list)

    def test_search_invalid_scope_in_call_raises(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        searcher = UnifiedSearcher(scopes=["memory"])
        with pytest.raises(ValueError, match="Invalid scope"):
            searcher.search("test", scopes=["bogus_scope"])

    def test_search_uses_uncapped_candidate_pool_for_budgeted_query(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        searcher = UnifiedSearcher(scopes=["memory"])
        with patch(
            "src.lib.knowledge.unified_search.rag_iterative_search",
            return_value=[
                {
                    "type": "hybrid",
                    "hits": [
                        {
                            "file": "memory/MEMORY.md",
                            "content": "budgeted",
                            "score": 0.1,
                            "budget": "tokenmax",
                            "provenance": ["ripgrep"],
                        }
                    ],
                }
            ],
        ) as rag_search:
            results = searcher.search("test", budget="tokenmax")

        rag_search.assert_called_with(
            "test",
            [mock_paths["memory_dir"]],
            [],
            [],
            top_k=50,
            budget=None,
            include_stale_documents=False,
        )
        assert results[0]["budget"] == "tokenmax"
        assert results[0]["provenance"] == ["ripgrep"]

    def test_budget_limits_results_across_scopes(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        skills_dir = mock_paths["project_root"] / "project-brain" / "capabilities" / "skills" / "knowledge"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("# Knowledge\n", encoding="utf-8")

        def fake_rag_search(
            query,
            source_dirs,
            priority_dirs,
            rag_dirs,
            *,
            top_k,
            budget,
            include_stale_documents,
        ):
            del include_stale_documents
            return [
                {
                    "type": "hybrid",
                    "hits": [
                        {
                            "file": f"{source_dirs or rag_dirs}-{index}",
                            "content": "hit",
                            "score": 0.1,
                            "budget": budget,
                            "provenance": ["ripgrep"],
                        }
                        for index in range(top_k)
                    ],
                }
            ]

        searcher = UnifiedSearcher(scopes=["memory", "skills"])
        with patch(
            "src.lib.knowledge.unified_search.rag_iterative_search",
            side_effect=fake_rag_search,
        ):
            results = searcher.search("test", budget="conservative")

        assert len(results) == 5
        assert all(result["budget"] is None for result in results)

    def test_current_work_query_ranks_recent_rag_document_before_old_memory(
        self,
        mock_paths,
    ):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        memory_file = mock_paths["memory_dir"] / "old-pitch-slide.md"
        memory_file.write_text(
            "pitch slide notes from an older investor draft\n",
            encoding="utf-8",
        )
        old_time = 1_700_000_000
        os.utime(memory_file, (old_time, old_time))

        for index in range(60):
            noise_doc = (
                mock_paths["rag_dir"]
                / "documents"
                / "career"
                / f"old-working-pitch-slide-{index:03}.md"
            )
            noise_doc.parent.mkdir(parents=True, exist_ok=True)
            noise_doc.write_text(
                "---\n"
                f"name: old-working-pitch-slide-{index:03}\n"
                "modified: '2024-01-01T00:00:00+00:00'\n"
                "---\n"
                "pitch slide working archive\n",
                encoding="utf-8",
            )

        rag_doc = (
            mock_paths["rag_dir"]
            / "documents"
            / "venture-augur"
            / "IntelSubmit"
            / "augur-angel-deck-v20.md"
        )
        rag_doc.parent.mkdir(parents=True)
        rag_doc.write_text(
            "---\n"
            "name: augur-angel-deck-v20\n"
            "source_path: /tmp/augur-angel-deck-v20.pptx\n"
            "modified: '2026-05-18T06:59:20+00:00'\n"
            "document_title: augur-angel-deck-v20\n"
            "---\n"
            "pitch slide current working deck\n",
            encoding="utf-8",
        )

        searcher = UnifiedSearcher(scopes=["memory", "rag"])
        results = searcher.search("pitch slide I am working on", top_k=2)

        assert results
        assert "augur-angel-deck-v20" in results[0]["file"]
        assert not any("/_meta/" in result["file"] for result in results)

    def test_current_work_query_filters_source_changed_recent_rag_documents(
        self,
        mock_paths,
    ):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        documents_dir = mock_paths["rag_dir"] / "documents" / "venture-augur"
        stale_doc = documents_dir / "stale-deck.md"
        fresh_doc = documents_dir / "fresh-deck.md"
        for path, index_status, title in (
            (stale_doc, "source_changed", "Stale Deck"),
            (fresh_doc, "synced", "Fresh Deck"),
        ):
            write_frontmatter(
                path,
                {
                    "name": title,
                    "document_title": title,
                    "index_status": index_status,
                },
                "pitch slide current working deck\n",
            )

        searcher = UnifiedSearcher(scopes=["rag"])
        with patch(
            "src.lib.knowledge.unified_search.rag_iterative_search",
            return_value=[],
        ):
            results = searcher.search("pitch slide I am working on", top_k=10)

        result_files = [result["file"] for result in results]
        assert str(fresh_doc) in result_files
        assert str(stale_doc) not in result_files

    def test_current_work_query_can_include_source_changed_recent_rag_documents(
        self,
        mock_paths,
    ):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        stale_doc = (
            mock_paths["rag_dir"]
            / "documents"
            / "venture-augur"
            / "stale-deck.md"
        )
        write_frontmatter(
            stale_doc,
            {
                "name": "Stale Deck",
                "document_title": "Stale Deck",
                "index_status": "source_changed",
            },
            "pitch slide current working deck\n",
        )

        searcher = UnifiedSearcher(scopes=["rag"])
        with patch(
            "src.lib.knowledge.unified_search.rag_iterative_search",
            return_value=[],
        ):
            results = searcher.search(
                "pitch slide I am working on",
                top_k=10,
                include_stale_documents=True,
            )

        stale_hit = next(
            result for result in results if result["file"] == str(stale_doc)
        )
        assert stale_hit["index_status"] == "source_changed"
        assert stale_hit["stale_source_warning"] == "source_changed"

    def test_exact_rag_index_filename_match_beats_weak_content_hits(self, mock_paths):
        from src.lib.knowledge.unified_search import UnifiedSearcher

        query = "2026-06-01-offload-demo-short-20260602T072136Z.md"
        source_path = (
            mock_paths["project_root"]
            / "vault"
            / "notes"
            / "examples"
            / "transcripts"
            / query
        )
        source_path.parent.mkdir(parents=True)
        source_path.write_text("real transcript body", encoding="utf-8")

        index_entry = (
            mock_paths["rag_dir"]
            / "vault"
            / "notes"
            / "private"
            / "examples"
            / "transcripts"
            / query
        )
        write_frontmatter(
            index_entry,
            {
                "id": "vault:private:notes/examples/transcripts/2026-06-01-offload-demo-short-20260602T072136Z",
                "type": "vault",
                "name": "2026-06-01-offload-demo-short-20260602T072136Z",
                "title": "Offload Workflow Example Offline Transcript",
                "description": "New workflow example transcript",
                "source_path": str(source_path),
                "modified": "2026-06-02T07:21:36+00:00",
                "indexed_at": "2026-06-02T07:21:38+00:00",
                "format": "md",
            },
            "",
        )

        def fake_rag_search(
            query,
            source_dirs,
            priority_dirs,
            rag_dirs,
            *,
            top_k,
            budget,
            include_stale_documents,
        ):
            del (
                query,
                source_dirs,
                priority_dirs,
                rag_dirs,
                top_k,
                budget,
                include_stale_documents,
            )
            return [
                {
                    "type": "hybrid",
                    "hits": [
                        {
                            "file": str(
                                mock_paths["project_root"]
                                / "vault"
                                / "sources"
                                / "extracted"
                                / f"2026-06-01-demo-hard-photo-{index}.extracted.md"
                            ),
                            "content": "Due Date: 2026-05-20",
                            "score": 0.02,
                            "provenance": ["ripgrep"],
                        }
                        for index in range(10)
                    ],
                }
            ]

        searcher = UnifiedSearcher(scopes=["rag"])
        with patch("src.lib.knowledge.unified_search.rag_iterative_search", side_effect=fake_rag_search):
            results = searcher.search(query, top_k=10, budget="balanced")

        assert results
        assert results[0]["source_path"] == str(source_path)
        assert results[0]["provenance"] == ["browse-index"]
        assert "hard-photo" not in results[0]["file"]

    def test_exact_rag_index_lookup_skips_generic_word_queries(self, mock_paths):
        from src.lib.knowledge.unified_search import _exact_rag_index_hits

        index_entry = mock_paths["rag_dir"] / "documents" / "deck.md"
        write_frontmatter(
            index_entry,
            {
                "type": "vault",
                "name": "deck",
                "title": "Investor deck",
                "source_path": "/tmp/deck.md",
            },
            "",
        )

        assert _exact_rag_index_hits("deck", mock_paths["rag_dir"]) == []


# ---------------------------------------------------------------------------
# Per-tab category scoping (Browse semantic search)
# ---------------------------------------------------------------------------


def _category_roots(tmp_path):
    """Build WatchRoots: a vault (with wiki) and a documents dir."""
    from src.lib.index.watch_roots import WatchRoot

    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    docs = tmp_path / "docs"
    docs.mkdir()
    return vault, docs, [
        WatchRoot(path=vault, category="vault"),
        WatchRoot(path=vault / "wiki", category="wiki"),
        WatchRoot(path=docs, category="documents"),
    ]


class TestHitBrowseCategory:
    """_hit_browse_category maps a hit to its Browse category by source path."""

    def test_document_path_maps_to_documents(self, tmp_path):
        from src.lib.knowledge.unified_search import _hit_browse_category

        _vault, docs, roots = _category_roots(tmp_path)
        hit = {"source_path": str(docs / "career" / "Star Dashboard.docx")}
        assert _hit_browse_category(hit, roots) == "documents"

    def test_vault_note_maps_to_vault(self, tmp_path):
        from src.lib.knowledge.unified_search import _hit_browse_category

        vault, _docs, roots = _category_roots(tmp_path)
        hit = {"source_path": str(vault / "notes" / "thought.md")}
        assert _hit_browse_category(hit, roots) == "vault"

    def test_wiki_page_maps_to_wiki(self, tmp_path):
        from src.lib.knowledge.unified_search import _hit_browse_category

        vault, _docs, roots = _category_roots(tmp_path)
        hit = {"source_path": str(vault / "wiki" / "topic.md")}
        assert _hit_browse_category(hit, roots) == "wiki"

    def test_metadata_source_path_is_used(self, tmp_path):
        from src.lib.knowledge.unified_search import _hit_browse_category

        _vault, docs, roots = _category_roots(tmp_path)
        hit = {"metadata": {"source_path": str(docs / "deck.pdf")}}
        assert _hit_browse_category(hit, roots) == "documents"

    def test_skills_scope_fallback(self, tmp_path):
        from src.lib.knowledge.unified_search import _hit_browse_category

        _vault, _docs, roots = _category_roots(tmp_path)
        hit = {"scope": "skills", "file": "/elsewhere/SKILL.md"}
        assert _hit_browse_category(hit, roots) == "skills"

    def test_decisions_scope_maps_to_adrs(self, tmp_path):
        from src.lib.knowledge.unified_search import _hit_browse_category

        _vault, _docs, roots = _category_roots(tmp_path)
        hit = {"scope": "decisions", "file": "/adrs/ADR-001.md"}
        assert _hit_browse_category(hit, roots) == "adrs"

    def test_unknown_path_maps_to_none(self, tmp_path):
        from src.lib.knowledge.unified_search import _hit_browse_category

        _vault, _docs, roots = _category_roots(tmp_path)
        hit = {"source_path": "/totally/unrelated/file.txt"}
        assert _hit_browse_category(hit, roots) is None

    def test_rag_chunk_document_path_maps_to_documents(self, tmp_path):
        # Real search hits often carry the rag chunk path, not the source file.
        from src.lib.knowledge.unified_search import _hit_browse_category

        _vault, _docs, roots = _category_roots(tmp_path)
        hit = {
            "scope": "rag",
            "source_path": "chunks/documents/career/Interview/Star Dashboard/x_77.md",
        }
        assert _hit_browse_category(hit, roots) == "documents"

    def test_graph_entity_token_maps_to_none(self, tmp_path):
        from src.lib.knowledge.unified_search import _hit_browse_category

        _vault, _docs, roots = _category_roots(tmp_path)
        hit = {"scope": "rag", "source_path": "the-startupists-guide-to-the-galaxy"}
        assert _hit_browse_category(hit, roots) is None


class TestSearchCategoryScope:
    """search(category=...) restricts results to the active Browse category."""

    def test_category_filters_out_other_categories(self, mock_paths, tmp_path):
        from src.lib.knowledge.unified_search import UnifiedSearcher
        from src.lib.index.watch_roots import WatchRoot

        vault = tmp_path / "vault"
        vault.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        roots = [
            WatchRoot(path=vault, category="vault"),
            WatchRoot(path=docs, category="documents"),
        ]

        doc_path = str(docs / "career" / "Star Dashboard.docx")
        note_path = str(vault / "notes" / "star-thoughts.md")

        def fake_rag_search(query, source_dirs, priority_dirs, rag_dirs, **kwargs):
            return [
                {
                    "hits": [
                        {"file": doc_path, "source_path": doc_path,
                         "content": "STAR Dashboard", "score": 0.9},
                        {"file": note_path, "source_path": note_path,
                         "content": "star thoughts", "score": 0.8},
                    ]
                }
            ]

        searcher = UnifiedSearcher(scopes=["rag"])
        with patch(
            "src.lib.knowledge.unified_search.rag_iterative_search",
            side_effect=fake_rag_search,
        ), patch(
            "src.lib.index.watch_roots.resolve_watch_roots",
            return_value=roots,
        ):
            doc_results = searcher.search("star", scopes=["rag"], category="documents")
            all_results = searcher.search("star", scopes=["rag"])

        doc_paths = {r.get("source_path") for r in doc_results}
        assert doc_path in doc_paths
        assert note_path not in doc_paths
        # Without a category, both categories come back.
        assert {r.get("source_path") for r in all_results} >= {doc_path, note_path}
