"""auto-skill-enhance: Scan skills for missing or placeholder descriptions and metadata gaps.

Difficulty levels:
  d0: Check SKILL.md for missing/placeholder descriptions, missing x-augur-type
  d1: Generate improved descriptions from SKILL.md body content analysis
  d2: Deep — check evals/rank.json coverage, tag inference, description format
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
import json
import logging
import re
from pathlib import Path

from src.config.paths import get_skills_dir
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)

name = "auto-skill-enhance"

DIFFICULTY_SPEC = {
    0: "Surface — detect placeholder descriptions, missing x-augur-type",
    1: "Content — generate improved descriptions from body content analysis",
    2: "Deep — evals/rank.json coverage, tag inference, description format audit",
}

logger = logging.getLogger(__name__)

# Patterns that indicate a placeholder or auto-generated description
PLACEHOLDER_PATTERNS = [
    re.compile(r"^Skill:", re.IGNORECASE),
    re.compile(r"management for", re.IGNORECASE),
    re.compile(r"^TODO", re.IGNORECASE),
    re.compile(r"^placeholder", re.IGNORECASE),
    re.compile(r"^Description pending", re.IGNORECASE),
]

MIN_DESCRIPTION_WORDS = 10


def _is_placeholder_description(desc: str) -> bool:
    """Check if a description is a placeholder or too short."""
    if not desc or not desc.strip():
        return True
    words = desc.strip().split()
    if len(words) < MIN_DESCRIPTION_WORDS:
        return True
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(desc):
            return True
    return False


def _extract_description_from_body(body: str) -> str:
    """Extract a description from the SKILL.md body content.

    Analyzes headings, first paragraph, and key phrases to synthesize
    a description. Returns empty string if body is too sparse.
    """
    if not body or not body.strip():
        return ""

    lines = body.strip().splitlines()

    # Collect headings for context
    headings: list[str] = []
    first_paragraph_lines: list[str] = []
    in_first_para = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            heading_text = stripped.lstrip("#").strip()
            # Skip argument handling boilerplate headings
            if heading_text.lower() in ("argument handling (auto)",):
                continue
            headings.append(heading_text)
        elif stripped and not in_first_para and not stripped.startswith("<!--"):
            in_first_para = True
            first_paragraph_lines.append(stripped)
        elif not stripped and in_first_para:
            break  # End of first paragraph
        elif in_first_para:
            first_paragraph_lines.append(stripped)

    first_para = " ".join(first_paragraph_lines).strip()

    # Use first paragraph if it's substantial enough
    if first_para and len(first_para.split()) >= MIN_DESCRIPTION_WORDS:
        # Truncate to reasonable length
        if len(first_para) > 200:
            first_para = first_para[:197] + "..."
        return first_para

    # Fall back to heading synthesis
    if headings:
        meaningful_headings = [
            h for h in headings
            if not h.startswith("/") and h.lower() not in (
                "usage", "protocol", "implementation",
                "difficulty levels", "additional resources",
                "what it does", "scan", "fix",
            )
        ]
        if meaningful_headings:
            return f"Use when working with {', '.join(meaningful_headings[:3]).lower()}."

    return ""


def scan(ctx: OpsContext) -> ScanResult:
    """Scan skills for description and metadata gaps."""
    skills_dir = get_skills_dir()

    if not skills_dir.is_dir():
        return ScanResult(
            issues=[],
            summary="No skills directory found",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []
    skills_scanned = 0

    for skill_entry in sorted(skills_dir.iterdir()):
        if not skill_entry.is_dir() or skill_entry.name.startswith("."):
            continue

        skill_name = skill_entry.name
        skill_md = skill_entry / "SKILL.md"

        if not skill_md.is_file():
            continue  # No SKILL.md — other scanners handle this

        skills_scanned += 1

        try:
            fm, body = parse_frontmatter(skill_md)
        except Exception:
            continue

        if not isinstance(fm, dict):
            continue

        # --- d0 checks ---

        # Check for missing or placeholder descriptions
        desc = fm.get("description", "")
        if _is_placeholder_description(desc):
            issues.append(make_issue(
                category="skill-enhance",
                detail=(
                    f"Skill '{skill_name}' has placeholder/short description"
                    + (f": '{desc[:60]}'" if desc else ": (empty)")
                ),
                path=f"skills/{skill_name}/SKILL.md",
                kind="actionable",
                root_cause_type="manual_debt",
                fixability="auto",
                skill_name=skill_name,
                issue_type="placeholder-description",
            ))

        # Check for missing x-augur-type
        if not fm.get("x-augur-type"):
            issues.append(make_issue(
                category="skill-enhance",
                detail=f"Skill '{skill_name}' missing x-augur-type field",
                path=f"skills/{skill_name}/SKILL.md",
                kind="actionable",
                root_cause_type="manual_debt",
                fixability="manual",
                skill_name=skill_name,
                issue_type="missing-type",
            ))

    # --- d1 checks ---
    # (d1 is the fix tier for placeholder descriptions — no additional scan checks)

    # --- d2 checks ---

    if ctx.difficulty >= 2:
        for skill_entry in sorted(skills_dir.iterdir()):
            if not skill_entry.is_dir() or skill_entry.name.startswith("."):
                continue

            skill_name = skill_entry.name
            skill_md = skill_entry / "SKILL.md"
            if not skill_md.is_file():
                continue

            try:
                fm, body = parse_frontmatter(skill_md)
            except Exception:
                continue

            if not isinstance(fm, dict):
                continue

            # Check evals/rank.json existence
            rank_json = skill_entry / "evals" / "rank.json"
            if not rank_json.is_file():
                issues.append(make_issue(
                    category="skill-enhance",
                    detail=f"Skill '{skill_name}' has no evals/rank.json",
                    path=f"skills/{skill_name}/evals/rank.json",
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="manual",
                    skill_name=skill_name,
                    issue_type="missing-evals",
                ))

            # Check description format (ADR-463: should start with "Use when")
            desc = fm.get("description", "")
            if desc and not _is_placeholder_description(desc):
                if not desc.strip().startswith("Use when"):
                    issues.append(make_issue(
                        category="skill-enhance",
                        detail=(
                            f"Skill '{skill_name}' description does not follow "
                            f"'Use when...' format (ADR-463)"
                        ),
                        path=f"skills/{skill_name}/SKILL.md",
                        kind="maintenance",
                        root_cause_type="manual_debt",
                        fixability="auto",
                        skill_name=skill_name,
                        issue_type="description-format",
                    ))

            # Check for empty tags that could be inferred
            tags = fm.get("x-augur-tags", [])
            if isinstance(tags, list) and not tags:
                issues.append(make_issue(
                    category="skill-enhance",
                    detail=f"Skill '{skill_name}' has empty x-augur-tags — could be inferred",
                    path=f"skills/{skill_name}/SKILL.md",
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="auto",
                    skill_name=skill_name,
                    issue_type="empty-tags",
                ))

        # Evolution gaps at max difficulty with no issues
        if not issues:
            issues.append(evolution_gap(
                "All skill enhancement checks pass at max difficulty. "
                "Consider adding: cross-skill description uniqueness check, "
                "description-to-body coherence scoring, "
                "command execution log analysis for enhancement hints.",
                category="skill-enhance",
            ))

    severity = "warning" if any(i.get("kind") == "actionable" for i in issues) else "info"
    health = "degraded" if severity == "warning" else "verified"

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} skill enhancement issues across {skills_scanned} skills" if issues else f"All {skills_scanned} skills pass enhancement checks",
        severity=severity,
        health=health,
        items_scanned=skills_scanned,
    )


def _rewrite_frontmatter_field(skill_md: Path, field: str, new_value: str) -> bool:
    """Rewrite a single frontmatter field in a SKILL.md file.

    Returns True on success.
    """
    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError:
        return False

    if not content.startswith("---"):
        return False

    end_idx = content.find("\n---", 4)
    if end_idx == -1:
        return False

    fm_block = content[4:end_idx]
    body = content[end_idx:]

    # Replace the field value in the frontmatter block
    # Handle both single-line and multi-line (quoted) values
    import yaml
    try:
        fm_data = yaml.safe_load(fm_block)
    except yaml.YAMLError:
        return False

    if not isinstance(fm_data, dict):
        return False

    fm_data[field] = new_value

    # Rewrite with updated frontmatter
    new_fm = yaml.dump(fm_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    new_content = f"---\n{new_fm}---{body[4:]}"  # body starts with \n---

    try:
        skill_md.write_text(new_content, encoding="utf-8")
        return True
    except OSError:
        return False


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix skill enhancement issues."""
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issues found")

    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    if ctx.difficulty < 1:
        return FixResult(
            success=True,
            summary="Fix requires difficulty >= 1",
        )

    skills_dir = get_skills_dir()
    actions: list[dict] = []
    changes: list[str] = []

    # Fix placeholder descriptions
    desc_issues = [
        i for i in issues
        if i.get("issue_type") == "placeholder-description"
        and i.get("kind") == "actionable"
    ]

    for issue in desc_issues:
        skill_name = issue.get("skill_name", "")
        if not skill_name:
            continue

        skill_md = skills_dir / skill_name / "SKILL.md"
        if not skill_md.is_file():
            continue

        try:
            _fm, body = parse_frontmatter(skill_md)
        except Exception:
            continue

        new_desc = _extract_description_from_body(body)
        if not new_desc or _is_placeholder_description(new_desc):
            logger.info(f"Cannot generate description for '{skill_name}' — body too sparse")
            continue

        if _rewrite_frontmatter_field(skill_md, "description", new_desc):
            actions.append({
                "action": "improve_description",
                "skill": skill_name,
                "new_description": new_desc[:100],
            })
            changes.append(f"Improved description for '{skill_name}'")
        else:
            logger.warning(f"Failed to rewrite description for '{skill_name}'")

    summary = f"Applied {len(actions)} fixes" if actions else "No actionable fixes at current difficulty"
    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
    )
