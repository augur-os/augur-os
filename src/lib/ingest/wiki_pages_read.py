"""Read-only accessor for wiki pages (shared primitive for non-wiki skills).

Provides ``get_wiki_pages()`` — a lazy-initialized ``WikiPages`` instance
built from configured paths. Skills that need read-only access to wiki
pages (e.g. to call ``.read_tags()``) should use this accessor instead of
importing from the wiki skill bundle directly (which would be a
cross-bundle import forbidden by ADR-14 / rule 4).

The wiki engine (``WikiPages`` class) lives in the wiki skill; this
accessor merely holds a cached reference and wires it to the configured
paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

_wiki_pages: Any = None


def get_wiki_pages() -> Any:
    """Return a cached ``WikiPages`` instance wired to the configured wiki paths.

    Lazy-initialised on first call. Requires the wiki skill to be installed
    (project-brain on sys.path).

    Returns:
        A ``skills.wiki.scripts.wiki_pages.WikiPages`` instance.
    """
    global _wiki_pages
    if _wiki_pages is None:
        from skills.wiki.scripts.wiki_pages import WikiPages
        from src.config.paths import get_compiled_wiki_dir, get_runtime_dir, resolve_wiki_dir

        runtime_wiki = get_runtime_dir() / "wiki"
        wiki_dir = get_compiled_wiki_dir(resolve_wiki_dir())
        _wiki_pages = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki)
    return _wiki_pages


def reset_wiki_pages_cache() -> None:
    """Clear the cached WikiPages instance (for testing)."""
    global _wiki_pages
    _wiki_pages = None
