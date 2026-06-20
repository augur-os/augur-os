"""auto-root-pollution: Detect and relocate repo-local hygiene regressions.

The project root was polluted with 50+ screenshot PNGs and stray files
because no scanner detected it. This command scans the project root for
files and directories that don't belong, removes safe junk inside repo
hotspots, and flags legacy plugin skill copies that should no longer live
under ``plugins/*/skills/*``.

Scan:
  - difficulty 0: root strays + junk files in plugins/skills/scripts/factory
  - difficulty 1+: also flag legacy plugin skill copies for manual cleanup
Fix: relocates safe junk to runtime state (_collateral/){timestamp}/
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
import shutil
from datetime import datetime
from pathlib import Path

from src.config.paths import get_project_brain_skills_dir
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_issue
from src.lib.repo_hygiene import is_allowed_root_item

name = "auto-root-pollution"

_BINARY_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".pdf",
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".mp3", ".wav", ".flac", ".aac",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".dmg", ".iso", ".exe", ".msi",
}

_SAFE_JUNK_FILE_NAMES: set[str] = {".DS_Store"}
_SAFE_JUNK_FILE_SUFFIXES: tuple[str, ...] = (".bak", ".orig", ".rej")
_SAFE_JUNK_DIR_NAMES: set[str] = {"__pycache__"}
_LEGACY_PLUGIN_SKILL_ALLOWLIST: set[str] = {"overview"}
_JUNK_SCAN_ROOTS: tuple[str, ...] = ("plugins", "skills", "scripts", "factory")


def _is_binary(name: str) -> bool:
    """Check if a filename has a binary extension."""
    suffix = Path(name).suffix.lower()
    return suffix in _BINARY_EXTENSIONS


def _get_collateral_dir() -> Path:
    """Resolve the collateral directory for relocated stray files.

    Uses runtime state dir (auto-cleaned) rather than Documents (permanent).
    """
    try:
        from src.config.paths import get_runtime_dir
        return get_runtime_dir() / "_collateral"
    except (ImportError, Exception):
        return Path.home() / "Library" / "Application Support" / "Augur" / "state" / "_collateral"


def _scan_root_entries(root: Path, difficulty: int) -> tuple[list[dict], int]:
    """Scan root entries against the canonical repo layout."""
    issues: list[dict] = []
    entries_checked = 0

    for entry in sorted(root.iterdir()):
        entry_name = entry.name
        entries_checked += 1

        if is_allowed_root_item(entry_name):
            continue
        if difficulty < 1 and entry.is_dir():
            continue
        if difficulty < 1 and not _is_binary(entry_name):
            continue

        issues.append({
            "action": "stray-root-dir" if entry.is_dir() else "stray-root-file",
            "name": entry_name,
            "path": str(entry),
            "binary": _is_binary(entry_name),
        })

    return issues, entries_checked


def _scan_safe_junk(root: Path) -> list[dict]:
    """Scan known junk inside repo-owned directories."""
    issues: list[dict] = []

    for root_name in _JUNK_SCAN_ROOTS:
        scan_root = root / root_name
        if not scan_root.exists():
            continue

        for path in scan_root.rglob("*"):
            rel_path = path.relative_to(root)
            if any(part in {"node_modules", ".git", ".venv"} for part in rel_path.parts):
                continue
            if path.is_file() and (
                path.name in _SAFE_JUNK_FILE_NAMES
                or path.name.endswith(_SAFE_JUNK_FILE_SUFFIXES)
            ):
                issues.append({
                    **make_issue(
                        category=name,
                        detail=f"Safe junk file should be cleaned: {rel_path}",
                        path=str(path),
                        kind="maintenance",
                        root_cause_type="generated_artifact",
                        fixability="auto",
                    ),
                    "action": "safe-junk-file",
                    "name": path.name,
                    "relative_path": str(rel_path),
                })
            elif path.is_dir() and path.name in _SAFE_JUNK_DIR_NAMES:
                issues.append({
                    **make_issue(
                        category=name,
                        detail=f"Safe junk directory should be cleaned: {rel_path}",
                        path=str(path),
                        kind="maintenance",
                        root_cause_type="generated_artifact",
                        fixability="auto",
                    ),
                    "action": "safe-junk-dir",
                    "name": path.name,
                    "relative_path": str(rel_path),
                })

    return issues


def _scan_legacy_plugin_skill_dirs(root: Path) -> list[dict]:
    """Flag legacy skill directories that still live under plugins/*/skills/*."""
    issues: list[dict] = []
    plugins_root = root / "plugins"
    live_skills_root = get_project_brain_skills_dir(root)
    if not plugins_root.is_dir():
        return issues

    for skill_dir in sorted(plugins_root.glob("*/skills/*")):
        if not skill_dir.is_dir():
            continue
        if skill_dir.name.startswith(".") or skill_dir.name in _LEGACY_PLUGIN_SKILL_ALLOWLIST:
            continue

        rel = skill_dir.relative_to(root)
        live_skill = live_skills_root / skill_dir.name
        issues.append({
            "action": "legacy-plugin-skill-dir",
            "name": skill_dir.name,
            "path": str(skill_dir),
            "relative_path": str(rel),
            "has_live_skill": live_skill.is_dir(),
        })

    return issues


def _scan_script_candidates(root: Path) -> list[dict]:
    """Flag repo scripts that look like one-off migrations for manual review."""
    issues: list[dict] = []
    scripts_root = root / "scripts"
    if not scripts_root.is_dir():
        return issues

    migrate_dir = scripts_root / "migrate"
    if migrate_dir.is_dir():
        issues.append({
            "action": "legacy-script-candidate",
            "name": "migrate",
            "path": str(migrate_dir),
            "relative_path": str(migrate_dir.relative_to(root)),
        })

    for candidate in sorted(scripts_root.glob("migrate_*.py")):
        issues.append({
            "action": "legacy-script-candidate",
            "name": candidate.name,
            "path": str(candidate),
            "relative_path": str(candidate.relative_to(root)),
        })

    return issues


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    root = ctx.project_root
    issues, entries_checked = _scan_root_entries(root, ctx.difficulty)
    issues.extend(_scan_safe_junk(root))
    if ctx.difficulty >= 1:
        issues.extend(_scan_legacy_plugin_skill_dirs(root))
        issues.extend(_scan_script_candidates(root))

    if not issues:
        return ScanResult(
            issues=[],
            summary=f"Project root clean — {entries_checked} entries checked",
            severity="info",
            items_scanned=entries_checked,
        )

    binary_count = sum(1 for i in issues if i.get("binary"))
    legacy_count = sum(1 for i in issues if i["action"] == "legacy-plugin-skill-dir")
    script_count = sum(1 for i in issues if i["action"] == "legacy-script-candidate")
    dir_count = sum(
        1
        for i in issues
        if i["action"] in {"stray-root-dir", "safe-junk-dir", "legacy-plugin-skill-dir", "legacy-script-candidate"}
    )
    file_count = len(issues) - dir_count

    parts: list[str] = []
    if file_count:
        parts.append(f"{file_count} file issue(s)")
    if binary_count:
        parts.append(f"{binary_count} binary")
    if dir_count:
        parts.append(f"{dir_count} dir issue(s)")
    if legacy_count:
        parts.append(f"{legacy_count} legacy plugin skill dir(s)")
    if script_count:
        parts.append(f"{script_count} legacy script candidate(s)")

    return ScanResult(
        issues=issues,
        summary=f"Repo hygiene regression: {', '.join(parts)}",
        severity="warning",
        items_scanned=entries_checked,
    )


# ---------------------------------------------------------------------------
# Fix
# ---------------------------------------------------------------------------

def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if not issues:
        return FixResult(success=True, summary="No hygiene issues to relocate")

    movable = [
        issue
        for issue in issues
        if issue["action"] in {"stray-root-dir", "stray-root-file", "safe-junk-file", "safe-junk-dir"}
    ]
    manual = [
        issue
        for issue in issues
        if issue["action"] in {"legacy-plugin-skill-dir", "legacy-script-candidate"}
    ]

    if ctx.dry_run:
        names = [i.get("relative_path") or i["name"] for i in movable]
        if manual:
            names.extend(f"manual:{i['relative_path']}" for i in manual)
        return FixResult(
            success=True,
            summary=f"Dry run: would relocate {len(movable)} safe item(s): {', '.join(names)}",
        )

    collateral = _get_collateral_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = collateral / timestamp
    if movable:
        dest_dir.mkdir(parents=True, exist_ok=True)

    moved: list[str] = []
    errors: list[str] = []

    for issue in movable:
        src_path = Path(issue["path"])
        if not src_path.exists():
            continue
        try:
            rel_path = src_path.relative_to(ctx.project_root)
        except ValueError:
            rel_path = Path(issue["name"])

        # Ephemeral junk dirs (__pycache__) are deleted in-place — moving
        # them to collateral is pointless since Python recreates them on
        # the next import.
        if issue["action"] == "safe-junk-dir" and src_path.is_dir():
            try:
                shutil.rmtree(src_path)
                moved.append(str(rel_path))
            except OSError as exc:
                errors.append(f"{issue['name']}: {exc}")
            continue

        dest_path = dest_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            suffix = datetime.now().strftime("%H%M%S")
            dest_path = dest_path.with_name(f"{dest_path.stem}-{suffix}{dest_path.suffix}")
            dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src_path), str(dest_path))
            moved.append(str(rel_path))
        except OSError as exc:
            errors.append(f"{issue['name']}: {exc}")

    manual_note = ""
    if manual:
        manual_paths = ", ".join(issue["relative_path"] for issue in manual)
        manual_note = f"; {len(manual)} manual hygiene candidate(s) need review: {manual_paths}"

    if errors:
        return FixResult(
            success=False,
            changes=moved,
            summary=(
                f"Moved {len(moved)} item(s) to {dest_dir}; "
                f"{len(errors)} error(s): {'; '.join(errors)}{manual_note}"
            ),
        )

    return FixResult(
        success=True,
        changes=moved,
        summary=f"Relocated {len(moved)} hygiene item(s) to {dest_dir}{manual_note}",
    )
