"""reindex-rag: Rebuild centralized RAG indices for skills with markdown content."""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
from pathlib import Path

from src.config.paths import (
    get_all_client_skill_dirs,
    get_rag_dir,
    get_skill_data_dir,
)
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "reindex-rag"

IGNORED_PARTS = {".git", "node_modules", "__pycache__", ".next", "dist", "build"}


def _iter_markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    results: list[Path] = []
    for path in root.rglob("*.md"):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        results.append(path)
    return results


def _newest_source_mtime(project_root: Path) -> tuple[float, int]:
    """Return (newest source markdown mtime, files scanned) across all skills.

    Covers every client skill dir plus each skill's data dir. This is the
    freshness signal the incremental reindex (fix) actually consumes — the
    unified indexer rebuilds the whole central index in one pass, so a single
    aggregate check is correct and avoids the per-skill phantom-dir trap.
    """
    newest = 0.0
    count = 0
    for skills_dir in get_all_client_skill_dirs(project_root):
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            content_files = _iter_markdown_files(skill_dir)
            try:
                content_files.extend(_iter_markdown_files(get_skill_data_dir(skill_dir.name)))
            except ValueError:
                pass
            for path in content_files:
                try:
                    newest = max(newest, path.stat().st_mtime)
                except OSError:
                    continue
                count += 1
    return newest, count


def _newest_rag_mtime() -> float | None:
    """Newest file mtime in the central RAG output, or None if missing/empty.

    The unified indexer writes content-type subtrees (skills/, vault/, …) under
    a single central dir — never per-skill-name dirs — so freshness is measured
    against that central output, not against ``get_rag_dir() / <skill>``.
    """
    try:
        rag_dir = get_rag_dir()
    except ValueError:
        return None
    if not rag_dir.exists():
        return None
    newest: float | None = None
    for path in rag_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest:
            newest = mtime
    return newest


def scan(ctx: OpsContext) -> ScanResult:
    newest_source, n_files = _newest_source_mtime(ctx.project_root)
    newest_rag = _newest_rag_mtime()

    is_stale = newest_rag is None or (n_files > 0 and newest_source > newest_rag)
    if not is_stale:
        return ScanResult(
            issues=[],
            summary="Centralized RAG index is current",
            severity="info",
            items_scanned=n_files,
        )

    reason = (
        "Centralized RAG index is missing or empty"
        if newest_rag is None
        else "Source markdown is newer than the centralized RAG index"
    )
    return ScanResult(
        issues=[
            {
                "action": "rag-reindex",
                "category": "rag-reindex",
                "kind": "maintenance",
                "root_cause_type": "generated_artifact",
                "path": str(get_rag_dir()),
                "detail": reason,
            }
        ],
        summary="Centralized RAG index refresh needed",
        severity="info",
        items_scanned=n_files,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        skills = [issue.get("skill", "?") for issue in issues]
        return FixResult(
            success=True,
            summary=f"Dry run: would reindex {len(skills)} skill(s): {', '.join(skills)}",
        )

    # Delegate to src.lib.index.reindex_all() — single pass over all categories.
    # RAG output lives at ~/Library/Application Support/Augur/rag/ (outside repo),
    # so no git staging is needed.
    try:
        from src.config.paths import get_rag_dir
        from src.lib import index as index_lib

        try:
            from src.config.paths import get_vault_dir, get_documents_dir
            vault = get_vault_dir()
            documents = get_documents_dir()
        except ImportError:
            vault = None
            documents = None

        stats = index_lib.reindex_all(ctx.project_root, get_rag_dir(), vault, documents)
        total = sum(stats.values())
        return FixResult(
            success=True,
            actions=[{"stats": stats, "total": total}],
            summary=f"Unified reindex complete: {total} entries across {len(stats)} categories",
        )
    except Exception as e:
        return FixResult(success=False, summary=f"Unified reindex failed: {e}")
