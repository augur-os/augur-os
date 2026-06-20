---
status: Implemented
date: 2026-05-22
deciders:
  - gsannikov
related: [ADR-748, ADR-491, ADR-601, ADR-760]
hub: null
tags: [browse, dashboard, skills, decentralization, item-actions]
superseded_by: null
spec_file: 2026-05-22-browse-item-actions-all-tabs-design.md
plan_file: 2026-05-22-browse-item-actions-all-tabs.md
---

# ADR-776: Browse per-item actions for all tabs

> **ADR-776 is an index file.** The substantive design lives in the linked spec.
> This file carries pointers, status, and a one-line decision summary.

## Decision summary

Every Browse tab gains category-specific per-item actions declared in skill-owned
`<skill>/augur/browse-actions.yaml`, aggregated by a build-time generator into a
typed registry the dashboard reads, supporting two action kinds — `ai` (editable
chat draft) and `direct` (run-now MCP tool with toast). This decentralizes and
generalizes the agent-profiles + wiki proof-of-concept.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-22-browse-item-actions-all-tabs-design.md`](../superpowers/specs/2026-05-22-browse-item-actions-all-tabs-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-22-browse-item-actions-all-tabs.md`](../superpowers/plans/2026-05-22-browse-item-actions-all-tabs.md)

## Status notes

Implemented 2026-05-23. Browse per-item actions are now declared in
skill-owned `augur/browse-actions.yaml` files and merged by the dashboard
build into the ignored generated registry. `itemActions.ts` is a loader over
that registry, and the card/list overflow, file/note item panels, skills panel,
and background-routine panel all render the generated actions.

The runtime supports both `ai` editable chat-draft actions and `direct` MCP
actions with placeholder-resolved args, optional confirmation, toast feedback,
and declared react-query invalidation. Browser verification on the worktree
dashboard (`http://localhost:3004/browse?view=skills`) exercised real Browse
data and a real direct `Health` action (`skill-resolvable-report`) returning
HTTP 200 with a success toast. A broader sweep confirmed populated Browse tabs
render their generated verbs without framework overlays; empty `workflow-definitions`
and `system-metadata` tabs remained empty in the current real index.

> **Numbering note:** this work was briefly authored in a parallel worktree as
> "ADR-775" while ADR-775 was already taken by the Offline-Mode Routing Matrix.
> ADR-776 is the canonical record; the duplicate `ADR-775-browse-item-actions`
> file was removed during the merge reconciliation (no content lost).

## Related

- ADR-748 — chat-dispatch of resolved prompts (the `ai` editable-draft mechanism).
- ADR-491 — config-driven dashboard pages (the build-time generator pattern reused).
- ADR-601 — project/team skills live under `project-brain` (where the YAML lives).
- ADR-760 — Browse Page UX cleanup.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "apps/dashboard/lib/browse/itemActions.ts: data map → loader over generated registry; adds directItemActionsFor"
  patterns_deprecated:
    - "Central per-category action data hand-written in itemActions.ts (→ skill-owned augur/browse-actions.yaml)"
  files_affected:
    - "apps/dashboard/lib/browse/itemActions.ts"
    - "apps/dashboard/lib/browse/generated-item-actions.ts (new, generated)"
    - "apps/dashboard/scripts/* (new generator)"
    - "project-brain/capabilities/skills/*/augur/browse-actions.yaml (new, per skill)"
    - "apps/dashboard/components/shared/BrowseDetailPanel.tsx (direct executor)"
    - "apps/dashboard/components/shared/BrowseCardShell.tsx, BrowseListRowCard.tsx (direct executor)"
    - "apps/dashboard/app/(views)/browse/page.tsx, BrowseContentGrid.tsx, BrowseDisplayRenderer.tsx (thread onItemDirect)"
```

## Implementation Prompt

> Paste this into a **fresh session** to implement ADR-776. Read the canonical
> design first: the spec
> `docs/superpowers/specs/2026-05-22-browse-item-actions-all-tabs-design.md` and
> this ADR (esp. the per-tab catalog tables + Architecture). The PoC mechanism
> (agent-profiles + wiki) already ships from the central `itemActions.ts`; this work
> decentralizes it and adds the `direct` kind.

**Mission:** Implement decentralized, skill-owned Browse per-item actions for all
tabs, with two action kinds (`ai` editable chat draft, `direct` run-now MCP tool),
per ADR-776.

**Augur guardrails — read before touching anything:**
- Stay on the current worktree branch; never `git checkout -b` in the main checkout
  (breaks dashboard startup). Commit to the worktree branch; `/dev-merge` integrates.
- The worktree dashboard runs on its OWN port (read `.augur-worktree.yaml`, e.g.
  `:3003`), NOT `:3000` (that's the main checkout). Restart/verify only via
  `/dev-build` or `bash apps/dashboard/scripts/start-dev.sh` — `npm run dev` is
  hook-blocked.
- **Rule 2 (decentralization):** action data lives in `<skill>/augur/browse-actions.yaml`,
  never a hand-written central map. Any genuinely framework-owned default set must be
  classified in `config/dashboard/README.md`.
- **Rule 28/34:** verify each tab in a real browser against real vault/index data —
  not curl/tsc alone. (devOnly tabs: preset `localStorage['augur:dashboard-mode']='development'`
  then click the in-app tab; hard-nav to `?view=` races back to Skills.)
- **Rule 29:** `Run` verbs for tests/build/lint route through the auto-loops
  (`/auto-test-*`, `/dev-build`), never raw runners.
- **Do NOT use Agent `isolation: "worktree"`** for parallel subagents in Augur — it
  returns the main repo path, so parallel agents collide on `git checkout`. For
  fan-out, spawn parallel subagents WITHOUT worktree isolation and only on disjoint
  files; otherwise run sequentially.
- Direct-kind mutating ops set `confirm: true`; nothing destructive / credential /
  financial. `Sweep` archives, never hard-deletes.

**Execution:** Drive via `superpowers:subagent-driven-development` (one fresh
subagent per task; two-stage review; TDD: failing test → impl → commit). Phases 1–2
are the sequential critical path; Phase 3 fans out.

### Phase 1 — Foundation (sequential, critical path)
- **T1.1 [architect · opus]** Design the `browse-actions.yaml` schema + a JSON-schema
  validator (kinds, `{placeholder}` set, merge/dedupe rules, icon-in-icon-map +
  category-in-`BROWSE_CATEGORIES` checks) per spec §Architecture.1. TDD: validation
  tests first.
- **T1.2 [developer · opus]** Build the build-time generator (glob shared +
  private-vault `**/augur/browse-actions.yaml`, validate, merge by category) →
  `apps/dashboard/lib/browse/generated-item-actions.ts`; wire into
  `pnpm run ensure-generated` beside the ADR-491 page scanner. Refactor
  `itemActions.ts` into a loader exposing `aiItemActionsFor` +
  `directItemActionsFor`/`itemActionsFor`. TDD: generator fixtures → merged registry;
  rejection cases.
- **T1.3 [developer · sonnet]** Migrate shipped tabs: agent-profiles →
  `skills/ai/augur/browse-actions.yaml`, wiki → `skills/ingest/augur/browse-actions.yaml`;
  delete `AGENT_AI_ACTIONS`/`WIKI_AI_ACTIONS`; retarget `itemActions.test.ts`. Verify
  zero UX change on those two tabs (browser).
- **Gate:** tsc + eslint clean; generator + resolver tests green; agent-profiles &
  wiki unchanged live.

### Phase 2 — Direct executor (sequential, depends on Phase 1)
- **T2.1 [developer · opus]** Add `onItemDirect(action, item)` to `browse/page.tsx`;
  thread through `BrowseContentGrid` → `BrowseDisplayRenderer` → `BrowseCardShell` /
  `BrowseListRowCard` and `FileItemDetailPanel` (generalize the notes `Enrich`
  pattern). Resolve `args` placeholders, `mcpCall(tool, args)`, toast, invalidate the
  declared react-query keys.
- **T2.2 [security · opus]** Confirm-gate for `confirm:true`; safety review (no
  destructive/credential ops; rule-29 routing for run-verbs). TDD: executor +
  confirm-gate tests.
- **Gate:** one real direct action end-to-end (e.g. wiki *Find dead links* →
  `dream-dead-citations`) with toast + refetch on the worktree port.

### Phase 3 — Populate tabs (PARALLEL fan-out, disjoint files, NO worktree isolation)
Each tab's YAML lives in a different skill ⇒ disjoint files ⇒ parallel-safe. One
subagent per cluster [developer · sonnet], authoring YAML per the spec's per-tab
tables, then verifying each tab's overflow + panel render the verbs in a real browser:
- **T3.a content** — notes, documents, profile, drafts, archive (ingest, knowledge, document-extractor)
- **T3.b dev-tools** — adrs, commands, mcp-servers, mcp-tools, scripts, api-routes, tests, logs, system-metadata, workflow-definitions (augur-core, ai, platform-admin, routine-*, daemon)
- **T3.c misc** — pages, actions, integrations (plugin-pack, onboard)

### Phase 4 — Special-panel wiring (depends on Phase 1+2; two disjoint files → parallel-ok)
- **T4.1 [developer · sonnet]** Render catalog actions in `BrowseDetailPanel` (skills) Actions area.
- **T4.2 [developer · sonnet]** Render catalog actions in `BackgroundRoutineDetailPanel` (routines).

### Phase 5 — Verification & docs (validator · opus, last, sequential)
- **T5.1** Per-tab real-data browser sweep on the worktree port — one `ai` (draft
  prefilled, not sent) + one `direct` (runs, toast, refetch) per cluster. Run
  `/auto-test-pytest`, `/auto-test-dashboard`, `/auto-lint`. Update topic docs +
  `config/dashboard/README.md` (framework defaults). Then run every Completion Gate
  in the `/adr` Completion-Gates list — esp. #6 browser, #8 decentralization (zero
  new central data), #11 real-data value.

### On done
`/adr set 776 Implemented` → run the ADR post-write hook → hand off via
`superpowers:finishing-a-development-branch`.
