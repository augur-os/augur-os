"""auto-skill-md: Validate and generate SKILL.md files per Claude Code skills standard.

Tier 0 in the skill-standards loop. Ensures every Augur skill has a valid
SKILL.md with standards-compliant frontmatter.

Difficulty levels:
  d0: missing SKILL.md, empty body
  d1: name validation, missing description
  d2+: unknown frontmatter fields
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

import importlib.util
import sys

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

# Load sibling module dynamically — these files live under .claude/ which is
# not a valid Python package path, so normal dotted imports don't work.
_LIB_MOD_NAME = "skill_standards_lib"
if _LIB_MOD_NAME in sys.modules:
    _lib = sys.modules[_LIB_MOD_NAME]
else:
    _lib_path = Path(__file__).with_name("skill_standards_lib.py")
    _spec = importlib.util.spec_from_file_location(_LIB_MOD_NAME, str(_lib_path))
    _lib = importlib.util.module_from_spec(_spec)
    sys.modules[_LIB_MOD_NAME] = _lib
    _spec.loader.exec_module(_lib)

iter_all_skills = _lib.iter_all_skills
parse_skill_md = _lib.parse_skill_md
validate_name = _lib.validate_name
validate_frontmatter = _lib.validate_frontmatter
write_skill_md = _lib.write_skill_md
update_frontmatter = _lib.update_frontmatter

name = "auto-skill-md"


def scan(ctx: OpsContext) -> ScanResult:
    issues: list[dict] = []

    for skill in iter_all_skills(ctx.project_root):
        rel = str(skill.path.relative_to(ctx.project_root.resolve()))
        md_info = parse_skill_md(skill.path)

        if not md_info.exists:
            # Standard-skill bundles intentionally have no top-level SKILL.md:
            # they use DESCRIPTION.md plus nested sub-skill SKILL.md files
            # (see <skill>/tests/test_standard_layout.py::test_standard_bundle_shape).
            # Flagging them would contradict the canonical bundle layout.
            if (skill.path / "DESCRIPTION.md").is_file():
                continue
            issues.append({
                "action": "missing-skill-md",
                "file": rel,
                "detail": f"Skill '{skill.name}' has no SKILL.md",
                "skill_name": skill.name,
            })
            continue

        # Empty body check (all difficulty levels)
        if not md_info.body.strip():
            issues.append({
                "action": "empty-body",
                "file": rel,
                "detail": "SKILL.md has no markdown body",
                "skill_name": skill.name,
            })

        # d1+: name and frontmatter validation
        if ctx.difficulty >= 1:
            for issue in validate_name(md_info.frontmatter.get("name"), skill.name):
                issues.append({
                    "action": "invalid-name",
                    "file": rel,
                    "detail": issue["detail"],
                    "skill_name": skill.name,
                    "fix_value": skill.name,
                })

            for issue in validate_frontmatter(md_info):
                # At d1 only missing description, at d2+ unknown fields too
                if issue["problem"] == "missing" or ctx.difficulty >= 2:
                    issues.append({
                        "action": "invalid-frontmatter",
                        "file": rel,
                        "detail": issue["detail"],
                        "skill_name": skill.name,
                        "field": issue["field"],
                        "problem": issue["problem"],
                    })

    severity = "error" if any(i["action"] == "missing-skill-md" for i in issues) else (
        "warning" if issues else "info"
    )
    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} SKILL.md issue(s) (d={ctx.difficulty})",
        severity=severity,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would fix {len(issues)} SKILL.md issue(s)",
        )

    actions: list[dict] = []
    changes: list[str] = []

    for issue in issues:
        action = issue["action"]
        skill_dir = ctx.project_root / issue["file"]
        if not skill_dir.is_dir():
            skill_dir = skill_dir.parent

        if action == "missing-skill-md":
            # Refuse to create SKILL.md for ghost directories (only __pycache__
            # remnants from renamed/deleted skills). This prevents autoloops
            # from resurrecting deleted skills.
            real_files = [
                f for f in skill_dir.rglob("*")
                if f.is_file()
                and "__pycache__" not in f.parts
                and f.name != ".gitkeep"
            ]
            if not real_files:
                actions.append({"status": "skipped", "action": action,
                                "reason": "ghost directory (only __pycache__)",
                                "file": issue["file"]})
                continue
            _generate_skill_md(skill_dir, issue.get("skill_name", skill_dir.name))
            actions.append({"status": "fixed", "action": action, "file": issue["file"]})
            changes.append(str(skill_dir / "SKILL.md"))

        elif action == "invalid-name":
            md_path = skill_dir / "SKILL.md"
            update_frontmatter(md_path, {"name": issue.get("fix_value", skill_dir.name)})
            actions.append({"status": "fixed", "action": action, "file": issue["file"]})
            changes.append(str(md_path))

        elif action == "invalid-frontmatter":
            md_path = skill_dir / "SKILL.md"
            if issue.get("problem") == "missing" and issue.get("field") == "description":
                update_frontmatter(md_path, {"description": f"{skill_dir.name} skill"})
                actions.append({"status": "fixed", "action": action, "file": issue["file"]})
                changes.append(str(md_path))
            elif issue.get("problem") == "unknown" and issue.get("field"):
                # Rename non-standard field to x-augur- prefixed version
                field = issue["field"]
                new_field = f"x-augur-{field}"
                md_info = parse_skill_md(skill_dir)
                if md_info.exists and field in md_info.frontmatter:
                    value = md_info.frontmatter.pop(field)
                    md_info.frontmatter[new_field] = value
                    write_skill_md(md_path, md_info.frontmatter, md_info.body)
                    actions.append({"status": "fixed", "action": action, "file": issue["file"],
                                    "detail": f"Renamed '{field}' -> '{new_field}'"})
                    changes.append(str(md_path))
                else:
                    actions.append({"status": "skipped", "action": action, "reason": "field not found"})
            else:
                actions.append({"status": "skipped", "action": action, "reason": "manual review needed"})

        elif action == "empty-body":
            _generate_body(skill_dir)
            actions.append({"status": "fixed", "action": action, "file": issue["file"]})
            changes.append(str(skill_dir / "SKILL.md"))

    fixed = [a for a in actions if a.get("status") == "fixed"]
    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=f"Fixed {len(fixed)}/{len(issues)} SKILL.md issues",
    )


def _extract_difficulty_spec(script_path: Path) -> dict | None:
    """Extract DIFFICULTY_SPEC dict from an ops script using AST parsing.

    Returns the dict if found, None otherwise. Uses ast.literal_eval
    which is safe — it only evaluates literal Python expressions (dicts,
    lists, strings, numbers), never arbitrary code.
    """
    import ast

    try:
        content = script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    if "DIFFICULTY_SPEC" not in content:
        return None

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "DIFFICULTY_SPEC"
                for t in node.targets
            )
        ):
            try:
                return ast.literal_eval(node.value)  # noqa: S307 — literal_eval is safe
            except (ValueError, TypeError):
                return None

    return None


def _infer_hub_from_path(skill_dir: Path) -> str:
    """Infer a hub from plugin path layout when SKILL frontmatter is missing."""
    parts = skill_dir.parts
    if "plugins" in parts:
        idx = parts.index("plugins")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def _generate_skill_md(skill_dir: Path, skill_name: str) -> None:
    """Generate a SKILL.md from directory structure and existing content.

    Produces a complete SKILL.md with proper sections:
    - Title and description
    - Commands (from commands/*.md)
    - Scripts (from scripts/)
    - Difficulty Levels (from ops script DIFFICULTY_SPEC if present)
    - Data (from assets/seeds/ or data/)
    - Dashboard Pages (from augur/dashboard/)
    """
    description = f"{skill_name} skill"
    hub = _infer_hub_from_path(skill_dir)

    # Build frontmatter
    frontmatter: dict = {"name": skill_name, "description": description}
    if hub:
        frontmatter["x-augur-hub"] = hub

    if (skill_dir / "scripts" / "ops").is_dir():
        frontmatter["x-augur-visibility"] = "auto"

    # Build body sections
    body_parts = [f"# {skill_name.replace('-', ' ').title()}", "", description, ""]

    # Commands section
    cmd_dir = skill_dir / "commands"
    if cmd_dir.exists():
        cmd_files = sorted(cmd_dir.glob("*.md"))
        if cmd_files:
            body_parts.append("## Commands")
            body_parts.append("")
            for cmd_file in cmd_files:
                try:
                    cmd_content = cmd_file.read_text(encoding="utf-8").strip()
                except (OSError, UnicodeDecodeError):
                    cmd_content = ""
                body_parts.append(f"### {cmd_file.stem}")
                body_parts.append("")
                first_para = cmd_content.split("\n\n")[0] if cmd_content else ""
                body_parts.append(first_para)
                body_parts.append("")

    # Scripts section — discover what scripts exist
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        script_files = sorted(scripts_dir.rglob("*.py"))
        if script_files:
            body_parts.append("## Scripts")
            body_parts.append("")

            # Try to extract DIFFICULTY_SPEC from ops scripts
            difficulty_spec = None
            for sf in script_files:
                if difficulty_spec is None:
                    difficulty_spec = _extract_difficulty_spec(sf)
                rel = sf.relative_to(skill_dir)
                body_parts.append(f"- `{rel}`")
            body_parts.append("")

            # Difficulty Levels section (for auto-loop skills)
            if difficulty_spec and isinstance(difficulty_spec, dict):
                body_parts.append("## Difficulty Levels")
                body_parts.append("")
                for level in sorted(difficulty_spec.keys()):
                    body_parts.append(f"- **d{level}**: {difficulty_spec[level]}")
                body_parts.append("")

    # Dashboard pages section
    dashboard_dir = skill_dir / "augur" / "dashboard"
    if dashboard_dir.is_dir():
        pages = sorted(dashboard_dir.rglob("page.tsx"))
        if pages:
            body_parts.append("## Dashboard Pages")
            body_parts.append("")
            for page in pages:
                rel = page.parent.relative_to(dashboard_dir)
                body_parts.append(f"- `/{rel}`")
            body_parts.append("")

    # Data section — note what data directories exist
    data_dirs = []
    for candidate in [skill_dir / "assets" / "seeds", skill_dir / "data"]:
        if candidate.is_dir() and any(candidate.iterdir()):
            data_dirs.append(candidate)
    if data_dirs:
        body_parts.append("## Data")
        body_parts.append("")
        for dd in data_dirs:
            rel = dd.relative_to(skill_dir)
            subdirs = sorted(d.name for d in dd.iterdir() if d.is_dir() and not d.name.startswith("."))
            files = sorted(f.name for f in dd.iterdir() if f.is_file() and not f.name.startswith("."))
            if subdirs:
                body_parts.append(f"- `{rel}/`: {', '.join(subdirs)}")
            if files:
                body_parts.append(f"- `{rel}/`: {', '.join(files[:5])}" + (" ..." if len(files) > 5 else ""))
        body_parts.append("")

    write_skill_md(skill_dir / "SKILL.md", frontmatter, "\n".join(body_parts))


def _generate_body(skill_dir: Path) -> None:
    """Generate a body for an existing SKILL.md with empty body.

    Reuses the same section-discovery logic as _generate_skill_md to produce
    a rich body with Commands, Scripts, Difficulty Levels, Dashboard Pages,
    and Data sections derived from the skill directory structure.
    """
    md_info = parse_skill_md(skill_dir)
    skill_name = md_info.frontmatter.get("name", skill_dir.name)
    description = md_info.frontmatter.get("description", f"{skill_name} skill")

    body_parts = [f"# {skill_name.replace('-', ' ').title()}", "", description, ""]

    # Commands section
    cmd_dir = skill_dir / "commands"
    if cmd_dir.exists():
        cmd_files = sorted(cmd_dir.glob("*.md"))
        if cmd_files:
            body_parts.append("## Commands")
            body_parts.append("")
            for cmd_file in cmd_files:
                try:
                    cmd_content = cmd_file.read_text(encoding="utf-8").strip()
                except (OSError, UnicodeDecodeError):
                    cmd_content = ""
                body_parts.append(f"### {cmd_file.stem}")
                body_parts.append("")
                first_para = cmd_content.split("\n\n")[0] if cmd_content else ""
                body_parts.append(first_para)
                body_parts.append("")

    # Scripts and difficulty levels
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        script_files = sorted(scripts_dir.rglob("*.py"))
        if script_files:
            body_parts.append("## Scripts")
            body_parts.append("")
            difficulty_spec = None
            for sf in script_files:
                if difficulty_spec is None:
                    difficulty_spec = _extract_difficulty_spec(sf)
                rel = sf.relative_to(skill_dir)
                body_parts.append(f"- `{rel}`")
            body_parts.append("")

            if difficulty_spec and isinstance(difficulty_spec, dict):
                body_parts.append("## Difficulty Levels")
                body_parts.append("")
                for level in sorted(difficulty_spec.keys()):
                    body_parts.append(f"- **d{level}**: {difficulty_spec[level]}")
                body_parts.append("")

    # Dashboard pages
    dashboard_dir = skill_dir / "augur" / "dashboard"
    if dashboard_dir.is_dir():
        pages = sorted(dashboard_dir.rglob("page.tsx"))
        if pages:
            body_parts.append("## Dashboard Pages")
            body_parts.append("")
            for page in pages:
                rel = page.parent.relative_to(dashboard_dir)
                body_parts.append(f"- `/{rel}`")
            body_parts.append("")

    write_skill_md(skill_dir / "SKILL.md", md_info.frontmatter, "\n".join(body_parts))
