"""auto-skill-migrate: Detect skills that need migration (wrong directory structure).

Checks (per CLAUDE.md rule 19 — Skill folder schema):
  Banned dirs at skill root: docs/ (use references/), data/ (use assets/seeds/),
  lib/ (use scripts/ or augur/lib/).
  Also: missing SKILL.md, deprecated patterns (augur/seed/ -> assets/seeds/).

Difficulty levels:
  d0: Surface — detect banned root dirs, missing SKILL.md
  d1: Content — detect deprecated patterns (augur/seed/), move banned dirs
  d2: Deep — verify all skills follow Agent Skills standard structure
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
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.config.paths import get_project_root
from src.lib.ops_protocol import (
    DifficultySpec,
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)

name = "auto-skill-migrate"

DIFFICULTY_SPEC: DifficultySpec = {
    0: "Surface — banned root dirs, missing SKILL.md",
    1: "Content — deprecated patterns, auto-move banned dirs",
    2: "Deep — full Agent Skills standard compliance audit",
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillDirectoryClassification:
    mode: str
    required_metadata: tuple[str, ...]


def classify_skill_directory(root: Path) -> SkillDirectoryClassification:
    """Classify a skill directory without forcing Augur metadata on standards."""
    if (root / "DESCRIPTION.md").is_file() and any(root.glob("*/SKILL.md")):
        return SkillDirectoryClassification(mode="standard", required_metadata=())
    return SkillDirectoryClassification(
        mode="augur",
        required_metadata=("SKILL.md", "x-augur-hub", "x-augur-type"),
    )

# Banned dirs at skill root -> correct location (CLAUDE.md rule 19)
BANNED_ROOT_DIRS: dict[str, str] = {
    "docs": "references",
    "data": "assets/seeds",
    "lib": "scripts",
}

# Standard dirs allowed at skill root (Agent Skills spec)
STANDARD_ROOT_DIRS = {
    "commands", "references", "scripts", "assets", "examples", "modules",
    "augur", "evals",
}

# Deprecated patterns: old -> new
DEPRECATED_DIRS: dict[str, str] = {
    "augur/seed": "assets/seeds",
}


def _get_skills_dir() -> Path:
    return get_project_root() / "project-brain" / "capabilities" / "skills"


def scan(ctx: OpsContext) -> ScanResult:
    """Scan skills for directory structure violations."""
    skills_dir = _get_skills_dir()
    if not skills_dir.is_dir():
        return ScanResult(
            issues=[], summary="No project-brain/capabilities/skills/ directory found",
            severity="info", health="verified",
        )

    issues: list[dict] = []
    items_scanned = 0

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        items_scanned += 1
        skill_name = skill_dir.name
        rel_base = f"project-brain/capabilities/skills/{skill_name}"

        # --- d0: Missing SKILL.md ---
        # Standard-skill bundles (DESCRIPTION.md + nested sub-skill SKILL.md)
        # intentionally have no top-level SKILL.md; don't flag them.
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file() and classify_skill_directory(skill_dir).mode != "standard":
            issues.append(make_issue(
                category="skill-migrate",
                detail=f"Skill '{skill_name}' is missing SKILL.md",
                path=rel_base,
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
                violation="missing-skill-md",
            ))

        # --- d0: Banned root dirs ---
        for banned, replacement in BANNED_ROOT_DIRS.items():
            banned_path = skill_dir / banned
            if banned_path.is_dir():
                # Check it's not empty (only .gitkeep)
                contents = list(banned_path.iterdir())
                real_contents = [c for c in contents if c.name != ".gitkeep"]
                if real_contents:
                    issues.append(make_issue(
                        category="skill-migrate",
                        detail=(
                            f"Banned root dir '{banned}/' in skill '{skill_name}' — "
                            f"move contents to '{replacement}/'"
                        ),
                        path=f"{rel_base}/{banned}",
                        kind="actionable",
                        root_cause_type="repo_bug",
                        fixability="auto",
                        violation="banned-root-dir",
                        banned_dir=banned,
                        replacement_dir=replacement,
                        skill_name=skill_name,
                    ))
                else:
                    # Empty banned dir (just .gitkeep) — less urgent
                    issues.append(make_issue(
                        category="skill-migrate",
                        detail=(
                            f"Empty banned root dir '{banned}/' in skill '{skill_name}' — "
                            f"remove or rename to '{replacement}/'"
                        ),
                        path=f"{rel_base}/{banned}",
                        kind="maintenance",
                        root_cause_type="manual_debt",
                        fixability="auto",
                        violation="empty-banned-dir",
                        banned_dir=banned,
                        replacement_dir=replacement,
                        skill_name=skill_name,
                    ))

        # --- d1: Deprecated patterns ---
        if ctx.difficulty >= 1:
            for deprecated, replacement in DEPRECATED_DIRS.items():
                deprecated_path = skill_dir / deprecated
                if deprecated_path.is_dir() and any(deprecated_path.iterdir()):
                    issues.append(make_issue(
                        category="skill-migrate",
                        detail=(
                            f"Deprecated dir '{deprecated}/' in skill '{skill_name}' — "
                            f"move to '{replacement}/'"
                        ),
                        path=f"{rel_base}/{deprecated}",
                        kind="actionable",
                        root_cause_type="repo_bug",
                        fixability="auto",
                        violation="deprecated-dir",
                        deprecated_dir=deprecated,
                        replacement_dir=replacement,
                        skill_name=skill_name,
                    ))

        # --- d2: Full Agent Skills standard compliance ---
        if ctx.difficulty >= 2:
            # Check for non-standard root dirs (excluding hidden, augur/, evals/)
            for entry in sorted(skill_dir.iterdir()):
                if not entry.is_dir():
                    continue
                if entry.name.startswith("."):
                    continue
                if entry.name in STANDARD_ROOT_DIRS:
                    continue
                if entry.name in BANNED_ROOT_DIRS:
                    continue  # Already reported above
                issues.append(make_issue(
                    category="skill-migrate",
                    detail=(
                        f"Non-standard root dir '{entry.name}/' in skill '{skill_name}' — "
                        f"not in Agent Skills spec (allowed: {', '.join(sorted(STANDARD_ROOT_DIRS))})"
                    ),
                    path=f"{rel_base}/{entry.name}",
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="manual",
                    violation="non-standard-dir",
                    dir_name=entry.name,
                    skill_name=skill_name,
                ))

            # Check augur/ subdirs (only dashboard/, tests/, lib/, pages/ allowed)
            augur_dir = skill_dir / "augur"
            if augur_dir.is_dir():
                allowed_augur = {"dashboard", "tests", "lib", "pages"}
                for entry in sorted(augur_dir.iterdir()):
                    if not entry.is_dir() or entry.name.startswith("."):
                        continue
                    if entry.name not in allowed_augur:
                        issues.append(make_issue(
                            category="skill-migrate",
                            detail=(
                                f"Non-standard augur/ subdir '{entry.name}/' in skill '{skill_name}' — "
                                f"allowed: {', '.join(sorted(allowed_augur))}"
                            ),
                            path=f"{rel_base}/augur/{entry.name}",
                            kind="maintenance",
                            root_cause_type="manual_debt",
                            fixability="manual",
                            violation="non-standard-augur-dir",
                            dir_name=entry.name,
                            skill_name=skill_name,
                        ))

    # Evolution gap at max difficulty
    if ctx.difficulty >= 2 and not issues:
        issues.append(evolution_gap(
            "All skills follow Agent Skills standard structure. "
            "Consider adding: SKILL.md frontmatter completeness validation "
            "(required fields: name, description, x-augur-hub, x-augur-type), "
            "cross-reference validation between SKILL.md and actual skill contents. "
            "Next: implement frontmatter schema validation.",
            category="skill-migrate",
        ))

    severity = "warning" if any(i.get("kind") == "actionable" for i in issues) else "info"
    health = "degraded" if severity == "warning" else "verified"

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} migration issue(s) in {items_scanned} skill(s)" if issues else f"All {items_scanned} skills compliant",
        severity=severity,
        health=health,
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix skill migration issues.

    d0: Report only.
    d1+: Auto-move banned/deprecated dirs to correct locations.
    """
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} migration issues found")

    if not issues:
        return FixResult(success=True, summary="No migration issues to fix")

    if ctx.difficulty < 1:
        return FixResult(
            success=True,
            summary=f"{len(issues)} migration issues found (report only at d0)",
            fix_type="report",
        )

    skills_dir = _get_skills_dir()
    actions: list[dict] = []
    changes: list[str] = []

    for issue in issues:
        if issue.get("fixability") != "auto":
            continue

        violation = issue.get("violation", "")
        skill_name = issue.get("skill_name", "")
        if not skill_name:
            continue

        skill_dir = skills_dir / skill_name
        if not skill_dir.is_dir():
            continue

        if violation in ("banned-root-dir", "deprecated-dir"):
            banned = issue.get("banned_dir") or issue.get("deprecated_dir", "")
            replacement = issue.get("replacement_dir", "")
            if not banned or not replacement:
                continue

            src_path = skill_dir / banned
            dest_path = skill_dir / replacement
            if not src_path.is_dir():
                continue

            try:
                dest_path.mkdir(parents=True, exist_ok=True)
                # Move contents, not the dir itself
                for item in src_path.iterdir():
                    if item.name == ".gitkeep":
                        continue
                    dest_item = dest_path / item.name
                    if dest_item.exists():
                        # Destination already has this file — remove the
                        # stale source copy instead of skipping silently
                        logger.info(
                            "Removing stale %s — already exists at %s",
                            item, dest_item,
                        )
                        if item.is_dir():
                            shutil.rmtree(str(item))
                        else:
                            item.unlink()
                        continue
                    shutil.move(str(item), str(dest_item))

                # Remove empty source dir
                remaining = list(src_path.iterdir())
                if not remaining or all(f.name == ".gitkeep" for f in remaining):
                    shutil.rmtree(str(src_path))

                actions.append({
                    "action": "move_dir",
                    "skill": skill_name,
                    "from": banned,
                    "to": replacement,
                })
                changes.append(f"Moved {skill_name}/{banned}/ -> {skill_name}/{replacement}/")
            except OSError as e:
                logger.warning("Failed to move %s/%s: %s", skill_name, banned, e)

        elif violation == "empty-banned-dir":
            banned = issue.get("banned_dir", "")
            if not banned:
                continue
            banned_path = skill_dir / banned
            if banned_path.is_dir():
                try:
                    shutil.rmtree(str(banned_path))
                    actions.append({
                        "action": "remove_empty_dir",
                        "skill": skill_name,
                        "dir": banned,
                    })
                    changes.append(f"Removed empty {skill_name}/{banned}/")
                except OSError as e:
                    logger.warning("Failed to remove %s/%s: %s", skill_name, banned, e)

    manual_count = sum(1 for i in issues if i.get("fixability") != "auto")
    summary_parts = []
    if actions:
        summary_parts.append(f"Applied {len(actions)} migration(s)")
    if manual_count > 0:
        summary_parts.append(f"{manual_count} issue(s) require manual review")
    summary = "; ".join(summary_parts) if summary_parts else "No auto-fixable migration issues"

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if actions else "report",
    )
