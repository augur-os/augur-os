"""auto-empty-states: Validate dashboard pages handle empty data gracefully.

Pages that load data via hooks (useCachedFetch, useQuery, etc.) should
render a visible empty-state UI when the result set is empty, rather than
showing a blank white screen.

Scan: checks page.tsx files for empty-state handling patterns.
  - difficulty 0: checks pages that use data-loading hooks
  - difficulty 1+: also checks pages that consume props/context data
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
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-empty-states"

DIFFICULTY_SPEC = {
    0: "Surface check — pages using data-loading hooks have empty-state handling",
    1: "Content check — include pages using props/context data",
    2: "Deep check — same as d1",
    3: "Exhaustive — same as d1",
    4: "Expert — same as d1",
}

# Patterns that indicate data loading. The \b keeps `useQuery` from
# substring-matching `useQueryClient` (a cache handle, not a data load —
# it false-positived the login page, which only has a login mutation).
_DATA_HOOKS = re.compile(
    r"useCachedFetch|useQuery\b|useSWR|useFetch|useData\b|useActionRunner"
)

# Broader data consumption patterns (difficulty >= 1)
_DATA_CONSUMPTION = re.compile(
    r"\b(?:"
    r"data|items|results|records|entries|history|skills|agents|lights|scenes|"
    r"pipelines|commits|projects|status|summary|"
    r"[a-z][A-Za-z0-9_]*(?:Data|Items|Results|Records|Entries|History|Skills|"
    r"Agents|Lights|Scenes)"
    r")\s*(?:\?\.|\.)\s*(?:map|filter|forEach)\s*\("
    r"|"
    r"\b(?:"
    r"data|items|results|records|entries|history|skills|agents|lights|scenes|"
    r"pipelines|commits|projects|status|summary|"
    r"[a-z][A-Za-z0-9_]*(?:Data|Items|Results|Records|Entries|History|Skills|"
    r"Agents|Lights|Scenes)"
    r")\?\."
)

# Patterns that indicate empty-state handling. The dashboard uses a mix of
# dedicated components (`EmptySection`, `EmptyState`) and inline copy such as
# "No history entries" or "Nothing needs your attention".
_EMPTY_STATE_PATTERNS = re.compile(
    r"\.length\s*===?\s*0"
    r"|\.length\s*!\s*>"
    r"|!data\b"
    r"|isEmpty"
    r"|[Ee]mpty[A-Z][A-Za-z0-9_]*"
    r"|emptyState"
    r"|[Ee]mpty\s*[Mm]essage"
    r"|NoResults"
    r"|nothing.to.show"
    r"|nothing.found"
    r"|all\s+clear"
    r"|nothing\s+needs\s+your\s+attention"
    r"|[Nn]o\s+[^\\n]{0,80}\b("
    r"data|results?|items?|entries?|records?|history|status|skills?|"
    r"symptoms?|medications?|commits?|pipelines?|devices?|lights?|"
    r"scenes?|available|configured|connected|found|recorded|resolved"
    r")\b",
    re.IGNORECASE,
)

_SKIP_DIRS = {"node_modules", ".next", "__pycache__", "api"}

# When a page delegates content rendering to a local sibling component, the
# scanner should also inspect that component for empty-state handling. Names
# matching this pattern are strong delegation signals (Grid, Content, List,
# View, Section, Panel renderers, etc.). One-hop only — no recursive walk.
_DELEGATE_NAME = re.compile(
    r"\b([A-Z][A-Za-z0-9]*(?:Grid|Content|List|View|Section|Panel|Body|Renderer))\b"
)
_RELATIVE_IMPORT = re.compile(
    r"""from\s+["'](\.{1,2}/[A-Za-z0-9_/\-]+)["']""",
)


def _find_page_files(dashboard_app: Path) -> list[Path]:
    """Find all page.tsx files under the dashboard app directory."""
    pages: list[Path] = []
    if not dashboard_app.is_dir():
        return pages
    for page_file in dashboard_app.rglob("page.tsx"):
        if any(skip in page_file.parts for skip in _SKIP_DIRS):
            continue
        pages.append(page_file)
    return sorted(pages)


def _delegated_empty_state(page_path: Path, content: str) -> bool:
    delegate_names = set(_DELEGATE_NAME.findall(content))
    if not delegate_names:
        return False
    page_dir = page_path.parent
    for match in _RELATIVE_IMPORT.finditer(content):
        rel_import = match.group(1)
        for candidate in (
            page_dir / f"{rel_import}.tsx",
            page_dir / f"{rel_import}.ts",
            page_dir / rel_import / "index.tsx",
            page_dir / rel_import / "index.ts",
        ):
            try:
                if not candidate.is_file():
                    continue
                # Only walk into delegates whose stem matches the rendering
                # naming pattern; don't read every imported file.
                if not _DELEGATE_NAME.fullmatch(candidate.stem):
                    continue
                if not (delegate_names & {candidate.stem}):
                    continue
                delegate_text = candidate.read_text(encoding="utf-8", errors="ignore")
                if _EMPTY_STATE_PATTERNS.search(delegate_text):
                    return True
            except OSError:
                continue
    return False


def scan(ctx: OpsContext) -> ScanResult:
    """Check dashboard pages for empty-state handling."""
    dashboard_app = ctx.project_root / "apps" / "dashboard" / "app"
    if not dashboard_app.is_dir():
        return ScanResult(
            issues=[],
            summary="No dashboard app directory found",
            severity="info",
        )

    pages = _find_page_files(dashboard_app)
    if not pages:
        return ScanResult(
            issues=[],
            summary="No page.tsx files found",
            severity="info",
            items_scanned=0,
        )

    issues: list[dict] = []
    pages_checked = 0

    for page_path in pages:
        try:
            content = page_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        pages_checked += 1

        # Determine if the page loads or consumes data
        uses_data_hook = bool(_DATA_HOOKS.search(content))
        uses_data_consumption = bool(_DATA_CONSUMPTION.search(content))

        # At difficulty 0: only check pages with explicit data-loading hooks
        if ctx.difficulty < 1:
            needs_check = uses_data_hook
        else:
            needs_check = uses_data_hook or uses_data_consumption

        if not needs_check:
            continue

        # Check for empty-state handling, including a one-hop walk into local
        # sibling components whose names imply content rendering (Grid, Content,
        # List, View, etc.). Many page.tsx files only orchestrate state and
        # delegate the empty branch to the renderer they import.
        has_empty_state = bool(_EMPTY_STATE_PATTERNS.search(content))
        if not has_empty_state:
            has_empty_state = _delegated_empty_state(page_path, content)

        if not has_empty_state:
            rel_path = str(page_path.relative_to(ctx.project_root))
            issues.append({
                "fingerprint": f"empty-state:{rel_path}",
                "severity": "warning",
                "message": f"Page loads data but has no empty-state handling",
                "file": rel_path,
                "fixability": "manual",
            })

    if not issues:
        return ScanResult(
            issues=[],
            summary=f"All {pages_checked} data-loading pages have empty-state handling",
            severity="info",
            items_scanned=pages_checked,
        )

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} page(s) missing empty-state handling (of {pages_checked} checked)",
        severity="warning",
        items_scanned=pages_checked,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Report-only: empty-state gaps need page-specific UX decisions."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would report {len(issues)} empty-state issue(s)",
            fix_type="report",
        )

    return FixResult(
        success=True,
        summary=f"{len(issues)} empty-state issue(s) require manual remediation",
        fix_type="report",
    )
