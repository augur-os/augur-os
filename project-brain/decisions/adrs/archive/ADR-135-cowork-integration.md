---
status: Implemented
date: '2026-02-22'
deciders:
- Project team
related:
- ADR-130 (Action Button Dispatch Modes)
- ADR-134 (Dispatch Escalation Pattern)
- ADR-092 (CLI Agent Live Testing)
- ADR-014 (MCP Instance Management and Transport)
hub: null
tags:
- claude
- cowork
- integration
superseded_by: null
---

# ADR-135: Claude Cowork Integration

## Context

Augur's dashboard currently dispatches AI tasks to CLI agents (Claude Code, Cursor, Antigravity, etc.) via the IDE bridge (ADR-130) with automatic tier escalation (ADR-134). Claude Cowork — Anthropic's agentic desktop tool built into Claude Desktop — launched in January 2026 and shares the same plugin format as Claude Code but targets non-developer knowledge workers through a GUI interface.

Current integration gaps:

1. **No Cowork dispatch target**: The IDE bridge has 10 adapter entries (`claude_code`, `cursor`, `claude_desktop`, etc.) but treats Claude Desktop as a passive MCP client, not an active dispatch target for Cowork tasks. The `claude_desktop` adapter detects install/running status but cannot send prompts to Cowork's agent loop.

2. **No plugin export**: Augur's 17 hubs, 50+ skills, and 80+ slash commands are structured for Claude Code consumption (CLAUDE.md, `.claude/skills/`, `.agent/workflows/`). Cowork uses `.claude-plugin/plugin.json` manifests with `commands/`, `skills/`, and `.mcp.json` — a compatible but distinct format. Augur cannot be installed as a Cowork plugin today.

3. **MCP transport gap**: Cowork connects to MCP servers via the Claude Desktop config (`claude_desktop_config.json`). Augur's MCP server already supports stdio, SSE, and streamable-http transports with OAuth — but there is no automated setup flow for Cowork connections and no plugin `.mcp.json` that Cowork can auto-discover.

4. **Audience mismatch**: Augur's action buttons and prompts assume a developer-oriented IDE context with full filesystem access. Cowork users grant access to a single folder and expect GUI-driven interactions. Action prompts need adaptation for Cowork's scoped execution model.

## Decision

### 1. Cowork Plugin Export Pipeline

Create `plugins/ai/skills/ai_bridge/scripts/export_cowork_plugin.py` that generates a distributable `.claude-plugin` package from Augur's internal structure.

**Mapping rules:**

| Augur Source | Cowork Target |
|---|---|
| `plugins/*/skills/*/SKILL.md` + `modules/` | `skills/{skill-name}/SKILL.md` |
| `.claude/skills/*/SKILL.md` (mounted) | `skills/{skill-name}/SKILL.md` |
| `.agent/workflows/*.md` (core commands) | `commands/{command}.md` |
| `.claude/agents/*.md` | `agents/{agent}.md` |
| MCP server config | `.mcp.json` |
| CLAUDE.md (project instructions) | Folder instructions summary |

**Actions:**
- Create `plugins/ai/skills/ai_bridge/scripts/export_cowork_plugin.py` — reads plugin registry, generates `.claude-plugin/plugin.json` manifest, copies/transforms skill files into Cowork format
- Create `plugins/ai/skills/ai_bridge/augur/data/cowork/plugin.json.template` — manifest template with version, description, capabilities
- Create `plugins/ai/skills/ai_bridge/augur/data/cowork/README.md` — plugin README shown in Cowork marketplace
- Add `/dev-cowork-export` slash command to run the export pipeline

**Generated plugin structure:**
```
augur-cowork-plugin/
├── .claude-plugin/
│   └── plugin.json           # Manifest: name, version, description, capabilities
├── commands/
│   ├── focus.md              # /focus command adapted for Cowork
│   ├── learn.md              # /learn command
│   ├── rag.md                # /rag search command
│   └── start.md              # /start onboarding
├── skills/
│   ├── career/SKILL.md       # Career hub skill
│   ├── finance/SKILL.md      # Finance hub skill
│   ├── health/SKILL.md       # Health hub skill
│   └── ...                   # One skill per enabled hub
├── agents/
│   ├── researcher.md         # Research agent profile
│   └── developer.md          # Developer agent profile
├── .mcp.json                 # Points to Augur MCP server
└── hooks/
    └── hooks.json            # Post-task hooks (sync results back to Augur)
```

**Skill transformation rules:**
- Strip developer-only references (git commands, CI/CD, test runners)
- Preserve domain knowledge, procedures, and data file references
- Rewrite file paths from absolute Augur paths to relative `~/Augur/` references
- Include only skills from enabled hubs (read per-skill `.config` files, ADR-230)

### 2. Cowork Dispatch Target

Add `cowork` as a first-class dispatch mode in the IDE bridge, distinct from `claude_desktop` (passive MCP client).

**Detection:**
- Cowork runs inside Claude Desktop — detect via the same process check but distinguish by checking for the Cowork feature flag in the Claude Desktop config (`~/Library/Application Support/Claude/config.json` on macOS, `%APPDATA%/Claude/config.json` on Windows)
- Add `cowork` entry to `config/agents/ide_integrations.yaml`

**Dispatch mechanism:**
- Cowork accepts tasks via its folder-scoped agent loop — dispatch by writing a task file to the Cowork-watched folder
- Create `plugins/ai/skills/ai_bridge/augur/adapters/cowork.py` — adapter that writes prompt files to a designated dispatch directory (`runtime/cowork-dispatch/`)
- Cowork's folder instructions include a rule to check `runtime/cowork-dispatch/` for pending tasks on startup
- Adapt `useActionRunner` to include `cowork` as a dispatch target when detected

**Actions:**
- Create `plugins/ai/skills/ai_bridge/augur/adapters/cowork.py` — CoworkAdapter extending BaseAdapter
- Modify `plugins/ai/skills/ai_bridge/scripts/ide_bridge.py` — add Cowork detection and dispatch path
- Modify `config/agents/ide_integrations.yaml` — add `cowork` entry
- Modify `src/dashboard/hooks/useIdeBridge.ts` — include Cowork in IDE detection results
- Modify `src/dashboard/components/ActionDialogView.tsx` — show Cowork option in dispatch picker

### 3. MCP Connection Auto-Setup

Automate the process of connecting Cowork to Augur's MCP server.

**Approach:**
- Augur's MCP server already supports streamable-http transport on a configurable port (default: 6161)
- Generate a `.mcp.json` in the exported plugin that points to `http://localhost:6161` with streamable-http transport
- For local use: stdio transport via the existing `claude_desktop_config.json` injection (already implemented in `claude_desktop.py`)
- For plugin distribution: remote MCP via streamable-http with optional OAuth

**Actions:**
- Modify `plugins/ai/skills/ai_bridge/augur/adapters/claude_desktop.py` — add method to write Cowork-compatible `.mcp.json`
- Create `plugins/ai/skills/ai_bridge/augur/data/cowork/mcp.json.template` — MCP connection template with transport options
- Add MCP connection setup to the export pipeline (Phase 1)

### 4. Prompt Adaptation Layer

Action prompts written for Claude Code assume full project access and developer tools. Cowork operates in a scoped folder with GUI-oriented output.

**Adaptation rules:**
- Replace `Edit tool` / `Write tool` references with Cowork-native file operations
- Replace terminal commands with Cowork-compatible alternatives
- Add output formatting hints (Cowork renders rich markdown in its GUI)
- Scope file references to the granted folder path
- Remove references to git, npm, pytest, and other developer tooling

**Implementation:**
- Create `src/dashboard/lib/prompt-adapter.ts` — transforms action prompts based on target dispatch context
- The adapter reads the action's `dispatch` field and applies context-specific transformations
- For `cowork` dispatch: apply scoping rules, strip dev references, add GUI formatting hints
- For `ide` dispatch (Claude Code, Cursor): no transformation (current behavior)

**Actions:**
- Create `src/dashboard/lib/prompt-adapter.ts` — prompt transformation based on dispatch target
- Modify `src/dashboard/hooks/useActionRunner.ts` — pipe prompts through adapter before dispatch
- Add adapter tests to `tests/dashboard/unit/`

### 5. Bidirectional Result Sync

When Cowork completes a task, results need to flow back into Augur's data layer.

**Approach:**
- Cowork writes results to files in the granted folder
- A `hooks.json` in the plugin defines post-task hooks that call Augur's MCP tools to ingest results
- The dashboard polls for result files (reuse ADR-134's `output-polling.ts`)
- MCP tool `sync-cowork-results` reads completed task files and updates Augur's plugin data directories

**Actions:**
- Create `src/mcp/augur_mcp/domain/cowork.py` — MCP tools: `sync-cowork-results`, `get-cowork-status`
- Create `plugins/ai/skills/ai_bridge/augur/data/cowork/hooks.json` — post-task hook definitions
- Modify `src/dashboard/lib/output-polling.ts` — add Cowork result directory to poll targets

### 6. LLM-Powered Collateral Routing

When a user points Cowork at the Augur root folder and runs a task, Cowork generates collateral files (slides, docs, HTML tables, images, etc.) at the repo root. Currently, the `/dev-merge` workflow (step 7.5) and `cleanup_collateral.py` → `enforce_root_structure()` blindly move all non-whitelisted root files to `runtime/garbage_collector/` or `.agent/archive/` where they are eventually pruned. These files are valuable work product — not garbage.

**Current flow (broken):**
```
Cowork generates augur-elevator-pitch.pptx, comparison-table.html at repo root
  → user runs /merge all
  → step 7.5 garbage-collect moves stray files to runtime/garbage_collector/
  → files sit there, pruned after 7 days by nightly cleanup
  → work product lost
```

**New flow (LLM-analyzed routing integrated into /merge all):**
```
Cowork generates augur-elevator-pitch.pptx, comparison-table.html at repo root
  → user runs /merge all
  → NEW step 7.5: detect stray root files (non-whitelisted)
  → for each file: build context bundle (filename, extension, file content/preview,
    git diff summary of this merge, recent commit messages, branch name)
  → single LLM call (oneshot) classifies ALL stray files in one batch:
    {
      "augur-elevator-pitch.pptx": { "skill": "venture-augur", "hub": "professional", "reason": "elevator pitch is a venture/sales asset" },
      "augur-elevator-pitch.docx": { "skill": "venture-augur", "hub": "professional", "reason": "companion document to the pitch deck" },
      "comparison-table.html": { "skill": "venture-augur", "hub": "professional", "reason": "competitive comparison for market positioning" }
    }
  → files moved to plugins/professional/skills/venture-augur/augur/data/assets/
  → auto RAG indexing (ADR-127) picks up the new files
  → files searchable via /rag "elevator pitch", /rag "comparison table"
```

**Why LLM, not heuristics:**
- Filename alone is ambiguous — `comparison-table.html` could belong to venture, career (job comparison), or finance (investment comparison). Only the merge context reveals the correct skill.
- The LLM sees the full picture: what code was changed in this session, what the commit messages describe, what the file contents contain. It routes with the same understanding the user has.
- Cost is negligible: one oneshot call (~2K tokens) per merge with stray files. Most merges have 0-3 stray files.

**Integration point — `/dev-merge` step 7.5:**

Replace the current blind garbage-collect loop in step 7.5 with an LLM classification step. This is the natural hook because:
1. All commits are already done — the git diff is complete and available as context
2. The merge workflow already handles stray root files (just moves them to `runtime/garbage_collector/`)
3. The `/merge all` invocation guarantees this runs — no separate hook or daemon needed

**LLM classification prompt (assembled by the routing script):**

```
You are classifying work product files generated during a coding session.

## Session context
Recent commits in this merge:
{git_log_summary}

Files changed in this session:
{git_diff_stat}

Branch name: {branch_name}

## Available skills (routing targets)
{skill_registry: name, hub, description for each enabled skill}

## Files to classify
{for each stray file: filename, extension, size, first 500 chars of content (text files) or "binary" (non-text)}

## Task
For each file, determine which skill it belongs to. Return JSON:
{
  "filename": { "skill": "skill-name", "hub": "hub-name", "reason": "one sentence" }
}

If a file genuinely doesn't belong to any skill (e.g., temp scratch file), set skill to "_archive".
```

**Execution via dispatch escalation (ADR-134):**
- Tier 1 (oneshot): Send classification prompt via `send-ide-prompt` — cheapest, fastest
- Tier 0 (auto-repair): Validate JSON output, strip markdown fences if present
- Tier 2 (fallback): If oneshot fails or returns invalid JSON, retry via embedded CLI
- No Tier 3 needed — classification is a simple structured task

**File content extraction for the prompt:**
- Text files (`.html`, `.md`, `.txt`, `.csv`): include first 500 characters
- Office documents (`.docx`): extract text via `python-docx` if available, else filename-only
- Presentations (`.pptx`): extract slide titles via `python-pptx` if available, else filename-only
- Binary files (`.png`, `.jpg`, `.pdf`): filename and size only
- Total prompt stays under 4K tokens even with 10+ stray files

**Post-classification file routing:**
1. Parse LLM JSON response
2. For each file where `skill != "_archive"`:
   - Resolve target: `plugins/{hub}/skills/{skill}/augur/data/assets/`
   - Create `assets/` directory if it doesn't exist
   - Move file: `shutil.move(root/file, target/file)`
   - Log: `"Routed {file} → {skill} ({reason})"`
3. For `_archive` files: move to `runtime/garbage_collector/` as before
4. Commit routed files in the sync step (step 8) with message: `chore(assets): route session collateral to skill data dirs`

**RAG auto-indexing:**
- Files routed to `plugins/*/skills/*/augur/data/assets/` are automatically picked up by the RAG indexer (ADR-127) on its next scan cycle
- No additional configuration needed — the indexer already walks plugin data directories
- Supported formats: `.md`, `.txt`, `.pdf`, `.docx`, `.html` are indexed as text; binary formats (`.pptx`, `.xlsx`) are indexed by filename/metadata only
- After routing + indexing, files are searchable via `/rag "elevator pitch"` or any MCP RAG tool

**Actions:**
- Create `src/scripts/classify_collateral.py` — LLM-powered classification engine: builds context bundle, calls oneshot, parses response, routes files
- Modify `.agent/workflows/dev-merge.md` — replace step 7.5 garbage-collect loop with call to `classify_collateral.py`; route classified files, archive the rest
- Modify `plugins/dev/skills/devops/scripts/cleanup_collateral.py` — update `enforce_root_structure()` to call `classify_collateral.py` instead of blind archiving (for non-merge cleanup paths)
- Add `classify-collateral` MCP tool to `src/mcp/augur_mcp/domain/cowork.py` — exposes classification for manual re-routing from dashboard
- Ensure `plugins/*/skills/*/augur/data/assets/` directories exist for major skills (venture, career, finance, consulting, health)

## Consequences

**Positive:**
- Augur becomes accessible to non-developer users via Cowork's GUI without requiring terminal skills
- 50+ skills and 80+ commands become installable as a single Cowork plugin
- MCP tools remain the single backend — no code duplication between Claude Code and Cowork paths
- Dispatch escalation (ADR-134) naturally extends to Cowork as another tier option
- Plugin export pipeline enables future marketplace distribution
- Cowork-generated collateral (slides, docs, tables) is LLM-analyzed using full session context (git diff, commit messages, file content) and routed to the correct skill — then auto-indexed for RAG search
- Collateral routing is integrated into `/merge all` — zero extra steps for the user, files just appear in the right place
- Reuses ADR-134 dispatch escalation for the classification call — oneshot by default, auto-repair on bad JSON, embedded CLI fallback

**Negative:**
- Prompt adaptation adds a transformation layer that must be maintained per-dispatch target
- Cowork's folder-scoped model limits some skills that assume full filesystem access (e.g., git operations, cross-project analysis)
- Two plugin formats to maintain: Augur's internal structure and the exported `.claude-plugin` package
- Collateral routing adds one LLM call (~$0.01-0.02) per merge when stray files exist — negligible but non-zero cost
- Cowork is still in "research preview" — API surface may change

**Neutral:**
- The MCP server infrastructure (stdio, SSE, streamable-http) already exists and requires no transport changes
- Existing Claude Desktop adapter provides the detection foundation
- Plugin export is one-directional (Augur → Cowork) — Augur remains the source of truth

## Implementation Order

```
Phase 1: Plugin Export Pipeline
├── Step 1: Create plugin.json template and export script
├── Step 2: Implement skill/command format transformation
├── Step 3: Generate .mcp.json with transport config
└── Step 4: Add /dev-cowork-export slash command

Phase 2: Cowork Dispatch (depends on Phase 1)
├── Step 5: Create CoworkAdapter with detection and dispatch
├── Step 6: Add cowork to ide_integrations.yaml and IDE bridge
└── Step 7: Update ActionDialogView with Cowork option

Phase 3: Prompt Adaptation (depends on Phase 2)
├── Step 8: Create prompt-adapter.ts with dispatch-aware transforms
└── Step 9: Wire adapter into useActionRunner

Phase 4: Result Sync (depends on Phase 2)
├── Step 10: Create MCP tools for Cowork result ingestion
├── Step 11: Add hooks.json for post-task callbacks
└── Step 12: Extend output-polling for Cowork results

Phase 6: LLM-Powered Collateral Routing (parallel with Phases 3-4)
├── Step 13: Create classify_collateral.py — LLM classification engine with context bundling
├── Step 14: Update /dev-merge step 7.5 to call classify_collateral.py instead of blind move
├── Step 15: Update cleanup_collateral.py enforce_root_structure() for non-merge paths
├── Step 16: Add classify-collateral MCP tool
└── Step 17: Ensure augur/data/assets/ dirs exist for major skills

Phase 7: Verification (depends on Phases 1-6)
├── Step 18: Run export pipeline and validate plugin structure
├── Step 19: Test Cowork detection and dispatch flow
├── Step 20: Test LLM collateral classification end-to-end (sample files → oneshot → JSON → route)
├── Step 21: Verify MCP connection via streamable-http
└── Step 22: Run stale path scanner
```

## Alternatives Considered

### 1. Direct MCP Only (No Plugin Export)

Rely solely on Augur's MCP server connected to Claude Desktop — no `.claude-plugin` package.

**Rejected because:** Cowork's plugin system provides discoverability (marketplace), structured commands, and skill loading that raw MCP tools don't. Users get 358 MCP tools dumped into context with no organization vs. curated skills and commands in the plugin format. The plugin format is also the path to marketplace distribution.

### 2. Cowork-Native Rewrite

Rebuild Augur's skills natively in the `.claude-plugin` format, maintaining two separate codebases.

**Rejected because:** Unsustainable maintenance burden. Augur has 50+ skills across 17 hubs — maintaining parallel implementations would double the work. An export pipeline keeps Augur as the single source of truth while generating the Cowork-compatible format automatically.

### 3. Cowork as Primary, Claude Code as Secondary

Invert the architecture: make Cowork the default execution target and Claude Code the fallback.

**Rejected because:** Cowork's folder-scoped model and research-preview status make it unsuitable as the primary execution target. Claude Code's full project access, terminal integration, and production-ready status make it the correct default. Cowork is an additional distribution channel, not a replacement.

## References

- [ADR-130: Action Button Dispatch Modes](ADR-130-action-button-dispatch-modes.md)
- [ADR-134: Dispatch Escalation Pattern](ADR-134-dispatch-escalation-pattern.md)
- [ADR-092: CLI Agent Live Testing](ADR-092-cli-agent-live-testing.md)
- [ADR-014: MCP Instance Management and Transport](ADR-014-mcp-instance-management-and-transport.md)
- ADR-230: Per-Skill Config Files
- [Claude Cowork Plugin Docs](https://code.claude.com/docs/en/plugins)
- [Anthropic Knowledge Work Plugins](https://github.com/anthropics/knowledge-work-plugins)
- [MCP Connector Documentation](https://docs.claude.com/en/docs/agents-and-tools/mcp-connector)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-135: Claude Cowork Integration**.

Read the full ADR: `docs/decisions/ADR-135-cowork-integration.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-135-cowork", description="Implementing ADR-135: Claude Cowork Integration")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-135-cowork", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-135-cowork team.
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

**Team name**: `adr-135-cowork`

#### Phase 1: Plugin Export Pipeline
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create plugin.json manifest template with name, version, description, capabilities fields | `plugins/ai/skills/ai_bridge/augur/data/cowork/plugin.json.template` |
| 1.2 | developer | high | Build export script that reads plugin registry, transforms skills to Cowork format, generates .claude-plugin directory | `plugins/ai/skills/ai_bridge/scripts/export_cowork_plugin.py` |
| 1.3 | developer | medium | Generate .mcp.json template pointing to Augur MCP server via streamable-http on localhost:6161 | `plugins/ai/skills/ai_bridge/augur/data/cowork/mcp.json.template` |
| 1.4 | devops | low | Add /dev-cowork-export slash command that invokes the export pipeline | `.claude/skills/dev-cowork-export/SKILL.md` or `.agent/workflows/dev-cowork-export.md` |

#### Phase 2: Cowork Dispatch (depends on Phase 1)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create CoworkAdapter extending BaseAdapter with detection (process check + config flag) and dispatch (write prompt to dispatch dir) | `plugins/ai/skills/ai_bridge/augur/adapters/cowork.py` |
| 2.2 | developer | medium | Add cowork entry to IDE integrations config with health checks | `config/agents/ide_integrations.yaml` |
| 2.3 | developer | medium | Update IDE bridge script to include Cowork detection and prompt dispatch path | `plugins/ai/skills/ai_bridge/scripts/ide_bridge.py` |
| 2.4 | developer | medium | Update useIdeBridge hook to include Cowork in detection results and ActionDialogView to show Cowork dispatch option | `src/dashboard/hooks/useIdeBridge.ts`, `src/dashboard/components/ActionDialogView.tsx` |

#### Phase 3: Prompt Adaptation (depends on Phase 2)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Create prompt adapter that transforms action prompts based on dispatch target — strip dev references, scope file paths, add GUI formatting for Cowork context | `src/dashboard/lib/prompt-adapter.ts` |
| 3.2 | developer | medium | Wire prompt adapter into useActionRunner dispatch flow | `src/dashboard/hooks/useActionRunner.ts` |

#### Phase 4: Result Sync (depends on Phase 2)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Create MCP tools for Cowork result ingestion: sync-cowork-results, get-cowork-status | `src/mcp/augur_mcp/domain/cowork.py` |
| 4.2 | developer | low | Create hooks.json for post-task callbacks that trigger result sync | `plugins/ai/skills/ai_bridge/augur/data/cowork/hooks.json` |
| 4.3 | developer | medium | Extend output-polling.ts to include Cowork result directory as poll target | `src/dashboard/lib/output-polling.ts` |

#### Phase 6: LLM-Powered Collateral Routing (parallel with Phases 3-4)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 6.1 | developer | high | Create LLM-powered classification engine: builds context bundle (stray files + git diff summary + commit messages + skill registry), calls oneshot via send-ide-prompt, parses JSON response, routes files to skill assets dirs. Uses ADR-134 escalation (oneshot → auto-repair → embedded CLI). Extracts text previews from .html/.md/.csv, slide titles from .pptx via python-pptx, text from .docx via python-docx, filename-only for binaries. | `src/scripts/classify_collateral.py` |
| 6.2 | developer | medium | Update /dev-merge workflow: replace step 7.5 blind garbage-collect loop with call to classify_collateral.py. Routed files get committed in step 8 sync. Files classified as _archive still go to runtime/garbage_collector/. | `.agent/workflows/dev-merge.md` |
| 6.3 | developer | medium | Update cleanup_collateral.py: enforce_root_structure() calls classify_collateral.py for non-whitelisted files instead of blind archiving (covers non-merge cleanup paths) | `plugins/dev/skills/devops/scripts/cleanup_collateral.py` |
| 6.4 | developer | medium | Add classify-collateral MCP tool to cowork domain module for manual re-routing from dashboard | `src/mcp/augur_mcp/domain/cowork.py` |
| 6.5 | devops | low | Ensure augur/data/assets/ directories exist for major skills (venture, career, finance, consulting, health) with .gitkeep | `plugins/professional/skills/venture-augur/augur/data/assets/.gitkeep`, etc. |

#### Phase 7: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 7.1 | validator | low | Run export pipeline and validate generated plugin structure matches .claude-plugin spec |
| 7.2 | validator | low | Test collateral classification: place sample .pptx/.docx/.html at repo root, run classify_collateral.py with mock git context, verify LLM JSON response parses correctly and files route to correct skill assets dirs. Verify _archive files go to runtime/garbage_collector/. |
| 7.3 | validator | low | Run all tests: `pytest tests/src/`, `npm run build` |
| 7.4 | architect | low | Verify ADR intent matches implementation — all 6 decision sections covered |
| 7.5 | devops | low | Run stale path scanner: `python3 .github/scripts/scan_stale_paths.py --ci` |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Export pipeline generates valid `.claude-plugin` package
- [ ] Cowork detected in IDE bridge when Claude Desktop is running
- [ ] Prompt adapter correctly transforms prompts for Cowork context
- [ ] MCP connection works via streamable-http transport
- [ ] LLM collateral classification routes test files to correct skill assets directories
- [ ] Files classified as _archive go to runtime/garbage_collector/ (not silently deleted)
- [ ] /merge all workflow invokes classify_collateral.py at step 7.5
- [ ] RAG indexer picks up routed files on next scan cycle
- [ ] No orphaned files or broken references
- [ ] Stale path scanner clean
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-135-cowork-integration.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
