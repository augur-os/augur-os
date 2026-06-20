---
status: Implemented
date: 2026-03-21
deciders:
  - Gur Sannikov
related:
  - ADR-426
  - ADR-429
  - ADR-460
  - ADR-461
  - ADR-186
hub: null
tags:
  - agents
  - sync
  - cross-client
  - model-mapping
  - multi-master
superseded_by: null
---

# ADR-464: Cross-Client Agent Sync — Multi-Master Agent Distribution with Model Mapping

## Context

ADR-426 established client-native skill mastering: any AI client (Claude Code, Gemini, Codex, Cursor) can own a skill, and adapted copies flow to all other clients. This pattern works for skills today. However, a recent refactor (commits `bc1768e06`–`fe9d22969`, 2026-03-21) made `.claude/agents/*.md` the hardcoded master for all 14 agents, breaking the multi-master convention.

The problem has three parts:

1. **No master declaration on agents.** Agent `.md` files lack `x-augur-master` frontmatter. A Gemini-authored agent has no way to become the source of truth — `sync_subagents()` only reads from `.claude/agents/`.

2. **No model mapping.** Claude Code uses abstract model names (`haiku`, `sonnet`, `opus`). Gemini uses `gemini-2.5-flash`, `gemini-3-flash-preview`, `gemini-3.1-pro-preview`. Codex uses `gpt-5.4-mini`, `gpt-5.4`, `gpt-5.3-codex`. Cursor uses `fast`, `inherit`, or specific model IDs. There is no translation layer.

3. **Incompatible agent capabilities.** Each client supports a different subset of agent features:

| Capability | Claude Code | Gemini CLI | Codex CLI | Cursor |
|-----------|------------|-----------|----------|--------|
| Agent file location | `.claude/agents/` | `.gemini/agents/` | `config.toml [agents]` | `.cursor/agents/` + reads `.claude/agents/` |
| File format | MD + YAML frontmatter | MD + YAML frontmatter | TOML config section | MD + YAML frontmatter |
| Mode/permissions | `mode: auto\|plan` | None (all can act) | `sandbox_mode` per config | `readonly: true\|false` |
| Tool restriction | Via instructions | `tools: [wildcards]` | Per config section | Inherits parent tools |
| MCP scoping | `mcpServers: [augur]` | Inherited from settings.json | `[mcp_servers]` in config.toml | Inherited from mcp.json |
| Isolation | `isolation: worktree` | Global sandbox | `sandbox_mode` | Not per-agent |
| Hooks | Per-agent hooks | Global hooks only | None | None |
| Nesting | Yes (Agent tool) | No | Yes (`max_depth`) | No |
| Background exec | Via Agent tool | Not native | `max_threads` | `is_background: true` |
| Turn limits | No native limit | `max_turns` (default 30) | No limit | No limit |
| Temperature | Not configurable | `temperature: 0.0–2.0` | Not per-agent | Not per-agent |
| Status | Stable (GA) | Experimental | Stable | Stable (2.4+) |

Without this ADR, agents are Claude-Code-only. Users of Gemini, Codex, or Cursor get no agents at all, and there's no path for a non-Claude-Code agent to become the master.

## Decision

Extend the ADR-426 multi-master pattern from skills to agents, with a model mapping config and per-client capability translation.

### 1. Agent Master Declaration (`x-augur-master`)

Every agent `.md` file in any client directory declares its master via frontmatter:

```yaml
# .claude/agents/developer.md (Claude Code is master)
---
mode: auto
model: sonnet
mcpServers:
  - augur
x-augur-master: claude-code
---
```

```yaml
# .gemini/agents/researcher.md (Gemini is master)
---
name: researcher
description: Deep research agent with web search
model: gemini-3.1-pro-preview
tools:
  - read_file
  - grep_search
  - mcp_augur_*
x-augur-master: gemini
---
```

Valid values: `claude-code`, `gemini`, `codex`, `cursor`, `cline`, `copilot`, `windsurf`, `opencode`, `antigravity`.

Files without `x-augur-master` default to the client whose directory they're in (e.g., `.claude/agents/foo.md` defaults to `claude-code`).

Adapted copies include the `AUGUR-ADAPTED-COPY` marker comment, same as skills.

### 2. Model Mapping Configuration

A central config file maps abstract model tiers to client-specific model IDs:

**File**: `config/agents/model_mapping.yaml`

```yaml
# Model mapping: abstract tiers → client-specific model IDs
# Updated manually when clients release new models

tiers:
  fast:
    description: "Quick lookups, simple searches, low-cost tasks"
    clients:
      claude-code: haiku
      gemini: gemini-2.5-flash
      codex: gpt-5.4-mini
      cursor: fast
      copilot: gpt-5.4-mini
      opencode: haiku            # Supports any model via provider config
      kimi: kimi-k2-lite
  standard:
    description: "Feature implementation, bug fixes, general development"
    clients:
      claude-code: sonnet
      gemini: gemini-3-flash-preview
      codex: gpt-5.4
      cursor: inherit
      copilot: gpt-5.4
      opencode: sonnet
      kimi: kimi-k2
  deep:
    description: "Architecture, complex debugging, cross-system refactoring"
    clients:
      claude-code: opus
      gemini: gemini-3.1-pro-preview
      codex: gpt-5.3-codex
      cursor: claude-opus-4-6
      copilot: gpt-5.3-codex
      opencode: opus
      kimi: kimi-k2.5

# Reverse lookup: given a client-specific model, resolve to abstract tier
# Used when reading a master agent file authored in a non-Claude-Code client
reverse_lookup:
  gemini-2.5-flash: fast
  gemini-2.5-flash-lite: fast
  gemini-3-flash-preview: standard
  gemini-3.1-pro-preview: deep
  gpt-5.4-mini: fast
  gpt-5.4: standard
  gpt-5.3-codex: deep
  kimi-k2-lite: fast
  kimi-k2: standard
  kimi-k2.5: deep
  haiku: fast
  sonnet: standard
  opus: deep
  fast: fast
  inherit: standard
```

**Why central and not per-plugin**: Model mapping is cross-cutting infrastructure, not per-skill data. It changes when model providers release new models, not when skills change. This is the same category as `config/agents/agents.yaml` (IDE platform registry).

### 3. Capability Translation Rules

Each adapter translates the master agent's features to the target format, dropping unsupported features with a comment.

#### Claude Code → Gemini

| Claude Code field | Gemini equivalent | Notes |
|------------------|-------------------|-------|
| `mode: auto` | (omitted) | Gemini has no mode concept; all agents can act |
| `mode: plan` | (omitted, add instruction) | Append "You MUST NOT modify files" to body |
| `model: sonnet` | `model: gemini-3-flash-preview` | Via model_mapping.yaml |
| `mcpServers: [augur]` | (omitted) | Gemini inherits MCP from settings.json |
| `isolation: worktree` | (omitted) | Gemini uses global sandbox, not per-agent |
| `hooks: {...}` | (omitted) | Gemini hooks are global, not per-agent |
| Body (instructions) | Body (instructions) | Preserved verbatim |
| Safety constraints | Body (instructions) | Embedded as natural language (same as Claude Code) |

Added Gemini-specific fields:
- `name`: derived from filename (required by Gemini)
- `description`: extracted from first `>` blockquote or first paragraph
- `tools`: mapped from Allowed Tools section + MCP wildcards
- `max_turns: 30` (default, prevents runaway)

#### Claude Code → Codex

Codex does not have per-agent markdown files. Instead, agents are configured in `config.toml`:

```toml
[agents.developer]
description = "Code simplification, migration safety, Augur-aware refactoring"
# nickname_candidates = ["dev", "coder"]  # optional
```

The agent's instructions are written to `.codex/agents/{name}.md` (Codex reads `AGENTS.md` files from subdirectories). Model selection in Codex is global or per-profile, not per-agent — the adapter sets the profile's model via `model_mapping.yaml`.

#### Claude Code → Cursor

Cursor 2.4+ natively reads `.claude/agents/` — agents mastered by Claude Code work in Cursor without explicit sync. For agents mastered by other clients:

| Source field | Cursor equivalent | Notes |
|-------------|-------------------|-------|
| `model` | `model` | Via model_mapping.yaml; Cursor accepts specific model IDs |
| `mode: plan` | `readonly: true` | Direct mapping |
| `mode: auto` | `readonly: false` | Default |
| Body | Body | Preserved verbatim |
| `description` | `description` | Extracted from blockquote |

Cursor-specific: `is_background: true` maps to nothing in Claude Code (background execution is via the Agent tool).

#### Reverse: Non-Claude → Claude Code

When a Gemini-mastered agent syncs to Claude Code:

| Gemini field | Claude Code equivalent |
|-------------|----------------------|
| `model: gemini-3-flash-preview` | `model: sonnet` (via reverse_lookup) |
| `tools: [read_file, grep_search]` | Append to Allowed Tools section |
| `tools: [mcp_augur_*]` | `mcpServers: [augur]` |
| `temperature: 0.2` | (omitted, unsupported) |
| `max_turns: 10` | (omitted, unsupported) |
| `timeout_mins: 5` | (omitted, unsupported) |
| Body | Body |

Mode inference from Gemini body: if body contains "MUST NOT modify files" or "advisory mode", set `mode: plan`. Otherwise `mode: auto`.

### 4. Sync Flow

Update `sync_subagents()` (currently Claude-Code-only in `dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/`) to a multi-directional flow:

```
CLIENT_AGENT_DIRS = {
    "claude-code": ".claude/agents",
    "gemini":      ".gemini/agents",
    "codex":       ".codex/agents",
    "cursor":      ".cursor/agents",
    "cline":       ".claude/agents",   # Cline reads Claude's dir
    "copilot":     ".github/agents",   # .agent.md files
    "opencode":    ".opencode/agents", # Markdown with mode field
    "antigravity": ".subagents",       # Markdown + manifest.json registry
    # Kimi uses YAML agent configs, not markdown — requires separate adapter logic
}
```

**Additional clients with agent support** (extend in Phase 2):

| Client | Agent format | Location | Key differences |
|--------|-------------|----------|-----------------|
| Copilot | `.agent.md` with YAML frontmatter (name, description, tools, MCP servers) | `.github/agents/` | GA in VS Code + JetBrains + CLI; supports sub-agents and agent hooks |
| OpenCode | Markdown files with `mode: primary\|subagent\|all`, model override | `.opencode/agents/` | Two built-in agents (Plan + Build); subagents via @mention or auto-dispatch |
| Kimi CLI | YAML config with `subagents:` block, isolated contexts | YAML agent files | Supports agent swarms (up to 100 sub-agents on K2.5); YAML not markdown |

| Antigravity | Markdown subagent definitions, `manifest.json` registry | `~/.subagents/`, `.subagents/`, `.agent/workflows/subagent-{name}.md` | Router-worker pattern; isolation per subagent; also reads GEMINI.md, AGENTS.md, CLAUDE.md |

**Clients without per-agent subagent files** (instruction-only, no agent sync needed):

| Client | What they have | Why no agent sync |
|--------|---------------|-------------------|
| Windsurf | AGENTS.md + Agent Skills + parallel Cascade sessions (Wave 13) | Single-agent Cascade architecture; Skills/rules loaded into one context, no independent subagent delegation |
| Claude Desktop | CLAUDE.md | Desktop app — no subagent dispatch capability |

**Algorithm:**

1. **Scan all client agent dirs.** For each `.md` file, read frontmatter.
2. **Classify.** If `x-augur-master` matches this directory's client → it's a master. If file contains `AUGUR-ADAPTED-COPY` → it's an adapted copy (skip). Otherwise → legacy file, treat as master for this client.
3. **Collect masters.** Deduplicate by agent name. If two clients both claim master for the same name, warn and prefer the one with the most recent `git log` timestamp.
4. **For each master agent:**
   a. Read the full file (frontmatter + body).
   b. Resolve the abstract tier from `model_mapping.yaml` reverse_lookup.
   c. For each target client (all enabled clients except the master):
      - Translate frontmatter fields per capability translation rules.
      - Map model via `model_mapping.yaml` tiers → target client.
      - Render adapted copy with `AUGUR-ADAPTED-COPY` marker.
      - Write to target client's agent dir.
5. **Build registry.** Parse all master agent files → `registry.json` (at `.claude/agents/registry.json` as today, but now includes `master_client` field per entry).
6. **Clean orphans.** Remove adapted copies whose master no longer exists.

### 5. Registry Schema Update

`registry.json` adds `master_client` per entry:

```json
[
  {
    "name": "developer",
    "mode": "auto",
    "model": "sonnet",
    "role": "executor",
    "master_client": "claude-code",
    "tools": ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]
  },
  {
    "name": "researcher",
    "mode": "auto",
    "model": "sonnet",
    "role": "advisor",
    "master_client": "gemini",
    "tools": ["Read", "Glob", "Grep"]
  }
]
```

### 6. Drift Detection

`sync_agents --check` extended to verify:
- Every master agent has adapted copies in all enabled target clients
- Every adapted copy matches what would be generated from its master
- No adapted copy exists without a corresponding master
- Model mapping file is valid YAML with all required tiers

## Consequences

### Positive

- Any client can author agents — Gemini users can create agents that sync to Claude Code and Cursor
- Model mapping is explicit and auditable — no hardcoded model assumptions
- Consistent with ADR-426 skill mastering — same `x-augur-master` pattern, same `AUGUR-ADAPTED-COPY` marker
- Cursor gets agents for free (reads `.claude/agents/` natively) — minimal sync overhead
- Registry includes provenance (`master_client`) for debugging

### Negative

- Model mapping is manual maintenance — new model releases require updating `model_mapping.yaml`
- Capability translation is lossy — Gemini's `temperature`, `max_turns`, `timeout_mins` have no Claude Code equivalent and are silently dropped
- Codex agent format (TOML config) is fundamentally different from markdown files — the adapter is more complex

### Risks

- **Gemini agents are experimental.** The `.gemini/agents/` format may change. Mitigated by: adapter abstraction isolates format changes to one file.
- **Model tier mapping is approximate.** `gemini-3-flash-preview` is not exactly equivalent to `sonnet`. Mitigated by: this is a best-effort mapping, not a guarantee of identical behavior. Users can override with explicit model IDs in the adapted copy.
- **Dual master conflict.** Two clients claiming master for the same agent name. Mitigated by: warning + git timestamp tiebreak, and this should be rare since agents typically originate in one client.

## Alternatives Considered

### Alternative 1: Claude Code as Permanent Master

Keep `.claude/agents/` as the only source. Other clients receive adapted copies but can never be masters. Rejected: violates ADR-426's multi-master principle. Users who primarily work in Gemini or Codex should be able to author agents natively.

### Alternative 2: Abstract Agent Format

Define a client-neutral `.augur/agents/*.yaml` format that no client reads natively. All client-specific files are generated from it. Rejected: adds a layer of indirection. The whole point of ADR-426 is that skills/agents feel native to the platform that created them.

### Alternative 3: Model Mapping in Each Agent File

Each agent file declares its own per-client model mapping instead of a central config. Rejected: duplicates mapping across 14+ agents. Model releases affect all agents simultaneously — central config is the right granularity.

### Alternative 4: No Model Mapping — Use Abstract Tiers Everywhere

All clients receive `model: standard` and resolve it locally. Rejected: most clients don't understand abstract tier names. Claude Code doesn't know what `standard` means — it needs `sonnet`.

## References

- ADR-426: Client-Native Skill Mastering — the multi-master pattern this extends
- ADR-429: Multi-Client Memory System — cross-client data flow precedent
- ADR-460: Agent Tier Operationalization — tier system this builds on
- ADR-461: MCP-Based Skill Sync — parallel skill sync infrastructure
- ADR-186: Sync Agents Refactor — the sync_agents package architecture
- [Gemini CLI Subagents Docs](https://geminicli.com/docs/core/subagents/)
- [Codex CLI Configuration Reference](https://developers.openai.com/codex/config-reference)
- [Cursor Subagents Docs](https://cursor.com/docs/context/subagents)

## Implementation Prompt

**Team name**: `adr-464-cross-client-agents`

### Phase 1: Model Mapping and Master Declaration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `model_mapping.yaml` with all tiers, client model IDs, and reverse lookup | `config/agents/model_mapping.yaml` |
| 1.2 | developer | medium | Add `x-augur-master: claude-code` to all 14 existing agent `.md` files | `.claude/agents/*.md` |
| 1.3 | developer | medium | Add `model_mapping` loader to sync_agents package — read YAML, expose `resolve_model(from_client, to_client, model_name)` and `resolve_tier(client, model_name)` | `dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/model_mapping.py` |
| 1.4 | dev-test | low | Validate: all 14 agents have `x-augur-master`, model_mapping.yaml parses, resolve functions return correct values | — |

### Phase 2: Capability Translation Adapters
**Strategy**: PARALLEL (each adapter is independent)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Implement Gemini agent adapter: `sync_subagents()` generates `.gemini/agents/*.md` from master files using capability translation rules and model mapping | `…/sync_agents/adapters/gemini.py` |
| 2.2 | developer | medium | Implement Codex agent adapter: `sync_subagents()` generates `.codex/agents/*.md` and updates config.toml `[agents]` section | `…/sync_agents/adapters/codex.py` |
| 2.3 | developer | low | Implement Cursor agent adapter: `sync_subagents()` generates `.cursor/agents/*.md` (skip for agents already in `.claude/agents/` since Cursor reads that natively) | `…/sync_agents/adapters/cursor.py` |
| 2.4 | developer | medium | Implement reverse sync: read non-Claude master agents, translate to Claude Code format, write to `.claude/agents/` as adapted copies | `…/sync_agents/adapters/claude_code.py` |

### Phase 3: Multi-Directional Sync Engine
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Refactor `sync_subagents()` in engine.py: scan all `CLIENT_AGENT_DIRS`, classify master/adapted/legacy, collect masters, dispatch to target adapters | `…/sync_agents/engine.py` |
| 3.2 | developer | medium | Update registry.json generation to include `master_client` field per entry | `…/sync_agents/adapters/claude_code.py`, `…/sync_agents/engine.py` |
| 3.3 | developer | medium | Extend `--check` drift detection for agent sync (master→adapted consistency, orphan detection) | `…/sync_agents/engine.py` |

### Phase 4: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | dev-test | medium | Unit tests: model mapping resolution, capability translation for each adapter, registry schema | `src/tests/test_agent_sync.py` |
| 4.2 | dev-test | medium | Integration test: run `sync_agents --subagents`, verify files generated in all client dirs with correct format | — |
| 4.3 | validator | deep | End-to-end: create a test agent mastered by Gemini, run sync, verify Claude Code adapted copy has correct model/mode/tools | — |

### Completion Criteria

- [ ] All 14 existing agents have `x-augur-master: claude-code` in frontmatter
- [ ] `config/agents/model_mapping.yaml` exists with fast/standard/deep tiers for all 7 agent-capable clients
- [ ] `resolve_model()` correctly maps between any two clients
- [ ] `sync_agents --subagents` generates agents in `.gemini/agents/`, `.codex/agents/`, `.cursor/agents/`
- [ ] Adapted copies include `AUGUR-ADAPTED-COPY` marker
- [ ] Gemini agents have correct frontmatter: `name`, `description`, `model`, `tools`
- [ ] Codex agents have `.codex/agents/*.md` instruction files
- [ ] Cursor agents in `.cursor/agents/` have `model`, `readonly`, `description`
- [ ] `registry.json` includes `master_client` field per entry
- [ ] Reverse sync works: a Gemini-mastered agent generates a Claude Code adapted copy with correct model/mode
- [ ] `sync_agents --check` detects drift in agent adapted copies
- [ ] No regression in existing skill sync
- [ ] ADR status updated to Implemented
