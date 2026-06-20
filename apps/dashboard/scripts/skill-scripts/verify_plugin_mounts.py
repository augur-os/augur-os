#!/usr/bin/env python3
"""Verify plugin mount integrity — detect stale mounts and direct edits."""

import sys
import os

sys.path.insert(0, '.')

import json
from pathlib import Path
from src.config.paths import get_project_root

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging

    def get_entity_logger(name: str):
        return logging.getLogger(name)


logger = get_entity_logger("frontend")


AUTO_GENERATED_HEADER = "AUTO-GENERATED FILE"


def find_mounted_files(dashboard_app: Path) -> list[Path]:
    """Find all auto-generated mounted files in the dashboard."""
    mounted = []
    for f in dashboard_app.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix not in {".tsx", ".ts", ".css"}:
            continue
        try:
            first_lines = f.read_text()[:500]
            if AUTO_GENERATED_HEADER in first_lines:
                mounted.append(f)
        except (PermissionError, OSError):
            continue
    return mounted


def extract_source_path(mounted_file: Path) -> str | None:
    """Extract the source plugin path from the auto-generated header."""
    try:
        content = mounted_file.read_text()
        lines = content.splitlines()[:20]
        for i, line in enumerate(lines):
            normalized = line.strip().lstrip("* ").strip()
            if "Source:" in line:
                return line.split("Source:")[1].strip()
            if "SOURCE file at:" in line or "source file at:" in line:
                for candidate in lines[i + 1 :]:
                    normalized_candidate = candidate.strip().lstrip("* ").strip().strip("`")
                    if normalized_candidate.startswith("plugins/"):
                        return normalized_candidate
                return None
            if normalized.startswith("plugins/"):
                return normalized.strip("`")
    except (PermissionError, OSError):
        pass
    return None


def _trim_issues(issues: list[str], max_items: int = 100) -> tuple[list[str], int]:
    if len(issues) <= max_items:
        return issues, 0
    return issues[:max_items], len(issues) - max_items


def verify_mounts(root: Path) -> dict[str, object]:
    """Verify all mounted files have valid sources."""
    errors: list[str] = []
    warnings: list[str] = []
    dashboard_app = root / "apps" / "dashboard" / "app"

    if not dashboard_app.exists():
        return {
            "success": False,
            "summary": {
                "checked_files": 0,
                "stale_mounts": 0,
                "possible_direct_edits": 0,
                "missing_source_header": 0,
                "errors_count": 1,
                "warnings_count": 0,
            },
            "errors": ["Dashboard app directory not found"],
            "warnings": [],
        }

    mounted_files = find_mounted_files(dashboard_app)

    if not mounted_files:
        warnings.append("No auto-generated mounted files found (expected some)")
        return {
            "success": True,
            "summary": {
                "checked_files": 0,
                "stale_mounts": 0,
                "possible_direct_edits": 0,
                "missing_source_header": 0,
                "errors_count": 0,
                "warnings_count": 1,
            },
            "errors": [],
            "warnings": warnings,
        }

    stale_count = 0
    edited_count = 0
    missing_source_count = 0
    strict_edit_check = os.getenv("VERIFY_MOUNT_STRICT_EDIT_CHECK", "0") == "1"
    for mounted in mounted_files:
        source_path = extract_source_path(mounted)
        if not source_path:
            rel = mounted.relative_to(root)
            warnings.append(f"No source path in header: {rel}")
            missing_source_count += 1
            continue

        source_file = root / source_path
        if not source_file.exists():
            rel = mounted.relative_to(root)
            errors.append(f"STALE MOUNT: {rel} -> source missing: {source_path}")
            stale_count += 1
        else:
            # Check if mounted file is newer (possible direct edit)
            if strict_edit_check and mounted.stat().st_mtime > source_file.stat().st_mtime + 60:
                rel = mounted.relative_to(root)
                warnings.append(f"POSSIBLY EDITED DIRECTLY: {rel} (newer than source)")
                edited_count += 1

    logger.info(f"Checked {len(mounted_files)} mounted files, {stale_count} stale")
    warnings_trimmed, warnings_hidden = _trim_issues(warnings)
    errors_trimmed, errors_hidden = _trim_issues(errors)
    return {
        "success": len(errors) == 0,
        "summary": {
            "checked_files": len(mounted_files),
            "stale_mounts": stale_count,
            "possible_direct_edits": edited_count,
            "missing_source_header": missing_source_count,
            "errors_count": len(errors),
            "warnings_count": len(warnings),
        },
        "errors": errors_trimmed,
        "warnings": warnings_trimmed,
        "errors_truncated": errors_hidden,
        "warnings_truncated": warnings_hidden,
    }


def main():
    root = get_project_root()
    result = verify_mounts(root)
    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
