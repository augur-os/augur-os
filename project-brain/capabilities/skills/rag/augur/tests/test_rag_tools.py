"""
Tests for the rag MCP wrapper plus its underlying search library helpers.

Library helpers (parse_ripgrep_hit, _to_rg_pattern, _score_hits, _dedup_by_file,
_collect_rg_hits) live in src/lib/index/unified_search.py — extracted from
rag_tools.py on 2026-04-30 to retire the last architecture-test allowlist
entry. MCP-tool-specific helpers (_count_status, register_tools) remain in
skills/rag/scripts/mcp/rag_tools.py.
"""

import asyncio
import json


class _FakeMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str, annotations=None):  # noqa: ANN001
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


def _identity(fn):
    return fn


# ---------------------------------------------------------------------------
# parse_ripgrep_hit
# ---------------------------------------------------------------------------


class TestParseRipgrepHit:
    """Tests for parse_ripgrep_hit splitting rg output into structured dicts."""

    def test_standard_three_part_hit(self):
        from src.lib.index.unified_search import parse_ripgrep_hit

        result = parse_ripgrep_hit("/path/to/file.md:42:This is the matching line")
        assert result["file"] == "/path/to/file.md"
        assert result["line"] == "42"
        assert result["content"] == "This is the matching line"

    def test_chunk_path_adds_parent_document(self):
        from src.lib.index.unified_search import parse_ripgrep_hit

        result = parse_ripgrep_hit("/rag/index/chunks/doc_chunk_0.md:10:chunk content")
        assert result["file"] == "/rag/index/chunks/doc_chunk_0.md"
        assert "parent_document" in result

    def test_malformed_line_returns_raw(self):
        from src.lib.index.unified_search import parse_ripgrep_hit

        result = parse_ripgrep_hit("just-a-string-without-colons")
        assert "raw" in result
        assert result["raw"] == "just-a-string-without-colons"

    def test_content_with_colons_preserved(self):
        from src.lib.index.unified_search import parse_ripgrep_hit

        result = parse_ripgrep_hit("/f.md:1:key: value: nested")
        assert result["content"] == "key: value: nested"


# ---------------------------------------------------------------------------
# _to_rg_pattern
# ---------------------------------------------------------------------------


class TestToRgPattern:
    """Tests for _to_rg_pattern converting queries to ripgrep regex."""

    def test_single_word_escaped(self):
        from src.lib.index.unified_search import _to_rg_pattern

        result = _to_rg_pattern("hello")
        assert result == "hello"

    def test_multi_word_becomes_alternation(self):
        from src.lib.index.unified_search import _to_rg_pattern

        result = _to_rg_pattern("hello world")
        assert result == "hello|world"

    def test_punctuation_tokenizes_into_alternation(self):
        from src.lib.index.unified_search import _to_rg_pattern

        # _to_rg_pattern tokenizes queries on non-alphanumeric characters and
        # OR-joins the alphanumeric tokens (commit fe2457e1b), so "file.txt"
        # becomes the alternation "file|txt" rather than a single escaped token.
        result = _to_rg_pattern("file.txt")
        assert result == "file|txt"

    def test_empty_query(self):
        from src.lib.index.unified_search import _to_rg_pattern

        result = _to_rg_pattern("")
        assert result == ""


# ---------------------------------------------------------------------------
# _score_hits
# ---------------------------------------------------------------------------


class TestScoreHits:
    """Tests for _score_hits ranking results by word match count."""

    def test_higher_match_count_first(self):
        from src.lib.index.unified_search import _score_hits

        hits = [
            {"file": "a.md", "content": "hello"},
            {"file": "b.md", "content": "hello world"},
        ]
        scored = _score_hits(hits, ["hello", "world"])
        assert scored[0]["file"] == "b.md"  # Matches both words

    def test_single_word_no_reorder(self):
        from src.lib.index.unified_search import _score_hits

        hits = [
            {"file": "a.md", "content": "first"},
            {"file": "b.md", "content": "second"},
        ]
        scored = _score_hits(hits, ["first"])
        # Single word query should return hits as-is
        assert scored == hits


# ---------------------------------------------------------------------------
# _dedup_by_file
# ---------------------------------------------------------------------------


class TestDedupByFile:
    """Tests for _dedup_by_file removing duplicate file paths."""

    def test_removes_duplicate_files(self):
        from src.lib.index.unified_search import _dedup_by_file

        hits = [
            {"file": "a.md", "content": "line 1"},
            {"file": "a.md", "content": "line 2"},
            {"file": "b.md", "content": "line 3"},
        ]
        deduped = _dedup_by_file(hits)
        assert len(deduped) == 2
        files = [h["file"] for h in deduped]
        assert files == ["a.md", "b.md"]

    def test_preserves_first_occurrence(self):
        from src.lib.index.unified_search import _dedup_by_file

        hits = [
            {"file": "x.md", "content": "first"},
            {"file": "x.md", "content": "second"},
        ]
        deduped = _dedup_by_file(hits)
        assert deduped[0]["content"] == "first"

    def test_empty_input(self):
        from src.lib.index.unified_search import _dedup_by_file

        assert _dedup_by_file([]) == []

    def test_hits_without_file_key(self):
        from src.lib.index.unified_search import _dedup_by_file

        hits = [
            {"raw": "no file field"},
            {"raw": "another raw"},
        ]
        # Hits without file key have empty string path, which is falsy
        # so they are skipped by the dedup filter
        deduped = _dedup_by_file(hits)
        assert len(deduped) == 0


# ---------------------------------------------------------------------------
# _count_status
# ---------------------------------------------------------------------------


class TestCountStatus:
    """Tests for _count_status aggregating RAG directory contents."""

    def test_counts_chunks_and_symbols(self, tmp_path):
        from plugins.ai.skills.rag.scripts.mcp.rag_tools import _count_status

        rag_dir = tmp_path / "rag"
        chunks_dir = rag_dir / "chunks"
        chunks_dir.mkdir(parents=True)
        (chunks_dir / "doc_chunk_0.md").write_text("chunk")
        (chunks_dir / "doc_chunk_1.md").write_text("chunk")
        (rag_dir / "symbols.yaml").write_text("file: []\n")

        status = _count_status([rag_dir])
        assert status["chunks"] == 2
        assert status["symbols"] == 1
        assert str(rag_dir) in status["rag_paths"]

    def test_missing_dir_returns_zeros(self, tmp_path):
        from plugins.ai.skills.rag.scripts.mcp.rag_tools import _count_status

        status = _count_status([tmp_path / "nonexistent"])
        assert status["chunks"] == 0
        assert status["symbols"] == 0
        assert status["rag_paths"] == []


class TestWikiReindexTools:
    # NOTE: `wiki-status` was relocated from rag to ingest (Phase 0 v3 Task 4).
    # See skills/ingest/augur/tests/test_wiki_tools.py::test_registers_wiki_status_tool_from_shared_status_helper
    # for the canonical coverage of that tool.

    def test_rag_reindex_wiki_category_drops_legacy_wiki_compile_metadata(self, monkeypatch, tmp_path):
        from plugins.ai.skills.rag.scripts.mcp import rag_tools
        from src.lib.frontmatter_utils import parse_frontmatter

        wiki_dir = tmp_path / "wiki"
        rag_dir = tmp_path / "rag"
        (wiki_dir / "dev").mkdir(parents=True, exist_ok=True)
        wiki_file = wiki_dir / "dev" / "architecture.md"
        wiki_file.write_text(
            "---\ntitle: Architecture\ntype: wiki-page\nhub: dev\n---\n# Architecture\n\nCompiled knowledge v2.\n",
            encoding="utf-8",
        )
        (rag_dir / "wiki" / "dev").mkdir(parents=True, exist_ok=True)
        (rag_dir / "wiki" / "dev" / "architecture.md").write_text(
            "---\n"
            "type: wiki\n"
            "hub: dev\n"
            "name: dev/architecture\n"
            f"source_path: {wiki_file}\n"
            "checksum: old-checksum\n"
            "wiki_compile_status: compiled\n"
            "wiki_compiled_checksum: old-checksum\n"
            "wiki_compiled_at: 2026-04-14T09:00:00+00:00\n"
            "wiki_targets:\n"
            "  - dev/architecture\n"
            "---\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(rag_tools, "get_compiled_wiki_dir", lambda runtime_wiki_dir=None: wiki_dir)
        monkeypatch.setattr(rag_tools, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(rag_tools, "get_rag_dir", lambda: rag_dir)
        monkeypatch.setattr(rag_tools, "get_vault_dir", lambda: tmp_path / "vault")
        monkeypatch.setattr(rag_tools, "get_documents_dir", lambda: tmp_path / "documents")

        fake_mcp = _FakeMCP()
        rag_tools.register_tools(fake_mcp, _identity, None)

        payload = json.loads(asyncio.run(fake_mcp.tools["rag-reindex"](category="wiki")))

        assert payload["status"] == "ok"
        assert payload["category"] == "wiki"
        assert payload["mode"] == "index-only"
        assert payload["count"] == 1
        meta, _ = parse_frontmatter(rag_dir / "wiki" / "private" / "dev" / "architecture.md")
        assert meta["checksum"] != "old-checksum"
        assert "wiki_compile_status" not in meta
        assert "wiki_compiled_checksum" not in meta
        assert "wiki_compiled_at" not in meta
        assert "wiki_targets" not in meta

    def test_rag_reindex_documents_drops_legacy_wiki_compile_metadata(self, monkeypatch, tmp_path):
        from plugins.ai.skills.rag.scripts.mcp import rag_tools
        from src.lib.index import unified_indexer
        from src.lib.frontmatter_utils import parse_frontmatter

        documents_dir = tmp_path / "documents"
        (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
        source_file = documents_dir / "brain" / "live.md"
        source_file.write_text("# Live\n\n" + ("content " * 60), encoding="utf-8")

        rag_dir = tmp_path / "rag"
        entry = rag_dir / "documents" / "brain" / "live.md"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text(
            "---\n"
            f"source_path: {source_file.resolve()}\n"
            "type: document\n"
            "wiki_compile_status: compiled\n"
            "wiki_compiled_checksum: old-checksum\n"
            "wiki_compiled_at: 2026-04-14T09:00:00+00:00\n"
            "wiki_targets:\n"
            "  - brain/live\n"
            "---\n"
            "old body\n",
            encoding="utf-8",
        )

        def _fake_extract(path):  # noqa: ANN001
            return {
                "format": "md",
                "size_bytes": len(path.read_bytes()),
                "created": "2026-04-14T10:00:00+00:00",
                "body": "fresh body",
            }

        monkeypatch.setattr(unified_indexer, "_extract_document", _fake_extract)
        monkeypatch.setattr(rag_tools, "get_documents_dir", lambda: documents_dir)
        monkeypatch.setattr(rag_tools, "get_rag_dir", lambda: rag_dir)

        fake_mcp = _FakeMCP()
        rag_tools.register_tools(fake_mcp, _identity, None)

        payload = json.loads(asyncio.run(fake_mcp.tools["rag-reindex"](category="documents")))

        assert payload["status"] == "ok"
        assert payload["category"] == "documents"
        assert payload["count"] == 1
        meta, _ = parse_frontmatter(entry)
        assert "wiki_compile_status" not in meta
        assert "wiki_compiled_checksum" not in meta
        assert "wiki_compiled_at" not in meta
        assert "wiki_targets" not in meta

    def test_wiki_reindex_indexes_existing_pages_without_seeding(self, monkeypatch, tmp_path):
        from plugins.ai.skills.rag.scripts.mcp import rag_tools
        from src.lib.frontmatter_utils import parse_frontmatter

        wiki_dir = tmp_path / "wiki"
        rag_dir = tmp_path / "rag"
        (wiki_dir / "dev").mkdir(parents=True, exist_ok=True)
        wiki_file = wiki_dir / "dev" / "architecture.md"
        wiki_file.write_text(
            "---\ntitle: Architecture\ntype: wiki-page\nhub: dev\n---\n# Architecture\n\nCompiled knowledge v2.\n",
            encoding="utf-8",
        )
        (rag_dir / "wiki" / "dev").mkdir(parents=True, exist_ok=True)
        (rag_dir / "wiki" / "dev" / "architecture.md").write_text(
            "---\n"
            "type: wiki\n"
            "hub: dev\n"
            "name: dev/architecture\n"
            f"source_path: {wiki_file}\n"
            "checksum: old-checksum\n"
            "wiki_compile_status: compiled\n"
            "wiki_compiled_checksum: old-checksum\n"
            "wiki_compiled_at: 2026-04-14T09:00:00+00:00\n"
            "wiki_targets:\n"
            "  - dev/architecture\n"
            "---\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(rag_tools, "get_compiled_wiki_dir", lambda runtime_wiki_dir=None: wiki_dir)
        monkeypatch.setattr(rag_tools, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(rag_tools, "get_rag_dir", lambda: rag_dir)

        fake_mcp = _FakeMCP()
        rag_tools.register_tools(fake_mcp, _identity, None)

        payload = json.loads(asyncio.run(fake_mcp.tools["wiki-reindex"]()))

        assert payload["status"] == "ok"
        assert payload["mode"] == "index-only"
        assert payload["indexed"] == 1
        assert payload["wiki_dir"] == str(wiki_dir)
        meta, _ = parse_frontmatter(rag_dir / "wiki" / "private" / "dev" / "architecture.md")
        assert meta["checksum"] != "old-checksum"
        assert "wiki_compile_status" not in meta
        assert "wiki_compiled_checksum" not in meta
        assert "wiki_compiled_at" not in meta
        assert "wiki_targets" not in meta
