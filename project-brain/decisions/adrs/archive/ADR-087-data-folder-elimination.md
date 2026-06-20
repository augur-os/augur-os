---
status: Implemented
date: '2026-02-12'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- eliminate
- data
- directory
- final
- partition
superseded_by: null
---

# ADR-087: Eliminate data/ Directory — Final Partition

**Supersedes**: Completes ADR-083 (plugin-data-colocation)

## Context

The `data/` directory was originally a catch-all for "anything that isn't code." Over time, ADR-083 colocated plugin data into `plugins/{bundle}/skills/{skill}/data/`, and the data path consolidation refactor (494b0542, 5e55f005) cleaned up legacy paths. But `data/` still holds 5 subdirectories that don't belong together:

```
data/
├── config/           # System configuration — not "data"
├── defaults/         # Template configs for init — also config
├── ide-integration/  # AI bridge workflows/registry — plugin data
├── memory/           # Canonical memory store
├── runtime/          # Ephemeral logs/cache/temp
└── services/         # Orphan: just rag/project-index.yaml
```

Problems:
1. **Semantic mismatch**: `config/` and `defaults/` are configuration, not user data
2. **Plugin leak**: `ide-integration/` is ai-bridge plugin data living outside its plugin
3. **Orphaned residue**: `services/` has 1 file — remnant of pre-ADR-083 layout
4. **Buried ephemeral storage**: `runtime/` nested under `data/` implies persistence — it's gitignored temp files
5. **`data/` lost its purpose**: After ADR-083, it's no longer "the data directory" — it's a grab bag

## Decision

Eliminate `data/` by relocating its contents to their correct homes. Four moves:

### Move 1: `data/ide-integration/` → `plugins/ai/skills/ai_bridge/augur/ide-integration/`

**Rationale**: Workflows, hooks, chains, and the registry are ai-bridge skill data. ADR-083 says plugin data lives colocated with the plugin.

| Current Path | New Path |
|---|---|
| `data/ide-integration/registry.yaml` | `plugins/ai/skills/ai_bridge/augur/ide-integration/registry.yaml` |
| `data/ide-integration/workflows/` | `plugins/ai/skills/ai_bridge/augur/ide-integration/workflows/` |
| `data/ide-integration/hooks/` | `plugins/ai/skills/ai_bridge/augur/ide-integration/hooks/` |
| `data/ide-integration/chains/` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` |
| `data/ide-integration/index.yaml` | `plugins/ai/skills/ai_bridge/augur/ide-integration/index.yaml` |

**Code impact**: 1 file (`src/dashboard/scripts/generate_registry.py`) + documentation references.

### Move 2: `config/` + `data/defaults/` → root `config/`

**Rationale**: Configuration belongs at the project root alongside `src/`, `plugins/`, `docs/`. Merging `config/` and `defaults/` eliminates the artificial split between "active config" and "template config."

| Current Path | New Path |
|---|---|
| `config/agents/` | `config/agents/` |
| `config/dashboard/` | `config/dashboard/` |
| `config/integrations/` | `config/integrations/` |
| `config/system/` | `config/system/` |
| `data/defaults/` | `config/defaults/` |

**Code impact**: ~26 references across 18 files. All centralized through `get_config_data_dir()` in `src/config/paths.py` — single function update propagates everywhere.

**Gitignore note**: `config/system/preferences.yaml`, `config/system/plugin_state.json`, and other user-specific files should be gitignored. `config/defaults/` remains tracked as upstream templates.

### Move 3: `data/services/` → `plugins/ai/skills/knowledge/data/`

**Rationale**: Only contains `rag/project-index.yaml` — this is knowledge plugin data. Should have been moved during ADR-083 colocation.

| Current Path | New Path |
|---|---|
| `plugins/ai/skills/knowledge/data/rag/project-index.yaml` | `plugins/ai/skills/knowledge/data/rag/project-index.yaml` |

**Code impact**: ~3 code files. Minimal.

### Move 4: `data/runtime/` → root `runtime/`

**Rationale**: Ephemeral storage (logs, cache, temp, chain executions) shouldn't be nested under a "data" directory that implies persistence. Root placement makes the gitignored nature more visible and aligns with Unix convention (`/var/run`, `/tmp`).

| Current Path | New Path |
|---|---|
| `data/runtime/logs/` | `runtime/logs/` |
| `data/runtime/cache/` | `runtime/cache/` |
| `data/runtime/temp/` | `runtime/temp/` |
| `data/runtime/chain-executions/` | `runtime/chain-executions/` |
| `data/runtime/*` | `runtime/*` |

**Code impact**: ~67 references across 37 files. All centralized through `get_runtime_dir()` — single function update. Also update `src/dashboard/lib/paths.ts` (hardcoded construction).

### Move 5: `data/memory/` → `docs/memory/`

**Rationale**: Memory is persistent curated knowledge — closer to documentation than to config or runtime. Nesting under `docs/` groups all human-readable knowledge artifacts together (ADRs, guides, and now memory). With everything else moved, `data/` would contain only `memory/` — no reason to keep a directory for one child.

| Current Path | New Path |
|---|---|
| `data/memory/MEMORY.md` | `docs/memory/MEMORY.md` |
| `data/memory/daily/` | `docs/memory/daily/` |

**Code impact**: ~12 references across 7 files (memory_sync.py, knowledge MCP tools, advisor analytics).

**Gitignore note**: `docs/memory/daily/` should remain gitignored (ephemeral 14-day retention logs). `docs/memory/MEMORY.md` stays tracked.

### Post-Migration Structure

```
augur/
├── config/              # System & integration configuration
│   ├── agents/          # Agent configs, contexts, prompts
│   ├── dashboard/       # Dashboard UI config
│   ├── integrations/    # MCP config, external providers
│   ├── system/          # Core config, LLM, paths, prefs
│   └── defaults/        # Upstream templates for new users
├── runtime/             # Ephemeral storage (GITIGNORED)
│   ├── logs/
│   ├── cache/
│   ├── temp/
│   └── ...
├── src/                 # Framework code
├── plugins/             # Plugin bundles (own their data)
└── docs/                # Documentation & knowledge
    ├── decisions/       # ADRs
    ├── guides/          # How-to guides
    ├── archive/         # Outdated docs
    └── memory/          # Persistent memory (ADR-057)
        ├── MEMORY.md    # Curated memory
        └── daily/       # Ephemeral daily logs (gitignored)
```

`data/` directory is **deleted** after migration.

### Path Resolution Updates

All changes are centralized in two files:

**`src/config/paths.py`**:
```python
# Before
def get_user_data_base(): return get_project_root() / "data"
def get_config_data_dir(): return get_user_data_base() / "config"
def get_runtime_dir(): return get_user_data_base() / "runtime"

# After
def get_config_dir(): return get_project_root() / "config"
def get_runtime_dir(): return get_project_root() / "runtime"
def get_memory_dir(): return get_project_root() / "docs" / "memory"
# get_user_data_base() → DEPRECATED, remove after migration
```

**`src/dashboard/lib/paths.ts`**:
```typescript
// Before
export function resolveRuntimeBase() { return path.join(repoRoot, 'data', 'runtime') }

// After
export function resolveRuntimeBase() { return path.join(repoRoot, 'runtime') }
```

**`src/config/path_config.yaml`**:
```yaml
# Before
runtime: "data/runtime"
config: "config"

# After
runtime: "runtime"
config: "config"
```

## Consequences

### Positive

- **`data/` eliminated** — no more ambiguous catch-all directory
- **Root structure is self-documenting**: `config/`, `runtime/`, `src/`, `plugins/`, `docs/` — each directory has one clear purpose
- **Plugin data fully colocated** — completes ADR-083's vision
- **Config and defaults unified** — no more split between active config and templates
- **Ephemeral storage visually separated** — `runtime/` at root makes gitignored nature obvious

### Negative

- **174 references to `get_user_data_base()`** need migration or deprecation — bulk of the work
- **Documentation, agent rules, READMEs** all reference `data/` — need updating
- **`.gitignore`** needs restructuring (currently `data/runtime/` patterns → `runtime/` patterns)
- **Memory sync pipeline** (memory_sync.py) and Claude Code memory path hardcoded in multiple IDE configs

### Neutral

- **4-category model stays at 4**: CORE (src/ + docs/), CONFIG, PLUGINS, RUNTIME (was CORE, DATA, PLUGINS, RUNTIME). Memory lives under CORE as `docs/memory/`
- **Shell hooks** (offload-gate.sh, emit_heal_event.sh) construct paths manually — must be updated alongside Python resolution

## Alternatives Considered

### Alternative 1: Keep `data/` with Just Config + Memory

Move only `ide-integration`, `services`, `runtime` out. Keep `config/` and `data/memory/`.

Rejected because: Half-measure. `data/` would still exist with unclear purpose — is it "config and memory"? That's not a coherent category.

### Alternative 2: Rename `data/` to `config/` and Move Runtime Out

Rename `data/` → `config/`, keep everything except `runtime/` inside.

Rejected because: Memory isn't config. ide-integration isn't config. Still a grab bag under a different name.

### Alternative 3: Keep `data/runtime/` Nested

Only move config-like things, leave runtime under `data/`.

Rejected because: `data/` implies persistence. `runtime/` is ephemeral. The nesting misleads about the lifecycle of these files.

## References

- ADR-083: Plugin data colocation (this ADR completes its vision)
- ADR-057: Two-layer memory system (memory path changes)
- Refactor 494b0542: Data path consolidation
- Refactor 5e55f005: Runtime/config relocation
- `src/config/paths.py`: Central path resolution
- `src/config/path_config.py`: 4-category path config

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-087-data-elimination`

### Phase 1: Create Target Directories & Move Files
**Strategy**: PIPELINE (must create dirs before moving)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | devops | low | Create root `config/`, `runtime/` and `docs/memory/` directories. Move all files from `config/` → `config/`, `data/defaults/` → `config/defaults/`, `data/memory/` → `docs/memory/`, `data/runtime/` → `runtime/` | Shell operations |
| 1.2 | devops | low | Move `data/ide-integration/` → `plugins/ai/skills/ai_bridge/augur/ide-integration/` | Shell operations |
| 1.3 | devops | low | Move `plugins/ai/skills/knowledge/data/rag/` → `plugins/ai/skills/knowledge/data/rag/` | Shell operations |
| 1.4 | devops | low | Delete empty `data/` directory. Update `.gitignore` to replace `data/runtime/` patterns with `runtime/` | `.gitignore` |

### Phase 2: Update Path Resolution
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Update `src/config/paths.py`: change `get_config_data_dir()` → `get_config_dir()`, update `get_runtime_dir()`, add `get_memory_dir()` pointing to `docs/memory/`, deprecate `get_user_data_base()` | `src/config/paths.py` |
| 2.2 | developer | medium | Update `src/config/path_config.py` and `path_config.yaml`: adjust 4-category model to new root paths | `src/config/path_config.py`, `config/system/paths.yaml` |
| 2.3 | frontend | medium | Update `src/dashboard/lib/paths.ts`: change hardcoded `data/runtime` → `runtime`, `config` → `config` | `src/dashboard/lib/paths.ts` |
| 2.4 | developer | low | Update shell scripts: `.claude/hooks/offload-gate.sh`, `src/scripts/emit_heal_event.sh`, `.github/scripts/ci_check.sh` | Shell scripts |

### Phase 3: Update All Consumers
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Grep for all `get_user_data_base()` calls, migrate to specific `get_config_dir()`, `get_runtime_dir()`, or `get_memory_dir()` as appropriate | ~20 Python files |
| 3.2 | developer | medium | Update `src/scripts/augur_init.py` to use `config/defaults/` path | `src/scripts/augur_init.py` |
| 3.3 | developer | low | Update `src/dashboard/scripts/generate_registry.py` for new ide-integration path | `src/dashboard/scripts/generate_registry.py` |
| 3.4 | developer | medium | Update memory_sync.py and knowledge MCP tools for new `docs/memory/` path | `.github/scripts/memory_sync.py`, knowledge plugin files |

### Phase 4: Update Documentation & Agent Rules
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Update `CLAUDE.md`, `data/README.md` (delete), `plugins/README.md`, `src/README.md` | Documentation |
| 4.2 | developer | low | Update agent-rules.md monorepo structure diagram and path references | `plugins/ai/skills/ai_bridge/augur/agent-rules.md` |
| 4.3 | developer | low | Run `sync_agents.py` to propagate updated rules to all IDE adapters | Sync script |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `pytest tests/src/` — all path tests pass |
| V.2 | validator | low | Run `npm run build` in `src/dashboard/` — clean build |
| V.3 | validator | low | Run `python3 .github/scripts/audit_paths.py` — no hardcoded paths |
| V.4 | validator | low | Verify `data/` directory no longer exists |
| V.5 | validator | low | Run `grep -r "config\|data/runtime\|data/memory\|data/services\|data/ide-integration" src/ plugins/` — zero hits (except `docs/memory/` which is the new canonical path) |

### Completion Criteria
- [ ] `data/` directory deleted
- [ ] All 5 moves completed
- [ ] `get_user_data_base()` deprecated or removed
- [ ] All tests pass (Python + TypeScript)
- [ ] Dashboard builds cleanly
- [ ] No orphaned `data/` references in code
- [ ] Agent rules and CLAUDE.md updated
- [ ] ADR status updated to Accepted
