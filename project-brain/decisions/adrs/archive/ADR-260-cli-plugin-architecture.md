---
status: Implemented
date: '2026-03-07'
deciders:
- Gur Sannikov
- Claude
related: []
hub: null
tags:
- cli
- plugin
- architecture
superseded_by: null
---

# ADR-260: CLI Plugin Architecture

**Related ADRs**: ADR-012 (Community Package Extraction), ADR-163 (Config Decentralization), ADR-254 (Agent Discovery Protocol), ADR-258 (Standalone CLI Package), ADR-250 (MCP Tool Hygiene)

## Context

The Augur CLI (`aug`) wraps MCP tools for command-line access. Three architectural gaps exist:

1. **CLI subcommands are hard-coded.** The only subcommand (`discover`) is an `if args.tool == "discover":` block in `src/cli.py`. Plugins cannot contribute CLI-specific commands. Adding a new subcommand requires modifying a centralized file.

2. **ADR-163 Phase 2-3 incomplete.** The decentralization ADR specified migrating tool metadata (groups, display names, modes) from centralized YAML files (`config/dashboard/mcp_tool_groups.yaml`, `tool_display_names.yaml`) to plugin-level declarations assembled at build time. The centralized files still exist (664 lines) with **25+ consumers** across the codebase — source code, tests, CI scripts, validator scripts, daemon health checks, and agent topic docs. All 44 plugin `augur.yaml` `mcp:` sections contain empty stubs (`tools: []`).

3. **No schema-driven tool help.** `aug <tool> --help` shows generic argparse output. MCP tools have rich `inputSchema` (Pydantic models) with parameter names, types, and descriptions, but this metadata is invisible to CLI users.

**Note:** Plugin tools are already wired. `server.py:674` calls `register_domain_tools()`, which calls `register_plugin_tools()` from `plugin_tools.py` (aliased as `register_dynamic_plugin_tools` in `domain/__init__.py:102`). No one-line fix is needed.

## Decision

### 1. Unified Plugin Entry Point for CLI Subcommands

Plugins contribute CLI subcommands via an optional `register_subcommands(subparsers)` function in their existing `augur/mcp/__init__.py`:

```python
# plugins/core/skills/discovery/augur/mcp/__init__.py

def register_tools(mcp, mcp_tool_interceptor, metrics):
    # existing MCP tools...

def register_subcommands(subparsers):
    """Optional — most plugins won't need this."""
    p = subparsers.add_parser("discover", help="Assemble the agent manifest")
    p.add_argument("--hub", help="Filter by hub")
    p.set_defaults(func=_run_discover)
```

**Why unified, not separate files:** The earlier design considered `augur/cli/__init__.py` as a separate entry point but rejected it. One file per plugin is simpler — 90%+ of plugins won't have subcommands, so no empty directories. The MCP entry point already handles plugin identity and loading.

Discovery: `src/cli_plugins.py` reuses the same scan pattern as `plugin_tools.py`, loads each `augur/mcp/__init__.py`, calls `register_subcommands()` if present. If two plugins register the same subcommand name, first-registered wins and a warning is logged.

### 3. Runtime Schema-Driven Tool Help

When a user runs `aug <tool> --help`:

1. CLI queries `mcp.list_tools()` for the tool's `inputSchema`
2. Renders each schema property as `--param-name TYPE  description`
3. Shows required/optional markers and the tool description

No cached registry. MCP schemas are the source of truth. Latency only affects `--help`, not execution.

**Fallback:** If the MCP server is unreachable (not running), print a clear error: `"MCP server not running. Start with: aug --server or augur-mcp"` instead of hanging.

### 4. Assembly-Time Metadata (ADR-163 Completion)

- `mount-plugins.ts` gains a tool assembly step that introspects plugin MCP modules
- Generates `config/dashboard/generated/assembled_tool_config.json`
- `augur.yaml` `mcp:` section stays minimal — only `max_tools` and optional display overrides (tool code is single source of truth)
- Delete centralized `config/dashboard/mcp_tool_groups.yaml` and `tool_display_names.yaml`
- Migrate **25+ consumer files** to read from generated assembly (see Impact Manifest for full list)

### 5. Subcommand Collision Handling

If two plugins attempt to register the same CLI subcommand name, the first plugin loaded wins. A warning is logged: `"Subcommand '{name}' already registered by {first_plugin}, skipping {second_plugin}"`. Plugin load order follows the alphabetical bundle scan in `PLUGIN_BUNDLES`.

### 6. No Framework Change

argparse stays. No Click/Typer adoption. The CLI is a thin MCP wrapper — the framework value comes from MCP tool schemas, not CLI argument parsing. The auto-generated help from `inputSchema` provides the same UX benefits as Typer's type-hint-driven help.

### 7. Infrastructure Tools Stay Centralized

The 62 static tools in `src/mcp/augur_mcp/core/` and `infrastructure/` are foundational cross-cutting operations (files, config, system, health, discovery). They are not plugin-specific and don't benefit from migration.

## Consequences

### Positive
- Plugins can contribute CLI subcommands without modifying centralized code
- `aug <tool> --help` shows actual parameters, not generic argparse output
- Centralized tool config files eliminated — tool code is single source of truth
- Consistent pattern: `augur/mcp/__init__.py` is the sole plugin capability entry point

### Negative
- Plugin subcommand discovery adds a scan at CLI startup
- Migrating 25+ consumers off centralized YAML requires careful per-file changes (source, tests, CI, validators, agent docs)
- Assembly step adds build-time complexity to `mount-plugins.ts`
- Schema help requires MCP server to be running (mitigated by clear error message)

### Neutral
- argparse stays — no new dependency
- `augur.yaml` `mcp.tools` sections remain empty stubs (intentional — assembly derives from code)
- Infrastructure tools remain centralized (may revisit in future)
- Plugin tools already wired — no server.py change needed

## Alternatives Considered

### Alternative 1: Separate `augur/cli/__init__.py` for subcommands
Each plugin with CLI subcommands would have a dedicated `augur/cli/__init__.py` alongside `augur/mcp/__init__.py`.
**Rejected:** Creates a second discovery path, second file per plugin, and empty directories for 90%+ of plugins that don't need subcommands. The unified entry point is simpler.

### Alternative 2: Adopt Click/Typer CLI framework
Replace argparse with Typer for auto-generated help from type hints and Pydantic integration.
**Rejected:** Adds a framework dependency for a CLI whose main job is `mcp.call_tool()`. The MCP tool `inputSchema` already provides the same metadata. Runtime schema rendering gives identical UX without the dependency.

### Alternative 3: Populate `augur.yaml` `mcp.tools` with tool names
Script-generate tool lists into each plugin's `augur.yaml` as the metadata source.
**Rejected:** Creates a second source of truth that drifts from the actual code. Assembly-time introspection of the code itself is more reliable and requires zero maintenance.

## References

- ADR-012: Community Package Extraction (plugin tool loading mechanism)
- ADR-163: Config Decentralization (Phase 2-3 completion)
- ADR-254: Agent Discovery Protocol (parent roadmap)
- ADR-258: Standalone CLI Package (CLI packaging)
- `src/mcp/augur_mcp/plugin_tools.py` — existing plugin tool loader (188 lines)
- `src/cli.py` — current CLI implementation
- `src/mcp/augur_mcp/domain/__init__.py` — existing plugin tool wiring (line 139)
- [Implementation Plan](../plans/2026-03-07-cli-plugin-architecture-plan.md)

## Impact Manifest

```yaml
patterns_deprecated:
  - pattern: "Hard-coded CLI subcommands in src/cli.py"
    replacement: "Plugin register_subcommands() in augur/mcp/__init__.py"
  - pattern: "Centralized mcp_tool_groups.yaml"
    replacement: "Generated assembled_tool_config.json from plugin introspection"

files_affected:
  modified:
    - src/cli.py                             # Subparser routing, schema help, remove hard-coded discover
    - src/dashboard/scripts/mount-plugins.ts # Tool assembly step
  created:
    - src/cli_plugins.py                     # CLI subcommand discovery
    - src/dashboard/scripts/mount/tool-assembly.ts  # Tool introspection
    - plugins/core/skills/discovery/augur/mcp/__init__.py  # discover subcommand
  deleted:
    - config/dashboard/mcp_tool_groups.yaml
    - config/dashboard/tool_display_names.yaml
  migrated_source:  # Source code consumers — must switch to assembled_tool_config.json
    - src/mcp/augur_mcp/context_manager.py
    - src/mcp/augur_mcp/tool_controller.py
    - src/mcp/augur_mcp/tool_filter.py
    - src/mcp/augur_mcp/infrastructure/mcp_management.py
    - src/mcp/augur_mcp/config.py
    - src/mcp/augur_mcp/compat.py
    - src/config/mcp_tools.py
    - src/config/paths.py
    - src/scripts/seed_tool_tiers.py
    - src/dashboard/lib/server/toolFilter.ts
    - src/dashboard/scripts/generate-hub-registry.ts
  migrated_tests:  # Test files referencing YAML — update or remove path references
    - tests/mcp/test_new_tools.py
    - tests/mcp/test_phase2_phase3_integration.py
    - tests/mcp/test_route_migration.py
    - tests/scripts/test_seed_tool_tiers.py
    - tests/dashboard/unit/chat/toolFilter.test.ts
  migrated_ci:  # CI/validation scripts — will break if YAML deleted without update
    - .github/scripts/ci_check.sh
    - .github/workflows/ci-lint.yml
    - plugins/dev/skills/validator/scripts/security/validate_mcp_config.py
    - plugins/observability/skills/daemon/scripts/mcp_health_check.py
    - plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py
  migrated_docs:  # Agent topic docs and references — update text references
    - docs/agent-topics/CONTEXT.md
    - docs/agent-topics/ARCHITECTURE.md
    - plugins/ai/skills/ai_bridge/augur/data/agent-topics/CONTEXT.md
    - plugins/ai/skills/ai_bridge/augur/data/agent-topics/ARCHITECTURE.md
    - plugins/observability/skills/observe/modules/context-budget.md
    - .antigravity/topics/CONTEXT.md
    - .antigravity/topics/ARCHITECTURE.md
    - .gemini/topics/CONTEXT.md
    - .gemini/topics/ARCHITECTURE.md
```

## Implementation Order

### Phase 1: CLI Subcommand Discovery (PARALLEL with Phase 2)
| Step | Task | Files |
|------|------|-------|
| 1.1 | Create `cli_plugins.py` with `discover_subcommands()` | `src/cli_plugins.py` |
| 1.2 | Wire subparsers into `src/cli.py` main() | `src/cli.py` |
| 1.3 | Extract `discover` into core/discovery plugin | `plugins/core/skills/discovery/augur/mcp/__init__.py` |
| 1.4 | Test plugin subcommand loading and discover migration | `tests/cli/test_cli_plugins.py`, `tests/cli/test_cli_subcommands.py` |

### Phase 2: Schema-Driven Help (PARALLEL with Phase 1)
| Step | Task | Files |
|------|------|-------|
| 2.1 | Add `_render_tool_help()` using MCP inputSchema | `src/cli.py` |
| 2.2 | Intercept `<tool> --help` before execution, add MCP unreachable fallback | `src/cli.py` |
| 2.3 | Test schema rendering for known tools | `tests/cli/test_tool_help.py` |

### Phase 3: Metadata Assembly (PIPELINE — sequential steps)
| Step | Task | Files |
|------|------|-------|
| 3.1 | Create tool-assembly.ts introspection module | `src/dashboard/scripts/mount/tool-assembly.ts` |
| 3.2 | Wire into mount-plugins.ts build pipeline | `src/dashboard/scripts/mount-plugins.ts` |
| 3.3 | Migrate 11 source consumer files to generated config | `migrated_source` files (see Impact Manifest) |
| 3.4 | Migrate 5 test files to generated config | `migrated_tests` files (see Impact Manifest) |
| 3.5 | Migrate 5 CI/validation scripts to generated config | `migrated_ci` files (see Impact Manifest) |
| 3.6 | Update 9 agent topic/doc files to remove YAML references | `migrated_docs` files (see Impact Manifest) |
| 3.7 | Delete centralized YAML files, grep for zero stale references | `config/dashboard/mcp_tool_groups.yaml`, `tool_display_names.yaml` |

### Completion Criteria
- [ ] `aug discover` works as plugin subcommand (not hard-coded in cli.py)
- [ ] `aug get-skill --help` shows parameter names and descriptions from schema
- [ ] `aug get-skill --help` with MCP server down shows clear error (not hang)
- [ ] `config/dashboard/mcp_tool_groups.yaml` deleted, zero grep hits in source/test/CI
- [ ] `config/dashboard/tool_display_names.yaml` deleted, zero grep hits in source/test/CI
- [ ] `assembled_tool_config.json` generated by mount-plugins
- [ ] All existing CLI and dashboard tests pass (no regressions)
- [ ] CI pipeline (`ci_check.sh`, `ci-lint.yml`) passes without YAML files

## Implementation Prompt

### Team: ADR-260 CLI Plugin Architecture

**Phase 1 — CLI Subcommand Discovery (PARALLEL with Phase 2)**

| Step | Agent | Model | Task |
|------|-------|-------|------|
| 1.1 | developer-1 | high | Create `src/cli_plugins.py`: `discover_subcommands(subparsers)` scanning plugins for `register_subcommands()`. Reuse `get_all_plugin_dirs()` and `PLUGIN_BUNDLES`. First-registered wins on name collision with warning log. |
| 1.2 | developer-1 | high | Refactor `src/cli.py` main(): add subparsers, call `discover_subcommands()`, route via `args.func()` for subcommands, fall through to MCP tool routing. Remove hard-coded discover block and `_print_manifest_markdown`. |
| 1.3 | developer-1 | high | Create `plugins/core/skills/discovery/augur/mcp/__init__.py` with `register_subcommands()` containing the discover logic extracted from cli.py. |
| 1.4 | tester-1 | low | Write tests: `test_cli_plugins.py` (discovery loads plugins, skips without function, collision warning), `test_cli_subcommands.py` (cli.py uses discover_subcommands, no hard-coded discover). |

**Phase 2 — Schema Help (PARALLEL with Phase 1)**

| Step | Agent | Model | Task |
|------|-------|-------|------|
| 2.1 | developer-2 | medium | Add `_render_tool_help()` to cli.py: reads `inputSchema.properties`, renders as `--param TYPE desc (required)`. Intercept `--help` in remaining args before tool execution. Add fallback error if MCP server unreachable. |
| 2.2 | tester-2 | low | Write `tests/cli/test_tool_help.py`: test that `aug get-skill --help` shows parameter info, unknown tool returns error, MCP-down shows fallback message. |

**Phase 3 — Metadata Assembly (PIPELINE — sequential)**

| Step | Agent | Model | Task |
|------|-------|-------|------|
| 3.1 | developer-3 | medium | Create `src/dashboard/scripts/mount/tool-assembly.ts`: Python subprocess introspects plugin tools via mock MCP, outputs JSON. |
| 3.2 | developer-3 | medium | Wire `assembleToolConfig()` into mount-plugins.ts after `assembleAndWriteHubs()`. |
| 3.3 | developer-3 | high | Migrate 11 `migrated_source` files from centralized YAML to generated `assembled_tool_config.json`. Each file: find YAML read, replace with JSON read, update imports. |
| 3.4 | developer-3 | medium | Migrate 5 `migrated_tests` files: update path references, ensure tests work with generated JSON or properly skip. |
| 3.5 | developer-3 | medium | Migrate 5 `migrated_ci` files: update `ci_check.sh`, `ci-lint.yml`, `validate_mcp_config.py`, `mcp_health_check.py`, `dashboard_hardening_audit.py`. |
| 3.6 | developer-3 | low | Update 9 `migrated_docs` agent topic files: replace YAML references with generated JSON references. |
| 3.7 | developer-3 | low | Delete `config/dashboard/mcp_tool_groups.yaml` and `tool_display_names.yaml`. Grep entire repo for stale references — zero hits required. |

**Validation**

| Step | Agent | Model | Task |
|------|-------|-------|------|
| V.1 | validator | high | Run full CLI + dashboard test suite. Smoke test: `aug discover --format json` works. `aug get-skill --help` shows params. CI scripts pass. Verify zero grep hits for deleted YAML files across entire repo (excluding ADR docs and memory). |
