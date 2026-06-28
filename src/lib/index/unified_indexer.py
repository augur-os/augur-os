"""Unified RAG indexer — single entry point for all browse categories.

This module replaces rag_indexer.py and project_indexer.py with a
structured pointer-file approach. Each category scanner writes markdown
index entries to rag_dir/{category}/{hub}/{name}.md using write_frontmatter().

Currently implemented scanners:
  - index_skills()      — scans managed skill roots
  - index_adrs()        — scans get_adr_dir()/ADR-*.md
  - index_wiki()        — scans compiled runtime wiki pages
  - index_prompts()     — scans managed skill prompts and seed prompts
  - index_agents()      — scans plugins/agents/*.md + registry.json
  - index_integrations()— scans SKILL.md frontmatter integrations lists
  - index_commands()    — scans managed skill command docs
  - index_logs()        — scans runtime logs from get_logs_dir()
  - index_vault()       — scans external vault *.md files
  - index_scripts()     — scans managed skill scripts for .py/.sh files
  - index_api_routes()  — scans apps/dashboard/app/api/**/route.ts
  - index_tests()       — scans plugin augur/tests/ and dashboard tests/
  - index_pages()       — scans SKILL.md frontmatter contributions.pages lists
  - index_blocks()      — scans SKILL.md frontmatter contributions.blocks lists
  - index_mcp_tools()   — scans managed skill scripts/**/mcp/*.py
  - index_mcp_servers() — scans config/system/mcp_servers.yaml
"""

# TODO_CLEANUP: This file is 800 lines — consider splitting into smaller modules

from __future__ import annotations

import re
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root and scripts dir are on sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent


def _resolve_project_root(start_dir: Path) -> Path:
    """Find the repo root when the script is executed directly."""
    for candidate in (start_dir, *start_dir.parents):
        if (candidate / "src").is_dir() and (candidate / "config").is_dir():
            return candidate
    # Fallback for unexpected layouts; current repo root is 3 levels above scripts/.
    return start_dir.parents[3]


_PROJECT_ROOT = _resolve_project_root(_SCRIPT_DIR)
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
# project-brain/capabilities hosts the `skills.<bundle>` namespace
# (e.g. skills.ingest); scanners import from it when run as a script.
_PROJECT_BRAIN_CAPABILITIES_ROOT = _PROJECT_ROOT / "project-brain" / "capabilities"
if _PROJECT_BRAIN_CAPABILITIES_ROOT.is_dir() and str(_PROJECT_BRAIN_CAPABILITIES_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_BRAIN_CAPABILITIES_ROOT))

from src.config.paths import (
    get_compiled_wiki_dir,
    get_project_brain_dir,
    get_project_root,
    get_rag_dir,
    get_project_brain_wiki_dir,
)


def _progress(message: str) -> None:
    """Emit non-result progress messages to stderr.

    The unified indexer is imported by MCP tools that speak JSON-RPC over stdio.
    Any human-readable progress on stdout corrupts that protocol stream.
    """
    print(message, file=sys.stderr)


# ---------------------------------------------------------------------------
# Re-exports: all scanner functions remain importable from this module.
# ---------------------------------------------------------------------------
try:
    from ._indexer_helpers import (  # noqa: F401
        _checksum,
        _discover_bundles,
        _has_legacy_wiki_compile_metadata,
        _write_entry,
        clear_preserved_entry_metadata,
        prime_preserved_entry_metadata,
    )
    from ._scanners_knowledge import (  # noqa: F401
        index_adrs,
        index_agents,
        index_commands,
        index_integrations,
        index_prompts,
        index_skills,
        index_wiki,
    )
    from ._scanners_structural import (  # noqa: F401
        _extract_tool_name,
        index_api_routes,
        index_blocks,
        index_logs,
        index_mcp_servers,
        index_mcp_tools,
        index_pages,
        index_scripts,
        index_tests,
        index_vault,
    )
except ImportError:
    from _indexer_helpers import (  # noqa: F401
        _checksum,
        _discover_bundles,
        _has_legacy_wiki_compile_metadata,
        _write_entry,
        clear_preserved_entry_metadata,
        prime_preserved_entry_metadata,
    )
    from _scanners_knowledge import (  # noqa: F401
        index_adrs,
        index_agents,
        index_commands,
        index_integrations,
        index_prompts,
        index_skills,
        index_wiki,
    )
    from _scanners_structural import (  # noqa: F401
        _extract_tool_name,
        index_api_routes,
        index_blocks,
        index_logs,
        index_mcp_servers,
        index_mcp_tools,
        index_pages,
        index_scripts,
        index_tests,
        index_vault,
    )

try:
    from .document_sources import (
        DocumentSource,
        media_kind_for_path,
        should_index_source_file,
    )
except ImportError:
    from document_sources import (
        DocumentSource,
        media_kind_for_path,
        should_index_source_file,
    )


# ---------------------------------------------------------------------------
# Document extraction helper (replaces binary_extractor.py)
# ---------------------------------------------------------------------------


# macOS marks an iCloud "Optimize Mac Storage" placeholder (content evicted to the
# cloud) with the SF_DATALESS file flag. Opening such a file forces an on-demand
# download; under the daemon's concurrent indexing that deadlocks (EDEADLK /
# "Resource deadlock avoided" / pymupdf "Failed to open file") and NEVER converges,
# while the always-retry refresh policy re-attempts every cycle — an unbounded
# storm (observed: ~448 placeholder PDFs → 82k failed conversions per log). A bare
# stat() does NOT trigger a download, so detecting + skipping is cheap and safe.
_SF_DATALESS = 0x40000000


def _is_dataless(path: Path) -> bool:
    """True if *path* is a macOS dataless iCloud placeholder (no local content)."""
    try:
        return bool(getattr(path.stat(), "st_flags", 0) & _SF_DATALESS)
    except OSError:
        return False


def _dataless_skip_result(path: Path) -> dict[str, Any]:
    """A non-failing 'skipped' extraction for an un-materialized iCloud placeholder.

    method='skipped_dataless' (NOT 'failed') so the refresh policy does not retry it
    every cycle; it re-extracts once the file is materialized locally. stat() is
    side-effect-free (no download), so size is safe to read.
    """
    from datetime import datetime as _dt, timezone as _tz

    try:
        from .document_understanding import UNDERSTANDING_VERSION
    except ImportError:
        from document_understanding import UNDERSTANDING_VERSION
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {
        "format": path.suffix.lstrip(".").lower() or "unknown",
        "size_bytes": size,
        "created": _dt.now(_tz.utc).isoformat(),
        "body": "",
        "extraction_error": "icloud_placeholder_not_downloaded",
        "document_title": path.stem,
        "document_kind": "unknown",
        "document_summary": "",
        "document_key_insights": [],
        "document_sections": [],
        "document_extraction_method": "skipped_dataless",
        "document_visual_structure_used": False,
        "document_understanding_version": UNDERSTANDING_VERSION,
        "document_action_candidates": [],
        "document_extraction_confidence": "low",
        "document_low_signal_warnings": ["icloud_placeholder"],
        "document_llm_assisted": False,
    }


def _extract_document(path: Path) -> dict[str, Any]:
    """Extract text from a document using the document-extractor skill.

    Returns a dict with format, size_bytes, created, body, and optionally
    extraction_error — matching the shape that index_documents() expects.
    """
    from datetime import datetime as _dt, timezone as _tz

    if _is_dataless(path):
        return _dataless_skip_result(path)

    try:
        from .document_understanding import understand_document
    except ImportError:
        from document_understanding import understand_document

    understanding = understand_document(path)
    return {
        "format": understanding["format"],
        "size_bytes": path.stat().st_size,
        "created": _dt.now(_tz.utc).isoformat(),
        "body": understanding["body"],
        "extraction_error": understanding.get("error"),
        "document_title": understanding["title"],
        "document_kind": understanding["document_kind"],
        "document_summary": understanding["summary"],
        "document_key_insights": understanding["key_insights"],
        "document_sections": understanding["section_hints"],
        "document_extraction_method": understanding["extraction_method"],
        "document_visual_structure_used": understanding["visual_structure_used"],
        "document_understanding_version": understanding["understanding_version"],
        "document_action_candidates": understanding["action_candidates"],
        "document_extraction_confidence": understanding["extraction_confidence"],
        "document_low_signal_warnings": understanding["low_signal_warnings"],
        "document_llm_assisted": understanding["llm_assisted"],
    }


_INDEXABLE_DOCUMENT_EXTENSIONS = {
    ".csv",
    ".doc",
    ".docx",
    ".epub",
    ".htm",
    ".html",
    ".json",
    ".md",
    ".markdown",
    ".odp",
    ".ods",
    ".odt",
    ".pdf",
    ".ppt",
    ".pptx",
    ".rst",
    ".rtf",
    ".svg",
    ".tex",
    ".text",
    ".toml",
    ".tsv",
    ".txt",
    ".xls",
    ".xlsx",
    ".xml",
    ".yaml",
    ".yml",
}

_DIRECT_TEXT_EXTENSIONS = {
    ".csv",
    ".htm",
    ".html",
    ".json",
    ".markdown",
    ".md",
    ".rst",
    ".svg",
    ".tex",
    ".text",
    ".toml",
    ".tsv",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

_DOCUMENT_UNDERSTANDING_FIELDS = {
    "document_action_candidates",
    "document_extraction_confidence",
    "document_low_signal_warnings",
    "document_llm_assisted",
}


def _needs_document_understanding_refresh(meta: dict[str, Any], path: Path | None = None) -> bool:
    if not _DOCUMENT_UNDERSTANDING_FIELDS.issubset(meta):
        return True
    method = str(meta.get("document_extraction_method") or "")
    # An un-materialized iCloud placeholder cannot be extracted without forcing a
    # download (which deadlocks). Re-extract ONLY once it has been materialized
    # locally — never every cycle, which is what turned 448 placeholders into the
    # 82k-failure storm.
    if method == "skipped_dataless":
        return path is not None and not _is_dataless(path)
    # A failed/empty prior extraction must never stick: always retry it so a
    # transient read failure (e.g. EDEADLK under concurrent indexing) self-heals
    # on the next index instead of caching an unreadable-source result forever.
    if method == "failed":
        return True
    warnings = meta.get("document_low_signal_warnings") or []
    if "unreadable_source" in warnings or "empty_body" in warnings:
        return True
    return str(meta.get("document_understanding_version") or "") < "v3"


def _backfill_document_title(meta: dict[str, Any], body: str, stem: str) -> None:
    """Set a human-readable display title when the entry only carries the stem.

    Browse renders ``title`` (falling back to the filename stem). Entries indexed
    before title inference existed have ``document_title == stem`` and no
    ``title``; derive a real one from the stored body so cards stop showing bare
    filenames like "L28" or "document". Cheap: no re-extraction.
    """
    try:
        from .document_understanding import _infer_title, is_noise_title
    except ImportError:
        from document_understanding import _infer_title, is_noise_title  # type: ignore
    # A previously-stored title that is markup noise (e.g. a MarkItDown
    # "<!-- Slide number: 1 -->" artifact) is worse than the stem — re-derive it.
    current = str(meta.get("title") or "").strip()
    if current and not is_noise_title(current):
        return
    existing = str(meta.get("document_title") or "").strip()
    candidate = existing if existing and existing != stem and not is_noise_title(existing) else ""
    if not candidate:
        candidate = _infer_title(body, fallback=stem)
    if candidate and candidate != stem and not is_noise_title(candidate):
        meta["title"] = candidate
        meta["document_title"] = candidate
    elif current and is_noise_title(current):
        # Drop the noise title; fall back to the stem display.
        meta.pop("title", None)
        if is_noise_title(existing):
            meta["document_title"] = stem


def _is_indexable_document(path: Path, source: DocumentSource | None = None) -> bool:
    """Return True when the nightly document index should attempt extraction."""
    if source is not None:
        return should_index_source_file(path, source)
    return path.suffix.lower() in _INDEXABLE_DOCUMENT_EXTENSIONS


def _best_effort_document_body(path: Path) -> str:
    """Read text-like content directly and degrade safely for binary files."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        try:
            return path.read_bytes().decode("utf-8", errors="ignore")
        except OSError:
            return ""


def _document_checksum(path: Path) -> tuple[str, OSError | None]:
    """Return a content checksum, degrading when macOS refuses a source read.

    Uses the retrying reader so transient lock contention (EDEADLK under
    concurrent indexing / iCloud materialization) does not get recorded as an
    unreadable source.
    """
    import hashlib

    try:
        from .ocr_extractor import read_source_bytes
    except ImportError:  # pragma: no cover - script-path import fallback
        from ocr_extractor import read_source_bytes  # type: ignore

    try:
        return hashlib.md5(read_source_bytes(path), usedforsecurity=False).hexdigest(), None  # noqa: S324
    except OSError as exc:
        return "", exc


def _load_mtime_cache() -> dict[str, float]:
    """Load the file mtime cache from the runtime state directory.

    Returns a dict mapping absolute file path strings to mtime floats.
    On first run (no cache file), returns an empty dict.
    """
    import json

    from src.config.paths import get_runtime_dir

    cache_path = get_runtime_dir() / "adaptive" / "rag_mtime_cache.json"
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_mtime_cache(cache: dict[str, float]) -> None:
    """Persist the file mtime cache to the runtime state directory."""
    import json

    from src.config.paths import get_runtime_dir

    cache_path = get_runtime_dir() / "adaptive" / "rag_mtime_cache.json"
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        # Cache persistence is an optimization; indexing should still succeed
        # when runtime state is unavailable in tests or restricted shells.
        return None


def index_documents(documents_dir: Path, rag_dir: Path) -> int:
    """Recursively index the primary document source (~/Documents) into rag_dir.

    Existing callers keep the historical output layout:

        rag_dir/documents/{skill}/{sub_dir}/{name}.md
    """
    source = DocumentSource(
        "documents",
        "Documents",
        Path(documents_dir),
        preserve_legacy_output=True,
    )
    return _index_document_source(source, rag_dir)


def index_document_sources(
    sources: list[DocumentSource],
    rag_dir: Path,
    *,
    project_root: Path | None = None,
) -> int:
    """Index all configured document sources into the Browse documents category."""
    count = 0
    for source in sources:
        count += _index_document_source(source, rag_dir, project_root=project_root)
    return count


def _remove_empty_dirs(root: Path) -> None:
    """Remove empty subdirectories under ``root`` (bottom-up); keep ``root`` itself.

    Pruning orphaned entry files (after a source moves/deletes) can leave empty
    directory shells; this clears them so the index never looks stale on move.
    """
    if not root.is_dir():
        return
    subdirs = sorted(
        (p for p in root.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for d in subdirs:
        try:
            next(d.iterdir())
        except StopIteration:
            try:
                d.rmdir()
            except OSError:
                pass
        except OSError:
            pass


def _index_document_source(
    source: DocumentSource,
    rag_dir: Path,
    *,
    project_root: Path | None = None,
) -> int:
    """Index one source root while pruning only that source's output namespace."""
    import hashlib

    from src.lib.frontmatter_utils import parse_frontmatter

    documents_dir = source.resolved_path
    category_dir = rag_dir / "documents"
    count = 0

    if not documents_dir.is_dir():
        return count

    document_catalog: dict[str, Any] = {}
    if project_root is not None:
        try:
            from .document_catalog import load_document_catalog
        except ImportError:
            from document_catalog import load_document_catalog

        document_catalog = load_document_catalog(project_root)

    clear_preserved_entry_metadata()
    try:
        prime_preserved_entry_metadata(category_dir)

        def document_output_path(source_path: Path) -> Path | None:
            try:
                rel = source_path.relative_to(documents_dir)
            except ValueError:
                return None

            base_output = base_document_output_path(rel)
            if base_output is None:
                return None

            file_key = str(source_path.resolve())
            if file_key not in collision_source_keys:
                return base_output

            return collision_document_output_path(rel)

        def base_document_output_path(rel: Path) -> Path | None:
            if source.preserve_legacy_output:
                return legacy_document_output_path(rel)
            return source_document_output_path(source, rel)

        def legacy_document_output_path(rel: Path) -> Path | None:
            parts = rel.parts
            if not parts:
                return None

            name = rel.stem
            if parts[0] == "_sources":
                escaped_parent = category_dir / "_legacy_sources"
                escaped_parts = parts[1:]
                if not escaped_parts or len(escaped_parts) == 1:
                    return escaped_parent / f"{name}.md"
                if len(escaped_parts) == 2:  # noqa: PLR2004
                    return escaped_parent / escaped_parts[0] / f"{name}.md"
                return escaped_parent / escaped_parts[0] / escaped_parts[1] / f"{name}.md"
            if len(parts) == 1:
                return category_dir / "_root" / f"{name}.md"
            if len(parts) == 2:  # noqa: PLR2004
                return category_dir / parts[0] / f"{name}.md"
            return category_dir / parts[0] / parts[1] / f"{name}.md"

        def source_document_output_path(source: DocumentSource, rel: Path) -> Path | None:
            parts = rel.parts
            if not parts:
                return None

            parent = category_dir / "_sources" / source.id
            if len(parts) == 1:
                return parent / f"{rel.stem}.md"
            if len(parts) == 2:  # noqa: PLR2004
                return parent / parts[0] / f"{rel.stem}.md"
            return parent / parts[0] / parts[1] / f"{rel.stem}.md"

        def collision_document_output_path(rel: Path) -> Path:
            base_output = base_document_output_path(rel)
            if base_output is None:
                parent = category_dir / "_root"
                if not source.preserve_legacy_output:
                    parent = category_dir / "_sources" / source.id / "_root"
                return parent / f"{rel.stem}.md"
            extension = rel.suffix.lower().lstrip(".") or "document"
            digest = hashlib.sha1(rel.as_posix().encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
            return base_output.with_name(f"{rel.stem}__{extension}-{digest}.md")

        def source_key_belongs_to_source(file_key: str) -> bool:
            try:
                Path(file_key).expanduser().resolve(strict=False).relative_to(documents_dir)
            except (OSError, ValueError):
                return False
            return True

        def apply_source_metadata(
            entry_meta: dict[str, Any],
            rel: Path,
            media_kind: str,
            skill: str,
        ) -> None:
            try:
                from .document_attachments import (
                    DocumentAttachmentMetadata,
                    document_sync_status,
                )
                from .document_catalog import lookup_catalog_entry
            except ImportError:
                from document_attachments import (
                    DocumentAttachmentMetadata,
                    document_sync_status,
                )
                from document_catalog import lookup_catalog_entry

            source_path = Path(str(entry_meta.get("source_path") or documents_dir / rel))
            source_relative_path = rel.as_posix()
            resolved_source_path = source_path.expanduser().resolve(strict=False)
            fallback_canonical_id = (
                f"filesystem:{resolved_source_path}"
                if source.provider == "filesystem"
                else f"{source.provider}:{source.id}:{source_relative_path}"
            )
            catalog_entry = lookup_catalog_entry(
                document_catalog,
                remote_id="",
                canonical_document_id=fallback_canonical_id,
                source_id=source.id,
                source_relative_path=source_relative_path,
            )

            if catalog_entry is not None:
                canonical_document_id = (
                    catalog_entry.canonical_document_id or catalog_entry.remote_id or fallback_canonical_id
                )
                remote_id = catalog_entry.remote_id
                attached_brain_ids = catalog_entry.attached_brain_ids or source.attached_brain_ids
                provider = catalog_entry.provider or source.provider
                catalog_title = catalog_entry.title
                catalog_summary = catalog_entry.summary
                summary_status = catalog_entry.summary_status
                summary_revision = catalog_entry.summary_generated_from_revision
                remote_revision = catalog_entry.remote_revision or source.remote_revision
                remote_modified_at = catalog_entry.remote_modified_at or source.remote_modified_at
                if project_root is not None:
                    try:
                        catalog_entry_path = catalog_entry.path.relative_to(project_root).as_posix()
                    except ValueError:
                        catalog_entry_path = catalog_entry.path.as_posix()
                else:
                    catalog_entry_path = ""
            else:
                canonical_document_id = fallback_canonical_id
                remote_id = ""
                attached_brain_ids = source.attached_brain_ids
                provider = source.provider
                catalog_title = source.catalog_title
                catalog_summary = source.catalog_summary
                summary_status = source.summary_status
                summary_revision = source.summary_generated_from_revision
                remote_revision = source.remote_revision
                remote_modified_at = source.remote_modified_at
                catalog_entry_path = source.catalog_entry_path

            indexed_revision = (
                source.remote_revision if source.source_type == "shared" else remote_revision or source.remote_revision
            )
            index_status = document_sync_status(
                remote_revision=remote_revision or None,
                indexed_revision=indexed_revision or None,
                summary_generated_from_revision=summary_revision or None,
                has_local_index=True,
                has_access=True,
                requires_remote_revision=source.source_type == "shared",
            )
            attachment = DocumentAttachmentMetadata(
                canonical_document_id=canonical_document_id,
                source_id=source.id,
                source_type=source.source_type,
                provider=provider,
                attached_brain_ids=tuple(attached_brain_ids),
                remote_id=remote_id,
                remote_revision=remote_revision,
                remote_modified_at=remote_modified_at,
                indexed_revision=indexed_revision,
                index_status=index_status,
                catalog_entry_path=catalog_entry_path,
                catalog_title=catalog_title,
                catalog_summary=catalog_summary,
                summary_status=summary_status,
                summary_generated_from_revision=summary_revision,
            )
            entry_meta.update(
                {
                    "hub": source.id if not source.preserve_legacy_output else skill,
                    "source_root": source.id,
                    "source_root_name": source.name,
                    "source_root_path": str(source.resolved_path),
                    "source_relative_path": source_relative_path,
                    "file_ext": rel.suffix.lower().lstrip("."),
                }
            )
            entry_meta.update(attachment.to_frontmatter())
            if catalog_title:
                entry_meta["title"] = catalog_title
                entry_meta["document_title"] = catalog_title
            if catalog_summary:
                entry_meta["description"] = catalog_summary
                entry_meta["document_summary"] = catalog_summary
            if media_kind:
                entry_meta["media_kind"] = media_kind
            else:
                entry_meta.pop("media_kind", None)

        def prune_candidates() -> list[Path]:
            if not source.preserve_legacy_output:
                source_root = category_dir / "_sources" / source.id
                return sorted(source_root.rglob("*.md")) if source_root.is_dir() else []
            if not category_dir.is_dir():
                return []
            candidates: list[Path] = []
            for indexed_output in sorted(category_dir.rglob("*.md")):
                try:
                    rel_parts = indexed_output.relative_to(category_dir).parts
                except ValueError:
                    continue
                if rel_parts and rel_parts[0] == "_sources":
                    continue
                candidates.append(indexed_output)
            return candidates

        candidate_files: list[Path] = []
        base_outputs: dict[Path, list[Path]] = {}
        for file_path in sorted(documents_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.is_symlink():
                continue
            if file_path.relative_to(documents_dir).parts[:1] == ("_augur",):
                # Docs-store machine output (_augur/: evals, reports, migration
                # manifests) is not user content — keep it out of retrieval.
                continue
            if not _is_indexable_document(file_path, source):
                continue
            if media_kind_for_path(file_path):
                # Media files stay visible to listings (should_index_source_file)
                # and media pipelines, but produce NO documents-category entry.
                continue
            try:
                rel = file_path.relative_to(documents_dir)
            except ValueError:
                continue
            output_path = base_document_output_path(rel)
            if output_path is None:
                continue
            candidate_files.append(file_path)
            base_outputs.setdefault(output_path, []).append(file_path)

        collision_source_keys = {
            str(file_path.resolve()) for files in base_outputs.values() if len(files) > 1 for file_path in files
        }

        # Load mtime cache — maps absolute file path to last-seen mtime
        mtime_cache = _load_mtime_cache()
        new_cache: dict[str, float] = {
            file_key: mtime for file_key, mtime in mtime_cache.items() if not source_key_belongs_to_source(file_key)
        }

        # Collect the set of current source files for deletion detection
        current_files: set[str] = set()

        for file_path in candidate_files:
            file_key = str(file_path.resolve())
            current_files.add(file_key)
            output_path = document_output_path(file_path)
            if output_path is None:
                continue

            rel = file_path.relative_to(documents_dir)
            parts = rel.parts
            name = file_path.stem
            skill = "_root" if len(parts) == 1 else parts[0]
            sub_dir = parts[1] if len(parts) > 2 else None
            media_kind = media_kind_for_path(file_path)

            # Check mtime — skip extraction if file is unchanged and output exists
            current_mtime = file_path.stat().st_mtime
            cached_mtime = mtime_cache.get(file_key)
            if cached_mtime is not None and cached_mtime == current_mtime and output_path.exists():
                # File unchanged since last index — keep cache entry, count it, skip extraction.
                # If the on-disk entry still carries legacy wiki compiler metadata,
                # rewrite it in place using the existing body and manual metadata only.
                existing_meta, existing_body = parse_frontmatter(output_path)
                if not _needs_document_understanding_refresh(existing_meta, file_path):
                    refreshed_meta = dict(existing_meta)
                    apply_source_metadata(refreshed_meta, rel, media_kind, skill)
                    # Backfill a human-readable display title for entries indexed
                    # before title inference existed — derive it from the stored
                    # body (frontmatter title / first heading) without re-extracting.
                    _backfill_document_title(refreshed_meta, existing_body, name)
                    if _has_legacy_wiki_compile_metadata(existing_meta) or refreshed_meta != existing_meta:
                        _write_entry(output_path, refreshed_meta, existing_body)
                    new_cache[file_key] = current_mtime
                    count += 1
                    continue

            # Extract content and metadata via document-extractor
            # Note: media files are skipped at candidate collection above, so media_kind is always empty here.
            extraction = _extract_document(file_path)

            if extraction.get("document_extraction_method") == "skipped_dataless":
                # Reading bytes for a checksum would force the iCloud download and
                # re-arm the EDEADLK storm (and add an `unreadable_source` warning
                # that re-triggers refresh). Skip it; the placeholder entry stays
                # cheap and re-extracts once the file is materialized.
                checksum, checksum_error = "", None
            else:
                checksum, checksum_error = _document_checksum(file_path)
            if checksum_error is not None:
                read_error = f"Unable to read source bytes for checksum: {checksum_error}"
                if extraction.get("extraction_error"):
                    extraction["extraction_error"] = f"{extraction['extraction_error']}; {read_error}"
                else:
                    extraction["extraction_error"] = read_error
                extraction["document_extraction_confidence"] = "low"
                warnings = list(extraction.get("document_low_signal_warnings") or [])
                if "unreadable_source" not in warnings:
                    warnings.append("unreadable_source")
                extraction["document_low_signal_warnings"] = warnings

            entry_meta: dict[str, Any] = {
                "type": "document",
                "category": "binary",
                "skill": skill,
                "name": name,
                "source_path": file_key,
                "format": extraction["format"],
                "size_bytes": extraction["size_bytes"],
                "created": extraction["created"],
                "modified": datetime.fromtimestamp(current_mtime, tz=timezone.utc).isoformat(),
                "checksum": checksum,
            }

            if sub_dir is not None:
                entry_meta["sub_dir"] = sub_dir

            if extraction.get("extraction_error"):
                entry_meta["extraction_error"] = extraction["extraction_error"]

            entry_meta.update(
                {
                    "document_title": extraction.get("document_title", name),
                    "document_kind": extraction.get("document_kind", file_path.suffix.lstrip(".") or "document"),
                    "document_summary": extraction.get("document_summary", ""),
                    "document_key_insights": extraction.get("document_key_insights", []),
                    "document_sections": extraction.get("document_sections", []),
                    "document_extraction_method": extraction.get("document_extraction_method", "unknown"),
                    "document_visual_structure_used": extraction.get("document_visual_structure_used", False),
                    "document_understanding_version": extraction.get("document_understanding_version", "v1"),
                    "document_action_candidates": extraction.get("document_action_candidates", []),
                    "document_extraction_confidence": extraction.get("document_extraction_confidence", "low"),
                    "document_low_signal_warnings": extraction.get("document_low_signal_warnings", []),
                    "document_llm_assisted": extraction.get("document_llm_assisted", False),
                }
            )
            # Surface the understood title as the entry's display title so Browse
            # cards show "L28 — Pitch Deck Review", not the bare filename stem.
            # A catalog title (set above) always wins; otherwise use the
            # understanding title when it improves on the stem.
            understood_title = str(entry_meta.get("document_title") or "").strip()
            if not entry_meta.get("title") and understood_title and understood_title != name:
                entry_meta["title"] = understood_title
            apply_source_metadata(entry_meta, rel, media_kind, skill)

            # Preserve existing manual metadata.
            if output_path.exists():
                existing_meta, _ = parse_frontmatter(output_path)
                if existing_meta.get("manual_related"):
                    entry_meta.setdefault("manual_related", existing_meta["manual_related"])

            _write_entry(output_path, entry_meta, extraction["body"])
            if checksum_error is None:
                new_cache[file_key] = current_mtime
            count += 1

        # Prune output entries for files that no longer exist
        stale_keys = {
            file_key for file_key in set(mtime_cache.keys()) - current_files if source_key_belongs_to_source(file_key)
        }
        for stale_key in stale_keys:
            stale_path = Path(stale_key)
            try:
                stale_rel = stale_path.relative_to(documents_dir)
            except ValueError:
                continue
            stale_parts = stale_rel.parts
            if not stale_parts:
                continue
            stale_output = document_output_path(stale_path)
            if stale_output is None:
                continue
            if stale_output.exists():
                try:
                    stale_meta, _ = parse_frontmatter(stale_output)
                except Exception:
                    stale_output.unlink()
                    continue
                if str(stale_meta.get("source_path") or "") == stale_key:
                    stale_output.unlink()

        # Prune orphaned output files even when their old source paths are no longer
        # represented in the mtime cache, such as after a bad documents root was indexed.
        for indexed_output in prune_candidates():
            if not indexed_output.is_file():
                continue
            try:
                indexed_meta, _ = parse_frontmatter(indexed_output)
            except Exception:
                indexed_output.unlink()
                continue

            source_path_raw = indexed_meta.get("source_path")
            if not source_path_raw:
                indexed_output.unlink()
                continue

            source_path = Path(str(source_path_raw))
            expected_output = document_output_path(source_path)
            if expected_output is None:
                indexed_output.unlink()
                continue

            source_key = str(source_path.resolve())
            if source_key not in current_files or expected_output != indexed_output:
                indexed_output.unlink()

        # Remove empty entry-dir shells left after pruning moved/deleted sources,
        # so moving files never leaves stale-looking empty dirs in the index.
        _remove_empty_dirs(category_dir)

        # Persist updated mtime cache
        _save_mtime_cache(new_cache)

        return count
    finally:
        clear_preserved_entry_metadata()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

_DEFAULT_SHARED_ROOT = object()


def reindex_all(
    root: Path,
    rag_dir: Path,
    vault_dir: "Path | None" = None,
    documents_dir: "Path | None" = None,
    document_sources: "list[DocumentSource] | None" = None,
) -> "dict[str, int]":
    """Run all category scanners and write manifest + per-category checksums.

    Returns a dict mapping category name to the number of indexed entries.

    Manifest is written to rag_dir/_meta/manifest.yaml.
    Per-category checksums are written to rag_dir/_meta/checksums/{category}.yaml.
    """
    stats: dict[str, int] = {}

    # Knowledge scanners
    stats["skills"] = reindex_category("skills", root, rag_dir)
    stats["adrs"] = reindex_category("adrs", root, rag_dir)
    stats["wiki"] = reindex_category("wiki", root, rag_dir, wiki_dir=get_compiled_wiki_dir())
    stats["prompts"] = reindex_category("prompts", root, rag_dir)
    stats["agents"] = reindex_category("agents", root, rag_dir)
    stats["integrations"] = reindex_category("integrations", root, rag_dir)
    stats["commands"] = reindex_category("commands", root, rag_dir)

    # Vault scanner (optional)
    if vault_dir is not None:
        stats["vault"] = reindex_category("vault", root, rag_dir, vault_dir=vault_dir)
    else:
        stats["vault"] = 0

    # Structural scanners
    stats["scripts"] = reindex_category("scripts", root, rag_dir)
    stats["api-routes"] = reindex_category("api-routes", root, rag_dir)
    stats["tests"] = reindex_category("tests", root, rag_dir)
    stats["pages"] = reindex_category("pages", root, rag_dir, documents_dir=documents_dir)
    stats["blocks"] = reindex_category("blocks", root, rag_dir)
    stats["mcp-tools"] = reindex_category("mcp-tools", root, rag_dir)
    stats["mcp-servers"] = reindex_category("mcp-servers", root, rag_dir)
    stats["logs"] = reindex_category("logs", root, rag_dir)

    # Documents scanner (optional — uses document-extractor skill directly)
    if document_sources is not None:
        stats["documents"] = index_document_sources(document_sources, rag_dir, project_root=root)
    elif documents_dir is not None:
        from src.lib.index.document_source_config import configured_document_sources

        stats["documents"] = index_document_sources(
            configured_document_sources(project_root=root, documents_dir=documents_dir),
            rag_dir,
            project_root=root,
        )
    else:
        stats["documents"] = 0

    # Chunk extracted documents only. Source markdown is searched in-place.
    chunk_count, bm25_chunks = _chunk_all(rag_dir, root)
    stats["chunks"] = chunk_count

    # Build BM25 sparse index from in-memory chunk data
    _build_bm25(rag_dir, bm25_chunks)

    # Post-processing: enrich empty/stub descriptions from source files
    try:
        from .enrich_descriptions import enrich_all as _enrich_all
    except ImportError:
        try:
            from enrich_descriptions import enrich_all as _enrich_all
        except ImportError:
            _enrich_all = None
    if _enrich_all is not None:
        try:
            enrich_stats = _enrich_all(rag_dir, root)
            enriched_total = sum(enrich_stats.values())
            if enriched_total > 0:
                _progress(
                    f"  Enriched {enriched_total} descriptions across "
                    f"{sum(1 for v in enrich_stats.values() if v)} categories"
                )
        except Exception as e:
            _progress(f"  Warning: description enrichment failed: {e}")

    indexed_at = datetime.now(tz=timezone.utc).isoformat()

    # Write per-category checksums
    checksums_dir = rag_dir / "_meta" / "checksums"
    checksums_dir.mkdir(parents=True, exist_ok=True)
    for category, count in stats.items():
        checksum_file = checksums_dir / f"{category}.yaml"
        checksum_data = {
            "category": category,
            "count": count,
            "indexed_at": indexed_at,
        }
        checksum_file.write_text(yaml.dump(checksum_data, default_flow_style=False))

    # Collect entries from all category directories
    from src.lib.frontmatter_utils import parse_frontmatter

    entries: list[dict[str, Any]] = []
    for category_dir in sorted(rag_dir.iterdir()):
        if category_dir.name.startswith("_") or not category_dir.is_dir():
            continue
        if category_dir.name in ("chunks", "cache", "projects"):
            continue
        for entry_file in sorted(category_dir.rglob("*.md")):
            try:
                fm_data, _ = parse_frontmatter(entry_file)
                entries.append(
                    {
                        "name": fm_data.get("name", entry_file.stem),
                        "category": category_dir.name,
                        "hub": fm_data.get("hub", ""),
                        "path": entry_file.relative_to(rag_dir).as_posix(),
                        "description": fm_data.get("description", ""),
                    }
                )
            except Exception:
                continue

    # Write manifest
    meta_dir = rag_dir / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "2.0",
        "indexed_at": indexed_at,
        "root": str(rag_dir),
        "stats": stats,
        "total": sum(stats.values()),
        "entries": entries,
    }
    (meta_dir / "manifest.yaml").write_text(yaml.dump(manifest, default_flow_style=False))

    # Generate content-oriented index.md for LLM navigation
    _generate_index_md(rag_dir, entries, stats, indexed_at)

    return stats


def reindex_category(
    category: str,
    root: Path,
    rag_dir: Path,
    *,
    vault_dir: Path | None = None,
    shared_vault_dir: Any = _DEFAULT_SHARED_ROOT,
    documents_dir: Path | None = None,
    document_sources: list[DocumentSource] | None = None,
    wiki_dir: Path | None = None,
    shared_wiki_dir: Any = _DEFAULT_SHARED_ROOT,
) -> int:
    """Rebuild a single RAG category with preserved compile metadata priming."""
    clear_preserved_entry_metadata()
    try:
        prime_preserved_entry_metadata(rag_dir / category)

        if category == "skills":
            return index_skills(root, rag_dir)
        if category == "adrs":
            return index_adrs(root, rag_dir)
        if category == "wiki":
            if wiki_dir is None:
                wiki_dir = get_compiled_wiki_dir()
            if shared_wiki_dir is _DEFAULT_SHARED_ROOT:
                shared_wiki_dir = get_project_brain_wiki_dir(root)
            return index_wiki(wiki_dir, rag_dir, shared_wiki_dir=shared_wiki_dir, root=root)
        if category == "prompts":
            return index_prompts(root, rag_dir)
        if category == "agents":
            return index_agents(root, rag_dir)
        if category == "integrations":
            return index_integrations(root, rag_dir)
        if category == "commands":
            return index_commands(root, rag_dir)
        if category == "vault":
            if vault_dir is None:
                raise ValueError("vault_dir is required for vault reindex")
            if shared_vault_dir is _DEFAULT_SHARED_ROOT:
                shared_vault_dir = get_project_brain_dir(root)
            return index_vault(vault_dir, rag_dir, shared_vault_dir=shared_vault_dir, root=root)
        if category == "documents":
            if document_sources is not None:
                return index_document_sources(document_sources, rag_dir, project_root=root)
            if documents_dir is None:
                raise ValueError("documents_dir is required for documents reindex")
            from src.lib.index.document_source_config import configured_document_sources

            return index_document_sources(
                configured_document_sources(project_root=root, documents_dir=documents_dir),
                rag_dir,
                project_root=root,
            )
        if category == "scripts":
            return index_scripts(root, rag_dir)
        if category == "api-routes":
            return index_api_routes(root, rag_dir)
        if category == "tests":
            return index_tests(root, rag_dir)
        if category == "pages":
            return index_pages(root, rag_dir, documents_dir=documents_dir)
        if category == "blocks":
            return index_blocks(root, rag_dir)
        if category == "mcp-tools":
            return index_mcp_tools(root, rag_dir)
        if category == "mcp-servers":
            return index_mcp_servers(root, rag_dir)
        if category == "logs":
            return index_logs(root, rag_dir)
        raise ValueError(f"Unknown category: {category}")
    finally:
        clear_preserved_entry_metadata()


# ---------------------------------------------------------------------------
# Content-oriented index generation (Karpathy LLM Wiki pattern)
# ---------------------------------------------------------------------------


# Categories useful for LLM navigation — skip chunks and internal metadata
_INDEX_CATEGORIES = {
    "skills",
    "adrs",
    "wiki",
    "pages",
    "mcp-tools",
    "mcp-servers",
    "vault",
    "commands",
    "documents",
    "scripts",
    "logs",
}

# Hub display names for readable headings
_HUB_LABELS = {
    "adaptive": "Adaptive Engine",
    "brain": "Brain / Knowledge",
    "career": "Career / Professional",
    "command": "Command Center",
    "life": "Life / Personal",
    "studio": "Studio / Content",
    "dev": "Developer Tools",
}


def _generate_index_md(
    rag_dir: Path,
    entries: list[dict[str, Any]],
    stats: dict[str, int],
    indexed_at: str,
) -> None:
    """Generate a content-oriented index.md for LLM navigation.

    Organized by hub, then by category within each hub. Each entry is one line
    with name and description. This file is the first thing an LLM reads when
    searching the knowledge base — it replaces manifest.yaml for navigation.

    Inspired by Karpathy's LLM Wiki pattern: the index is a content catalog
    the LLM reads to find relevant pages before drilling into details.
    """
    # Group entries by hub → category
    by_hub: dict[str, dict[str, list[dict]]] = {}
    no_hub: dict[str, list[dict]] = {}

    for entry in entries:
        cat = entry.get("category", "")
        if cat not in _INDEX_CATEGORIES:
            continue

        hub = entry.get("hub", "") or ""
        desc = entry.get("description", "") or ""
        name = entry.get("name", "")
        if not name:
            continue

        record = {"name": name, "description": desc, "category": cat}

        if hub:
            by_hub.setdefault(hub, {}).setdefault(cat, []).append(record)
        else:
            no_hub.setdefault(cat, []).append(record)

    # Build the markdown
    lines: list[str] = []
    lines.append("# Knowledge Base Index")
    lines.append("")
    total = sum(v for k, v in stats.items() if k != "chunks")
    lines.append(f"*{total} entries across {len(stats) - 1} categories — indexed {indexed_at[:10]}*")
    lines.append("")
    lines.append("Use this index to find relevant pages. Each entry links to a detailed")
    lines.append("index file in the RAG directory. Search by topic, then drill into details.")
    lines.append("")

    # Hubs in sorted order
    for hub in sorted(by_hub.keys()):
        label = _HUB_LABELS.get(hub, hub.title())
        categories = by_hub[hub]
        entry_count = sum(len(v) for v in categories.values())
        lines.append(f"## {label} ({entry_count})")
        lines.append("")

        for cat in sorted(categories.keys()):
            items = categories[cat]
            lines.append(f"### {cat} ({len(items)})")
            lines.append("")
            for item in sorted(items, key=lambda x: x["name"]):
                desc = item["description"]
                if desc:
                    # Truncate long descriptions to keep index scannable
                    if len(desc) > 120:
                        desc = desc[:117] + "..."
                    lines.append(f"- **{item['name']}** — {desc}")
                else:
                    lines.append(f"- **{item['name']}**")
            lines.append("")

    # Entries without a hub
    if no_hub:
        no_hub_count = sum(len(v) for v in no_hub.values())
        lines.append(f"## Cross-Cutting ({no_hub_count})")
        lines.append("")
        for cat in sorted(no_hub.keys()):
            items = no_hub[cat]
            lines.append(f"### {cat} ({len(items)})")
            lines.append("")
            for item in sorted(items, key=lambda x: x["name"]):
                desc = item["description"]
                if desc:
                    if len(desc) > 120:
                        desc = desc[:117] + "..."
                    lines.append(f"- **{item['name']}** — {desc}")
                else:
                    lines.append(f"- **{item['name']}**")
            lines.append("")

    (rag_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    _progress(f"  Generated index.md ({len(entries)} entries, {len(by_hub)} hubs)")


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------


# Only extracted documents are chunked and ranked with BM25.
_CHUNK_CATEGORIES = {"documents"}
# Categories whose content should be chunked as code rather than markdown.
_CODE_CATEGORIES = {"scripts", "mcp-tools"}
# Directories under rag_dir to skip during Pass 2 category scanning.
_SKIP_DIRS = {"chunks", "_meta", "cache", "projects", "skills"}


def _safe_heading(heading: str) -> str:
    """Sanitize a heading string for use in a filename."""
    return re.sub(r'[^\w\-.]', '-', heading)[:60]


def _chunk_all(rag_dir: Path, root: Path) -> tuple[int, list[dict]]:
    """Chunk extracted document markdown for BM25 retrieval only."""
    import shutil

    try:
        from .chunker import auto_chunk
    except ImportError:
        from chunker import auto_chunk
    from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter

    chunks_dir = rag_dir / "chunks"
    if chunks_dir.exists():
        for child in sorted(chunks_dir.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    count = 0
    bm25_chunks: list[dict] = []
    for category_dir in sorted(rag_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        if category.startswith("_") or category in _SKIP_DIRS:
            continue
        if category not in _CHUNK_CATEGORIES:
            continue

        content_type = "code" if category in _CODE_CATEGORIES else "markdown"

        for entry_file in sorted(category_dir.rglob("*.md")):
            try:
                entry_meta, body = parse_frontmatter(entry_file)
            except Exception:
                continue

            if not body or len(body.strip()) < 200:  # noqa: PLR2004
                continue

            entry_rel = entry_file.relative_to(category_dir).with_suffix("")
            entry_key = entry_rel.as_posix()
            entry_name = entry_meta.get("name", entry_file.stem)
            source_path = entry_meta.get("source_path", str(entry_file))
            hub = entry_meta.get("hub", "uncategorized") or "uncategorized"
            inherited_chunk_fields = {
                key: entry_meta.get(key)
                for key in (
                    "canonical_document_id",
                    "remote_id",
                    "source_id",
                    "source_type",
                    "provider",
                    "attached_brain_ids",
                    "brain_id",
                    "remote_revision",
                    "remote_modified_at",
                    "indexed_revision",
                    "index_status",
                    "catalog_entry_path",
                    "summary_status",
                    "summary_generated_from_revision",
                    "source_relative_path",
                )
                if entry_meta.get(key) not in (None, "")
            }

            chunks = auto_chunk(body, content_type=content_type)
            if not chunks:
                continue

            chunks_dir.mkdir(parents=True, exist_ok=True)
            out_dir = chunks_dir / category / entry_rel
            out_dir.mkdir(parents=True, exist_ok=True)

            for chunk in chunks:
                sh = _safe_heading(chunk["section_heading"])
                chunk_name = f"{sh}_{chunk['chunk_index']}"
                output_path = out_dir / f"{chunk_name}.md"
                rel_path = f"chunks/{category}/{entry_key}/{chunk_name}.md"

                chunk_meta = {
                    "source": entry_name,
                    "source_path": source_path,
                    "category": category,
                    "hub": hub,
                    "heading": chunk["section_heading"],
                    "parent_heading": chunk["parent_heading"],
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": chunk["total_chunks"],
                    **inherited_chunk_fields,
                }
                write_frontmatter(output_path, chunk_meta, chunk["text"])
                count += 1

                bm25_chunks.append(
                    {
                        "path": rel_path,
                        "text": chunk["text"],
                        "meta": {
                            "source": entry_name,
                            "heading": chunk["section_heading"],
                            "hub": hub,
                            "category": category,
                            **inherited_chunk_fields,
                        },
                    }
                )

    return count, bm25_chunks


def _build_bm25(rag_dir: Path, bm25_chunks: list[dict]) -> None:
    """Build BM25 index from in-memory chunk data and save to _meta/.

    Accepts the chunk list returned by _chunk_all() to avoid re-reading
    chunk files from disk. Gracefully skips if rank_bm25 is not installed.
    """
    if not bm25_chunks:
        return

    try:
        from .bm25_index import BM25Index
    except ImportError:
        try:
            from bm25_index import BM25Index
        except ImportError as e:
            _progress(f"  Warning: BM25 index skipped (missing dependency: {e})")
            return

    index = BM25Index.build(bm25_chunks)
    meta_dir = rag_dir / "_meta"
    index.save(meta_dir)
    _progress(f"  BM25 index built: {index.size()} chunks")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Unified RAG indexer")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--rag-dir", type=Path, default=None)
    parser.add_argument("--vault-dir", type=Path, default=None)
    parser.add_argument("--documents-dir", type=Path, default=None)
    parser.add_argument("--wiki-dir", type=Path, default=None)
    parser.add_argument("--category", type=str, default=None)
    args = parser.parse_args()

    from src.config.paths import (
        get_documents_dir as _get_docs_dir,
        get_vault_dir,
    )

    root = args.root or get_project_root()
    rag = args.rag_dir or get_rag_dir()
    vault = args.vault_dir or get_vault_dir()
    documents = args.documents_dir or _get_docs_dir()
    wiki = args.wiki_dir or get_compiled_wiki_dir()

    if args.category:
        try:
            if args.category == "vault":
                if args.vault_dir is not None:
                    count = reindex_category(args.category, root, rag, vault_dir=vault, shared_vault_dir=None)
                else:
                    count = reindex_category(args.category, root, rag, vault_dir=vault)
            elif args.category == "documents":
                from src.lib.index.document_source_config import configured_document_sources

                count = index_document_sources(
                    configured_document_sources(project_root=root, documents_dir=documents),
                    rag,
                    project_root=root,
                )
            elif args.category == "wiki":
                if args.wiki_dir is not None:
                    count = reindex_category(args.category, root, rag, wiki_dir=wiki, shared_wiki_dir=None)
                else:
                    count = reindex_category(args.category, root, rag, wiki_dir=wiki)
            else:
                count = reindex_category(args.category, root, rag)
            print(f"Indexed {count} {args.category} entries")
        except ValueError:
            print(f"Unknown category: {args.category}")
    else:
        stats = reindex_all(root, rag, vault_dir=vault, documents_dir=documents)
        total = sum(stats.values())
        print(f"Indexed {total} entries across {len(stats)} categories")
        for cat, count in stats.items():
            print(f"  {cat}: {count}")
