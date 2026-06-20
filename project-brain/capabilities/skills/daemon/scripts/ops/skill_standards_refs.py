"""auto-skill-refs: Validate and fix supporting file references and folder structure.

Tier 2 in the skill-standards loop. Ensures SKILL.md references valid files,
scripts live in scripts/, and folder structure follows the open standard.

Difficulty levels:
  d0: broken references to functional files (scripts/, commands/, augur/, .py/.sh/.ts/.js)
  d1: all broken references, loose scripts (folder restructuring)
  d2: SKILL.md too long (content splitting)
  d3: orphan detection
  d4: cross-skill refs
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
import re
import sys

import yaml

from src.config.paths import get_managed_skill_source_dirs
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
extract_command_callables = _lib.extract_command_callables
validate_folder_structure = _lib.validate_folder_structure
move_file_with_refs = _lib.move_file_with_refs

name = "auto-skill-refs"

# Files/directories to skip during orphan detection
_SKIP_NAMES = {
    "SKILL.md", "config.yaml", "__init__.py", "__pycache__",
    "scripts", "commands", "tests", "examples", "augur", "dashboard",
    "node_modules", ".DS_Store",
}
_SKIP_SUFFIXES = {".pyc"}

# At d0, only flag broken refs to functional files that affect skill operation
_FUNCTIONAL_PREFIXES = ("scripts/", "commands/", "augur/")
_FUNCTIONAL_EXTS = {".py", ".sh", ".ts", ".js"}


def scan(ctx: OpsContext) -> ScanResult:
    issues: list[dict] = []

    # auto-skill-refs validates SOURCE skills only. iter_all_skills also yields
    # generated client projections (.opencode/skills, .claude/skills, ...) which
    # are SKILL.md-only copies by design — their commands/, scripts/, and
    # references/ links always dangle there even though the canonical refs
    # resolve at the source skill (which IS scanned). Scanning projections
    # produced permanent false-positive broken-refs that fix() can never resolve
    # (the files aren't in the projection) and would even rewrite generated
    # output. Restrict to the managed source roots.
    source_dirs = {
        source_dir.resolve()
        for source_dir in get_managed_skill_source_dirs(ctx.project_root)
    }

    for skill in iter_all_skills(ctx.project_root):
        if skill.path.parent.resolve() not in source_dirs:
            continue
        rel = str(skill.path.relative_to(ctx.project_root.resolve()))
        md_info = parse_skill_md(skill.path)

        # Skip skills without SKILL.md — auto-skill-md (tier 0) handles that
        if not md_info.exists:
            continue

        # d0: broken references to functional files (scripts, commands)
        # d1+: all broken references including docs, examples, assets
        for ref in md_info.file_refs:
            ref_path = skill.path / ref
            if not ref_path.exists():
                # At d0, only flag refs to functional files that affect skill operation
                if ctx.difficulty < 1:
                    ref_p = Path(ref)
                    is_functional = (
                        any(ref.startswith(pfx) for pfx in _FUNCTIONAL_PREFIXES)
                        or ref_p.suffix in _FUNCTIONAL_EXTS
                    )
                    if not is_functional:
                        continue
                issues.append({
                    "action": "broken-ref",
                    "file": rel,
                    "detail": f"Reference '{ref}' not found",
                    "skill_name": skill.name,
                    "ref": ref,
                })

        # d1+: folder structure issues (call once, filter by difficulty)
        if ctx.difficulty >= 1:
            for issue in validate_folder_structure(skill.path):
                if issue["problem"] == "loose_script":
                    issues.append({
                        "action": "loose-script",
                        "file": rel,
                        "detail": issue["detail"],
                        "skill_name": skill.name,
                        "filename": issue["file"],
                    })
                elif issue["problem"] == "too_long" and ctx.difficulty >= 2:
                    issues.append({
                        "action": "skill-md-too-long",
                        "file": rel,
                        "detail": issue["detail"],
                        "skill_name": skill.name,
                    })

        # d3: orphaned files
        if ctx.difficulty >= 3:
            for orphan in _scan_orphans(skill.path, md_info):
                orphan["file"] = rel
                orphan["skill_name"] = skill.name
                issues.append(orphan)

    severity = "warning" if issues else "info"
    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} reference/structure issue(s) (d={ctx.difficulty})",
        severity=severity,
    )


def _scan_orphans(skill_dir: Path, md_info) -> list[dict]:
    """Find files not referenced from SKILL.md. Returns list of orphan issues."""
    referenced = set(md_info.file_refs)
    referenced.update(extract_command_callables(md_info.frontmatter))

    orphans = []
    for item in _walk_files(skill_dir):
        item_rel = str(item.relative_to(skill_dir))
        if item.name in _SKIP_NAMES or item.suffix in _SKIP_SUFFIXES:
            continue
        if item_rel not in referenced and item.name not in referenced:
            # Check if parent directory is a known structure dir
            if any(part in _SKIP_NAMES for part in item.relative_to(skill_dir).parts):
                continue
            orphans.append({
                "action": "orphaned-file",
                "detail": f"File '{item_rel}' not referenced from SKILL.md",
                "orphan": item_rel,
            })
    return orphans


def _walk_files(directory: Path):
    """Walk files in directory, pruning hidden dirs and known non-content dirs."""
    import os
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in sorted(dirs) if d not in _SKIP_NAMES and not d.startswith(".")]
        for f in sorted(files):
            yield Path(root) / f


def _path_matches_disk_case(root: Path, path: Path) -> bool:
    """Return true only when every path component matches on-disk casing."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False

    current = root
    for part in rel.parts:
        try:
            matches = [child for child in current.iterdir() if child.name == part]
        except OSError:
            return False
        if len(matches) != 1:
            return False
        current = matches[0]
    return True


_MAX_LINES = 500  # Standard recommends under this
_CONFIG_SIDECAR = "config.yaml"  # Sidecar file for extracted x-augur-config


def _is_auto_generated(content: str) -> str | None:
    """Return the source path if the file is auto-generated, else None."""
    if "AUTO-GENERATED FILE" not in content:
        return None
    m = re.search(r"Source:\s*(.+)", content)
    return m.group(1).strip() if m else "(unknown source)"


def _extract_config_to_sidecar(skill_dir: Path) -> dict:
    """Extract x-augur-config from SKILL.md frontmatter into a config.yaml sidecar.

    When SKILL.md is over the line limit and the bloat is in YAML frontmatter
    (specifically the x-augur-config key), this function:
    1. Writes x-augur-config data to config.yaml alongside SKILL.md
    2. Replaces the inline config with x-augur-config-file: config.yaml pointer
    3. Rewrites SKILL.md with the slimmed frontmatter

    Returns an action dict with status/details.
    """
    md_path = skill_dir / "SKILL.md"
    content = md_path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return {"status": "skipped", "reason": "No frontmatter"}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {"status": "skipped", "reason": "Malformed frontmatter"}

    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {"status": "skipped", "reason": "YAML parse error in frontmatter"}

    config = fm.get("x-augur-config")
    if not config or not isinstance(config, dict):
        return {"status": "skipped", "reason": "No x-augur-config in frontmatter"}

    # Count how many lines x-augur-config contributes
    config_yaml = yaml.dump(
        {"x-augur-config": config},
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    config_lines = config_yaml.count("\n")
    if config_lines < 30:
        return {"status": "skipped", "reason": f"x-augur-config only {config_lines} lines, not worth extracting"}

    # Write sidecar
    sidecar_path = skill_dir / _CONFIG_SIDECAR
    sidecar_content = yaml.dump(
        config,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    sidecar_path.write_text(sidecar_content, encoding="utf-8")

    # Replace inline config with pointer
    fm.pop("x-augur-config")
    fm["x-augur-config-file"] = _CONFIG_SIDECAR

    body = parts[2]
    new_fm_yaml = yaml.dump(
        fm,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    ).rstrip("\n")

    new_content = f"---\n{new_fm_yaml}\n---{body}"
    total_before = content.count("\n")
    total_after = new_content.count("\n")

    md_path.write_text(new_content, encoding="utf-8")

    return {
        "status": "fixed",
        "action": "skill-md-too-long",
        "extracted": [_CONFIG_SIDECAR],
        "detail": f"Extracted x-augur-config to {_CONFIG_SIDECAR}, {total_before} -> {total_after} lines",
    }


def _slugify(title: str) -> str:
    """Convert a section title to a filename slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")[:64]


def _parse_sections(content: str) -> list[dict]:
    """Split markdown content into sections by ## headings.

    Returns list of dicts with keys: heading, start_line, end_line, line_count, text.
    The first entry (before any ##) has heading=None.
    """
    lines = content.split("\n")
    sections: list[dict] = []
    current_heading = None
    current_start = 0

    for i, line in enumerate(lines):
        if line.startswith("## "):
            # Close previous section
            sections.append({
                "heading": current_heading,
                "start_line": current_start,
                "end_line": i,
                "line_count": i - current_start,
                "text": "\n".join(lines[current_start:i]),
            })
            current_heading = line[3:].strip()
            current_start = i
    # Close last section
    sections.append({
        "heading": current_heading,
        "start_line": current_start,
        "end_line": len(lines),
        "line_count": len(lines) - current_start,
        "text": "\n".join(lines[current_start:]),
    })
    return sections


def _fix_skill_md_too_long(skill_dir: Path) -> dict:
    """Bring SKILL.md under the line limit by extracting content.

    Strategy (tried in order):
    1. If bloat is in x-augur-config frontmatter, extract to config.yaml sidecar
    2. Otherwise, extract the largest ## section(s) into docs/

    Returns an action dict with status/details.
    """
    md_path = skill_dir / "SKILL.md"
    content = md_path.read_text(encoding="utf-8")
    total_lines = content.count("\n")

    # Don't fix auto-generated files — the source needs fixing instead
    source = _is_auto_generated(content)
    if source:
        return {
            "status": "skipped",
            "action": "skill-md-too-long",
            "reason": f"Auto-generated from {source}; fix the source file instead",
        }

    # Strategy 1: Extract x-augur-config to sidecar if it's the main bloat source
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                fm = {}
            if "x-augur-config" in fm and isinstance(fm["x-augur-config"], dict):
                config_yaml = yaml.dump(
                    {"x-augur-config": fm["x-augur-config"]},
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
                config_lines = config_yaml.count("\n")
                # If config accounts for enough lines that extraction would help
                if config_lines >= 30 and (total_lines - config_lines) < _MAX_LINES:
                    return _extract_config_to_sidecar(skill_dir)

    # Strategy 2: Extract largest ## sections into docs/
    sections = _parse_sections(content)
    # Only consider named sections (skip the preamble before any ##)
    named = [s for s in sections if s["heading"] is not None]
    if not named:
        return {
            "status": "skipped",
            "action": "skill-md-too-long",
            "reason": "No ## sections to extract",
        }

    # Sort by line count descending — extract largest sections first
    named.sort(key=lambda s: s["line_count"], reverse=True)

    lines_to_remove = total_lines - _MAX_LINES
    extracted: list[dict] = []
    docs_dir = skill_dir / "docs"

    for section in named:
        if lines_to_remove <= 0:
            break
        # Skip very small sections — not worth extracting
        if section["line_count"] < 20:
            continue
        slug = _slugify(section["heading"])
        if not slug:
            continue
        extracted.append({"section": section, "slug": slug})
        lines_to_remove -= section["line_count"]

    if not extracted:
        return {
            "status": "skipped",
            "action": "skill-md-too-long",
            "reason": "No section large enough to extract",
        }

    # Perform the extraction — work backwards through the file to preserve line numbers
    lines = content.split("\n")
    docs_dir.mkdir(parents=True, exist_ok=True)
    extracted_files: list[str] = []

    # Sort extracted sections by start_line descending so we can splice safely
    extracted.sort(key=lambda e: e["section"]["start_line"], reverse=True)

    for entry in extracted:
        section = entry["section"]
        slug = entry["slug"]
        doc_file = docs_dir / f"{slug}.md"

        # Write the section content to the docs file
        doc_file.write_text(section["text"].rstrip() + "\n", encoding="utf-8")
        extracted_files.append(f"docs/{slug}.md")

        # Replace the section in the original with a reference link
        heading = section["heading"]
        ref_line = f"## {heading}\n\nSee [{heading}](docs/{slug}.md) for details.\n"
        start = section["start_line"]
        end = section["end_line"]
        lines[start:end] = ref_line.split("\n")

    new_content = "\n".join(lines)
    md_path.write_text(new_content, encoding="utf-8")

    new_line_count = new_content.count("\n")
    return {
        "status": "fixed",
        "action": "skill-md-too-long",
        "extracted": extracted_files,
        "detail": f"Extracted {len(extracted)} section(s) to docs/, {total_lines} -> {new_line_count} lines",
    }


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would fix {len(issues)} reference issue(s)",
        )

    actions: list[dict] = []
    changes: list[str] = []

    for issue in issues:
        action = issue["action"]
        skill_dir = ctx.project_root / issue["file"]
        if not skill_dir.is_dir():
            skill_dir = skill_dir.parent

        if action == "loose-script":
            filename = issue["filename"]
            src = skill_dir / filename
            dst = skill_dir / "scripts" / filename
            try:
                ref_files = [skill_dir / "SKILL.md"]
                move_file_with_refs(src, dst, ref_files)
                actions.append({"status": "fixed", "action": action, "file": filename})
                changes.append(str(dst))
            except FileNotFoundError:
                actions.append({"status": "skipped", "action": action, "reason": f"File '{filename}' no longer exists"})

        elif action == "broken-ref":
            ref = issue["ref"]
            ref_name = Path(ref).name
            candidates = [
                candidate
                for candidate in skill_dir.rglob(ref_name)
                if candidate.name == ref_name
                and _path_matches_disk_case(skill_dir, candidate)
            ]
            if len(candidates) == 1:
                new_ref = candidates[0].relative_to(skill_dir).as_posix()
                md_path = skill_dir / "SKILL.md"
                content = md_path.read_text(encoding="utf-8")
                content = content.replace(ref, new_ref)
                md_path.write_text(content, encoding="utf-8")
                actions.append({"status": "fixed", "action": action, "ref": ref, "new_ref": new_ref})
                changes.append(str(md_path))
            else:
                actions.append({"status": "skipped", "action": action, "reason": f"Could not resolve '{ref}'"})

        elif action == "orphaned-file":
            md_path = skill_dir / "SKILL.md"
            orphan = issue["orphan"]
            content = md_path.read_text(encoding="utf-8")
            # Guard: skip if this resource is already listed
            link_entry = f"- [{orphan}]({orphan})"
            if link_entry in content or f"- {orphan}" in content:
                actions.append({"status": "skipped", "action": action, "reason": f"'{orphan}' already in Additional resources"})
            else:
                if "## Additional resources" not in content:
                    content += "\n## Additional resources\n\n"
                content += f"{link_entry}\n"
                md_path.write_text(content, encoding="utf-8")
                actions.append({"status": "fixed", "action": action, "file": orphan})
                changes.append(str(md_path))

        elif action == "skill-md-too-long":
            result = _fix_skill_md_too_long(skill_dir)
            actions.append(result)
            if result["status"] == "fixed":
                changes.append(str(skill_dir / "SKILL.md"))
                for doc in result.get("extracted", []):
                    changes.append(str(skill_dir / doc))

    fixed = [a for a in actions if a.get("status") == "fixed"]
    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=f"Fixed {len(fixed)}/{len(issues)} reference issues",
    )
