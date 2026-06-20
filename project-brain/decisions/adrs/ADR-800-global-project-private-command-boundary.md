---
status: Accepted
date: 2026-06-05
deciders:
  - gsannikov
related:
  - ADR-745
  - ADR-781
  - ADR-791
  - ADR-795
  - ADR-796
  - ADR-797
hub: command
tags:
  - commands
  - slash-commands
  - project-router
  - global
  - private
  - cleanup
superseded_by: null
spec_file: null
plan_file: 2026-06-05-command-scope-split.md
---

# ADR-800: Global, Project, And Private Commands Have Separate Surfaces

## Decision summary

Augur exposes a small global command set with stable meaning everywhere, routes every current-folder/project operation through `/project <verb>`, and keeps private repo commands local to that repo instead of syncing them into global client command catalogs.

## Plan

- [`docs/superpowers/plans/2026-06-05-command-scope-split.md`](../superpowers/plans/2026-06-05-command-scope-split.md)

## Context

The launch command surface was too easy to confuse:

- Some top-level commands behaved globally in one context and project-scoped in another.
- Legacy standalone commands and generated body files made it look like more commands existed than the curated command catalog intended.
- Project/private repo workflows should not be globally projected just because Augur can discover them.
- `/ask` and similar commands are useful in both personal/global and project contexts, but the entrypoint must make the scope obvious.

The user requirement is simple: no mixed behavior, no hidden shortcuts, and no need to memorize a large command taxonomy.

## Decision

### 1. Global commands keep the same meaning everywhere

The curated top-level command set is:

```text
/ask
/discover
/keep
/project
/routines
/skillify
```

These commands are global or personal by default:

- `/ask` answers from the personal/global second brain unless explicitly routed to a project through `/project ask`.
- `/keep` captures to personal/global context unless routed through `/project keep`.
- `/routines` lists and runs personal/global routines unless routed through `/project routines`.
- `/skillify` creates or improves a global/personal Augur skill unless routed through `/project skillify`.
- `/discover` is read-only capability and system discovery.

### 2. `/project` is the only current-folder command

Every command that inspects or mutates the active repository/folder routes through `/project <verb>`:

```text
/project status
/project init
/project ask
/project keep
/project skillify
/project routines
/project adr
/project dev
/project sweep
```

The project router runs the project status gate first. If the folder is not initialized, it stops and tells the user to run `/project init`. If the folder has an invalid manifest, it stops before mutation.

### 3. Project-only bodies are not top-level commands

Command body files for `adr`, `dev`, and `sweep` may remain on disk as project-router dispatch bodies. They are not invokable top-level commands and must not be advertised as primary slash commands.

Standalone `/dev-*` body files may remain as implementation bodies where a router needs them, but they are not user-facing commands.

### 4. Private repo commands stay private

A private project can define commands under its own project brain or private vault. Those commands are available only when that project is active and routed through the project surface. They are not synced into the global Augur command catalog and are not projected into unrelated client folders.

### 5. Scope beats namespacing tricks

Augur should avoid proprietary tags or special names to distinguish command scope. The physical source and command route define scope:

- Global/shared: Augur project capability source, exported to supported clients.
- User/private: private vault source, available to the user's personal scope.
- Project/private repo: project brain source, active only through `/project`.

### 6. Help must not execute

Every command and project subcommand keeps the existing `--help` contract: show usage and stop execution.

## Non-Goals

- No broad command marketplace.
- No reintroduction of retired top-level `/adr`, `/dev`, `/sweep`, `/dev-build`, `/dev-merge`, `/note`, `/save`, or `/search`.
- No compatibility aliases for retired commands unless a future ADR explicitly approves one.
- No client-specific command behavior drift.
- No hidden dashboard execution path for command logic.

## Current implementation state

The command catalog and client projection work have landed:

- `uv run aug discover --commands --format json` reports exactly six slash commands: `ask`, `discover`, `keep`, `project`, `routines`, and `skillify`.
- `project-brain/capabilities/skills/augur-core/commands/project.md` declares the project router and the project status gate.
- `project-brain/capabilities/skills/ai/augur/tests/test_command_discovery.py` asserts no hidden command sections and no exported `adr`, `dev`, `sweep`, or `dev-*`.
- Plugin-pack profiles export `project`, not `adr`, `dev`, or `sweep`.

This ADR remains `Accepted`, not `Implemented`, because some live instruction tables still use `/dev build`, `/dev merge`, and `/dev debug` wording. Implementation is complete only after those authoritative workflow docs and generated projections say `/project dev ...` consistently or intentionally classify `/dev ...` as a non-primary internal body with explicit rationale.

## Consequences

Positive:

- New users learn six commands, not a large legacy catalog.
- The same top-level command means the same scope in every supported AI client.
- Project-private behavior is explicit and local.
- Existing project workflows remain reachable without preserving top-level ambiguity.

Tradeoffs:

- Users who previously typed retired top-level project commands need the `/project` prefix.
- Workflow docs and generated projections must be audited whenever command scope changes.
- The command body file count can remain larger than the public command count because routers need dispatch bodies.

## Verification

Implementation can be marked complete only when all of these are true:

- `uv run aug discover --commands --format json` reports only `ask`, `discover`, `keep`, `project`, `routines`, and `skillify`.
- `list-commands` MCP payload reports the same six ids and no `auto_commands` hidden section.
- Generated client command manifests expose the same primary set.
- `rg '/(adr|dev|sweep)(\\s|$)|/dev-(build|merge|debug|clean)'` over authoritative instruction sources finds no retired top-level usage except historical docs or explicit body-file references.
- `/project status` and `/project init` work against real initialized and uninitialized folders.
- Private project commands do not appear in unrelated global command catalogs.

## Status notes

Accepted on 2026-06-05 to lock the user-facing command split. It supersedes the top-level `/dev <verb>` user-facing conclusion from ADR-796 when the remaining instruction wording is reconciled; ADR-796 remains the historical cleanup record for standalone `/dev-*` aliases.

## Related

- ADR-745: Skillify workflow.
- ADR-781: Harness layering and capability merge across brain scopes.
- ADR-791: Brain-scoped standard skill source.
- ADR-795: Private vault skills are process-separated from the project-tier MCP server.
- ADR-796: `/dev <verb>` canonical surface and `/dev-*` alias retirement.
- ADR-797: Fast launch is inventory-only folder init.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "public slash-command catalog reduced to ask/discover/keep/project/routines/skillify"
    - "project-only work routed through /project <verb>"
  patterns_deprecated:
    - "top-level project-mutating commands"
    - "global projection of private project commands"
    - "legacy aliases or shortcut commands hidden behind generated command surfaces"
  files_affected:
    - "project-brain/capabilities/skills/augur-core/commands/project.md"
    - "project-brain/capabilities/skills/augur-core/commands/adr.md"
    - "project-brain/capabilities/skills/platform-admin/commands/dev.md"
    - "project-brain/capabilities/skills/routine-vault/commands/sweep.md"
    - "config/system/capability_exposure.yaml"
    - "project-brain/capabilities/skills/plugin-pack/scripts/profiles.py"
    - "docs/superpowers/plans/2026-06-05-command-scope-split.md"
```
