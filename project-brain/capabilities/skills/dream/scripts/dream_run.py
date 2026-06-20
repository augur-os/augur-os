"""Ledger-backed dream-cycle runner.

Runs the deterministic dream phases in-process and records each umbrella run as
a ``kind=dream`` ADR-743 job so ``aug dream status`` has real history.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILLS_DIR = Path(__file__).resolve().parents[2]

import sys

for _path in (
    _SCRIPT_DIR,
    _SKILLS_DIR / "daemon" / "scripts",
    _SKILLS_DIR / "graph" / "scripts",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from job_ledger import job_record
from job_ledger.ledger import run as ledger_run


_PHASE_KINDS: dict[str, str] = {
    "orphans": "deterministic",
    "dead-citations": "deterministic",
    "cache-gc": "deterministic",
    "tier-recompute": "deterministic",
    "stale-pages": "judgment",
    "pattern-extraction": "judgment",
    "merge-candidates": "judgment",
}


def dream_run(
    *,
    vault_root: Path,
    cache_root: Path,
    report_output_root: Path,
    iterations: int = 1,
    cache_gc_dry_run: bool = False,
) -> dict[str, Any]:
    """Run one or more dream cycles and record each in the job ledger."""
    if iterations < 1:
        raise ValueError("iterations must be >= 1")

    runs = [
        _dream_run_once(
            vault_root=vault_root,
            cache_root=cache_root,
            report_output_root=report_output_root,
            cache_gc_dry_run=cache_gc_dry_run,
        )
        for _ in range(iterations)
    ]
    return {"count": len(runs), "runs": runs}


def _dream_run_once(
    *,
    vault_root: Path,
    cache_root: Path,
    report_output_root: Path,
    cache_gc_dry_run: bool,
) -> dict[str, Any]:
    config = _load_config()
    phases_cfg = config.get("phases") if isinstance(config.get("phases"), dict) else {}
    phase_order = list(phases_cfg.get("order") or [])
    skipped = set(phases_cfg.get("skips") or [])

    with ledger_run(
        kind="dream",
        name="dream-cycle",
        args={"phase_count": len(phase_order), "cache_gc_dry_run": cache_gc_dry_run},
        timeout_s=3600,
        submitter="dream",
    ) as job:
        job_id = Path(job.job_dir).name if job.job_dir else None
        phase_results: list[dict[str, Any]] = []

        for phase_id in phase_order:
            if phase_id in skipped:
                phase_results.append({
                    "id": phase_id,
                    "kind": _PHASE_KINDS.get(phase_id, "unknown"),
                    "state": "skipped",
                    "result": {"reason": "configured skip"},
                })
                continue

            job.phase(phase_id)
            try:
                result = _execute_phase(
                    phase_id,
                    config=config,
                    vault_root=vault_root,
                    cache_root=cache_root,
                    cache_gc_dry_run=cache_gc_dry_run,
                )
                phase_results.append({
                    "id": phase_id,
                    "kind": _PHASE_KINDS.get(phase_id, "unknown"),
                    "state": "complete",
                    "result": result,
                })
                job.log(f"{phase_id}: complete")
            except Exception as exc:  # noqa: BLE001 - one phase must not block the run
                phase_results.append({
                    "id": phase_id,
                    "kind": _PHASE_KINDS.get(phase_id, "unknown"),
                    "state": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                job.log(f"{phase_id}: failed: {type(exc).__name__}: {exc}")

        job.phase("report")
        import dream_report

        report_path = dream_report.dream_report_write(
            phase_results={"job_id": job_id, "phases": phase_results},
            output_root=report_output_root,
        )
        job.log(f"report: {report_path}")

        return {
            "job_id": job_id,
            "state": "complete",
            "report_path": str(report_path),
            "phases": phase_results,
        }


def _load_config() -> dict[str, Any]:
    import dream_config

    return dream_config.dream_config()


def _execute_phase(
    phase_id: str,
    *,
    config: dict[str, Any],
    vault_root: Path,
    cache_root: Path,
    cache_gc_dry_run: bool,
) -> dict[str, Any]:
    if phase_id == "orphans":
        import aggregators

        cfg = config.get("orphans") if isinstance(config.get("orphans"), dict) else {}
        return aggregators.dream_orphans(
            vault_root=vault_root,
            cache_root=cache_root,
            max_timeline_entries=int(cfg.get("max_timeline_entries", 3)),
        )
    if phase_id == "dead-citations":
        import dead_citations

        return dead_citations.dream_dead_citations(vault_root=vault_root, cache_root=cache_root)
    if phase_id == "cache-gc":
        import cache_gc

        cfg = config.get("cache_gc") if isinstance(config.get("cache_gc"), dict) else {}
        return cache_gc.dream_cache_gc(
            cache_root=cache_root,
            retention_days=int(cfg.get("retention_days", 30)),
            paths=list(cfg.get("paths") or []),
            dry_run=cache_gc_dry_run,
        )
    if phase_id == "tier-recompute":
        import graph_ops

        tiers = graph_ops.recompute_tiers()
        return {"entities": len(tiers)}
    if phase_id == "stale-pages":
        import aggregators

        cfg = config.get("stale_pages") if isinstance(config.get("stale_pages"), dict) else {}
        return aggregators.dream_stale_pages(
            vault_root=vault_root,
            gap_days=int(cfg.get("gap_days", 14)),
        )
    if phase_id == "merge-candidates":
        import aggregators

        return aggregators.dream_merge_candidates(vault_root=vault_root)
    if phase_id == "pattern-extraction":
        return {
            "proposal_required": True,
            "note": "Inline client judgment phase; no deterministic Augur write.",
        }
    return {"skipped": f"no deterministic implementation for {phase_id}"}


__all__ = ["dream_run"]
