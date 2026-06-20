"""Shared path-security helpers for browse tools."""

import logging
from pathlib import Path

from src.config.paths import (
    get_documents_dir,
    get_logs_dir,
    get_project_root,
    get_runtime_dir,
    get_vault_dir,
)
from src.lib.index.document_attachments import DocumentAttachmentConfigError
from src.lib.index.document_source_config import configured_document_sources
from src.lib.index.document_sources import default_document_sources

logger = logging.getLogger(__name__)


def _allowed_roots() -> list[Path]:
    """Return the list of allowed root paths for file operations.

    Includes every indexed document-source root (Documents plus Desktop and
    Downloads, plus configured shared source caches) so files Browse surfaces
    from those folders can be revealed and opened. The reveal/open allow-list
    must track the same roots the indexer scans
    (``configured_document_sources``); otherwise indexed files become
    un-revealable. See file_platform.get_allowed_roots for the read/write side.
    """
    project_root = get_project_root()
    documents_dir = get_documents_dir()
    roots = [
        project_root,
        get_vault_dir(),
        documents_dir,
        get_logs_dir(),
        # Archived-ADR bodies are extracted to runtime adr-extracts before the
        # dashboard opens them (ADR-642 flow, ADR-811 plain-file model). The
        # open/reveal allow-list must include that destination or the Browse
        # "Open ADR" primary action fails with "Path not within allowed
        # directories".
        get_runtime_dir() / "adr-extracts",
    ]
    try:
        document_sources = configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
        )
    except DocumentAttachmentConfigError as exc:
        logger.warning("Ignoring invalid document source config for browse file actions: %s", exc)
        document_sources = default_document_sources(documents_dir=documents_dir)
    roots.extend(source.resolved_path for source in document_sources)
    return roots


def _is_path_allowed(path: str) -> bool:
    """Check if a path is within any allowed root."""
    resolved = Path(path).resolve()
    return any(resolved == root or root in resolved.parents for root in _allowed_roots())
