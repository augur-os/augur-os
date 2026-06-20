<!--
⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: docs/agent-topics/WORKFLOWS.md
Generator: project-brain/capabilities/skills/ai/scripts/sync_agents/__init__.py
-->
# Workflows

> **When to load**: Load this doc when running commands, executing workflows, using action dispatch, or syncing repos.

## Common Commands

### Dashboard (Next.js) -- use slash-command workflows
```bash
/dev build               # Rebuild dashboard and diagnose build errors
/dev debug               # Diagnose runtime/browser issues
/auto-lint               # Lint and apply allowed fixes
pnpm --filter dashboard test             # Run dashboard tests
pnpm --filter dashboard test -- <file>   # Run a specific dashboard test
```

### Python
```bash
pytest tests/src/                      # Run all Python tests
pytest tests/src/test_paths.py -v      # Run specific test
python3 .github/scripts/audit_paths.py     # Check for hardcoded paths
python3 .github/scripts/validate_dashboard.py <skill>  # Validate UI
python3 .github/scripts/scan_code_markers.py           # Scan for in-code markers
python3 .github/scripts/scan_code_markers.py --summary # Quick summary
```

### Sync & CI
```bash
/sync-repos              # Commit both repos with pre-commit hooks
/ci-check                # Run full CI pipeline locally
python3 .github/scripts/sync_repos.py --message "msg"  # Manual sync
```

## Cross-OS Command Work

When adding or changing a user-facing command:

1. Update `config/system/command_surfaces.yaml`.
2. Put shared behavior in a shell-neutral implementation.
3. Use `.ps1` for Windows adapters and `.sh` only for POSIX adapters.
4. In plans and manual verification gates, label commands as Windows PowerShell, POSIX, or cross-platform.
5. Do not use Bash, WSL, Git Bash, `python3`, heredocs, `grep`, `sed`, or `awk` as the Windows path unless the user explicitly asks for that environment.

## Key Workflows

### Creating/Modifying Dashboard UI
1. Run `/dev build` FIRST — if already broken, fix before doing anything else
2. Run `get-design-standards` MCP tool
3. Read the relevant page's current implementation
4. Check high-scoring pages as benchmarks (Page Score >90)
5. Implement changes
6. Run `/dev build` to verify — never skip this
7. Run targeted dashboard tests for affected components

### Adding a New Skill
1. Read existing skill as template: `cat project-brain/capabilities/skills/{skill}/SKILL.md`
2. Create skill directory structure (see Architecture)
3. Write SKILL.md (<100 lines)
4. Add data directory in `project-brain/capabilities/skills/{skill}/data/` if needed
5. Register in relevant dashboard hub
6. **If skill needs Python dependencies**: Create `requirements.txt` in skill folder

Skills hot-reload: Changes to `project-brain/capabilities/skills/*/SKILL.md` take effect immediately. No restart needed.

### Worktree Creation and the Registry

Before creating or registering a worktree, **identify the worktree you are already
in**. A session frequently runs from inside an existing worktree (not the main
checkout). Run `git rev-parse --show-toplevel` and `git branch --show-current` first,
and never assume the current directory is `main`. Creating a second worktree without
knowing the first one is how sessions cross-contaminate each other's branches.

`scripts/worktree_registry.py register --path PATH --name NAME` records port
allocation **and the branch checked out at PATH**. The branch must be resolved with
`git -C PATH rev-parse --abbrev-ref HEAD` — i.e. *inside the target worktree*, never
from the caller's cwd. Every worktree shares one object store but keeps its own HEAD,
so reading the branch from the calling process records the wrong branch and the
registry then points downstream tooling (`worktree_preflight.py`, dashboard instance
resolution) at the wrong checkout. The registry is the source of truth for
"which branch is this worktree on" — it must never inherit the registrar's branch.

### Dashboard Toolchain Sharing

`apps/dashboard/node_modules` is shared across worktrees at the filesystem layer via
pnpm hardlinks (configured in `apps/dashboard/.npmrc` with
`package-import-method=hardlink`). The preflight orchestrator materializes
`node_modules` in a new worktree by CoW-cloning from main when the filesystem supports
it (APFS / btrfs / ReFS), or falling through to
`pnpm install --frozen-lockfile --package-import-method hardlink` otherwise. Both paths
preserve the existing invariant that each worktree owns its own real `node_modules`
(no symlinks).

If preflight reports `worktree/toolchain/pnpm-store-misaligned`, the pnpm store and
projects directory are on different filesystem volumes — hardlinks won't work until you
resolve that. See `apps/dashboard/README.md` for remediation. Run
`uv run python scripts/verify_worktree_toolchain.py` to measure the actual byte-sharing
rate across a real throwaway worktree (ADR-759).

### Worktree Cleanup
When removing a worktree after merge, also check `~/Library/LaunchAgents/` for launchd plists that reference the worktree path. Stale plists cause the daemon to crash-loop with exit code 78 after the directory is gone.

After a successful verified `/dev merge` from a worktree, the originating
worktree and branch should be removed automatically only when no live AI/client
process still owns that path. Before deleting an Augur worktree, repair Codex
thread state with `project-brain/capabilities/skills/platform-admin/scripts/codex_thread_state.py` so saved
sessions no longer point at a deleted checkout. If `codex`, `claude`, `gemini`,
or Cowork still has the path open, report the cwd/branch/PID and defer deletion
instead of removing the checkout from under an active session.

### Detached Worktree Recovery
Codex worktrees often end up in detached HEAD state with uncommitted WIP. During `/dev merge all`, detect detached worktrees and offer: (a) **rescue** — create a branch in-place with `git checkout -b`, commit, and merge; or (b) **cleanup** — remove if the commit is already in main. Multiple worktrees forked from the same base will produce identical merge conflicts in shared files (e.g., `discovery.py`) — resolve the first, expect the same pattern in subsequent merges.

### Mixed Leftover Branch Recovery
When `/dev merge` finds a leftover branch/worktree whose full branch no longer
merges cleanly, it must not stop at "branch still exists".

Required behavior:
- Create an isolated merge worktree from the target branch.
- Classify leftover branch commits into `already_in_main`, `clean_salvage`, and `stale_or_conflicting`.
- Merge or cherry-pick every `clean_salvage` commit, and verify that `already_in_main` commits are truly equivalent in the target branch.
- After all merge-worthy repo work is proven present in the target branch, discard the leftover branch/worktree automatically unless a live AI/client process still owns that worktree path; report exactly which `stale_or_conflicting` commits were discarded or which PID blocked deletion.
- If equivalence or salvage cannot be proven safely, escalate instead of leaving silent leftovers behind.

### Plugin Dependency Management (ADR-018)

**CRITICAL**: Plugins must be self-contained. Never add plugin-specific dependencies to root `requirements.txt`.

```
# WRONG - adding plugin deps to root
Edit /requirements.txt  # Adding psutil for knowledge skill

# CORRECT - skill manages its own deps
Edit project-brain/capabilities/skills/knowledge/requirements.txt
```

**Core vs Plugin Dependencies**:
- **Core** (`requirements.txt`): Framework essentials only (mcp, pyyaml, pydantic, requests)
- **Plugin** (`project-brain/capabilities/skills/{skill}/requirements.txt`): Plugin-specific deps

**When creating a plugin with Python dependencies**:
```bash
# 1. Create requirements.txt in skill folder
project-brain/capabilities/skills/{skill}/requirements.txt

# 2. Document in SKILL.md installation section
## Installation
pip install -r project-brain/capabilities/skills/{skill}/requirements.txt

# 3. For complex plugins with entry points, use pyproject.toml instead
```

**Current plugins with dependencies**:
| Plugin | Deps File | Key Dependencies |
|--------|-----------|-----------------|
| knowledge | requirements.txt | psutil |
| validator | requirements.txt | playwright |

## Action Dispatch

Action defaults are defined in `project-brain/capabilities/skills/{skill}/assets/actions/*.yaml` with optional user overrides in `get_skill_data_dir(skill) / "actions"`:

| Dispatch Mode | When to Use |
|---|---|
| `fire` | Pure bash/script execution, no LLM needed |
| `oneshot` | Single native AI-client prompt with focused context |
| `ide` | Multi-step agent work, exploration, code changes |
| `modal` | User confirmation or interactive input required |

## Planning Artifact Convention (ADR-172)

**Single source of truth**: The ADR is the canonical artifact for any architectural decision.

**Artifact hierarchy**:
1. **ADR** (always exists, canonical) — `get_adr_dir()/ADR-NNN.md`
2. **Plan** (optional, references ADR) — `docs/plans/YYYY-MM-DD-*-plan.md`
3. **Design draft** (transient, deleted after ADR absorbs) — `docs/plans/YYYY-MM-DD-*-design.md`

**Lifecycle rules**:
- Brainstorming produces a transient design draft — absorbed into the ADR by `/adr write` Phase 0, then deleted
- Writing plans are optional — only for TDD-granular task breakdown beyond the ADR's Implementation Prompt
- Plan files must include header: `> **Implements**: ADR-NNN — [Title]`
- After brainstorming, route to `/adr write` for architectural work

## Modifying Workflows

When adding a new flag or mode to a workflow (e.g. `/ops-learn execute`), you MUST update all cross-referencing workflows that invoke the original command. Search with `Grep` for `/<command>` across `data/agent-workflows/` and `data/ide-integration/workflows/` to find references.

## Global Command Flags

All slash commands support these optional flags:

### `--help`

When a command is invoked with `--help`, the agent MUST NOT execute the command. Instead:

1. Load the command's SKILL.md (via the Skill tool or by reading `project-brain/capabilities/skills/{command}/SKILL.md`)
2. Extract and display the **Usage**, **Options/Flags**, and **Mode Selection** sections (whatever is documented)
3. Append the global flags (`--help`, `--evolve`) to the output
4. Stop — do not run any steps of the command

**Example** (`/dev merge --help`):
```
/dev merge — Commit, merge, push, clean up in fast/full/all/sync modes.

Usage:
  /dev merge           Fast mode (default). Git operations only.
  /dev merge full      Full mode. Includes collateral routing, sync_agents, vault repo sync, learnings.
  /dev merge all       Batch mode. Fast-merge all worktrees, then heavy steps once.
  /dev merge sync      Safe sync main with origin/main via rebase, preserving dirty work and using no force push.
  /dev merge <branch>  Merge a specific branch into main.
  --purge              Remove stalled leftover branches/worktrees only when no merge-worthy commits remain and only technical leftovers are dirty

Flags:
  --stage-all          Stage and commit all dirty files (skip selective staging)
  --into <target>      Merge into a different target branch
  --push               Sync all active repositories

Global flags:
  --help               Show this help and exit
  --evolve             Emit execution telemetry after completion
```

### `--evolve`

When a command is invoked with `--evolve`, the agent MUST call the `emit-execution-event` MCP tool after the command completes. This feeds the command-evolution adaptive loop with execution telemetry.

**Required fields** (always collect):
- `command` — slash command name (without leading `/`)
- `outcome` — `success`, `failure`, or `partial_success`

**Recommended fields** (collect when available):
- `duration_ms` — approximate execution duration in milliseconds
- `phases` — list of `{name, status, duration_ms}` for each major step
- `tools_called` — list of `{name, count}` for each tool invoked
- `errors` — list of `{phase, message, recoverable}` for errors encountered
- `files_changed` — list of `{path, action}` where action is `created`, `edited`, or `deleted`
- `learnings` — list of strings: what went wrong or could be improved
- `assessment` — structured self-assessment:
  - `what_worked` — what went well
  - `what_was_slow` — bottlenecks or slow steps
  - `what_to_improve` — suggestions for the command itself
  - `confidence` — `high`, `medium`, or `low`

**Example** (after `/dev merge --evolve` completes):
```
Call emit-execution-event with:
  command: dev-merge
  outcome: success
  duration_ms: 45000
  phases: [{name: staging, status: success}, {name: push, status: success}]
  tools_called: [{name: Bash, count: 8}, {name: Read, count: 3}]
  errors: []
  files_changed: [{path: src/app/page.tsx, action: edited}]
  learnings: []
  assessment:
    what_worked: Selective staging avoided unrelated files
    what_was_slow: tsc --noEmit took 20s
    what_to_improve: Skip type-check for markdown-only changes
    confidence: high
```

## Slash Commands

The command roster is generated from the live catalog — see the **Slash Commands** section in the generated `CLAUDE.md` / `AGENTS.md` / `CODEX.md`, or run `/commands` (in Gemini/Codex, call the `list-commands` MCP tool). Do not hand-author a command list here: it has no data source and would silently drift from the catalog. Use canonical hyphenated command names only (for example: `/kill-augur`).

## Memory Sync (ADR-057)

Memory is managed via the external vault memory store (canonical source) and synced to all agents:
- **Curate**: `python3 .github/scripts/memory_sync.py` (vault daily logs -> vault MEMORY.md)
- **Sync**: `python3 .github/scripts/memory_sync.py --sync` (distribute to enabled client memory targets such as Claude Code, Codex, Gemini, Cursor, Copilot, and Kimi)
- **Via sync_agents**: `PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync agents all`

## Dev-merge salvage and cleanup

`/dev merge full` covers the code repo and the configured vault repo from
`config/system/vault.yaml`. Inspect both repositories, commit and push vault
changes when the vault is dirty, and verify both remote tips before reporting a
successful full merge.

When `/dev merge` finds leftover branches or worktrees, classify commits into `already_in_main`, `clean_salvage`, and `stale_or_conflicting`. Salvage merge-worthy commits before discarding leftovers. After salvage is proven, cleanup may remove leftover branches and worktrees only when no active AI/client process owns the path.

If salvage cannot be proven safely or equivalence cannot be proven safely, escalate instead of silently leaving or discarding leftovers.

### Dev Merge Demo Proof Flags

Use `/dev merge full --com --skillify` when the user wants a demo-visible proof
that wiki compounding and skillification are real before merge.

**Compound Review Preflight:** For the first project-compounding demo, collect deterministic evidence
with `--compound-review`. The native AI client supplies the proposal JSON; then
rerun with `--review-proposal-json`. The review explains
the durable lesson and target artifact; proof gates remain deterministic and
decide whether the wiki and skillify claims are already durable. Compound
review does not write wiki, skill, or ADR files, and passing review is not proof
durable artifacts changed. A proposal that is missing, malformed, generic, or not evidence-backed
can block before merge.

- `--com` / `--compound-wiki` prints the wiki compounding summary.
- `--skillify` / `--skilify` prints the skillify summary.
- When both are present, run wiki proof first and skillify proof second; print
  the wiki compounding summary and skillify summary before merge/push.
- The proof must use real repo/vault data and stop before merge/push when proof
  is missing, weak, generated-only, or inconsistent.
- `--com` is gated by live `wiki-status` readiness plus the configured vault
  git change set, not only current-session proof. When durable `wiki/` files
  changed, non-passable verdicts such as queued compile backlog,
  stale/low-coverage/current-low-coverage, structure/compiler errors, or other
  demo-readiness failures block before merge/push. If no durable `wiki/` files
  changed, queued compile backlog is reported as a verified no-op summary and
  normal merge continues. Verified-noop wiki proof must name real page/query
  evidence and include a current freshness timestamp; aggregate counts alone
  block.
- `--skillify` must name the durable skill behavior and include routing/quality
  evidence. Routing proof comes from a matching skill manifest root or a
  `skill:<name>` capability policy entry; `primary_skill` ownership metadata on
  another capability is not routing proof by itself. Code-bearing skill changes
  run the affected skill's `augur/tests/` through the existing
  `auto-test-pytest` operation and block on missing/failing quality
  verification. Generated-only or deletion-only skill diffs block.
- Blocked proof exits non-zero; helper automation uses exit 2 for blocked proof.
- Passing proof continues the existing `/dev merge full` contract; it does not
  weaken vault coverage, remote-tip verification, merge-lock handling, or
  worktree cleanup.

Before deleting an Augur worktree:

1. Repair Codex thread state with `project-brain/capabilities/skills/platform-admin/scripts/codex_thread_state.py`.
2. Check for active `codex`, `claude`, `gemini`, or Cowork ownership of the path.
3. Treat `lsof -Fpc +D <worktree>` stdout as meaningful even when `lsof` exits non-zero.
4. If active ownership exists, report PID, command, cwd, branch, and defer deletion.
5. Do not kill AI/client processes unless the user explicitly asks for that exact process kill or a documented lifecycle gate owns that process class.

## Main checkout branch safety

The main checkout must stay on `main`. If the primary checkout is on a non-main branch, stop branch work there and continue in a worktree or merge through `/dev merge`.
