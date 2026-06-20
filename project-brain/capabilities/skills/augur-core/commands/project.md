---
description: Current-folder project router for init, status, project-scoped ask, keep, skillify, routines, ADR, dev, and sweep work.
visibility: core
x-augur-export-command: true
---

# /project
<!-- AUGUR_ARGUMENT_CONTRACT_V1 -->
## Argument Handling (Auto)

1. Parse runtime arguments from `$ARGUMENTS`.
2. If `$ARGUMENTS` is empty, parse text after `/project` in the user request.
3. Preserve argument tokens exactly, including flags and order.
4. The first token is the project verb.
5. If the verb is missing, `--help`, or `-h`, print the usage table and stop.
6. If the verb is unrecognized, print the usage table and stop.

`/project` is the only primary command that is allowed to mutate or inspect the current folder as a project. Top-level `/ask`, `/keep`, `/skillify`, and `/routines` stay personal/global. Top-level `/discover` stays read-only. Top-level `/adr`, `/dev`, and `/sweep` are retired and must be used through `/project`.

## Usage

```text
/project status                         -> show whether the current folder is initialized
/project init [<path>] [--sync]          -> create or attach a project brain; inventory-only unless --sync is present
/project ask <question>                  -> ask against this project folder and its project brain
/project keep <url|file|folder|thought>  -> capture into this project context
/project skillify <incident>             -> create or improve a project-scoped skill
/project routines <args>                 -> run or inspect project routines
/project adr <args>                      -> manage project ADRs
/project dev <args>                      -> run project development workflows
/project sweep <args>                    -> sweep stale project artifacts
```

## Status Gate

Before any verb except `status` and `init`, inspect the active folder with:

```text
uv run aug project status --project <current-folder> --format json
```

If the JSON field `initialized` is `false`, stop and respond:

```text
This folder is not initialized as an Augur project. Run /project init here first.
```

If the JSON field `status` is `invalid_manifest`, stop and show the `message` field. Do not mutate the folder.

If the JSON field `status` is `initialized_unregistered`, run `/project init` before dispatching the requested project verb. This attaches the existing project brain and refreshes the inventory without rewriting vendor files.

## Dispatch

| Verb | Behavior |
|------|----------|
| `status` | Run `uv run aug project status --project <current-folder> --format json`; report project root, brain id when present, brain root, status, and whether init is available. |
| `init` | Run `uv run aug project init --project <path-or-current-folder> --format json`; pass `--sync` only when the user explicitly included it. Report project brain id, inventory count, warning count, and inventory path. |
| `ask` | After the status gate passes, execute `project-brain/capabilities/skills/augur-core/commands/ask.md` with project scope. Use the project brain and current folder artifacts before personal/global memory. |
| `keep` | After the status gate passes, execute `project-brain/capabilities/skills/augur-core/commands/keep.md` with project scope. Writes go to the project brain or project artifact flow unless the user explicitly asks for personal/global capture. |
| `skillify` | After the status gate passes, execute `project-brain/capabilities/skills/auto-skill-quality/commands/skillify.md` with project scope. The resulting skill is project-private unless the user explicitly asks to promote it. |
| `routines` | After the status gate passes, execute `project-brain/capabilities/skills/daemon/commands/routines.md` with project scope. |
| `adr` | After the status gate passes, execute `project-brain/capabilities/skills/augur-core/commands/adr.md`. |
| `dev` | After the status gate passes, execute `project-brain/capabilities/skills/platform-admin/commands/dev.md`. |
| `sweep` | After the status gate passes, execute `project-brain/capabilities/skills/routine-vault/commands/sweep.md`. |

## Retired Top-Level Commands

If the user types `/adr`, `/dev`, or `/sweep` directly, do not execute the old top-level behavior. Respond with the exact replacement:

```text
Use /project adr for current-folder ADR work.
Use /project dev for current-folder development work.
Use /project sweep for current-folder artifact sweeping.
```

## Safety

- `status` is read-only.
- `init` is inventory-only by default and must not adopt, rewrite, merge, delete, or project into existing vendor files.
- `--sync` is explicit opt-in for generated client projection.
- Every project-only verb must run the status gate first.
