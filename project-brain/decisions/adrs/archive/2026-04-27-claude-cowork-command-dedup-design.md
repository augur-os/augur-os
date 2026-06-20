# Claude/Cowork Command Deduplication

**Date:** 2026-04-27
**Status:** Approved

## Problem

Claude/Cowork is showing duplicate Augur slash commands. The confirmed local
shape is that Augur commands can be exposed through more than one channel:
repo-local Claude Code command exports in `.claude/commands/*.md`, and Cowork
plugin commands installed into Claude Desktop session storage under
`local-agent-mode-sessions/*/*/cowork_plugins/.../augur/commands/*.md`.

The concrete observed overlap is `/wiki`, but the user reports the issue across
all commands. This should be treated as a command-surface ownership bug rather
than a one-file cleanup issue.

## Goals

- Keep one visible Augur slash command owner per Claude/Cowork context.
- Preserve Claude Code project-local commands such as `/wiki`, `/dev-merge`,
  `/ingest`, and related generated `.claude/commands` entries.
- Preserve Cowork plugin value: MCP connector, plugin skills, and Claude
  Desktop integration.
- Prevent future sync or plugin-pack changes from reintroducing duplicate
  command names.
- Provide an exact diagnostic report when duplicates exist.

## Non-Goals

- Do not broad-delete Claude Desktop, Claude Code, or Cowork state.
- Do not remove unrelated Cowork plugins or official Claude plugins.
- Do not replace the existing command export system with a central command
  registry.
- Do not rename every command unless a future user decision explicitly chooses
  namespacing.

## Recommended Approach

Claude Code owns project-local slash commands. Cowork owns the Claude Desktop
plugin install: MCP connector, plugin skills, and any Cowork-only commands that
do not overlap with Claude Code project commands.

The Cowork plugin-pack profile should not blindly export `_CORE_COMMANDS` when
those same command names are already exported by `sync_agents` into
`.claude/commands`. In practice, Cowork should omit colliding command files from
the plugin bundle while keeping `.mcp.json`, `.claude-plugin/plugin.json`, and
plugin skills.

## Alternatives Considered

### Prefix Cowork Commands

Cowork commands could be renamed to names such as `/augur-ask` or
`/augur-wiki`. This is low risk for collision, but it creates two user-facing
command models and leaves users to decide which version is canonical.

### Cowork-Only Commands

The repo-local `.claude/commands` surface could be removed and Cowork plugin
commands could become canonical. This is cleaner inside Claude Desktop, but it
is risky because Claude Code and project-local workflows already depend on
`.claude/commands`.

### Runtime Cleanup Only

Deleting installed duplicate command files from the current Cowork session would
give fast relief. It is not durable: the next `sync_agents` or plugin-pack
install can recreate the duplicate surface.

## Command Surface Inventory

Add a diagnostic path that inventories Augur command exposure across:

- repo-local `.claude/commands/*.md`
- installed Cowork plugin `commands/*.md`
- Cowork `installed_plugins.json` entries for Augur plugin keys
- legacy Cowork cache dirs such as `cache/augur-cowork`
- plugin-pack generated output under `build/cowork`

The diagnostic should report:

- command name
- every source path where that command appears
- source class, such as `claude-code-project`, `cowork-upload`,
  `cowork-cache`, or `cowork-build`
- suggested owner based on the single-owner policy

## Cleanup Behavior

Cleanup must be surgical and Augur-scoped:

- Remove only Augur-owned duplicate Cowork command files or stale Augur plugin
  registrations.
- Preserve non-Augur Cowork plugins, official Claude plugins, and user-owned
  Claude state.
- Prefer regeneration over manual editing: once the Cowork profile stops
  emitting overlapping commands, reinstalling the plugin should remove the
  duplicate source.
- Keep `.claude/commands` intact unless a future design explicitly changes the
  command owner.

## Tests And Guardrails

Add focused regression coverage:

- Cowork plugin-pack profile or formatter test: assembled Cowork plugin should
  not include command files that collide with `.claude/commands`.
- Claude Code sync lifecycle test: generated `.claude/commands` still works and
  remains the command owner.
- Diagnostic test: duplicate inventory reports command name plus all source
  paths.
- Cleanup test: Cowork cleanup removes Augur-owned stale command surfaces while
  preserving unrelated Cowork plugins.
- Idempotence test: running sync/install twice does not produce duplicate
  command files, `/wiki1`, `/ask1`, or renamed duplicate entries.

## Expected Final State

- Claude Code exposes project commands through `.claude/commands`.
- Cowork plugin exposes Augur MCP and skills.
- Cowork no longer contributes duplicate slash commands for names already owned
  by Claude Code.
- Repeated sync and plugin install are idempotent.
- If a duplicate reappears, diagnostics point to exact paths and ownership
  classes instead of requiring manual filesystem inspection.
