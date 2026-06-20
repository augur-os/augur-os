"""The documents indexer must skip the docs-store _augur/ machine area
(evals, reports, migration manifests) — indexing it pollutes retrieval
(2026-06-12 reorg verification finding)."""

from src.lib.index.unified_indexer import index_documents


def test_documents_indexer_skips_machine_area(tmp_path):
    docs = tmp_path / "docs"
    (docs / "career" / "cv").mkdir(parents=True)
    (docs / "career" / "cv" / "resume.md").write_text("# resume", encoding="utf-8")
    (docs / "_augur" / "evals").mkdir(parents=True)
    (docs / "_augur" / "evals" / "report.md").write_text("# machine", encoding="utf-8")
    (docs / "_augur" / "migration-before.json").write_text("{}", encoding="utf-8")
    rag = tmp_path / "rag"
    rag.mkdir()

    index_documents(docs, rag)

    indexed = {str(p.relative_to(rag)) for p in rag.rglob("*.md")}
    assert any("resume" in p for p in indexed), indexed
    assert not any("_augur" in p for p in indexed), indexed
