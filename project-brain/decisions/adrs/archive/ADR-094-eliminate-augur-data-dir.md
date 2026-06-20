---
status: Implemented
date: '2026-02-13'
deciders:
- Gur Sannikov
related:
- ADR-018 (plugin self-containment)
- ADR-024 (MCP package decoupling)
hub: null
tags:
- eliminate
- augur
- data
- dir
- plugin
superseded_by: null
---

# ADR-094: Eliminate AUGUR_DATA_DIR — Plugin-Colocated Data Model

**Supersedes**: Completes ADR-087 (data-folder-elimination), ADR-083 (plugin-data-colocation)

## Context

`AUGUR_DATA_DIR` is a zombie concept. It was introduced as "the path to user data" when data lived in a single `data/` directory. Two refactors later:

- **ADR-083** moved plugin data into `plugins/{bundle}/skills/{skill}/data/`
- **ADR-087** moved config to `config/`, runtime to `runtime/`, memory to `docs/memory/`, and deleted `data/`

After these refactors, `AUGUR_DATA_DIR` has no coherent meaning. In practice:

| Config | Current Value | What It Actually Means |
|--------|---------------|----------------------|
| Claude Desktop | `.../Augur` (just fixed) | Project root |
| Claude Code | `.../Augur/data` | Non-existent directory |
| Cursor | `.../Augur/data` | Non-existent directory |
| Gemini | `.../Augur/data` | Non-existent directory |
| `scripts/augur` | `$PROJECT_ROOT/data` | Non-existent directory |
| `scripts/augur-mcp` | `$PROJECT_ROOT/data` | Non-existent directory |

The MCP server's `config.py` treats `data_dir` as its primary path concept, then builds `config_dir = data_dir / "config"` and `runtime_dir = data_dir / "runtime"` from it. This only works when `data_dir` equals the project root — making it semantically identical to `AUGUR_ROOT`, which already exists.

**Problems:**

1. **Semantic lie**: `AUGUR_DATA_DIR` implies a data directory exists. It doesn't. There is no single "data" location — data is distributed across 27 plugin `data/` folders.
2. **4 of 6 IDE configs point to a non-existent path** (`Augur/data`). The MCP server only works because `_get_default_data_dir()` has a fallback to detect project root from file location.
3. **Two env vars for the same thing**: `AUGUR_ROOT` and `AUGUR_DATA_DIR` both mean "project root" post-ADR-087. Having both creates confusion about which to use.
4. **Legacy fallbacks proliferate**: `paths.ts` has `resolveUserDataBase()` with fallback chains, `config.py` has `data_dir` → `project_root` indirection, `AUGUR_DATA` alias still exists.
5. **620 references across 237 files** use `AUGUR_DATA_DIR`, `AUGUR_DATA`, `get_user_data_base()`, or `data_dir` — all doing the same thing as `AUGUR_ROOT`.

## Decision

Eliminate `AUGUR_DATA_DIR` entirely. Standardize on `AUGUR_ROOT` as the single env var for project location. Remove all fallback chains.

### 1. Delete `AUGUR_DATA_DIR` and `AUGUR_DATA` env vars

**No fallback. No alias. No deprecation period.** Pre-launch, we don't maintain backward compatibility.

All consumers that read `AUGUR_DATA_DIR` switch to `AUGUR_ROOT`. The mapping is direct:

| Before | After |
|--------|-------|
| `os.environ.get("AUGUR_DATA_DIR")` | `os.environ.get("AUGUR_ROOT")` |
| `process.env.AUGUR_DATA_DIR` | `process.env.AUGUR_ROOT` |
| `AUGUR_DATA` (alias) | Deleted |
| `USER_DATA_BASE` (legacy alias) | Deleted |

### 2. Refactor `MCPConfig` (`src/mcp/augur_mcp/config.py`)

Replace `data_dir` with `project_root` as the primary concept:

```python
# Before
@dataclass
class MCPConfig:
    data_dir: Path           # "user data directory" (actually project root)
    plugins_dir: Path
    project_root: Path | None  # redundant with data_dir

# After
@dataclass
class MCPConfig:
    project_root: Path       # Single source of truth
    plugins_dir: Path
```

Derived paths become direct:

```python
# Before
def get_config_data_dir(): return config.data_dir / "config"
def get_user_data_base(): return config.data_dir

# After
def get_config_dir(): return config.project_root / "config"
def get_runtime_dir(): return config.project_root / "runtime"
def get_memory_dir(): return config.project_root / "docs" / "memory"
# get_user_data_base() → DELETED
# get_config_data_dir() → renamed to get_config_dir()
```

The `_get_default_data_dir()` function becomes `_get_project_root()`:

```python
def _get_project_root() -> Path:
    env_path = os.environ.get("AUGUR_ROOT")
    if env_path:
        path = Path(os.path.expanduser(env_path)).resolve()
        if not path.exists():
            raise FileNotFoundError(f"AUGUR_ROOT does not exist: {path}")
        return path
    # Detect from file location (5 levels up from config.py)
    detected = Path(__file__).parent.parent.parent.parent.parent
    if (detected / "plugins").exists():
        return detected
    raise FileNotFoundError("Set AUGUR_ROOT environment variable")
```

### 3. Refactor `paths.ts` (`src/dashboard/lib/paths.ts`)

Delete `resolveUserDataBase()`, `AUGUR_DATA_DIR` export, and all legacy fallbacks:

```typescript
// Before
export const AUGUR_DATA_DIR = resolveUserDataBase();  // compat shim
export const AUGUR_CONFIG_DIR = path.join(AUGUR_ROOT, 'config');

// After
export const AUGUR_CONFIG_DIR = path.join(AUGUR_ROOT, 'config');
export const AUGUR_RUNTIME_DIR = path.join(AUGUR_ROOT, 'runtime');
export const AUGUR_MEMORY_DIR = path.join(AUGUR_ROOT, 'docs', 'memory');
// AUGUR_DATA_DIR → DELETED
```

All consumers that import `AUGUR_DATA_DIR` switch to the specific path they actually need (`AUGUR_CONFIG_DIR`, `AUGUR_ROOT`, etc.).

### 4. Fix all IDE and MCP configs

Every config file that sets `AUGUR_DATA_DIR` drops it and ensures `AUGUR_ROOT` is set:

| File | Change |
|------|--------|
| `.claude/mcp.json` | Remove `AUGUR_DATA_DIR`, keep `AUGUR_ROOT` |
| `.cursor/mcp.json` | Remove `AUGUR_DATA_DIR`, keep `AUGUR_ROOT` |
| `.gemini/settings.json` | Remove `AUGUR_DATA_DIR`, keep `AUGUR_ROOT` |
| `~/Library/Application Support/Claude/claude_desktop_config.json` | Remove `AUGUR_DATA_DIR`, add `AUGUR_ROOT` |
| `src/config/mcp_config.template.json` | Remove `AUGUR_DATA_DIR`, use `AUGUR_ROOT` |
| `scripts/augur` | Remove `AUGUR_DATA_DIR` export |
| `scripts/augur-mcp` | Remove `AUGUR_DATA_DIR` and `AUGUR_DATA` exports |
| `scripts/install.sh` | Remove `AUGUR_DATA_DIR` references |
| `scripts/configure_mcp.py` | Remove `AUGUR_DATA_DIR` from generated configs |

### 5. Update plugin scripts

Plugin scripts that construct paths via `AUGUR_DATA_DIR` switch to `AUGUR_ROOT` or use `get_project_root()`:

```python
# Before (scattered across ~112 plugin files)
env = os.environ.get("AUGUR_DATA") or os.environ.get("AUGUR_DATA_DIR")
base = Path(env)
config_path = base / "config" / "system" / "config.yaml"

# After
from augur_mcp.config import get_config_dir  # or get_project_root
config_path = get_config_dir() / "system" / "config.yaml"
```

For scripts that can't import `augur_mcp` (standalone execution), use `AUGUR_ROOT` directly:

```python
root = Path(os.environ.get("AUGUR_ROOT", Path(__file__).resolve().parents[N]))
```

### 6. Plugin data path model (codifying what already exists)

Each plugin owns its data under `plugins/{bundle}/skills/{skill}/data/`. This is already the reality (ADR-083). This ADR makes it the *only* model — no global data directory concept exists anymore.

```
plugins/career/skills/career/augur/       → Career job data
plugins/finance/skills/finance/augur/      → Finance transactions
plugins/ai/skills/knowledge/data/ → RAG indexes
plugins/ai/skills/ai_bridge/augur/ → IDE configs, registry
```

Resolution is via `dashboard.yaml`'s `data_dir` field (TypeScript) or `get_skill_data_dir()` (Python). No fallback to a global directory.

## Consequences

### Positive

- **One env var**: `AUGUR_ROOT` is the only location concept. No aliases, no fallbacks.
- **No semantic lies**: There is no "data directory" because data is distributed. The code reflects reality.
- **Broken configs fail loudly**: If `AUGUR_ROOT` is wrong, the server errors immediately instead of silently falling back.
- **~620 lines of fallback/alias code deleted**: Simpler codepaths everywhere.

### Negative

- **237 files touched**: Large refactor. Must be executed carefully with parallel agents.
- **Every IDE config needs updating**: Claude Code, Cursor, Gemini, Claude Desktop, plus template.
- **Plugin scripts that run standalone** need `AUGUR_ROOT` in their environment or robust parent-dir detection.

### Neutral

- Plugin data layout unchanged — this ADR deletes the global concept, not the plugin-level one.
- `runtime/`, `config/`, `docs/memory/` paths unchanged — only how they're derived changes.

## Implementation Order

```
Phase 1: Config Core (PIPELINE)
├── 1.1: Refactor MCPConfig — replace data_dir with project_root
├── 1.2: Rename get_config_data_dir → get_config_dir, delete get_user_data_base
└── 1.3: Refactor paths.ts — delete resolveUserDataBase, AUGUR_DATA_DIR

Phase 2: IDE Configs (PARALLEL)
├── 2.1: Fix .claude/mcp.json, .cursor/mcp.json, .gemini/settings.json
├── 2.2: Fix claude_desktop_config.json
├── 2.3: Fix scripts/augur, scripts/augur-mcp, scripts/install.*
└── 2.4: Fix src/config/mcp_config.template.json, scripts/configure_mcp.py

Phase 3: MCP Package Consumers (PARALLEL)
├── 3.1: Update augur_mcp/ internal imports (25 files, ~161 refs)
└── 3.2: Update context_manager.py — get_user_data_base → get_project_root

Phase 4: Dashboard Consumers (PARALLEL)
├── 4.1: Update src/dashboard/ imports — AUGUR_DATA_DIR → AUGUR_ROOT/AUGUR_CONFIG_DIR (~95 files)
└── 4.2: Update src/ non-dashboard files (~15 files)

Phase 5: Plugin Scripts (PARALLEL)
├── 5.1: Update plugins/dev/ scripts (~30 files)
├── 5.2: Update plugins/ai/ scripts (~40 files)
├── 5.3: Update plugins/orchestration/ scripts (~15 files)
└── 5.4: Update plugins/consulting/ scripts (~10 files)

Phase 6: Verification (PIPELINE)
├── 6.1: pytest tests/src/ + npm run build
├── 6.2: Grep for any remaining AUGUR_DATA_DIR/AUGUR_DATA/get_user_data_base
└── 6.3: Start MCP server with only AUGUR_ROOT set — verify it works
```

## Alternatives Considered

### Alternative 1: Rename AUGUR_DATA_DIR to AUGUR_ROOT and keep the code structure

Just change the env var name, keep `data_dir` in MCPConfig, keep `resolveUserDataBase()` in paths.ts.

Rejected because: Renames the lie instead of fixing it. `data_dir` pointing to project root is still semantically wrong. The fallback chains stay.

### Alternative 2: Deprecation period with warnings

Keep `AUGUR_DATA_DIR` working but log deprecation warnings. Remove in 3 months.

Rejected because: Pre-launch — no users to break. No backward compatibility until launch. Unix way.

### Alternative 3: Keep AUGUR_DATA_DIR as alias for AUGUR_ROOT

Support both forever, resolve identically.

Rejected because: Two names for the same thing is a permanent source of confusion. One concept, one name.

## References

- ADR-083: Plugin data colocation (created the `plugins/*/skills/*/data/` pattern)
- ADR-087: Data folder elimination (moved config/, runtime/, memory/ to root)
- ADR-018: Plugin self-containment (plugins own their dependencies and data)
- ADR-024: MCP package decoupling (introduced env var-based configuration)
- `src/mcp/augur_mcp/config.py`: Current MCPConfig with `data_dir`
- `src/dashboard/lib/paths.ts`: Current TypeScript path resolution with fallbacks

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-094: Eliminate AUGUR_DATA_DIR — Plugin-Colocated Data Model**.

Read the full ADR: `docs/decisions/ADR-094-eliminate-augur-data-dir.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict:
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-094-kill-data-dir", description="Implementing ADR-094: Eliminate AUGUR_DATA_DIR")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-094-kill-data-dir", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-094 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-094-kill-data-dir`

#### Phase 1: Config Core
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Refactor `MCPConfig`: remove `data_dir` field, make `project_root` required (not Optional). Update `_get_default_data_dir()` → `_get_project_root()`. Remove `AUGUR_DATA`/`AUGUR_DATA_DIR`/`USER_DATA_BASE` env var reads. Delete `get_user_data_base()`, rename `get_config_data_dir()` → `get_config_dir()`, add `get_runtime_dir()` and `get_memory_dir()`. | `src/mcp/augur_mcp/config.py` |
| 1.2 | developer | medium | Update all `augur_mcp/` internal consumers of `data_dir`, `get_user_data_base`, `get_config_data_dir` to use new API. Run `grep -r "data_dir\|get_user_data_base\|get_config_data_dir" src/mcp/` to find all 25 files. | `src/mcp/augur_mcp/*.py` (25 files) |
| 1.3 | frontend | medium | Refactor `paths.ts`: delete `resolveUserDataBase()`, delete `AUGUR_DATA_DIR` export, remove legacy `data/` fallback from `resolveRuntimeBase()`. Replace all dashboard imports of `AUGUR_DATA_DIR` with `AUGUR_ROOT` or specific dir constants. | `src/dashboard/lib/paths.ts` + ~95 consumer files |

#### Phase 2: IDE & Script Configs
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | devops | low | Fix IDE MCP configs: remove `AUGUR_DATA_DIR` from env, ensure `AUGUR_ROOT` is present and correct. | `.claude/mcp.json`, `.cursor/mcp.json`, `.gemini/settings.json` |
| 2.2 | devops | low | Fix Claude Desktop config and MCP template: remove `AUGUR_DATA_DIR`, add `AUGUR_ROOT`. | `~/Library/Application Support/Claude/claude_desktop_config.json`, `src/config/mcp_config.template.json` |
| 2.3 | devops | low | Fix shell scripts: remove all `AUGUR_DATA_DIR` and `AUGUR_DATA` exports. | `scripts/augur`, `scripts/augur-mcp`, `scripts/install.sh`, `scripts/install.ps1` |
| 2.4 | devops | low | Fix `configure_mcp.py`: stop generating `AUGUR_DATA_DIR` in MCP configs, use `AUGUR_ROOT` instead. | `scripts/configure_mcp.py` |

#### Phase 3: Plugin Scripts
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Update `plugins/dev/` scripts: replace `AUGUR_DATA_DIR`/`AUGUR_DATA`/`USER_DATA_BASE` reads with `AUGUR_ROOT` or `get_project_root()`. | ~30 files in `plugins/dev/` |
| 3.2 | developer | medium | Update `plugins/ai/` scripts: same pattern. Pay attention to `ai_bridge/scripts/sync_agents.py` (11 refs) and `ai_bridge/scripts/context_injector.py` (5 refs). | ~40 files in `plugins/ai/` |
| 3.3 | developer | low | Update `plugins/orchestration/` scripts: `chain_executor.py`, `claim_task.py`, `index_manager.py`, etc. | ~15 files in `plugins/orchestration/` |
| 3.4 | developer | low | Update `plugins/consulting/` MCP init files and TypeScript routes. | ~10 files in `plugins/consulting/` |

#### Phase 4: Dashboard & Src Consumers
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | frontend | medium | Update all `src/dashboard/app/api/` routes that import `AUGUR_DATA_DIR` — replace with `AUGUR_ROOT`, `AUGUR_CONFIG_DIR`, or `AUGUR_RUNTIME_DIR` as appropriate. | ~60 API route files |
| 4.2 | frontend | medium | Update `src/dashboard/lib/` and `src/dashboard/app/` non-API files. | ~20 files |
| 4.3 | developer | low | Update `src/lib/`, `src/config/`, `src/app/` files (non-dashboard). | ~15 files |

#### Phase 5: Tests & Documentation
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | low | Update test files that set `AUGUR_DATA_DIR` in env: switch to `AUGUR_ROOT`. | `tests/test_telemetry_perf.py`, `tests/dashboard/api/*.test.ts` |
| 5.2 | developer | low | Update agent-rules.md and CLAUDE.md with new path model — remove all `AUGUR_DATA_DIR` references. | `plugins/ai/skills/ai_bridge/augur/agent-rules.md` |
| 5.3 | devops | low | Run `sync_agents.py --workflows` to propagate updated rules. | Sync script |

#### Final Phase: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `pytest tests/src/` — all Python tests pass |
| V.2 | validator | low | Run `npm run build` in `src/dashboard/` — clean build |
| V.3 | validator | low | Grep for remaining references: `grep -r "AUGUR_DATA_DIR\|AUGUR_DATA[^_]\|get_user_data_base\|resolveUserDataBase\|get_config_data_dir" src/ plugins/ plugins/ scripts/ .claude/ .cursor/ .gemini/` — zero hits (except docs/decisions/ which are historical) |
| V.4 | validator | low | Start MCP server with only `AUGUR_ROOT` set — verify it initializes without error |
| V.5 | validator | low | Run `python3 .github/scripts/audit_paths.py` — no hardcoded paths |

### Completion Criteria
- [ ] `AUGUR_DATA_DIR` env var not read anywhere in code (only in historical ADRs)
- [ ] `AUGUR_DATA` env var not read anywhere
- [ ] `get_user_data_base()` function deleted from Python and TypeScript
- [ ] `MCPConfig.data_dir` replaced with `MCPConfig.project_root`
- [ ] All IDE configs use `AUGUR_ROOT` only
- [ ] All tests pass (Python + TypeScript)
- [ ] Dashboard builds cleanly
- [ ] MCP server starts with only `AUGUR_ROOT` in environment
- [ ] ADR status updated to Accepted

### How to Run
```
# Option 1: Use /implement-adr
/implement-adr docs/decisions/ADR-094-eliminate-augur-data-dir.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
