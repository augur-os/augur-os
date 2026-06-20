---
title: Browse per-item actions — all tabs (decentralized catalog + dual action kinds)
date: 2026-05-22
status: proposed
related_adrs: [ADR-748, ADR-491, ADR-601, ADR-760, ADR-758]
supersedes_spec: 2026-05-22-browse-tab-actions-agent-profiles-design.md
---

# Browse per-item actions — all tabs

## Problem

Browse is the universal discovery surface: every tab renders the same
`BrowseItem` card grid + detail panel (rule 32). After the PoC, exactly **two**
tabs offer category-appropriate item actions — **Agent Profiles** (Follow-up /
Enhance / Update / Sweep) and **Wiki** (Follow-up / Update / Find dead links /
Enhance). Both ship from a single hand-written central catalog
(`apps/dashboard/lib/browse/itemActions.ts`) and use only the **AI-prompt-draft**
mechanism (the action opens the chat with a resolved, editable, un-sent prompt).

Every other tab's panel/overflow still offers only generic file ops (Open /
Reveal / Copy) or a one-off direct button (notes' `Enrich`). There is nothing to
*do* with a document, an ADR, an MCP tool, a test, a routine, or a memory entry
from Browse — even though each has obvious, valuable, category-specific verbs
backed by real Augur tools.

We want **every Browse tab** to offer meaningful per-item actions, sourced and
owned the right way (rule 2), with both review-first AI actions and one-click
direct operations.

## What shipped (PoC — to be migrated, not discarded)

- **Catalog** `apps/dashboard/lib/browse/itemActions.ts` — `aiItemActionsFor(category)`
  returns a typed `AiItemAction[]` (`{id, label, icon, template(item)}`).
- **Dispatch** — AI actions resolve `template(item)` and hand the result to the
  chat as an **editable draft** (`chatStore.openChat({mode:"ide", draft:true})`),
  surfaced in both the **detail panel** (`FileItemDetailPanel`) and the **card
  overflow menu** (`BrowseCardShell` + `BrowseListRowCard`, threaded via
  `onItemPrompt` + `category`).
- **Tabs populated** — `agent-profiles`, `wiki`. Unit-tested
  (`tests/dashboard/browse/itemActions.test.ts`), verified live on `:3003`.

This spec keeps that runtime behavior and **re-homes its data** under the
decentralized model below; the PoC catalog file becomes a thin loader.

## Decisions (locked 2026-05-22)

1. **Decentralized, skill-owned catalog.** Each skill declares the actions for
   the Browse category it owns in skill-local config
   (`<skill>/augur/browse-actions.yaml`). A build-time generator aggregates every
   skill's declarations into one typed registry the dashboard reads. This matches
   rule 2 (skill-owned config lives in the skill) and reuses the ADR-491
   config-driven-pages generator pattern. The central
   `itemActions.ts` stops carrying data and becomes the registry loader + resolver.
2. **Two action kinds.** `kind: ai` opens an editable chat draft (multi-step /
   judgment verbs — Enhance, Update, Sweep, Summarize, Follow-up). `kind: direct`
   runs an MCP tool immediately with toast feedback + react-query invalidation
   (immediate ops — Reindex, Re-extract, Run, Invoke, Restart, Curate). The
   detail panel and card overflow gain a `direct` executor alongside the existing
   `onItemPrompt` draft path.

## Architecture

### 1. Skill config schema — `<skill>/augur/browse-actions.yaml`

```yaml
# project-brain/capabilities/skills/ingest/augur/browse-actions.yaml
# One file per skill; a skill may contribute to multiple categories.
categories:
  wiki:
    - id: wiki-update
      label: Update
      icon: RefreshCw          # must exist in apps/dashboard/lib/icon-map.ts
      kind: ai
      template: |
        Update the {title} wiki page ({path}). Re-scan its sources, reconcile the
        compiled-truth section against the timeline (ADR-740), and write back with
        wiki-scan-sources / wiki-read / wiki-update / wiki-write. Summarize changes.
    - id: wiki-dead-links
      label: Find dead links
      icon: Search
      kind: direct
      tool: dream-dead-citations     # MCP tool name (direct kind only)
      args: { page: "{path}" }       # placeholders resolved from the BrowseItem
      confirm: false                 # true → confirm dialog before running
      invalidates: [browse-index]    # react-query keys to refetch after success
  notes:
    - id: note-summarize
      label: Summarize
      icon: BookOpen
      kind: ai
      template: "Summarize the {title} note ({path}) into a tight executive summary + key insights."
```

- **Placeholders** `{title}`, `{path}`, `{id}`, `{hub}`, `{metadata.<key>}` are
  resolved from the active `BrowseItem` at click time (replaces today's TS
  `template(item)` closures). For `ai` → substituted into the draft body. For
  `direct` → substituted into `args` values.
- **Merge semantics** — multiple skills may declare actions for the same category;
  the generator concatenates them in skill load order. IDs are namespaced
  (`<category>-<verb>`) and deduped; collisions are a build error.
- **Category default** — the framework injects a universal **Follow-up** (`ai`,
  `"I'm looking at {title} ({path}). "`) for every category unless the skill
  declares its own, so every tab gets the lightweight conversational entry for free.

### 2. Build-time generator

A Node script in the existing `apps/dashboard/scripts` build pipeline (run by
`pnpm run ensure-generated`, beside the ADR-491 page scanner and block registry):

1. Glob `**/augur/browse-actions.yaml` across shared (`project-brain/.../skills/`)
   and private-vault skills.
2. Validate each against a JSON schema (kind ∈ {ai,direct}; `template` required
   for `ai`; `tool` required for `direct`; icon ∈ icon-map; category ∈
   `BROWSE_CATEGORIES`).
3. Merge by category, emit `apps/dashboard/lib/browse/generated-item-actions.ts`
   (gitignored generated output, like the tab/block registries) — a typed
   `Record<categoryId, ItemAction[]>`.

`itemActions.ts` imports the generated registry and exposes the stable resolvers
`aiItemActionsFor(category)` (filters `kind:ai`) and the new
`directItemActionsFor(category)` / `itemActionsFor(category)` — so the already-wired
panel + cards need no signature change.

### 3. Dispatch — dual executor

- **`ai`** — unchanged: `onItemPrompt(resolve(template, item))` → chat draft.
- **`direct`** — new `onItemDirect(action, item)` in the page, threaded the same
  way `onItemPrompt` is (page → grid → renderer → cards / panel). It resolves
  `args`, optionally confirms, calls `mcpCall(action.tool, args)` (or
  `executeBrowseAction` for navigate/copy kinds), toasts success/failure, and
  invalidates the declared react-query keys. Mirrors the existing notes `Enrich`
  button, generalized.

### 4. Migration of the two shipped tabs

Move the agent-profiles entries to `skills/ai/augur/browse-actions.yaml` and the
wiki entries to `skills/ingest/augur/browse-actions.yaml`; delete the hand-written
`AGENT_AI_ACTIONS` / `WIKI_AI_ACTIONS` arrays. `itemActions.test.ts` retargets to
assert against the generated registry. No runtime/UX change — the same four verbs
render on each tab.

### 5. Special-panel tabs

`skills` (rich `BrowseDetailPanel` with Actions/Prompts/Adopt) and
`background-routines` (`BackgroundRoutineDetailPanel`) do **not** use
`FileItemDetailPanel`, so their **detail panels** need explicit catalog wiring
(append the resolved actions to their existing Actions area). Their **card
overflow** already flows through the universal card components, so catalog actions
appear there immediately. Panel wiring for these two is a tracked sub-phase, not a
blocker for the other tabs.

## Full per-tab catalog (brainstorm)

Verbs, kind (`ai` = chat draft, `direct` = run-now MCP), backend, and the skill
that owns the declaration. Owner is a proposal; the plan finalizes ambiguous
cross-cutting categories.

### Content tabs

| Tab | Verbs (kind) | Backend(s) | Owner |
|---|---|---|---|
| notes | Summarize (ai), Enrich (direct), Clean (ai) | knowledge-summarize-file/url, enrich-article | ingest |
| documents | Summarize (ai), Re-extract (direct), Index (direct), Ask (ai) | knowledge-summarize-file, extract-document, index-documents | knowledge / document-extractor |
| wiki ✓ | Follow-up (ai), Update (ai), Find dead links (direct), Enhance (ai) | wiki-*, dream-dead-citations, wiki-lint | ingest |
| pages | Explain (ai), Edit config (ai) | agent edit of page YAML | plugin-pack |
| profile | Refine (ai), Curate (direct), Regenerate profile (direct) | memory-curate, memory-profile-regenerate | knowledge |
| skills △ | Enhance (ai), Audit (direct), Health (direct) | scan-skill-structure, skill-resolvable-report, get-skill-health | auto-skill-quality |
| actions | Run (direct), Explain (ai) | executeBrowseAction trigger | plugin-pack |
| drafts | Clean (ai), Publish (direct) | agent edit, promote | ingest |
| archive | Restore (direct) | un-archive op | ingest |

### System tabs

| Tab | Verbs (kind) | Backend(s) | Owner |
|---|---|---|---|
| integrations | Configure (direct→navigate), Test connection (direct) | navigate, integration health | onboard |
| extensions-bundles ✦ | (defer to manager surface) | Open Manager (exists) | plugin-pack |
| background-routines △ | Run now (direct), Pause/Resume (direct), View last run (direct) | routine trigger / schedule toggle / job ledger | routine-* / daemon |

### Dev tabs (devOnly)

| Tab | Verbs (kind) | Backend(s) | Owner |
|---|---|---|---|
| adrs | Implement (ai), Harden (ai), Check gaps (direct) | /adr implement, /adr harden, /adr gaps | augur-core |
| commands | Explain (ai), Edit (ai), Run (ai-draft†) | agent edit / dispatch | augur-core |
| mcp-servers | Restart (direct), Health check (direct) | get-infrastructure-health, restart script | platform-admin |
| mcp-tools | Invoke (ai), Check coverage (direct), Explain (ai) | skill-resolvable-report | ai |
| api-routes | Test (direct, GET-only), Explain (ai) | route fetch | platform-admin |
| scripts | Run (ai-draft†), Explain (ai), Refactor (ai) | agent / dispatch | platform-admin |
| workflow-definitions | Run (direct), Edit (ai) | routine trigger | routine-* |
| agent-profiles ✓ | Follow-up (ai), Enhance (ai), Update (ai), Sweep (ai) | sync_agents, registry.json, .archive/ | ai |
| tests | Run (direct→auto-loop†), Explain failure (ai), Fix (ai) | /auto-test-pytest, /auto-test-build | platform-admin |
| logs | Analyze (ai), Find errors (ai) | seed chat over log content | daemon |
| system-metadata | Follow-up (ai) only | — | platform-admin |

✓ shipped · △ special panel (needs panel wiring) · ✦ manager-surface tab
(catalog minimal) · † safety-gated below.

## Safety constraints

- **Rule 29 loops** — `Run` on `tests` / `scripts` / build-touching verbs must
  route through the auto-loops (`/auto-test-*`, `/dev-build`), never raw runners.
  Implemented either as an `ai` draft that names the loop, or a `direct` action
  whose tool *is* the loop trigger. Default to `ai-draft` (†) where a raw run
  would bypass a loop.
- **Prohibited / review-first** — no destructive direct ops. `Sweep` archives,
  never hard-deletes. Mutating direct verbs (`Restart`, `Curate`, `Set status`,
  `Run workflow`) set `confirm: true`. Nothing touches access controls,
  credentials, or money (safety rules).
- **Placeholder hygiene** — metadata interpolated into templates/args is treated
  as data; the resolver does not eval and escapes shell-bound args.

## Verification plan (rule 34 — real data)

- **Generator** — unit test: fixtures of `browse-actions.yaml` → expected merged
  registry; schema-rejection cases (bad kind, missing tool/template, unknown icon/
  category, id collision).
- **Resolver** — `aiItemActionsFor` / `directItemActionsFor` over the generated
  registry; placeholder substitution incl. missing-path fallback.
- **Per-tab live checks** on `:3003`: for each populated tab, open a real item's
  card overflow + detail panel, confirm the declared verbs render; fire one `ai`
  (draft prefilled, not sent) and one `direct` (tool runs, toast, data refetched)
  per cluster against real vault/index data. Screenshot each cluster.
- tsc + eslint clean; existing tabs unchanged (regression check on notes/skills).

## Alternatives considered

1. **Keep the central `itemActions.ts` for all tabs** (rejected, Q1) — fastest,
   but a 23-tab central map editing every skill's verbs in one dashboard-owned
   file is exactly the central-config debt rule 2 forbids.
2. **AI-prompt-draft only** (rejected, Q2) — zero new plumbing, but `Run test`,
   `Reindex`, `Invoke tool`, `Restart MCP` read as weak drafted prompts; dev tabs
   need one-click direct ops to be useful.
3. **Per-skill React components instead of declarative YAML** — maximal
   flexibility, but pushes UI into skills, breaks the universal card mechanism
   (rule 32), and can't be validated/aggregated at build time. Rejected.

## Open questions / risks

- **Cross-cutting ownership** — `mcp-tools`, `scripts`, `api-routes`,
  `system-metadata` aren't cleanly owned by one skill. Proposal: a small
  framework-default set ships with the dashboard (classified in
  `config/dashboard/README.md`) for genuinely framework-owned categories; everything
  domain-specific is skill-owned. The plan pins each.
- **Special-panel wiring** (`skills`, `background-routines`) — sequence after the
  `FileItemDetailPanel` tabs.
- **Direct-kind arg safety** — finalize the `args` placeholder + confirm contract
  before wiring mutating tools.

## Implementation order (for the plan / `/adr implement`)

1. Schema + generator + generated registry; `itemActions.ts` → loader. Migrate the
   two shipped tabs to skill YAML (no UX change). Tests green.
2. `direct` executor wired into page → grid → cards + `FileItemDetailPanel`
   (generalize the notes `Enrich` pattern); toast + invalidation; confirm gate.
3. Populate content tabs (notes, documents, profile, drafts), then dev tabs.
4. Special-panel wiring (skills, background-routines).
5. Per-tab real-data verification; topic-doc + `config/dashboard/README.md` updates.

## Related

- ADR-748 — chat-dispatch of resolved prompts (the `ai` draft mechanism).
- ADR-491 — config-driven dashboard pages (the generator pattern reused here).
- ADR-601 — skills under `project-brain` (where the YAML lives).
- ADR-760 — Browse page UX cleanup. Rule 32 — every tab is the same card grid.
