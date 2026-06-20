"""Tests for src/lib/index/watch_roots.py — registry-driven RAG watch roots."""

from __future__ import annotations


from src.lib.index.watch_roots import (
    WatchRoot,
    categorize_path,
    resolve_watch_roots,
)


class _FakeBrain:
    def __init__(self, data_root):
        self.data_root = data_root


class _FakeRegistry:
    def __init__(self, brains):
        self.brains = brains


def _make_brain_tree(tmp_path, name, with_wiki=True, with_capabilities_wiki=False):
    root = tmp_path / name
    (root / "notes").mkdir(parents=True)
    if with_wiki:
        (root / "wiki").mkdir()
    if with_capabilities_wiki:
        (root / "capabilities" / "wiki").mkdir(parents=True)
    return root


def test_resolves_vault_and_wiki_roots_per_brain(tmp_path):
    personal = _make_brain_tree(tmp_path, "Au-vault")
    project = _make_brain_tree(tmp_path, "project-brain", with_wiki=False, with_capabilities_wiki=True)
    registry = _FakeRegistry(
        {
            "personal": _FakeBrain(personal),
            "project-augur": _FakeBrain(project),
        }
    )
    docs = tmp_path / "documents"
    docs.mkdir()

    roots = resolve_watch_roots(registry=registry, document_dirs=[docs])

    paths = {(r.path, r.category) for r in roots}
    assert (personal, "vault") in paths
    assert (personal / "wiki", "wiki") in paths
    assert (project, "vault") in paths
    assert (project / "capabilities" / "wiki", "wiki") in paths
    assert (docs, "documents") in paths


def test_resolves_knowledge_layout_wiki_root(tmp_path):
    # A "knowledge"-layout brain (no BRAIN.yaml -> default) keeps its wiki under
    # knowledge/wiki/. resolve_watch_roots must register that as a wiki root so
    # those pages categorize as wiki, not vault. Regression for wiki pages
    # leaking into notes-scoped search.
    brain = tmp_path / "project-brain"
    knowledge_wiki = brain / "knowledge" / "wiki"
    knowledge_wiki.mkdir(parents=True)
    (brain / "knowledge" / "notes").mkdir(parents=True)
    registry = _FakeRegistry({"project-augur": _FakeBrain(brain)})

    roots = resolve_watch_roots(registry=registry, document_dirs=[])

    paths = {(r.path, r.category) for r in roots}
    assert (knowledge_wiki, "wiki") in paths
    assert (brain, "vault") in paths
    # A page under knowledge/wiki categorizes as wiki (longest-prefix), and a
    # note under knowledge/notes stays vault.
    from src.lib.index.watch_roots import categorize_path

    assert categorize_path(knowledge_wiki / "topic.md", roots) == "wiki"
    assert categorize_path(brain / "knowledge" / "notes" / "n.md", roots) == "vault"


def test_categorize_longest_prefix_wins(tmp_path):
    vault = _make_brain_tree(tmp_path, "Au-vault")
    roots = [
        WatchRoot(path=vault, category="vault"),
        WatchRoot(path=vault / "wiki", category="wiki"),
    ]
    assert categorize_path(vault / "notes" / "a.md", roots) == "vault"
    assert categorize_path(vault / "wiki" / "page.md", roots) == "wiki"
    assert categorize_path(tmp_path / "elsewhere" / "x.md", roots) is None


def test_categorize_filters_irrelevant_extensions(tmp_path):
    vault = _make_brain_tree(tmp_path, "Au-vault")
    docs = tmp_path / "docs"
    docs.mkdir()
    roots = [
        WatchRoot(path=vault, category="vault"),
        WatchRoot(path=docs, category="documents"),
    ]
    # .tmp / editor swap noise is ignored everywhere
    assert categorize_path(vault / "notes" / "a.tmp", roots) is None
    assert categorize_path(vault / "notes" / ".a.md.swp", roots) is None
    # binary docs count only under documents roots
    assert categorize_path(docs / "report.pdf", roots) == "documents"
    assert categorize_path(vault / "notes" / "report.pdf", roots) is None


def test_categorize_ignores_dot_prefixed_intermediate_dirs(tmp_path):
    vault = _make_brain_tree(tmp_path, "Au-vault")
    roots = [WatchRoot(path=vault, category="vault")]
    assert categorize_path(vault / ".obsidian" / "config.json", roots) is None
    assert categorize_path(vault / ".Trash" / "note.md", roots) is None


def test_categorize_documents_root_nested_in_vault_longest_prefix_wins(tmp_path):
    vault = _make_brain_tree(tmp_path, "Au-vault")
    nested_docs = vault / "attachments"
    nested_docs.mkdir()
    roots = [
        WatchRoot(path=vault, category="vault"),
        WatchRoot(path=nested_docs, category="documents"),
    ]
    assert categorize_path(nested_docs / "report.pdf", roots) == "documents"
    assert categorize_path(vault / "notes" / "a.md", roots) == "vault"


def test_skips_missing_brain_roots(tmp_path):
    registry = _FakeRegistry({"ghost": _FakeBrain(tmp_path / "does-not-exist")})
    roots = resolve_watch_roots(registry=registry, document_dirs=[])
    assert roots == []
