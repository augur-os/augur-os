<!--
⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: docs/agent-topics/ARCHITECTURE.md
Generator: project-brain/capabilities/skills/ai/scripts/sync_agents/__init__.py
-->
# Architecture

> **When to load**: Load this doc when working on file structure, path resolution, plugin mounting, data separation, or API routes.

## Monorepo Structure

```
augur/                    # Single monorepo
├── src/
│   ├── config/               # Path resolution (paths.py, path_config.py)
│   ├── scripts/              # Python utilities (sync, audit, validate)
│   └── dashboard/            # Next.js 14 app (App Router)
├── project-brain/capabilities/skills/                   # SKILLS - Project/team skills live here (self-contained)
│   ├── channels/             # System admin: channel management
│   ├── ai_bridge/            # AI tooling: IDE sync, agent configs
│   ├── knowledge/            # AI tooling: RAG, search
│   ├── career/               # Career & growth tracking
│   ├── advisor/              # Dev tooling: code review
│   ├── daemon/               # Monitoring & health checks
│   └── ...                   # 130+ skills across all hubs
├── config/                   # CONFIG - Configuration (ADR-087)
│   ├── agents/               # Agent configs, prompts, rules
│   ├── dashboard/            # Dashboard settings (action buttons, tools)
│   ├── defaults/             # Default configs for fresh installs
│   ├── integrations/         # MCP configs, external providers
│   └── system/               # System config (llm.yaml, preferences)
├── docs/                     # Documentation (flat structure)
│   ├── archive/              # Outdated/superseded docs
│   └── guides/               # How-to guides
```

External ADR-270 locations (paths configured in `project.yaml`, resolve via `src.config.paths`):
- `get_vault_dir()` = user-editable skill data + memory
- `get_documents_dir()` = external documents and collateral (reports, exports, binaries)
- `get_runtime_dir()` = persistent state + IPC (`~/Library/Application Support/Augur/state`)
- `get_logs_dir()` = logs (`~/Library/Logs/Augur/`)
- `get_cache_dir()` = caches (`~/Library/Caches/Augur/`)

## Data Separation (Monorepo)

- `src/`, `project-brain/capabilities/skills/`, `docs/` = CODE (Python, TypeScript, configs)
- `config/` = CONFIGURATION (agents, dashboard, system, integrations)
- external state/logs/cache dirs = runtime data
- `get_memory_dir()` = canonical memory root
- **NEVER** mix code and user data in the same directories

## Harness LLM Boundary

Augur is the harness/control layer around native AI clients. The active AI client supplies the default LLM reasoning for classification, summarization, wiki synthesis, planning, and workflow orchestration. MCP tools prepare handoffs, read/write/validate data, and perform atomic mutations; dashboards transport and render; daemons schedule.

Augur code should not hide model calls behind dashboard, daemon, or MCP paths. Execution that needs language-model judgment is routed through the active agent/client handoff unless a governing ADR defines a different execution boundary.

## Vault Directory Conventions (ADR-416)

| Directory Pattern | Purpose | Sync-eligible |
|---|---|---|
| `tasks/`, `notes/`, `items/`, etc. | User data (.md files with frontmatter) | Yes |
| `_config/` | Machine config within a data directory | No |
| `_cache/` | Generated indexes, caches | No |
| `prompts/` | AI prompt templates | No |
| `actions/` | Action definitions | No |

**FORBIDDEN in vault:** `hardening-reports/` — use `get_hardening_dir()` which resolves to `~/Library/Application Support/Augur/state/hardening/`.

Directories starting with `_` are machine-managed and excluded from sync operations.

## Stray Directory Cleanup (Garbage Collector)

When you encounter stray output directories in the repo root (e.g. `output/`, `tmp/`, `results/`, `exports/`, or any ad-hoc folder that doesn't belong to the project structure), move them under `get_runtime_dir() / "garbage_collector"` instead of deleting them.

```bash
# Move stray directory to garbage collector
python3 - <<'PY'
from src.config.paths import get_runtime_dir
print(get_runtime_dir() / "garbage_collector")
PY

# Or for files
python3 - <<'PY'
from src.config.paths import get_runtime_dir
print(get_runtime_dir() / "garbage_collector")
PY
```

**Rules**:
- `garbage_collector/` lives under the canonical external state dir
- Append a timestamp suffix to avoid collisions
- The nightly cleanup job prunes items older than 7 days
- This preserves files temporarily in case the user needs them, while keeping the repo root clean
- Known stray patterns: `output/`, `tmp/`, `temp/`, `results/`, `exports/`, `scratch/`, any `*.zip` not in `.gitignore`

**When to trigger**: During `/dev-merge` or whenever you notice untracked directories in the repo root that aren't part of the project structure.

## Path Resolution - Read Config First

```python
from src/lib.config.paths import (
    get_project_root,      # Monorepo root
    get_config_dir,        # config/ directory
    get_skill_data_dir,    # get_vault_dir()/{bundle}/{skill}
    get_runtime_dir,       # ~/Library/Application Support/Augur/state
    get_logs_dir,          # ~/Library/Logs/Augur
    get_memory_dir,        # get_vault_dir()/memory/
)
```
**Critical**: Runtime data (state, logs, cache, temp) goes to external platform dirs, not code dirs.

## No Hardcoded Paths

```python
# FORBIDDEN - will fail pre-commit audit
path = "/Users/username/Projects/augur"

# CORRECT
from src.config.paths import get_config_dir, get_project_root
```

## Dashboard

- **Framework**: Next.js 16 with App Router + Turbopack
- **Styling**: Tailwind CSS 4 + shadcn/ui
- **State**: React Query for server state, Zustand for client state
- **Routing**: Catch-all `[[...slug]]` routes per hub with dynamic imports

### Dual-Alias Architecture (ADR-483)

Dashboard source code lives in two locations with a **stability boundary**:

```
apps/dashboard/     → @/        (framework — stable, changes rarely)
apps/dashboard/features/   → @/features/   (features — volatile, changes with skills)
```

**Dependency rule:** `@/` NEVER imports `@/features/`. `@/features/` can import `@/`. Framework has zero knowledge of domain features.

```typescript
// Feature importing framework primitive
import { GlassCard } from '@/components/ui/GlassCard';
import { useMcpQuery } from '@/hooks/useMcpQuery';

// Feature importing another feature
import { ChatPanel } from '@/features/components/chat/ChatPanel';

// FORBIDDEN — framework importing feature
import { Chat } from '@/features/components/chat/Chat';
```

**What lives where:**

| Location | Alias | Contains | Changes when skills change? |
|----------|-------|----------|-----------------------------|
| `apps/dashboard/` | `@/` | UI primitives, plugin system (SkillAutoPage), MCP client, server utils, auth, framework hooks, Next.js routes, build scripts | No |
| `apps/dashboard/features/` | `@/features/` | Custom pages, domain components (chat, blocks, agents), domain lib, domain hooks, MCP tool scripts, SKILL.md | Yes |

**tsconfig.json:**
```jsonc
{
  "compilerOptions": {
    "baseUrl": "../..",
    "paths": {
      "@/*": ["apps/dashboard/*"],
      "@/features/*": ["apps/dashboard/features/*"]
    }
  }
}
```

**Test:** "If you replaced all Augur features with a different product, what would you keep?" That's `@/` (framework). What you'd throw away is `@/features/` (features).

### Plugin File Mounting (ADR-483)

Custom pages live in `apps/dashboard/features/pages/{hub}/{page}/`. The mount system discovers them at build time and generates catch-all route registries.

- **Page source**: `apps/dashboard/features/pages/{hub}/{page}/page.tsx`
- **Registry target**: `apps/dashboard/app/{hub}/[[...slug]]/registry.ts` (auto-generated)
- **Mount trigger**: `pnpm run mount-plugins` from `apps/dashboard/`

**How page discovery works:**
1. Mount system scans `apps/dashboard/features/pages/` for hub directories
2. For each hub, finds `page.tsx` files recursively
3. Cross-references against installed skills' `x-augur-dashboard-pages` in SKILL.md
4. Only mounts pages whose declaring skill is present
5. Generates registry.ts with dynamic imports using `@/features/pages/` prefix

**Skills that don't have custom pages** get auto-generated pages (autopages) from their SKILL.md block/action metadata — no page.tsx needed.

**Framework code alignment:** `apps/dashboard/features/` is framework-layer code exempt from skill bundle-grouping rules. It does not need to declare Workspace pages via `x-augur-dashboard-pages`.

**node_modules resolution:** All dashboard code lives in `apps/dashboard/` — no cross-directory symlinks needed (ADR-526).

**FORBIDDEN: Pages in `project-brain/capabilities/skills/*/augur/dashboard/`** — Pages placed in `project-brain/capabilities/skills/*/augur/dashboard/` are discovered by the tab generator but NOT included in the catch-all registry, creating orphan tabs that crash the build. Always place custom pages in `apps/dashboard/features/pages/{hub}/{page}/page.tsx`. The `project-brain/capabilities/skills/*/augur/dashboard/` path exists as a legacy fallback in the discovery system but the registry generator does not scan it.

**Naming constraint:** When a skill's name matches its hub name (e.g., skill "career" in hub "career"), route computation for subpages must skip the skill segment to avoid double paths (`/career/career/pipeline` → should be `/career/pipeline`). The mount system handles this automatically via the `skill === hubId` guard in `page-discovery.ts` and `mount-plugins.ts`. Verify new pages with `pnpm run mount-plugins` — check for `0 orphans` in the tab registry output.

## API Routes (TypeScript)

```typescript
// FORBIDDEN
sys.path.insert(0, '/Users/username/Projects/augur')

// CORRECT
sys.path.insert(0, '${process.cwd()}')
```

### MCP-Direct Data Fetching (MANDATORY)

Dashboard pages call MCP tools directly via hooks — no proxy route layer, no per-tool API routes. All data flows through a single transport endpoint:

```
Component --> useMcpQuery/useMcpMutation/useMcpPoll
  --> POST /api/mcp/tool { tool, args }
    --> MCPBridge.callTool() over stdio JSON-RPC
      --> Python MCP server --> @mcp.tool handler
```

**Hooks:**

| Hook | Purpose | Example |
|------|---------|---------|
| `useMcpQuery(key, tool, preset, opts?)` | Read data (GET-style) | `useMcpQuery('health', 'get-system-health', 'device')` |
| `useMcpMutation(tool, opts?)` | Write data (mutations) | `useMcpMutation('update-preference')` |
| `useMcpPoll(key, tool, intervalMs, opts?)` | Polling (interval refetch) | `useMcpPoll('status', 'get-daemon-status', 5000)` |
| `mcpCall(tool, args)` | Low-level imperative call | `await mcpCall('skill-action', { id })` |

**Presets** control cache/stale/retry behavior: `device`, `realtime`, `live`, `user-data`, `config`, `static`.

**Transport:** Only two API routes remain — `POST /api/mcp/tool` (tool calls) and `/api/blocks/data` (block data).

NEVER call Python scripts directly (`runPythonScript`, `execFile`, `spawn`). NEVER import `fs` or `node:fs` in dashboard code.

**Why**: MCP tools are the single API layer. Direct hooks eliminate the proxy route indirection that previously required hundreds of route config entries.

**When adding new dashboard features**: Create or extend an MCP tool, then call it from the component via `useMcpQuery` or `useMcpMutation`. No API route needed.

## Documentation Structure

### Flat Structure (No Nesting)
```
docs/
├── agent-rules.md              # Agent instructions (this file)
├── vision.md                   # Project philosophy & goals
├── developer-guide.md          # Developer onboarding
├── user-guide.md               # User documentation
├── architecture-*.md           # Architecture docs (flat, prefixed)
├── archive/                    # Outdated docs (preserved for history)
└── guides/                     # How-to guides
```

### ADR Guidelines (Architecture Decision Records)
- **Location**: `get_adr_dir()/ADR-NNN-title.md` (`get_documents_dir()/adrs/`)
- **Numbering**: Sequential (ADR-001, ADR-002, ...). Check latest with `ls $(python3 -c "from src.config.paths import get_adr_dir; print(get_adr_dir())")`
- **Template**: Copy from the ADR template in `get_adr_dir()/TEMPLATE.md`
- **When to create**: Major architectural changes, new patterns, breaking changes
- **Responsible skill**: `knowledge` (documentation maintenance)

### Documentation Maintenance
- **knowledge skill** owns documentation cleanup and consistency
- Archive outdated docs to `docs/archive/` (don't delete)
- Keep `docs/` flat - no deep nesting (max 1 level: decisions/, archive/, guides/)

## Config Decentralization (ADR-163 — Critical Rule #1)

Centralized config files in `config/dashboard/` are **technical debt**, not patterns to extend:

| Centralized File (LEGACY) | Decentralized Location (TARGET) | Status |
|---|---|---|
| `config/dashboard/mcp_tool_groups.yaml` | `config/dashboard/generated/assembled_tool_config.json` | ADR-260: replaced by generated assembly |
| `config/dashboard/tool_display_names.yaml` | `config/dashboard/generated/assembled_tool_config.json` | ADR-260: replaced by generated assembly |
| `config/dashboard/mcp_tools.yaml` | SKILL.md `x-augur-mcp-tools` frontmatter | Pending |

**Rule**: Never add entries to centralized config. Tool config is generated by `mount-plugins` tool assembly step (ADR-260). Add tool metadata to the skill's SKILL.md frontmatter (`x-augur-*` fields) and let assembly scripts discover it.

## Action Dispatch Model (ADR-162)

Actions use the `dispatch` field (not legacy `flow:`):

| Dispatch Mode | When to Use |
|---|---|
| `fire` | Pure bash/script execution, no LLM needed |
| `oneshot` | Single native AI-client prompt with focused context |
| `ide` | Multi-step agent work, exploration, code changes |
| `modal` | User confirmation or interactive input required |

**Canonical type**: `DispatchMode` from `apps/dashboard/lib/actions/types.ts` — import from there, never define inline union types.

## Worktree Isolation (ADR-101)

### Why Worktrees

Git worktrees enable **parallel ADR implementation** via `/adr` and hub hardening via `/harden`. Multiple agents work on different features simultaneously without branch switching. Without isolation, collisions occur in:
- **Port bindings** (multiple dev servers on port 3000)
- **MCP server paths** (AUGUR_ROOT pointing to wrong directory)
- **Instance locks** (PID file contention)
- **Path migration** (worktree paths committed to main)

### Port Allocation

| Context | Dashboard Port | MCP Port | Lock File |
|---------|---------------|----------|-----------|
| Main repo | 3000 | 8080 | `<state>/mcp_server.pid` |
| Worktree N | 3000+N | 8080+N | `<state>/mcp_server_{port}.pid` |

- **Dashboard ports**: 3001-3010 (max 10 concurrent worktrees)
- **MCP ports**: 8081-8090 (dashboard port + 5080)
- Set via `PORT` environment variable in `.env.local`

### Worktree Registry

**Location**: `<state>/worktree_registry.yaml`

```yaml
worktrees:
  /path/to/augur-adr-101:
    name: adr-101
    dashboard_port: 3001
    mcp_port: 8081
    branch: adr-101-impl
    created_at: 2026-02-14T10:00:00
    status: active
```

**Operations**:
- `scripts/worktree_registry.py register --path $(pwd) --name adr-101` — allocate port
- `scripts/worktree_registry.py list` — show active worktrees
- `scripts/worktree_registry.py unregister --path $(pwd)` — free port

### Marker File

**Location**: `.augur-worktree.yaml` (gitignored)

```yaml
worktree: true
dashboard_port: 3001
mcp_port: 8081
main_repo: /Users/username/Projects/Augur
name: adr-101
```

Daemon detects this file to skip monitoring in worktree context.

### Daemon Behavior

| Mode | In Main Repo | In Worktree |
|------|-------------|-------------|
| **Production** | Monitor + auto-restart | Skip (notify only) |
| **Dev** | Notify only | Skip (silent) |

The daemon calls `get_repo_context()` to detect worktree context and defers all monitoring operations.

### MCP Config Isolation

Worktrees use generated MCP config from template:

```
main/.claude/mcp.worktree.json  # Template with {{WORKTREE_PATH}}, {{MCP_PORT}}
worktree/.claude/mcp.json       # Generated with actual values
```

**Generated at worktree creation**:
```bash
WORKTREE_PATH=$(pwd) MCP_PORT=8081 \
  scripts/generate-worktree-mcp.py > .claude/mcp.json
```

### Key References

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | Full rules (generated from `docs/agent-topics/agent-rules.md`) |
| `get_adr_dir()` | Architecture Decision Records |
| `src/config/paths.py` | Path resolution functions |
| `src/config/path_config.py` | 4-category path config |
