"""
sync_agents/vault.py

Vault and memory sync logic for the sync_agents package.

Contains:
    - _run_memory_assembler(): Multi-client memory assembler.
    - _get_all_vault_adapters(): Lazy-load vault adapter instances.
    - sync_vaults(): Orchestrate vault adapter sync (ADR-436).
"""

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
import sys

from src.lib.brain_memory_tiers import resolve_memory_write_brain_target
from src.lib.brain_stack import resolve_active_stack

from .constants import (
    PROJECT_ROOT,
    logger,
)


def _candidate_project_roots() -> list:
    """Project roots whose client memory dirs feed the review queue.

    Client-native memory is keyed to the repo path the client ran in, so in a
    worktree the live memory lives under the main checkout (``main_repo`` in
    ``.augur-worktree.yaml``). Scan both so the count is honest from anywhere.
    """
    roots = [PROJECT_ROOT]
    marker = PROJECT_ROOT / ".augur-worktree.yaml"
    if marker.is_file():
        try:
            import yaml

            data = yaml.safe_load(marker.read_text(encoding="utf-8")) or {}
            main_repo = data.get("main_repo")
            if main_repo:
                roots.append(_AugurPath(str(main_repo)))
        except Exception:
            pass
    return roots


def _feed_memory_review_queue() -> None:
    """Surface client-native memory as review candidates (ADR-772).

    Client memory is *input*, not canonical state. Per ADR-772 the sync no longer
    auto-promotes raw client memory into a brain's ``memory/entries/``; instead
    candidate facts await explicit approval at ``/workspace/memory-review``. This
    step reports how many candidates are pending so the gate stays visible. The
    per-adapter ``sync_memory()`` calls still project *approved* canonical memory
    back to clients (ADR-771), so cross-client compounding is preserved — only
    the unreviewed auto-import is removed.
    """
    try:
        assembler_dir = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "ai" / "scripts" / "ops"
        if str(assembler_dir) not in sys.path:
            sys.path.insert(0, str(assembler_dir))
        from memory_assembler import collect_review_candidates

        from src.lib.memory_review import build_queue

        candidates = collect_review_candidates(_candidate_project_roots())
        if not candidates:
            logger.info("Memory review: no client memory candidates found")
            return

        target = _resolve_memory_review_target(PROJECT_ROOT)
        snapshot = build_queue(target=target, client_candidates=candidates)
        counts = snapshot["counts"]
        logger.info(
            "Memory review: %d pending, %d already promoted (brain=%s) — review at /workspace/memory-review",
            counts["pending"],
            counts["promoted"],
            target.brain.id,
        )
    except Exception as e:
        logger.error("Memory review queue refresh failed: %s", e)


def _resolve_memory_review_target(project_root: _AugurPath):
    target = resolve_memory_write_brain_target(resolve_active_stack(cwd=project_root))
    if target is None:
        raise RuntimeError("no writable memory tier available for memory review")
    return target


# Back-compat alias: older callers referenced the auto-promoting name. The
# behavior is now review-feeding (no canonical auto-writes) per ADR-772.
_run_memory_assembler = _feed_memory_review_queue


def _get_all_vault_adapters():
    """Lazily import and instantiate all vault adapters (ADR-436)."""
    from .vault_adapters.obsidian import ObsidianVaultAdapter

    return [
        ObsidianVaultAdapter(),
    ]


def sync_vaults() -> int:
    """Orchestrate vault adapter sync (ADR-436).

    Discovers and runs all vault adapters. Each adapter syncs
    bidirectionally between Augur and its vault tool.

    Returns:
        Total number of files synced across all vault adapters.
    """
    total = 0
    vault_adapters = _get_all_vault_adapters()

    for adapter in vault_adapters:
        name = adapter.__class__.__name__
        if not adapter.detect_installed():
            logger.info(f"Vault adapter {name} not installed, skipping")
            continue
        try:
            from_vault = adapter.sync_from_vault()
            if from_vault:
                logger.info(f"Read {sum(len(v) for v in from_vault.values())} items from {name}")
            written = adapter.sync_to_vault(from_vault)
            total += written
        except Exception as e:
            logger.error(f"Failed vault sync for {name}: {e}")

    if total:
        logger.info(f"Vault sync complete: {total} files written")
    return total
