---
status: Implemented
date: '2026-03-06'
deciders:
- Gur Sannikov
- Claude
related: []
hub: null
tags:
- agent
- discovery
- protocol
- build
- agents
superseded_by: null
---

# ADR-254: Agent Discovery Protocol and Build-for-Agents Roadmap

## Context

Augur has 500+ MCP tools, 54 skills across 17 hubs, a CLI wrapper (`aug`), and a rich dashboard — but external agents can't discover what Augur can do without navigating multiple files. The system requires explicit `/focus` commands and button clicks to scope context, despite already collecting signals (dashboard page navigation, CLI usage, IDE history, git context) that could infer focus automatically.

Inspired by Karpathy's "Build for Agents" thesis: CLIs are agent-native, docs should be markdown-exportable, products should be usable via CLI/MCP, and composability into larger pipelines is the unlock.

**Current gaps scored against these principles:**

| Principle | Score | Gap |
|-----------|-------|-----|
| CLI-native | 5/10 | No standalone `augur` binary, no `discover` command |
| Markdown docs | 9/10 | Missing single-file agent overview |
| Skills written | 9/10 | No external-agent-facing registry |
| CLI/MCP usable | 8/10 | Too many tools, no installable package |
| Composable module | 5/10 | Hard to use as component in external pipelines |
| Agent-first thinking | 7/10 | Great internally, friction externally |

**Existing focus infrastructure to replace:**
- `/focus` slash command (`plugins/ai/skills/focus/SKILL.md`)
- Focus button + FocusStrip in dashboard chat (`ChatToolbar.tsx`, `FocusStrip.tsx`, `FloatingChat.tsx`)
- `focus_context_tool()` and `get_current_focus_tool()` MCP tools (`mcp_management.py`)
- `FocusPayload` dataclass and `focus_on_skill()`/`focus_with_discovery()` methods (`context_manager.py`)
- `focus_discover.py` script (`plugins/ai/skills/ai_bridge/scripts/`)
- `/api/mcp/context/focus/` and `/api/focus-state/` dashboard routes

## Decision

### Phase 1: Agent Discovery Protocol + Public Tool Surface (This ADR — Implement Now)

Replace explicit focus management with **passive signal-based discovery**. Remove the `/focus` command, focus button, and all focus-specific MCP logic. Add a tool tier system and `aug discover` / `discover-augur` MCP tool.

#### 1.1 Tool Tier Model

Three tiers declared in each plugin's `augur.yaml`:

| Tier | Purpose | Audience | Target |
|------|---------|----------|--------|
| `public` | Core capabilities any agent should know | External agents | ~25-30 tools |
| `standard` | Full operational surface | Internal agents | ~200 tools |
| `internal` | Admin, debug, dev-only | Dev/nightly | Everything else |

```yaml
# In plugin augur.yaml
mcp:
  tools: [get-career-jobs, tailor-resume, get-career-hard-skills]
  tiers:
    public: [get-career-jobs, tailor-resume]
    internal: []
    # unlisted tools default to standard
```

Auto-seeded by one-time script: `core_tools` → public, 3+ page references → public, dev/admin/debug name patterns → internal.

#### 1.2 Per-Session Focus State

Each session gets its own focus file — parallel sessions don't contaminate:

```
runtime/
  focus_state.json            # global (cold-start fallback)
  sessions/
    dashboard-{tab_id}.json
    cli-{pid}.json
    claude-{session_id}.json
```

Session lifecycle:
- CLI: created at first tool call, deleted via Python `atexit`
- Dashboard: created at page load, deleted via `beforeunload` + `sendBeacon`
- IDE agents: created at MCP connect, deleted at MCP disconnect
- Safety net: nightly daemon prunes files older than 1 hour

#### 1.3 Signal Refresh Strategy (Client-Dependent)

| Client | When signals are read | Rationale |
|--------|----------------------|-----------|
| Web CLI (dashboard chat) | On every user message | Chat reflects the page user is on |
| Terminal CLI (`aug`) | Session start + explicit `aug discover` | Independent workstream, zero per-tool overhead |
| IDE agents | MCP connect + explicit `discover-augur` | Agent controls when to refresh |

Existing signal sources (no new writers needed):
- `runtime/focus_state.json` — dashboard page navigation (real-time)
- `runtime/daemon/usage_stats.yaml` — page view counts (daily)
- `runtime/logs/ide_history.json` — IDE executions (real-time)
- Git context — branch, recent files (live)

Dashboard heartbeat guard: only writes when `document.visibilityState === "visible"` — background tabs stop polluting signals.

#### 1.4 Discovery Command and MCP Tool

**CLI**: `aug discover [--hub X] [--tier X] [--compact] [--format markdown]`

**MCP**: `discover-augur { tier?, hub? }`

Returns structured manifest:
```json
{
  "focus": { "hub": "career", "skill": "career", "signals": {...} },
  "recommended_tools": [...tools scoped to hub/tier...],
  "manifest": {
    "name": "augur",
    "capabilities": { "skills": 54, "hubs": 17, "tools": {...} },
    "hubs": [...],
    "cli": { "binary": "aug", "usage": "..." },
    "mcp": { "server": "augur", "transport": "stdio" }
  }
}
```

#### 1.5 Focus Removal

| Component | Action |
|-----------|--------|
| `plugins/ai/skills/focus/` | DELETE entire directory |
| `FocusButton` in `ChatToolbar.tsx` | DELETE component |
| `FocusStrip.tsx` | DELETE file |
| `FloatingChat.tsx` focus handlers | DELETE `handleFocusClick`, `handleDeepFocusFromStrip`, focus useEffect |
| `ChatLayout.tsx` focus props | DELETE focus-related rendering |
| `focus_context_tool()` in `mcp_management.py` | DELETE |
| `FocusPayload`, `focus_on_skill()`, `focus_with_discovery()` in `context_manager.py` | DELETE |
| `focus_discover.py` | DELETE |
| `/api/mcp/context/focus/route.ts` | DELETE |
| `/api/focus-state/route.ts` | REPURPOSE for per-session writes |
| `useMCPContext.ts` | SIMPLIFY — remove `focusContext()` calls |
| `MCPContextClient.ts` | SIMPLIFY — remove `focusContext()` method |
| Focus tests (`focus-state.test.ts`, `focus-state-smoke.spec.ts`) | DELETE |

### Phase 2: Standalone CLI Package (Future)

Package `aug` as `pip install augur-cli` with `pyproject.toml` entry point. Mostly packaging work — the CLI already exists and works.

- Add `pyproject.toml` with `[project.scripts] aug = "src.cli:main"`
- Ensure clean stdout (JSON/text, no ANSI when piped)
- Publish to PyPI or local registry
- Any agent can `pip install augur-cli && aug discover`

### Phase 3: Composable Python API (Future)

Thin import layer over MCP tool functions:

```python
from augur import career, health, knowledge
jobs = career.get_jobs(status="active")
```

- One module per hub, wrapping MCP tool calls
- Standardize return envelope: `{status, data, metadata}`
- Enables use in pipelines and scripts without MCP setup

### Phase 4: Event/Webhook Layer (Future)

Let external systems subscribe to Augur events:

- "New job match" → webhook
- "Health alert" → notification
- Requires subscription model, persistence, delivery guarantees
- Build only when external consumers prove demand

### Phase 5: Agent Gateway (Future, If Needed)

Separate minimal MCP server exposing only public-tier tools:

- `npx augur-gateway` or `uvx augur-gateway`
- Curated 25-tool surface, built-in `discover` as first tool
- Own package, zero-config startup
- Only warranted if external agent ecosystem grows

## Consequences

### Positive

- External agents can discover and use Augur via `aug discover` without reading codebase
- 500+ tools reduced to curated ~25 public surface for external consumers
- No more explicit `/focus` — context inferred automatically from existing signals
- Parallel CLI/dashboard/IDE sessions work independently without signal contamination
- Zero per-tool-call overhead in terminal CLI
- Cleaner codebase — removes ~1000 lines of focus-specific code across 15+ files

### Negative

- Terminal CLI won't auto-detect context shifts (only on explicit `aug discover`)
- Removing `/focus` requires users to rely on automatic inference — no manual override button
- Initial tier tagging requires one-time curation of ~500 tools

### Neutral

- Dashboard page navigation still writes `focus_state.json` — mechanism unchanged, just scoped to session
- `ContextManager.switchContext()` and tool group switching remain unchanged
- MCP tool registration and filtering infrastructure reused, just extended with tier

## Alternatives Considered

### Alternative 1: Metadata-Only (Tier tags + filter, no discovery protocol)

Add `tier: public` to augur.yaml and filter in MCP server. No manifest, no signal reading, no session isolation.

Rejected: Too thin. Filtering without discovery doesn't help external agents self-orient. The value is in the structured manifest + automatic context, not just hiding tools.

### Alternative 2: Full Agent Gateway (Separate MCP server)

Build a separate `augur-gateway` package exposing only public tools with its own entry point and registration.

Rejected: Premature. No external consumers yet. Maintaining two MCP servers adds complexity without proven demand. Can be added as Phase 5 if needed.

### Alternative 3: Per-Tool-Call Signal Refresh

Re-read `focus_state.json` on every MCP tool call with context-shift notifications injected into responses.

Rejected: Adds failure surface and coupling to every tool invocation. Race conditions with parallel calls. Checking 100x more often than context changes. Terminal CLI should have zero overhead.

## References

- Design doc: `docs/plans/2026-03-06-agent-discovery-protocol-design.md`
- Implementation plan: `docs/plans/2026-03-06-agent-discovery-protocol-plan.md`
- Karpathy "Build for Agents" thesis (2026-03-06 tweet)
- ADR-059: Skill-Aware Context Focus (superseded by this ADR)
- ADR-072: Focus WoW Demo (superseded by this ADR)
- ADR-124: Focus Button Contextual Discovery (superseded by this ADR)
- ADR-163: Plugin Decentralization (tier metadata follows this pattern)
- ADR-250: MCP Tool Hygiene (tier filtering extends this)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - function: focus_context_tool
      module: augur_mcp.infrastructure.mcp_management
      breaking: true
    - function: get_current_focus_tool
      module: augur_mcp.infrastructure.mcp_management
      breaking: true
    - function: focus_on_skill
      module: augur_mcp.context_manager
      breaking: true
    - function: focus_with_discovery
      module: augur_mcp.context_manager
      breaking: true
    - function: FocusPayload
      module: augur_mcp.context_manager
      breaking: true
  patterns_deprecated:
    - grep: "focus_context_tool|focus_on_skill|FocusPayload|FocusButton|FocusStrip|handleFocusClick"
      replacement: "discover-augur MCP tool + per-session focus in runtime/sessions/"
    - grep: "/api/mcp/context/focus"
      replacement: "discover-augur MCP tool"
    - grep: "/focus"
      replacement: "aug discover or discover-augur MCP tool"
  files_affected:
    - glob: "plugins/ai/skills/focus/**"
    - glob: "src/dashboard/components/chat/FocusStrip.tsx"
    - glob: "src/dashboard/components/chat/ChatToolbar.tsx"
    - glob: "src/dashboard/components/FloatingChat.tsx"
    - glob: "src/dashboard/components/chat/ChatLayout.tsx"
    - glob: "src/mcp/augur_mcp/infrastructure/mcp_management.py"
    - glob: "src/mcp/augur_mcp/context_manager.py"
    - glob: "plugins/ai/skills/ai_bridge/scripts/focus_discover.py"
    - glob: "src/dashboard/app/api/mcp/context/focus/**"
    - glob: "src/dashboard/app/api/focus-state/**"
    - glob: "src/dashboard/hooks/useMCPContext.ts"
    - glob: "src/dashboard/lib/mcp/MCPContextClient.ts"
    - glob: "tests/dashboard/api/focus-state.test.ts"
    - glob: "tests/dashboard/visual/focus-state-smoke.spec.ts"
```

## Implementation Prompt

> Paste this into Claude Code to execute Phase 1 using Agent Teams.

**Team name**: `adr-254-agent-discovery`

### Phase 1: Core Discovery Module
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Signal reader: read_signals(), infer_hub() with tests | `src/mcp/augur_mcp/domain/discovery.py`, `tests/mcp/domain/test_discovery.py` |
| 1.2 | developer | medium | Manifest assembler: assemble_manifest(), _scan_skills() with tests | `src/mcp/augur_mcp/domain/discovery.py`, `tests/mcp/domain/test_discovery.py` |
| 1.3 | developer | medium | Session manager: create/read/update/delete/prune with tests | `src/mcp/augur_mcp/domain/sessions.py`, `tests/mcp/domain/test_sessions.py` |
| 1.4 | developer | low | Auto-seeding script: derive tiers from mcp_tool_groups.yaml | `src/scripts/seed_tool_tiers.py`, `tests/scripts/test_seed_tool_tiers.py` |

### Phase 2: CLI + MCP Integration
**Strategy**: PIPELINE (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | `aug discover` CLI subcommand with session lifecycle + atexit | `src/cli.py`, `tests/cli/test_discover.py` |
| 2.2 | developer | medium | `discover-augur` MCP tool registration | `src/mcp/augur_mcp/infrastructure/mcp_management.py`, `tests/mcp/infrastructure/test_discover_tool.py` |

### Phase 3: Focus Removal
**Strategy**: PIPELINE (depends on Phase 2)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Delete /focus skill directory and command registration | `plugins/ai/skills/focus/`, `.claude/skills/` |
| 3.2 | frontend | medium | Remove FocusButton, FocusStrip, focus handlers from dashboard | `ChatToolbar.tsx`, `FocusStrip.tsx`, `ChatLayout.tsx`, `FloatingChat.tsx` |
| 3.3 | developer | medium | Remove focus MCP tools and FocusPayload from backend | `mcp_management.py`, `context_manager.py`, `focus_discover.py` |
| 3.4 | frontend | medium | Repurpose /api/focus-state for per-session writes + visibility guard | `route.ts`, `useMCPContext.ts`, `MCPContextClient.ts` |
| 3.5 | frontend | low | Add beforeunload session cleanup via sendBeacon | `ContextManager.tsx`, `api/focus-state/cleanup/route.ts` |

### Phase 4: Documentation + Verification
**Strategy**: PIPELINE (depends on Phase 3)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Update agent-topics and agent-rules, regenerate synced files | `CONTEXT.md`, `agent-rules.md`, `sync_agents.py` |
| 4.2 | validator | medium | Full test suite, dashboard build, grep for focus remnants | All |

### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | validator | low | `aug discover --compact` returns tools, session file lifecycle works |
| V.3 | validator | low | Grep for FocusButton, FocusStrip, focus_context_tool — zero matches in active code |
| V.4 | architect | low | Verify ADR-254 intent matches implementation |

### Completion Criteria

- [ ] `aug discover` returns structured manifest with focus inference
- [ ] `discover-augur` MCP tool registered and functional
- [ ] Per-session files created/deleted correctly (atexit, beforeunload, MCP disconnect)
- [ ] Tool tier metadata in augur.yaml, ~25 tools tagged as public
- [ ] `/focus` command removed from skill registry
- [ ] Focus button and FocusStrip removed from dashboard
- [ ] FocusPayload, focus_on_skill, focus_with_discovery removed from MCP backend
- [ ] focus_discover.py deleted
- [ ] Dashboard builds successfully
- [ ] All existing tests pass (focus-specific tests removed)
- [ ] Agent docs updated (CONTEXT.md, agent-rules.md)
- [ ] ADR-254 status updated to Implemented
