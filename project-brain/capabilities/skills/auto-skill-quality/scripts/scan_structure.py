"""auto-skill-structure: Scan skill directories for structure violations (ADR-430)."""
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
import logging
import re
import shutil
from pathlib import Path

from src.config.paths import get_all_client_skill_dirs, get_skills_dir
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)

name = "auto-skill-structure"

DIFFICULTY_SPEC = {
    0: "Surface — report structure violations",
    1: "Content — auto-move banned dirs, delete banned files",
    2: "Deep — full structure audit, remove empty banned dirs",
}

logger = logging.getLogger(__name__)

BANNED_FILES = [
    (".config", "Replaced by plugin enable/disable (ADR-430)"),
    ("augur/version.yaml", "Replaced by plugin.json version (ADR-430)"),
    ("augur/README.md", "Auto-generated, should be gitignored (ADR-430)"),
]

# Banned dirs with their migration targets (relative to skill root).
# User-editable data lives in the vault; packaged fallback data lives in assets/seeds/.
BANNED_DIRS = [
    ("augur/seed", "assets/seeds", "Deprecated, use assets/seeds/ (ADR-430)"),
    ("assets/prompts", "assets/seeds/prompts", "Consolidated into assets/seeds/prompts/ (ADR-430)"),
    ("assets/seed-data", "assets/seeds", "Renamed to assets/seeds/ (ADR-430)"),
]

# Banned root-level dirs per CLAUDE.md rule 19
BANNED_ROOT_DIRS = [
    ("docs", "references", "Banned at skill root — use references/ (ADR-430)"),
    ("data", "assets/seeds", "Banned at skill root — use assets/seeds/ or vault-first data helpers (ADR-430)"),
    ("lib", "scripts", "Banned at skill root — use scripts/ or augur/lib/ (ADR-430)"),
]

BANNED_EXTENSIONS = [
    (".xlsx", "User data — move to vault"),
    (".docx", "User data — move to vault"),
    (".m4a", "User data — move to vault"),
    (".mp3", "User data — move to vault"),
    (".mp4", "User data — move to vault"),
]

REQUIRED_FILES = [
    ("SKILL.md", "Every skill must have a SKILL.md"),
]


def scan_skills(skills_dir: Path) -> list[dict]:
    """Scan all skills for structure violations.

    Returns list of issue dicts compatible with make_issue() output.
    """
    violations: list[dict] = []

    if not skills_dir.exists():
        return violations

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue

        skill_name = skill_dir.name

        # Check banned files
        for rel_path, reason in BANNED_FILES:
            target = skill_dir / rel_path
            if target.exists():
                violations.append(make_issue(
                    category="skill-structure",
                    detail=f"Banned file: {reason}",
                    path=f"project-brain/capabilities/skills/{skill_name}/{rel_path}",
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="auto",
                    fix_type="delete-file",
                    skill=skill_name,
                ))

        # Check banned directories (augur-internal)
        for rel_path, target_path, reason in BANNED_DIRS:
            target = skill_dir / rel_path
            if target.exists() and target.is_dir():
                violations.append(make_issue(
                    category="skill-structure",
                    detail=f"Banned directory: {reason}",
                    path=f"project-brain/capabilities/skills/{skill_name}/{rel_path}/",
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="auto",
                    fix_type="move-dir",
                    skill=skill_name,
                    move_target=target_path,
                ))

        # Check banned root-level dirs (CLAUDE.md rule 19)
        for dir_name, target_name, reason in BANNED_ROOT_DIRS:
            target = skill_dir / dir_name
            if target.exists() and target.is_dir():
                violations.append(make_issue(
                    category="skill-structure",
                    detail=f"Banned root dir: {reason}",
                    path=f"project-brain/capabilities/skills/{skill_name}/{dir_name}/",
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="auto",
                    fix_type="move-dir",
                    skill=skill_name,
                    move_target=target_name,
                ))

        # Check banned extensions (recursive)
        for ext, reason in BANNED_EXTENSIONS:
            for match in skill_dir.rglob(f"*{ext}"):
                if match.is_file():
                    rel = str(match.relative_to(skill_dir))
                    violations.append(make_issue(
                        category="skill-structure",
                        detail=f"Banned extension '{ext}': {reason}",
                        path=f"project-brain/capabilities/skills/{skill_name}/{rel}",
                        kind="actionable",
                        root_cause_type="repo_bug",
                        fixability="manual",
                        fix_type="move-to-vault",
                        skill=skill_name,
                    ))

        # Check required files — skip standard bundles (DESCRIPTION.md + nested
        # sub-skill SKILL.md, no top-level SKILL.md): these are intentionally
        # structured without a root-level SKILL.md (ADR-601).
        is_standard_bundle = (
            (skill_dir / "DESCRIPTION.md").is_file()
            and any(skill_dir.glob("*/SKILL.md"))
        )
        if not is_standard_bundle:
            for rel_path, reason in REQUIRED_FILES:
                target = skill_dir / rel_path
                if not target.exists():
                    violations.append(make_issue(
                        category="skill-structure",
                        detail=f"Missing required file: {reason}",
                        path=f"project-brain/capabilities/skills/{skill_name}/{rel_path}",
                        kind="actionable",
                        root_cause_type="repo_bug",
                        fixability="auto",
                        fix_type="create-file",
                        skill=skill_name,
                    ))

    return violations


def scan(ctx: OpsContext) -> ScanResult:
    """Scan project-local skill directories for structure violations.

    Only scans skills under the project root (not external plugin caches)
    since those are read-only and outside our control.
    """
    all_violations: list[dict] = []

    # Only scan the project-local skills directory — external plugin cache
    # skills are read-only and cannot be auto-fixed.
    project_skills_dir = get_skills_dir()
    if project_skills_dir.exists():
        all_violations.extend(scan_skills(project_skills_dir))

    errors = [v for v in all_violations if v.get("fixability") == "auto"]
    manual = [v for v in all_violations if v.get("fixability") == "manual"]

    if all_violations:
        severity = "error" if errors else "warning"
        summary = f"{len(all_violations)} structure violation(s) ({len(errors)} auto-fixable, {len(manual)} manual)"
    else:
        severity = "info"
        summary = "All skills pass structure checks"

    # Evolution gap at max difficulty with no issues
    if ctx.difficulty >= 2 and not all_violations:
        all_violations.append(evolution_gap(
            "All skills pass structure checks at max difficulty. "
            "Consider adding: augur/dashboard/ file type checks, "
            "pre-commit hook validation for new banned patterns, "
            "cross-skill import boundary enforcement.",
            category="skill-structure",
        ))

    return ScanResult(
        issues=all_violations,
        summary=summary,
        severity=severity,
        health="degraded" if errors else "verified",
        items_scanned=sum(
            1
            for d in project_skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ) if project_skills_dir.exists() else 0,
    )


def _update_skill_md_refs(skill_dir: Path, old_rel: str, new_rel: str) -> bool:
    """Rewrite references from old_rel to new_rel inside SKILL.md.

    Handles path references in both frontmatter and body text, e.g.:
      docs/design.md  -> references/design.md
      lib/utils.py    -> scripts/utils.py
      augur/seed/     -> assets/seeds/
      data/cache.yaml -> assets/seeds/cache.yaml

    Returns True if any references were updated.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return False

    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError:
        return False

    # Build patterns: match the old dir path with optional trailing /
    # Both bare dir references (docs/, lib/) and file paths (docs/foo.md)
    old_stripped = old_rel.rstrip("/")
    new_stripped = new_rel.rstrip("/")

    # Pattern matches: old_rel/ or old_rel/something (word-boundary start)
    pattern = re.compile(
        r'(?<![a-zA-Z0-9_/])' + re.escape(old_stripped) + r'(?=/|["\s\n\r`)]|$)',
    )
    updated = pattern.sub(new_stripped, content)

    if updated == content:
        return False

    try:
        skill_md.write_text(updated, encoding="utf-8")
        return True
    except OSError:
        return False


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix structure violations.

    d0: Report summary only.
    d1+: Auto-move banned dirs to correct locations, delete banned files,
         create missing SKILL.md stubs, update SKILL.md references.
    d2+: Also remove empty banned dirs after migration.
    """
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} structure violation(s)")

    if not issues:
        return FixResult(success=True, summary="No structure violations to fix")

    if ctx.difficulty < 1:
        return FixResult(
            success=True,
            summary=f"{len(issues)} structure violation(s) found (report only at d0)",
            fix_type="report",
        )

    skills_dir = get_skills_dir()
    actions: list[dict] = []
    changes: list[str] = []

    for issue in issues:
        fix_type = issue.get("fix_type", "")
        skill_name = issue.get("skill", "")
        path_str = issue.get("path", "")

        if not skill_name or issue.get("fixability") != "auto":
            continue

        skill_dir = skills_dir / skill_name
        if not skill_dir.is_dir():
            continue

        if fix_type == "delete-file":
            # Remove banned files (e.g. .config, augur/version.yaml)
            # Extract relative path within skill from the full path
            rel_in_skill = path_str.removeprefix(f"project-brain/capabilities/skills/{skill_name}/")
            target = skill_dir / rel_in_skill
            if target.is_file():
                try:
                    target.unlink()
                    actions.append({"action": "delete", "file": path_str})
                    changes.append(f"Deleted banned file: {path_str}")
                except OSError as e:
                    logger.warning("Failed to delete %s: %s", target, e)

        elif fix_type == "move-dir":
            # Move contents from banned dir to correct location
            rel_in_skill = path_str.removeprefix(f"project-brain/capabilities/skills/{skill_name}/").rstrip("/")
            src_path = skill_dir / rel_in_skill
            move_target = issue.get("move_target", "")
            if not move_target or not src_path.is_dir():
                continue

            dst_path = skill_dir / move_target
            try:
                dst_path.mkdir(parents=True, exist_ok=True)
                moved_count = 0
                skipped_count = 0
                # Walk all files recursively to handle nested subdirectories
                for item in list(src_path.rglob("*")):
                    if not item.is_file():
                        continue
                    # Preserve relative structure under source dir
                    rel_to_src = item.relative_to(src_path)
                    dest_item = dst_path / rel_to_src
                    if dest_item.exists():
                        # Destination already has this file — delete the
                        # source copy since the destination dir is canonical.
                        logger.info(
                            "Deleted duplicate %s — canonical copy exists at %s",
                            rel_to_src, dst_path,
                        )
                        item.unlink()
                        skipped_count += 1
                        continue
                    dest_item.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(item), str(dest_item))
                    moved_count += 1

                # Remove the now-empty banned dir tree
                if src_path.exists():
                    shutil.rmtree(str(src_path), ignore_errors=True)

                # Update references in SKILL.md: old path -> new path
                refs_updated = _update_skill_md_refs(skill_dir, rel_in_skill, move_target)

                actions.append({
                    "action": "move-dir",
                    "from": path_str,
                    "to": f"project-brain/capabilities/skills/{skill_name}/{move_target}",
                    "items_moved": moved_count,
                    "duplicates_removed": skipped_count,
                    "refs_updated": refs_updated,
                })
                ref_note = " (updated SKILL.md refs)" if refs_updated else ""
                dup_note = f", removed {skipped_count} duplicate(s)" if skipped_count else ""
                changes.append(
                    f"Moved {moved_count} item(s) from {rel_in_skill}/ to "
                    f"{move_target}/ in {skill_name}{dup_note}{ref_note}"
                )
            except OSError as e:
                logger.warning("Failed to move %s -> %s: %s", src_path, dst_path, e)

        elif fix_type == "create-file" and "SKILL.md" in path_str:
            # Create minimal SKILL.md stub
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                try:
                    skill_md.write_text(
                        f"---\nname: {skill_name}\n---\n# {skill_name}\n",
                        encoding="utf-8",
                    )
                    actions.append({"action": "create", "file": path_str})
                    changes.append(f"Created SKILL.md stub for {skill_name}")
                except OSError as e:
                    logger.warning("Failed to create SKILL.md for %s: %s", skill_name, e)

    manual_count = sum(1 for i in issues if i.get("fixability") != "auto")
    summary_parts = []
    if actions:
        summary_parts.append(f"Applied {len(actions)} fix(es)")
    if manual_count > 0:
        summary_parts.append(f"{manual_count} issue(s) require manual review")
    summary = "; ".join(summary_parts) if summary_parts else "No auto-fixable structure issues"

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if actions else "report",
    )
