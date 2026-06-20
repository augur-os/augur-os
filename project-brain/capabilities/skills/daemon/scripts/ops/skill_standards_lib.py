"""Shared library for skill-standards loop auto-commands.

Provides parsing, validation, and fixing utilities for SKILL.md
standardization per the Claude Code skills open standard.
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
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml

from src.config.paths import get_all_client_skill_dirs


# --- Standard frontmatter fields (Claude Code skills open standard) ---

STANDARD_FIELDS = frozenset({
    "name",
    "description",
    "argument-hint",
    "disable-model-invocation",
    "user-invocable",
    "allowed-tools",
    "model",
    "context",
    "agent",
    "hooks",
})

AUGUR_PREFIX = "x-augur-"

# Valid skill IDs in this repo use lowercase letters, numbers, hyphens, and underscores.
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}[a-z0-9]?$")

# Markdown link/reference pattern: [text](path) — excludes URLs
_REF_PATTERN = re.compile(r"\[.*?\]\((?!https?://|#)(.*?)\)")


# --- Data Types ---


@dataclass
class SkillMdInfo:
    exists: bool = False
    frontmatter: dict = field(default_factory=dict)
    body: str = ""
    file_refs: list[str] = field(default_factory=list)
    raw: str = ""


@dataclass
class SkillPath:
    """Represents a discovered skill directory."""
    path: Path
    name: str  # directory name
    bundle: str  # parent bundle (hub) name
    plugin_dir: str  # e.g. "skills"


# --- Parsing ---


def _merge_config_sidecar(skill_dir: Path, frontmatter: dict) -> dict:
    """Merge x-augur-config from a sidecar file if pointer is present.

    When frontmatter contains ``x-augur-config-file`` (e.g. "config.yaml")
    and no inline ``x-augur-config``, load the sidecar and inject the data
    as ``x-augur-config`` so consumers see a unified view.
    """
    config_file = frontmatter.get("x-augur-config-file")
    if not config_file or "x-augur-config" in frontmatter:
        return frontmatter

    sidecar_path = skill_dir / config_file
    if not sidecar_path.exists():
        return frontmatter

    try:
        config = yaml.safe_load(sidecar_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return frontmatter

    if isinstance(config, dict):
        frontmatter = {**frontmatter, "x-augur-config": config}
    return frontmatter


def parse_skill_md(skill_dir: Path) -> SkillMdInfo:
    """Parse SKILL.md from a skill directory.

    Supports x-augur-config-file sidecar: when frontmatter contains
    ``x-augur-config-file: config.yaml`` (and no inline x-augur-config),
    the referenced YAML file is loaded and merged as x-augur-config.
    """
    md_path = skill_dir / "SKILL.md"
    if not md_path.exists():
        return SkillMdInfo(exists=False)

    raw = md_path.read_text(encoding="utf-8")
    frontmatter: dict = {}
    body = raw

    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = parts[2].strip()

    # Merge x-augur-config from sidecar file if pointer is present
    frontmatter = _merge_config_sidecar(skill_dir, frontmatter)

    file_refs = _REF_PATTERN.findall(body)

    return SkillMdInfo(
        exists=True,
        frontmatter=frontmatter,
        body=body,
        file_refs=file_refs,
        raw=raw,
    )


# --- Discovery ---


def _is_ghost_dir(skill_dir: Path) -> bool:
    """Check if a directory is a ghost left by a git rename/delete.

    A ghost directory contains only __pycache__ dirs and/or .gitkeep files
    but no real source files or SKILL.md. These linger after git renames
    because __pycache__ is untracked.
    """
    for item in skill_dir.rglob("*"):
        if not item.is_file():
            continue
        # Skip __pycache__ bytecode and .gitkeep placeholders
        if "__pycache__" in item.parts or item.name == ".gitkeep":
            continue
        return False  # Found a real file
    return True  # Only __pycache__/.gitkeep or empty


def iter_all_skills(project_root: Path) -> Iterator[SkillPath]:
    """Yield all skill directories under client skill dirs.

    Only yields skills within the project root — external plugin cache
    directories (e.g. ~/.claude/plugins/cache/) are skipped.
    Skips ghost directories that only contain __pycache__ remnants
    from renamed/deleted skills.
    """
    resolved_root = project_root.resolve()
    for client_skills_dir in get_all_client_skill_dirs(project_root):
        resolved_dir = client_skills_dir.resolve()
        try:
            resolved_dir.relative_to(resolved_root)
        except ValueError:
            continue  # Skip dirs outside project root
        for skill_dir in sorted(client_skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            if _is_ghost_dir(skill_dir):
                continue  # Skip __pycache__-only remnants of deleted skills
            yield SkillPath(
                path=skill_dir,
                name=skill_dir.name,
                bundle=client_skills_dir.parent.name,
                plugin_dir=str(client_skills_dir.relative_to(project_root)),
            )


# --- Validation ---


def validate_name(name: str | None, dir_name: str) -> list[dict]:
    """Validate the name frontmatter field."""
    issues = []
    if not name:
        issues.append({
            "field": "name",
            "problem": "missing",
            "detail": f"Missing name field, should be '{dir_name}'",
        })
    elif name != dir_name:
        issues.append({
            "field": "name",
            "problem": "mismatch",
            "detail": f"name '{name}' does not match directory '{dir_name}'",
        })
    elif not NAME_PATTERN.match(name):
        issues.append({
            "field": "name",
            "problem": "invalid_chars",
            "detail": (
                f"name '{name}' must be lowercase letters, numbers, hyphens, or underscores, "
                "max 64 chars"
            ),
        })
    return issues


def validate_frontmatter(info: SkillMdInfo) -> list[dict]:
    """Validate frontmatter fields against the standard."""
    issues = []
    fm = info.frontmatter

    if not fm.get("description"):
        issues.append({
            "field": "description",
            "problem": "missing",
            "detail": "Missing required description field",
        })

    for key in fm:
        if key not in STANDARD_FIELDS and not key.startswith(AUGUR_PREFIX):
            issues.append({
                "field": key,
                "problem": "unknown",
                "detail": f"Unknown frontmatter field '{key}', should use x-augur- prefix",
            })

    return issues


def validate_folder_structure(skill_dir: Path) -> list[dict]:
    """Check skill folder follows the standard structure."""
    issues = []

    # Check for loose scripts at root (not in scripts/ subdir)
    script_exts = {".py", ".sh", ".bash", ".zsh"}
    for f in skill_dir.iterdir():
        if f.is_file() and f.suffix in script_exts and f.name != "__init__.py":
            issues.append({
                "file": str(f.name),
                "problem": "loose_script",
                "detail": f"Script '{f.name}' should be in scripts/ subdirectory",
            })

    # Check SKILL.md line count
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        lines = skill_md.read_text(encoding="utf-8").count("\n")
        if lines > 500:
            issues.append({
                "file": "SKILL.md",
                "problem": "too_long",
                "detail": f"SKILL.md has {lines} lines, standard recommends under 500",
            })

    return issues


def extract_command_callables(frontmatter: dict) -> set[str]:
    """Collect callable paths declared in canonical SKILL frontmatter."""
    referenced: set[str] = set()

    commands = frontmatter.get("x-augur-commands")
    if isinstance(commands, list):
        for command in commands:
            if isinstance(command, dict):
                callable_path = command.get("callable")
                if isinstance(callable_path, str) and callable_path:
                    referenced.add(callable_path)

    config = frontmatter.get("x-augur-config")
    if not isinstance(config, dict):
        return referenced

    contributions = config.get("contributions")
    if not isinstance(contributions, dict):
        return referenced

    commands = contributions.get("commands")
    if not isinstance(commands, list):
        return referenced

    for command in commands:
        if isinstance(command, dict):
            callable_path = command.get("callable")
            if isinstance(callable_path, str) and callable_path:
                referenced.add(callable_path)

    return referenced


# --- Writing ---


def write_skill_md(path: Path, frontmatter: dict, body: str) -> None:
    """Write a SKILL.md file with frontmatter and body."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    lines.append(yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).rstrip())
    lines.append("---")
    lines.append("")
    lines.append(body)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_frontmatter(skill_md_path: Path, updates: dict) -> None:
    """Update frontmatter fields in an existing SKILL.md, preserving body."""
    info = parse_skill_md(skill_md_path.parent)
    if not info.exists:
        return
    merged = {**info.frontmatter, **updates}
    write_skill_md(skill_md_path, merged, info.body)


def move_file_with_refs(
    src: Path,
    dst: Path,
    ref_files: list[Path],
) -> list[str]:
    """Move a file and update references in ref_files. Returns list of updated files."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)

    updated = []
    old_name = src.name
    new_rel = str(dst.relative_to(dst.parent.parent)) if dst.parent != src.parent else dst.name

    for ref_file in ref_files:
        try:
            content = ref_file.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            continue
        # Only replace within markdown link targets to avoid corrupting prose
        new_content = content.replace(f"]({old_name})", f"]({new_rel})")
        if new_content != content:
            ref_file.write_text(new_content, encoding="utf-8")
            updated.append(str(ref_file))

    return updated
