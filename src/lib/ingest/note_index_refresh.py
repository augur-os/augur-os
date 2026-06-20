"""Shared post-write Browse refresh for /note outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.paths import get_project_root, get_rag_dir, get_vault_dir
from src.lib.index.incremental import sync_categories
from src.lib.index.unified_indexer import reindex_category
from src.lib.index.watch_roots import categories_for_path, resolve_watch_roots


@dataclass(frozen=True)
class NoteBrowseIndexRefresh:
    """Structured status for the Browse vault-index refresh."""

    success: bool
    count: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "success": self.success,
            "count": self.count,
        }
        if self.error:
            payload["error"] = self.error
        return payload


def _refresh_category(
    category: str,
    *,
    project_root: Path | None = None,
    rag_dir: Path | None = None,
    vault_dir: Path | None = None,
) -> NoteBrowseIndexRefresh:
    """Reindex one Browse category, never raising on failure."""
    try:
        resolved_root = project_root or get_project_root()
        resolved_rag_dir = rag_dir or get_rag_dir()
        resolved_vault_dir = vault_dir or get_vault_dir()
        count = reindex_category(
            category,
            resolved_root,
            resolved_rag_dir,
            vault_dir=resolved_vault_dir,
        )
        return NoteBrowseIndexRefresh(success=True, count=int(count))
    except Exception as exc:  # noqa: BLE001 - indexing failure is user-visible status
        return NoteBrowseIndexRefresh(success=False, error=str(exc))


def refresh_notes_browse_index(
    *,
    project_root: Path | None = None,
    rag_dir: Path | None = None,
    vault_dir: Path | None = None,
) -> NoteBrowseIndexRefresh:
    """Refresh Browse's vault index after a note write.

    This must never roll back or break a successful note write. Callers surface
    the returned failure status instead.
    """
    return _refresh_category("vault", project_root=project_root, rag_dir=rag_dir, vault_dir=vault_dir)


def refresh_prompts_browse_index(
    *,
    project_root: Path | None = None,
    rag_dir: Path | None = None,
    vault_dir: Path | None = None,
) -> NoteBrowseIndexRefresh:
    """Refresh Browse's prompts index after a prompt-card write.

    The Prompts tab reads the "prompts" rag category, which the "vault" refresh
    does not touch — so prompt-card saves must call this too or the card won't
    appear until a full reindex.
    """
    return _refresh_category("prompts", project_root=project_root, rag_dir=rag_dir, vault_dir=vault_dir)


def refresh_browse_after_write(
    *,
    paths: list[Path] | None = None,
    categories: set[str] | None = None,
    vault_dir: Path | None = None,
    documents_dir: Path | None = None,
) -> dict[str, NoteBrowseIndexRefresh]:
    """Reindex every Browse category affected by the given paths/categories.

    ``paths`` are mapped through categories_for_path(); ``categories`` are added
    explicitly (for deletes/moves where the caller already knows what it
    touched). Delegates to sync_categories() so documents also refresh
    chunks/BM25. Never raises — returns a per-category status dict so a failed
    refresh never breaks the successful write that triggered it.
    """
    cats: set[str] = set(categories or set())
    if paths:
        roots = resolve_watch_roots()
        for p in paths:
            cats |= categories_for_path(Path(p), roots)
    if not cats:
        return {}
    try:
        counts = sync_categories(
            cats,
            project_root=get_project_root(),
            rag_dir=None,
            vault_dir=vault_dir,
            documents_dir=documents_dir,
        )
        return {cat: NoteBrowseIndexRefresh(success=True, count=int(counts.get(cat, 0))) for cat in cats}
    except Exception as exc:  # noqa: BLE001 - refresh failure is user-visible status
        return {cat: NoteBrowseIndexRefresh(success=False, error=str(exc)) for cat in cats}


__all__ = [
    "NoteBrowseIndexRefresh",
    "refresh_notes_browse_index",
    "refresh_prompts_browse_index",
    "refresh_browse_after_write",
]
