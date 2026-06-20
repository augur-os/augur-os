"""
sync_agents/generators.py

File generation utilities for the sync_agents package.

Contains:
    - write_generated_file(): Write generated files with header and read-only perms.
    - clean_directory(): Clean all files in a directory, handling read-only files.
    - generate_ide_manifest(): Generate .antigravity/ide-manifest.json for IDE discovery.
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
from datetime import datetime
from pathlib import Path, PurePosixPath

from .constants import (
    PROJECT_ROOT,
    SOURCE_RULES_LABEL,
    ANTIGRAVITY_IDE_MANIFEST,
    HEADER_TEMPLATE,
    GENERATED_FILES,
    logger,
)
from src.lib.generated_artifacts import write_stable_json


def write_generated_file(path: Path, content: str, source: str) -> None:
    """Write a generated file with header and read-only permissions.

    Skips write when the file already exists with identical content,
    avoiding unnecessary file-system events that trigger hot-reload watchers.
    """
    try:
        if not path.parent.exists():
            path.parent.mkdir(parents=True)

        header = HEADER_TEMPLATE.format(source=source)
        # For markdown files with YAML frontmatter, insert header AFTER frontmatter
        # so parsers (Claude Code, Gemini CLI) that require frontmatter at line 1
        # can read it correctly.
        if path.suffix == ".md" and content.startswith("---"):
            try:
                end_idx = content.index("---", 3) + 3
                final_content = content[:end_idx] + "\n" + header + content[end_idx:]
            except ValueError:
                final_content = header + content
        else:
            final_content = header + content

        # Skip write if content unchanged (hot-reload optimization)
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
                if existing == final_content:
                    GENERATED_FILES.append(path)
                    return
            except OSError:
                pass
            current_mode = path.stat().st_mode
            if not (current_mode & 0o200):
                path.chmod(current_mode | 0o200)

        path.write_text(final_content, encoding="utf-8")
        path.chmod(0o444)  # Read only

        GENERATED_FILES.append(path)
        try:
            display_path = path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = path
        logger.info(f"✅ Generated {display_path}")

    except PermissionError as e:
        logger.error(f"❌ Permission denied for {path}: {e}")
    except OSError as e:
        logger.error(f"❌ Failed to generate {path}: {e}")


def clean_directory(path: Path) -> None:
    """Clean all files in a directory, handling read-only files."""
    if not path.exists():
        path.mkdir(parents=True)
        return

    for item in path.iterdir():
        if item.is_file():
            try:
                if not os.access(item, os.W_OK):
                    item.chmod(0o666)
                item.unlink()
            except PermissionError as e:
                logger.warning(f"Permission denied deleting {item}: {e}")
            except OSError as e:
                logger.warning(f"Failed to delete {item}: {e}")


def generate_ide_manifest() -> None:
    """Generate .antigravity/ide-manifest.json for IDE discovery."""
    try:
        # Collect all generated files relative to PROJECT_ROOT
        all_files = []
        for f in GENERATED_FILES:
            try:
                rel = f.relative_to(PROJECT_ROOT)
            except ValueError:
                # Skip files outside the repo root (e.g., ~/.codex)
                continue
            all_files.append(rel.as_posix())

        # Antigravity only needs its own generated files under .antigravity/.
        antigravity_manifest_files = []

        for f_str in all_files:
            if f_str.startswith(".antigravity/"):
                # Calculate relative path from .antigravity/
                # e.g. .antigravity/workflows/foo.md -> workflows/foo.md
                # Use PurePosixPath to ensure forward slashes on all platforms
                rel_path = str(PurePosixPath(f_str).relative_to(".antigravity"))
                antigravity_manifest_files.append(rel_path)

        antigravity_path = ANTIGRAVITY_IDE_MANIFEST
        if antigravity_manifest_files:
            antigravity_manifest = {
                "source": SOURCE_RULES_LABEL,
                "generator": "project-brain/capabilities/skills/ai/scripts/sync_agents/",
                "generated_at": datetime.now().isoformat(),
                "files": sorted(set(antigravity_manifest_files)),
                "note": "AUTO-GENERATED (Filtered for Antigravity)",
            }

            if not antigravity_path.parent.exists():
                antigravity_path.parent.mkdir(parents=True, exist_ok=True)

            write_stable_json(
                antigravity_path,
                antigravity_manifest,
                volatile_keys=("generated_at",),
            )
            logger.info(f"✅ Generated {antigravity_path.relative_to(PROJECT_ROOT)} (Filtered)")
        elif antigravity_path.exists():
            antigravity_path.unlink()
            logger.info(f"🧹 Removed stale {antigravity_path.relative_to(PROJECT_ROOT)}")

    except Exception as e:
        logger.error(f"Failed to generate IDE manifest: {e}")
