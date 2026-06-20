---
status: Implemented
date: '2026-03-06'
deciders:
- Gur Sannikov
- Claude
related: []
hub: null
tags:
- mcp
- tool
- hygiene
- client
- aware
superseded_by: null
---

# ADR-250: MCP Tool Hygiene and Client-Aware Filtering

**Related ADRs**: ADR-176 (adaptive loop engine), ADR-163 (plugin decentralization), ADR-238 (skill standards loop), ADR-282 (auto-loop consolidation), ADR-129 (plugin enable/disable)

## Context

Augur's MCP tool surface is ~254 tools across 23 plugins and growing as the dashboard evolves. AI agents both produce and consume these tools. Four maintenance problems compound over time:

1. **Adding a new tool** requires touching multiple files (MCP `__init__.py`, `augur.yaml`, `mcp_tool_groups.yaml`) with no validation that the registration is complete or consistent
2. **Discovery** — no way to check if a tool already covers a need before creating a duplicate within a plugin
3. **Deprecation** — no lifecycle; dead tools linger indefinitely
4. **Consistency** — naming conventions (`get-X` vs `fetch-X` vs `find-X`), parameter patterns, and descriptions vary within plugins

Some IDE clients impose tool count limits, making hygiene a scaling concern.

### Tool filtering is broken

The MCP server has 4 filtering layers, but only 2 are active:

| Layer | File | Status |
|-------|------|--------|
| 1. Category toggles | `mcp_tools.yaml` | Active — disables tool categories at registration |
| 2. Tool filter | `tool_filter.py` | Active — enforces layer 1 via `FilteredToolDecorator` |
| 3. Context controller | `tool_controller.py` | **Dead code** — initialized on server.py:909 but `get_active_tools()` is never called for filtering |
| 4. Page scoping | `mcp_tool_groups.yaml` | **Dead config** — no consumer at runtime |

The tool controller (`tool_controller.py`, ~430 lines) and page scoping config (`mcp_tool_groups.yaml`) were built for a pre-lazy-loading world. CLI/IDE clients like Claude Code now have protocol-level deferred tool loading — tools are listed by name but schemas aren't loaded until called. Page-level filtering in these clients is both unnecessary and harmful: it blocks cross-domain operations (e.g., creating a Reminder from a dev session).

However, the **Augur web chat client** does benefit from page-aware filtering because it lacks deferred loading and sends all tools in the system prompt. The two client modes have different needs:

| Client | Has deferred loading | Knows current page | Needs page filtering |
|--------|---------------------|-------------------|---------------------|
| CLI/IDE (Claude Code, Cursor, etc.) | Yes | No | No |
| Augur web chat | No | Yes | Yes |

Cross-plugin overlap is minimal because each plugin covers a distinct domain. The problem is intra-plugin entropy: naming drift, orphaned registrations, and unused tools accumulating within individual plugins.

## Decision

### New auto-command: `auto-mcp-hygiene`

A nightly auto-fix loop that runs **per plugin**, auditing and cleaning up MCP tool registrations. Assigned to the **code-quality** loop (existing, budget 18).

Tier: 1 (moderate trust — modifies code and config files)
Trigger: nightly

### Per-plugin scan and auto-fix

For each plugin at `plugins/{bundle}/skills/{skill}/` that has an MCP module:

#### 1. Naming normalization

Enforce `{verb}-{noun}` convention with a controlled verb vocabulary:
- `get`, `list`, `search`, `create`, `update`, `delete`, `run`, `check`
- Auto-rename synonyms: `fetch` to `get`, `find` to `search`, `remove` to `delete`, `execute` to `run`
- Update both the Python registration and `augur.yaml` tool declarations

#### 2. Registration completeness

Detect mismatches between:
- Tools registered in Python (`__init__.py`) but missing from `augur.yaml`
- Tools declared in `augur.yaml` but not registered in Python
- Auto-fix by adding missing declarations or removing orphaned entries

#### 3. Dead tool detection

Cross-reference tool names against execution logs in `runtime/logs/` to identify tools with zero invocations over the last 30 days. Auto-remove tools with zero usage that are also not referenced in `mcp_tool_groups.yaml` page scoping.

#### 4. Intra-plugin duplicate detection

Flag tools within the same plugin that have:
- Identical parameter signatures
- Names differing only by verb synonym (already caught by naming normalization)
- Descriptions with >80% token overlap

Merge duplicates by keeping the tool with more recent usage, removing the other, and updating all references.

#### 5. Commit

One commit per plugin with changes: `fix(adaptive): mcp-hygiene cleanup for {skill}`

### Client-aware tool filtering

Make the tool controller active only for web chat clients, and bypass it for CLI/IDE clients.

#### 1. Gate filtering on client ID

The MCP server already receives `--client-id` (e.g., `claude-code`, `cursor`, `codex`, `web-chat`). Add a check in the tool listing path:

- **CLI/IDE clients**: Register all enabled tools. No page scoping. Let the client's deferred loading handle context.
- **Web chat client**: Apply `tool_controller.get_active_tools(context)` with the current page from the request. Keep the 80-tool cap and `mcp_tool_groups.yaml` page scoping.

#### 2. Web chat passes page context

Web chat requests include the current dashboard page in the MCP context payload (e.g., `{"current_page": "/career"}`). The tool controller uses this to select relevant tool groups.

#### 3. Remove dead code paths

- Delete the `get_active_tools()` call ambiguity — make it explicit that filtering only runs for `client_id == "web-chat"`
- Clean up the hardcoded `plugin_prefixes` list in `tool_controller.py` line 265-288 — derive from plugin discovery instead
- Remove the default tool groups (`_get_default_tool_groups`) that reference non-existent tools (UI, BACKEND, CHAIN, etc.)

### Hardening report

Generate per-run report at `plugins/{bundle}/skills/{skill}/augur/data/hardening-reports/mcp_hygiene_{date}.yaml` with:
- Tools scanned, renamed, removed, merged
- Registration mismatches fixed
- Dead tools removed

### Files affected

- New: `plugins/observability/skills/daemon/scripts/ops/auto_mcp_hygiene.py` — the auto-command
- Modified: `plugins/observability/skills/daemon/augur.yaml` — register the auto-command with loop wiring
- Modified: `src/mcp/augur_mcp/server.py` — gate tool filtering on client ID
- Modified: `src/mcp/augur_mcp/tool_controller.py` — clean up dead defaults, derive plugin prefixes from discovery
- Modified per plugin (by the auto-fixer at runtime): `augur/mcp/__init__.py`, `augur.yaml`

## Consequences

### Positive
- Tool catalog stays clean without manual intervention
- Naming consistency enforced automatically
- Dead tools pruned before hitting client caps
- AI agents creating tools get immediate feedback via nightly validation
- CLI/IDE clients get full tool access — no more cross-domain blocking (e.g., creating a Reminder from a dev session)
- Web chat retains page-aware scoping where it actually helps

### Negative
- Auto-renaming tools could break external references (mitigated: references updated in same commit)
- Dead tool detection depends on log retention (30 days may miss seasonal tools)

### Neutral
- No cross-plugin analysis needed — each plugin is self-contained
- Fits existing adaptive loop infrastructure with no engine changes
- Tool controller stays in codebase but with a clear, narrower purpose (web chat only)

## Alternatives Considered

### 1. Consolidate tools into fewer mega-tools with action arguments
Rejected — reduces LLM tool-selection clarity and requires migrating all callers.

### 2. Per-plugin tool budgets enforced by CI
Rejected — adds centralized policy that conflicts with plugin autonomy. The hygiene loop achieves the same goal through cleanup rather than hard limits.

### 3. Cross-plugin overlap detection
Rejected — overlap between plugins is minimal since each covers a distinct domain. Not worth the complexity.

## Implementation Order

### Phase 1: Client-aware filtering
1. Add client ID check in `server.py` tool listing — bypass `tool_controller` for CLI/IDE clients
2. Wire web chat to pass `current_page` in MCP context
3. Clean up `tool_controller.py` — remove dead defaults, derive plugin prefixes from discovery
4. Test: CLI client sees all tools, web chat sees page-scoped tools

### Phase 2: Tool hygiene loop
5. Create `auto_mcp_hygiene.py` with scan + naming + completeness + dead-tool + duplicate logic
6. Register in daemon's `augur.yaml` as `auto-mcp-hygiene` with code-quality loop, tier 1, nightly trigger
7. Test against 2-3 plugins with known issues
8. Enable in nightly cycle

## Implementation Gaps

### Phase 1, Step 2: Web-chat `current_page` injection — UNIMPLEMENTED

The server-side plumbing exists: `_patched_list_tools` in `server.py` filters
tools when `ctx_mgr.client == WEB_CHAT_CLIENT`, and `context_manager.py` defines
`WEB_CHAT_CLIENT = "web-chat"` with `ClientCapability.NONE`.

However, **no client connects as `web-chat`**. The dashboard chat infrastructure
(FloatingChat, useCliChat, MCPBridge, MCPContextClient) all spawn CLI processes
via `/api/cli` which auto-detect as `claude_code`/`cursor`/etc. There is no
MCP client path that passes `--client-id web-chat` and injects `current_page`
on connection.

Implementing this requires: (a) a web-chat MCP client that connects with
`client_id=web-chat`, (b) automatic `current_page` injection on connection start
and page navigation, and (c) the tool_controller `get_active_tools()` to
actually filter by page (currently it adds all groups regardless of
`current_page`). This is not a small fix — it needs a new client transport path.

### Phase 2, Step 7: Tests — ADDED

52 unit tests added at `plugins/admin/skills/auto-mcp-hygiene/tests/test_mcp_hygiene.py`
covering all scan/fix functions, difficulty gating, OpsCommand protocol conformance,
and edge cases.

## References

- ADR-176: Adaptive Loop Engine
- ADR-129: Plugin Enable/Disable
- ADR-163: Plugin Decentralization
- ADR-238: Skill Standards Loop (similar per-plugin scan pattern)
- ADR-246: Auto-Loop Consolidation
- `src/mcp/augur_mcp/server.py` — MCP server, tool registration
- `src/mcp/augur_mcp/tool_controller.py` — context-aware filtering (currently dead code for CLI)
- `src/mcp/augur_mcp/tool_filter.py` — category toggle enforcement
- `src/mcp/augur_mcp/plugin_tools.py` — plugin tool discovery
- `config/dashboard/mcp_tool_groups.yaml` — page scoping config
- `config/system/adaptive_loops.yaml` — loop configuration
