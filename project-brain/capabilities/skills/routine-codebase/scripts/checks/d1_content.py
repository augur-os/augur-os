"""d1: Content validation — block data sources, page mounts, expandTo targets, component wiring."""
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

import yaml

from src.lib.ops_protocol import make_issue

BLOCK_TYPES_DIR = Path("apps/dashboard/components/blocks/types")
APP_DIR = Path("apps/dashboard/app")


def check_d1_content(project_root: Path) -> list[dict]:
    """Validate block data sources, page mounts, expandTo targets, component wiring."""
    issues: list[dict] = []

    # Scan all SKILL.md for blocks with broken expandTo
    for yf in (project_root / "project-brain" / "capabilities" / "skills").glob("*/SKILL.md"):
        try:
            text = yf.read_text()
            if not text.startswith("---"):
                continue
            _, fm, _ = text.split("---", 2)
            data = yaml.safe_load(fm)
        except Exception:
            continue
        if not data:
            continue
        config = data.get("x-augur-config", {}) or {}
        if "contributions" not in config:
            continue

        contrib = config.get("contributions", {})
        skill_name = data.get("name", yf.parent.name)
        # Resolve hub: prefer x-augur-hub (standard), fall back to contributions.contributes_to
        hub = data.get("x-augur-hub") or contrib.get("contributes_to") or data.get("contributes_to", "")

        # Check blocks
        for block in contrib.get("blocks", []):
            bid = f"{skill_name}:{block.get('id', '?')}"

            # expandTo must have a real page
            # The block registry normalizes short paths: /hub/page -> /hub/skill/page
            expand = block.get("expandTo", "")
            if expand:
                expand_segments = expand.strip("/").split("/")
                expand_hub = expand_segments[0] if expand_segments else ""

                # Check if the hub uses a [[...slug]] catch-all route (handles all sub-paths)
                hub_catchall = (project_root / APP_DIR / expand_hub / "[[...slug]]").is_dir()

                if not hub_catchall:
                    # Try raw path first, then normalized /{hub}/{skill}/{page}
                    candidates = [
                        project_root / APP_DIR / expand.lstrip("/") / "page.tsx",
                    ]
                    # If expandTo is /{hub}/{page} (2 segments), try /{hub}/{skill}/{page}
                    if len(expand_segments) == 2 and expand_segments[0] == hub:
                        normalized = f"{hub}/{skill_name}/{expand_segments[1]}"
                        candidates.append(project_root / APP_DIR / normalized / "page.tsx")

                    if not any(c.exists() for c in candidates):
                        issues.append(make_issue(
                            category="webmcp-blocks",
                            detail=f"Block {bid} expandTo '{expand}' — page.tsx missing",
                            path=str(candidates[0]),
                            kind="actionable",
                            root_cause_type="repo_bug",
                            fixability="manual",
                        ))

            # data_source.mcp_tool should be a non-empty string
            ds = block.get("data_source", {})
            mcp_tool = ds.get("mcp_tool", "") if ds else ""
            if not mcp_tool:
                issues.append(make_issue(
                    category="webmcp-blocks",
                    detail=f"Block {bid} has no data_source.mcp_tool",
                    path=str(yf),
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                ))

        # Check pages — auto pages must have a page.tsx (generated or custom)
        # Skip if the hub uses a [[...slug]] catch-all route (handles all sub-paths)
        hub_catchall = (project_root / APP_DIR / hub / "[[...slug]]").is_dir()
        if not hub_catchall:
            for page in contrib.get("pages", []):
                pid = page.get("id", "?")
                page_type = page.get("page_type", "custom")

                # Build expected path — check both /{hub}/{skill}/page.tsx and /{hub}/{skill}/{pid}/page.tsx
                candidates = [
                    project_root / APP_DIR / hub / skill_name / "page.tsx",
                    project_root / APP_DIR / hub / skill_name / pid / "page.tsx",
                ]

                if not any(c.exists() for c in candidates):
                    issues.append(make_issue(
                        category="webmcp-pages",
                        detail=f"Page {skill_name}:{pid} ({page_type}) — page.tsx missing (checked {', '.join(str(c.relative_to(project_root)) for c in candidates)})",
                        path=str(candidates[0]),
                        kind="actionable",
                        root_cause_type="repo_bug",
                        fixability="auto" if page_type == "auto" else "manual",
                    ))

    # Check block components accept data/loading/error props (Phase 1 refactor)
    for bt_file in sorted((project_root / BLOCK_TYPES_DIR).glob("*.tsx")):
        content = bt_file.read_text()
        # Check for the props fallback pattern
        if "useBlockData" in content and "props.data" not in content and "propsData" not in content:
            # Old pattern — block fetches its own data, not receiving from BlockRenderer
            if "selfFetched" not in content and ".data ??" not in content:
                issues.append(make_issue(
                    category="webmcp-blocks",
                    detail=f"{bt_file.name} not accepting data props from BlockRenderer",
                    path=str(bt_file.relative_to(project_root)),
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                ))

    # Check BlockRenderer imports WebMCP hooks
    renderer = project_root / "apps/dashboard/components/blocks/BlockRenderer.tsx"
    if renderer.exists():
        content = renderer.read_text()
        if "useWebMCPReport" not in content:
            issues.append(make_issue(
                category="webmcp-wiring",
                detail="BlockRenderer missing useWebMCPReport import",
                path=str(renderer.relative_to(project_root)),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))
        if "useWebMCPSubscribe" not in content:
            issues.append(make_issue(
                category="webmcp-wiring",
                detail="BlockRenderer missing useWebMCPSubscribe import",
                path=str(renderer.relative_to(project_root)),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))

    # Check layout.tsx has WebMCPProvider
    layout = project_root / "apps/dashboard/app/layout.tsx"
    if layout.exists():
        content = layout.read_text()
        if "WebMCPProvider" not in content:
            issues.append(make_issue(
                category="webmcp-wiring",
                detail="Root layout missing WebMCPProvider",
                path=str(layout.relative_to(project_root)),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))

    # Check SkillAutoPage has WebMCP reporting
    autopage = project_root / "apps/dashboard/components/plugin/SkillAutoPage.tsx"
    if autopage.exists():
        content = autopage.read_text()
        if "useWebMCPPageReport" not in content:
            issues.append(make_issue(
                category="webmcp-wiring",
                detail="SkillAutoPage missing useWebMCPPageReport",
                path=str(autopage.relative_to(project_root)),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))

    # Check ViewCanvas has WebMCP reporting
    viewcanvas = project_root / "apps/dashboard/components/blocks/ViewCanvas.tsx"
    if viewcanvas.exists():
        content = viewcanvas.read_text()
        if "useWebMCPViewReport" not in content:
            issues.append(make_issue(
                category="webmcp-wiring",
                detail="ViewCanvas missing useWebMCPViewReport",
                path=str(viewcanvas.relative_to(project_root)),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))

    # Check action YAML files have valid dispatch types
    valid_dispatches = {"fire", "oneshot", "chat", "ide", "modal"}
    for action_file in project_root.glob("project-brain/capabilities/skills/*/augur/actions/*.yaml"):
        try:
            action_data = yaml.safe_load(action_file.read_text())
        except Exception:
            continue
        if not action_data:
            continue
        dispatch = action_data.get("dispatch", "")
        if dispatch and dispatch not in valid_dispatches:
            issues.append(make_issue(
                category="webmcp-actions",
                detail=f"Action {action_file.name} has invalid dispatch: '{dispatch}'",
                path=str(action_file.relative_to(project_root)),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))

    return issues
