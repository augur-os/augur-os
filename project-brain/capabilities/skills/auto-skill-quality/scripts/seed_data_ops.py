"""auto-seed-data: Seed template data for skills with empty data directories.

Scans for skills that have seed templates in assets/seeds/. Packaged seeds stay
in source and are served through the vault-first fallback path; fixes remove
empty seed scaffolds or create assets/seeds templates when vault data is empty.
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
from pathlib import Path

import yaml

from src.config.paths import get_all_client_skill_dirs, get_skill_data_dir
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-seed-data"

DIFFICULTY_SPEC = {
    0: "Surface check — count skills with seed dirs",
    1: "Content check — list skills with seed templates",
    2: "Deep check — report skills with empty data dirs but no seed templates",
    3: "Exhaustive — validate seed files against MCP tool schema",
}


def _display_path(path: Path, project_root: Path) -> str:
    """Render a project-relative path when possible, otherwise absolute."""
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def _find_seedable_skills(project_root: Path) -> list[dict]:
    """Find skills with seed directories.

    Scans both legacy augur/seed/ and canonical assets/seeds/ locations.
    Seeds are read from plugin source via SkillDataStore fallback — no vault copy needed.
    """
    results = []
    seen_skills: set[str] = set()
    seed_globs = [
        "*/augur/seed",
        "*/assets/seeds",
    ]
    for skills_dir in get_all_client_skill_dirs(project_root):
        for seed_glob in seed_globs:
            for seed_dir in sorted(skills_dir.glob(seed_glob)):
                if not seed_dir.is_dir():
                    continue
                # Navigate to skill dir: augur/seed -> augur -> skill, or assets/seeds -> assets -> skill
                skill_dir = seed_dir.parent.parent
                if str(skill_dir) in seen_skills:
                    continue
                seen_skills.add(str(skill_dir))

                data_dir = get_skill_data_dir(skill_dir.name)
                skill_md = skill_dir / "SKILL.md"

                # Load manifest if exists
                manifest_file = seed_dir / "_seed.yaml"
                manifest = None
                if manifest_file.exists():
                    try:
                        manifest = yaml.safe_load(manifest_file.read_text())
                    except Exception:
                        pass

                # Determine target data path
                target_dir = data_dir
                if manifest and manifest.get("data_path"):
                    target_dir = data_dir / manifest["data_path"]

                # Check if vault copy has data (informational only)
                has_data = False
                if target_dir.exists():
                    data_files = [
                        f for f in target_dir.rglob("*")
                        if f.is_file() and f.name != ".gitkeep"
                    ]
                    has_data = len(data_files) > 0

                # Check if seed dir has actual seed files (not just the manifest)
                seed_files = [
                    f for f in seed_dir.rglob("*")
                    if f.is_file() and f.name != "_seed.yaml" and f.name != ".gitkeep"
                ]
                has_seed_files = len(seed_files) > 0

                results.append({
                    "skill_dir": _display_path(skill_dir, project_root),
                    "seed_dir": _display_path(seed_dir, project_root),
                    "target_dir": _display_path(target_dir, project_root),
                    "manifest": manifest,
                    "has_data": has_data,
                    "has_seed_files": has_seed_files,
                    "skill_md": _display_path(skill_md, project_root),
                })
    return results


def _find_empty_data_skills(project_root: Path) -> list[dict]:
    """Find skills with data_paths declared but empty data directories."""
    results = []
    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue

            data_dir = get_skill_data_dir(skill_dir.name)
            has_seed = (skill_dir / "augur" / "seed").exists() or (skill_dir / "assets" / "seeds").exists()

            if not data_dir.exists():
                continue
            if has_seed:
                continue  # Has seed dir — handled by _find_seedable_skills

            data_files = [
                f for f in data_dir.rglob("*")
                if f.is_file() and f.name != ".gitkeep" and not f.name.startswith(".")
            ]
            if len(data_files) == 0:
                results.append({
                    "skill_dir": _display_path(skill_dir, project_root),
                    "data_dir": _display_path(data_dir, project_root),
                })
    return results


def scan(ctx: OpsContext) -> ScanResult:
    """Scan for skills with seed templates (informational — seeds read from plugin source via fallback)."""
    seedable = _find_seedable_skills(ctx.project_root)

    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary=f"{len(seedable)} skills with seed/ dirs (seeds served from plugin source via fallback, d0 surface)",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []
    working_count = 0

    # d1: only report skills where seed dir exists but has NO actual seed files
    # (empty seed dir = broken fallback). Skills with seed files work correctly
    # via SkillDataStore._resolve_read_path() fallback — not issues.
    # Skip skills outside the project root (plugin cache copies).
    for skill in seedable:
        if _is_external_path(skill["skill_dir"], ctx.project_root):
            continue  # Skip external plugin cache copies
        if skill["has_seed_files"]:
            # Seed files present — fallback path works, not an issue
            working_count += 1
            continue
        # Seed dir exists but is empty — fallback will also fail
        issues.append({
            "type": "needs_seeding",
            "kind": "actionable",
            "skill_dir": skill["skill_dir"],
            "seed_dir": skill["seed_dir"],
            "target_dir": skill["target_dir"],
            "manifest": skill["manifest"],
            "has_vault_data": skill["has_data"],
            "detail": (
                f"Skill {skill['skill_dir']} has empty seed dir {skill['seed_dir']} "
                f"— no seed files and no vault data, fallback will fail"
            ),
        })

    # d2: skills with empty data but no seed templates
    if ctx.difficulty >= 2:
        empty_no_seed = _find_empty_data_skills(ctx.project_root)
        for skill in empty_no_seed:
            issues.append({
                "type": "needs_seed_templates",
                "kind": "actionable",
                "skill_dir": skill["skill_dir"],
                "data_dir": skill["data_dir"],
                "detail": f"Skill {skill['skill_dir']} has empty data dir but no seed/ templates",
            })

    severity = "warning" if issues else "info"
    health = "degraded" if issues else "verified"

    return ScanResult(
        issues=issues,
        summary=(
            f"{working_count} skill(s) with seed data served via fallback (ok); "
            f"{len(issues)} issue(s) with missing/empty seed data"
        ),
        severity=severity,
        health=health,
    )


def _create_seed_scaffold(skill_dir_rel: str, project_root: Path) -> list[str]:
    """Create a minimal assets/seeds/ scaffold for a skill with empty data.

    Creates:
    - assets/seeds/_seed.yaml manifest with default config
    - assets/seeds/.gitkeep placeholder

    Returns list of created file paths (project-relative).
    """
    skill_path = project_root / skill_dir_rel
    if not skill_path.is_dir():
        return []

    seeds_dir = skill_path / "assets" / "seeds"
    seeds_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skill_name = skill_path.name

    # Create _seed.yaml manifest
    manifest_path = seeds_dir / "_seed.yaml"
    if not manifest_path.exists():
        manifest_content = (
            f"# Seed manifest for {skill_name}\n"
            f"# Place seed data files in this directory alongside this manifest.\n"
            f"# They will be served via SkillDataStore fallback when vault data is empty.\n"
            f"skill: {skill_name}\n"
            f"version: 1\n"
        )
        manifest_path.write_text(manifest_content)
        try:
            created.append(str(manifest_path.relative_to(project_root)))
        except ValueError:
            created.append(str(manifest_path))

    # Create .gitkeep so the directory is tracked
    gitkeep = seeds_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("")
        try:
            created.append(str(gitkeep.relative_to(project_root)))
        except ValueError:
            created.append(str(gitkeep))

    return created


def _is_external_path(path_str: str, project_root: Path) -> bool:
    """Check if a path string refers to a location outside the project root.

    Handles both absolute paths and project-relative paths. A project-relative
    path (e.g. 'skills/foo') is always internal; an absolute path is external
    only if it does not start with project_root.
    """
    p = Path(path_str)
    if not p.is_absolute():
        return False  # Project-relative paths are always internal
    try:
        p.relative_to(project_root)
        return False
    except ValueError:
        return True


def _cleanup_empty_seed_scaffold(skill_dir_rel: str, project_root: Path) -> list[str]:
    """Remove an empty seed scaffold (manifest + .gitkeep, no real seed files).

    When a seed dir has only _seed.yaml (with empty files/directories lists)
    and .gitkeep but no actual seed data, the scaffold is useless — the
    fallback will fail regardless. Clean it up so the scan passes.

    Returns list of removed paths (project-relative).
    """
    skill_path = project_root / skill_dir_rel
    if not skill_path.is_dir():
        return []

    changes: list[str] = []

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(project_root))
        except ValueError:
            return str(p)

    for seeds_dir_name in ["assets/seeds", "augur/seed"]:
        seeds_dir = skill_path / seeds_dir_name
        if not seeds_dir.is_dir():
            continue

        # Only cleanup if there are no real seed files
        real_files = [
            f for f in seeds_dir.rglob("*")
            if f.is_file() and f.name not in ("_seed.yaml", ".gitkeep")
        ]
        if real_files:
            continue  # Has real seed files, don't touch

        # Check manifest declares nothing useful
        manifest_path = seeds_dir / "_seed.yaml"
        if manifest_path.is_file():
            try:
                manifest = yaml.safe_load(manifest_path.read_text()) or {}
            except Exception:
                manifest = {}
            has_declared_files = bool(manifest.get("files"))
            has_declared_dirs = bool(manifest.get("directories"))
            if has_declared_files or has_declared_dirs:
                continue  # Manifest declares content — don't remove

            manifest_path.unlink()
            changes.append(_rel(manifest_path))

        gitkeep = seeds_dir / ".gitkeep"
        if gitkeep.is_file():
            gitkeep.unlink()
            changes.append(_rel(gitkeep))

        # Remove empty parent dirs
        if seeds_dir.is_dir() and not any(seeds_dir.iterdir()):
            seeds_dir.rmdir()
            changes.append(f"removed {_rel(seeds_dir)}")
            # Also remove assets/ if now empty
            parent = seeds_dir.parent
            if parent.name == "assets" and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                changes.append(f"removed {_rel(parent)}")

    return changes


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix skills with broken or missing seed data.

    Difficulty escalation:
    - d0: report only (scan summary, no file writes)
    - d1+: remove empty seed scaffolds or create assets/seeds templates
    - d2+: same as d1 (deeper scan finds more issues, fix logic is identical)

    Auto-fixable:
    - needs_seeding (empty seed dir): remove the empty seed scaffold
    - needs_seed_templates (empty vault dir): create assets/seeds templates
    """
    if ctx.dry_run:
        return FixResult(
            success=True,
            changes=[],
            summary=f"Dry run: {len(issues)} issue(s) reported",
        )

    if ctx.difficulty < 1:
        # d0: report only — no file writes
        return FixResult(
            success=True,
            changes=[],
            summary=f"Report only (d0): {len(issues)} seed data issue(s) detected",
            fix_type="report",
        )

    skipped: list[str] = []
    changes: list[str] = []

    for issue in issues:
        skill = issue.get("skill_dir", "unknown")
        issue_type = issue.get("type", "")

        # Skip external paths (plugin cache copies)
        if _is_external_path(skill, ctx.project_root):
            continue

        if issue_type == "needs_seeding":
            # Empty seed scaffold — remove it so the next scan does not claim
            # a fallback exists when there are no packaged seed files.
            cleaned = _cleanup_empty_seed_scaffold(skill, ctx.project_root)
            if cleaned:
                changes.extend(cleaned)
            else:
                skipped.append(skill)
        elif issue_type == "needs_seed_templates":
            # Has data dir but no seed templates — create scaffold
            scaffolded = _create_seed_scaffold(skill, ctx.project_root)
            if scaffolded:
                changes.extend(scaffolded)
            else:
                skipped.append(skill)
        else:
            cleaned = _cleanup_empty_seed_scaffold(skill, ctx.project_root)
            if cleaned:
                changes.extend(cleaned)
            else:
                skipped.append(skill)

    parts = []
    if changes:
        parts.append(f"{len(changes)} seed file(s) created/cleaned/copied")
    if skipped:
        parts.append(f"{len(skipped)} skill(s) could not be fixed: {', '.join(skipped)}")
    if not parts:
        parts.append("No seed data issues to fix.")

    return FixResult(
        success=True,
        changes=changes,
        summary=". ".join(parts),
        fix_type="code-fix" if changes else "report",
    )
