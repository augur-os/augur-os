"""reindex-project: Rebuild the master project index via unified_indexer.

Extracted from KnowledgeEnrichmentLoop._run_project_index_rebuild (ADR-200).
Updated to use unified_indexer.reindex_all() (replaces project_indexer.py).
Also regenerates reference indexes (ADR index, skill registry) that were
previously in nightly_maintainer.regenerate_indexes() — absorbed here after
the ADR-180 consolidation left them orphaned.
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
import subprocess
from pathlib import Path

from src.config.paths import get_all_client_skill_dirs, get_python_executable, get_rag_dir
from src.lib.adr_utils import get_adr_dir
from src.lib.frontmatter_utils import get_skill_config_sidecar
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "reindex-project"


def _latest_input_mtime(project_root: Path) -> float:
    latest = 0.0
    # Scan client skill dirs for SKILL.md plus any declared config sidecars.
    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_md in skills_dir.glob("*/SKILL.md"):
            try:
                latest = max(latest, skill_md.stat().st_mtime)
            except OSError:
                continue
            sidecar = get_skill_config_sidecar(skill_md)
            if sidecar and sidecar.exists():
                try:
                    latest = max(latest, sidecar.stat().st_mtime)
                except OSError:
                    continue
    # Also check ADRs — ADR-642: central JSON index is the freshness signal.
    adr_dir = get_adr_dir()
    if adr_dir.is_dir():
        central_index = adr_dir / "adrs-index.json"
        if central_index.is_file():
            try:
                latest = max(latest, central_index.stat().st_mtime)
            except OSError:
                pass
        for path in adr_dir.glob("ADR-*.md"):
            try:
                latest = max(latest, path.stat().st_mtime)
            except OSError:
                continue
    return latest


def scan(ctx: OpsContext) -> ScanResult:
    """Rebuild the project index only when relevant source metadata changed."""
    rag_dir = get_rag_dir()
    manifest_path = rag_dir / "_meta" / "manifest.yaml"
    latest_input = _latest_input_mtime(ctx.project_root)
    if manifest_path.exists() and manifest_path.stat().st_mtime >= latest_input:
        return ScanResult(
            issues=[],
            summary="Project index is current",
            severity="info",
        )

    return ScanResult(
        issues=[{
            "action": "rebuild-project-index",
            "category": "project-index-rebuild",
            "kind": "maintenance",
            "root_cause_type": "generated_artifact",
            "detail": "Project index is older than source metadata and needs rebuild",
            "path": str(manifest_path),
        }],
        summary="Project index refresh needed",
        severity="info",
    )


def _run_script(
    script: Path,
    ctx: OpsContext,
    timeout: int = 120,
    extra_args: list[str] | None = None,
) -> str | None:
    """Run a Python script, return error message or None on success."""
    result = subprocess.run(
        [str(get_python_executable()), str(script), *(extra_args or [])],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(ctx.project_root),
    )
    if result.returncode != 0:
        return result.stderr[:500].strip() or f"{script.name} exit {result.returncode}"
    return None


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Rebuild RAG index and regenerate reference indexes plus local Markdown inventory."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary="Dry run: would rebuild project index and reference indexes",
        )

    errors: list[str] = []

    # 1. RAG project index via unified_indexer.
    indexer_script = (
        ctx.project_root / "src" / "lib"
        / "index" / "unified_indexer.py"
    )
    if indexer_script.exists():
        index_timeout = int(ctx.config.get("index_timeout", 900))
        err = _run_script(
            indexer_script,
            ctx,
            timeout=index_timeout,
            extra_args=["--root", str(ctx.project_root)],
        )
        if err:
            errors.append(f"unified_indexer: {err}")
    else:
        try:
            indexer_display = indexer_script.relative_to(ctx.project_root).as_posix()
        except ValueError:
            indexer_display = indexer_script.as_posix()
        errors.append(f"unified_indexer.py not found at {indexer_display}")

    # 2. Reference indexes plus ignored local Markdown convenience output.
    ref_scripts = [
        ctx.project_root / ".github" / "scripts" / "generate_adr_index.py",
        ctx.project_root / ".github" / "scripts" / "generate_skill_registry.py",
    ]
    for script in ref_scripts:
        if not script.exists():
            continue
        err = _run_script(script, ctx, timeout=60)
        if err:
            errors.append(f"{script.stem}: {err}")

    if errors:
        return FixResult(
            success=False,
            summary="; ".join(errors),
        )

    return FixResult(
        success=True,
        summary="Project index and reference indexes rebuilt successfully",
    )
