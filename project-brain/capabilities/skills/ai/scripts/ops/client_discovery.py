"""Client-native skill discovery.

Scans Claude Code, Codex, and Gemini config directories for skills
that are NOT synced from Augur (i.e., client-native skills).
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

from src.config.paths import get_client_config_dir, get_project_root

logger = logging.getLogger(__name__)

# Glob patterns per client for finding SKILL.md files
_SCAN_PATTERNS: dict[str, list[str]] = {
    "claude-code": [
        "plugins/**/skills/*/SKILL.md",
        "commands/*/SKILL.md",
        "skills/*/SKILL.md",
    ],
    "codex": [
        "skills/*/SKILL.md",
    ],
    "gemini": [
        "skills/*/SKILL.md",
        "workflows/*/SKILL.md",
    ],
}

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_FIELD_RE = re.compile(r"^(\w[\w-]*):\s*(.+)$", re.MULTILINE)


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Extract YAML-like frontmatter fields from SKILL.md content."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}
    block = match.group(1)
    return {m.group(1): m.group(2).strip().strip("'\"") for m in _FIELD_RE.finditer(block)}


def _load_codex_manifest_skills(native_root: Path) -> set[str]:
    manifest_path = native_root / ".augur-managed.json"
    if not manifest_path.exists():
        return set()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    skills = data.get("skills", [])
    return {name for name in skills if isinstance(name, str)}


def _is_augur_symlink(skill_md_path: Path) -> bool:
    """Check if a SKILL.md is a symlink pointing back to the Augur project tree."""
    try:
        augur_root = str(get_project_root())
    except FileNotFoundError:
        return False

    if skill_md_path.is_symlink():
        target = str(skill_md_path.resolve())
        if target.startswith(augur_root):
            return True
    # Also check parent directory for symlinks
    parent = skill_md_path.parent
    if parent.is_symlink():
        target = str(parent.resolve())
        if target.startswith(augur_root):
            return True
    return False


def _is_augur_managed_codex_copy(skill_md_path: Path) -> bool:
    """Return True for Augur-managed Codex skill copies."""
    try:
        candidate = skill_md_path.resolve()
    except OSError:
        return False

    for scope in ("project", "global"):
        try:
            native_root = (get_client_config_dir("codex", scope=scope) / "skills").resolve()
        except OSError:
            continue
        try:
            candidate.relative_to(native_root)
        except ValueError:
            continue
        skill_name = candidate.parent.name
        if skill_name in _load_codex_manifest_skills(native_root):
            return True
    return False


def discover_client_skills(
    clients: list[str] | None = None,
) -> list[dict]:
    """Discover client-native skills across specified clients.

    Args:
        clients: List of client names to scan. Defaults to all supported clients.

    Returns:
        List of skill metadata dicts with keys:
        name, description, source_client, scope, path, tools, visibility, has_skill_md
    """
    if clients is None:
        clients = list(_SCAN_PATTERNS.keys())

    results: list[dict] = []

    for client in clients:
        if client not in _SCAN_PATTERNS:
            logger.warning("Unknown client: %s, skipping", client)
            continue

        for scope in ("global", "project"):
            try:
                config_dir = get_client_config_dir(client, scope=scope)
            except ValueError:
                continue

            if not config_dir.is_dir():
                if client != "codex" or scope != "global":
                    continue

            for pattern in _SCAN_PATTERNS[client]:
                for candidate in config_dir.glob(pattern):
                    if _is_augur_symlink(candidate):
                        continue
                    if _is_augur_managed_codex_copy(candidate):
                        continue

                    try:
                        content = candidate.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        continue

                    is_flat_prompt = candidate.is_file()
                    fm = _parse_frontmatter(content)
                    name = fm.get("name", candidate.stem if is_flat_prompt else candidate.parent.name)
                    description = fm.get("description", "")
                    tools_raw = fm.get("x-augur-mcp-tools", "")
                    visibility = fm.get("x-augur-visibility", "")

                    results.append({
                        "name": name,
                        "description": description,
                        "source_client": client,
                        "scope": scope,
                        "path": str(candidate if is_flat_prompt else candidate.parent),
                        "tools": [t.strip() for t in tools_raw.strip("[]").split(",") if t.strip()] if tools_raw else [],
                        "visibility": visibility,
                        "has_skill_md": True,
                    })

    return results
