# DataResult & Seed Transparency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make seed data explicit across the entire pipeline — MCP tools return `source`/`vault_status` metadata, dashboard shows a badge, scanner enforces adoption.

**Architecture:** A shared `DataResult` helper in `src/lib/` replaces hand-rolled seed fallbacks in 14 MCP tool files. The dashboard `useBlockData` hook extracts metadata before unwrapping, and a `SeedBadge` component renders when `source === "seed"`. The e2e-pipeline scanner tracks migration progress.

**Tech Stack:** Python (dataclass, yaml, json), TypeScript/React (Next.js component, hook modification)

**Spec:** `docs/superpowers/specs/2026-03-25-data-result-seed-transparency-design.md`

---

### Task 1: DataResult helper — tests

**Files:**
- Create: `tests/unit/test_data_result.py`

- [ ] **Step 1: Write failing tests for all vault_status paths**

```python
"""Tests for src.lib.data_result."""
from __future__ import annotations
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from src.lib.data_result import DataResult, read_skill_data


@pytest.fixture
def skill_tree(tmp_path):
    """Create a minimal skill directory structure."""
    skill_root = tmp_path / "skills" / "test-skill"
    (skill_root / "scripts" / "mcp").mkdir(parents=True)
    caller = skill_root / "scripts" / "mcp" / "tools.py"
    caller.write_text("# stub")
    seed_dir = skill_root / "assets" / "seeds"
    seed_dir.mkdir(parents=True)
    return {"root": skill_root, "caller": caller, "seed_dir": seed_dir}


def test_vault_ok(skill_tree, tmp_path):
    vault_dir = tmp_path / "vault" / "test-skill"
    vault_dir.mkdir(parents=True)
    (vault_dir / "data.yaml").write_text("items:\n  - name: real\n")
    with patch("src.lib.data_result.get_own_data_dir", return_value=vault_dir):
        with patch("src.lib.data_result._find_skill_root", return_value=skill_tree["root"]):
            r = read_skill_data(skill_tree["caller"], "data.yaml", default={})
    assert r.source == "vault"
    assert r.vault_status == "ok"
    assert r.data["items"][0]["name"] == "real"


def test_vault_missing_dir_falls_to_seed(skill_tree, tmp_path):
    vault_dir = tmp_path / "vault" / "test-skill"  # does NOT exist
    (skill_tree["seed_dir"] / "data.yaml").write_text("items:\n  - name: seed\n")
    with patch("src.lib.data_result.get_own_data_dir", return_value=vault_dir):
        with patch("src.lib.data_result._find_skill_root", return_value=skill_tree["root"]):
            r = read_skill_data(skill_tree["caller"], "data.yaml", default={})
    assert r.source == "seed"
    assert r.vault_status == "missing_dir"
    assert r.data["items"][0]["name"] == "seed"


def test_vault_no_file_falls_to_seed(skill_tree, tmp_path):
    vault_dir = tmp_path / "vault" / "test-skill"
    vault_dir.mkdir(parents=True)  # dir exists, file doesn't
    (skill_tree["seed_dir"] / "data.yaml").write_text("items:\n  - name: seed\n")
    with patch("src.lib.data_result.get_own_data_dir", return_value=vault_dir):
        with patch("src.lib.data_result._find_skill_root", return_value=skill_tree["root"]):
            r = read_skill_data(skill_tree["caller"], "data.yaml", default={})
    assert r.source == "seed"
    assert r.vault_status == "no_file"


def test_vault_empty_file_falls_to_seed(skill_tree, tmp_path):
    vault_dir = tmp_path / "vault" / "test-skill"
    vault_dir.mkdir(parents=True)
    (vault_dir / "data.yaml").write_text("")  # empty
    (skill_tree["seed_dir"] / "data.yaml").write_text("items:\n  - name: seed\n")
    with patch("src.lib.data_result.get_own_data_dir", return_value=vault_dir):
        with patch("src.lib.data_result._find_skill_root", return_value=skill_tree["root"]):
            r = read_skill_data(skill_tree["caller"], "data.yaml", default={})
    assert r.source == "seed"
    assert r.vault_status == "empty_file"


def test_no_seed_returns_default(skill_tree, tmp_path):
    vault_dir = tmp_path / "vault" / "test-skill"  # no vault, no seed
    with patch("src.lib.data_result.get_own_data_dir", return_value=vault_dir):
        with patch("src.lib.data_result._find_skill_root", return_value=skill_tree["root"]):
            r = read_skill_data(skill_tree["caller"], "data.yaml", default=[])
    assert r.source == "default"
    assert r.data == []


def test_vault_takes_priority_over_seed(skill_tree, tmp_path):
    vault_dir = tmp_path / "vault" / "test-skill"
    vault_dir.mkdir(parents=True)
    (vault_dir / "data.yaml").write_text("items:\n  - name: real\n")
    (skill_tree["seed_dir"] / "data.yaml").write_text("items:\n  - name: seed\n")
    with patch("src.lib.data_result.get_own_data_dir", return_value=vault_dir):
        with patch("src.lib.data_result._find_skill_root", return_value=skill_tree["root"]):
            r = read_skill_data(skill_tree["caller"], "data.yaml", default={})
    assert r.source == "vault"
    assert r.data["items"][0]["name"] == "real"


def test_json_loader(skill_tree, tmp_path):
    vault_dir = tmp_path / "vault" / "test-skill"
    vault_dir.mkdir(parents=True)
    (vault_dir / "data.json").write_text(json.dumps({"count": 42}))
    with patch("src.lib.data_result.get_own_data_dir", return_value=vault_dir):
        with patch("src.lib.data_result._find_skill_root", return_value=skill_tree["root"]):
            r = read_skill_data(skill_tree["caller"], "data.json", default={}, loader="json")
    assert r.source == "vault"
    assert r.data["count"] == 42


def test_collection_loader(skill_tree, tmp_path):
    vault_dir = tmp_path / "vault" / "test-skill"
    coll_dir = vault_dir / "items"
    coll_dir.mkdir(parents=True)
    (coll_dir / "one.md").write_text("---\ntitle: One\n---\nBody\n")
    (coll_dir / "two.md").write_text("---\ntitle: Two\n---\nBody\n")
    with patch("src.lib.data_result.get_own_data_dir", return_value=vault_dir):
        with patch("src.lib.data_result._find_skill_root", return_value=skill_tree["root"]):
            r = read_skill_data(skill_tree["caller"], "items", default=[], loader="collection")
    assert r.source == "vault"
    assert len(r.data) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python -m pytest tests/unit/test_data_result.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.lib.data_result'`

- [ ] **Step 3: Commit test file**

```bash
git add tests/unit/test_data_result.py
git commit -m "test(data-result): add unit tests for DataResult helper"
```

---

### Task 2: DataResult helper — implementation

**Files:**
- Create: `src/lib/data_result.py`

- [ ] **Step 1: Implement `DataResult` and `read_skill_data`**

```python
"""Vault-first data loader with seed fallback and source diagnostics.

Replaces hand-rolled seed fallback patterns in MCP tool files.
Tools call read_skill_data() which returns a DataResult envelope
with source tracking ("vault"/"seed"/"default") and vault path
diagnosis so the dashboard can badge seed data and developers
can debug missing-data issues.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.lib.frontmatter_utils import load_collection
from src.lib.skill_paths import _find_skill_root, get_own_data_dir

logger = logging.getLogger(__name__)


@dataclass
class DataResult:
    """Envelope for skill data with source tracking and vault diagnostics."""
    data: Any
    source: str                    # "vault" | "seed" | "default"
    vault_status: str              # "ok" | "missing_dir" | "no_file" | "empty_file"
    vault_path: str | None = None
    seed_path: str | None = None


def read_skill_data(
    caller_file: str | Path,
    filename: str,
    default: Any = None,
    *,
    loader: str = "yaml",
) -> DataResult:
    """Load skill data vault-first with seed fallback and diagnostics.

    Args:
        caller_file: __file__ of the calling MCP tool module.
        filename: Relative path within the skill's data dir (e.g. "recipes.yaml",
                  "tasks" for a collection directory).
        default: Value to return when neither vault nor seed has data.
        loader: "yaml", "json", or "collection".

    Returns:
        DataResult with data, source, and vault diagnostic fields.
    """
    vault_dir = get_own_data_dir(caller_file)
    vault_path = vault_dir / filename
    skill_root = _find_skill_root(caller_file)
    seed_path = skill_root / "assets" / "seeds" / filename

    # ── Try vault first ──────────────────────────────────────────
    vault_status = _diagnose_vault(vault_path, loader)
    if vault_status == "ok":
        data = _load(vault_path, loader, default)
        if data is not None and data != default:
            return DataResult(
                data=data,
                source="vault",
                vault_status="ok",
                vault_path=str(vault_path),
            )
        # Loaded but empty/falsy — treat as empty_file
        vault_status = "empty_file"

    # ── Fallback to seed ─────────────────────────────────────────
    if seed_path.exists() if seed_path.is_file() or (loader == "collection" and seed_path.is_dir()) else False:
        data = _load(seed_path, loader, default)
        if data is not None:
            return DataResult(
                data=data,
                source="seed",
                vault_status=vault_status,
                vault_path=str(vault_path),
                seed_path=str(seed_path),
            )

    # ── Default ──────────────────────────────────────────────────
    return DataResult(
        data=default,
        source="default",
        vault_status=vault_status,
        vault_path=str(vault_path),
    )


def _diagnose_vault(vault_path: Path, loader: str) -> str:
    """Diagnose why vault data might be missing."""
    vault_dir = vault_path.parent if loader != "collection" else vault_path.parent
    # For collection loader, vault_path IS the directory
    check_path = vault_path if loader != "collection" else vault_path

    if loader == "collection":
        if not vault_path.parent.is_dir():
            return "missing_dir"
        if not vault_path.is_dir():
            return "no_file"
        if not any(vault_path.iterdir()):
            return "empty_file"
        return "ok"

    if not vault_path.parent.is_dir():
        return "missing_dir"
    if not vault_path.exists():
        return "no_file"
    if vault_path.stat().st_size == 0:
        return "empty_file"
    return "ok"


def _load(path: Path, loader: str, default: Any) -> Any:
    """Load data from path using the specified loader."""
    try:
        if loader == "yaml":
            return yaml.safe_load(path.read_text(encoding="utf-8")) or default
        elif loader == "json":
            return json.loads(path.read_text(encoding="utf-8"))
        elif loader == "collection":
            return load_collection(path)
        return default
    except Exception as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return default
```

- [ ] **Step 2: Run tests**

Run: `PYTHONPATH=. python -m pytest tests/unit/test_data_result.py -v`
Expected: All 8 tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/lib/data_result.py
git commit -m "feat(data-result): add DataResult helper with vault diagnostics"
```

---

### Task 3: Migrate skills — batch 1 (shared helpers: lifestyle, reading-list, career)

**Files:**
- Modify: `skills/lifestyle/scripts/mcp/_shared.py`
- Modify: `skills/reading-list/scripts/mcp/__init__.py`
- Modify: `skills/career/scripts/mcp/_shared.py`

These three skills have shared `_read_yaml()` helpers that serve multiple tools. Migrating the helper migrates all callers at once.

- [ ] **Step 1: Migrate lifestyle `_read_yaml()`**

Read `skills/lifestyle/scripts/mcp/_shared.py`, find `_read_yaml` function. Replace the seed fallback logic with `read_skill_data`. The helper's callers pass a full path — change to pass just the filename.

- [ ] **Step 2: Migrate reading-list `_read_yaml_file()`**

Read `skills/reading-list/scripts/mcp/__init__.py`, find `_read_yaml_file`. Same pattern as lifestyle.

- [ ] **Step 3: Migrate career `_shared.py`**

Read `skills/career/scripts/mcp/_shared.py`, find `_seed_dir()` usage. Replace with `read_skill_data`.

- [ ] **Step 4: Run scanner to verify**

Run: `PYTHONPATH=. python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ep', 'skills/auto-e2e-pipeline/scripts/e2e_pipeline.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
from src.lib.ops_protocol import OpsContext
for i in mod._detect_seed_fallbacks(mod.get_project_root()):
    if i.get('skill') in ('lifestyle', 'reading-list', 'career'):
        print(i['detail'])
print('(should be empty)')
"`
Expected: No output for those 3 skills

- [ ] **Step 5: Commit**

```bash
git add skills/lifestyle/scripts/mcp/_shared.py skills/reading-list/scripts/mcp/__init__.py skills/career/scripts/mcp/_shared.py
git commit -m "refactor: migrate lifestyle, reading-list, career to DataResult"
```

---

### Task 4: Migrate skills — batch 2 (inline fallbacks: apple, google-workspace, evolve, growth, daemon)

**Files:**
- Modify: `skills/apple/scripts/mcp/tools_notes.py`
- Modify: `skills/google-workspace/scripts/mcp/_tasks.py`
- Modify: `skills/google-workspace/scripts/mcp/_chat.py`
- Modify: `skills/evolve/scripts/mcp/__init__.py`
- Modify: `skills/growth/scripts/mcp/__init__.py`
- Modify: `skills/daemon/scripts/mcp/_plugin_events.py`

These have inline seed fallback blocks inside tool functions. Replace each with `read_skill_data`.

For `apple` and `google-workspace`: the fallback fires after an external API call, not a vault read. Use `read_skill_data` only for the seed loading part. Keep the API call as-is.

- [ ] **Step 1: Migrate apple `tools_notes.py`** (~line 76-84)
- [ ] **Step 2: Migrate google-workspace `_tasks.py`** (~line 59-67)
- [ ] **Step 3: Migrate google-workspace `_chat.py`** (~line 90-115)
- [ ] **Step 4: Migrate evolve `__init__.py`** (~line 104-111)
- [ ] **Step 5: Migrate growth `__init__.py`** (~line 231)
- [ ] **Step 6: Migrate daemon `_plugin_events.py`** (~line 97)
- [ ] **Step 7: Run scanner, verify 0 hits for these skills**
- [ ] **Step 8: Commit**

```bash
git add skills/apple/scripts/mcp/tools_notes.py skills/google-workspace/scripts/mcp/_tasks.py skills/google-workspace/scripts/mcp/_chat.py skills/evolve/scripts/mcp/__init__.py skills/growth/scripts/mcp/__init__.py skills/daemon/scripts/mcp/_plugin_events.py
git commit -m "refactor: migrate apple, google-workspace, evolve, growth, daemon to DataResult"
```

---

### Task 5: Migrate skills — batch 3 (remaining: health, smb-client-template, knowledge, career/tools_jobs)

**Files:**
- Modify: `skills/health/scripts/mcp/_shared.py`
- Modify: `skills/smb-client-template/scripts/mcp/tools_content.py`
- Modify: `skills/smb-client-template/scripts/mcp/tools_knowledge.py`
- Modify: `skills/knowledge/scripts/mcp/__init__.py`
- Modify: `skills/career/scripts/mcp/tools_jobs.py`

`health` is the special case — 3 separate `read_skill_data` calls for symptoms, medications, history.

- [ ] **Step 1: Migrate health `_shared.py`** (per-section calls)
- [ ] **Step 2: Migrate smb-client-template `tools_content.py`** (~line 135-144)
- [ ] **Step 3: Migrate smb-client-template `tools_knowledge.py`** (~line 294)
- [ ] **Step 4: Migrate knowledge `__init__.py`** (~line 170)
- [ ] **Step 5: Migrate career `tools_jobs.py`** (~line 351, the `_seed_dir()` usage in `get_companies`)
- [ ] **Step 6: Run full scanner — expect 0 seed_fallback issues**

Run: `PYTHONPATH=. python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ep', 'skills/auto-e2e-pipeline/scripts/e2e_pipeline.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
issues = mod._detect_seed_fallbacks(mod.get_project_root())
print(f'seed_fallback issues: {len(issues)}')
for i in issues: print(f'  {i[\"detail\"]}')
"`
Expected: `seed_fallback issues: 0`

- [ ] **Step 7: Commit**

```bash
git add skills/health/scripts/mcp/_shared.py skills/smb-client-template/scripts/mcp/tools_content.py skills/smb-client-template/scripts/mcp/tools_knowledge.py skills/knowledge/scripts/mcp/__init__.py skills/career/scripts/mcp/tools_jobs.py
git commit -m "refactor: migrate health, smb-client-template, knowledge, career/jobs to DataResult"
```

---

### Task 6: Scanner enforcement — adoption tracking

**Files:**
- Modify: `skills/auto-e2e-pipeline/scripts/e2e_pipeline.py`

- [ ] **Step 1: Update `_detect_seed_fallbacks` to also track `read_skill_data` adoption**

After the existing legacy detection loop, add a second pass that scans for `from src.lib.data_result import` or `read_skill_data(`. Count as migrated. Report both counts.

- [ ] **Step 2: Improve scanner regex to catch embedded helpers**

The current regex misses `reading-list`, `lifestyle`, and `career/_shared.py` patterns. Add pattern: function contains `_seed_dir()` call regardless of surrounding condition keywords.

- [ ] **Step 3: Run scanner to verify 0 legacy, N migrated**

Run: `PYTHONPATH=. python skills/daemon/scripts/adaptive_loop_executor.py --run testing 2>&1 | grep e2e-pipeline`
Expected: `auto-e2e-pipeline` shows clean or reduced issue count

- [ ] **Step 4: Commit**

```bash
git add skills/auto-e2e-pipeline/scripts/e2e_pipeline.py
git commit -m "feat(e2e-pipeline): add DataResult adoption tracking to seed fallback scanner"
```

---

### Task 7: Pulse endpoint cleanup

**Files:**
- Modify: `apps/dashboard/app/api/settings/layout/pulse/route.ts`

- [ ] **Step 1: Read the pulse route and identify dead endpoints**

Read `apps/dashboard/app/api/settings/layout/pulse/route.ts`. Find `QUICK_ENDPOINTS` (~line 15) and `DEEP_ENDPOINTS` (~line 23).

- [ ] **Step 2: Remove dead endpoints from both arrays**

Remove these 8:
- `/api/mcp/summary`
- `/api/bridge/summary?hub=brain`
- `/api/config/llm`
- `/api/agents/rules`
- `/api/agents/weights`
- `/api/bridge/connections?hub=brain`
- `/api/registry?page=/brain`
- `/api/workflows?hub=brain&page=/brain`

Keep only endpoints with actual route.ts files: `/api/activity/summary`, `/api/agents/available?mode=api`.

- [ ] **Step 3: Run scanner to verify 0 dead pulse endpoints**

Run: `PYTHONPATH=. python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ep', 'skills/auto-e2e-pipeline/scripts/e2e_pipeline.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
issues = mod._detect_dead_pulse_endpoints(mod.get_project_root())
print(f'dead pulse endpoints: {len(issues)}')
"`
Expected: `dead pulse endpoints: 0`

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/app/api/settings/layout/pulse/route.ts
git commit -m "fix(pulse): remove 8 dead probe endpoints"
```

---

### Task 8: useBlockData metadata sideband

**Files:**
- Modify: `apps/dashboard/lib/blocks/useBlockData.ts`

- [ ] **Step 1: Read the file, locate `unwrapToolData` and return shape**

Read `apps/dashboard/lib/blocks/useBlockData.ts`. Find where raw MCP response is received and unwrapped (~line 44-100 for unwrap, ~line 139-179 for hook).

- [ ] **Step 2: Extract metadata before unwrap**

Before the `unwrapToolData` call, extract `source` and `vault_status` from the raw response. Add a `meta` field to the return type.

```typescript
// Add to the return interface
interface BlockDataMeta {
  source?: string;        // "vault" | "seed" | "default"
  vaultStatus?: string;   // "ok" | "missing_dir" | "no_file" | "empty_file"
}

// In the hook, before unwrap:
const rawObj = typeof raw === 'object' && raw !== null ? raw as Record<string, unknown> : {};
const meta: BlockDataMeta = {
  source: rawObj.source as string | undefined,
  vaultStatus: rawObj.vault_status as string | undefined,
};
```

Return `meta` alongside `data` in the hook result.

- [ ] **Step 3: Verify dashboard builds**

Run: `pnpm --filter dashboard build`
Expected: Build succeeds (meta is additive, existing consumers ignore it)

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/lib/blocks/useBlockData.ts
git commit -m "feat(blocks): extract source/vault_status metadata before unwrap"
```

---

### Task 9: SeedBadge component + BlockRenderer integration

**Files:**
- Create: `apps/dashboard/components/ui/SeedBadge.tsx`
- Modify: `apps/dashboard/components/blocks/BlockRenderer.tsx`

- [ ] **Step 1: Create SeedBadge component**

```tsx
/**
 * Shows a subtle indicator when block data comes from seed/demo files
 * rather than the user's vault.
 */
export function SeedBadge({ source, vaultStatus }: {
  source?: string;
  vaultStatus?: string;
}) {
  if (source !== "seed") return null;

  const hint = vaultStatus === "missing_dir"
    ? " — vault directory not found"
    : vaultStatus === "no_file"
    ? " — no data file yet"
    : "";

  return (
    <div className="text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded inline-flex items-center gap-1">
      <span className="opacity-60">Sample data</span>
      {hint && <span className="opacity-40">{hint}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Integrate into BlockRenderer**

Read `apps/dashboard/components/blocks/BlockRenderer.tsx`. Find where blocks are rendered (~line 116-149). Pass `meta` from `useBlockData` and render `<SeedBadge>` above or below the block content.

- [ ] **Step 3: Verify dashboard builds**

Run: `pnpm --filter dashboard build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/components/ui/SeedBadge.tsx apps/dashboard/components/blocks/BlockRenderer.tsx
git commit -m "feat(dashboard): add SeedBadge component for seed data visibility"
```

---

### Task 10: Final verification

- [ ] **Step 1: Run full testing loop**

Run: `PYTHONPATH=. python skills/daemon/scripts/adaptive_loop_executor.py --run testing 2>&1 | tail -20`
Expected: `auto-e2e-pipeline` shows reduced issues (ideally 0 seed_fallback, 0 pulse_dead_endpoint)

- [ ] **Step 2: Run full e2e-actions scan**

Run: `PYTHONPATH=. python skills/daemon/scripts/adaptive_loop_executor.py --run testing 2>&1 | grep e2e`
Expected: Both `auto-e2e-actions` and `auto-e2e-pipeline` clean or report-only

- [ ] **Step 3: Final commit with summary**

```bash
git add -u
git commit -m "chore: DataResult seed transparency migration complete — 14 files migrated, 0 legacy fallbacks"
```
