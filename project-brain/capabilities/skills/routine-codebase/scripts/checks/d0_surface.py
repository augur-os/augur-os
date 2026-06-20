"""d0: Surface checks — verify files exist and block registry is populated."""
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

from src.lib.ops_protocol import make_issue

WEBMCP_DIR = Path("apps/dashboard/lib/webmcp")
TOOLS_DIR = WEBMCP_DIR / "tools"
BLOCK_TYPES_DIR = Path("apps/dashboard/components/blocks/types")


def check_d0_surface(project_root: Path) -> list[dict]:
    """Verify source files and block registry exist and are populated."""
    issues: list[dict] = []

    # Check core WebMCP files
    required = [
        WEBMCP_DIR / "types.ts",
        WEBMCP_DIR / "polyfill.ts",
        WEBMCP_DIR / "state-registry.ts",
        WEBMCP_DIR / "WebMCPProvider.tsx",
        WEBMCP_DIR / "useWebMCPReport.ts",
        TOOLS_DIR / "errors.ts",
        TOOLS_DIR / "blocks.ts",
        TOOLS_DIR / "pages.ts",
        TOOLS_DIR / "views.ts",
        TOOLS_DIR / "navigation.ts",
        # actions.ts retired by ADR-806 (FILE-actions pipeline removal)
        TOOLS_DIR / "catalog.ts",
        TOOLS_DIR / "forms.ts",
        TOOLS_DIR / "agents.ts",
    ]
    for f in required:
        if not (project_root / f).exists():
            issues.append(make_issue(
                category="webmcp-files",
                detail=f"Missing: {f}",
                path=str(f),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))

    # Check generated block registry has entries
    registry_file = project_root / "apps/dashboard/lib/blocks/generated-block-registry.ts"
    if registry_file.exists():
        content = registry_file.read_text()
        entry_count = content.count("':")  # each entry starts with 'id':
        if entry_count < 10:
            issues.append(make_issue(
                category="webmcp-registry",
                detail=f"Block registry has only {entry_count} entries (expected 100+)",
                path=str(registry_file),
                kind="actionable",
                root_cause_type="generated_artifact",
                fixability="auto",
            ))
    else:
        issues.append(make_issue(
            category="webmcp-registry",
            detail="Block registry not generated",
            path=str(registry_file),
            kind="actionable",
            root_cause_type="generated_artifact",
            fixability="auto",
        ))

    # Check all 14 block type components exist
    expected_types = [
        "StatCardBlock", "StatGridBlock", "DataListBlock", "DataTableBlock",
        "ActionBarBlock", "CardGridBlock", "ChartBlock", "MarkdownBlock",
        "CalendarBlock", "ActivityFeedBlock", "NotesBlock", "EmbedBlock",
        "OpsBoardBlock", "ProgressBlock",
    ]
    for bt in expected_types:
        if not (project_root / BLOCK_TYPES_DIR / f"{bt}.tsx").exists():
            issues.append(make_issue(
                category="webmcp-blocks",
                detail=f"Block component missing: {bt}.tsx",
                path=str(BLOCK_TYPES_DIR / f"{bt}.tsx"),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))

    return issues
