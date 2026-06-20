"""auto-frontmatter-lint: Validate user-facing files use markdown with YAML frontmatter.

Enforces ADR-404: ADRs, actions, and vault data should be .md with YAML frontmatter.
Pure YAML is only for machine config (config.yaml, seeds, versions).

Difficulty levels:
  d0: ADR files only
  d1+: plugin action files
  d2+: vault action files
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

from src.config.paths import get_all_client_skill_dirs
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-frontmatter-lint"


def _rel_path(path: Path, base: Path) -> str:
    """Return a project-relative path, falling back to absolute if outside the base."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _check_frontmatter(path: Path, rel_base: Path) -> dict | None:
    """Check if a .md file starts with --- frontmatter. Returns issue dict or None."""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None

    if not content.startswith("---"):
        return {
            "action": "missing-frontmatter",
            "file": _rel_path(path, rel_base),
            "detail": f"File lacks YAML frontmatter (must start with ---)",
        }
    return None


def _check_stale_yaml(directory: Path, pattern: str, rel_base: Path) -> list[dict]:
    """Check for .yaml files that should have been migrated to .md."""
    issues = []
    for yaml_file in sorted(directory.rglob(pattern)):
        rel_path = _rel_path(yaml_file, rel_base)
        issues.append({
            "action": "stale-yaml-action",
            "file": rel_path,
            "path": rel_path,
            "kind": "actionable",
            "finding_band": "mechanical",
            "path_fix": True,
            "detail": f"Action file is still YAML — should be .md with frontmatter (ADR-404)",
        })
    return issues


def scan(ctx: OpsContext) -> ScanResult:
    """Validate frontmatter format compliance."""
    issues = []

    # d0: ADR files
    decisions_dir = ctx.project_root / "docs" / "decisions"
    if decisions_dir.is_dir():
        for adr in sorted(decisions_dir.glob("ADR-*.md")):
            issue = _check_frontmatter(adr, ctx.project_root)
            if issue:
                issues.append(issue)

    if ctx.difficulty < 1:
        severity = "error" if issues else "info"
        return ScanResult(
            issues=issues,
            summary=f"{len(issues)} frontmatter issue(s) found (d0: ADRs only)",
            severity=severity,
        )

    # d1+: skill action files (project-local only, skip read-only plugin caches)
    for skills_dir in get_all_client_skill_dirs(ctx.project_root):
        try:
            skills_dir.relative_to(ctx.project_root)
        except ValueError:
            continue  # skip plugin cache dirs outside project root
        # Check for stale .yaml action files
        issues.extend(_check_stale_yaml(skills_dir, "*/actions/*.yaml", ctx.project_root))
        # Check .md action files have frontmatter
        for md_file in sorted(skills_dir.glob("*/actions/*.md")):
            issue = _check_frontmatter(md_file, ctx.project_root)
            if issue:
                issues.append(issue)

    if ctx.difficulty < 2:
        severity = "error" if issues else "info"
        return ScanResult(
            issues=issues,
            summary=f"{len(issues)} frontmatter issue(s) found (d1: ADRs + plugin actions)",
            severity=severity,
        )

    # d2+: vault action files
    import os

    from src.config.path_primitives import resolve_vault_standalone
    vault_dir = resolve_vault_standalone()
    if vault_dir.is_dir():
        issues.extend(_check_stale_yaml(vault_dir, "actions/*.yaml", vault_dir))
        for md_file in sorted(vault_dir.rglob("actions/*.md")):
            issue = _check_frontmatter(md_file, vault_dir)
            if issue:
                issues.append(issue)

    severity = "error" if issues else "info"
    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} frontmatter issue(s) found (d2: full scan)",
        severity=severity,
    )


def _migrate_yaml_to_md(yaml_path: Path) -> Path | None:
    """Convert a YAML action file to .md with YAML frontmatter (ADR-404).

    Reads the YAML content, wraps it in --- frontmatter delimiters,
    and writes a .md file. Removes the original .yaml file.
    Returns the new Markdown path on success.
    """
    try:
        content = yaml_path.read_text(encoding="utf-8").strip()
        md_path = yaml_path.with_suffix(".md")
        md_path.write_text(f"---\n{content}\n---\n", encoding="utf-8")
        yaml_path.unlink()
        return md_path
    except Exception:
        return None


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Auto-fix stale YAML action files by migrating to .md with frontmatter."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would fix {len(issues)} frontmatter issue(s)",
        )

    if not issues:
        return FixResult(success=True, summary="No frontmatter issues to report")

    # d2+: auto-migrate stale YAML action files to .md
    migrated = []
    remaining = []
    for issue in issues:
        file_rel = issue.get("file", "")
        action = issue.get("action", "")
        if action == "stale-yaml-action" and file_rel and ctx.difficulty >= 2:
            yaml_path = ctx.project_root / file_rel
            migrated_path = _migrate_yaml_to_md(yaml_path) if yaml_path.is_file() else None
            if migrated_path is not None:
                migrated.append((file_rel, str(migrated_path.relative_to(ctx.project_root))))
            else:
                remaining.append(issue)
        else:
            remaining.append(issue)

    # Write remaining findings summary
    changes = [path for pair in migrated for path in pair]
    report_dir = ctx.project_root / "docs" / "generated" / "hardening"
    report_dir.mkdir(parents=True, exist_ok=True)

    from datetime import date
    report_file = report_dir / f"frontmatter-lint-{date.today().isoformat()}.md"

    lines = [
        "# Frontmatter Lint Report",
        "",
        f"**{len(migrated)} auto-migrated, {len(remaining)} remaining**",
        "",
    ]
    if migrated:
        lines.extend(["## Migrated (YAML → .md)", ""])
        for old_path, new_path in migrated:
            lines.append(f"- `{old_path}` → `{new_path}`")
        lines.append("")
    if remaining:
        lines.extend([
            "## Remaining Issues", "",
            "| File | Issue |",
            "|------|-------|",
        ])
        for issue in remaining:
            lines.append(f"| `{issue.get('file', 'unknown')}` | {issue.get('detail', issue.get('action', ''))} |")
        lines.append("")

    report_file.write_text("\n".join(lines), encoding="utf-8")
    fix_type = "code-fix" if migrated else "report"
    return FixResult(
        success=True,
        changes=changes,
        summary=f"Migrated {len(migrated)} YAML→MD, {len(remaining)} remaining",
        fix_type=fix_type,
    )
