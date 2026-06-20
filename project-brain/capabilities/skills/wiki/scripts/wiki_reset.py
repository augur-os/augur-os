"""Safe clean-slate wiki reset orchestration."""
from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config.paths import (
    get_documents_dir,
    get_project_root,
    get_rag_category_dir,
    get_rag_dir,
    get_runtime_dir,
    get_vault_dir,
    get_wiki_dir,
    resolve_wiki_dir,
)

from src.lib.index.unified_indexer import reindex_all, reindex_category
from src.lib.frontmatter_utils import parse_frontmatter

from src.config.paths import get_compiled_wiki_dir
try:
    from .wiki_concept_compiler import (
        prepare_extraction_batch,
        summarize_extraction_batch,
        write_extraction_batch_file,
    )
    from .wiki_concept_pages import write_wiki_index
    from .wiki_concept_state import STATE_FILENAME, WikiCompilerState
    from .wiki_maintenance import lint_wiki
    from .wiki_source_inventory import build_source_inventory
except ImportError:
    from wiki_concept_compiler import (
        prepare_extraction_batch,
        summarize_extraction_batch,
        write_extraction_batch_file,
    )
    from wiki_concept_pages import write_wiki_index
    from wiki_concept_state import STATE_FILENAME, WikiCompilerState
    from wiki_maintenance import lint_wiki
    from wiki_source_inventory import build_source_inventory


DEFAULT_SCOPE_SOURCE_LIMIT = 75


def _count_markdown_files(root: Path) -> int:
    path = Path(root)
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob("*.md"))


def _remove_tree(path: Path) -> bool:
    target = Path(path)
    if not target.exists():
        return False
    shutil.rmtree(target)
    return True


def _remove_file(path: Path) -> bool:
    target = Path(path)
    if not target.exists():
        return False
    target.unlink()
    return True


def _find_legacy_source_summary_pages(wiki_dir: Path) -> list[str]:
    topics_dir = Path(wiki_dir) / "topics"
    if not topics_dir.exists():
        return []

    matches: list[str] = []
    for path in sorted(topics_dir.glob("*.md")):
        try:
            metadata, _body = parse_frontmatter(path)
        except (OSError, ValueError):
            continue
        if str(metadata.get("page_type") or "").strip() != "source-summary":
            continue
        matches.append(path.relative_to(wiki_dir).as_posix())
    return matches


def _remove_legacy_source_summary_pages(wiki_dir: Path) -> list[str]:
    removed = _find_legacy_source_summary_pages(wiki_dir)
    for relative_path in removed:
        (Path(wiki_dir) / relative_path).unlink()
    return removed


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _effective_source_limit(*, full_compile: bool, source_limit: int, source_count: int) -> int:
    if source_limit > 0:
        return source_limit
    if full_compile:
        return source_count
    return DEFAULT_SCOPE_SOURCE_LIMIT


def run_concept_rebuild(
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    rag_dir: Path,
    source_limit: int = 0,
    full_compile: bool = False,
) -> dict[str, Any]:
    """Prepare an agent-action concept extraction batch without running an LLM."""
    sources = build_source_inventory(rag_dir=Path(rag_dir), wiki_dir=Path(wiki_dir))
    effective_limit = _effective_source_limit(
        full_compile=full_compile,
        source_limit=source_limit,
        source_count=len(sources),
    )
    batch = prepare_extraction_batch(
        sources,
        WikiCompilerState(),
        limit=effective_limit,
    )
    batch_file = write_extraction_batch_file(
        Path(runtime_wiki_dir),
        batch,
        mode="reset",
    )
    batch_summary = summarize_extraction_batch(batch, batch_file=batch_file)

    return {
        "status": "agent_action_required",
        "action": "wiki_concept_extraction",
        "instructions": [
            "Read full extraction prompts from batch_file and run them through an IDE/CLI agent.",
            "Return extraction payloads to the concept compiler apply step; Python reset does not call an LLM.",
            "The batch was built from a fresh compiler state after reset.",
        ],
        "source_count": len(sources),
        "batch_count": len(batch.items),
        "effective_source_limit": effective_limit,
        "runtime_state_path": str(Path(runtime_wiki_dir) / STATE_FILENAME),
        "batch_file": batch_summary["batch_file"],
        "batch_handle": batch_summary["batch_handle"],
        "batch_items": [
            {
                "source": item["source"],
                "prompt_handle": item["prompt_handle"],
                "prompt_preview": item["prompt_preview"],
                "prompt_length": item["prompt_length"],
            }
            for item in batch_summary["items"]
        ],
    }


def run_wiki_reset(
    *,
    full_compile: bool = False,
    source_limit: int = 0,
) -> dict[str, Any]:
    """Purge wiki and RAG artifacts, rebuild indexes, and bootstrap wiki again."""
    wiki_dir = resolve_wiki_dir()
    runtime_dir = get_runtime_dir()
    runtime_wiki_dir = runtime_dir / "wiki"
    compiled_wiki_dir = get_compiled_wiki_dir(wiki_dir)
    rag_dir = get_rag_dir()
    rag_wiki_dir = get_rag_category_dir("wiki")
    project_root = get_project_root()
    vault_dir = get_vault_dir()
    documents_dir = get_documents_dir()

    before = {
        "wiki_files": _count_markdown_files(compiled_wiki_dir),
        "rag_total_files": _count_markdown_files(rag_dir),
        "rag_wiki_files": _count_markdown_files(rag_wiki_dir),
    }
    legacy_source_summary_pages = _find_legacy_source_summary_pages(compiled_wiki_dir)
    legacy_sources_existed = (compiled_wiki_dir / "sources").exists()
    concept_compiler_state_existed = (runtime_wiki_dir / STATE_FILENAME).exists()

    removed = {
        "wiki": _remove_tree(compiled_wiki_dir),
        "runtime_wiki": _remove_tree(runtime_wiki_dir),
        "rag_wiki": _remove_tree(rag_wiki_dir),
        "rag": _remove_tree(rag_dir),
        "legacy_sources": legacy_sources_existed,
        "legacy_source_summary_pages": legacy_source_summary_pages,
        "concept_compiler_state": concept_compiler_state_existed,
    }

    rag_dir.mkdir(parents=True, exist_ok=True)
    rag_stats = reindex_all(
        project_root,
        rag_dir,
        vault_dir=vault_dir,
        documents_dir=documents_dir,
    )
    removed["legacy_sources"] = _remove_tree(compiled_wiki_dir / "sources") or bool(removed["legacy_sources"])
    removed["legacy_source_summary_pages"] = [
        *removed["legacy_source_summary_pages"],
        *[
            path
            for path in _remove_legacy_source_summary_pages(compiled_wiki_dir)
            if path not in removed["legacy_source_summary_pages"]
        ],
    ]
    removed["concept_compiler_state"] = (
        _remove_file(runtime_wiki_dir / STATE_FILENAME) or bool(removed["concept_compiler_state"])
    )

    index_path = write_wiki_index(compiled_wiki_dir, timestamp=_utc_timestamp())
    concept_rebuild = run_concept_rebuild(
        wiki_dir=wiki_dir,
        runtime_wiki_dir=runtime_wiki_dir,
        rag_dir=rag_dir,
        source_limit=source_limit,
        full_compile=full_compile,
    )
    wiki_indexed = reindex_category("wiki", project_root, rag_dir, wiki_dir=compiled_wiki_dir)
    lint = lint_wiki(wiki_dir=compiled_wiki_dir)
    after = {
        "wiki_files": _count_markdown_files(compiled_wiki_dir),
        "rag_total_files": _count_markdown_files(rag_dir),
        "rag_wiki_files": _count_markdown_files(rag_wiki_dir),
    }

    return {
        "before": before,
        "removed": removed,
        "rag_stats": rag_stats,
        "concept_rebuild": concept_rebuild,
        "index_path": str(index_path),
        "full_compile": bool(full_compile),
        "effective_source_limit": int(concept_rebuild.get("effective_source_limit", 0)),
        "wiki_indexed": wiki_indexed,
        "lint": lint,
        "after": after,
    }
