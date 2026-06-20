---
title: Cross-Client Bundle Architecture (Layer 1 — Capability Manifest)
date: 2026-04-28
status: proposed
scope: design
---

# Cross-Client Bundle Architecture (Layer 1)

## Purpose

Augur today exposes 213 skill-registered MCP tools. A hardcoded server-side allowlist (`CURATED_VISIBLE_TOOLS` in `src/mcp/augur_mcp/client_surface.py`) hides ~91% of them from non-dashboard clients. Six entire skills — `obsidian`, `platform-admin`, `apple`, `lifestyle`, `document-extractor`, `auto-skill-quality` — have zero tools reaching Claude Code. The allowlist is unmaintained, doesn't read skill metadata, and breaks silently every time a new tool is added.

The architectural fix is not a better allowlist. It is to stop having an Augur-proprietary "skill" abstraction at the protocol layer and to lean on what the standards already define:

- **Tool capabilities** are MCP servers. MCP defines `tools/list`, `serverInfo`, and per-tool `annotations`. There is no native concept of "skill" in MCP.
- **Knowledge / instructions** are SKILL.md files following the open Anthropic Agent Skills format (`agentskills.io/specification`). SKILL.md defines a frontmatter schema and a flexible folder convention.
- **Visibility** is the user's own client config. Claude Code, Codex, and Gemini all support per-server enable/disable through config layering (project-tier vs user-tier). No server-side filter is needed.

Under this design, the unit on disk is a **bundle**: a directory that may ship one MCP server, zero or more SKILL.md files, optional dashboard contributions, optional loop registrations, and optional slash commands. The MCP server layer is one consumer; the dashboard is another; the daemon is another. Each consumer reads a well-known file with a well-known schema. No proprietary `x-augur-*` vocabulary appears in any protocol-facing place.

This document is the foundation (Layer 1) of a four-layer redesign. Layer 2 (server-side discovery), Layer 3 (per-client consumption profiles), and Layer 4 (migration) are explicitly deferred to follow-up specs. The decisions here lock the contract every later layer depends on.

## Decisions

- Each Augur bundle is a directory containing zero-or-one MCP server, zero-or-more SKILL.md files, and optional consumer-specific manifests.
- The bundle root MAY contain `SKILL.md`, `dashboard.yaml`, `loops.yaml`, `commands/`, `scripts/`, `references/`, `assets/`, `evals/`, `tests/`. No other peer files at the bundle root.
- Drop the `_config/` and `augur/` subfolders. Their content is redistributed across the new layout or removed.
- The MCP server boundary is the bundle boundary on the tool side. One bundle, at most one MCP server.
- `serverInfo` (name, version, optional instructions) is the bundle's declarative tool-side identity. Per-tool MCP `annotations` (readOnlyHint, destructiveHint, idempotentHint, openWorldHint, title) carry tool metadata. No proprietary fields.
- SKILL.md frontmatter follows the Anthropic Agent Skills spec (`name`, `description`, optional `model`, `tools`, `allowed-tools`, `experimental`). No `x-augur-*` extensions.
- `dashboard.yaml` carries the dashboard's contributions (`blocks`, `pages`, `actions`, `modals`). Schema is owned by the dashboard, documented as a dashboard concern, vocabulary is plain English. Bundles without dashboard surface omit the file.
- `loops.yaml` carries daemon-managed loop registrations. Schema is owned by daemon, documented internally.
- `commands/` follows Claude Code's `commands/<name>.md` convention for slash commands. Codex and Gemini equivalents are generated from the same source at build time.
- Visibility per client is controlled by the user's client config layering (project tier + user tier). The `CURATED_VISIBLE_TOOLS` filter is removed.
- The `client_surface.py` per-client allowlist (`COWORK_VISIBLE_TOOLS`, etc.) is replaced by per-client config files in each client's native format.
- Bundles split into two distribution tiers using a single principle: **operational meta-tooling stays project-tier; domain integrations live in the user's vault.** The Python-import audit confirms which library code moves to `src/lib/`; the meta-tooling-vs-integration distinction determines bundle tier.
- **Project tier — framework operations** (always-on, ships with framework):
  - `augur-core` (registry MCP server)
  - `augur-framework` (multiplexes wrappers around `src/lib/` + the operational MCP tools from `auto-skill-quality` and `platform-admin`)
  - 12 SKILL.md-only operational bundles: 10 `loop-*` bundles + `onboard` + `plugin-pack`
  - The daemon process (small bundle around `src/lib/runtime/`)
- **Vault tier — user integrations** (per-user, each its own MCP server):
  - `apple`, `lifestyle` (already vault)
  - `ingest`, `obsidian`, `file-manager` (migrated from project — domain integrations)
  - `auto-skill-quality` and `platform-admin` are NOT in the vault tier; they belong with the rest of the operational meta-tooling family (their tools fold into `augur-framework`).
- Heavily-imported skills are framework libraries, not bundles. `ai`, `rag`, `document-extractor`, and the daemon's library code move to `src/lib/` (`src/lib/ai/`, `src/lib/index/`, `src/lib/extraction/`, `src/lib/runtime/`, `src/lib/knowledge/`).
- Three layering smells the audit exposed are fixed by the migration: `src/config/mcp_tools.py:apple` reference removed, dashboard scripts hardcoding `lifestyle` generalized, `daemon → platform-admin` import inverted via shared utilities in `src/lib/`.
- Cross-bundle operations (`browse-index`, `find-skill`, `list-skills`, `cross-skill`, `unified-search`, `search-skill-knowledge`) live in the `augur-core` MCP server. `augur-core` discovers other connected MCP servers from the user's client config at startup.
- This spec does not specify the cutover plan. Layer 4 (migration) will be a separate spec.

## Architecture

### The two protocol layers, both standardized

Augur participates in two open standards. They are independent and have separate consumers.

| Layer | Standard | What it ships | Consumer |
|---|---|---|---|
| **Tool capabilities** | MCP (Model Context Protocol) | An MCP server per bundle, declared via `serverInfo` + per-tool `annotations` | Any MCP-speaking client (Claude Code, Codex, Gemini, dashboard, etc.) |
| **Knowledge / instructions** | Anthropic Agent Skills (SKILL.md) | One or more `SKILL.md` files in the bundle | Any agent runtime that implements SKILL.md (Claude Code today, Codex/Gemini via per-client export) |

These layers are connected by reference, not by nesting: a SKILL.md may name MCP tools by string in its frontmatter `tools` field; the MCP server defines those tools. They are not "the same thing" and are not unified into a single Augur-proprietary manifest.

### Bundle directory layout

```
bundle/
  SKILL.md            (optional) Anthropic Agent Skills frontmatter + body
  dashboard.yaml      (optional) Dashboard contributions: blocks/pages/actions/modals
  loops.yaml          (optional) Daemon-managed loop registrations
  commands/           (optional) Slash commands per Claude Code convention; auto-exported per client
    <command>.md
  scripts/            (optional) Bundle-local scripts; MCP server entry under scripts/mcp/__init__.py
    mcp/
      __init__.py     register_tools(mcp, mcp_tool_interceptor, metrics)
      <tool_module>.py
    <other_scripts>.py
  references/         (optional) Heavy reference docs per Anthropic spec convention
  assets/             (optional) Static assets (icons, templates, fixtures)
  evals/              (optional) Skill evaluations
  tests/              (optional) Bundle-local tests
```

Removed compared to today: `_config/config.yaml` (split into `dashboard.yaml` + `loops.yaml` + `commands/`), the `augur/` proprietary subfolder (its contents redistributed: `augur/tests/` → `tests/`, `augur/dashboard/` → produced into `apps/dashboard/` at build time, not stored in the bundle, `augur/data/` → `assets/` or runtime state).

A bundle is **valid** if it contains at minimum one of: `SKILL.md`, `scripts/mcp/__init__.py`, `dashboard.yaml`, `commands/`, or `loops.yaml`. A bundle with only `scripts/` and no peer manifests is not a bundle in the architectural sense — it's a Python library and belongs in `src/lib/`.

### Three code-organization tiers

The audit (Python-import dependency analysis across the repo + vault) classified skills by how they are consumed at the code level. The result is a clean three-tier layout:

```
src/lib/                ← Framework libraries (Python imports only — not bundles)
  ai/                   was skills/ai (18 importers)
  index/                was skills/rag (15 importers — indexer + document_understanding)
  extraction/           was skills/document-extractor (4 importers via sys.path)
  runtime/              daemon library code (11 importers)
  knowledge/            knowledge library code (memory + search APIs, 2 importers)

skills/                 ← Real bundles (project tier — operational meta-tooling)
  augur-core/           Registry MCP server (browse-index, cross-skill, etc.)
  augur-framework/      MCP wrappers around src/lib/ + auto-skill-quality MCP +
                        platform-admin MCP, multiplexed
  daemon/               Small process bundle wrapping src/lib/runtime/
  auto-skill-quality/   SKILL.md + commands + scripts; MCP tool folded into augur-framework
  platform-admin/       SKILL.md + commands + scripts; MCP tools folded into augur-framework
  loop-docs/            10 SKILL.md-only loop bundles
  loop-hub-coverage/
  loop-memory/
  loop-observability/
  loop-ops/
  loop-quality/
  loop-repo/
  loop-security/
  loop-test/
  loop-wiring/
  onboard/              Framework setup bundle
  plugin-pack/          Framework distribution bundle

<vault>/skills/         ← Vault tier (user-installed domain integrations)
  apple/                Already vault
  lifestyle/            Already vault (after dashboard hardcode is removed)
  ingest/               Migrated from project — URL/file capture (optional)
  obsidian/             Migrated from project — Obsidian sync (optional)
  file-manager/         Migrated from project — file organization (audit: 0 importers)
```

The classification is principled along two axes:

- **Library vs bundle**: heavy Python importers move to `src/lib/`. Confirmed by audit: ≥4 incoming imports = library candidate.
- **Operational vs integration**: operational meta-tooling (loops, scanners, dev tools) stays project-tier together; domain integrations (apple, obsidian, ingest, etc.) live in the user's vault. The "auto-" / "loop-" / "platform-admin" naming family belongs in one place; the audit's import-count signal is what surfaced inconsistencies in earlier passes.

### MCP server topology

```
PROJECT TIER (always-on; ships with framework)
  augur-core
    - Registry: list-skills, find-skill, get-skill, list-skill-actions
    - Cross-bundle: cross-skill, unified-search, search-skill-knowledge
    - Browse: browse-index, get-scheduled-execution-detail, list-api-routes
    - Discovers connected MCP servers from the user's client config at startup
    - ~10–15 tools, always loaded
  augur-framework
    - MCP wrappers around src/lib/* exposing user-callable framework operations
    - Tools call into src/lib/ai, src/lib/index, src/lib/extraction, src/lib/runtime,
      src/lib/knowledge in-process
    - Multiplexes the operational MCP tools from auto-skill-quality (1 tool) and
      platform-admin (~22 tools) — these stay project-tier with the rest of their
      operational family rather than running as separate processes
    - Hosts the daemon process bundle's status/control surface
    - ~50 tools (bounded; not the 200-tool monolith)

VAULT TIER (per-user domain integrations; each its own MCP server)
  augur-apple
  augur-lifestyle
  augur-ingest
  augur-obsidian
  augur-file-manager
  + future user-installed bundles
```

Visibility per client falls out of which MCP servers each client config registers. The user's project-tier config (committed to the repo) registers `augur-core` and `augur-framework` for every Augur user. The user's user-tier config (per-machine, in their home directory) registers vault bundles. Each client supports this layering natively:

| Client | Project-tier config | User-tier config |
|---|---|---|
| Claude Code | `.claude/settings.json` (repo-committed) | `~/.claude/settings.json` |
| Codex | `.codex/config.toml` (repo-referenced) | `~/.codex/config.toml` |
| Gemini | `.gemini/settings.json` (repo-committed) | `~/.gemini/settings.json` |
| Dashboard | reads MCP via `apps/dashboard/lib/mcp/` | reads vault registry from user vault |

No server-side allowlist. No per-client filter in `client_surface.py`. The protocol is used as designed.

### Discovery flow

```
1. User starts a client (Claude Code, Codex, etc.).
2. Client reads its merged config (project-tier + user-tier) and connects to each
   declared MCP server: augur-core, augur-framework, and any vault servers.
3. Each MCP server returns its tools/list per the standard MCP handshake.
   Tool counts are bounded: augur-core ~15, augur-framework ~25, vault servers
   small per-bundle. Total surface for a typical user is well under the
   threshold that triggers Claude Code's deferred-tools mechanism.
4. augur-core, on its own initialize, reads the same client config and indexes
   the other servers' tools/list responses to support cross-bundle operations
   (find-skill, unified-search, cross-skill).
5. SKILL.md files are discovered by each client through that client's
   own native skill-discovery path (Claude Code: bundle-rooted SKILL.md;
   Codex/Gemini: per-client export at build time).
```

The dashboard reads its data from the same set of connected MCP servers (via `apps/dashboard/lib/mcp/`), no different from any other client. The browse page's single MCP call (`browse-index`) is hosted by `augur-core` and reads from the on-disk RAG index populated by `src/lib/index/`. The dashboard does not depend on per-skill MCP servers being up — when a vault bundle isn't connected, its category contributes nothing to the index, which is the correct behavior.

### Per-tier cleanup the migration must perform

The audit caught three layering violations that the new architecture must not preserve:

1. **`src/config/mcp_tools.py` references `apple`.** Project code names a vault-private skill. Remove the reference; replace with dynamic discovery from connected MCP servers.
2. **Dashboard scripts hardcode references to `lifestyle`.** Generalize to read from the skill registry, not specific skill names.
3. **`daemon` imports `platform-admin`.** Runtime depends on dev tooling. Move shared utilities (`ops/stale_paths.py`, `ops/run_system_audits.py` content) into `src/lib/runtime/` so daemon and platform-admin both consume them.

Two minor coupling inversions are also part of the migration:

4. **`rag` imports `ingest`** (`rag/scripts/mcp/rag_tools.py`). Move the helper into `src/lib/index/` or invert the call.
5. **`ingest` imports `obsidian`** (`ingest/scripts/url_source_card.py`). Same — move shared logic to a library or invert.

### What this design replaces

| Before | After |
|---|---|
| `CURATED_VISIBLE_TOOLS` (frozenset literal in `client_surface.py`, hand-edited) | Per-client config layering, native to each client |
| `COWORK_VISIBLE_TOOLS` (second hardcoded set) | Removed; cowork is just another client with its own config |
| `filter_tools_for_client()` if/elif chain | Removed; clients connect to whichever servers their config names |
| `x-augur-visibility` SKILL.md frontmatter | Removed; not consulted by any consumer in the new design |
| `x-augur-hub` field driving dashboard layout | Replaced by `dashboard.yaml` `hub` field (or equivalent), schema owned by dashboard |
| `x-augur-tab`, `x-augur-data-deps`, etc. | Removed where redundant with bundle filesystem location; moved to `dashboard.yaml` where they encode real dashboard intent |
| Single 200-tool MCP server (`augur`) | augur-core + augur-framework + N vault servers, bounded surfaces per server |
| Skills registering Python libraries used by other skills | Libraries moved to `src/lib/`; bundles only hold consumer-facing surface |
| `_config/config.yaml` mixing dashboard + loops + commands | Split: `dashboard.yaml` + `loops.yaml` + `commands/*.md` |

### What this design does NOT specify

The following are deliberately out of scope and will be addressed by follow-up specs:

- **Layer 2 — Server-side discovery details.** How `augur-core` discovers connected servers, the cross-server tool index format, error handling when servers go offline.
- **Layer 3 — Per-client consumption profiles.** Concrete config schemas per client, the build-time export pipeline (SKILL.md → `.codex/skills/`, commands → per-client formats), token-budget tuning.
- **Layer 4 — Migration plan.** The phased cutover: which bundle moves first, compatibility shims, ADR sequencing, dashboard regression strategy, the dual-stack period.
- **Per-bundle dashboard.yaml schema.** A complete documented schema for the dashboard's contribution manifest. The current `_config/config.yaml` is an acceptable starting point; a documented schema is its own work item.
- **`loops.yaml` schema.** Owned by daemon; the current loop registry format is the working spec until a Layer 4 design upgrades it.

## Risks and Trade-offs

### Risks

- **Process count growth.** Vault tier with 5 bundles = 5 stdio processes; project tier adds 2 (`augur-core` + `augur-framework`) plus the daemon process. Per-process startup and memory cost is real but bounded; the previous 200-tool single server is gone, and users typically install 2–4 vault bundles, not all 5.
- **augur-core single-server failure mode.** If `augur-core` is down, browse and unified-search are dead. Mitigation: augur-core is intentionally small and stable; its failure should be rare and recoverable.
- **Discovery latency.** augur-core scanning N other MCP servers at startup adds initialization time. Acceptable as a one-time cost; cache via `serverInfo` versioning.
- **Library refactor surface area.** Moving `ai`, `rag`, `document-extractor`, daemon library code into `src/lib/` touches many import sites. Mitigated by Layer 4 phasing.
- **Vault portability.** Bundles installed in one user's vault aren't portable to another user without explicit export. Acceptable — that's exactly the trust boundary we want.

### Trade-offs accepted

- **The dashboard's contribution schema is owned by the dashboard, not standardized.** No consumer-neutral schema exists for "blocks, pages, modals" across UIs. We accept dashboard-ownership of `dashboard.yaml`'s schema in exchange for keeping the protocol layers (MCP, SKILL.md) standards-pure.
- **`loops.yaml` and daemon's loop registry are Augur-internal.** Not standardized across ecosystems because no daemon framework standard exists. Internal-only is fine.
- **Per-bundle vault servers (vs. one multiplexed `augur-vault`) cost N processes.** Trade for granularity: each bundle is independently enable/disable-able via client config, and the trust boundary is per-bundle.

## Verification — How we know this works

The design is verified at three checkpoints during implementation:

1. **After library extraction (Layer 4 Phase 1):** The five `src/lib/` packages exist and pass tests. The `skills/` directories that lost library content still build their MCP servers correctly. Imports in `apps/dashboard/`, `src/mcp/`, `daemon/` all resolve to the new paths.
2. **After server split (Layer 4 Phase 2):** `augur-core` and `augur-framework` are running as separate stdio processes. Vault bundles connect as separate servers. Each client's config (Claude Code, Codex, Gemini, dashboard) lists each connected server. `tools/list` against any individual server returns a bounded tool count.
3. **After visibility filter removal (Layer 4 Phase 3):** `CURATED_VISIBLE_TOOLS` is deleted from `client_surface.py`. Claude Code session opens with all framework + enabled vault tools visible (deferred or schema-loaded depending on count). Codex and Gemini sessions show the same. The 91%-hidden problem cannot recur because the mechanism that caused it is gone.

The acceptance criterion is end-user-observable: a fresh Augur install + a fresh user vault should result in Claude Code, Codex, and Gemini each seeing the same set of MCP tools (the framework set), with vault bundles appearing in each client whenever the user has wired them into the user-tier config. No hand-edited allowlists. No proprietary `x-augur-visibility` field is consulted anywhere in the protocol path.
