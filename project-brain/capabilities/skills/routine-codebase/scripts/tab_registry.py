"""auto-tab-registry: Validate tab registry entries resolve to page files or catch-all routes.

Prevents build failures from orphan tabs by checking that every tab href
in generated-registry.ts has a corresponding page.tsx or catch-all route.
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
import shutil
from pathlib import Path

try:
    import yaml as _yaml
    def _yaml_safe_load(text: str) -> dict:
        return _yaml.safe_load(text) or {}
except ImportError:
    import json as _json

    def _yaml_safe_load(text: str) -> dict:
        """Minimal YAML-subset parser for simple key: value frontmatter."""
        result: dict = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                result[key.strip()] = val.strip()
        return result

from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
    report_only_fix,
    write_report,
)

name = "auto-tab-registry"

REGISTRY_REL = Path("apps/dashboard/lib/tabs/generated-registry.ts")
APP_REL = Path("apps/dashboard/app")
FEATURES_PAGES_REL = Path("apps/dashboard/features/pages")


def _parse_registry(registry_path: Path) -> dict[str, list[dict]]:
    """Parse generated-registry.ts and return {hub_id: [tab_dicts]}."""
    if not registry_path.exists():
        return {}

    text = registry_path.read_text()
    hubs: dict[str, list[dict]] = {}

    # Match hub blocks: "hub_id": { ... }
    hub_pattern = re.compile(r'"(\w[\w-]*)"\s*:\s*\{', re.MULTILINE)
    tab_pattern = re.compile(r'"href"\s*:\s*"([^"]+)"')

    current_hub: str | None = None
    brace_depth = 0

    for line in text.splitlines():
        hub_match = hub_pattern.search(line)
        if hub_match and brace_depth == 1:
            current_hub = hub_match.group(1)
            hubs[current_hub] = []

        brace_depth += line.count("{") - line.count("}")

        if current_hub is not None:
            tab_match = tab_pattern.search(line)
            if tab_match:
                href = tab_match.group(1)
                hubs[current_hub].append({"href": href})

    return hubs


def _parse_registry_generated_source_slugs(registry_path: Path) -> dict[str, set[str]]:
    """Parse generated-registry.ts for config/auto page slugs per hub.

    The tab generator can synthesize routeable pages from YAML wrappers and
    generated root configs even when there is no committed page.tsx under
    features/pages/ or apps/dashboard/app/. The scanner needs to treat those
    generated entries as valid page sources to avoid false missing-catchall and
    orphan-tab reports.
    """
    if not registry_path.exists():
        return {}

    hub_pattern = re.compile(r'"(\w[\w-]*)"\s*:\s*\{', re.MULTILINE)
    href_pattern = re.compile(r'"href"\s*:\s*"([^"]+)"')

    current_hub: str | None = None
    current_section: str | None = None
    brace_depth = 0
    bracket_depth = 0
    sources: dict[str, set[str]] = {}

    for line in registry_path.read_text().splitlines():
        hub_match = hub_pattern.search(line)
        if hub_match and brace_depth == 1:
            current_hub = hub_match.group(1)
            sources.setdefault(current_hub, set())

        if current_hub and current_section is None:
            if '"configPages": [' in line:
                current_section = "configPages"
                bracket_depth = line.count("[") - line.count("]")
            elif '"autoPages": [' in line:
                current_section = "autoPages"
                bracket_depth = line.count("[") - line.count("]")
        elif current_hub and current_section is not None:
            href_match = href_pattern.search(line)
            if href_match:
                parts = href_match.group(1).strip("/").split("/")
                if len(parts) > 1:
                    sources[current_hub].add("/".join(parts[1:]))
            bracket_depth += line.count("[") - line.count("]")
            if bracket_depth <= 0:
                current_section = None

        brace_depth += line.count("{") - line.count("}")

    return sources


def _parse_catchall_pages(registry_ts: Path) -> set[str]:
    """Parse a [[...slug]]/registry.ts and return the set of registered page paths."""
    if not registry_ts.exists():
        return set()
    text = registry_ts.read_text()
    # Match entries like: 'knowledge/memory': () => import(...)
    return set(re.findall(r"'([^']+)'\s*:", text))


def _hub_has_catchall(app_dir: Path, hub_id: str) -> bool:
    """Check if hub has a [[...slug]]/page.tsx catch-all route."""
    return (app_dir / hub_id / "[[...slug]]" / "page.tsx").exists()


def _hub_has_subpage_tabs(tabs: list[dict], hub_id: str) -> bool:
    """Check if a hub has any tabs pointing to sub-pages (not just the hub root)."""
    for tab in tabs:
        href = tab.get("href", "")
        parts = href.strip("/").split("/")
        if len(parts) > 1:
            return True
    return False


def _hub_has_page_sources(project_root: Path, hub_id: str) -> bool:
    """Check if mount-plugins would generate a catch-all for this hub.

    Catch-all routes are auto-generated by mount-plugins Phase 6b when page
    sources exist in features/pages/{hub}/, project-brain/capabilities/skills/*/augur/dashboard/,
    or project-brain/capabilities/skills/*/augur/pages/*.yaml with matching hub field.
    These generated files are intentionally not committed to git.
    """
    features_dir = project_root / FEATURES_PAGES_REL / hub_id
    if features_dir.is_dir():
        # Check if any page.tsx files exist under this hub's features/pages dir
        for p in features_dir.rglob("page.tsx"):
            return True
    # Also check project-brain/capabilities/skills for pages contributing to this hub
    skills_dir = project_root / "project-brain" / "capabilities" / "skills"
    if skills_dir.is_dir():
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            # Check augur/dashboard/ for TSX pages
            dashboard_dir = skill_dir / "augur" / "dashboard"
            if dashboard_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    content = skill_md.read_text(errors="replace")
                    if f"x-augur-hub: {hub_id}" in content:
                        for p in dashboard_dir.rglob("page.tsx"):
                            return True
            # Check augur/pages/*.yaml for YAML config pages
            pages_dir = skill_dir / "augur" / "pages"
            if pages_dir.is_dir():
                for yaml_file in pages_dir.glob("*.yaml"):
                    try:
                        config = _yaml_safe_load(yaml_file.read_text(errors="replace"))
                        if config.get("hub") == hub_id:
                            return True
                    except Exception:
                        continue
    return False


def _collect_source_slugs(project_root: Path, hub_id: str) -> set[str]:
    """Collect slug paths that mount-plugins would register for this hub.

    Checks two sources:
    1. TSX pages in features/pages/{hub}/{skill}/page.tsx
    2. YAML config pages in project-brain/capabilities/skills/*/augur/pages/*.yaml with matching hub field

    Returns slugs like "knowledge/memory", "reading-list/import", "consulting-template".
    """
    slugs: set[str] = set()

    # Source 1: features/pages/{hub}/{skill}/ TSX pages
    features_dir = project_root / FEATURES_PAGES_REL / hub_id
    if features_dir.is_dir():
        for skill_dir in sorted(features_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            # Check for top-level page
            if (skill_dir / "page.tsx").exists():
                slugs.add(skill_name)
            # Check for sub-pages: {skill}/{sub}/page.tsx
            for sub_dir in sorted(skill_dir.iterdir()):
                if not sub_dir.is_dir():
                    continue
                if (sub_dir / "page.tsx").exists():
                    slugs.add(f"{skill_name}/{sub_dir.name}")

    # Source 2: YAML config pages in project-brain/capabilities/skills/*/augur/pages/*.yaml
    skills_dir = project_root / "project-brain" / "capabilities" / "skills"
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            pages_dir = skill_dir / "augur" / "pages"
            if not pages_dir.is_dir():
                continue
            for yaml_file in sorted(pages_dir.glob("*.yaml")):
                try:
                    config = _yaml_safe_load(yaml_file.read_text(errors="replace"))
                    if config.get("hub") == hub_id and config.get("route"):
                        slugs.add(config["route"])
                except Exception:
                    continue

    return slugs


def _find_template_catchall(app_dir: Path) -> Path | None:
    """Find an existing catch-all directory to use as template."""
    for hub_dir in sorted(app_dir.iterdir()):
        if not hub_dir.is_dir():
            continue
        candidate = hub_dir / "[[...slug]]" / "page.tsx"
        if candidate.exists():
            return candidate.parent
    return None


def scan(ctx: OpsContext) -> ScanResult:
    """Validate tab registry entries resolve to page files or catch-all routes."""
    registry_path = ctx.project_root / REGISTRY_REL
    app_dir = ctx.project_root / APP_REL

    if not registry_path.exists():
        return ScanResult(
            issues=[make_issue(
                category="missing-registry",
                detail="generated-registry.ts not found - run npm run generate-tabs",
                path=str(REGISTRY_REL),
                kind="environment",
            )],
            summary="Registry file missing",
            severity="error",
            health="broken",
        )

    hubs = _parse_registry(registry_path)
    generated_source_slugs = _parse_registry_generated_source_slugs(registry_path)
    issues: list[dict] = []
    items_scanned = 0

    for hub_id, tabs in hubs.items():
        items_scanned += 1
        has_catchall = _hub_has_catchall(app_dir, hub_id)
        has_subpages = _hub_has_subpage_tabs(tabs, hub_id)
        source_slugs = _collect_source_slugs(ctx.project_root, hub_id) | generated_source_slugs.get(
            hub_id, set()
        )

        # d0: Check hub catch-all exists (only when the hub has sub-page tabs)
        # Overview-only hubs (no sub-page tabs) don't need a catch-all route.
        # Hubs with page sources in features/pages/ or project-brain/capabilities/skills/*/augur/dashboard/
        # get catch-all routes auto-generated by mount-plugins Phase 6b — these
        # are intentionally not committed to git and will appear after build.
        if not has_catchall and has_subpages:
            if source_slugs:
                # Catch-all will be generated by mount-plugins — not a real issue
                pass
            else:
                issues.append(make_issue(
                    category="missing-catchall",
                    detail=f"Hub '{hub_id}' has sub-page tabs but no [[...slug]]/page.tsx catch-all route and no page sources for mount-plugins to generate one",
                    path=f"apps/dashboard/app/{hub_id}/[[...slug]]/page.tsx",
                    kind="actionable",
                    root_cause_type="missing_file",
                    fixability="auto",
                    hub_id=hub_id,
                ))

        # d1+: Validate each tab href resolves
        if ctx.difficulty >= 1:
            catchall_pages: set[str] = set()
            if has_catchall:
                catchall_registry = app_dir / hub_id / "[[...slug]]" / "registry.ts"
                catchall_pages = _parse_catchall_pages(catchall_registry)

            for tab in tabs:
                href = tab.get("href", "")
                if not href:
                    continue
                items_scanned += 1

                # Strip leading /hub_id/ to get the slug
                parts = href.strip("/").split("/")
                if len(parts) <= 1:
                    # Hub root (e.g. /brain) - always resolves to the overview
                    continue

                slug = "/".join(parts[1:])
                tab_id = parts[-1]

                # Check direct page
                direct_page = app_dir / hub_id / slug / "page.tsx"
                if direct_page.exists():
                    continue

                # Check catch-all registry
                if has_catchall and slug in catchall_pages:
                    continue

                # Check page sources that mount-plugins would generate
                if slug in source_slugs:
                    continue

                # Orphan tab
                if not has_catchall and not source_slugs:
                    detail = f"Tab '{tab_id}' in hub '{hub_id}' has no page - hub also missing catch-all"
                elif not has_catchall:
                    detail = f"Tab '{tab_id}' in hub '{hub_id}' (href={href}) has no page source in features/pages/{hub_id}/"
                else:
                    detail = f"Tab '{tab_id}' in hub '{hub_id}' (href={href}) resolves to neither direct page nor catch-all entry"

                issues.append(make_issue(
                    category="orphan-tab",
                    detail=detail,
                    path=f"apps/dashboard/app/{hub_id}/{slug}/page.tsx",
                    kind="actionable",
                    root_cause_type="missing_file",
                    fixability="manual",
                    hub_id=hub_id,
                    tab_id=tab_id,
                    href=href,
                ))

    # d2+: Cross-check registry.ts imports against actual files
    if ctx.difficulty >= 2:
        for hub_id in hubs:
            catchall_registry = app_dir / hub_id / "[[...slug]]" / "registry.ts"
            if not catchall_registry.exists():
                continue
            text = catchall_registry.read_text()
            for match in re.finditer(r"import\(['\"]([^'\"]+)['\"]\)", text):
                import_path = match.group(1)
                items_scanned += 1
                # @skill/ and @/ imports are resolved by Next.js — skip
                # We only flag obviously broken patterns (relative imports)
                if import_path.startswith("./") or import_path.startswith("../"):
                    resolved = (catchall_registry.parent / import_path).resolve()
                    if not resolved.exists() and not resolved.with_suffix(".tsx").exists():
                        issues.append(make_issue(
                            category="dead-registry-import",
                            detail=f"Registry import '{import_path}' in hub '{hub_id}' does not resolve",
                            path=str(catchall_registry.relative_to(ctx.project_root)),
                            kind="actionable",
                            root_cause_type="stale_reference",
                            fixability="manual",
                            hub_id=hub_id,
                        ))

    # Evolution gaps when clean at max difficulty
    if not issues and ctx.difficulty >= 2:
        for hub_id, tabs in hubs.items():
            has_catchall_or_sources = (
                _hub_has_catchall(app_dir, hub_id)
                or bool(
                    _collect_source_slugs(ctx.project_root, hub_id)
                    | generated_source_slugs.get(hub_id, set())
                )
            )
            if not has_catchall_or_sources:
                continue
            tab_count = sum(1 for t in tabs if len(t.get("href", "").strip("/").split("/")) > 1)
            direct_count = sum(
                1 for t in tabs
                if len(t.get("href", "").strip("/").split("/")) > 1
                and (app_dir / hub_id / "/".join(t["href"].strip("/").split("/")[1:]) / "page.tsx").exists()
            )
            if tab_count > 0 and direct_count == 0:
                issues.append(evolution_gap(
                    f"Hub '{hub_id}' has {tab_count} tabs all resolving via catch-all only - "
                    "no dedicated page.tsx files. Next: consider generating stub pages for "
                    "frequently visited tabs.",
                    category="catchall-only-hub",
                ))

    severity = "error" if any(i.get("kind") == "actionable" for i in issues) else "info"
    health = "broken" if severity == "error" else "verified"

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} tab registry issue(s) across {len(hubs)} hubs",
        severity=severity,
        health=health,
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix tab registry issues - auto-create missing catch-all dirs at d1+."""
    if ctx.difficulty < 1:
        report_path = write_report(ctx, "tab-registry-latest.json", {"issues": issues})
        return FixResult(
            success=True,
            actions=[{"report": str(report_path)}],
            summary=f"Tab registry report written with {len(issues)} issue(s)",
            fix_type="report",
        )

    app_dir = ctx.project_root / APP_REL
    template_dir = _find_template_catchall(app_dir)
    actions: list[dict] = []
    changes: list[str] = []

    for issue in issues:
        if issue.get("category") != "missing-catchall":
            continue

        hub_id = issue.get("hub_id", "")
        if not hub_id:
            continue

        target = app_dir / hub_id / "[[...slug]]"
        if target.exists():
            continue

        if ctx.dry_run:
            actions.append({"action": "would-create", "path": str(target)})
            continue

        target.mkdir(parents=True, exist_ok=True)

        if template_dir:
            shutil.copy2(template_dir / "page.tsx", target / "page.tsx")
        else:
            (target / "page.tsx").write_text(
                "'use client';\n"
                "export default function HubPage() { return null; }\n"
            )

        (target / "registry.ts").write_text(
            "// AUTO-GENERATED by mount-plugins — do not edit\n"
            "export const DEFAULT_PATH: string | null = null;\n"
            "\n"
            "export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {\n"
            "};\n"
        )

        actions.append({"action": "created-catchall", "hub": hub_id, "path": str(target)})
        changes.append(str(target / "page.tsx"))
        changes.append(str(target / "registry.ts"))

    non_fixable = [i for i in issues if i.get("category") != "missing-catchall"]
    if non_fixable:
        write_report(ctx, "tab-registry-latest.json", {"issues": non_fixable})

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=f"Created {len(changes) // 2} catch-all route(s), {len(non_fixable)} issue(s) reported",
        fix_type="code-fix" if changes else "report",
    )
