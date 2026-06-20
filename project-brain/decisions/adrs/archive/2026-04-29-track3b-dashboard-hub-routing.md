# Track 3b — Dashboard Hub-Routing Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Worktree required:** Before starting, use `superpowers:using-git-worktrees` to create a worktree off `main` with branch name `track3b-dashboard-hub-routing`.

**Goal:** Replace the dashboard's hardcoded `lifestyle`/`apple` literals and the legacy `{vertical/horizontal/factory}` taxonomy with a metadata-driven hub model rooted in `config/system/hubs.yaml` and consumed via a generated typed `HUBS` map at `apps/dashboard/lib/hubs/generated.ts`.

**Architecture:** Five sequential PRs — infrastructure (PR 1) is purely additive; production-code consumers (PR 2), scanner templates (PR 3), and workflow tools (PR 4) migrate one surface boundary at a time; cleanup + ADR (PR 5) deletes the legacy taxonomy and proves zero hardcodes remain. Each PR has its own verification gate (browser load, scaffold smoke, workflow execution, audit grep).

**Tech Stack:** Python 3.11+, Next.js (TypeScript), pnpm, pyyaml, pytest. No new dependencies.

**Related specs:**
- Layer 1: `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- Layer 4 migration: `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- Track 3b design: `docs/superpowers/specs/2026-04-29-track3b-dashboard-hub-routing-design.md`
- Sibling plans: `2026-04-29-track2-vault-server-split.md`, `2026-04-29-track1-rag-index-extraction.md`

## File Structure

### New files (created in PR 1)

| File | Purpose |
|---|---|
| `config/system/hubs.yaml` | Source-of-truth for hub-level metadata. Hand-edited. Six hubs: life, brain, career, command, studio, adaptive. |
| `apps/dashboard/lib/hubs/generated.ts` | Auto-generated typed `HUBS` map + `Hub` interface. Imported by all dashboard consumers in PRs 2-4. |
| `apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py` | Python loader/validator for `config/system/hubs.yaml`. Reused by `dashboard_generator.py` and the orphan-validator test. |
| `apps/dashboard/scripts/skill-scripts/skill_generation/hubs_emitter.py` | Emits `apps/dashboard/lib/hubs/generated.ts` from a parsed manifest. |
| `tests/cli/test_hub_metadata.py` | Schema validation + orphan-free check (`x-augur-hub` references must exist in `hubs.yaml`). |
| `apps/dashboard/lib/hubs/generated.test.ts` | Smoke test: `HUBS` keys match expected ids; `NAV_VISIBLE_HUBS` is sorted by `order`; `HUBS_BY_CATEGORY` groups correctly. |

### Files modified (across PRs)

| File | PR | Change |
|---|---|---|
| `apps/dashboard/scripts/skill-scripts/skill_generation/dashboard_generator.py` | 1 | Read `config/system/hubs.yaml` via `hubs_loader`; emit `apps/dashboard/lib/hubs/generated.ts` via `hubs_emitter`. PR 5 deletes the legacy `{vertical/horizontal/factory}` mapping. |
| `apps/dashboard/scripts/skill-scripts/skill_generation/comprehensive_dashboard_generator.py` | 1, 5 | Stop hardcoding `'lifestyle'` (PR 1) → consume `HUBS` map. Delete legacy taxonomy mapping (PR 5). |
| `apps/dashboard/app/actions.ts` | 2 | Replace `"lifestyle"` literal with `HUBS["life"].id` (or category-based fallback). |
| `apps/dashboard/lib/api/record-helpers.ts` | 2 | Replace `"lifestyle"` literal with `HUBS["life"].id`. |
| `apps/dashboard/lib/help.ts` | 2 | Replace hardcoded hub list with `Object.keys(HUBS)`. |
| `apps/dashboard/lib/paths.ts` | 2 | Replace hub URL prefix literals with `HUBS[id]` lookups. |
| `apps/dashboard/lib/server/voice-memos.ts` | 2 | Replace `"lifestyle"` fallback with category-based lookup or explicit error. |
| `apps/dashboard/lib/browse/types.ts` | 2 | Hub-id type changes from string-literal union to `keyof typeof HUBS`. |
| `apps/dashboard/features/components/CalendarWidget.tsx` | 2 | Replace `"lifestyle"` link target with `HUBS["life"].id`. |
| `apps/dashboard/features/extensions-bundles/plugins/plugin-dialogs.tsx` | 2 | Replace hardcoded hub options with `NAV_VISIBLE_HUBS`. |
| `apps/dashboard/scripts/skill-scripts/blueprint_generator.py` | 3 | Stop emitting hardcoded `x-augur-hub: lifestyle`; require explicit hub or pick from `hubs.yaml`. |
| `apps/dashboard/scripts/skill-scripts/skill_generation/placement_analyzer.py` | 3 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/skill_generation/route_templates.py` | 3 | Replace `'lifestyle'` route prefix with hub-parametrized route. |
| `apps/dashboard/scripts/skill-scripts/skill_generation/productization_plan_generator.py` | 3 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/_hardening_implementation.py` | 3 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/import_stages/blueprint.py` | 3 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/skill_importer.py` | 3 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/skill_import.py` | 3 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/import_codegen.py` | 3 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/generate_skill_ui.py` | 3 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/mcp/tools_plugin.py` | 4 | Case-by-case: migrate templating; preserve intentional domain logic with explanatory comments. |
| `apps/dashboard/scripts/skill-scripts/mcp/tools_workflow.py` | 4 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/workflow/engine.py` | 4 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/workflow/state_manager.py` | 4 | Same pattern. |
| `apps/dashboard/scripts/skill-scripts/scoring/user_research.py` | 4 | Same pattern. |

### Files deleted (in PR 5)

- The legacy `{vertical: lifestyle, horizontal: hands, factory: agents}` mapping block in `dashboard_generator.py` and `comprehensive_dashboard_generator.py` (deleted in place; no whole-file deletions).

### What stays

- `config/system/{paths.yaml, mcp_servers.yaml, ...}` other system config files — untouched.
- `apps/dashboard/lib/plugin-runtime/assembled-hubs.json` — regenerated by PR 1's pipeline; format unchanged.
- `apps/dashboard/lib/tabs/generated-registry.ts` — regenerated by PR 1's pipeline; consumes `HUBS` indirectly via the scanner.

## PR Sequencing

| PR | Title | Net effect | Commits |
|---|---|---|---|
| 1 | Infrastructure: hubs.yaml + scanner + generated.ts (additive) | `generated.ts` exists, no consumers yet; dashboard renders unchanged | 1 |
| 2 | Dashboard production code (8 files) | Production consumers migrate to `HUBS[id]`; browser verification required | 1 |
| 3 | Scanner templates (~10 files) | Skill-import pipeline emits hub-neutral code | 1 |
| 4 | Workflow tools (~5 files) | Workflow code migrates; intentional domain logic preserved with comments | 1 |
| 5 | Cleanup + ADR | Legacy taxonomy deleted; audit grep clean; ADR written; final browser verify | 1 |

Total: **5 commits**.

## Critical execution rules (read before every task)

- **Never** use `--no-verify` on `git commit`. Pre-commit failures get a NEW commit with the fix (per CLAUDE.md commit-safety rules).
- **Worktree pollution**: every commit step verifies `git status --short` shows only expected paths. If anything else, restore with `git checkout HEAD --` before committing.
- **Dashboard ops slash commands** (per CLAUDE.md rule #29) are the canonical dashboard-rebuild + diagnostic surface. Use `/dev-build` for any rebuild step in this plan and `/dev-debug` for any diagnostic check. The project's pre-commit hook rejects manual dev-server invocations (the patterns enumerated in `scripts/hooks/dashboard-shortcut-patterns.sh`); those bypass `/dev-build`'s port-owner detection, codex thread state, vault sync, and post-build verify. Read `docs/agent-topics/agent-rules.md` for the canonical list of forbidden patterns.
- **Browser verification** is required for PRs 1, 2, 5 (per CLAUDE.md rule #28). The pattern is: run `/dev-build` from the user's main checkout (or in the worktree if `/dev-build` supports it on this machine), then verify the affected pages load to interactive state in a real browser or via Chrome MCP. HTTP 200 from `curl` is NOT sufficient. If `/dev-build` is unavailable in the worktree's session, complete the verification from the user's main session and report client-load status, not just SSR.
- **Test runs use `pytest` (Python) and the project's standard JS test runner via the workspace.** When a JS test step appears, prefer the project's existing test invocation — if a direct invocation is blocked by the pre-commit hook, route the test through `/dev-build`'s post-build verify or run pytest-driven equivalents. Never bypass the hook with `--no-verify`.
- **Hub ownership rule** (CLAUDE.md rule #13): a skill's `x-augur-hub` is the per-skill hub assignment. Do NOT add skill-specific hub data to `config/system/hubs.yaml`; that file describes hubs themselves.

---

## Task 1: PR 1 — Infrastructure (additive)

**Files (Create):**
- `config/system/hubs.yaml`
- `apps/dashboard/lib/hubs/generated.ts` (will be emitted; checked into git so consumers in PR 2 can import without an intermediate build)
- `apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py`
- `apps/dashboard/scripts/skill-scripts/skill_generation/hubs_emitter.py`
- `tests/cli/test_hub_metadata.py`
- `apps/dashboard/lib/hubs/generated.test.ts`

**Files (Modify):**
- `apps/dashboard/scripts/skill-scripts/skill_generation/dashboard_generator.py` — add `hubs_loader` + `hubs_emitter` invocation. Legacy taxonomy stays for now (deleted in PR 5).

This PR is **additive only**. No production-code consumers updated yet. Dashboard renders unchanged after.

### Step 1.1: Verify worktree branch + clean status

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git branch --show-current && \
  git status --short
```

Expected: `track3b-dashboard-hub-routing`, clean. STOP if not.

### Step 1.2: Create `config/system/hubs.yaml`

Save:

```yaml
# Augur dashboard hub registry.
# Source-of-truth for hub-level metadata. Hand-edited.
#
# Read by:
#   - apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py
#       (which feeds dashboard_generator.py + the orphan-validator test)
#
# Per-skill hub assignment lives in each skill's SKILL.md frontmatter
# (`x-augur-hub: <id>`). This file describes hubs themselves, not skills.
#
# Track 3b spec: docs/superpowers/specs/2026-04-29-track3b-dashboard-hub-routing-design.md

hubs:
  - id: life
    label: Life
    subtitle: Personal operating system surfaces
    icon: Home
    category: personal
    layout: masonry
    order: 1

  - id: brain
    label: Brain
    subtitle: Knowledge, memory, and learning
    icon: Brain
    category: knowledge
    layout: masonry
    order: 2

  - id: career
    label: Career
    subtitle: Professional growth and outreach
    icon: Briefcase
    category: work
    layout: masonry
    order: 3

  - id: command
    label: Command
    subtitle: Operational tooling and platform admin
    icon: Terminal
    category: system
    layout: masonry
    order: 4

  - id: studio
    label: Studio
    subtitle: Content, creative, and production
    icon: Palette
    category: creative
    layout: masonry
    order: 5

  - id: adaptive
    label: Adaptive
    subtitle: Self-improving loops and meta-tooling
    icon: Activity
    category: meta
    layout: masonry
    order: 6
    nav_hidden: true
```

### Step 1.3: Create `hubs_loader.py`

Save to `apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py`:

```python
"""Loader and validator for config/system/hubs.yaml.

The file is hand-edited; this module is the canonical reader. It:
  - Loads the YAML.
  - Validates schema (required fields, enum values, unique ids/orders).
  - Returns a structured Hub list ready to feed hubs_emitter.py and the
    orphan-free validator in tests/cli/test_hub_metadata.py.

Track 3b spec: docs/superpowers/specs/2026-04-29-track3b-dashboard-hub-routing-design.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_CATEGORIES = {"personal", "knowledge", "work", "system", "creative", "meta"}
VALID_LAYOUTS = {"masonry"}


@dataclass(frozen=True)
class Hub:
    """One hub entry from config/system/hubs.yaml."""

    id: str
    label: str
    icon: str
    category: str
    layout: str
    order: int
    subtitle: str = ""
    nav_hidden: bool = False
    search_enabled: bool = True


@dataclass(frozen=True)
class HubManifest:
    """Parsed config/system/hubs.yaml."""

    hubs: list[Hub]

    def by_id(self) -> dict[str, Hub]:
        return {h.id: h for h in self.hubs}

    def ids(self) -> set[str]:
        return {h.id for h in self.hubs}


def load_hub_manifest(path: Path | None = None) -> HubManifest:
    """Load and validate config/system/hubs.yaml.

    Args:
        path: Override path (used by tests). Defaults to the canonical
            project-relative location.

    Raises:
        FileNotFoundError: if the manifest doesn't exist.
        ValueError: if any entry is malformed or constraints are violated.
    """
    if path is None:
        from src.config.paths import get_project_root

        path = get_project_root() / "config" / "system" / "hubs.yaml"

    if not path.exists():
        raise FileNotFoundError(f"Hub manifest not found at {path}")

    raw = yaml.safe_load(path.read_text()) or {}
    return _build_manifest(raw)


def _build_manifest(raw: dict[str, Any]) -> HubManifest:
    entries = raw.get("hubs", []) or []
    if not isinstance(entries, list):
        raise ValueError(f"hubs.yaml: 'hubs' must be a list, got {type(entries).__name__}")

    hubs = [_build_hub(e) for e in entries]
    _validate_unique(hubs, key=lambda h: h.id, what="id")
    _validate_unique(hubs, key=lambda h: h.order, what="order")
    return HubManifest(hubs=hubs)


def _build_hub(raw: dict[str, Any]) -> Hub:
    required = {"id", "label", "icon", "category", "layout", "order"}
    missing = required - set(raw.keys())
    if missing:
        raise ValueError(f"hubs.yaml entry missing required fields: {sorted(missing)}; raw={raw!r}")

    category = str(raw["category"])
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"hubs.yaml entry {raw['id']!r}: category {category!r} must be one of {sorted(VALID_CATEGORIES)}"
        )

    layout = str(raw["layout"])
    if layout not in VALID_LAYOUTS:
        raise ValueError(
            f"hubs.yaml entry {raw['id']!r}: layout {layout!r} must be one of {sorted(VALID_LAYOUTS)}"
        )

    search_raw = raw.get("search") or {}
    search_enabled = bool(search_raw.get("enabled", True)) if isinstance(search_raw, dict) else True

    return Hub(
        id=str(raw["id"]),
        label=str(raw["label"]),
        icon=str(raw["icon"]),
        category=category,
        layout=layout,
        order=int(raw["order"]),
        subtitle=str(raw.get("subtitle", "")),
        nav_hidden=bool(raw.get("nav_hidden", False)),
        search_enabled=search_enabled,
    )


def _validate_unique(items: list[Hub], key, what: str) -> None:
    seen: dict[Any, str] = {}
    for h in items:
        v = key(h)
        if v in seen:
            raise ValueError(
                f"hubs.yaml: duplicate {what} {v!r} on hub {h.id!r}; first seen on hub {seen[v]!r}"
            )
        seen[v] = h.id
```

### Step 1.4: Create `hubs_emitter.py`

Save to `apps/dashboard/scripts/skill-scripts/skill_generation/hubs_emitter.py`:

```python
"""Emit apps/dashboard/lib/hubs/generated.ts from a HubManifest.

Track 3b: typed `HUBS` map replaces all hardcoded `'lifestyle'`/`'apple'`
literals in dashboard production code.
"""
from __future__ import annotations

import json
from pathlib import Path

from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import HubManifest

HEADER = """// Auto-generated from config/system/hubs.yaml by hubs_emitter.py.
// Do not edit by hand. Run `/dev-build` to regenerate.

export type HubCategory =
  | "personal"
  | "knowledge"
  | "work"
  | "system"
  | "creative"
  | "meta";

export interface Hub {
  id: string;
  label: string;
  subtitle?: string;
  icon: string;
  category: HubCategory;
  layout: "masonry";
  order: number;
  navHidden: boolean;
  search: { enabled: boolean };
}
"""


def emit_generated_ts(manifest: HubManifest, out_path: Path) -> None:
    """Write apps/dashboard/lib/hubs/generated.ts.

    Idempotent: if the rendered content matches the existing file byte-for-byte,
    no write happens (avoids touching mtime in CI).
    """
    rendered = _render(manifest)
    if out_path.exists() and out_path.read_text() == rendered:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered)


def _render(manifest: HubManifest) -> str:
    lines = [HEADER, "", "export const HUBS: Record<string, Hub> = {"]
    for hub in sorted(manifest.hubs, key=lambda h: h.order):
        entry = {
            "id": hub.id,
            "label": hub.label,
            "icon": hub.icon,
            "category": hub.category,
            "layout": hub.layout,
            "order": hub.order,
            "navHidden": hub.nav_hidden,
            "search": {"enabled": hub.search_enabled},
        }
        if hub.subtitle:
            entry["subtitle"] = hub.subtitle
        # Render as a TS object literal in stable key order.
        body = ", ".join(f"{k}: {json.dumps(v)}" for k, v in entry.items())
        lines.append(f"  {hub.id}: {{ {body} }},")
    lines.append("};")
    lines.append("")
    lines.append("export const HUBS_BY_CATEGORY: Record<HubCategory, Hub[]> = Object.values(HUBS).reduce(")
    lines.append("  (acc, hub) => {")
    lines.append("    (acc[hub.category] ||= []).push(hub);")
    lines.append("    return acc;")
    lines.append("  },")
    lines.append("  {} as Record<HubCategory, Hub[]>,")
    lines.append(");")
    lines.append("")
    lines.append("export const NAV_VISIBLE_HUBS: Hub[] = Object.values(HUBS)")
    lines.append("  .filter((h) => !h.navHidden)")
    lines.append("  .sort((a, b) => a.order - b.order);")
    lines.append("")
    return "\n".join(lines)
```

### Step 1.5: Wire `hubs_emitter` into `dashboard_generator.py`

Read `apps/dashboard/scripts/skill-scripts/skill_generation/dashboard_generator.py` and locate the function that runs at the end of the dashboard scan (the one that writes `assembled-hubs.json` or similar). Add a call at the same level so `generated.ts` emits whenever dashboard generation runs.

Insert near the top of the file (after existing imports):

```python
from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import (
    load_hub_manifest,
)
from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_emitter import (
    emit_generated_ts,
)
```

In whatever top-level orchestration function emits artifacts (commonly named `generate_dashboard()` or `main()`), add immediately before `return`:

```python
    # Track 3b: emit apps/dashboard/lib/hubs/generated.ts from config/system/hubs.yaml.
    from src.config.paths import get_project_root

    _hub_manifest = load_hub_manifest()
    _hubs_out = get_project_root() / "apps" / "dashboard" / "lib" / "hubs" / "generated.ts"
    emit_generated_ts(_hub_manifest, _hubs_out)
```

If the file's orchestration function isn't obvious from a quick scan, add a small `def emit_hubs_generated() -> None:` function exposing the same logic and call it from wherever `dashboard_generator.py` is invoked (top of the existing `if __name__ == "__main__":` block, or inside the function the build script imports).

The legacy `{vertical/horizontal/factory}` block at lines ~26-50 stays untouched in PR 1. PR 5 deletes it.

### Step 1.6: Create the orphan-validator test

Save to `tests/cli/test_hub_metadata.py`:

```python
"""Schema validation + orphan-free check for config/system/hubs.yaml.

Track 3b spec: docs/superpowers/specs/2026-04-29-track3b-dashboard-hub-routing-design.md
"""
from __future__ import annotations

from pathlib import Path

import pytest

from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import (
    Hub,
    HubManifest,
    VALID_CATEGORIES,
    VALID_LAYOUTS,
    load_hub_manifest,
)
from src.config.paths import get_project_root


def _project_root() -> Path:
    return get_project_root()


def test_hubs_yaml_loads():
    """The shipped config/system/hubs.yaml parses without errors."""
    manifest = load_hub_manifest()
    assert isinstance(manifest, HubManifest)
    assert len(manifest.hubs) >= 1


def test_hubs_yaml_contains_six_known_hubs():
    """Track 3b ships with these six hub ids (others may be added later)."""
    manifest = load_hub_manifest()
    expected = {"life", "brain", "career", "command", "studio", "adaptive"}
    assert expected.issubset(manifest.ids())


def test_every_hub_has_valid_category_and_layout():
    manifest = load_hub_manifest()
    for hub in manifest.hubs:
        assert hub.category in VALID_CATEGORIES, hub
        assert hub.layout in VALID_LAYOUTS, hub


def test_hub_orders_are_unique_and_positive():
    manifest = load_hub_manifest()
    orders = [h.order for h in manifest.hubs]
    assert len(orders) == len(set(orders)), "duplicate orders"
    assert all(o > 0 for o in orders), "non-positive order found"


def test_skill_x_augur_hub_references_existing_hub():
    """Every SKILL.md's `x-augur-hub` value must be a hub id in hubs.yaml."""
    import yaml as _yaml

    manifest = load_hub_manifest()
    valid_ids = manifest.ids()

    skills_root = _project_root() / "skills"
    if not skills_root.exists():
        pytest.skip("no skills/ directory at project root")

    orphans: list[tuple[Path, str]] = []
    for skill_md in skills_root.glob("*/SKILL.md"):
        text = skill_md.read_text()
        if not text.startswith("---"):
            continue
        # Frontmatter parse — split on the second '---'.
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            meta = _yaml.safe_load(parts[1]) or {}
        except _yaml.YAMLError:
            continue
        hub = meta.get("x-augur-hub")
        if hub is None:
            continue
        if hub not in valid_ids:
            orphans.append((skill_md.relative_to(_project_root()), hub))

    if orphans:
        msg_lines = [f"  {path} -> x-augur-hub: {hub!r}" for path, hub in orphans]
        pytest.fail(
            "Skills reference x-augur-hub values not present in config/system/hubs.yaml:\n"
            + "\n".join(msg_lines)
            + f"\nValid ids: {sorted(valid_ids)}"
        )
```

### Step 1.7: Run the orphan validator (audit existing skills)

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  uv run pytest tests/cli/test_hub_metadata.py -v 2>&1 | tail -20
```

Expected: 5 passed.

If `test_skill_x_augur_hub_references_existing_hub` fails listing skills with stale `x-augur-hub`, fix each skill's frontmatter to reference a hub id that exists in `hubs.yaml`. Common stale values to remap:

| Stale value | Replacement |
|---|---|
| `lifestyle` | `life` |
| `apple` | (vault-private; ensure the skill is moved to vault per Track 2, OR leave unchanged if it's already a vault skill not subject to this validator) |

Re-run until green. Commit the orphan fixes inside the same PR (one PR; the orphan fix is part of PR 1's contract).

### Step 1.8: Generate `generated.ts` for the first time

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  uv run python -c "
from pathlib import Path
from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import load_hub_manifest
from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_emitter import emit_generated_ts
from src.config.paths import get_project_root

m = load_hub_manifest()
out = get_project_root() / 'apps' / 'dashboard' / 'lib' / 'hubs' / 'generated.ts'
emit_generated_ts(m, out)
print('Wrote', out)
"
```

Expected: `Wrote ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing/apps/dashboard/lib/hubs/generated.ts`

Verify the file:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  head -30 apps/dashboard/lib/hubs/generated.ts
```

Expected: typed header + `export interface Hub` + entries for `life`, `brain`, `career`, `command`, `studio`, `adaptive`.

### Step 1.9: Create `generated.test.ts` smoke test

Save to `apps/dashboard/lib/hubs/generated.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { HUBS, HUBS_BY_CATEGORY, NAV_VISIBLE_HUBS } from "./generated";

describe("hubs/generated", () => {
  it("contains the six known hub ids", () => {
    expect(Object.keys(HUBS).sort()).toEqual(
      ["adaptive", "brain", "career", "command", "life", "studio"].sort(),
    );
  });

  it("every hub has required fields", () => {
    for (const hub of Object.values(HUBS)) {
      expect(hub.id).toBeTruthy();
      expect(hub.label).toBeTruthy();
      expect(hub.icon).toBeTruthy();
      expect(hub.layout).toBe("masonry");
      expect(typeof hub.order).toBe("number");
    }
  });

  it("NAV_VISIBLE_HUBS is sorted by order and excludes nav-hidden hubs", () => {
    const orders = NAV_VISIBLE_HUBS.map((h) => h.order);
    expect(orders).toEqual([...orders].sort((a, b) => a - b));
    for (const hub of NAV_VISIBLE_HUBS) {
      expect(hub.navHidden).toBe(false);
    }
  });

  it("HUBS_BY_CATEGORY groups all hubs", () => {
    const grouped = Object.values(HUBS_BY_CATEGORY).flat();
    expect(grouped.length).toBe(Object.values(HUBS).length);
  });

  it("life hub is in the personal category", () => {
    expect(HUBS.life.category).toBe("personal");
  });

  it("adaptive hub is meta and nav-hidden", () => {
    expect(HUBS.adaptive.category).toBe("meta");
    expect(HUBS.adaptive.navHidden).toBe(true);
  });
});
```

Note: if the dashboard project uses Jest instead of Vitest, replace the import line with `import { describe, expect, it } from "@jest/globals";` (or omit if globals are configured).

### Step 1.10: Run the dashboard build via `/dev-build`

Invoke `/dev-build` (per CLAUDE.md rule #29). This runs the production build with port-owner detection, codex thread state checks, vault sync, and post-build verify.

Expected: build succeeds. The dashboard does NOT yet import `@/lib/hubs/generated`, so its presence is invisible to the build except as a tracked file.

If `/dev-build` re-emits `generated.ts` with a diff, that means the in-tree version is stale. Re-run Step 1.8 to regenerate.

If `/dev-build` reports a chunk-load issue or other failure, run `/dev-debug` to diagnose, fix the underlying issue, then re-run `/dev-build` until it passes. Manual dev-server gymnastics (the patterns in `scripts/hooks/dashboard-shortcut-patterns.sh`) bypass `/dev-build`'s safety contract and are blocked by the project's pre-commit hook.

### Step 1.11: Run the smoke test via `/dev-build`

`/dev-build`'s post-build verify step runs the dashboard's TS/JS test suite. Confirm the new `apps/dashboard/lib/hubs/generated.test.ts` was discovered and passed in `/dev-build`'s output from Step 1.10.

If the test runner skipped the new file (path not yet picked up), re-run `/dev-build` after confirming the file is staged and the workspace test glob includes `apps/dashboard/lib/hubs/*.test.ts`.

Expected: 6 tests passing for `generated.test.ts`. If `/dev-build` reports failures specifically in `generated.test.ts`, run `/dev-debug` for diagnostics and fix the underlying issue.

### Step 1.12: Browser verification (per CLAUDE.md rule #28)

`/dev-build` from Step 1.10 left the dashboard running and verified at `localhost:3000`. Use that running instance.

Manual verification (or Chrome MCP):

1. Open `http://localhost:3000` in a real browser.
2. Confirm the home page loads to interactive state (no chunk-load error overlay, no console red errors).
3. Click into each of the 5 nav-visible hubs (life, brain, career, command, studio) — confirm each renders.
4. Open DevTools console; confirm no errors about `@/lib/hubs/generated`.

If the browser flagged any regression, STOP and report. PR 1 is supposed to be invisible to runtime — any visible change indicates the wiring leaked. Use `/dev-debug` to diagnose any chunk-load or runtime errors before commit.

Do NOT manually start, kill, or restart the dev server — `/dev-build` owns that lifecycle (rule #29).

### Step 1.13: Worktree pollution check + commit

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git status --short
```

Expected (only these paths; no others):

```
?? apps/dashboard/lib/hubs/generated.test.ts
?? apps/dashboard/lib/hubs/generated.ts
?? apps/dashboard/scripts/skill-scripts/skill_generation/hubs_emitter.py
?? apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py
?? config/system/hubs.yaml
?? tests/cli/test_hub_metadata.py
 M apps/dashboard/scripts/skill-scripts/skill_generation/dashboard_generator.py
```

(Plus any skill SKILL.md frontmatter fixes from Step 1.7. If anything else, restore with `git checkout HEAD --` before committing.)

Commit:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git add config/system/hubs.yaml \
          apps/dashboard/lib/hubs/generated.ts \
          apps/dashboard/lib/hubs/generated.test.ts \
          apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py \
          apps/dashboard/scripts/skill-scripts/skill_generation/hubs_emitter.py \
          apps/dashboard/scripts/skill-scripts/skill_generation/dashboard_generator.py \
          tests/cli/test_hub_metadata.py && \
  git commit -m "$(cat <<'EOF'
feat(dashboard): add config/system/hubs.yaml + generated TS map (additive)

Track 3b PR 1 — infrastructure for the hub-routing redesign. This PR is
purely additive: production code does not yet import @/lib/hubs/generated,
so the dashboard renders unchanged.

Changes:
- config/system/hubs.yaml: source-of-truth for hub-level metadata. Six
  hubs registered (life, brain, career, command, studio, adaptive).
- apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py:
  Python loader + validator (schema, unique ids/orders, enum categories).
- apps/dashboard/scripts/skill-scripts/skill_generation/hubs_emitter.py:
  emits apps/dashboard/lib/hubs/generated.ts from a HubManifest;
  idempotent (no write when content matches).
- apps/dashboard/lib/hubs/generated.ts: typed HUBS map + Hub interface +
  HUBS_BY_CATEGORY + NAV_VISIBLE_HUBS. Auto-generated.
- apps/dashboard/lib/hubs/generated.test.ts: smoke test covering known
  ids, schema, nav-ordering, category grouping.
- tests/cli/test_hub_metadata.py: orphan-free validator — every SKILL.md
  x-augur-hub value must reference a hub in hubs.yaml.
- dashboard_generator.py: invokes hubs_emitter at the end of generation.

Legacy {vertical/horizontal/factory} taxonomy in dashboard_generator.py
and comprehensive_dashboard_generator.py is untouched in PR 1; PR 5
deletes it.

Verification:
- tests/cli/test_hub_metadata.py: 5 passed
- /dev-build: succeeded (post-build verify includes generated.test.ts: 6 passed)
- Browser: dashboard renders unchanged (no consumer changes yet)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If pre-commit hooks reject, do NOT use `--no-verify`. Read the hook output, fix the issue (e.g., a lint flag on `hubs_loader.py`), `git add` the fix, and create a NEW commit (do not amend).

---

## Task 2: PR 2 — Dashboard production code (8 files)

**Files (Modify):**
- `apps/dashboard/app/actions.ts`
- `apps/dashboard/lib/api/record-helpers.ts`
- `apps/dashboard/lib/help.ts`
- `apps/dashboard/lib/paths.ts`
- `apps/dashboard/lib/server/voice-memos.ts`
- `apps/dashboard/lib/browse/types.ts`
- `apps/dashboard/features/components/CalendarWidget.tsx`
- `apps/dashboard/features/extensions-bundles/plugins/plugin-dialogs.tsx`

Replace hardcoded `"lifestyle"` / `"apple"` literals in 8 files with `HUBS[id]` lookups via `@/lib/hubs/generated` (added in PR 1). Each file is touched once; behavior is preserved.

### Step 2.1: Verify `@/lib/hubs/generated` is importable

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  ls apps/dashboard/lib/hubs/generated.ts && \
  head -10 apps/dashboard/lib/hubs/generated.ts
```

Expected: file exists, header reads `// Auto-generated from config/system/hubs.yaml ...`. If missing, return to PR 1.

### Step 2.2: Inventory hardcodes in the 8 files

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "\"lifestyle\"\|'lifestyle'\|\"apple\"\|'apple'" \
    apps/dashboard/app/actions.ts \
    apps/dashboard/lib/api/record-helpers.ts \
    apps/dashboard/lib/help.ts \
    apps/dashboard/lib/paths.ts \
    apps/dashboard/lib/server/voice-memos.ts \
    apps/dashboard/lib/browse/types.ts \
    apps/dashboard/features/components/CalendarWidget.tsx \
    apps/dashboard/features/extensions-bundles/plugins/plugin-dialogs.tsx
```

Expected: a list of file:line:literal triples. Note them — they are the migration targets for Steps 2.3-2.10.

### Step 2.3: Migrate `apps/dashboard/app/actions.ts`

Add to the file's top imports (after existing imports):

```typescript
import { HUBS } from "@/lib/hubs/generated";
```

For each hardcoded `"lifestyle"` literal in this file:

| Pattern in original code | Replacement |
|---|---|
| `bundle: "lifestyle"` (object literal) | `bundle: HUBS.life.id` |
| `if (hub === "lifestyle")` | `if (hub === HUBS.life.id)` |
| `"lifestyle"` as a function default | `HUBS.life.id` (drop the `"` quotes) |
| `["lifestyle", "apple"]` (array literal) | `Object.values(HUBS).filter(h => h.category === "personal").map(h => h.id)` — if the original list was meant to enumerate "personal hubs"; otherwise enumerate explicitly: `[HUBS.life.id]` |

Apply each substitution at the noted file:line. Save.

If any hardcode is a fallback ("if no hub specified, default to lifestyle"), replace the fallback with category-based selection:

```typescript
const DEFAULT_PERSONAL_HUB =
  Object.values(HUBS).find((h) => h.category === "personal")?.id ?? HUBS.life.id;
```

Use `DEFAULT_PERSONAL_HUB` in place of the literal.

### Step 2.4: Migrate `apps/dashboard/lib/api/record-helpers.ts`

Add to the file's top imports:

```typescript
import { HUBS } from "@/lib/hubs/generated";
```

For each `"lifestyle"` / `"apple"` literal in this file, apply the substitution rules from Step 2.3. Common patterns in record-helpers:

| Pattern | Replacement |
|---|---|
| `record.bundle === "lifestyle"` | `record.bundle === HUBS.life.id` |
| `defaultBundle = "lifestyle"` | `defaultBundle = HUBS.life.id` |
| Type narrowing: `if (bundle === "lifestyle" \|\| bundle === "apple")` | `if (bundle in HUBS)` (loosens to any hub) — use this only if behavior should be "any registered hub"; otherwise enumerate explicitly. |

### Step 2.5: Migrate `apps/dashboard/lib/help.ts`

Read the file first to understand the structure:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "lifestyle\|apple\|hub" apps/dashboard/lib/help.ts | head -20
```

`help.ts` typically defines per-hub help content. Replace any hardcoded list of hub ids with a derivation from `HUBS`:

```typescript
import { HUBS, NAV_VISIBLE_HUBS } from "@/lib/hubs/generated";

// If the file had: const HUB_IDS = ["lifestyle", "brain", "career"];
// Replace with:
const HUB_IDS = NAV_VISIBLE_HUBS.map((h) => h.id);
```

For per-hub help-text maps (`{ lifestyle: "...", apple: "..." }`), rename the keys to match `HUBS` ids (`life`, `brain`, etc.) and add a runtime check:

```typescript
import { HUBS } from "@/lib/hubs/generated";

const HELP_BY_HUB: Record<string, string> = {
  [HUBS.life.id]: "Personal operating-system surfaces — calendars, voice memos, day plan.",
  [HUBS.brain.id]: "Knowledge, memory, learning loops.",
  // ...etc; one entry per hub
};

export function getHelpForHub(hubId: string): string | undefined {
  if (!(hubId in HUBS)) return undefined;
  return HELP_BY_HUB[hubId];
}
```

If the file had Apple-specific help that should remain (e.g., a vault-only "Apple" entry), gate it on the skill registry rather than a hub literal — Apple is a skill within the Life hub, not a hub itself.

### Step 2.6: Migrate `apps/dashboard/lib/paths.ts`

This file likely defines URL-prefix helpers. Migration pattern:

```typescript
import { HUBS } from "@/lib/hubs/generated";

// Old:
//   export const LIFESTYLE_PATH = "/lifestyle";
// New:
export const LIFE_HUB_PATH = `/${HUBS.life.id}`;

// Old generic:
//   function hubPath(hub: "lifestyle" | "apple"): string { return `/${hub}`; }
// New generic:
export function hubPath(hubId: keyof typeof HUBS): string {
  return `/${HUBS[hubId].id}`;
}
```

For helpers that constructed paths from a literal hub name, accept `keyof typeof HUBS` (a string-literal union derived from `HUBS`) and use `HUBS[hubId].id` to render.

If the file exports any constant whose name embeds the legacy hub name (e.g., `LIFESTYLE_ROUTE`), keep the export name backward-compatible only if a downstream consumer references it; otherwise rename to `LIFE_ROUTE`. Confirm with:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -rn "LIFESTYLE_ROUTE\|LIFESTYLE_PATH" apps/dashboard/ | grep -v generated.ts
```

If matches outside `paths.ts`, either rename them in the same PR or leave the alias in place with a `// TODO_CLEANUP(track3b-pr5)` comment.

### Step 2.7: Migrate `apps/dashboard/lib/server/voice-memos.ts`

Voice memos are a Life-hub feature. The file likely contains `bundle: "lifestyle"` or a fallback to `"lifestyle"`. Migration:

```typescript
import { HUBS } from "@/lib/hubs/generated";

// Old:
//   bundle: "lifestyle"
// New:
bundle: HUBS.life.id
```

If the file had a fallback (`bundle ?? "lifestyle"`), replace with explicit category-based selection:

```typescript
const fallbackHub =
  Object.values(HUBS).find((h) => h.category === "personal")?.id ?? HUBS.life.id;
const resolvedBundle = bundle ?? fallbackHub;
```

If the file's logic is "voice memos always go to the Life hub" (not a fallback for missing input), keep the explicit reference: `bundle: HUBS.life.id` and add a comment:

```typescript
// Voice memos are a Life-hub-owned feature (per skill registry).
bundle: HUBS.life.id,
```

### Step 2.8: Migrate `apps/dashboard/lib/browse/types.ts`

This file likely defines a discriminated union or type alias for hub ids. Migration:

```typescript
// Old:
//   export type HubId = "lifestyle" | "apple" | "brain" | ...;
// New:
import type { Hub } from "@/lib/hubs/generated";
import { HUBS } from "@/lib/hubs/generated";

export type HubId = keyof typeof HUBS;
export type { Hub };
```

This is purely a type-level change. Runtime behavior is identical. Downstream consumers that imported `HubId` keep working — the union just expands to include any hub registered in `HUBS`.

If `types.ts` exported any const arrays of hub ids (e.g., `BROWSE_HUB_IDS`), replace with:

```typescript
export const BROWSE_HUB_IDS: HubId[] = Object.keys(HUBS) as HubId[];
```

### Step 2.9: Migrate `apps/dashboard/features/components/CalendarWidget.tsx`

The Calendar widget likely links to `/lifestyle/...` for the day-plan. Migration:

```tsx
import { HUBS } from "@/lib/hubs/generated";

// Old:
//   <Link href="/lifestyle/day-plan">Today</Link>
// New:
<Link href={`/${HUBS.life.id}/day-plan`}>Today</Link>
```

If the widget renders multiple hub links, inline-construct each:

```tsx
<Link href={`/${HUBS.life.id}`}>{HUBS.life.label}</Link>
<Link href={`/${HUBS.brain.id}`}>{HUBS.brain.label}</Link>
```

### Step 2.10: Migrate `apps/dashboard/features/extensions-bundles/plugins/plugin-dialogs.tsx`

Plugin dialogs typically render a hub picker. Migration:

```tsx
import { NAV_VISIBLE_HUBS } from "@/lib/hubs/generated";

// Old:
//   <Select>
//     <option value="lifestyle">Lifestyle</option>
//     <option value="apple">Apple</option>
//     <option value="brain">Brain</option>
//   </Select>
// New:
<Select>
  {NAV_VISIBLE_HUBS.map((hub) => (
    <option key={hub.id} value={hub.id}>
      {hub.label}
    </option>
  ))}
</Select>
```

If the dialog had a hardcoded "default hub" for new plugin installations, replace with a category-derived default:

```tsx
const defaultHubId =
  NAV_VISIBLE_HUBS.find((h) => h.category === "personal")?.id ?? NAV_VISIBLE_HUBS[0].id;
```

### Step 2.11: Verify zero remaining hardcodes in the 8 files

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "\"lifestyle\"\|'lifestyle'\|\"apple\"\|'apple'" \
    apps/dashboard/app/actions.ts \
    apps/dashboard/lib/api/record-helpers.ts \
    apps/dashboard/lib/help.ts \
    apps/dashboard/lib/paths.ts \
    apps/dashboard/lib/server/voice-memos.ts \
    apps/dashboard/lib/browse/types.ts \
    apps/dashboard/features/components/CalendarWidget.tsx \
    apps/dashboard/features/extensions-bundles/plugins/plugin-dialogs.tsx 2>&1 | head
```

Expected: zero matches. If any remain, return to the relevant Step 2.X.

### Step 2.12: TypeScript build via `/dev-build`

Invoke `/dev-build` (per CLAUDE.md rule #29).

Expected: build succeeds. `/dev-build`'s post-build verify exercises the TS test suite, including any tests that touch the migrated 8 files.

If the build fails with "Cannot find name `HUBS`", an import is missing — re-add `import { HUBS } from "@/lib/hubs/generated";` to the offending file, then re-run `/dev-build`.

If it fails with "Type 'string' is not assignable to type ...", the type narrowing changed; either widen the consumer's type to `keyof typeof HUBS` or cast where appropriate, then re-run `/dev-build`.

For any chunk-load or runtime issue, run `/dev-debug` for diagnostics. Do NOT manually invoke `pnpm`/`next` builds (rule #29).

### Step 2.13: Architecture + CLI tests

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  uv run pytest tests/cli/test_hub_metadata.py tests/architecture/ 2>&1 | tail -5
```

Expected: all pass.

The dashboard JS test suite ran inside `/dev-build`'s post-build verify in Step 2.12; confirm that output reported zero failures before proceeding.

### Step 2.14: Browser verification (per CLAUDE.md rule #28)

`/dev-build` from Step 2.12 left the dashboard running at `localhost:3000`. Use that running instance.

In a real browser (or Chrome MCP):

1. Open `http://localhost:3000` — confirm home page loads to interactive state.
2. Visit `http://localhost:3000/life` — confirm the Life hub renders (was previously `/lifestyle`; existing redirects in `paths.ts` should keep `/lifestyle` working if applicable).
3. Open `http://localhost:3000/settings` and click "Plugins" — confirm the hub-picker dialog enumerates the 5 nav-visible hubs.
4. Confirm the Calendar widget on the home page links to `/life/day-plan`.
5. Open DevTools console — zero errors about `@/lib/hubs/generated`, zero `Failed to load chunk`.

UI/UX review per CLAUDE.md rule #27: confirm spacing, alignment, mobile behavior on the affected pages haven't regressed.

If any browser regression appears, STOP and run `/dev-debug` for diagnostics; fix before commit. Do NOT manually restart the dev server (rule #29).

### Step 2.15: Worktree pollution check + commit

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git status --short
```

Expected: only the 8 modified files (plus any regenerated `apps/dashboard/lib/hubs/generated.ts` from a build run — if so, `git checkout HEAD -- apps/dashboard/lib/hubs/generated.ts` to revert noise unless it's a real diff).

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git add apps/dashboard/app/actions.ts \
          apps/dashboard/lib/api/record-helpers.ts \
          apps/dashboard/lib/help.ts \
          apps/dashboard/lib/paths.ts \
          apps/dashboard/lib/server/voice-memos.ts \
          apps/dashboard/lib/browse/types.ts \
          apps/dashboard/features/components/CalendarWidget.tsx \
          apps/dashboard/features/extensions-bundles/plugins/plugin-dialogs.tsx && \
  git commit -m "$(cat <<'EOF'
refactor(dashboard): consume @/lib/hubs/generated in 8 production files

Track 3b PR 2 — migrate dashboard production code from hardcoded
'lifestyle'/'apple' literals to typed HUBS lookups via the generated
metadata derived from config/system/hubs.yaml in PR 1.

Files migrated:
- apps/dashboard/app/actions.ts
- apps/dashboard/lib/api/record-helpers.ts
- apps/dashboard/lib/help.ts
- apps/dashboard/lib/paths.ts
- apps/dashboard/lib/server/voice-memos.ts
- apps/dashboard/lib/browse/types.ts
- apps/dashboard/features/components/CalendarWidget.tsx
- apps/dashboard/features/extensions-bundles/plugins/plugin-dialogs.tsx

Where a hardcoded literal was a fallback ("if no hub, use lifestyle"),
the fallback is replaced with a category-based selection
(Object.values(HUBS).find(h => h.category === "personal")) or kept as
an explicit reference to HUBS.life.id with a comment if the binding is
intentional domain logic (e.g., voice memos are a Life-hub feature).

Verification:
- /dev-build: succeeded (post-build verify includes dashboard JS tests)
- uv run pytest tests/cli/test_hub_metadata.py tests/architecture/: passed
- Browser: home, /life, /life/day-plan, /browse?category=extensions-bundles all render
  correctly; zero console errors; nav and calendar widget link to
  HUBS.life.id

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If pre-commit hooks reject, do NOT use `--no-verify`. Fix and create a NEW commit.

---

## Task 3: PR 3 — Scanner templates (~10 files)

**Files (Modify):**
- `apps/dashboard/scripts/skill-scripts/blueprint_generator.py`
- `apps/dashboard/scripts/skill-scripts/skill_generation/placement_analyzer.py`
- `apps/dashboard/scripts/skill-scripts/skill_generation/route_templates.py`
- `apps/dashboard/scripts/skill-scripts/skill_generation/productization_plan_generator.py`
- `apps/dashboard/scripts/skill-scripts/_hardening_implementation.py`
- `apps/dashboard/scripts/skill-scripts/import_stages/blueprint.py`
- `apps/dashboard/scripts/skill-scripts/skill_importer.py`
- `apps/dashboard/scripts/skill-scripts/skill_import.py`
- `apps/dashboard/scripts/skill-scripts/import_codegen.py`
- `apps/dashboard/scripts/skill-scripts/generate_skill_ui.py`

These are the skill-import pipeline templates. Today they hardcode `lifestyle` for new-skill scaffolding. After PR 3, they read `config/system/hubs.yaml` and emit hub-neutral code.

### Step 3.1: Inventory hardcodes across the 10 files

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "\"lifestyle\"\|'lifestyle'\|x-augur-hub: lifestyle\|hub.*=.*lifestyle\|hub.*=.*\"life\"" \
    apps/dashboard/scripts/skill-scripts/blueprint_generator.py \
    apps/dashboard/scripts/skill-scripts/skill_generation/placement_analyzer.py \
    apps/dashboard/scripts/skill-scripts/skill_generation/route_templates.py \
    apps/dashboard/scripts/skill-scripts/skill_generation/productization_plan_generator.py \
    apps/dashboard/scripts/skill-scripts/_hardening_implementation.py \
    apps/dashboard/scripts/skill-scripts/import_stages/blueprint.py \
    apps/dashboard/scripts/skill-scripts/skill_importer.py \
    apps/dashboard/scripts/skill-scripts/skill_import.py \
    apps/dashboard/scripts/skill-scripts/import_codegen.py \
    apps/dashboard/scripts/skill-scripts/generate_skill_ui.py 2>&1 | head -40
```

Note each file:line — those are the migration targets.

### Step 3.2: Define a shared default-hub helper

For consistency across the 10 files, the default-hub-resolver lives in `hubs_loader.py`. Add to the bottom of `apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py`:

```python
def resolve_default_hub_for_type(skill_type: str | None) -> str:
    """Pick a default hub for a newly-imported skill based on its declared type.

    `skill_type` is the value of `x-augur-type` in the skill's SKILL.md
    frontmatter (or None if not declared). The mapping below reflects current
    Augur hub semantics; new types fall back to the user's declared default
    via PROMPT (callers should treat None as "ask the user").

    Track 3b: replaces hardcoded `'lifestyle'` defaults across the
    skill-import pipeline.
    """
    manifest = load_hub_manifest()
    by_id = manifest.by_id()

    type_to_category = {
        "personal": "personal",
        "knowledge": "knowledge",
        "career": "work",
        "platform": "system",
        "creative": "creative",
        "meta": "meta",
    }
    category = type_to_category.get(skill_type or "")
    if category is None:
        # Caller should prompt the user; we return None-equivalent ("life")
        # only as last-resort fallback to keep templates compile-able.
        return next(iter(by_id))  # First hub in YAML order.

    candidates = [h for h in manifest.hubs if h.category == category]
    if candidates:
        return min(candidates, key=lambda h: h.order).id
    return next(iter(by_id))
```

This commits in PR 3 (PR 1 didn't need it). Confirm by reading PR 1's `hubs_loader.py` first; if `resolve_default_hub_for_type` already exists from PR 1, skip this step.

### Step 3.3: Migrate `blueprint_generator.py`

Read the current state:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "lifestyle\|x-augur-hub" apps/dashboard/scripts/skill-scripts/blueprint_generator.py | head
```

For each match, replace the hardcoded `'lifestyle'` with a call to `resolve_default_hub_for_type`:

| Pattern | Replacement |
|---|---|
| `hub = 'lifestyle'` | `from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import resolve_default_hub_for_type` (top of file) + `hub = resolve_default_hub_for_type(skill_type)` |
| `frontmatter += "x-augur-hub: lifestyle\n"` | `frontmatter += f"x-augur-hub: {hub}\n"` (where `hub` was resolved earlier) |
| `default_hub = "lifestyle"` (function arg default) | Remove the default; require the caller to pass `hub` explicitly. |

If the function signature was `def generate_blueprint(skill_name, hub="lifestyle")`, change to:

```python
def generate_blueprint(skill_name: str, hub: str | None = None, skill_type: str | None = None) -> str:
    from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import resolve_default_hub_for_type
    if hub is None:
        hub = resolve_default_hub_for_type(skill_type)
    # ... rest of function uses `hub`
```

### Step 3.4: Migrate `placement_analyzer.py`

Same pattern. Replace `'lifestyle'` literals with `resolve_default_hub_for_type(skill_type)` calls. Add the import to the top of the file:

```python
from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import resolve_default_hub_for_type
```

If `placement_analyzer.py` enumerates a list of "valid hubs" (e.g., `VALID_HUBS = ['lifestyle', 'apple', 'brain']`), replace with:

```python
from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import load_hub_manifest

def _valid_hub_ids() -> set[str]:
    return load_hub_manifest().ids()
```

Use `_valid_hub_ids()` everywhere `VALID_HUBS` was previously consulted.

### Step 3.5: Migrate `route_templates.py`

This file likely contains route-prefix string templates. Replace literal route prefixes:

| Pattern | Replacement |
|---|---|
| `f"/lifestyle/{skill_name}"` | `f"/{hub}/{skill_name}"` (where `hub` is a parameter passed in) |
| `route_prefix = '/lifestyle'` | Drop the constant; parameterize the template caller. |

Add at the top:

```python
from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import resolve_default_hub_for_type
```

Refactor each template-rendering function to accept a `hub: str` parameter (no default):

```python
def render_skill_route_template(skill_name: str, hub: str) -> str:
    return f"""
import {{ HUBS }} from '@/lib/hubs/generated';

export const ROUTE_PATH = `/${{HUBS.{hub}.id}}/${skill_name}`;
"""
```

### Step 3.6: Migrate `productization_plan_generator.py`

Same substitution pattern. Read the file, locate `lifestyle` literals, replace with `resolve_default_hub_for_type` or parameterize.

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "lifestyle" apps/dashboard/scripts/skill-scripts/skill_generation/productization_plan_generator.py
```

For each match: if it's a default value, replace with `resolve_default_hub_for_type(skill_type)`; if it's a comparison (`if hub == "lifestyle"`), replace with `if hub == HUBS["life"].id` semantics — but in Python that's `if hub == "life"` (use the new hub id directly, with a comment):

```python
# Track 3b: 'lifestyle' renamed to 'life' in config/system/hubs.yaml.
if hub == "life":
    ...
```

### Step 3.7: Migrate `_hardening_implementation.py`

Same pattern. Inventory + substitute.

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "lifestyle" apps/dashboard/scripts/skill-scripts/_hardening_implementation.py
```

If this file does hardening checks like "every skill must declare x-augur-hub", verify it uses the orphan-validator approach (against `hubs.yaml`) rather than a hardcoded list. Add:

```python
from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import load_hub_manifest

def _is_valid_hub(hub_id: str) -> bool:
    return hub_id in load_hub_manifest().ids()
```

### Step 3.8: Migrate `import_stages/blueprint.py`

Same pattern.

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "lifestyle" apps/dashboard/scripts/skill-scripts/import_stages/blueprint.py
```

For each match: substitute via `resolve_default_hub_for_type` or `load_hub_manifest`.

### Step 3.9: Migrate `skill_importer.py`, `skill_import.py`, `import_codegen.py`, `generate_skill_ui.py`

All four follow the same substitution rule. For each file:

1. Add the import at the top:
   ```python
   from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import (
       load_hub_manifest,
       resolve_default_hub_for_type,
   )
   ```
2. Replace each `'lifestyle'` literal with one of:
   - `resolve_default_hub_for_type(skill_type)` if it's a default-fallback site.
   - `"life"` (the new hub id) if it's a domain-correct reference (e.g., the Calendar feature lives in the Life hub).
   - `load_hub_manifest().ids()` if it's part of an allow-list check.

3. Remove any function default of `hub="lifestyle"` and require the caller to pass `hub` explicitly.

For each file, read it after editing to confirm the substitutions applied cleanly:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  for f in apps/dashboard/scripts/skill-scripts/skill_importer.py \
           apps/dashboard/scripts/skill-scripts/skill_import.py \
           apps/dashboard/scripts/skill-scripts/import_codegen.py \
           apps/dashboard/scripts/skill-scripts/generate_skill_ui.py; do
    echo "=== $f ==="
    grep -n "lifestyle" "$f" || echo "  (clean)"
  done
```

Expected: each file reports `(clean)` or only references inside comments / docstrings explicitly noting "renamed from lifestyle to life".

### Step 3.10: Verify zero hardcodes in the 10 PR 3 files

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "\"lifestyle\"\|'lifestyle'" \
    apps/dashboard/scripts/skill-scripts/blueprint_generator.py \
    apps/dashboard/scripts/skill-scripts/skill_generation/placement_analyzer.py \
    apps/dashboard/scripts/skill-scripts/skill_generation/route_templates.py \
    apps/dashboard/scripts/skill-scripts/skill_generation/productization_plan_generator.py \
    apps/dashboard/scripts/skill-scripts/_hardening_implementation.py \
    apps/dashboard/scripts/skill-scripts/import_stages/blueprint.py \
    apps/dashboard/scripts/skill-scripts/skill_importer.py \
    apps/dashboard/scripts/skill-scripts/skill_import.py \
    apps/dashboard/scripts/skill-scripts/import_codegen.py \
    apps/dashboard/scripts/skill-scripts/generate_skill_ui.py
```

Expected: zero matches (or only inside explanatory comments).

### Step 3.11: "Generate a new skill" smoke test

The skill-import pipeline isn't trivially invoked from the command line in all setups; if a high-level driver exists (e.g., `aug skills import <name>`), use it. Otherwise, drive `blueprint_generator.py` directly:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  uv run python -c "
from apps.dashboard.scripts.skill_scripts.blueprint_generator import generate_blueprint
text = generate_blueprint(skill_name='track3b-smoke-skill', skill_type='knowledge')
print(text[:500])
assert 'x-augur-hub: brain' in text or 'x-augur-hub: ' in text, text
print('OK')
"
```

Expected: prints a blueprint with `x-augur-hub: brain` (or another knowledge-category hub).

If the skill-import driver picks a different default behavior (e.g., always prompts the user), adapt the smoke test to call the lower-level function that returns the rendered blueprint directly.

### Step 3.12: Idempotency check (existing scanner output unchanged)

The existing scanner emits `apps/dashboard/lib/plugin-runtime/assembled-hubs.json` and `apps/dashboard/lib/tabs/generated-registry.ts`. After PR 3, regenerating must produce no diff for already-imported skills.

Invoke `/dev-build` (per CLAUDE.md rule #29). After it completes, check the regenerated artifact diff:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git diff --stat apps/dashboard/lib/plugin-runtime/assembled-hubs.json apps/dashboard/lib/tabs/generated-registry.ts apps/dashboard/lib/hubs/generated.ts
```

Expected: no diff (or only `apps/dashboard/lib/hubs/generated.ts` if PR 1 didn't yet check in the canonical version — should be clean). If `assembled-hubs.json` or `generated-registry.ts` show drift, PR 3 introduced a behavioral regression for existing skills. Investigate via `/dev-debug` if the cause isn't obvious from the diff.

### Step 3.13: Pytest cascade

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  uv run pytest tests/cli/test_hub_metadata.py tests/architecture/ skills/ 2>&1 | tail -10
```

Expected: all pass.

### Step 3.14: Worktree pollution check + commit

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git status --short
```

Expected: only the 10 PR 3 files (plus possibly `hubs_loader.py` if Step 3.2 added `resolve_default_hub_for_type`).

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git add apps/dashboard/scripts/skill-scripts/blueprint_generator.py \
          apps/dashboard/scripts/skill-scripts/skill_generation/placement_analyzer.py \
          apps/dashboard/scripts/skill-scripts/skill_generation/route_templates.py \
          apps/dashboard/scripts/skill-scripts/skill_generation/productization_plan_generator.py \
          apps/dashboard/scripts/skill-scripts/_hardening_implementation.py \
          apps/dashboard/scripts/skill-scripts/import_stages/blueprint.py \
          apps/dashboard/scripts/skill-scripts/skill_importer.py \
          apps/dashboard/scripts/skill-scripts/skill_import.py \
          apps/dashboard/scripts/skill-scripts/import_codegen.py \
          apps/dashboard/scripts/skill-scripts/generate_skill_ui.py \
          apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py && \
  git commit -m "$(cat <<'EOF'
refactor(scanner): skill-import templates consume config/system/hubs.yaml

Track 3b PR 3 — migrate the 10 files in the skill-import pipeline that
hardcoded 'lifestyle' for new-skill scaffolding. Each template now
reads config/system/hubs.yaml via hubs_loader.resolve_default_hub_for_type
and emits hub-neutral code; the default hub for a new skill is picked
based on the declared x-augur-type, never hardcoded to 'lifestyle'.

Files migrated:
- blueprint_generator.py
- skill_generation/placement_analyzer.py
- skill_generation/route_templates.py
- skill_generation/productization_plan_generator.py
- _hardening_implementation.py
- import_stages/blueprint.py
- skill_importer.py
- skill_import.py
- import_codegen.py
- generate_skill_ui.py

hubs_loader.py gains resolve_default_hub_for_type(skill_type) for
shared use across the pipeline.

Verification:
- Generate-a-skill smoke: blueprint renders with x-augur-hub: brain
  for a knowledge-typed skill.
- Idempotency: /dev-build produces zero diff in
  apps/dashboard/lib/{plugin-runtime/assembled-hubs.json,tabs/generated-registry.ts}.
- pytest tests/cli/test_hub_metadata.py tests/architecture/ skills/: all pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If pre-commit hooks reject, do NOT use `--no-verify`. Fix and create a NEW commit.

---

## Task 4: PR 4 — Workflow tools (~5 files)

**Files (Modify):**
- `apps/dashboard/scripts/skill-scripts/mcp/tools_plugin.py`
- `apps/dashboard/scripts/skill-scripts/mcp/tools_workflow.py`
- `apps/dashboard/scripts/skill-scripts/workflow/engine.py`
- `apps/dashboard/scripts/skill-scripts/workflow/state_manager.py`
- `apps/dashboard/scripts/skill-scripts/scoring/user_research.py`

Workflow tools sometimes legitimately reference a specific hub as part of domain logic (e.g., user-research scoring rules tied to a hub). Each site is reviewed case-by-case.

### Step 4.1: Inventory hardcodes across the 5 files

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "\"lifestyle\"\|'lifestyle'\|\"apple\"\|'apple'" \
    apps/dashboard/scripts/skill-scripts/mcp/tools_plugin.py \
    apps/dashboard/scripts/skill-scripts/mcp/tools_workflow.py \
    apps/dashboard/scripts/skill-scripts/workflow/engine.py \
    apps/dashboard/scripts/skill-scripts/workflow/state_manager.py \
    apps/dashboard/scripts/skill-scripts/scoring/user_research.py
```

Note each file:line:literal triple. Each one needs a case-by-case decision.

### Step 4.2: Classify each hardcode

For each match from Step 4.1, classify into one of three buckets:

- **Templating (migrate)**: the literal is a placeholder for "whatever hub the tool was invoked for". Replace with a parameter or `resolve_default_hub_for_type`.
- **Domain logic (preserve with comment)**: the literal is intentional — the workflow specifically operates on the Life or Apple hub for product reasons. Keep the literal; add a comment explaining why.
- **Stale code (cleanup)**: the literal is dead code from a previous abstraction. Delete or rewrite.

Apply the appropriate rewrite per site:

**Templating substitution (same as PR 3):**

```python
from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import (
    resolve_default_hub_for_type,
)

# Old:
#   hub = "lifestyle"
# New:
hub = resolve_default_hub_for_type(skill_type)
```

**Domain-logic preservation:**

```python
# Track 3b: 'life' is intentional — user-research scoring weights are
# tuned for personal-OS workflows specifically. Other hubs use the
# generic scoring path (see _generic_score_workflow below).
if hub == "life":
    return _personal_os_scoring(workflow)
```

(Note the rename: `'lifestyle'` → `'life'` per `hubs.yaml`.)

**Stale code:**

```python
# Old:
#   if hub == "lifestyle" and feature == "deprecated_thing":
#       return special_handling()
# New:
# (Delete the entire block — feature was removed in <prior commit>.)
```

### Step 4.3: Migrate `tools_plugin.py`

Apply the classification + rewrite from Step 4.2 to each match in this file. Read the file first to understand the call sites:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -B 3 -A 3 "lifestyle\|'apple'\|\"apple\"" apps/dashboard/scripts/skill-scripts/mcp/tools_plugin.py | head -40
```

For each match:
- If it's a default value in a function signature, drop the default and require an explicit `hub` parameter.
- If it's a comparison, replace `"lifestyle"` with `"life"` (the new id) and add a `# Track 3b: renamed from lifestyle to life.` comment if the rename isn't obvious.
- If it's an `apple` reference, the situation is different — `apple` is a vault-private skill, not a hub. Confirm by reading the surrounding context; if `apple` is used as a hub id, fix the conceptual confusion: replace with the hub the apple skill belongs to (`HUBS.life.id` per the `apple` skill's `x-augur-hub` value). If `apple` is used as a skill id, leave it.

### Step 4.4: Migrate `tools_workflow.py`

Same procedure as Step 4.3.

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -B 3 -A 3 "lifestyle\|'apple'\|\"apple\"" apps/dashboard/scripts/skill-scripts/mcp/tools_workflow.py | head -40
```

Apply the rewrite per Step 4.2's classification.

### Step 4.5: Migrate `workflow/engine.py`

Same procedure.

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -B 3 -A 3 "lifestyle\|'apple'\|\"apple\"" apps/dashboard/scripts/skill-scripts/workflow/engine.py | head -40
```

Workflow-engine references are most likely templating (a workflow's target hub is parametrized at run time). If you find a hardcoded fallback ("if no hub specified, default to lifestyle"), replace with an explicit error:

```python
if hub is None:
    raise ValueError(
        "workflow.engine: hub must be specified explicitly; "
        "previous default of 'lifestyle' is removed in Track 3b"
    )
```

This is a behavior change. If callers actually depended on the silent default, you'll catch them at test time — fix each caller to pass `hub` explicitly.

### Step 4.6: Migrate `workflow/state_manager.py`

Same procedure.

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -B 3 -A 3 "lifestyle\|'apple'\|\"apple\"" apps/dashboard/scripts/skill-scripts/workflow/state_manager.py | head -40
```

### Step 4.7: Migrate `scoring/user_research.py`

This file is the highest-likelihood site for intentional domain logic. User-research scoring may legitimately treat the Life hub differently from other hubs because the underlying questionnaire is personal-OS-specific.

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -B 5 -A 5 "lifestyle\|'apple'\|\"apple\"" apps/dashboard/scripts/skill-scripts/scoring/user_research.py
```

Classify each match. If it's intentional domain logic, preserve with explanatory comments per Step 4.2's "Domain-logic preservation" pattern. If it's templating, migrate.

### Step 4.8: Verify zero unintentional hardcodes

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "\"lifestyle\"\|'lifestyle'" \
    apps/dashboard/scripts/skill-scripts/mcp/tools_plugin.py \
    apps/dashboard/scripts/skill-scripts/mcp/tools_workflow.py \
    apps/dashboard/scripts/skill-scripts/workflow/engine.py \
    apps/dashboard/scripts/skill-scripts/workflow/state_manager.py \
    apps/dashboard/scripts/skill-scripts/scoring/user_research.py
```

Expected: zero matches of `"lifestyle"` (the legacy literal). Any remaining `"life"` or other hub literals should have an adjacent `# Track 3b:` comment explaining intentional preservation.

### Step 4.9: Workflow execution test

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  uv run pytest apps/dashboard/scripts/skill-scripts/workflow/ -v 2>&1 | tail -10
```

Expected: all pass.

If the workflow tests don't live alongside the source, find them:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  find . -name "test_workflow*.py" -not -path "*/node_modules/*" -not -path "*/.next/*" -not -path "*/.worktrees/*" 2>/dev/null
```

Run the tests at whatever path they live.

### Step 4.10: MCP tool smoke test

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  uv run pytest tests/architecture/ tests/cli/test_hub_metadata.py 2>&1 | tail -5
```

Expected: all pass.

If a project-tier MCP server smoke test exists (e.g., `tests/mcp/test_tools_plugin.py`), run it to confirm the workflow MCP tools still register and return the expected tool list:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  find tests -name "test_tools_*" 2>/dev/null
```

### Step 4.11: Worktree pollution check + commit

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git status --short
```

Expected: only the 5 PR 4 files.

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git add apps/dashboard/scripts/skill-scripts/mcp/tools_plugin.py \
          apps/dashboard/scripts/skill-scripts/mcp/tools_workflow.py \
          apps/dashboard/scripts/skill-scripts/workflow/engine.py \
          apps/dashboard/scripts/skill-scripts/workflow/state_manager.py \
          apps/dashboard/scripts/skill-scripts/scoring/user_research.py && \
  git commit -m "$(cat <<'EOF'
refactor(workflow): hub references migrated case-by-case

Track 3b PR 4 — migrate the 5 workflow / MCP tool files that
case-by-case reference hub names. Each site classified into one of:

- Templating: replaced with resolve_default_hub_for_type() or required
  explicit hub parameter.
- Domain logic: preserved with explanatory `# Track 3b:` comment.
- Stale code: deleted.

Files migrated:
- mcp/tools_plugin.py
- mcp/tools_workflow.py
- workflow/engine.py (silent 'lifestyle' default replaced with explicit
  ValueError; callers fixed to pass hub explicitly)
- workflow/state_manager.py
- scoring/user_research.py (highest-likelihood domain logic site;
  intentional Life-hub references preserved with comments)

Verification:
- pytest workflow tests: passed
- pytest tests/architecture/ tests/cli/test_hub_metadata.py: passed
- MCP tool smoke (where available): tools register correctly

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If pre-commit hooks reject, do NOT use `--no-verify`. Fix and create a NEW commit.

---

## Task 5: PR 5 — Cleanup + ADR

**Files (Modify):**
- `apps/dashboard/scripts/skill-scripts/skill_generation/dashboard_generator.py` — delete the legacy `{vertical/horizontal/factory}` mapping block.
- `apps/dashboard/scripts/skill-scripts/skill_generation/comprehensive_dashboard_generator.py` — delete the same block.

**Files (Create):**
- `<get_adr_dir()>/track3b-dashboard-hub-routing.md` — the ADR. Path resolves at runtime via `src.config.paths.get_adr_dir()`; on this machine it's `~/Documents/Augur/adrs/track3b-dashboard-hub-routing.md`.

Final pass: delete the legacy taxonomy, run the audit grep, write the ADR, run final browser verify.

### Step 5.1: Locate the legacy taxonomy block in `dashboard_generator.py`

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "vertical\|horizontal\|factory\|lifestyle" apps/dashboard/scripts/skill-scripts/skill_generation/dashboard_generator.py
```

Expected approximate output (line numbers may have shifted):

```
26:        layer: Layer (factory, horizontal, vertical)
41:    if layer == 'vertical':
42:        page_path = dashboard_dir / 'lifestyle' / skill_name / 'page.tsx'
43:        layout_path = dashboard_dir / 'lifestyle' / skill_name / 'layout.tsx'
44:    elif layer == 'horizontal':
47:    else:  # factory
181:    if layer not in ['vertical', 'horizontal']:
184:    parent_route = 'lifestyle' if layer == 'vertical' else 'hands'
```

### Step 5.2: Delete the legacy taxonomy in `dashboard_generator.py`

Read the file first to understand what each function does. The `{vertical/horizontal/factory}` mapping is conceptually replaced by the `category` field on each hub in `hubs.yaml`.

Replacements:

- Functions that branched on `layer` in `('vertical', 'horizontal', 'factory')` should now branch on the hub's `category` (`personal`, `knowledge`, `work`, `system`, `creative`, `meta`).
- Function signatures previously taking a `layer: str` parameter should take `hub: str` (a hub id).
- Path constructions like `dashboard_dir / 'lifestyle' / skill_name` become `dashboard_dir / hub / skill_name`.

Apply the edit:

For the function whose signature is `def emit_skill_pages(skill_name: str, layer: str, dashboard_dir: Path)`:

```python
def emit_skill_pages(skill_name: str, hub: str, dashboard_dir: Path) -> None:
    """Emit skill page + layout under apps/dashboard/app/<hub>/<skill_name>/.

    Track 3b: replaces the previous `layer in {vertical, horizontal, factory}`
    selector. The hub's category determines what kind of layout the
    generator emits (see hubs.yaml).
    """
    from apps.dashboard.scripts.skill_scripts.skill_generation.hubs_loader import load_hub_manifest

    by_id = load_hub_manifest().by_id()
    if hub not in by_id:
        raise ValueError(f"Unknown hub {hub!r}; valid: {sorted(by_id)}")
    hub_meta = by_id[hub]

    page_path = dashboard_dir / hub / skill_name / "page.tsx"
    layout_path = dashboard_dir / hub / skill_name / "layout.tsx"
    # ...rest of body uses hub_meta.category for layout-template selection
```

For the function with `parent_route = 'lifestyle' if layer == 'vertical' else 'hands'`:

```python
def parent_route_for(hub: str) -> str:
    """Return the URL parent route for a hub.

    Track 3b: simplified — the parent route is just the hub id; the
    legacy 'hands' route was the horizontal-layer artifact and no longer
    applies once skills declare their hub directly via x-augur-hub.
    """
    return f"/{hub}"
```

Update all call sites of the renamed functions to pass `hub: str` instead of `layer: str`.

If a call site receives `layer` from upstream code that no longer exists, trace upstream and fix the callsite-of-the-callsite.

### Step 5.3: Delete the legacy taxonomy in `comprehensive_dashboard_generator.py`

Same procedure as Step 5.2 for the parallel block in `comprehensive_dashboard_generator.py`. Locate:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -n "vertical\|horizontal\|factory\|lifestyle" apps/dashboard/scripts/skill-scripts/skill_generation/comprehensive_dashboard_generator.py
```

Apply the same parameter rename + path-construction rewrite.

### Step 5.4: Audit grep — zero remaining hardcodes

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  grep -rn "\"apple\"\|'apple'\|\"lifestyle\"\|'lifestyle'\|\"obsidian\"\|'obsidian'\|\"file-manager\"\|'file-manager'\|\"ingest\"\|'ingest'\|\"vertical\"\|'vertical'\|\"horizontal\"\|'horizontal'\|\"factory\"\|'factory'" \
    --include="*.py" --include="*.ts" --include="*.tsx" \
    apps/dashboard/ scripts/skill-scripts/ 2>&1 | grep -v "^Binary\|node_modules\|\.next\|__pycache__\|generated\.ts\|generated-registry\.ts\|assembled-hubs\.json"
```

Acceptable matches (allowlisted in the commit message):

1. **Test fixtures** — files under `*/tests/fixtures/` that intentionally include legacy taxonomy strings to test backward compat or migration logic. Confirm by reading the file path; allow if it's a fixture.
2. **Comments / docstrings** — explanatory comments noting "renamed from `lifestyle` to `life` in Track 3b" are acceptable.
3. **Intentional domain logic** (PR 4 sites) — entries with adjacent `# Track 3b: ...` comments preserving a specific hub binding for domain reasons.
4. **`comprehensive_dashboard_generator.py` and `dashboard_generator.py`** — should now have ZERO matches after Steps 5.2 + 5.3. If matches persist, return to those steps.

For each remaining match, classify and either:
- Add a `# Track 3b: intentional, ...` comment if it's domain logic.
- Add to a documented allowlist (in PR 5's commit message body, list the file:line:reason for each preserved match).
- Fix it (replace with a non-literal lookup).

Real hardcodes get fixed in this step.

### Step 5.5: Final dashboard build via `/dev-build`

Invoke `/dev-build` (per CLAUDE.md rule #29).

Expected: build succeeds with the legacy taxonomy fully removed. `/dev-build`'s post-build verify exercises the dashboard JS test suite plus the orphan validator.

If `/dev-build` fails, run `/dev-debug` for diagnostics. Do NOT manually invoke `pnpm` or remove `.next` (rule #29).

### Step 5.6: Final pytest cascade

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  uv run pytest tests/cli/test_hub_metadata.py tests/architecture/ skills/ 2>&1 | tail -10
```

Expected: all pass.

### Step 5.7: Browser verification (per CLAUDE.md rule #28)

`/dev-build` from Step 5.5 left the dashboard running at `localhost:3000`. Use that running instance.

In a real browser (or Chrome MCP):

1. Open `http://localhost:3000` — confirm home page loads to interactive state, no `Failed to load chunk`, no console red errors.
2. Visit each nav-visible hub: `/life`, `/brain`, `/career`, `/command`, `/studio`. Each renders.
3. Pick one skill in each hub and visit its detail page. Each renders.
4. Open `/browse?category=extensions-bundles` — confirm the Extensions & Bundles manager renders and the hub-picker enumerates the 5 nav-visible hubs.
5. Calendar widget on home links to `/life/...`.
6. UI/UX review per CLAUDE.md rule #27: spacing, alignment, mobile breakpoints, CTA consistency intact.

If anything regresses, run `/dev-debug` for diagnostics; fix before commit. Do NOT manually restart the dev server (rule #29).

### Step 5.8: Write the ADR

Resolve the ADR directory:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  uv run python -c "from src.config.paths import get_adr_dir; print(get_adr_dir())"
```

Expected: `~/Documents/Augur/adrs` (or wherever `get_adr_dir()` resolves on this machine).

Save to `<that-dir>/track3b-dashboard-hub-routing.md`:

```markdown
---
title: ADR — Track 3b: Dashboard Hub-Routing Redesign
date: 2026-04-29
status: Implemented
related:
  - 2026-04-28-cross-client-bundle-architecture-design
  - 2026-04-28-cross-client-bundle-migration-design
  - 2026-04-29-track3b-dashboard-hub-routing-design
---

# ADR — Track 3b: Dashboard Hub-Routing Redesign

## Status

Implemented.

## Context

Layer 4 of the cross-client bundle architecture migration deferred the
dashboard hub-routing redesign to its own track. The dashboard hardcoded
specific hub names (`lifestyle`, `apple`) across 50+ files instead of
reading hub assignments from skill metadata. The legacy
`{vertical/horizontal/factory}` taxonomy in `dashboard_generator.py` was
not reflected in `x-augur-hub` and not documented in CLAUDE.md.

References:
- `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- `docs/superpowers/specs/2026-04-29-track3b-dashboard-hub-routing-design.md`

## Decision

The canonical hub model is:
- `config/system/hubs.yaml` — hand-edited source-of-truth for hub-level
  metadata (id, label, icon, category, layout, order, nav_hidden).
- `apps/dashboard/lib/hubs/generated.ts` — auto-generated typed `HUBS`
  map plus `Hub` interface, `HUBS_BY_CATEGORY`, and `NAV_VISIBLE_HUBS`.
- Per-skill hub assignment stays in each skill's SKILL.md via
  `x-augur-hub`, per CLAUDE.md rule #13.

The generation pipeline runs as part of `/dev-build`:
Python `hubs_loader` reads `hubs.yaml`; `hubs_emitter` writes the typed
TS derivative; the orphan validator (`tests/cli/test_hub_metadata.py`)
ensures every `x-augur-hub` references a registered hub id.

The legacy `{vertical: lifestyle, horizontal: hands, factory: agents}`
taxonomy is retired. It is replaced by the `category` field on each hub
(values: `personal`, `knowledge`, `work`, `system`, `creative`, `meta`).

The migration shipped as 5 PRs:
1. Infrastructure (additive: `hubs.yaml`, scanner, `generated.ts`).
2. Dashboard production code (8 files in `apps/dashboard/{app,lib,features}/`).
3. Scanner templates (10 files in the skill-import pipeline).
4. Workflow tools (5 files; case-by-case domain logic preserved with comments).
5. Cleanup + this ADR (legacy taxonomy deleted; audit grep clean).

## Verification

- `tests/cli/test_hub_metadata.py` enforces orphan-free `x-augur-hub`
  references and schema validity.
- Browser verification on PRs 1, 2, 5 confirmed the dashboard renders
  correctly with the new pipeline.
- Audit grep across `apps/dashboard/` and `scripts/skill-scripts/` shows
  zero hardcoded `"lifestyle"` / `"apple"` / `"obsidian"` /
  `"file-manager"` / `"ingest"` / `"vertical"` / `"horizontal"` /
  `"factory"` literals in production code (allowlist documented in
  PR 5's commit body).

## Consequences

- New hubs are added by editing `config/system/hubs.yaml` and running
  `/dev-build`. No code changes required.
- Skills declare their hub via `x-augur-hub` in SKILL.md frontmatter;
  the orphan validator catches stale references at CI time.
- The dashboard's hub URL prefixes derive from hub ids in `hubs.yaml`
  rather than hardcoded literals, so renaming a hub is a one-line edit
  in YAML plus a regeneration.
- Track 3b retires no architecture-test allowlist entries (the allowlist
  is about cross-skill Python imports; this track is dashboard hub
  routing).
```

### Step 5.9: Confirm the ADR file path

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  ADR_DIR=$(uv run python -c "from src.config.paths import get_adr_dir; print(get_adr_dir())") && \
  ls -la "$ADR_DIR/track3b-dashboard-hub-routing.md"
```

Expected: file exists.

The ADR lives in the external `get_adr_dir()` repo (per CLAUDE.md rule #12 and ADR-270 paths). It is NOT inside the Augur worktree, so it does not need to be `git add`-ed to this PR. Commit the ADR in its own repo separately if `get_adr_dir()` is a git repo:

```bash
ADR_DIR=$(cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && uv run python -c "from src.config.paths import get_adr_dir; print(get_adr_dir())") && \
  cd "$ADR_DIR" && \
  git status --short
```

If `$ADR_DIR` is a git repo with uncommitted changes including the new ADR, commit:

```bash
cd "$ADR_DIR" && \
  git add track3b-dashboard-hub-routing.md && \
  git commit -m "$(cat <<'EOF'
ADR: Track 3b — Dashboard Hub-Routing Redesign (Implemented)

Records the canonical hub model (config/system/hubs.yaml + per-skill
x-augur-hub), the generation pipeline (Python scanner emits typed TS
derivative), and the retirement of the {vertical/horizontal/factory}
legacy taxonomy. Five PRs landed: infrastructure, dashboard production
(8 files), scanner templates (10 files), workflow tools (5 files),
cleanup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If `$ADR_DIR` is not a git repo, just leave the file in place and proceed.

### Step 5.10: Worktree pollution check + commit (Augur side)

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git status --short
```

Expected: only the 2 modified generator files (and possibly regenerated `apps/dashboard/lib/hubs/generated.ts` if the build re-emitted it; if so, `git checkout HEAD -- apps/dashboard/lib/hubs/generated.ts` to discard the noise unless it represents a real diff).

Commit:

```bash
cd ~/Projects/Augur/.worktrees/track3b-dashboard-hub-routing && \
  git add apps/dashboard/scripts/skill-scripts/skill_generation/dashboard_generator.py \
          apps/dashboard/scripts/skill-scripts/skill_generation/comprehensive_dashboard_generator.py && \
  git commit -m "$(cat <<'EOF'
refactor(dashboard): retire {vertical/horizontal/factory} legacy taxonomy

Track 3b PR 5 — final cleanup. Deletes the legacy
{vertical: lifestyle, horizontal: hands, factory: agents} mapping
block from dashboard_generator.py and comprehensive_dashboard_generator.py.

The functions that branched on `layer in (vertical, horizontal, factory)`
now branch on the hub's `category` field (personal, knowledge, work,
system, creative, meta) read from config/system/hubs.yaml. Path
constructions previously hardcoded to `'lifestyle' / skill_name` now
use the `hub` parameter directly.

Audit grep across apps/dashboard/ and scripts/skill-scripts/ shows zero
hardcoded 'lifestyle'/'apple'/'obsidian'/'file-manager'/'ingest'/
'vertical'/'horizontal'/'factory' literals in production code outside
the documented allowlist:

Allowlist (intentional preservations, all carry inline `# Track 3b:`
comments):
- apps/dashboard/scripts/skill-scripts/scoring/user_research.py — Life-hub
  scoring weights are personal-OS-specific by design.
- (any other PR 4 preserved domain-logic sites)

Verification:
- /dev-build: succeeded (post-build verify clean)
- pytest tests/cli/test_hub_metadata.py tests/architecture/ skills/: passed
- Browser: home + 5 nav-visible hubs render correctly; `/browse?category=extensions-bundles`
  hub-picker enumerates from NAV_VISIBLE_HUBS; Calendar widget links
  to /life; zero console errors

ADR written: <get_adr_dir()>/track3b-dashboard-hub-routing.md
(committed separately in the ADR repo).

Track 3b complete. The 5 PRs in this track:
1. Infrastructure (config/system/hubs.yaml + scanner + generated.ts)
2. Dashboard production code (8 files)
3. Scanner templates (10 files)
4. Workflow tools (5 files; case-by-case)
5. This PR (cleanup + ADR)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If pre-commit hooks reject, do NOT use `--no-verify`. Fix and create a NEW commit.

---

## Done criteria

Track 3b is complete when:

1. `config/system/hubs.yaml` exists with all 6 hubs registered (life, brain, career, command, studio, adaptive).
2. `apps/dashboard/lib/hubs/generated.ts` is auto-generated and imported across the dashboard.
3. The 8 PR 2 files import from `@/lib/hubs/generated`.
4. The 10 PR 3 scanner templates consume `hubs_loader.resolve_default_hub_for_type` and emit hub-neutral code.
5. The 5 PR 4 workflow files have intentional domain logic preserved with `# Track 3b:` comments; templating sites migrated.
6. Audit grep across `apps/dashboard/` and `scripts/skill-scripts/` returns zero hardcoded `"lifestyle"` / `"apple"` / `"obsidian"` / `"file-manager"` / `"ingest"` / `"vertical"` / `"horizontal"` / `"factory"` literals in production code (allowlist documented in PR 5's commit body).
7. `tests/cli/test_hub_metadata.py` passes (orphan-free check + schema validation).
8. `/dev-build` succeeds and emits idempotent artifacts (post-build verify clean).
9. Browser verification on PRs 1, 2, 5: dashboard loads to interactive state across home + 5 nav-visible hubs + `/browse?category=extensions-bundles`; zero console errors; UI/UX review intact.
10. All 5 commits merged to `main`.
11. ADR `track3b-dashboard-hub-routing.md` written in `get_adr_dir()`.
