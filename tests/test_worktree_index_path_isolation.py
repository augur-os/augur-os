"""Worktree index path-isolation regression tests.

The RAG index is machine-shared across checkouts/worktrees (ADR-270/759), so
in-repo ``source_path`` values must be stored project-root-relative (POSIX) and
resolved against the ACTIVE project root at read time. External paths (private
vault, logs) stay absolute. File-action helpers must also support Windows.

Covers the worktree Browse file-action bug: a worktree dashboard was served
main-checkout absolute paths that its MCP refused.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --------------------------------------------------------------------------- #
#  Writers store relative source_path for in-repo, absolute for external       #
# --------------------------------------------------------------------------- #


def test_index_wiki_stores_relative_source_path_for_in_repo(tmp_path):
    from src.lib.index.unified_indexer import index_wiki

    tmp = tmp_path.resolve()
    root = tmp / "repo"
    shared_wiki = root / "project-brain" / "knowledge" / "wiki"
    shared_wiki.mkdir(parents=True)
    (shared_wiki / "page.md").write_text("---\ntitle: Page\n---\n\nBody text.\n")
    rag_dir = tmp / "rag"

    count = index_wiki(tmp / "absent_private", rag_dir, shared_wiki_dir=shared_wiki, root=root)

    assert count == 1
    entry = (rag_dir / "wiki" / "shared" / "page.md").read_text()
    # POSIX, project-root-relative — resolves from any checkout.
    assert "source_path: project-brain/knowledge/wiki/page.md" in entry


def test_index_wiki_keeps_external_source_path_absolute(tmp_path):
    from src.lib.index.unified_indexer import index_wiki

    tmp = tmp_path.resolve()
    root = tmp / "repo"
    root.mkdir()
    private_wiki = tmp / "external_vault" / "wiki"
    private_wiki.mkdir(parents=True)
    (private_wiki / "note.md").write_text("---\ntitle: Note\n---\n\nBody.\n")
    rag_dir = tmp / "rag"

    index_wiki(private_wiki, rag_dir, root=root)

    entry = (rag_dir / "wiki" / "private" / "note.md").read_text()
    # Not under the project root → stored absolute (already checkout-agnostic).
    assert f"source_path: {(private_wiki / 'note.md').as_posix()}" in entry


def test_index_vault_stores_relative_source_path_for_in_repo(tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index.unified_indexer import index_vault

    tmp = tmp_path.resolve()
    root = tmp / "repo"
    shared_vault = root / "project-brain"
    private_vault = tmp / "private-vault"
    (shared_vault / "notes" / "career").mkdir(parents=True)
    (private_vault / "notes").mkdir(parents=True)
    (shared_vault / "notes" / "career" / "strategy.md").write_text(
        "---\ntitle: Team Strategy\n---\nShared plan\n", encoding="utf-8"
    )
    rag_dir = tmp / "rag"

    index_vault(private_vault, rag_dir, shared_vault_dir=shared_vault, root=root)

    entries = [parse_frontmatter(p)[0] for p in (rag_dir / "vault").rglob("*.md")]
    shared = [e for e in entries if e.get("vault_scope") == "shared"]
    assert shared, "expected a shared vault entry"
    assert any(e.get("source_path") == "project-brain/notes/career/strategy.md" for e in shared)


# --------------------------------------------------------------------------- #
#  Read-time resolution against the active project root                         #
# --------------------------------------------------------------------------- #


def test_source_path_for_output_resolves_relative_under_active_root(monkeypatch, tmp_path):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index
    from src.mcp.augur_framework.tools.infrastructure.browse import index_resolve

    root = tmp_path.resolve() / "wt"
    target = root / "project-brain" / "knowledge" / "wiki" / "README.md"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    monkeypatch.setattr(browse_index, "get_project_root", lambda: root)
    monkeypatch.setattr(index_resolve, "get_project_root", lambda: root)

    out = browse_index._source_path_for_output("wiki", {"source_path": "project-brain/knowledge/wiki/README.md"})
    assert out == str(target)


def test_source_path_for_output_passes_through_external_and_urls(monkeypatch, tmp_path):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    monkeypatch.setattr(browse_index, "get_project_root", lambda: tmp_path.resolve())

    external = "/Users/someone/Projects/Au-vault/wiki/active-projects.md"
    assert browse_index._source_path_for_output("wiki", {"source_path": external}) == external

    url = "https://example.com/page"
    assert browse_index._source_path_for_output("wiki", {"source_path": url}) == url


def test_source_path_for_output_rejects_traversal(monkeypatch, tmp_path):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    monkeypatch.setattr(browse_index, "get_project_root", lambda: tmp_path.resolve())
    sneaky = "../../etc/passwd"
    # Traversal is not resolved; returned unchanged (never escapes the root).
    assert browse_index._source_path_for_output("wiki", {"source_path": sneaky}) == sneaky


# --------------------------------------------------------------------------- #
#  Cross-platform file actions (macOS / Windows / Linux)                        #
# --------------------------------------------------------------------------- #


def test_reveal_in_finder_windows_uses_explorer_select(monkeypatch, tmp_path):
    from src.mcp.augur_framework.tools.infrastructure.browse import file_actions

    f = tmp_path / "x.md"
    f.write_text("x")
    monkeypatch.setattr(file_actions, "_is_path_allowed", lambda p: True)
    monkeypatch.setattr(file_actions.platform, "system", lambda: "Windows")
    calls: list = []
    monkeypatch.setattr(file_actions.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    res = json.loads(asyncio.run(file_actions.reveal_in_finder_impl(str(f))))

    assert res["success"] is True
    argv, kwargs = calls[0]
    assert argv[0][0] == "explorer"
    assert argv[0][1].startswith("/select,")
    # explorer.exe exits non-zero even on success, so check must be disabled.
    assert kwargs.get("check") is False


def test_open_file_windows_uses_startfile(monkeypatch, tmp_path):
    from src.mcp.augur_framework.tools.infrastructure.browse import file_actions

    f = tmp_path / "x.md"
    f.write_text("x")
    monkeypatch.setattr(file_actions, "_is_path_allowed", lambda p: True)
    monkeypatch.setattr(file_actions.platform, "system", lambda: "Windows")
    started: list = []
    # os.startfile only exists on Windows; add it for the test (raising=False).
    monkeypatch.setattr(file_actions.os, "startfile", lambda p: started.append(p), raising=False)

    res = json.loads(asyncio.run(file_actions.open_file_impl(str(f))))

    assert res["success"] is True
    assert started == [str(f.resolve())]


def test_reveal_in_finder_macos_uses_open_dash_r(monkeypatch, tmp_path):
    from src.mcp.augur_framework.tools.infrastructure.browse import file_actions

    f = tmp_path / "x.md"
    f.write_text("x")
    monkeypatch.setattr(file_actions, "_is_path_allowed", lambda p: True)
    monkeypatch.setattr(file_actions.platform, "system", lambda: "Darwin")
    calls: list = []
    monkeypatch.setattr(file_actions.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    res = json.loads(asyncio.run(file_actions.reveal_in_finder_impl(str(f))))

    assert res["success"] is True
    assert calls[0][0][0][:2] == ["open", "-R"]
