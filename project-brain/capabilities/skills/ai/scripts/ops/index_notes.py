"""auto-index-notes: Detect and index unindexed notes files in skill data directories.

Extracted from KnowledgeEnrichmentLoop._scan_unindexed_notes / _rebuild_notes_cache (ADR-200).
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
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.config.paths import (
    get_managed_skill_source_dirs,
    get_python_executable,
    get_skill_data_dir,
    get_vault_dir,
)
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult
from src.lib.staged_skill_catalog import find_skill_file

name = "auto-index-notes"


def _vault_root() -> Path:
    """Resolve the vault root, preferring the live env override over cached paths."""
    env_vault = os.environ.get("AUGUR_VAULT")
    if env_vault:
        return Path(env_vault)
    return get_vault_dir()


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    """Stage specific paths and commit. Returns commit hash or None."""
    for p in paths:
        subprocess.run(
            ["git", "add", p],
            capture_output=True,
            cwd=str(project_root),
        )
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return None  # No changes to commit
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        return rev.stdout.strip() if rev.returncode == 0 else None
    return None


def _cache_path_for(notes_dir: Path) -> Path:
    """Return the canonical local cache file for a notes directory."""
    return notes_dir / "_index.cache.yaml"


def _build_minimal_notes_cache(notes_dir: Path) -> None:
    """Fallback minimal cache builder when notes_lib is unavailable."""
    entries = []
    for md_file in sorted(notes_dir.glob("*.md")):
        if md_file.name.startswith("_"):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Extract title from frontmatter or use stem
        title = md_file.stem
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                fm_text = content[3:end]
                for line in fm_text.splitlines():
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip("\"'")
                        break
        entries.append({
            "file": md_file.name,
            "title": title,
            "created": "",
            "source": "unknown",
            "skill": _infer_skill_name(notes_dir),
            "tags": [],
        })

    cp = _cache_path_for(notes_dir)
    cp.write_text(
        yaml.safe_dump(
            {
                "notes": entries,
                "count": len(entries),
                "updated": datetime.now(timezone.utc).isoformat(),
                "notes_dir": str(notes_dir),
            },
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _infer_skill_name(notes_dir: Path) -> str:
    """Infer the owning skill from either vault or repo-local notes paths."""
    for parent in notes_dir.parents:
        if parent.parent.name == "skills":
            return parent.name

    if notes_dir.parent.name and notes_dir.parent.name not in {"data", "augur"}:
        return notes_dir.parent.name

    return "unknown"


def _discover_notes_dirs(project_root: Path) -> list[tuple[str, Path]]:
    """Discover vault-backed notes directories for all known skills.

    Supports both the current flat vault layout (`vault/<skill>/notes`) and the
    older bundled layout (`vault/<bundle>/<skill>/notes`) still used by some
    tests and historical content.
    """
    discovered: list[tuple[str, Path]] = []
    skill_dirs: list[tuple[str, Path]] = []

    for managed_skills_dir in get_managed_skill_source_dirs(project_root):
        for skill_dir in sorted(managed_skills_dir.iterdir()):
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                skill_dirs.append(("canonical", skill_dir))

    legacy_plugins_dir = project_root / "plugins"
    if legacy_plugins_dir.exists():
        for skill_dir in sorted(legacy_plugins_dir.glob("*/skills/*")):
            if skill_dir.is_dir():
                skill_dirs.append((skill_dir.parent.parent.name, skill_dir))

    if not skill_dirs:
        return []

    for bundle_name, skill_dir in skill_dirs:
        if not skill_dir.is_dir():
            continue

        vault_root = _vault_root()

        for candidate in sorted(vault_root.glob(f"*/{skill_dir.name}/notes")):
            if candidate.is_dir():
                discovered.append((skill_dir.name, candidate))
                break
        else:
            direct_notes_dir = vault_root / skill_dir.name / "notes"
            if direct_notes_dir.is_dir():
                discovered.append((skill_dir.name, direct_notes_dir))
                continue

        try:
            notes_dir = get_skill_data_dir(skill_dir.name) / "notes"
        except Exception:
            notes_dir = Path()

        if notes_dir.is_dir():
            discovered.append((skill_dir.name, notes_dir))
            continue

        legacy_notes_dir = vault_root / bundle_name / skill_dir.name / "notes"
        if legacy_notes_dir.is_dir():
            discovered.append((skill_dir.name, legacy_notes_dir))

    return discovered


def scan(ctx: OpsContext) -> ScanResult:
    """Walk vault-backed notes directories and find dirs with unindexed .md files."""
    discovered = _discover_notes_dirs(ctx.project_root)
    if not discovered:
        return ScanResult(issues=[], summary="No notes directories found", severity="info")

    issues: list[dict] = []
    for skill_name, notes_dir in discovered:
        md_files = {
            f.name for f in notes_dir.glob("*.md")
            if not f.name.startswith("_")
        }
        if not md_files:
            continue

        # Read cached entries from platform cache dir
        cp = _cache_path_for(notes_dir)
        cached_files: set[str] = set()
        if cp.exists():
            try:
                cache_data = yaml.safe_load(cp.read_text()) or {}
                cached_files = {
                    entry.get("file", "")
                    for entry in cache_data.get("notes", [])
                }
            except Exception:
                pass

        unindexed = md_files - cached_files
        if unindexed:
            issues.append({
                "action": f"index-notes-{skill_name}",
                "category": "index-new-files",
                "kind": "maintenance",
                "skill": skill_name,
                "path": str(notes_dir),
                "unindexed_count": len(unindexed),
            })

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} notes dir(s) with unindexed files",
        severity="info",
    )


def _resolve_notes_lib_path(project_root: Path) -> Path | None:
    return find_skill_file(project_root, "apple", "scripts", "notes_lib.py")


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Rebuild note index caches for each notes directory with unindexed files.

    Caches are written to the platform cache dir, not the vault.
    """
    if ctx.dry_run:
        skills = [i.get("skill", "?") for i in issues]
        return FixResult(
            success=True,
            summary=f"Dry run: would index notes for {', '.join(skills)}",
        )

    notes_lib_path = _resolve_notes_lib_path(ctx.project_root)

    all_actions: list[dict] = []
    failed: list[str] = []

    for issue in issues:
        notes_dir = Path(issue.get("path", ""))
        skill_name = issue.get("skill", "unknown")

        if not notes_dir.exists():
            failed.append(f"{skill_name}(dir not found)")
            continue

        if notes_lib_path is not None and notes_lib_path.exists():
            # Use notes_lib.write_index_cache via subprocess to avoid import-path issues
            result = subprocess.run(
                [
                    str(get_python_executable()), "-c",
                    f"import sys; sys.path.insert(0, {str(notes_lib_path.parent)!r}); "
                    f"sys.path.insert(0, {str(ctx.project_root)!r}); "
                    f"from notes_lib import write_index_cache; "
                    f"from pathlib import Path; "
                    f"write_index_cache(Path({str(notes_dir)!r}))",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(ctx.project_root),
            )
            if result.returncode != 0:
                failed.append(f"{skill_name}({result.stderr[:200].strip()})")
                continue
        else:
            # Fallback: build minimal cache inline
            try:
                _build_minimal_notes_cache(notes_dir)
            except Exception as e:
                failed.append(f"{skill_name}({e})")
                continue

        # Caches now live in platform cache dir, no vault commit needed
        all_actions.append({"skill": skill_name, "commit": None})

    success = len(failed) == 0
    indexed = len(all_actions)
    summary_parts = [f"Indexed notes for {indexed} skill(s)"]
    if failed:
        summary_parts.append(f"failed: {', '.join(failed)}")

    return FixResult(
        success=success,
        actions=all_actions,
        summary="; ".join(summary_parts),
    )
