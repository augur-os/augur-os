---
status: Implemented
date: 2026-05-25
deciders:
  - gsannikov
related: [754, 769, 770, 771, 772, 490]
hub: null
tags: [multi-brain, harness, layering, precedence, projection, cli, mcp, skills, subagents, memory, profile, knowledge, onboarding, dashboard]
superseded_by: null
spec_file: null
plan_file: 2026-05-25-harness-layering-phase1-stack-resolution.md
---

# ADR-781: Harness Layering and Capability Merge Across Global/User/Project Brains

## ADR Family (this is the parent / index)

This ADR owns the **model** (tiers, precedence, two-axis ownership, promotion, cardinality, active-stack resolution, cross-client vision) plus the **shared safety infrastructure** (`verify-harness` correctness gate, dry-run/count-check migration harness, parity-gated cutover, the pure effective/shadowed resolver). The buildable subsystems are split into focused child ADRs, each individually reviewable and each gated by `verify-harness` (+ the migration harness where it moves data). Canonical design across the family: [`docs/superpowers/specs/2026-05-25-harness-layering-family-design.md`](../superpowers/specs/2026-05-25-harness-layering-family-design.md).

| ADR | Subsystem | Build order |
|---|---|---|
| **781 (this)** | Model + index + shared verify/migration infra | foundation (shipped this session) |
| ADR-782 (Implemented, archived) | C1 · Capability Projection & Client Sync (3→2 collapse, effective/shadowed, sync-safety, gated home-dir writes, parity cutover) | 1 |
| [ADR-783](ADR-783-c2-cli-and-mcp-tier-scoping.md) | C2 · CLI & MCP Tier-Scoping | 2 |
| [ADR-784](ADR-784-c3-cross-client-data-memory-profile-knowledge.md) | C3 · Cross-Client Data (Memory · Profile · Knowledge) — implements A2 | 3 |
| [ADR-785](ADR-785-c4-harness-manager-surface.md) | C4 · Harness Manager Surface (UI) | 4 |
| [ADR-786](ADR-786-c5-migration-verification-and-closeout.md) | C5 · Migration Verification & Closeout | 5 |

## Status notes

Implemented 2026-05-25. The family landed through ADR-782, ADR-783,
ADR-784, ADR-785, and ADR-786. Final closeout evidence from
`project-brain/capabilities/skills/platform-admin/scripts/harness_closeout.py --json`
reported `all_ok: true`: Claude, Codex, Gemini, and OpenCode had no missing
effective skills; parity had no dropped skills; the family orphan-reference
scan found 0 stale migrated path references; and the tiered memory projection
contained 40 real records with Codex and Gemini projection targets checked.

## Context

The multi-brain work to date established the *substrate* for more than one brain but never the *combination* of brains. ADR-754 (Stage 1) added the brain registry and aliasing; ADR-769–772 added the phased model: a `project-brain/BRAIN.yaml` manifest, single active-brain resolution (`resolve_active_context()`), brain-aware write routing (`resolve_write_target()`), path→brain mapping (`resolve_brain_id_for_path()`), and review-gated memory promotion keyed per brain.

Every one of those resolves to **exactly one active brain**. The harness an AI agent actually receives — its instruction files, slash commands, `aug` subcommands, skills, subagents, MCP servers and tool exposure, plus the data layers (profile, memory, knowledge) — is projected from that single brain. There is no notion of *layering*: no precedence order, no merge, no way for one capability to come from the platform while another comes from the user and a third from the current project.

A real Augur user does not live in one brain. On a single laptop they have:

1. **Augur core** — the installed platform (the harness itself), present on every machine regardless of cwd.
2. **A personal brain** — their machine-wide second brain, spanning every project.
3. **N project brains** — one per repo they work in.

These must combine the way every modern AI client already combines configuration: a **global** layer, a **user** layer, and a **project** layer, merged with a precedence order so the most specific layer wins. Today Augur has the pieces of each layer but no model for stacking them. This ADR defines that model: how each capability is projected and merged across tiers, what precedence governs conflicts, how the active context is resolved when a new chat starts, how a new project is initialized, and how the whole stack is managed from the dashboard.

Constraints and prior commitments folded in during design:

- **Mirror the AI-client harness pattern explicitly** (global + user + project, most-specific wins). This is the requested architecture, not an Augur invention.
- **Teams are out of scope.** The team tier is deferred (registry field stays dormant); the three-tier spine is designed so a team tier can later slot between User and Project without rework.
- **Client-native and Augur-managed capabilities coexist** within a tier, and a user can *promote* a client-native capability into Augur management.

## Decision

Adopt a **three-tier, two-axis harness layering model**. Tiers map 1:1 onto the AI-client pattern; a second axis distinguishes who owns a capability; and a fixed precedence merges them.

### D1 — Three tiers mapped to the AI-client pattern; precedence

| Tier | Augur meaning | Source root | Writable? |
|------|---------------|-------------|-----------|
| **Global** | Augur core (the installed platform/harness) | Augur installation root | **No** — platform-managed |
| **User** | Personal brain | personal brain `data_root` (e.g. `~/Projects/Au-vault`) | Yes |
| **Project** | Active project brain | `<repo>/project-brain/` | Yes |

Precedence is **most-specific-wins**: `Project ⊐ User ⊐ Global`. This is the same ordering AI clients use for managed → user → workspace configuration. Global + User are **always** in the stack; the Project tier is present only when a project brain is active (see D7).

### D2 — Two-axis ownership model and the promotion framework

Every harness capability sits on two independent axes:

- **Axis A — Tier:** Global / User / Project (where it applies).
- **Axis B — Ownership:**
  - **client-native** — lives in a client's own config (`~/.claude/`, `./.claude/`, `~/.codex/`, `~/.gemini/`, …), is managed by that one client, and is invisible to the other clients.
  - **Augur-managed** — lives in the brain structure at some tier, is governed centrally, and is **projected to every client**.

**Promotion** is the deliberate move from client-native to Augur-managed, holding the tier fixed. The decision rule is the user's:

> If a capability is coupled to a single client, leave it client-native. If you want to manage it centrally / across clients, **promote** it into the Augur brain at the matching tier.

The promotion ladder (for a user's *own* capability):

| From (client-native) | Promote → (Augur-managed) |
|---|---|
| `./.claude/skills/x` (this repo, one client) | Project brain (`project-brain/capabilities/skills/x`) — this repo, all clients |
| `~/.claude/skills/x` (machine-wide, one client) | **User/personal brain** — machine-wide, all clients |

Promotion of a personal capability **tops out at the User tier** (see D3). **Demote/Eject** is the inverse: collapse an Augur-managed capability back to a single client.

Not every capability carries Axis B. Only capabilities that *both* a client and Augur can own (instructions, slash commands, skills, subagents, MCP servers) are dual-ownership. Capabilities with no client slot (`aug` subcommands, MCP tool exposure, profile, memory, knowledge) are **Augur-managed by definition** and carry the Tier axis only — for them, "promotion" is meaningless because there is no client artifact to promote from.

### D3 — Global is platform-managed; cardinality

**Global is read-only to users.** It is the installed Augur core, replaced on update. Users never hand-edit it; their machine-wide capabilities land in the **User/personal brain** (which is also cross-client). "Push to Augur global" therefore resolves to "promote into the personal brain." This matches the AI-client managed/system layer (admin-owned, not user-edited), keeps the install reinstall-safe, and means there are exactly **two user-writable tiers** (User, Project) — no global-overlay write mechanism to build.

The only path that mutates Global is contributing to the Augur project itself (see D10).

**Cardinality per laptop:** exactly **1 Global**, exactly **1 User**, and **N Projects**. `aug brain init` enforces this (D8).

### D4 — Per-capability projection & merge matrix

| Capability | Client slot? | Ownership | Tier write targets | Merge point & rule |
|---|---|---|---|---|
| Instructions (CLAUDE/AGENTS.md) | yes | native or Augur | G (ro) / U / P | **Client.** Augur pre-merges G⊕U → client home; P → client repo (D5) |
| Slash commands | yes | native or Augur | G (ro) / U / P | **Client.** Same projection as instructions |
| Skills | yes | native or Augur | G (ro) / U / P | **Client.** Most-specific name wins; shadowed instances flagged |
| Subagents | yes | native or Augur | G (ro) / U / P | **Client.** Most-specific name wins |
| MCP servers | yes (per client) | native or Augur | G (ro) / P (project `.mcp.json`) | **Client.** Project servers merge under global; name collision → project wins |
| MCP tool exposure | Augur concept | Augur-only | G / P (`scope:` in `capability_exposure.yaml`) | **Augur sync.** Project scope adds to global scope |
| `aug` CLI subcommands | no (`aug` *is* Augur) | Augur-only | G / U / P | **`aug` runtime** (tier-aware `discover_subcommands`); most-specific name wins |
| Profile / identity | no | Augur-only | G / U / P (overlay) | **Augur-MCP runtime.** Overlay merge: project role overlays user identity overlays global defaults |
| Memory | no | Augur-only | G / U / P | **Augur-MCP runtime.** Read = union bottom-up; write = most-specific writable |
| Knowledge index | no | Augur-only | G / U / P | **Augur-MCP runtime.** Federated search across tiers; results tagged by source brain |

### D5 — Three-into-two client projection mechanics

A client exposes only **two** writable config levels (home + repo) but Augur has **three** tiers. Augur collapses the upper two before projecting:

1. **Pre-merge Global ⊕ User** (User wins on conflict) → write to **client home** (`~/.claude/`, `~/.codex/`, `~/.gemini/`).
2. **Project** → write to **client repo** (`./.claude/`, `./CLAUDE.md`, repo `AGENTS.md`, repo `.mcp.json`).
3. The client enforces **repo ⊐ home**, yielding the full **Project ⊐ User ⊐ Global** order.

Hand-placed client-native artifacts coexist in those same directories. The sync pipeline only ever writes/removes **Augur-managed** entries (existing sync-safety rule) — it must never clobber a non-Augur skill, prompt, or plugin the user dropped in.

This logic lives in the `sync_agents` generation pipeline (`project-brain/capabilities/skills/ai/scripts/sync_agents/`): `engine.py` orchestrates the per-tier projection; `templates.py` / `command_surface.py` / `skill_sync.py` emit the merged artifacts; the context envelope (`brain_projection.render_augur_context_envelope()`) is extended to emit the **full stack** (`global` + `user` + active `project`) instead of a single `active_brain` block.

### D6 — Data-capability merge at the Augur-MCP runtime

Profile, memory, and knowledge have no client slot, so they are merged when an Augur-MCP tool reads them, not at projection time:

- **Memory** — `read` returns the **union** of Global + User + (active) Project, with the most-specific tier winning on a key conflict; `write` goes to the **most-specific writable** tier (active Project, else User; Global never). Stores are tier-keyed (extends `src/lib/knowledge/memory_store.py` from its current vault singleton; the review queue at `<runtime>/memory_review/<brain_id>/` is already brain-keyed).
- **Profile / identity** — an **overlay** merge: Global defaults ← User identity ← Project role overlay. A project can override "what role am I in here" without rewriting who the user is.
- **Knowledge** — **federated search** across the per-tier indexes; each result is tagged with its source brain so provenance is visible.

### D7 — Active-context resolution on a new chat

Global + User are always in the stack, so the only question a new session must answer is **whether a Project tier is active, and which**. Resolution order (extends `resolve_active_context()` in `src/lib/brain_context.py`):

1. Explicit `--brain <id>`.
2. Nearest `project-brain/BRAIN.yaml` walking up from cwd.
3. Registered project whose `auto_activate_cwd_under` prefixes cwd (deepest prefix wins, per `resolve_brain_id_for_path()`).
4. None → stack is just **Global + User** (personal mode).

`resolve_active_context()` is refactored to return an **ordered stack** (`resolve_active_stack()` → `[global, user, project?]`) rather than one brain; the single-brain accessor is retained as "the most-specific writable tier" for callers that still need one target.

### D8 — `aug brain init` and registry cardinality

- **`aug brain init` (project)** — run inside a project repo: scaffolds `project-brain/BRAIN.yaml`, scaffolds the capability dirs, registers the brain in `~/.augur/brains.yaml`, and sets `auto_activate_cwd_under = <repo root>`. Repeatable → N projects. (Backs the existing `brain-init` MCP tool.)
- **User/personal brain** — created once at first-run onboarding (`onboard` skill). `init` **refuses a second `type: personal`**.
- **Global** — implicit = the install root. Never created by `init`; not a user-writable registry row.
- **Enforcement** lives in the registry layer (`src/lib/brain_registry_models.py` + the registry writer): reject a second `personal`; allow unlimited `project`; there is no user-creatable `global`. The dormant `team` field is left untouched.

### D9 — The harness manager surface (UI/UX)

Management is a **single interactive manager surface** — the sanctioned exception to Browse rule 32 (a genuine install/configure/manage console, not a card-grid tab). The model is the **VS Code settings editor**: show the effective value and where it is overridden, and let the user copy/promote between scopes.

- **Top filter = tier selector:** Global · User · Project · **Effective** (the merged result the agent actually sees).
- **Each tier lists both ownerships side by side** — client-native *and* Augur-managed — grouped by capability type (instructions, commands, skills, subagents, MCP, `aug` subcommands, and the data caps).
- **Each row shows:** an owner badge (`claude-native` / `codex-native` / `augur`), its tier, and **effective vs shadowed** status (a Global skill `x` shadowed by a Project skill `x` is marked overridden, with a link to the winner).
- **Actions:** `Promote` (client-native → Augur-managed, landing tier chosen per the D2 ladder) and `Demote/Eject` (Augur-managed → a single client). Data is sourced from `brain_discovery.build_discovery_snapshot()`, extended to report the full stack and per-capability effective/shadowed state.

### D10 — The Augur-repo self-hosting duality

"Global = Augur" is true at the **platform** level, not the **checkout** level:

- **Global tier = Augur core**, the installed platform — it applies on every machine regardless of cwd.
- **The Augur dev repo is a *project brain* (`project-augur`)** that happens to be the *source* of the Global tier; it dogfoods the Project tier like any repo.
- This duality exists **only for the Augur repo**. Every other project sees Global and its own Project brain as cleanly distinct layers. When working inside the Augur repo, editing `project-brain/capabilities/` *is* editing the Global source (the contributor path that mutates Global), so projection counts those capabilities **once**, as Global; the Project tier adds only Augur-repo-specific dev overrides, if any.

## Consequences

### Positive
- A user's full harness (platform + personal + project) is finally **combined** with a predictable precedence, instead of resolving to one brain.
- The model is the AI-client mental model users already hold (global/user/project, most-specific wins) — low conceptual overhead.
- The two-axis split gives a clean, opt-in path to centralize capabilities (promotion) without forcing everything into Augur.
- Global stays read-only → reinstall-safe, no global-overlay machinery.
- The seam for a future Team tier is explicit and non-disruptive.

### Negative
- Real complexity moves into the projection pipeline (3→2 collapse, effective/shadowed computation) and into the data-capability runtime merges.
- "Where did this capability come from?" can be non-obvious without the manager surface — the Effective view becomes load-bearing.
- Pre-merging Global⊕User into client home means a single client-home directory now reflects two Augur tiers; the sync-safety boundary (never clobber non-Augur entries) becomes more critical.

### Neutral
- Most existing single-brain functions are *extended* (stack-aware) rather than replaced; single-brain callers keep working against "the most-specific writable tier."
- The team tier remains dormant — designed-for, not built.

## Implementation Order

Each phase is implemented from its own placeholder-free plan under `docs/superpowers/plans/`. Phase 1's plan (`2026-05-25-harness-layering-phase1-stack-resolution.md`, the `plan_file` above) is written; Phases 2–6 get their plans when their turn comes.

**Phase 1 — Stack resolution (foundation).** Add `BrainType.GLOBAL` + a `read_only` write policy; synthesize the Global (Augur-core) brain; add the ordered `BrainStack` value object and `resolve_active_stack()` (delegating to the retained `resolve_active_context()` so no caller breaks); add registry cardinality enforcement (≤1 personal, ≤1 global). No projection/CLI/dashboard changes.

**Phase 2 — Projection of client-native-capable capabilities.** Extend `render_augur_context_envelope()` and the `sync_agents` pipeline to do the 3→2 collapse (G⊕U→home, P→repo) for instructions, commands, skills, subagents, MCP servers. Preserve sync-safety (never touch non-Augur entries). Add effective/shadowed computation.

**Phase 3 — Augur-only capabilities.** Tier-aware `aug` subcommand discovery (`discover_subcommands`); tier-scoped `capability_exposure.yaml` / `mcp_servers.yaml` (`scope: global|user|project`).

**Phase 4 — Data-capability runtime merges.** Tier-keyed memory (read-union / write-most-specific), profile overlay merge, federated knowledge search with provenance tags.

**Phase 5 — Harness manager surface.** Extend `build_discovery_snapshot()` for the full stack; build the VS-Code-settings-style manager (tier filter + Effective view + Promote/Demote).

**Phase 6 — Validation against real data.** Verify on a real machine with Augur core + the personal brain + at least two project brains: confirm precedence, promotion, active-context resolution, and that each client (Claude/Codex/Gemini) receives the correctly merged harness (rule 34).

## Amendment A1 (2026-05-25) — Phase 2b refinement

Phase 2b surface exploration surfaced facts that **refine** (do not reverse) D4/D5/D10:

1. **Two skill-source resolvers must be unified.** `resolve_brain_projection_sources(brain)` is tier-aware but reads only `<data_root>/capabilities/skills`; `get_managed_skill_source_dirs()` (`src/config/paths.py`) is what the skill-stub sync actually consumes and already unions project-brain skills + the vault `skills/` dir. Phase 2b unifies these into one tier-aware resolver, and refactors the module-level source constants in `sync_agents/constants.py` (`SOURCE_RULES/SKILLS/WORKFLOWS/TOPICS`, computed once from a single brain) to per-call multi-tier resolution.

2. **Personal skill layout canonicalized on `capabilities/skills/`.** Personal skills migrate from the private-vault `skills/` dir to `capabilities/skills/` so every tier uses one layout; path helpers (`get_vault_skills_dir`, `get_configured_vault_skills_dir`, `get_managed_skill_source_dirs`) and docs update accordingly (rule 23).

3. **Global tier root = core *brain* root (clarifies D10; supersedes the earlier "distinct tiers" framing).** The Global brain's `data_root` is the Augur core brain root (`<repo>/project-brain` in dev), not the install root, so projection resolves real capability roots consistent with the personal/project tiers. In the Augur repo this **coincides** with project-augur; the layered merge **dedupes coincident roots** (each core capability projected once). For non-Augur projects the installed-Augur Global root and the project's `project-brain` are genuinely distinct. *(Implemented: `resolve_global_brain` default.)*

4. **The 3→2 collapse is outward-facing.** Writing User-tier capabilities to client HOME (`~/.claude`, `~/.codex`, `~/.gemini`) modifies the user's global client config across all repos. It ships behind an explicit opt-in/confirmation, never a silent default.

**Phase 2 slicing (actual):** 2a stack envelope *(Implemented)* → 2b-vaultmig (layout canonicalization) → 2b-merge (`resolve_layered_projection` + dedupe) → 2b-wire (pipeline consumes the merge + home/repo split, gated) → 2c effective/shadowed.

## Amendment A2 (2026-05-25) — Memory (and profile) are bidirectional cross-client capabilities (corrects D4)

D4 mislabeled **memory** (and profile) as having "no client slot." Correction: **every AI client has its own native memory** (Claude memory, ChatGPT memory, Cursor / Gemini / Copilot memory, …). Memory is therefore a **dual-ownership, bidirectional** capability, and the user-facing goal is **cross-client awareness** — what the user does in one client becomes visible to all of them through Augur.

Two directions, both tier-aware:

1. **INGEST (client → Augur).** Each client's native memory is captured into Augur as additional cross-client context, **review-gated** (ADR-772 — no auto-promotion of raw client memory). Promoted entries land at the most-specific writable tier (active Project, else User). *Existing machinery: `sync_agents` `_feed_memory_review_queue()`.*
2. **PROJECT (Augur → all clients).** Augur's aggregated cross-tier memory (read-union Global+User+Project) is written back into every client's native memory/context, so each client is aware of what the user did in the others. *Existing machinery: `adapter.sync_memory()`.*

Net: **Augur is the cross-client memory hub** — clients feed it (review-gated), it aggregates across tiers, and projects the union back so every client shares awareness.

This supersedes the D4 row for **memory**: `client slot = yes (per-client native memory)`; `ownership = dual (client-native source + Augur aggregate)`; `flow = bidirectional (ingest review-gated ↑ / project union ↓)`. **Profile/identity** follows the same dual/bidirectional pattern where a client exposes a profile surface (e.g. custom instructions). **Knowledge** stays Augur-native (clients have no equivalent index slot). Tier precedence and write-routing are unchanged (promotion still targets the most-specific writable tier); only the ownership classification and the explicit ingest / cross-client-awareness direction are corrected.

## Alternatives Considered

1. **Keep single-active-brain (status quo).** Rejected: it cannot express "platform skill + personal command + project subagent" simultaneously, which is the entire user need.
2. **Merge everything at the Augur-MCP runtime; ignore client-native config layering.** Rejected: it discards the layering each client already does well (the user explicitly asked to *use* the client pattern), forces every capability through Augur, and breaks client-native artifacts the user wants to keep single-client.
3. **Four tiers including Team now.** Rejected for scope: the user chose to focus on Global/User/Project. The design leaves a clean insertion point so Team can be added between User and Project later without reworking precedence.
4. **User-writable Global overlay.** Rejected: adds a fourth write location, overlay-merge logic, and a reinstall-collision story for marginal benefit; the personal brain already provides a machine-wide, cross-client, user-writable layer.

## References

- ADR-754 — Multi-Brain Augur Stage 1 (Brain Registry & Aliasing)
- ADR-769–772 — Multi-brain phased model (manifest, active-context, write routing, path→brain mapping, review-gated promotion)
- ADR-490 — Dashboard import architecture (framework/feature partition; informs the manager surface placement)
- `src/lib/brain_context.py`, `src/lib/brain_projection.py`, `src/lib/brain_write_routing.py`, `src/lib/brain_path.py`, `src/lib/brain_registry_models.py`, `src/lib/brain_discovery.py`
- `src/lib/knowledge/memory_store.py`, `src/lib/memory_review.py`
- `src/cli.py`, `src/cli_plugins.py`
- `config/system/capability_exposure.yaml`, `config/system/mcp_servers.yaml`, `config/system/vault.yaml`
- `project-brain/capabilities/skills/ai/scripts/sync_agents/` (`engine.py`, `templates.py`, `command_surface.py`, `skill_sync.py`)
- `~/.augur/brains.yaml`, `project-brain/BRAIN.yaml`
- CLAUDE.md rules 2, 11, 19, 32, 34; Client Integration section (instruction precedence, client sync safety, MCP runtime contract)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "src/lib/brain_context.py: resolve_active_context() -> resolve_active_stack() returning an ordered [global, user, project?] stack; single-brain accessor retained as most-specific-writable tier"
    - "src/lib/brain_projection.py: render_augur_context_envelope() emits the full stack (global + user + active project) instead of a single active_brain block"
    - "src/cli_plugins.py: discover_subcommands() becomes tier-aware (merge global + user + project, most-specific name wins)"
    - "src/lib/brain_discovery.py: build_discovery_snapshot() reports the full stack and per-capability effective/shadowed state"
    - "config/system/capability_exposure.yaml & mcp_servers.yaml: gain a tier scope (global|user|project)"
    - "src/lib/knowledge/memory_store.py: tier-keyed stores (read-union / write-most-specific) replacing the vault singleton"
  patterns_deprecated:
    - "Single-active-brain harness projection (one brain supplies the entire harness)"
    - "Treating Global as the literal Augur checkout rather than the installed platform layer"
  files_affected:
    - src/lib/brain_context.py
    - src/lib/brain_projection.py
    - src/lib/brain_write_routing.py
    - src/lib/brain_path.py
    - src/lib/brain_registry_models.py
    - src/lib/brain_discovery.py
    - src/lib/knowledge/memory_store.py
    - src/lib/memory_review.py
    - src/cli.py
    - src/cli_plugins.py
    - config/system/capability_exposure.yaml
    - config/system/mcp_servers.yaml
    - project-brain/capabilities/skills/ai/scripts/sync_agents/engine.py
    - project-brain/capabilities/skills/ai/scripts/sync_agents/templates.py
    - project-brain/capabilities/skills/ai/scripts/sync_agents/command_surface.py
    - project-brain/capabilities/skills/ai/scripts/sync_agents/skill_sync.py
```
