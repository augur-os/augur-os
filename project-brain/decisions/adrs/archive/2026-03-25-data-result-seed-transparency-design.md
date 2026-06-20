# Data Result & Seed Transparency

**Date:** 2026-03-25
**Status:** Draft
**Scope:** Framework helper, 13 skill file migrations, scanner enforcement, pulse cleanup, dashboard badge

## Problem

MCP tools silently return seed/demo data when vault data is missing. The dashboard and user cannot distinguish real data from demo data. Additionally, when vault returns empty, there's no diagnosis of WHY — wrong path, missing directory, or genuinely no data yet.

Secondary: the pulse health check probes 8 API endpoints that don't exist, polluting health status with false 404s.

## Design

### 1. DataResult Helper

**New file:** `src/lib/data_result.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass
class DataResult:
    """Envelope for skill data with source tracking and vault diagnostics."""
    data: Any
    source: str                  # "vault" | "seed" | "default"
    vault_status: str            # "ok" | "missing_dir" | "no_file" | "empty_file"
    vault_path: str | None = None  # Resolved vault path that was checked
    seed_path: str | None = None   # Seed path if seed was used
```

**Main entry point:**

```python
def read_skill_data(
    caller_file: str | Path,
    filename: str,
    default: Any = None,
    *,
    loader: str = "yaml",       # "yaml" | "json" | "collection"
) -> DataResult:
```

**Skill root resolution:** Uses `_find_skill_root(caller_file)` from `src/lib/skill_paths.py` to locate the skill directory for seed path resolution: `{skill_root}/assets/seeds/{filename}`.

**Logic flow:**

1. Resolve vault path: `get_own_data_dir(caller_file) / filename`
2. Diagnose vault state:
   - Vault dir doesn't exist → `vault_status="missing_dir"`
   - Vault dir exists, file/dir missing → `vault_status="no_file"`
   - Vault file exists, empty content → `vault_status="empty_file"`
   - Vault data loaded → `source="vault"`, `vault_status="ok"`, return
3. Fallback to seed:
   - Resolve seed path: `_find_skill_root(caller_file) / "assets" / "seeds" / filename`
   - Seed exists → load, `source="seed"`
   - No seed → `source="default"`, return default value
4. Return `DataResult` envelope

**Loader variants:**

| Loader | Reads | Returns |
|--------|-------|---------|
| `"yaml"` | `.yaml`/`.yml` file | Parsed YAML (dict or list) |
| `"json"` | `.json` file | Parsed JSON |
| `"collection"` | Directory of `.md` files | List of frontmatter dicts via `load_collection()` |

**Collection loader semantics:** Vault-first, all-or-nothing. If the vault directory exists and has files, ALL data comes from vault (`source="vault"`). Seed data is only used when the vault directory is entirely empty or missing. No per-item merging — that would make `source` ambiguous. Skills needing per-section control (see health special case below) make multiple `read_skill_data` calls.

### 2. Skill Migration (13 files across 11 skills)

Each skill's shared helper gets replaced with `read_skill_data()`. The MCP tool serializes the `source` and `vault_status` fields into the JSON response.

**Files to migrate:**

| Skill | File | Current Pattern | Scanner detects? |
|-------|------|-----------------|-----------------|
| apple | `tools_notes.py` | Inline seed fallback after empty AppleNotesIO | Yes |
| career | `tools_jobs.py` | `_seed_dir()` fallback in `get_jobs()` | Yes |
| career | `_shared.py` | `_seed_dir()` helper used by other tools | No (migrate anyway) |
| google-workspace | `_tasks.py` | Inline seed fallback on empty API response | Yes |
| google-workspace | `_chat.py` | Inline seed fallback on API error AND empty | Yes |
| evolve | `__init__.py` | Seed fallback when state dir empty | Yes |
| reading-list | `__init__.py` | Silent fallback in `_read_yaml_file()` helper | No (migrate anyway) |
| lifestyle | `_shared.py` | Silent fallback in `_read_yaml()` helper | No (migrate anyway) |
| health | `_shared.py` | Per-section seed fallback (see special case) | Yes |
| growth | `__init__.py` | Seed fallback on empty state | Yes |
| smb-client-template | `tools_content.py` | Seed fallback when vault dir missing | Yes |
| smb-client-template | `tools_knowledge.py` | Seed fallback when vault dir missing | Yes |
| daemon | `_plugin_events.py` | Seed fallback on empty events | Yes |
| knowledge | `__init__.py` | Seed fallback on empty data | Yes |

Note: 3 files (career `_shared.py`, reading-list, lifestyle) are not caught by the current scanner regex because the fallback condition is embedded inside the helper function. They need migration regardless. The scanner regex should be updated post-migration to catch these patterns too.

**Migration pattern (before/after):**

Before:
```python
def _read_yaml(file_path: Path, default):
    if file_path.exists():
        return yaml.safe_load(file_path.read_text()) or default
    seed_path = _seed_dir() / rel
    if seed_path.exists():
        return yaml.safe_load(seed_path.read_text()) or default
    return default
```

After:
```python
from src.lib.data_result import read_skill_data

def _load_data(filename: str, default=None) -> DataResult:
    return read_skill_data(__file__, filename, default, loader="yaml")
```

MCP tool usage:
```python
result = _load_data("recipes.yaml", default=[])
return json.dumps({
    "success": True,
    "data": result.data,
    "source": result.source,
    "vault_status": result.vault_status,
})
```

**Special cases:**

- `apple` and `google-workspace`: These fallback after an external API call fails, not after vault file read. The pattern is: API call → empty → seed. Migration wraps only the seed part — the API call stays as-is, but when it returns empty and we fall to seed, the tool response carries `source: "seed"`.
- `lifestyle` and `reading-list`: Their `_read_yaml()` is used by multiple tools. Migrating the helper migrates all callers at once.
- `health`: Loads 3 sub-collections (symptoms, medications, history) from vault, then selectively fills each empty section from seed. This requires 3 separate `read_skill_data(__file__, "symptoms", ...)` calls — one per sub-collection. Each section carries its own `source` field. The tool response aggregates: `"source": "vault"` if all sections from vault, `"source": "mixed"` if some vault + some seed, `"source": "seed"` if all from seed.

### 3. Scanner Enforcement

Extend the existing `auto-e2e-pipeline` d0 `seed_fallback` check with **adoption tracking**:

- Current d0 check already detects legacy seed patterns via regex
- Add a second pass: scan for `read_skill_data` or `from src.lib.data_result import` — count as migrated
- Report: `{migrated: N, legacy: M, total: N+M}`
- After all 14 files are migrated, the legacy count should be 0
- Update the scanner regex to also catch the `reading-list`, `lifestyle`, and `career/_shared.py` patterns that the current regex misses (embedded fallback condition inside helper functions)
- Evolution gap: when legacy hits 0, suggest promoting to d2 (runtime validation that `source` field is present in responses)

### 4. Pulse Endpoint Cleanup

Remove 8 dead endpoints from the pulse route probe lists:

```
/api/agents/rules
/api/agents/weights
/api/bridge/connections
/api/bridge/summary
/api/config/llm
/api/mcp/summary
/api/registry
/api/workflows
```

These features don't exist. If built later, endpoints get added back.

**File:** `apps/dashboard/app/api/settings/layout/pulse/route.ts`

### 5. Dashboard SeedBadge Component

**New file:** `apps/dashboard/components/ui/SeedBadge.tsx` (framework layer, `@/` alias)

`SeedBadge` is a generic UI primitive (any block from any skill can return seed data), so it belongs in the framework layer per ADR-490: `@/` never imports `@skill/`.

```tsx
export function SeedBadge({ source, vaultStatus }: {
  source?: string;
  vaultStatus?: string;
}) {
  if (source !== "seed") return null;
  return (
    <div className="text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded">
      Sample data
      {vaultStatus === "missing_dir" && " — vault directory not found"}
      {vaultStatus === "no_file" && " — no data file yet"}
    </div>
  );
}
```

### 6. useBlockData Metadata Sideband

**Problem:** `useBlockData` runs `unwrapToolData()` which strips the response envelope, discarding `source` and `vault_status` before they reach the block renderer.

**Fix:** Modify `useBlockData` (at `apps/dashboard/lib/blocks/useBlockData.ts`) to extract metadata fields BEFORE unwrapping, and return them as a separate sideband:

```typescript
// Before unwrap: extract metadata
const raw = response;
const meta = {
  source: raw?.source,           // "vault" | "seed" | "default" | undefined
  vaultStatus: raw?.vault_status, // diagnosis string | undefined
};
// Then unwrap as before
const data = unwrapToolData(raw);
return { data, meta };
```

The `BlockRenderer` then passes `meta` to `<SeedBadge>`:

```tsx
<SeedBadge source={meta?.source} vaultStatus={meta?.vaultStatus} />
```

This is additive — `meta` is `undefined` for tools not yet migrated, and `SeedBadge` renders nothing when `source !== "seed"`. No breakage for existing blocks.

## Build Order

1. `src/lib/data_result.py` — the framework helper + unit tests
2. Migrate 14 skill files — mechanical, each testable independently
3. Scanner enforcement — update regex, add adoption tracking
4. Pulse cleanup — independent, can parallel with 2-3
5. `useBlockData` metadata sideband — extract `source`/`vault_status` before unwrap
6. `SeedBadge` component — depends on 5

## Testing

**Unit tests** (`skills/auto-e2e-pipeline/augur/tests/test_data_result.py`):
- `test_vault_ok` — vault file exists with data → `source="vault"`, `vault_status="ok"`
- `test_vault_missing_dir` — vault dir doesn't exist → `source="seed"`, `vault_status="missing_dir"`
- `test_vault_no_file` — vault dir exists, file missing → `source="seed"`, `vault_status="no_file"`
- `test_vault_empty_file` — vault file exists, empty content → `source="seed"`, `vault_status="empty_file"`
- `test_no_seed` — vault empty, no seed file → `source="default"`, returns default value
- `test_collection_loader` — vault directory with .md files → returns list of frontmatter dicts
- `test_vault_takes_priority` — both vault and seed exist → always returns vault data
- `test_json_loader` — `.json` file loading works

**Integration test** (one migrated skill):
- Call a migrated MCP tool via the test harness
- Verify response JSON contains `source` and `vault_status` fields
- Verify `source="seed"` when vault is empty, `source="vault"` when vault has data

## Success Criteria

- `auto-e2e-pipeline` d0 reports 0 `seed_fallback` issues (all 14 files migrated)
- `auto-e2e-pipeline` d0 reports 0 `pulse_dead_endpoint` issues
- Every MCP tool that loads skill data returns `source` field in response
- Dashboard shows "Sample data" badge when `source === "seed"`
- Vault path diagnosis (`vault_status`) visible in tool responses for debugging
- All unit tests pass for `DataResult` helper

## Not In Scope

- Changing `get_own_data_dir()` or vault path resolution
- Migrating tools that don't have seed fallback (they already return empty correctly)
- Building the full empty-state dashboard UX (future work, builds on this)
