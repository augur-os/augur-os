"""Derive RAG watch roots from the brain registry and map paths to categories.

A brain has the same shape wherever it lives (spec 2026-06-10): its root
indexes as the `vault` category and its wiki dir (either `<root>/wiki` for
personal brains or `<root>/capabilities/wiki` for project brains) as `wiki`.
Document source roots index as `documents`. Longest-prefix match decides the
category for a changed path, so wiki-under-vault resolves correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.lib.brain_layout import brain_wiki_dir, is_machine_path
from src.lib.index.document_sources import INDEXABLE_EXTENSIONS

# Source extensions the index scanners actually consume. Vault/wiki stay
# text-only; "documents" uses the canonical set the documents scanner
# consumes (should_index_source_file in document_sources.py).
TEXT_EXTENSIONS = {".md", ".yaml", ".yml", ".json", ".txt", ".csv"}
_EXTENSIONS_BY_CATEGORY = {
    "vault": TEXT_EXTENSIONS,
    "wiki": TEXT_EXTENSIONS,
    "documents": INDEXABLE_EXTENSIONS,
}
# Dot-prefixed parts (.git, .obsidian, .Trash, swap files, ...) are ignored
# via a startswith(".") check on root-relative parts, matching
# document_sources.py; this set covers the non-dot noise dirs.
_IGNORED_PARTS = {"node_modules", "__pycache__"}


@dataclass(frozen=True)
class WatchRoot:
    path: Path
    category: str  # "vault" | "wiki" | "documents"


def resolve_watch_roots(
    *,
    registry: Any = None,
    document_dirs: Iterable[Path] | None = None,
) -> list[WatchRoot]:
    """Build the watch-root list. Both inputs are injectable for tests.

    Defaults: registry from src.lib.brain_registry.get_registry(); document
    dirs from configured document sources (which include the documents dir,
    desktop, downloads, and any config/documents/sources.yaml entries).
    """
    if registry is None:
        from src.lib.brain_registry import get_registry

        registry = get_registry()
    if document_dirs is None:
        document_dirs = _default_document_dirs()

    roots: list[WatchRoot] = []
    for brain in registry.brains.values():
        data_root = Path(brain.data_root).resolve()
        if not data_root.is_dir():
            continue
        roots.append(WatchRoot(path=data_root, category="vault"))
        # brain_wiki_dir() resolves the layout-correct wiki location: wiki/ for
        # the "domains" layout (Au-vault) and knowledge/wiki/ for the "knowledge"
        # layout (project-brain). Hardcoding data_root/wiki missed the latter,
        # so knowledge-layout wiki pages categorized as "vault" — leaking into
        # notes-scoped search and dropping out of wiki-scoped search.
        wiki_candidates = (
            brain_wiki_dir(data_root),
            data_root / "wiki",
            data_root / "capabilities" / "wiki",
        )
        for wiki_candidate in wiki_candidates:
            if wiki_candidate.is_dir():
                roots.append(WatchRoot(path=wiki_candidate, category="wiki"))

    for doc_dir in document_dirs:
        doc_dir = Path(doc_dir)
        if doc_dir.is_dir():
            roots.append(WatchRoot(path=doc_dir, category="documents"))

    # Dedupe, keep stable order.
    seen: set[tuple[str, str]] = set()
    unique: list[WatchRoot] = []
    for root in roots:
        key = (str(root.path), root.category)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _default_document_dirs() -> list[Path]:
    from src.config.paths import get_documents_dir, get_project_root
    from src.lib.index.document_source_config import configured_document_sources

    sources = configured_document_sources(project_root=get_project_root(), documents_dir=get_documents_dir())
    return [source.resolved_path for source in sources]


def categorize_path(path: Path, roots: list[WatchRoot]) -> str | None:
    """Map a changed file path to its index category, or None to ignore."""
    best: WatchRoot | None = None
    best_depth = -1
    relative_parts: tuple[str, ...] = ()
    for root in roots:
        try:
            candidate_parts = path.relative_to(root.path).parts
        except ValueError:
            continue
        depth = len(root.path.parts)
        if depth > best_depth:
            best = root
            best_depth = depth
            relative_parts = candidate_parts
    if best is None:
        return None
    if any(part.startswith(".") or part in _IGNORED_PARTS for part in relative_parts):
        return None
    if path.suffix.lower() not in _EXTENSIONS_BY_CATEGORY[best.category]:
        return None
    return best.category


def _is_prompt_card(path: Path) -> bool:
    """True when a vault .md carries x-augur-note-type: prompt (best-effort)."""
    if path.suffix.lower() != ".md":
        return False
    try:
        from src.lib.frontmatter_utils import parse_frontmatter

        meta, _ = parse_frontmatter(path)
    except Exception:
        return False
    return str(meta.get("x-augur-note-type") or "").strip() == "prompt"


def categories_for_path(path: Path, roots: list[WatchRoot]) -> set[str]:
    """All Browse categories a changed path feeds (possibly empty).

    Single source of truth shared by the watcher and the per-action refresh
    helper. Builds on categorize_path() (longest-prefix base category) and adds
    "prompts" when a vault .md is a triggerable prompt card. Machine paths,
    symlinks, ignored dirs, and non-indexable extensions yield an empty set.
    """
    base = categorize_path(path, roots)
    if base is None:
        return set()
    # Exclude machine paths (_augur/, brain-contract files) for vault content;
    # categorize_path already drops dot-prefixed and node_modules/__pycache__.
    if base == "vault":
        for root in roots:
            if root.category != "vault":
                continue
            try:
                path.relative_to(root.path)
            except ValueError:
                continue
            if is_machine_path(root.path, path):
                return set()
            break
    cats = {base}
    if base == "vault" and _is_prompt_card(path):
        cats.add("prompts")
    return cats
