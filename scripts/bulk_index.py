"""Bulk RAG index — delegates to unified_indexer.reindex_all()."""

import importlib
import sys
from pathlib import Path

# Ensure project root is on sys.path for src imports
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _load_unified_indexer():
    """Import the canonical unified_indexer as a real package module so its
    relative imports (`.document_understanding`, `.bm25_index`, etc.) resolve."""
    return importlib.import_module("src.lib.index.unified_indexer")


def main():
    from src.config.paths import get_project_root, get_rag_dir

    root = get_project_root()
    rag_dir = get_rag_dir()

    try:
        from src.config.paths import get_vault_dir, get_documents_dir
        vault = get_vault_dir()
        documents = get_documents_dir()
    except ImportError:
        vault = None
        documents = None

    unified_indexer = _load_unified_indexer()

    print(f"Running unified reindex from {root}...")
    stats = unified_indexer.reindex_all(root, rag_dir, vault_dir=vault, documents_dir=documents)
    total = sum(stats.values())
    print(f"Indexed {total} entries across {len(stats)} categories")
    for cat, count in stats.items():
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
