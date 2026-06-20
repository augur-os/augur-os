# Browse Per-Item Actions — All Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (one fresh subagent per task, two-stage review) or `superpowers:executing-plans`.
> Steps use checkbox (`- [ ]`) syntax. Canonical design: ADR-776 +
> `docs/superpowers/specs/2026-05-22-browse-item-actions-all-tabs-design.md`
> (read the per-tab catalog tables there — this plan does not re-list every verb).

**Goal:** Give every Browse tab category-appropriate per-item actions, sourced
from **skill-owned** `<skill>/augur/browse-actions.yaml` (rule 2), aggregated by a
build-time generator into a typed registry the dashboard reads, supporting two
action kinds — `ai` (editable chat draft) and `direct` (run-now MCP tool + toast).
Generalizes the shipped agent-profiles + wiki proof-of-concept.

**Architecture:** Skills declare actions in YAML → a Node generator validates +
merges by category → `apps/dashboard/lib/browse/generated-item-actions.ts` (typed,
gitignored). `itemActions.ts` becomes a loader exposing `aiItemActionsFor`,
`directItemActionsFor`, `itemActionsFor` over the generated registry, with
placeholder resolution. The detail panel + card overflow already render
`aiItemActionsFor`; this plan adds the parallel `direct` executor and re-homes the
data.

**Tech Stack:** Next.js + React + TS dashboard; Zustand `chatStore`
(`openChat`/`draft`); `mcpCall` + react-query for direct ops; Jest; `@/` alias;
Node build scripts (beside the ADR-491 page scanner) for the generator; PyYAML/JS
YAML for parsing skill config.

**Parallelization:** Tasks 1→4 are the sequential critical path. Tasks 5/6/7
(per-tab YAML authoring) touch **disjoint per-skill files** and are parallel-safe —
spawn one subagent per task **without** Agent `isolation:"worktree"` (it returns the
main repo path in Augur and collides; run them in the current worktree on disjoint
files). Task 8's two panels are also disjoint.

**Augur guardrails:** stay on the worktree branch (never `git checkout -b` in main);
the worktree dashboard runs on its OWN port from `.augur-worktree.yaml` (e.g. :3003),
not :3000; restart/verify only via `/dev-build` or `start-dev.sh`; verify in a real
browser (rule 28/34); `Run` verbs route through auto-loops (rule 29); direct mutating
ops set `confirm:true`; nothing destructive/credential/financial.

---

## File Structure

- **Create** `apps/dashboard/lib/browse/itemActionSchema.ts` — TS types + a pure
  validator for one parsed `browse-actions.yaml` document. Unit-testable.
- **Create** `apps/dashboard/scripts/generate-item-actions.mjs` — build-time
  generator (glob skills' YAML → validate → merge → emit registry). Wired into
  `pnpm run ensure-generated`.
- **Create** `apps/dashboard/lib/browse/generated-item-actions.ts` — generated,
  gitignored registry (`Record<categoryId, GeneratedItemAction[]>`).
- **Modify** `apps/dashboard/lib/browse/itemActions.ts` — loader + resolver over
  the generated registry; keep `aiItemActionsFor` stable, add `directItemActionsFor`
  / `itemActionsFor`.
- **Create** `project-brain/capabilities/skills/<skill>/augur/browse-actions.yaml`
  — one per contributing skill (Tasks 3, 5, 6, 7).
- **Modify** `apps/dashboard/app/(views)/browse/page.tsx`,
  `BrowseContentGrid.tsx`, `BrowseDisplayRenderer.tsx`,
  `components/shared/BrowseCardShell.tsx`, `BrowseListRowCard.tsx`,
  `components/shared/BrowseDetailPanel.tsx` — thread + render the `direct` executor.
- **Modify** `tests/dashboard/browse/itemActions.test.ts` + new generator/resolver
  tests under `tests/dashboard/browse/`.
- **Modify** `config/dashboard/README.md` — classify any framework-default actions.

---

## Task 1: Action schema + validator (pure)

**Files:** Create `apps/dashboard/lib/browse/itemActionSchema.ts`; test
`tests/dashboard/browse/itemActionSchema.test.ts`.

- [ ] **Step 1 — failing test.** Assert the validator: accepts a well-formed doc
  (one `ai`, one `direct`); rejects `kind` ∉ {ai,direct}; rejects `ai` without
  `template`; rejects `direct` without `tool`; rejects an icon not in the icon-map;
  rejects a category not in `BROWSE_CATEGORIES`; rejects duplicate action ids.
- [ ] **Step 2 — run, verify it fails** (`cd apps/dashboard && npx jest itemActionSchema`).
- [ ] **Step 3 — implement.** Define and export:

  ```ts
  export type ItemActionKind = 'ai' | 'direct';
  export interface ItemActionDef {
    id: string; label: string; icon: string; kind: ItemActionKind;
    template?: string;                  // ai (required)
    tool?: string;                      // direct (required)
    args?: Record<string, string>;      // direct (placeholder-templated)
    confirm?: boolean;                  // direct mutation guard
    invalidates?: string[];             // react-query keys to refetch
  }
  export interface BrowseActionsDoc { categories: Record<string, ItemActionDef[]>; }
  export function validateBrowseActionsDoc(
    doc: unknown, ctx: { validCategories: Set<string>; validIcons: Set<string> },
  ): { ok: true; doc: BrowseActionsDoc } | { ok: false; errors: string[] };
  ```

  Validate kind→required-field, icon, category, and per-category id uniqueness.
- [ ] **Step 4 — run, verify it passes.**
- [ ] **Step 5 — commit** (`Skip-Verify: pure schema/validator + jest, no rendered surface`).

---

## Task 2: Generator + registry + loader

**Files:** Create `apps/dashboard/scripts/generate-item-actions.mjs`,
`apps/dashboard/lib/browse/generated-item-actions.ts` (generated); modify
`apps/dashboard/lib/browse/itemActions.ts`, `apps/dashboard/package.json`
(`ensure-generated`), `.gitignore`; tests
`tests/dashboard/browse/itemActions.test.ts` (resolver) + a generator test.

- [ ] **Step 1 — failing resolver test.** Cover placeholder resolution
  (`{title}`, `{path}`, `{id}`, `{hub}`, `{metadata.x}`), missing-placeholder →
  empty string, `aiItemActionsFor` filters `kind:ai`, `directItemActionsFor`
  filters `kind:direct`.
- [ ] **Step 2 — run, verify it fails.**
- [ ] **Step 3 — implement the generator.** Glob
  `project-brain/capabilities/skills/**/augur/browse-actions.yaml` + private-vault
  `skills/**/augur/browse-actions.yaml`; parse YAML; `validateBrowseActionsDoc`;
  merge by category (concat in deterministic skill order); hard-fail the build on
  any validation error or cross-skill id collision; emit
  `generated-item-actions.ts` exporting `GENERATED_ITEM_ACTIONS: Record<string, ItemActionDef[]>`.
  Add `generate-item-actions` to `ensure-generated`; gitignore the output (mirror the
  tab/block registries).
- [ ] **Step 4 — implement the loader** in `itemActions.ts`:

  ```ts
  import { GENERATED_ITEM_ACTIONS } from './generated-item-actions';
  import type { ItemActionDef } from './itemActionSchema';
  export interface AiItemActionItem { title: string; path?: string; metadata?: Record<string,string>; }
  export interface AiItemAction { id: string; label: string; icon: string; template: (i: AiItemActionItem) => string; }
  export interface DirectItemAction extends ItemActionDef { kind: 'direct'; }

  function resolve(tpl: string, i: AiItemActionItem): string {
    return tpl.replace(/\{(title|path|id|hub|metadata\.[A-Za-z0-9_]+)\}/g, (_, k) => {
      if (k === 'title') return i.title ?? '';
      if (k === 'path') return i.path ?? '';
      if (k.startsWith('metadata.')) return i.metadata?.[k.slice(9)] ?? '';
      return (i as Record<string, string>)[k] ?? '';
    });
  }
  export function aiItemActionsFor(category?: string): AiItemAction[] {
    return (category ? GENERATED_ITEM_ACTIONS[category] ?? [] : [])
      .filter(a => a.kind === 'ai')
      .map(a => ({ id: a.id, label: a.label, icon: a.icon, template: (i) => resolve(a.template!, i) }));
  }
  export function directItemActionsFor(category?: string): DirectItemAction[] {
    return (category ? GENERATED_ITEM_ACTIONS[category] ?? [] : []).filter((a): a is DirectItemAction => a.kind === 'direct');
  }
  ```

  > **Migration nuance:** the PoC's synthetic path fallback
  > (`plugins/agents/{title}.md` when `path` is missing) becomes plain `{path}` —
  > indexed file-backed items always carry a real `path`, so drop the fallback and
  > update the corresponding test. The wiki "omit `(path)` parenthetical when empty"
  > nicety is accepted as lost; templates assume `{path}` is present.
- [ ] **Step 5 — run resolver + generator tests, verify pass.**
- [ ] **Step 6 — `pnpm run ensure-generated && npx tsc --noEmit`,** verify the
  registry generates and typechecks. (At this point the registry may be empty until
  Task 3 adds YAML — that's expected; assert the file is generated and valid.)
- [ ] **Step 7 — commit** (`Skip-Verify: generator + loader, jest + tsc; no rendered surface yet`).

---

## Task 3: Migrate the two shipped tabs to skill YAML (behavior-preserving)

**Files:** Create `project-brain/capabilities/skills/ai/augur/browse-actions.yaml`
(agent-profiles), `project-brain/capabilities/skills/ingest/augur/browse-actions.yaml`
(wiki); modify `apps/dashboard/lib/browse/itemActions.ts` (delete
`AGENT_AI_ACTIONS`/`WIKI_AI_ACTIONS`); modify `tests/dashboard/browse/itemActions.test.ts`.

- [ ] **Step 1.** Author the two YAML files reproducing today's verbs verbatim
  (agent-profiles: Follow-up/Enhance/Update/Sweep; wiki: Follow-up/Update/Find dead
  links/Enhance) using `{title}`/`{path}` placeholders. Keep wiki *Find dead links*
  `kind: ai` for now (it can flip to `direct` in Task 6 once the executor exists).
- [ ] **Step 2.** Delete the hand-written arrays from `itemActions.ts`; the loader
  now sources both tabs from the generated registry.
- [ ] **Step 3.** `pnpm run ensure-generated`; retarget `itemActions.test.ts` to
  assert against the generated registry (same ids/order, template substrings). Drop
  the synthetic-path-fallback assertion (see Task 2 nuance). Keep the negative-case
  assertions (`notes`/`skills` → `[]`).
- [ ] **Step 4.** `npx jest browse/itemActions` + `tsc` + eslint — all green.
- [ ] **Step 5 — browser check** on the worktree port: agent-profiles + wiki card
  overflow and detail panel render the **same** four verbs as before; one action
  still prefills the chat as an un-sent draft.
- [ ] **Step 6 — commit** (`Verified-Browser: chrome-mcp (:PORT — agent-profiles + wiki unchanged after migration)`).

---

## Task 4: Direct-action executor (card + panel)

**Files:** Modify `apps/dashboard/app/(views)/browse/page.tsx`,
`BrowseContentGrid.tsx`, `BrowseDisplayRenderer.tsx`,
`components/shared/BrowseCardShell.tsx`, `BrowseListRowCard.tsx`,
`components/shared/BrowseDetailPanel.tsx`; test
`tests/dashboard/browse/directExecutor.test.ts`.

- [ ] **Step 1 — failing test** for the arg-resolver + executor contract (resolves
  `args` placeholders from the item; calls `mcpCall(tool, args)`; honors `confirm`;
  invalidates the declared keys). Mock `mcpCall`.
- [ ] **Step 2 — run, verify it fails.**
- [ ] **Step 3 — implement `onItemDirect`** in `page.tsx` (mirror the notes
  `Enrich` mutation pattern): resolve args, optional confirm dialog, `mcpCall`,
  toast success/error, `queryClient.invalidateQueries` per `invalidates`. Thread
  `onItemDirect` + `directItemActionsFor(category)` through grid → renderer → cards
  and `FileItemDetailPanel`, exactly as `onItemPrompt`/`category` are threaded
  today. Render direct actions as buttons (panel) / overflow items (cards) alongside
  the `ai` actions.
- [ ] **Step 4 — confirm gate:** `confirm:true` actions show a confirm step before
  running; mutating tools must set it. Security review: no destructive/credential
  ops; `Run`-style verbs route to auto-loops, not raw runners.
- [ ] **Step 5 — typecheck + lint + jest.**
- [ ] **Step 6 — browser check:** add a temporary `direct` action to wiki YAML (or
  flip *Find dead links* to `direct` → `dream-dead-citations`), run it on a real wiki
  page, confirm toast + refetch on the worktree port.
- [ ] **Step 7 — commit** (`Verified-Browser: chrome-mcp (:PORT — direct action runs, toast + refetch)`).

---

## Task 5: Populate content tabs  *(parallel-safe — disjoint skill files)*

**Files:** `augur/browse-actions.yaml` in `ingest` (notes, drafts, archive),
`knowledge` (profile, documents), `document-extractor` (documents extract verbs).

- [ ] Author per the spec's **Content tabs** table — notes (Summarize ai, Enrich
  direct→`enrich-article`, Clean ai), documents (Summarize ai, Re-extract
  direct→`extract-document`, Index direct→`index-documents`, Ask ai), profile (Refine
  ai, Curate direct→`memory-curate`, Regenerate direct→`memory-profile-regenerate`),
  drafts (Clean ai, Publish direct), archive (Restore direct).
- [ ] `ensure-generated`; per-tab browser check (overflow + panel render verbs; one
  ai draft + one direct run on a real item).
- [ ] Commit (`Verified-Browser: chrome-mcp (:PORT — notes/documents/profile/drafts/archive)`).

## Task 6: Populate dev tabs  *(parallel-safe — disjoint skill files)*

**Files:** `augur-core` (adrs, commands), `ai` (mcp-tools), `platform-admin`
(mcp-servers, scripts, api-routes, tests, system-metadata), `daemon` (logs),
`routine-*` (workflow-definitions).

- [ ] Author per the spec's **Dev tabs** table. Honor rule 29: `Run` on tests/
  scripts/build is an `ai`-draft naming the auto-loop **or** a `direct` whose tool
  *is* the loop trigger — never a raw runner. Mutating verbs (`Restart`, `Set
  status`, `Run workflow`) set `confirm:true`. Flip wiki *Find dead links* → `direct`.
- [ ] `ensure-generated`; per-tab browser check on devOnly tabs (preset
  `localStorage['augur:dashboard-mode']='development'`, click the in-app tab).
- [ ] Commit (`Verified-Browser: chrome-mcp (:PORT — adrs/commands/mcp-*/scripts/tests/logs)`).

## Task 7: Populate misc tabs  *(parallel-safe — disjoint skill files)*

**Files:** `plugin-pack` (pages, actions, extensions-bundles minimal),
`onboard` (integrations).

- [ ] Author per the spec's **System tabs** + pages/actions rows. `integrations`
  *Configure* is direct→navigate only (never mutate access controls — safety rule);
  `extensions-bundles` defers to its manager surface (Follow-up only).
- [ ] `ensure-generated`; browser check.
- [ ] Commit (`Verified-Browser: chrome-mcp (:PORT — pages/actions/integrations)`).

---

## Task 8: Special-panel wiring  *(two disjoint files — parallel-ok)*

**Files:** `components/shared/BrowseDetailPanel.tsx` (the `BrowseDetailPanel` skills
view) + `BackgroundRoutineDetailPanel`.

- [ ] **T8.1** Render `aiItemActionsFor('skills')` + `directItemActionsFor('skills')`
  in the skills `BrowseDetailPanel` Actions area (alongside the existing
  Actions/Prompts/Adopt), wired to the same `onItemPrompt`/`onItemDirect`.
- [ ] **T8.2** Same for `BackgroundRoutineDetailPanel` (routines). (Card overflow
  already shows them via the universal cards.)
- [ ] Browser check both; commit (`Verified-Browser: chrome-mcp (:PORT — skills + routines panels)`).

---

## Task 9: Verification sweep + docs

**Files:** `config/dashboard/README.md`, `docs/agent-topics/DASHBOARD.md` (or the
browse topic doc).

- [ ] Per-tab real-data sweep on the worktree port: every populated tab renders its
  verbs in card overflow + panel; one `ai` (draft prefilled, not sent) + one `direct`
  (runs, toast, refetch) per cluster against real vault/index data.
- [ ] `/auto-test-pytest`, `/auto-test-dashboard`, `/auto-lint`.
- [ ] Classify any framework-default action set in `config/dashboard/README.md`
  (rule 2); document the `browse-actions.yaml` convention in the browse/dashboard
  topic doc.
- [ ] Run every ADR Completion Gate (esp. #6 browser, #8 decentralization — zero new
  central data, #11 real-data value). Flip ADR-776 → Implemented (`/adr set 776
  Implemented`) + post-write hook + `superpowers:finishing-a-development-branch`.
- [ ] Commit (`Verified-Browser: chrome-mcp (:PORT — full per-tab sweep)`).

---

## Self-Review

**Spec coverage:** decentralized skill-owned catalog (Tasks 1–3) ✓; both action
kinds — `ai` existing + `direct` new (Task 4) ✓; all tabs populated (Tasks 5–7) ✓;
special panels (Task 8) ✓; framework-default classification + docs (Task 9) ✓;
universal Follow-up default — implement in the generator (inject when a category
declares none) as part of Task 2 ✓.

**Decisions honored:** Q1 decentralized (YAML + generator, no central data map —
rule 2 / gate #8) ✓; Q2 both kinds (Task 4 executor) ✓.

**Safety:** rule-29 loop routing (Task 6) ✓; `confirm:true` mutation gate (Task 4) ✓;
no destructive/credential ops; Sweep archives (inherited from PoC) ✓; `isolation:
"worktree"` avoided for parallel fan-out ✓.

**Migration risk:** behavior-preserving for agent-profiles + wiki (Task 3) with the
synthetic-path-fallback nuance documented; the loader keeps `aiItemActionsFor` stable
so the already-wired panel/cards need no change.

**Placeholder scan:** no TBD/TODO; the one runtime contract (direct executor + arg
resolution) is specified with a test in Task 4. Per-tab verb details live in the spec
tables (referenced, not duplicated) to keep this plan the execution layer.
