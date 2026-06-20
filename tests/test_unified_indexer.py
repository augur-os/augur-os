"""Auto-generated importability test for unified_indexer."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_unified_indexer_importable():
    """Verify that unified_indexer can be imported without errors."""
    import src.lib.index.unified_indexer

    assert src.lib.index.unified_indexer is not None


def test_mcp_tools_indexer_scans_nested_skill_mcp_packages(tmp_path):
    """Nested skill-owned MCP packages should appear in Browse's MCP Tools category."""
    from src.lib.index._scanners_structural import index_mcp_tools

    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "daemon"
    nested_mcp = skill_dir / "scripts" / "job_ledger" / "mcp"
    nested_mcp.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" "name: daemon\n" "description: Daemon skill\n" "x-augur-hub: command\n" "---\n" "# Daemon\n",
        encoding="utf-8",
    )
    (nested_mcp / "__init__.py").write_text(
        "def register_tools(mcp, interceptor, metrics):\n"
        "    @mcp.tool(name=\"jobs-list\")\n"
        "    async def jobs_list_tool():\n"
        "        \"\"\"List ledger jobs with current state.\"\"\"\n"
        "        return \"[]\"\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    count = index_mcp_tools(tmp_path, rag_dir)

    assert count == 1
    indexed = rag_dir / "mcp-tools" / "jobs-list.md"
    assert indexed.exists()
    assert "scripts/job_ledger/mcp/__init__.py" in indexed.read_text(encoding="utf-8")


def test_logs_indexer_exposes_runtime_job_ledger_card(tmp_path, monkeypatch):
    """Runtime job files should surface as one Browse Logs inspector card."""
    from src.lib.index import _scanners_structural as scanners

    logs_dir = tmp_path / "logs"
    runtime_dir = tmp_path / "runtime"
    job_dir = runtime_dir / "jobs" / "20260514-134333-476-000-adr-743-smoke"
    job_dir.mkdir(parents=True)
    logs_dir.mkdir()
    (job_dir / "meta.json").write_text(
        '{"job_id": "20260514-134333-476-000-adr-743-smoke", "loop_name": "adr-743-smoke"}\n',
        encoding="utf-8",
    )
    (job_dir / "events.jsonl").write_text(
        '{"state": "pending"}\n' '{"state": "running", "phase": "smoke"}\n' '{"state": "complete", "phase": "smoke"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(scanners, "get_logs_dir", lambda: logs_dir)
    monkeypatch.setattr(scanners, "get_runtime_dir", lambda: runtime_dir)

    rag_dir = tmp_path / "rag"
    count = scanners.index_logs(tmp_path, rag_dir)

    assert count == 1
    indexed = rag_dir / "logs" / "job-ledger.md"
    content = indexed.read_text(encoding="utf-8")
    assert "type: job-ledger" in content
    assert "hub: command" in content
    assert "jobs_root_path:" in content
    assert "latest_job_id: 20260514-134333-476-000-adr-743-smoke" in content
    assert "state_counts: complete:1" in content


def test_index_pages_ingests_sidecar_backed_artifacts(tmp_path):
    """Sidecar-backed HTML artifacts land in the pages category; orphan HTML is skipped."""
    from src.lib.index._scanners_structural import index_pages
    from src.lib.artifacts_sidecar import Sidecar, write_sidecar
    from src.lib.frontmatter_utils import parse_frontmatter

    root = tmp_path / "project"
    root.mkdir()
    rag_dir = tmp_path / "rag"
    docs_dir = tmp_path / "docs"

    # Sidecar-backed artifact → must be indexed
    artifact_dir = docs_dir / "dev" / "artifacts"
    artifact_dir.mkdir(parents=True)
    html = artifact_dir / "memory-architecture.html"
    html.write_text("<html><title>Memory Architecture</title></html>", encoding="utf-8")
    write_sidecar(
        artifact_dir / "memory-architecture.meta.yaml",
        Sidecar(
            slug="memory-architecture",
            title="Memory Architecture",
            kind="generated",
            hub="dev",
            tags=["memory"],
            created_at="2026-06-01T00:00:00Z",
            promoted_at="2026-06-01T00:00:00Z",
        ),
    )
    # Orphan HTML (no sidecar) → must NOT be indexed
    (artifact_dir / "orphan.html").write_text("<html></html>", encoding="utf-8")

    count = index_pages(root, rag_dir, documents_dir=docs_dir)

    assert count == 1
    entry_path = rag_dir / "pages" / "dev" / "artifact--memory-architecture.md"
    assert entry_path.exists()
    meta, _ = parse_frontmatter(entry_path)
    assert meta["type"] == "page"
    assert meta["kind"] == "generated"
    assert meta["slug"] == "memory-architecture"
    assert meta["title"] == "Memory Architecture"
    assert meta["url"] == "/artifact/memory-architecture"
    assert meta["hub"] == "dev"
    assert meta["tags"] == ["memory"]
    assert meta["path"] == str(html)


def test_index_pages_artifact_kind_and_hub_fallbacks(tmp_path):
    """A sidecar with empty kind/hub falls back to kind='saved', hub='uncategorized'."""
    from src.lib.index._scanners_structural import index_pages
    from src.lib.artifacts_sidecar import Sidecar, write_sidecar
    from src.lib.frontmatter_utils import parse_frontmatter

    root = tmp_path / "project"
    root.mkdir()
    rag_dir = tmp_path / "rag"
    docs_dir = tmp_path / "docs"

    artifact_dir = docs_dir / "artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "untyped.html").write_text("<html></html>", encoding="utf-8")
    write_sidecar(
        artifact_dir / "untyped.meta.yaml",
        Sidecar(slug="untyped", title="Untyped", kind="", hub=""),
    )

    count = index_pages(root, rag_dir, documents_dir=docs_dir)

    assert count == 1
    entry_path = rag_dir / "pages" / "uncategorized" / "artifact--untyped.md"
    assert entry_path.exists()
    meta, _ = parse_frontmatter(entry_path)
    assert meta["kind"] == "saved"
    assert meta["hub"] == "uncategorized"


def test_index_pages_without_documents_dir_still_works(tmp_path):
    """documents_dir pointing nowhere plus an empty project must not raise (artifact pass is optional)."""
    from src.lib.index._scanners_structural import index_pages

    root = tmp_path / "project"
    root.mkdir()
    rag_dir = tmp_path / "rag"

    count = index_pages(root, rag_dir, documents_dir=tmp_path / "missing")
    assert count == 0
