---
title: Multi-Brain Augur — N brain types on one laptop
date: 2026-05-16
status: Draft
authors: [gsannikov]
related_adrs: [ADR-601]
adr_slate: [ADR-754]
supersedes_memory: none
---

# Multi-Brain Augur — design spec

## Summary

Generalize Augur's existing two-vault model (`Au-vault` private + `shared-vault/` team) into an N-brain registry that supports four brain types — **personal**, **team**, **work**, and **project** — on a single laptop, with hard filesystem isolation, explicit cross-brain propagation, AI-client harness scoped per session via env var, and a unified dashboard that federates reads across all brains with mandatory per-brain badges. The two existing brains stay in place with zero data movement; new brain types plug into the same primitives.

The model exists to support workflows like an Intel firmware engineer who wants: a lifelong **personal** brain (finance, health, journals), a cloned **team** brain from their team, a **work** brain for company knowledge that must not leak off the device, and per-code-project **project** brains that travel with the project repo and auto-activate when cwd is inside the project.

## Goals

1. **N-brain registry.** Brain count is not hardcoded; each brain is a first-class registry entry with stable id, type, data root, git arrangement, and policy.
2. **Uniform brain layout.** Every brain — personal, team, work, project — has the same on-disk shape (`notes/`, `sources/`, `wiki/`, `drafts/`, `archive/`, `skills/`, `config/`, plus generated `.augur/` harness mount). No special wrappers for any type.
3. **Hard filesystem isolation.** Brain content lives in disjoint directory trees. The runtime carries a `BrainContext` that scopes every read/write. Path-containment checks (today's `_is_relative_to(resolved_source, private_vault)`) generalize to per-brain roots.
4. **Explicit cross-brain motion.** The only legal way data crosses a brain boundary is the existing promotion-packet primitive, generalized from `private → shared` to `N × M`. No silent classifiers, no auto-routing by content.
5. **Per-session brain scoping for AI clients.** Each brain has a `.augur/` mount with generated per-client harness files (CLAUDE.md, AGENTS.md, GEMINI.md, mcp.json, settings.local.json, skills/). The mount sets `AUGUR_BRAIN_ID=<id>` in the MCP server env; the central Augur MCP server scopes every request to that brain.
6. **Unified dashboard with brain badges.** The dashboard is the one process that federates across brains. Every record carries an immutable brain id; the UI renders a colored badge on every card. Top filter pill bar selects brain subset; focus mode toggle hides non-active brains for screen-shares.
7. **Default-personal write routing.** `/ingest`, `/save`, `/ask retain`, and other write commands default to the **personal** brain. Overrides come from (a) explicit `--to <brain-id>` flag or (b) cwd-based auto-activation for project brains. No session-scoped active-brain context.
8. **Git arrangement per brain.** Each brain declares standalone / bundled / untracked. `/dev-merge full` iterates the registry plus the Augur source repo, deduplicating bundled brains.
9. **Zero-data-movement migration for today's two brains.** The personal and team-augur brains register at their current paths under canonical ids; `vault.yaml` continues to work as a deprecated alias for one release per rule 14.

## Non-goals

- **LLM-based brain classification for captures.** Explicitly rejected: an auto-classifier on a hard-isolated system is a leak vector. Misclassification of work content into personal (or vice versa) is the precise failure mode this design exists to prevent.
- **Session-scoped active-brain context (`/brain use`).** Explicitly rejected: invisible state causes the exact accidents hard isolation is meant to prevent. The cost of typing `--to <id>` per command is the right trade-off.
- **Per-brain MCP server processes.** Single central MCP server, scoped per request by `AUGUR_BRAIN_ID` env var. If a future ADR finds the env-var enforcement insufficient (e.g., for compliance reasons that require process-level RAM isolation for work brains), that's a separate decision.
- **Directory renames of today's two vaults.** `Au-vault/` keeps its directory name; `shared-vault/` keeps its directory name. Brain id ≠ directory name; the registry abstracts identity from path. Future rename, if desired, is a separate cleanup ADR.
- **Cross-brain operations from AI client sessions.** An AI client session sees one brain (the bound brain via env var). Cross-brain queries are dashboard-only. This is a deliberate cut: the dashboard is the federation surface; AI clients are single-brain consumers.
- **Auto-activation for personal/team/work brains.** Only **project** brains opt into `auto_activate_when: cwd_under: [...]`. Personal/team/work brains are activated only by explicit cd into their root or by `--to <id>` flag.
- **A second harness installation per brain.** Exactly one Augur source tree per laptop, at `~/Projects/Augur/` (or wherever the user clones it). All `.augur/` mounts inside brain roots reference that single installation via PYTHONPATH + env vars.

## Locked decisions

The following were settled during brainstorming and are inputs to the design, not open questions:

1. **Isolation model: hard separation per brain.** Each brain = its own filesystem root + (optionally) its own git remote. Cross-brain federation happens in code at the dashboard layer, never via a shared store.
2. **UI federation model: always cross-brain with filters.** Every record badged; top filter pill bar defaults to All; focus mode hides non-active brains for screen-share safety.
3. **Write routing: three-tier (explicit → cwd auto-activate → personal default).** No invisible active-brain state.
4. **Propagation: generalized promotion packets only.** Append-only, contributor-attributed, source-containment-checked. Today's `create_promotion_packet` extends with a `--to <brain-id>` arg.
5. **A brain is a directory.** Uniform layout across all four types. The registry is the source of truth for identity; the directory name is convention, not contract.
6. **Brain registry lives outside any brain.** Location: `~/.augur/brains.yaml`. Deleting any one brain root must not break the registry.
7. **Memory follows AI-client cwd-keying.** Per-mount memory is automatic. A shared-memory symlink mechanism provides cross-cutting facts (user role, vendor-neutral rule, etc.) opt-in per memory at write time, defaulting to brain-local.
8. **Default git arrangement for new brains: standalone.** A brain added to a directory that already has git (e.g., `/brain init --in <project-with-git>`) defaults to a sibling brain directory with its own `.git`. Bundled is opt-in only and requires explicit user confirmation because of leakage risk.
9. **No session-scoped active-brain (`/brain use`).** Rejected; invisible state.
10. **No LLM auto-classification of captures.** Rejected; leak vector.

## The unified brain model

A **brain** is a directory designated for brain content, registered in `~/.augur/brains.yaml`. Every brain — regardless of type — has the same on-disk shape:

```
<brain-root>/
  notes/           ← captured notes, thoughts, journal entries
  sources/         ← ingested external sources (URLs, articles, files)
  wiki/            ← compounded wiki entries
  drafts/          ← in-progress drafts
  archive/         ← retired content
  prompts/         ← saved prompts
  skills/          ← skills installed for this brain
  config/          ← brain-local config (Augur-managed)
  .augur/          ← generated AI-client harness mount (regenerated by /dev-sync)
```

The directory MAY also contain unrelated content. The firmware-project brain at `~/Projects/my-firmware/` has `src/`, `tests/`, `CMakeLists.txt` (the code project) alongside `notes/`, `sources/`, `skills/`, `.augur/` (the brain content). They coexist at the same root. Augur's path helpers only care about the brain-content subdirs.

### Brain types and their default policy

| Type | Typical home | Activation | Default write policy | Default propagation in | Default propagation out |
| --- | --- | --- | --- | --- | --- |
| **personal** | Standalone dir (e.g. `~/Projects/Au-vault/`) | Explicit cd or `--to personal` | Free | Allowed from any | Allowed to any (work prompts confirm) |
| **team** | Bundled in harness repo, OR standalone clone (e.g. `~/Brains/team-X/`) | Explicit cd or `--to team-X` | Packets only | Allowed from personal, project | Allowed to personal, project |
| **work** | Standalone, often no remote (`~/Brains/work-X/`) | Explicit cd or `--to work-X` | Free | Allowed from personal (with UI confirm) | Denied by default (per-pair opt-in) |
| **project** | Sibling of code project, OR inside it (`~/Projects/my-firmware-brain/`) | cwd inside `auto_activate_when.cwd_under` paths | Free | Allowed from personal | Allowed to personal, team |

Type drives default policy. Layout is uniform. Users can override any policy in the registry.

## Brain registry

**Location:** `~/.augur/brains.yaml`. Deliberately outside every brain root, so deleting any one brain doesn't break the federation source of truth.

**Schema (YAML):**

```yaml
version: 1
brains:
  <brain-id>:                              # stable, kebab-case, type-prefix recommended for clarity
    type: personal | team | work | project
    data_root: /absolute/path/to/brain
    description: optional one-line human-readable

    git:
      arrangement: standalone | bundled | untracked
      # if standalone:
      remote: <git-url>                    # optional; brain may exist without a remote
      branch: main
      auto_commit: true
      auto_push: true
      # if bundled:
      host_repo: /absolute/path            # the parent repo whose git tracks this brain

    write_policy: free | packets_only      # packets_only forbids direct writes; promotion-packet-only

    auto_activate_when:                    # optional; typically only project brains use this
      cwd_under:
        - /absolute/path/to/code/project
        - /another/path

    propagation:                           # optional; if omitted, defaults from type table apply
      allow_from: [<brain-id>, ...]        # which brains may propagate INTO this one
      allow_to: [<brain-id>, ...]          # which brains this one may propagate INTO

    skills_allow: [<skill-id>, ...]        # optional; if set, only these skills exposed in this brain's mount
    skills_deny: [<skill-id>, ...]         # optional; mask out these skills in this brain's mount
```

**Brain id conventions:**
- `personal` — the single per-user personal brain
- `team-<name>` — team brains (`team-augur`, `team-intel-firmware`)
- `work-<name>` — work brains (`work-intel`)
- `project-<slug>` — project brains (`project-my-firmware`)

These are conventions enforced by `/brain init`, not the registry schema.

**Initial registry after migration:**

```yaml
version: 1
brains:
  personal:
    type: personal
    data_root: ~/Projects/Au-vault
    git:
      arrangement: standalone
      remote: https://github.com/gsannikov/augur-vault.git
      branch: main
      auto_commit: true
      auto_push: true

  team-augur:
    type: team
    data_root: ~/Projects/Augur/shared-vault
    git:
      arrangement: bundled
      host_repo: ~/Projects/Augur
    write_policy: packets_only
```

These two entries reproduce today's behavior exactly. New brains add new entries; the runtime treats the existing two as instances of the same model.

## AI-client harness mount (`.augur/`)

Each registered brain has a generated `.augur/` subdirectory inside its `data_root`. The mount is regenerated by `/dev-sync` whenever brain policy, registry, or skill set changes. Hand-edits get overwritten.

**Mount layout:**

```
<brain-root>/.augur/
  CLAUDE.md            ← imports central Augur CLAUDE.md + brain-policy overlay
  AGENTS.md            ← for Codex / OpenCode
  GEMINI.md            ← for Gemini CLI
  mcp.json             ← MCP server config with AUGUR_BRAIN_ID=<id> in env
  settings.local.json  ← Claude Code permissions/hooks (per brain)
  skills/              ← symlinks to allowed skills from the central catalog
```

**Per-client extension:** the existing per-client sync adapters (see `dev-sync` skill) extend to generate the relevant files into each registered brain's `.augur/`. Adapters handle:
- Claude Code: `CLAUDE.md`, `.claude/settings.local.json`, `.claude/mcp.json` (or generated `mcp.json` at the mount root)
- Codex / OpenCode: `AGENTS.md` and any per-client config
- Gemini CLI: `GEMINI.md`, `.gemini/` if present

**MCP scoping:** every `mcp.json` entry that points at central Augur sets:

```json
"env": {
  "AUGUR_BRAIN_ID": "project-my-firmware",
  "PYTHONPATH": "~/Projects/Augur:~/Projects/Augur/src/mcp"
}
```

The central MCP server reads `AUGUR_BRAIN_ID` on connection, resolves the brain via the registry, and scopes every read/write to that brain's `data_root`. Today's path-containment check `_is_relative_to(resolved_source, private_vault)` generalizes to `_is_relative_to(resolved_source, brain.data_root)`.

**The harness installation stays singular.** No per-brain Python install. One Augur source tree at the user's harness location. The mount's MCP config is a thin pointer at that single install with a brain id in env.

**Binding an AI-client session to a brain:**
- For standalone brain roots (`~/Brains/work-intel/`, `~/Projects/Au-vault/`): `cd` into the brain root; the AI client reads `<root>/.augur/CLAUDE.md` (or `<root>/CLAUDE.md` if one exists, which Augur ensures contains `@.augur/CLAUDE.md`).
- For project brain roots that ARE a code project root (`~/Projects/my-firmware/`): the project may have a pre-existing `CLAUDE.md`; Augur adds (with confirmation) one import line: `@.augur/CLAUDE.md`. Same for `AGENTS.md`, `GEMINI.md`. The project's existing content stays untouched.

For AI clients that don't support `@` includes in their root instruction file, the sync adapter generates the client-native equivalent (e.g., `.claude/settings.local.json` registers an additional system-prompt file).

## Write routing

Three-tier resolution for write commands (`/ingest`, `/save`, `/ask retain`, any MCP write tool):

1. **Explicit override:** `--to <brain-id>` argument on the command. Always wins. The destination's `write_policy` must permit it: for `packets_only` brains (team type by default), direct `--to` writes are rejected with a "use `/brain propagate` instead" hint.
2. **cwd auto-activate:** if the AI-client session's cwd is inside any brain's `auto_activate_when.cwd_under` list (path-prefix match, walking up the directory tree), that brain becomes the target for this invocation. Only project brains opt into this by default. **If multiple brains match**, the brain whose `cwd_under` entry is the deepest (longest path-prefix match) wins — so a project brain registered at `~/Projects/my-firmware/embedded/` takes precedence over an outer one registered at `~/Projects/my-firmware/`, mirroring how nested git repos resolve.
3. **Default:** the `personal` brain. Always.

The session's brain context (set by `AUGUR_BRAIN_ID` env at AI-client startup) is treated as the cwd-auto-activate result if no explicit override is passed. It is not a "currently active brain" the user can manually change mid-session — to switch, the user starts a new AI-client session in a different cwd, OR uses `--to` per command.

**UI write affordances:** every dashboard write action surfaces a destination selector defaulting to **personal**. The selector is independent of the brain filter selection — filter is a read concern, destination is a write concern. Never inherit silently from the filter.

## Propagation (cross-brain sharing)

Single command, generalizing today's `promote_browse_item_impl`:

```
/brain propagate \
  --from <source-brain-id>/<relative-path> \
  --to   <destination-brain-id> \
  --as   notes | sources | wiki | skills \
  [--roles ...] \
  [--domains ...] \
  [--synthesis "..."]
```

**Mechanics (unchanged from today, parametrized):**
- Source path is validated via `_is_relative_to(resolved_source, source_brain.data_root)`. Cross-brain references are rejected.
- A new append-only promotion packet is written into `destination_brain.data_root` with: contributor (`getpass.getuser()`), source brain id, source relative path, synthesis text, roles, domains, timestamp.
- The packet references the source by path + brain id; the source file does not move and is not copied wholesale. Synthesis text is the curated content.
- The destination brain's git commits the new packet on its next sync cycle.

**Default propagation matrix (enforced by the registry):**

| from \ to | personal | team | work | project |
| --- | --- | --- | --- | --- |
| **personal** | — | allowed | allowed (UI confirm) | allowed |
| **team** | allowed | — | denied | allowed |
| **work** | denied | denied | — | denied |
| **project** | allowed | allowed | allowed | — |

The matrix encodes one principle: **work is a sink, not a source.** Default-deny on work outbound prevents work content from leaving the work brain unless the user opts a specific pair in.

**Personal → work confirm gate.** Both the UI propagate action AND the `/brain propagate` CLI prompt for explicit confirmation when the destination is a work brain and the source is personal — that's a directionality humans frequently get wrong (the user means to file a work artifact and accidentally selects personal as source). The confirm is a single yes/no with the exact source path and destination brain id quoted back. Skipping is not allowed (no `--yes` flag).

Per-pair overrides live in `propagation.allow_from` and `propagation.allow_to` in the registry. A user who genuinely needs `work-intel → personal` (e.g., to extract a non-confidential takeaway) adds `personal` to `work-intel.propagation.allow_to` explicitly.

## Cross-brain UI federation

**The dashboard is the one process that crosses brain boundaries on purpose.** Every other surface — AI client sessions, MCP requests per session, the daemon — is single-brain via env-var scoping.

**Federation primitive:** the dashboard process replaces today's `get_vault_source_roots()` with a registry-driven `get_brain_read_set(filters)` that returns the list of `(brain_id, data_root)` pairs the user has marked readable. Every backing index (RAG, wiki, sources, drafts) lives per-brain in the brain's own `config/`. Queries fan out in parallel; results merge with mandatory brain badges.

**Mandatory brain badge.** Every record at every layer carries an immutable `brain_id` field, attached at write time, never editable or removable in the data model. The dashboard renders the badge as a colored pill on every card, every search result row, every `/ask` citation, every timeline entry. The badge is non-overridable in the UI. The only thing that can hide a non-active brain's badge is **focus mode**, which removes the entire record from the rendered set (not just the badge).

**Top filter pill bar.** Always visible at the top of the dashboard: `[All] [Personal] [Work-Intel] [Team-Augur] [Project-MyFirmware]`. Multi-select. Default: All. Selection scopes the read fan-out. Selection state persists per session in localStorage; not in the registry (it's a UI preference, not policy).

**Focus mode.** Single keybind (e.g., `Cmd+Shift+F`) toggles a session-only "show only active brain" mode. When on, all non-active brain records disappear from every page. Indicator in the chrome ("FOCUS: Work-Intel"). For screen-shares, work meetings, and one-handed task focus. Does not change the registry, the indices, or any policy — pure UI filter.

**Write affordances in UI.** Every action that writes (Save Note, Ingest URL, Propagate) renders a destination selector with personal as default. Visible at the action button. Never silent.

## Memory

AI clients (Claude Code, Codex, Gemini, OpenCode) key memory by cwd. Concretely:
- `cd ~/Brains/work-intel && claude` → memory at `~/.claude/projects/-Users-<user>-Brains-work-intel/memory/`
- `cd ~/Projects/my-firmware && claude` → memory at `~/.claude/projects/-Users-<user>-Projects-my-firmware/memory/`
- `cd ~/Projects/Augur && claude` → memory at today's location, unchanged

**Per-mount memory isolation is automatic.** No Augur work required to get the property that work-brain learnings don't appear in personal-brain sessions.

**Shared facts mechanism.** Cross-cutting truths that apply across all brains (user role, vendor-neutral design rule, "use slash commands not raw pnpm") would be lost if every new mount starts blank. Augur generates a `shared-memory/` symlink in each mount's memory directory, pointed at `~/.augur/shared-memory/`. The `MEMORY.md` index of each mount lists shared facts in a separate "Shared facts" section.

**Memory write classification (at save time):**
- When the auto-memory system saves a new memory, the memory-write skill checks if the content references brain-specific data (file paths inside a brain's data_root, brain-id mentions, etc.).
- If yes → brain-local (default).
- If no AND the memory looks cross-cutting (e.g., a user role fact, a feedback rule about coding style) → ask: "Save as shared across all brains?" defaulting to brain-local for safety.
- The user can promote a brain-local memory to shared via a `/memory promote <name> --shared` command.

This is a deliberate friction point: defaults are conservative. Promotion is explicit.

## Git arrangements

Each brain declares one of three git arrangements in `brains.yaml`:

- **standalone** — brain has its own `.git/` at `data_root`, independent of any other repo. May have a remote (auto-push) or be local-only.
- **bundled** — brain is tracked by another repo (`host_repo`). No own `.git/`. Useful only when brain content is intentionally shipped with the host repo. The only example after migration: `team-augur` bundled in `~/Projects/Augur/`.
- **untracked** — brain has no git, no version control. Backups handled out of band. Discouraged but supported for ad-hoc / ephemeral brains.

**`/brain init` detection flow.** When the target directory already has a `.git/` (e.g., `cd my-firmware && /brain init`), the wizard asks **one question**:

> "`<dir>` is already a git repo. Brain content (notes/, sources/, etc.) needs git separation so it isn't pushed to that remote. Where should the brain live?"
> 1. **Sibling directory** with its own `.git/` and remote *(recommended)* — brain at `<dir>-brain/`
> 2. **Inside `<dir>` but gitignored** from the project's git; brain has its own `.git/` and remote
> 3. **Inside `<dir>` and tracked by the project's git** (bundled — only if brain content is intentionally public to the project's audience)

Never auto-decide. Option (1) is the default and matches how `Au-vault` is a sibling of `Augur` today.

For option (2), Augur appends the brain content directories (`notes/`, `sources/`, `wiki/`, etc.) to the project's `.gitignore` and verifies the entries take effect via `git check-ignore` before initializing the brain's separate `.git/`.

For option (3), Augur prompts a confirm: "Brain content will be visible to anyone with `<project-remote>` access. Confirm?"

**Auto-activation `cwd_under`.** Independent of git arrangement. The firmware brain at `~/Projects/my-firmware-brain/` (sibling) registers `auto_activate_when.cwd_under: [~/Projects/my-firmware]` — when AI client cwd is inside the code project, the sibling brain auto-activates as write target. The brain follows the developer's work, not the disk layout.

## `/dev-merge full` extension

Today (per rule 25) `/dev-merge full` inspects, commits, pushes, and verifies two hardcoded surfaces: the Augur source repo + the personal vault from `vault.yaml`. The extension generalizes this to **iterate the brain registry + the Augur source repo**, deduplicating bundled brains.

**New flow:**

1. Build the set of git surfaces:
   - The Augur source repo (always — it's the harness installation).
   - Every brain with `git.arrangement == standalone`.
   - Skip brains with `git.arrangement == bundled` — their working-tree changes appear in the host repo, which step (1)'s pass handles transitively.
   - Skip brains with `git.arrangement == untracked` unless `--include-untracked` is passed.
2. For each surface in the set (parallel where safe, sequential where ownership conflicts could occur):
   - `git status`
   - Commit if dirty (using each surface's own commit conventions)
   - Push if `auto_push: true` and remote is configured
3. Verify every surface ends clean.
4. Report per surface: brain id (or "harness"), data_root, remote, result.

**For the user's example after adding a firmware brain**, one `/dev-merge full` run touches four surfaces in one invocation:

- `~/Projects/Augur/` (harness repo — carries `team-augur` along)
- `~/Projects/Au-vault/` (`personal`, standalone)
- `~/Projects/my-firmware-brain/` (`project-my-firmware`, standalone)
- *not* `~/Projects/my-firmware/` itself — that's the user's code project, outside Augur's purview

**Rule 25 update.** The text of CLAUDE.md rule 25 changes from "Full dev-merge covers vault" (singular) to "Full dev-merge covers all standalone brains + harness." Behavior on a freshly-migrated system with only the two existing brains is identical to today.

## CLI surface

Brain management commands (all part of a new `/brain` skill that owns this surface):

| Command | Purpose |
| --- | --- |
| `/brain init --type <t> --in <dir>` | Make `<dir>` into a new brain. Creates the standard subdirs + `.augur/`, asks the git-arrangement question if `<dir>` is already a git repo, adds import lines to existing AI-client root files. |
| `/brain register --type <t> --root <dir> --id <id>` | Register an existing directory as a brain without restructuring (no subdir creation). Used for migrating existing two vaults; adds `.augur/`, writes registry entry. |
| `/brain clone <git-url> --type <t> --as <id>` | Clone a remote brain (typically `--type team`) into `~/Brains/<id>/` and register it. |
| `/brain propagate --from <brain>/<path> --to <brain> --as <category>` | Generalizes today's `promote-browse-item` to N×M. |
| `/brain install-skill <skill-id> --to <brain-id>` | Symlink a skill from the central Augur catalog into a brain's `skills/`. |
| `/brain list` | Show registry: id, type, data_root, git arrangement, write policy, propagation. |
| `/brain status [<brain-id>]` | Per-brain: git state, last sync, notes count, sources count, skills count. |
| `/brain remove <id>` | Unregister (does not delete data). Prompts before removing registry entry. |

Each command is also exposed as the corresponding MCP tool with the same arguments.

## Migration

Three stages. The first stage is a no-op for users — pure infrastructure. Stages 2 and 3 add capabilities.

### Stage 1 — Registry & aliasing (zero data movement)

1. Introduce `~/.augur/brains.yaml` with two entries auto-generated from today's config: `personal` (pointing at `~/Projects/Au-vault/` from `vault.yaml`) and `team-augur` (pointing at `~/Projects/Augur/shared-vault/` from `get_shared_vault_dir()`).
2. `vault.yaml` keeps working — it becomes the source of truth for the `personal` entry's `data_root`/`git` block, generated into `brains.yaml` at startup. Deprecated with a one-release sunset.
3. `paths.py` keeps current API. `get_vault_dir()` and `get_shared_vault_dir()` continue to return the personal and team-augur data_roots respectively. New helper `get_brain_dir(brain_id)` is added but no existing call is changed yet.
4. Generate `.augur/` mounts inside each registered brain root. Today's `cd Augur && claude` workflow is unchanged — Augur cwd resolves to the personal brain as fallback.

### Stage 2 — BrainContext plumbing & generalized propagation

1. Add `BrainContext` parameter to MCP write tools, defaulting to personal. Tool signatures change but call sites get a default.
2. Generalize `promote_browse_item_impl` to take a `--to <brain-id>` arg, defaulting to `team-augur` for backward compatibility. Source-containment check generalizes to any registered brain.
3. Add `--to <brain-id>` flag to `/ingest`, `/save`, `/ask retain`, and other write commands.
4. Wire `AUGUR_BRAIN_ID` env var in generated `.mcp.json` for each brain mount. MCP server reads it and scopes per request.
5. Add per-brain RAG indices in `<brain>/config/`. Federation layer is not yet wired (single-brain reads still go through old code path; multi-brain reads via dashboard come in stage 3).

### Stage 3 — New brain types & federation UI

1. `/brain init --type project`, `/brain init --type work`, `/brain clone --type team` become fully usable for adding new brains.
2. `auto_activate_when.cwd_under` implementation in the AI-client startup flow.
3. Dashboard federation: `get_brain_read_set(filters)` replaces `get_vault_source_roots()` for read fan-out.
4. Brain badge rendering throughout the dashboard. Top filter pill bar. Focus mode toggle.
5. `/dev-merge full` extension to iterate registry + harness.
6. Memory shared-symlink mechanism.

Each stage is independently shippable. Stage 1 is invisible to users; stage 2 unlocks the `--to <brain-id>` surface; stage 3 unlocks new brain types and the federation UI.

## Open questions (resolve before implementation)

1. **Shared-memory symlink mechanism — opt-in or opt-out per mount?** Default in the spec is opt-in (each new mount gets the symlink). An equally defensible position: opt-out (mounts start empty; user explicitly enables the shared symlink). Hard-isolation purists prefer opt-out. Pragmatists prefer opt-in. Recommended: opt-in with a `--no-shared-memory` flag at `/brain init`.
2. **Brain id type prefixes — enforced or recommended?** The schema doesn't enforce `personal`, `team-*`, `work-*`, `project-*` prefixes. `/brain init` recommends them. Enforce at the CLI layer (reject `id: foo` if type is project)?
3. **Per-brain encryption at rest for work brains.** Out of scope for this spec; if a future ADR finds that env-var scoping is insufficient for work-brain isolation, encryption-at-rest is the next escalation.
4. **Skill catalog ownership.** Today `shared-vault/skills/` is both (a) the team-augur brain's skills and (b) the default skill catalog for all Augur installs. Stage 3 doesn't change this — but future work may want to split "harness-shipped default skills" from "team-augur brain skills" as distinct concerns. Deferred.
5. **Directory rename of `shared-vault/` → `team-brain/` (or similar).** Out of scope; brain id `team-augur` decouples identity from directory name. Future cleanup ADR.

## Future work

- Multi-team federation policies (when a user is on two team brains, how do propagation defaults interact?).
- Brain-level encryption at rest for work brains.
- A "brain export" command for backing up a brain as a portable archive.
- A "brain import" command for restoring or migrating brains across machines.
- Dashboard support for cross-brain wiki-link resolution (a wiki page in `personal` referencing an entity that also exists in `work-intel` — how does the UI render the relationship without leaking content?).
- Federated `/ask` across brains with per-brain answer attribution.

## References

- ADR-601 — shared-vault skill ownership (the foundation that conflated "team-augur brain" with "harness-shipped skill catalog"; this spec preserves that conflation as a Stage-3+ deferred item).
- `src/config/paths.py` — `get_vault_dir`, `get_shared_vault_dir`, `get_vault_source_roots`, `_VAULT_FIRST_SKILL_VAULT_DIRS`.
- `src/mcp/augur_framework/tools/infrastructure/browse/promotion.py` — `promote_browse_item_impl` (the propagation primitive to generalize).
- `src/lib/vault_promotion.py` — `create_promotion_packet`, `PromotionPacketRequest`.
- `config/system/vault.yaml` — the single-vault config to migrate from.
- CLAUDE.md rule 25 — "Full dev-merge covers vault" (text updates in stage 3).
