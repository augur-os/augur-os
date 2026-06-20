#!/usr/bin/env python3
"""
Standalone indexing script for Document-to-Skill wizard.
Indexes documents with progress tracking via metadata file updates.
"""

import os
import sys
from pathlib import Path


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add plugins to path
try:
    from src.config.paths import get_project_root
    REPO_ROOT = get_project_root()
except ImportError:
    REPO_ROOT = Path(__file__).parent.parent.parent.parent  # fallback
PACKAGES_DIR = REPO_ROOT / 'plugins'
sys.path.insert(0, str(PACKAGES_DIR))
sys.path.insert(0, str(REPO_ROOT))

from horizontal.memory.local_rag.services.index_service import DocumentIndexer  # noqa: E402


def main():
    if len(sys.argv) < 3:
        _out("Usage: python run_indexing.py <folder_path> <project_id>", file=sys.stderr)
        sys.exit(1)

    folder_path = sys.argv[1]
    project_id = sys.argv[2]

    # Set environment variable for progress tracking
    os.environ['AUGUR_RAG_PROJECT_ID'] = project_id

    # Determine data directory
    data_root = os.environ.get('AUGUR_ROOT') or str(Path.home() / 'Projects' / 'augur')

    user_data_dir = str(Path(data_root) / 'local-rag' / 'projects' / project_id)

    _out(f"Indexing: {folder_path}")
    _out(f"Project ID: {project_id}")
    _out(f"Data directory: {user_data_dir}")

    try:
        # Create indexer
        indexer = DocumentIndexer(
            user_data_dir=user_data_dir,
        )

        # Index directory
        stats = indexer.index_directory(Path(folder_path), force=False)

        # Print stats
        _out("\n" + "=" * 50)
        _out("Indexing Complete!")
        _out("=" * 50)
        _out(f"Files processed: {stats['files_processed']}")
        _out(f"Files skipped: {stats['files_skipped']}")
        _out(f"Chunks created: {stats['chunks_created']}")
        _out(f"Errors: {stats['errors']}")

    except Exception as e:
        _out(f"ERROR: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
