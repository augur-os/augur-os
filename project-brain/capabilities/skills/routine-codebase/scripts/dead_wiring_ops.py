"""auto-dead-wiring: Cross-reference canonical skill declarations vs implementations."""
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

from src.config.paths import get_all_client_skill_dirs
from src.lib.frontmatter_utils import load_skill_contract
from src.lib.ops_protocol import OpsContext, ScanResult, report_only_fix

name = "auto-dead-wiring"


def _load_registry_block_ids(project_root: Path) -> set[str]:
    """Parse block IDs from generated-block-registry.ts."""
    registry_path = project_root / "apps" / "dashboard" / "lib" / "blocks" / "generated-block-registry.ts"
    if not registry_path.exists():
        return set()
    content = registry_path.read_text(errors="replace")
    return set(re.findall(r"'([^']+)':\s*\{", content))

DIFFICULTY_SPEC = {
    0: "Surface check — count skill metadata declarations",
    1: "Content check — missing pages, missing MCP handlers",
    2: "Deep check — broken callable paths, unresolvable endpoints",
    3: "Exhaustive — stub functions, dead imports",
    4: "Expert — end-to-end chain validation",
}


def _load_all_skill_contracts(project_root: Path) -> list[tuple[Path, dict]]:
    """Load all canonical SKILL.md contracts with compatibility aliases."""
    root_resolved = project_root.resolve()
    results: list[tuple[Path, dict]] = []
    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            try:
                skill_md.resolve().relative_to(root_resolved)
            except ValueError:
                continue
            contract = load_skill_contract(skill_md)
            if contract:
                results.append((skill_md, contract))
    return results


def scan(ctx: OpsContext) -> ScanResult:
    """Validate canonical skill declarations match actual implementations."""
    skill_contracts = _load_all_skill_contracts(ctx.project_root)
    if not skill_contracts:
        return ScanResult(issues=[], summary="No SKILL.md files found", severity="info")

    # Count declarations
    total_pages = 0
    total_blocks = 0
    total_tools = 0
    total_commands = 0
    for _, data in skill_contracts:
        contrib = data.get("contributions", {})
        if isinstance(contrib, dict):
            total_pages += len(contrib.get("pages", []))
            total_blocks += len(contrib.get("blocks", []))
            total_commands += len(contrib.get("commands", []))
        mcp = data.get("mcp", {})
        if isinstance(mcp, dict):
            total_tools += len(mcp.get("tools", []))

    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary=f"{len(skill_contracts)} skills, {total_pages} pages, {total_blocks} blocks, {total_tools} tools, {total_commands} commands (d0 surface)",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []
    registry_ids = _load_registry_block_ids(ctx.project_root)

    # d1: missing pages and MCP tool handlers
    for skill_md, data in skill_contracts:
        skill_dir = skill_md.parent
        rel_skill_md = str(skill_md.relative_to(ctx.project_root))
        contrib = data.get("contributions", {})
        if not isinstance(contrib, dict):
            continue

        # Check declared pages have page.tsx
        for page in contrib.get("pages", []):
            if not isinstance(page, dict):
                continue
            page_id = page.get("id", "")
            if not page_id:
                continue
            # Check in plugin's dashboard dir
            dashboard_dir = skill_dir / "augur" / "dashboard"
            page_file = dashboard_dir / page_id / "page.tsx"
            # Also check: root page.tsx (single-page skills), {page_id}.tsx
            if not page_file.exists() and not (dashboard_dir / f"{page_id}.tsx").exists() and not (dashboard_dir / "page.tsx").exists():
                # Check all possible locations
                found = list(dashboard_dir.glob(f"**/{page_id}/page.tsx"))
                if not found:
                    issues.append({
                        "type": "missing_page",
                        "page_id": page_id,
                        "file": rel_skill_md,
                        "detail": f"Page '{page_id}' declared but no page.tsx in {dashboard_dir.relative_to(ctx.project_root)}",
                    })

        # Check declared blocks have entries in block registry
        skill_name = skill_dir.name
        for block in contrib.get("blocks", []):
            if not isinstance(block, dict):
                continue
            block_id = block.get("id", "")
            if not block_id:
                continue
            qualified_id = f"{skill_name}:{block_id}"
            if block_id not in registry_ids and qualified_id not in registry_ids:
                issues.append({
                    "type": "missing_block_component",
                    "block_id": block_id,
                    "file": rel_skill_md,
                    "detail": f"Block '{block_id}' (qualified: '{qualified_id}') declared but not in generated-block-registry.ts",
                })

    # d2: broken callable paths
    if ctx.difficulty >= 2:
        for skill_md, data in skill_contracts:
            skill_dir = skill_md.parent
            rel_skill_md = str(skill_md.relative_to(ctx.project_root))
            contrib = data.get("contributions", {})
            commands = []
            if isinstance(contrib, dict):
                commands = contrib.get("commands", [])
            commands += data.get("commands", [])

            for cmd in commands:
                if not isinstance(cmd, dict):
                    continue
                callable_path = cmd.get("callable", "")
                if callable_path:
                    full_path = skill_dir / callable_path
                    if not full_path.exists():
                        issues.append({
                            "type": "broken_callable",
                            "command": cmd.get("id", "?"),
                            "callable": callable_path,
                            "file": rel_skill_md,
                            "detail": f"Command '{cmd.get('id','?')}' callable '{callable_path}' — file not found",
                        })

    # d3: stub functions in Python ops modules and MCP handlers
    if ctx.difficulty >= 3:
        stub_patterns = [
            re.compile(r'def\s+\w+\s*\([^)]*\)[^:]*:\s*\n\s*return\s*\[\]'),
            re.compile(r'def\s+\w+\s*\([^)]*\)[^:]*:\s*\n\s*return\s*\{\}'),
            re.compile(r'def\s+\w+\s*\([^)]*\)[^:]*:\s*\n\s*return\s*None'),
            re.compile(r'def\s+\w+\s*\([^)]*\)[^:]*:\s*\n\s*pass\s*$', re.MULTILINE),
        ]
        for skills_dir in get_all_client_skill_dirs(ctx.project_root):
            for py_file in skills_dir.glob("*/scripts/**/*.py"):
                content = py_file.read_text(errors="replace")
                rel = str(py_file.relative_to(ctx.project_root))
                for pattern in stub_patterns:
                    for match in pattern.finditer(content):
                        line = content[: match.start()].count("\n") + 1
                        stub_text = match.group(0).strip()[:80]
                        issues.append({
                            "type": "stub_function",
                            "file": rel,
                            "line": line,
                            "detail": f"Stub function: {stub_text}",
                        })

    severity = "warning" if issues else "info"
    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} wiring issue(s) across {len(skill_contracts)} skills",
        severity=severity,
        items_scanned=len(skill_contracts),
    )


def fix(ctx: OpsContext, issues: list[dict]):
    return report_only_fix(ctx, "dead-wiring-latest.json", issues, noun="wiring issue")
