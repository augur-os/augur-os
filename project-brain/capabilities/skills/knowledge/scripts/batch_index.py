#!/usr/bin/env python3
"""
Batch Document Indexing Script

Batch index multiple folders/files for markdown RAG.
Designed for integration with chains and workflows.

Usage:
    python3 project-brain/capabilities/skills/knowledge/scripts/batch_index.py --folders /path1 /path2 --project my_project
    python3 project-brain/capabilities/skills/knowledge/scripts/batch_index.py --config batch_config.yaml
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _ensure_project_paths(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            for path in (candidate / "src" / "mcp", candidate, candidate / "project-brain"):
                text = str(path)
                if text not in sys.path:
                    sys.path.insert(0, text)
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


project_root = _ensure_project_paths(Path(__file__).resolve())
from src.logging import get_entity_logger  # noqa: E402

logger = get_entity_logger("rag.batch")


def _load_indexing_backends():
    """Load optional indexing backends without legacy plugin package paths."""
    try:
        from skills.knowledge.src.features.master_index import MasterIndex  # type: ignore
        from skills.knowledge.src.indexer import MarkdownIndexer  # type: ignore
        return MasterIndex, MarkdownIndexer
    except Exception:
        return None, None


def load_batch_config(config_path: Path) -> dict[str, Any]:
    """Load batch indexing configuration from YAML file

    Example config.yaml:
        project: my_project
        ocr_enabled: true
        ocr_language: eng
        folders:
          - /path/to/docs
          - /path/to/more/docs
        recursive: true
        rebuild_master: true
    """
    import yaml

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config


def batch_index_folders(
    folders: list[Path],
    project: str = "augur_global",
    ocr_enabled: bool = False,
    ocr_language: str = "eng",
    recursive: bool = True,
    mode: str = "full",
    rebuild_master: bool = True,
    progress_callback=None,
    warning_callback=None,
) -> dict[str, Any]:
    """Batch index multiple folders

    Args:
        folders: List of folder paths to index
        project: Project name for indexing
        ocr_enabled: Enable OCR for PDFs/images
        ocr_language: OCR language (default: eng)
        recursive: Recurse into subdirectories
        mode: Indexing mode (full or incremental)
        rebuild_master: Rebuild master index after indexing
        progress_callback: Optional progress callback
        warning_callback: Optional warning callback

    Returns:
        Dictionary with indexing statistics and results
    """
    MasterIndex, MarkdownIndexer = _load_indexing_backends()
    if MarkdownIndexer is None:
        raise RuntimeError("Knowledge indexing backends are unavailable in the canonical skill tree")

    indexer = MarkdownIndexer()

    results = {
        "project": project,
        "folders": [],
        "total_indexed": 0,
        "total_skipped": 0,
        "total_failed": 0,
        "started_at": time.time(),
        "completed_at": None,
        "duration_seconds": None,
    }

    # Index each folder
    for i, folder in enumerate(folders, 1):
        logger.info(f"\n[{i}/{len(folders)}] Indexing folder: {folder}")

        if not folder.exists():
            logger.warning(f"Folder not found, skipping: {folder}")
            results["folders"].append(
                {"path": str(folder), "status": "skipped", "reason": "not_found", "indexed_count": 0}
            )
            results["total_skipped"] += 1
            continue

        if not folder.is_dir():
            logger.warning(f"Path is not a directory, skipping: {folder}")
            results["folders"].append(
                {"path": str(folder), "status": "skipped", "reason": "not_directory", "indexed_count": 0}
            )
            results["total_skipped"] += 1
            continue

        try:
            # Index this folder
            indexed_paths = indexer.index_directory(
                folder,
                project,
                recursive=recursive,
                ocr_enabled=ocr_enabled,
                mode=mode,
                progress_callback=progress_callback,
                warning_callback=warning_callback,
            )

            results["folders"].append({"path": str(folder), "status": "success", "indexed_count": len(indexed_paths)})
            results["total_indexed"] += len(indexed_paths)

            logger.info(f"✓ Indexed {len(indexed_paths)} files from {folder}")

        except Exception as e:
            logger.error(f"✗ Failed to index {folder}: {e}", exc_info=True)
            results["folders"].append({"path": str(folder), "status": "failed", "error": str(e), "indexed_count": 0})
            results["total_failed"] += 1

    # Rebuild master index if requested
    if rebuild_master:
        logger.info("\nRebuilding master index...")
        try:
            if MasterIndex is None:
                raise RuntimeError("Master index backend is unavailable in the canonical skill tree")
            master = MasterIndex()
            master.rebuild()
            logger.info("✓ Master index rebuilt")
            results["master_index_rebuilt"] = True
        except Exception as e:
            logger.error(f"✗ Failed to rebuild master index: {e}", exc_info=True)
            results["master_index_rebuilt"] = False
            results["master_index_error"] = str(e)

    # Calculate duration
    results["completed_at"] = time.time()
    results["duration_seconds"] = results["completed_at"] - results["started_at"]

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Batch document indexing for markdown RAG", formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--folders", nargs="+", help="Folder paths to index")
    parser.add_argument("--project", default="augur_global", help="Project name (default: augur_global)")
    parser.add_argument("--ocr", action="store_true", default=False, help="Enable OCR for PDFs/images")
    parser.add_argument("--ocr-language", default="eng", help="OCR language (default: eng)")
    parser.add_argument(
        "--recursive", action="store_true", default=True, help="Recurse into subdirectories (default: true)"
    )
    parser.add_argument(
        "--no-recursive", dest="recursive", action="store_false", help="Don't recurse into subdirectories"
    )
    parser.add_argument("--mode", choices=["full", "incremental"], default="full", help="Indexing mode (default: full)")
    parser.add_argument(
        "--rebuild-master",
        action="store_true",
        default=True,
        help="Rebuild master index after indexing (default: true)",
    )
    parser.add_argument(
        "--no-rebuild-master", dest="rebuild_master", action="store_false", help="Don't rebuild master index"
    )
    parser.add_argument("--config", type=Path, help="Load configuration from YAML file")
    parser.add_argument("--json-output", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    # Load config from file if provided
    if args.config:
        logger.info(f"Loading configuration from: {args.config}")
        config = load_batch_config(args.config)

        folders = [Path(f).expanduser().resolve() for f in config.get("folders", [])]
        project = config.get("project", "augur_global")
        ocr_enabled = config.get("ocr_enabled", False)
        ocr_language = config.get("ocr_language", "eng")
        recursive = config.get("recursive", True)
        mode = config.get("mode", "full")
        rebuild_master = config.get("rebuild_master", True)

    elif args.folders:
        folders = [Path(f).expanduser().resolve() for f in args.folders]
        project = args.project
        ocr_enabled = args.ocr
        ocr_language = args.ocr_language
        recursive = args.recursive
        mode = args.mode
        rebuild_master = args.rebuild_master

    else:
        parser.error("Either --folders or --config must be provided")

    # Validate folders
    if not folders:
        logger.error("No folders provided for indexing")
        return 1

    logger.info("=" * 60)
    logger.info("BATCH DOCUMENT INDEXING")
    logger.info("=" * 60)
    logger.info(f"Project: {project}")
    logger.info(f"Folders: {len(folders)}")
    for folder in folders:
        logger.info(f"  - {folder}")
    logger.info(f"OCR Enabled: {ocr_enabled}")
    if ocr_enabled:
        logger.info(f"OCR Language: {ocr_language}")
    logger.info(f"Recursive: {recursive}")
    logger.info(f"Mode: {mode}")
    logger.info(f"Rebuild Master: {rebuild_master}")
    logger.info("=" * 60)

    # Progress callback
    def progress_callback(current: int, total: int, filename: str):
        percent = int(current / total * 100) if total > 0 else 0
        logger.info(f"  [{current}/{total}] ({percent}%) {filename}")

    # Warning callback
    def warning_callback(message: str, severity: str):
        logger.warning(f"  [{severity}] {message}")

    # Execute batch indexing
    results = batch_index_folders(
        folders,
        project=project,
        ocr_enabled=ocr_enabled,
        ocr_language=ocr_language,
        recursive=recursive,
        mode=mode,
        rebuild_master=rebuild_master,
        progress_callback=progress_callback,
        warning_callback=warning_callback,
    )

    # Output results
    logger.info("\n" + "=" * 60)
    logger.info("BATCH INDEXING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total Indexed: {results['total_indexed']} files")
    logger.info(f"Total Skipped: {results['total_skipped']} folders")
    logger.info(f"Total Failed: {results['total_failed']} folders")
    logger.info(f"Duration: {results['duration_seconds']:.2f} seconds")

    if results["total_failed"] > 0:
        logger.warning("\nFailed folders:")
        for folder_result in results["folders"]:
            if folder_result["status"] == "failed":
                logger.warning(f"  - {folder_result['path']}: {folder_result.get('error', 'Unknown error')}")

    if args.json_output:
        _out(json.dumps(results, indent=2))

    # Return exit code based on results
    if results["total_failed"] > 0:
        return 1  # Partial failure
    elif results["total_indexed"] == 0:
        return 1  # No files indexed
    else:
        return 0  # Success


if __name__ == "__main__":
    sys.exit(main())
