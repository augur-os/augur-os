# auto-tab-registry Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a pre-build scanner that validates every tab in the generated registry has a resolvable page (direct page.tsx or hub catch-all route), preventing build failures from orphan tabs.

**Architecture:** Python scanner using the ops_protocol scan-fix pattern. Parses `generated-registry.ts` as text to extract hub/tab data, validates against filesystem. Auto-fixes missing catch-all directories at d1+.

**Tech Stack:** Python 3.11+, ops_protocol, regex parsing, pathlib

---

### Task 1: Create skill directory and SKILL.md

**Files:**
- Create: `skills/auto-tab-registry/SKILL.md`
- Create: `skills/auto-tab-registry/evals/rank.json`
- Create: `skills/auto-tab-registry/references/.gitkeep`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p skills/auto-tab-registry/{scripts,augur/tests,evals,references}
```

- [ ] **Step 2: Write SKILL.md**

Create `skills/auto-tab-registry/SKILL.md`:

```markdown
---
name: auto-tab-registry
x-augur-type: autoloop
x-augur-tags: []
description: 'Validate tab registry entries resolve to page files or catch-all routes
  for adaptive engine and self-healing automation. Covers: auto-tab-registry, scan'
x-augur-visibility: auto
x-augur-loop:
  name: hardening
  tier: 0
  trigger: nightly
x-augur-hub: adaptive
x-augur-tab: infrastructure
---

# /auto-tab-registry

Pre-build scanner that validates every tab in the generated dashboard registry has a resolvable page — either a dedicated `page.tsx` or a hub-level `[[...slug]]/` catch-all route.

## What it checks

1. Every hub in the registry has a `[[...slug]]/page.tsx` catch-all
2. Every tab href resolves to either a direct page or a catch-all entry
3. (d2) Every import in `registry.ts` PAGES map resolves to an actual file

## Difficulty levels

| Level | Scan | Fix |
|-------|------|-----|
| d0 | Check hubs have catch-all routes | Report only |
| d1 | + validate each tab href resolves | Auto-create missing catch-all dirs |
| d2 | + cross-check registry.ts imports | + flag dead imports |

## Usage

```bash
/auto-tab-registry
```

## Examples

- `/auto-tab-registry` — Default scan
```

- [ ] **Step 3: Write evals/rank.json**

Create `skills/auto-tab-registry/evals/rank.json`:

```json
{
  "tier": "C",
  "score": 40,
  "rubric": "autoloop",
  "structural": {
    "score": 40,
    "dimensions": {
      "instruction": {
        "score": 70,
        "signals": {
          "desc_words": 20,
          "body_lines": 30,
          "sections": 5,
          "has_examples": true,
          "has_references": true,
          "has_workflow": false,
          "has_checklist": false
        },
        "weight": 0.2,
        "weighted": 14.0
      },
      "product": {
        "score": 20,
        "signals": {
          "has_data_dir": false,
          "has_mcp_tools": false,
          "has_api_routes": false,
          "has_actions": false,
          "has_scripts": true,
          "has_references": true
        },
        "weight": 0.3,
        "weighted": 6.0
      },
      "ui": {
        "score": 0,
        "signals": {
          "page_count": 0,
          "mature_pages": 0,
          "custom_pages": 0,
          "page_states": []
        },
        "weight": 0.05,
        "weighted": 0.0
      },
      "wiring": {
        "score": 45,
        "signals": {
          "has_api_route": false,
          "no_fs_bypasses": true,
          "has_mcp_tool": false,
          "no_fallback_masking": true
        },
        "weight": 0.45,
        "weighted": 20.2
      }
    }
  },
  "behavioral": null,
  "computed_at": "2026-03-28T00:00:00.000000+00:00"
}
```

- [ ] **Step 4: Create gitkeep**

```bash
touch skills/auto-tab-registry/references/.gitkeep
```

- [ ] **Step 5: Commit**

```bash
git add skills/auto-tab-registry/SKILL.md skills/auto-tab-registry/evals/rank.json skills/auto-tab-registry/references/.gitkeep
git commit -m "feat(auto-tab-registry): scaffold skill directory and SKILL.md"
```

---

### Task 2: Write the scanner script with tests (TDD)

**Files:**
- Create: `skills/auto-tab-registry/augur/tests/test_tab_registry.py`
- Create: `skills/auto-tab-registry/scripts/tab_registry.py`

- [ ] **Step 1: Write the failing test**

Create `skills/auto-tab-registry/augur/tests/test_tab_registry.py`:

```python
"""Tests for auto-tab-registry scanner."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project structure with generated-registry.ts."""
    app_dir = tmp_path / "apps" / "dashboard" / "app"

    # Create two hubs: one with catch-all, one without
    brain_catchall = app_dir / "brain" / "[[...slug]]"
    brain_catchall.mkdir(parents=True)
    (brain_catchall / "page.tsx").write_text("'use client'; export default function() {}")
    (brain_catchall / "registry.ts").write_text(
        "export const DEFAULT_PATH: string | null = null;\n"
        "export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {\n"
        "  'knowledge/memory': () => import('@skill/pages/brain/knowledge/memory/page'),\n"
        "};\n"
    )

    # templates hub: NO catch-all (should be flagged)
    templates_dir = app_dir / "templates"
    templates_dir.mkdir(parents=True)

    # Create generated-registry.ts
    lib_dir = tmp_path / "apps" / "dashboard" / "lib" / "tabs"
    lib_dir.mkdir(parents=True)
    (lib_dir / "generated-registry.ts").write_text(
        'export const pluginTabRegistry: TabRegistry = {\n'
        '  "brain": {\n'
        '    "title": "Brain",\n'
        '    "basePath": "/brain",\n'
        '    "tabs": [\n'
        '      { "id": "overview", "label": "Overview", "href": "/brain" },\n'
        '      { "id": "knowledge-memory", "label": "Memory", "href": "/brain/knowledge/memory" }\n'
        '    ],\n'
        '    "source": "plugin"\n'
        '  },\n'
        '  "templates": {\n'
        '    "title": "Templates",\n'
        '    "basePath": "/templates",\n'
        '    "tabs": [\n'
        '      { "id": "overview", "label": "Overview", "href": "/templates" },\n'
        '      { "id": "consulting-template", "label": "Consulting", "href": "/templates/consulting-template" }\n'
        '    ],\n'
        '    "source": "plugin"\n'
        '  }\n'
        '};\n'
    )

    return tmp_path


def test_scan_detects_missing_catchall(tmp_project: Path) -> None:
    """Hub without [[...slug]] directory should produce missing-catchall issue."""
    from skills.auto_tab_registry.scripts.tab_registry import scan
    from src.lib.ops_protocol import OpsContext

    ctx = OpsContext(project_root=tmp_project, difficulty=0)
    result = scan(ctx)

    missing = [i for i in result.issues if i.get("category") == "missing-catchall"]
    assert len(missing) == 1
    assert "templates" in missing[0]["detail"]


def test_scan_no_issues_when_all_hubs_have_catchall(tmp_project: Path) -> None:
    """All hubs with catch-all routes should produce no issues at d0."""
    from skills.auto_tab_registry.scripts.tab_registry import scan
    from src.lib.ops_protocol import OpsContext

    # Add catch-all to templates
    catchall = tmp_project / "apps" / "dashboard" / "app" / "templates" / "[[...slug]]"
    catchall.mkdir(parents=True)
    (catchall / "page.tsx").write_text("export default function() {}")
    (catchall / "registry.ts").write_text(
        "export const DEFAULT_PATH: string | null = null;\n"
        "export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {};\n"
    )

    ctx = OpsContext(project_root=tmp_project, difficulty=0)
    result = scan(ctx)

    missing = [i for i in result.issues if i.get("category") == "missing-catchall"]
    assert len(missing) == 0


def test_scan_d1_detects_orphan_tab(tmp_project: Path) -> None:
    """Tab whose href doesn't resolve to direct page or catch-all entry should be flagged at d1."""
    from skills.auto_tab_registry.scripts.tab_registry import scan
    from src.lib.ops_protocol import OpsContext

    # Add catch-all to templates but with empty PAGES
    catchall = tmp_project / "apps" / "dashboard" / "app" / "templates" / "[[...slug]]"
    catchall.mkdir(parents=True)
    (catchall / "page.tsx").write_text("export default function() {}")
    (catchall / "registry.ts").write_text(
        "export const DEFAULT_PATH: string | null = null;\n"
        "export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {};\n"
    )

    ctx = OpsContext(project_root=tmp_project, difficulty=1)
    result = scan(ctx)

    orphans = [i for i in result.issues if i.get("category") == "orphan-tab"]
    # consulting-template tab has no direct page and no catch-all PAGES entry
    assert len(orphans) >= 1
    assert any("consulting-template" in i["detail"] for i in orphans)


def test_fix_creates_missing_catchall(tmp_project: Path) -> None:
    """Fix at d1 should create missing catch-all directory with page.tsx and registry.ts."""
    from skills.auto_tab_registry.scripts.tab_registry import fix, scan
    from src.lib.ops_protocol import OpsContext

    ctx = OpsContext(project_root=tmp_project, difficulty=1)
    scan_result = scan(ctx)
    missing = [i for i in scan_result.issues if i.get("category") == "missing-catchall"]
    assert len(missing) == 1

    fix_result = fix(ctx, missing)
    assert fix_result.success

    # Verify the catch-all was created
    catchall = tmp_project / "apps" / "dashboard" / "app" / "templates" / "[[...slug]]"
    assert (catchall / "page.tsx").exists()
    assert (catchall / "registry.ts").exists()


def test_fix_d0_reports_only(tmp_project: Path) -> None:
    """Fix at d0 should not create any files — report only."""
    from skills.auto_tab_registry.scripts.tab_registry import fix, scan
    from src.lib.ops_protocol import OpsContext

    ctx = OpsContext(project_root=tmp_project, difficulty=0)
    scan_result = scan(ctx)
    missing = [i for i in scan_result.issues if i.get("category") == "missing-catchall"]
    assert len(missing) == 1

    fix_result = fix(ctx, missing)
    assert fix_result.fix_type == "report"

    # Catch-all should NOT have been created
    catchall = tmp_project / "apps" / "dashboard" / "app" / "templates" / "[[...slug]]"
    assert not catchall.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest skills/auto-tab-registry/augur/tests/test_tab_registry.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skills.auto_tab_registry'`

- [ ] **Step 3: Write the scanner implementation**

Create `skills/auto-tab-registry/scripts/tab_registry.py`:

```python
"""auto-tab-registry: Validate tab registry entries resolve to page files or catch-all routes.

Prevents build failures from orphan tabs by checking that every tab href
in generated-registry.ts has a corresponding page.tsx or catch-all route.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

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


def _find_template_catchall(app_dir: Path) -> Path | None:
    """Find an existing catch-all directory to use as template."""
    for hub_dir in sorted(app_dir.iterdir()):
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
                detail="generated-registry.ts not found — run npm run generate-tabs",
                path=str(REGISTRY_REL),
                kind="environment",
            )],
            summary="Registry file missing",
            severity="error",
            health="broken",
        )

    hubs = _parse_registry(registry_path)
    issues: list[dict] = []
    items_scanned = 0

    for hub_id, tabs in hubs.items():
        items_scanned += 1
        has_catchall = _hub_has_catchall(app_dir, hub_id)

        # d0: Check hub catch-all exists
        if not has_catchall:
            issues.append(make_issue(
                category="missing-catchall",
                detail=f"Hub '{hub_id}' has no [[...slug]]/page.tsx catch-all route",
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
                    # Hub root (e.g. /brain) — always resolves to the overview
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

                # Orphan tab
                if not has_catchall:
                    detail = f"Tab '{tab_id}' in hub '{hub_id}' has no page — hub also missing catch-all"
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

    # d2+: Cross-check registry.ts imports
    if ctx.difficulty >= 2:
        for hub_id in hubs:
            catchall_registry = app_dir / hub_id / "[[...slug]]" / "registry.ts"
            if not catchall_registry.exists():
                continue
            text = catchall_registry.read_text()
            for match in re.finditer(r"import\('\"['\"]\)", text):
                import_path = match.group(1)
                items_scanned += 1
                # @skill/ and @/ imports are resolved by Next.js — skip
                # We only flag obviously broken patterns
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
        # Report hubs where all tabs only resolve via catch-all (fragile)
        for hub_id, tabs in hubs.items():
            if not _hub_has_catchall(app_dir, hub_id):
                continue
            tab_count = sum(1 for t in tabs if len(t.get("href", "").strip("/").split("/")) > 1)
            direct_count = sum(
                1 for t in tabs
                if len(t.get("href", "").strip("/").split("/")) > 1
                and (app_dir / hub_id / "/".join(t["href"].strip("/").split("/")[1:]) / "page.tsx").exists()
            )
            if tab_count > 0 and direct_count == 0:
                issues.append(evolution_gap(
                    f"Hub '{hub_id}' has {tab_count} tabs all resolving via catch-all only — "
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
    """Fix tab registry issues — auto-create missing catch-all dirs at d1+."""
    if ctx.difficulty < 1:
        return report_only_fix(ctx, "tab-registry-latest.json", issues, noun="tab registry issue")

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
            # Copy page.tsx from template
            shutil.copy2(template_dir / "page.tsx", target / "page.tsx")
        else:
            # Seed minimal page.tsx
            (target / "page.tsx").write_text(
                "'use client';\n"
                "export default function HubPage() { return null; }\n"
            )

        # Seed empty registry.ts
        (target / "registry.ts").write_text(
            "// AUTO-GENERATED by mount-plugins \u2014 do not edit\n"
            "export const DEFAULT_PATH: string | null = null;\n"
            "\n"
            "export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {\n"
            "};\n"
        )

        actions.append({"action": "created-catchall", "hub": hub_id, "path": str(target)})
        changes.append(str(target / "page.tsx"))
        changes.append(str(target / "registry.ts"))

    # Non-fixable issues get reported
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && python -m pytest skills/auto-tab-registry/augur/tests/test_tab_registry.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-tab-registry/scripts/tab_registry.py skills/auto-tab-registry/augur/tests/test_tab_registry.py
git commit -m "feat(auto-tab-registry): implement scan/fix with TDD"
```

---

### Task 3: Register scanner in daemon

**Files:**
- Modify: `skills/daemon/SKILL.md:37-38` (insert after auto-page-mounts entry)

- [ ] **Step 1: Add registration entry**

Insert after the `auto-page-mounts` entry (line 37) in `skills/daemon/SKILL.md`:

```yaml
- id: auto-tab-registry
  type: workflow
  visibility: auto
  description: Validate tab registry entries resolve to page files or catch-all routes
  callable: scripts/tab_registry.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 0
    trigger: nightly
```

- [ ] **Step 2: Verify registration parses**

```bash
cd ~/Projects/Augur && python -c "
from src.lib.frontmatter_utils import parse_frontmatter
from pathlib import Path
fm, _ = parse_frontmatter(Path('skills/daemon/SKILL.md'))
cmds = fm.get('x-augur-commands', [])
entry = next((c for c in cmds if c['id'] == 'auto-tab-registry'), None)
assert entry is not None, 'auto-tab-registry not found in daemon commands'
assert entry['loop']['name'] == 'hardening'
print(f'OK: {entry}')
"
```

Expected: `OK: {'id': 'auto-tab-registry', ...}`

- [ ] **Step 3: Commit**

```bash
git add skills/daemon/SKILL.md
git commit -m "feat(auto-tab-registry): register scanner in daemon hardening loop"
```

---

### Task 4: Run scanner against live codebase

**Files:** None (validation only)

- [ ] **Step 1: Run scan at d0**

```bash
cd ~/Projects/Augur && python -c "
from skills.auto_tab_registry.scripts.tab_registry import scan
from src.lib.ops_protocol import OpsContext
from pathlib import Path

ctx = OpsContext(project_root=Path('.').resolve(), difficulty=0)
result = scan(ctx)
print(f'Severity: {result.severity}')
print(f'Health: {result.health}')
print(f'Items scanned: {result.items_scanned}')
print(f'Issues: {len(result.issues)}')
for issue in result.issues:
    print(f'  [{issue.get(\"category\")}] {issue.get(\"detail\")}')
"
```

Expected: 0 issues (we already fixed the templates hub catch-all earlier in this session)

- [ ] **Step 2: Run scan at d1**

```bash
cd ~/Projects/Augur && python -c "
from skills.auto_tab_registry.scripts.tab_registry import scan
from src.lib.ops_protocol import OpsContext
from pathlib import Path

ctx = OpsContext(project_root=Path('.').resolve(), difficulty=1)
result = scan(ctx)
print(f'Severity: {result.severity}')
print(f'Items scanned: {result.items_scanned}')
print(f'Issues: {len(result.issues)}')
for issue in result.issues:
    print(f'  [{issue.get(\"category\")}] {issue.get(\"detail\")}')
"
```

Expected: May find orphan tabs (tabs with catch-all but no PAGES entry). These are legitimate findings.

- [ ] **Step 3: Run full test suite**

```bash
cd ~/Projects/Augur && python -m pytest skills/auto-tab-registry/augur/tests/test_tab_registry.py -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit any adjustments**

If live run revealed parsing issues, fix and commit:

```bash
git add -A skills/auto-tab-registry/
git commit -m "fix(auto-tab-registry): adjustments from live codebase validation"
```
