"""Unit tests for src.lib.ingest.wiki_pages_read.

This module is a thin lazy-init accessor around the wiki skill's
``WikiPages`` class plus a cache-reset hook. The only logic that can be
exercised without the wiki skill bundle installed is the module-level
cache: the cache-hit short-circuit in ``get_wiki_pages`` and the reset.
We drive the real module-level ``_wiki_pages`` global to assert that
behavior, restoring it afterward so test isolation is preserved.
"""

from __future__ import annotations

import src.lib.ingest.wiki_pages_read as wiki_pages_read
from src.lib.ingest.wiki_pages_read import get_wiki_pages, reset_wiki_pages_cache


def test_reset_clears_cached_instance() -> None:
    original = wiki_pages_read._wiki_pages
    try:
        wiki_pages_read._wiki_pages = object()
        assert wiki_pages_read._wiki_pages is not None
        reset_wiki_pages_cache()
        assert wiki_pages_read._wiki_pages is None
    finally:
        wiki_pages_read._wiki_pages = original


def test_get_wiki_pages_returns_cached_instance_without_reinit() -> None:
    # When the cache is already populated, get_wiki_pages must return it
    # directly (cache-hit path) without importing the wiki skill bundle.
    original = wiki_pages_read._wiki_pages
    sentinel = object()
    try:
        wiki_pages_read._wiki_pages = sentinel
        assert get_wiki_pages() is sentinel
        # Idempotent: a second call returns the same cached object.
        assert get_wiki_pages() is sentinel
    finally:
        wiki_pages_read._wiki_pages = original


def test_reset_is_idempotent() -> None:
    original = wiki_pages_read._wiki_pages
    try:
        reset_wiki_pages_cache()
        reset_wiki_pages_cache()
        assert wiki_pages_read._wiki_pages is None
    finally:
        wiki_pages_read._wiki_pages = original
