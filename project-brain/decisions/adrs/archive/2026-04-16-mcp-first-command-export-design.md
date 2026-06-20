# MCP-First Client Export and Command Stub Policy — Design Spec

**Date:** 2026-04-16  
**Status:** Proposed  
**Scope:** Replace broad client skill copying with an MCP-first export model that keeps only explicitly marked command entrypoints as local client exports

---

## Problem

Augur currently has two separate export behaviors:

- `plugin-pack` applies a filtered profile and exports only a constrained set of skills/commands for target packages
- `_sync_skill_stubs()` broadly copies `skills/*/SKILL.md` into normal client surfaces with no equivalent filtering

That second path creates a large amount of duplicated client-local content:

- Claude local/global skill copies
- Gemini local/global skill copies
- Cursor local/global flattened skill copies
- Copilot local/global instruction copies
- OpenCode local/global skill copies
- a separate Codex-native skill path

This is too broad for the intended architecture. Most Augur capability should be available through MCP, not through copied client-local skills. The copied skill surface increases drift, cleanup cost, and user confusion.

At the same time, there are a few high-value daily entrypoints the user still wants available as client-local slash commands, such as:

- `/dev-merge`
- `/dev-loops`
- `/ask`

The new design needs to preserve those entrypoints without preserving the bulk skill-copying model.

---

## Goals

- Make MCP the default delivery path for Augur capabilities.
- Stop broad copying of `SKILL.md` content into normal client surfaces.
- Remove Codex-native special export behavior.
- Keep a small, explicit way to export selected slash-command entrypoints.
- Minimize config surface and avoid central export registries.
- Ensure cleanup of previously generated copied skills remains manifest-based and safe.

---

## Non-Goals

- Do not redesign plugin-pack packaging in this change.
- Do not remove command export entirely.
- Do not introduce a second central config file for exported commands.
- Do not require per-client export metadata on every skill.
- Do not move capability logic out of MCP and into copied command implementations.

---

## Decision

Use an **MCP-first, command-opt-in** export policy:

- copied skills to normal client surfaces are disabled by default
- copied command entrypoints remain available only when explicitly marked
- the only new export knob is command frontmatter:
  - `x-augur-export-command: true`

This keeps the model small and explicit:

- capabilities live behind MCP
- only user-facing entrypoints are mirrored into client command surfaces

---

## Core Policy

### Rule 1: Skills are MCP-first

`skills/*/SKILL.md` content should not be copied to normal client-local skill directories by default.

Normal clients should use MCP for skill-backed capability instead of mirrored `SKILL.md` copies.

### Rule 2: Commands are the only normal export lane

`skills/*/commands/*.md` may be copied only if their frontmatter includes:

```yaml
x-augur-export-command: true
```

If the flag is absent or false, the command remains MCP-only.

### Rule 3: Exported commands are entrypoints, not duplicated implementations

Exported command copies should be thin local entrypoint docs. They should direct the client toward Augur/MCP-backed behavior, not become a second full implementation channel for workflows.

### Rule 4: No Codex-native special path

Remove the Codex-native skill export path and the corresponding skill metadata requirement.

This means:

- no `x-augur-codex-native`
- no Codex-only native skill export surface
- no Codex-only prompt/skill exception inside the policy model

---

## Client Matrix

### Normal client surfaces

These should not receive copied skill exports:

- Claude local/global skills
- Gemini local/global skills
- Cursor local/global flattened skill docs
- Copilot local/global instruction-skill copies
- OpenCode local/global skills
- Codex native skills

For these clients, MCP is the primary capability path.

### Command surfaces

Normal client command export is limited to explicit command entrypoints.

Current intended behavior:

- Claude Code command docs continue to exist as a command surface
- only commands with `x-augur-export-command: true` are exported there

This design does not add new command-export surfaces for clients that do not already have them.

### Plugin-pack targets

Plugin-pack can keep its target-specific packaging behavior, but it should conceptually align with the same architecture:

- minimal local packaged surface
- MCP-backed capability
- no broad “copy all skills” behavior outside a clearly justified package target

Plugin-pack is not the source of truth for normal client export policy.

---

## In Practice

### Example: `/ask`

If the command doc for `/ask` contains:

```yaml
x-augur-export-command: true
```

then `/ask` remains available as a client-local slash-command entrypoint where command export is supported.

The command should still drive MCP-backed retrieval and reasoning rather than rely on a copied local skill tree.

### Example: `/dev-merge`

If marked for export, `/dev-merge` remains a small local entrypoint for the user’s daily merge workflow, while the real operational behavior remains in Augur.

### Example: `/dev-loops`

If marked for export, `/dev-loops` remains available as a high-value operational entrypoint without reintroducing daemon/adaptive skill copying to clients.

---

## Source of Truth

### Skill source of truth

The repository `skills/` tree remains the authored source of truth for skills and commands.

### Export decision source of truth

Command export eligibility lives inside the command doc itself:

- `x-augur-export-command: true`

This is preferred over:

- central registry files
- client-specific allowlist config
- hub-based bulk export rules

because it minimizes config surface and keeps the decision close to the authored command.

---

## Required Code Changes

### 1. `_sync_skill_stubs()`

Change behavior from:

- export loaded skills to all enabled client surfaces

to:

- stop bulk skill export to normal client surfaces
- clean up previously managed copied skills via existing manifests
- preserve user-created files in those client directories

This should make `_sync_skill_stubs()` effectively cleanup-first for normal client surfaces.

### 2. `_load_command_sources()`

Filter loaded command docs so only commands with:

- `x-augur-export-command: true`

are eligible for client export.

### 3. `_sync_command_stubs()`

Keep command export as the normal export lane, but export only explicitly marked commands.

### 4. Codex-native export removal

Remove the Codex-native skill export pathway and its metadata dependence.

This includes:

- code paths that mirror skills into Codex native discovery dirs
- references to `x-augur-codex-native`
- tests that rely on Codex-native special casing

### 5. Cleanup behavior

Any formerly generated skill exports that are no longer allowed must be removed via manifest-based cleanup during sync.

This migration must:

- remove Augur-managed generated copies
- preserve user-authored files
- avoid destructive scavenging beyond managed outputs

---

## Migration

On the first sync after this change:

- previously generated client-local copied skills should be removed from managed client export dirs
- previously generated exported commands should remain only if their source command docs are explicitly marked with `x-augur-export-command: true`
- Codex-native Augur skill exports should be removed
- user-created content in those directories should remain untouched

This migration is part of normal sync behavior, not a separate one-off command.

---

## Testing

The implementation should be considered correct only if it proves all of the following:

- `_sync_skill_stubs()` no longer bulk-exports skills to normal clients
- previously managed copied skills are removed on sync
- user-created files in those same directories are preserved
- only command docs with `x-augur-export-command: true` are exported
- unmarked command docs are not exported
- exported command count reflects only flagged commands
- Codex-native export behavior is removed
- migration cleanup removes stale Codex-native Augur exports without touching user content

---

## Risks

### Risk: users lose familiar local command entrypoints

Mitigation:

- keep command export available for a small set of explicitly marked daily-driver commands

### Risk: MCP outages become more visible because fewer local copies exist

Mitigation:

- this is an architectural truth already hidden by duplication; capability should be fixed at the MCP layer rather than masked by client-local copies

### Risk: plugin-pack and normal client export drift conceptually

Mitigation:

- define plugin-pack as a package-target exception, not the normal export model
- keep the normal export policy centered on MCP-first + command opt-in

---

## Summary

The new export model is:

- MCP-first for capabilities
- no broad copied skills to normal clients
- no Codex-native special skill path
- one explicit opt-in for copied slash-command entrypoints:
  - `x-augur-export-command: true`

This preserves the commands the user actually uses, such as `/dev-merge`, `/dev-loops`, and `/ask`, while removing the mass copied-skill surface that is currently causing drift and cleanup problems.
