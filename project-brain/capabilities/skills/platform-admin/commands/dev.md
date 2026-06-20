---
description: "Project-scoped development operations: build, merge, release, sync, debug, clean. Use through /project dev."
visibility: project
x-augur-export-command: false
x-augur-parent-command: project
x-augur-project-verb: dev
---

# /project dev

This command body is no longer a top-level slash command. It executes only when `/project dev` dispatches to it after the project status gate passes.

Unified development command surface. Dispatches to specialized dev workflows.

## Dispatch

The argument-after-slash is in `ARGUMENTS`. Parse the first word as the verb.

| Verb | Dispatches to | Description |
|------|--------------|-------------|
| `build` | `project-brain/capabilities/skills/platform-admin/commands/dev-build.md` | Clean caches, rebuild dashboard, validate pages |
| `merge` | `project-brain/capabilities/skills/platform-admin/commands/dev-merge.md` | Commit, merge, push, cleanup |
| `release` | `project-brain/capabilities/skills/platform-admin/commands/release.md` | Release pipeline (stage, port, publish) |
| `sync` | `project-brain/capabilities/skills/ai/commands/dev-sync.md` | Inspect and repair client sync |
| `debug` | `project-brain/capabilities/skills/platform-admin/commands/dev-debug.md` | 6-phase debugging protocol |
| `clean` | `project-brain/capabilities/skills/platform-admin/commands/dev-clean.md` | Reclaim caches and disk space |
| `eval` | `project-brain/capabilities/skills/evals/commands/eval.md` | Run command KPI evals, reports, and gates |

### Verb: eval

`/project dev eval` is the developer command-quality evaluation workflow. The
evals skill remains the engine of record; `/project dev` chooses the developer
workflow and delegates to `aug eval`.

| Dev command | Engine command |
|-------------|----------------|
| `/project dev eval bootstrap` | `aug eval command-kpi-bootstrap` |
| `/project dev eval run` | `aug eval command-kpi-run` |
| `/project dev eval run <command>` | `aug eval command-kpi-run --command <command>` |
| `/project dev eval report` | `aug eval command-kpi-report` |
| `/project dev eval gate` | `aug eval command-kpi-gate --required-consecutive-passes 3` |
| `/project dev eval improve [command]` | Run the matching eval loop, inspect `command-kpi-report`, patch the command, then rerun until the gate/report meets the KPI. |

### Verb: release

The `release` verb absorbs the former `/release`, `/stage-release`, and `/port-release` commands:

- `/project dev release` -> full release workflow (formerly `/release`)
- `/project dev release stage <rN>` -> stage a release payload (formerly `/stage-release`)
- `/project dev release port <rN>` -> port staged payload (formerly `/port-release`)

### No verb

For `/project dev`, if `ARGUMENTS` is empty, print this dispatch table and stop.
For `/project dev`, if `ARGUMENTS` is `--help` or `-h`, print this dispatch table and stop.
For `/project dev`, if the verb is unrecognized, suggest the closest match and print the table.
