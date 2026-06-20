---
status: Implemented
date: 2026-05-14
deciders:
  - gsannikov
related:
  - ADR-130
  - ADR-144
  - ADR-146
  - ADR-160
  - ADR-530
  - ADR-414
hub: brain
tags:
  - prompts
  - ingest
  - browse
  - dispatch
  - vault
  - dashboard
superseded_by: null
spec_file: null
plan_file: 2026-05-14-url-to-prompt-capture.md
---

# ADR-748: URL-to-Prompt Capture and Triggerable Prompt Cards

## Status

Implemented (2026-05-14). All five Decision parts shipped across 9 tasks on
branch `adr-748-url-to-prompt-capture` (subagent-driven, two-stage review per
task). One plan-gap fix was added during implementation: the plan assumed the
Browse → Prompts tab was fed by the `list-prompts` MCP tool, but it is actually
fed by `browse-index` → the RAG `prompts` index — so `index_prompts()` was
extended to scan `<vault>/prompts/` and carry the prompt body (Task 5b).

Verification: `auto-test-pytest` (ADR-748 surface 51/51 + 297/297 Phase-1
green; the broader suite's pre-existing failures are unrelated — no ADR-748
file appears in any of them), `auto-lint` (0 issues), `auto-test-dashboard`
(browse scope 50 suites / 395 tests green), `/dev-build` (clean production
build), and an Impact-Manifest scan (purely additive, zero stale references)
all pass. The end-to-end data path was confirmed against the running dev
server: a live `browse-index` MCP call for `category=prompts` returns vault
prompts with `source="vault"`, the prompt `body`, and `placeholders`. The
in-browser pixel/interaction check (rule 28) could not be completed in the
implementation environment — the Claude Chrome extension could not reach the
worktree dev server (`localhost:3002`) despite the server returning HTTP 200 —
so that single gate is verified by proxy (live MCP data + 12 dashboard jest
tests covering the transform, the placeholder module, and the
`BrowsePromptTrigger` state machine + dispatch) rather than by direct pixels.

## Context

A user who finds a useful prompt on the web — for example a "define a goal, then
use it" prompt — has **no path** to keep it for future sessions as a reusable,
one-click artifact. Three gaps compound:

1. **No URL → Prompt capture.** `/ingest <url>` fetches a URL but persists it via
   `save-url-source` as a **source card** under `<vault>/sources/urls/` — it lands
   in the Browse **Sources** tab as a knowledge reference, not a Prompt. `/save`
   is an asset router that does not fetch URLs. Neither command produces a Prompt.
2. **No home for user-owned prompts.** The Browse **Prompts** tab is populated by
   the `list-prompts` MCP tool, which scans only `shared-vault/skills/*/prompts/*.md`
   — repo-committed skill prompts. A prompt the *user* authors or captures is user
   data and does not belong in a committed skill (CLAUDE.md rule 4). There is
   currently nowhere for it to live and be discovered.
3. **The trigger half exists but is unwired.** The "trigger a prompt → run it in
   my CLI in the chat window" capability is already mature and Implemented — the
   dispatch engine of ADR-130 / ADR-144 / ADR-146 / ADR-160 / ADR-530, surfaced
   through `apps/dashboard/lib/prompt-adapter.ts` and `remote-dispatch.ts`. It is
   simply not wired to user prompt cards.

The user's intended workflow: encounter a useful prompt → run one command with the
URL → the prompt is extracted and saved → open Browse → Prompts → trigger the
prompt card → their default CLI opens in chat with the prompt pasted in, ready for
their own input. The capture half is missing; the trigger half exists and needs
wiring.

## Decision

Extend the existing `/ingest` command with a prompt-capture mode, give user prompts
a home in the vault, surface them in the existing Prompts tab, and wire the
existing dispatch engine to prompt cards with a placeholder-fill trigger UX. Reuse
over rebuild throughout — the genuinely new surface area is small.

### 1. Prompt-capture mode on `/ingest`

Add an `--as-prompt` branch to the `/ingest` command policy doc
(`shared-vault/skills/ingest/commands/ingest.md`). On `/ingest <url> --as-prompt`
the agent fetches the page with the **same fetcher pipeline** it already uses for
URL ingestion (per `agent-fetch-primitives.md`), but instead of routing to
`save-url-source` it extracts *just the prompt text* — agent judgment, since the
page may be an article with an embedded prompt — and persists it via a new atomic
op. Default `/ingest <url>` behavior (source card) is unchanged; `--as-prompt` is
purely additive.

### 2. User prompts live in the vault

User-saved prompts live at `get_vault_dir()/prompts/<slug>.md` — markdown with
frontmatter mirroring the existing skill-prompt shape plus capture metadata:

```yaml
id: <slug>
label: <human label>
description: <one-line summary shown on the card>
icon: <lucide icon name>
source_url: <origin URL>          # optional — set on URL capture
placeholders: [goal, constraints] # optional — derived from {{slots}} in the body
```

The body is the prompt text, optionally containing `{{placeholder}}` slots. New
path helper `get_vault_prompts_dir()` in `src/config/paths.py`. New atomic MCP op
`save-prompt` that mirrors the `save-url-source` pattern: assembles frontmatter,
extracts placeholders, dedupes by content hash, persists, and returns the path.
Vault storage means these prompts sync across machines via the vault repo
(rule 25) and stay out of the code repo (rule 4).

### 3. `list-prompts` scans the vault

Extend `list_prompts_impl` in
`src/mcp/augur_framework/tools/infrastructure/browse/skills.py` to also scan
`get_vault_prompts_dir()/*.md`, tagging each item with a `source` discriminator
(`vault` vs `skill`). Vault prompts join the **same** Browse "prompts" category and
the same file-card mechanism — no bespoke view (rule 32). The card shows a `source`
badge so user prompts are visually distinct from skill prompts.

### 4. Trigger action on prompt cards

Prompt cards in Browse gain a **Trigger** action that dispatches the prompt to the
user's default CLI in the chat window. This **reuses the existing dispatch engine**
— `prompt-adapter.ts` + `remote-dispatch.ts`, dispatch mode `chat`/`ide` per
ADR-144 / ADR-146 / ADR-530. No new dispatch path is built. The action is wired in
the prompt card and `BrowseDetailPanel`; the (placeholder-substituted) prompt body
becomes the dispatched message.

### 5. Placeholder-fill trigger UX with graceful degradation

A single model that subsumes "structured" and "simple" prompts:

- A shared placeholder utility parses `{{slot}}` tokens from the prompt body
  (results cached in frontmatter `placeholders:`) and substitutes them.
- Triggering a prompt **with** placeholders opens a small inline form (one field
  per slot) in the card / detail panel; on submit the slots are substituted and
  the completed prompt is dispatched.
- Triggering a prompt **with no** placeholders dispatches the body as-is — this is
  the simple "paste it into my CLI" behavior, for free.

## Non-Goals

- **No new dispatch engine.** Strictly reuse ADR-130 / ADR-144 / ADR-146 / ADR-160
  / ADR-530.
- **No prompt-editing UI** in this ADR — capture + trigger only. Editing a saved
  prompt means editing the vault `.md` file; an inline editor is a later ADR.
- **No prompt sharing / marketplace** — local vault only.
- **No auto-detection** of "is this page a prompt?" — the user explicitly passes
  `--as-prompt`, matching their described flow ("he types some command").
- **No change to `save-url-source` or source cards** — `--as-prompt` is an
  additional branch; the default `/ingest <url>` path is untouched.
- **No change to `/save`** — it remains an asset router.

## Consequences

### Positive

- Closes the loop the user described: encounter a prompt on the web → one command
  to save → one click to reuse with their own input filled in.
- User prompts get a real, correct home (the vault) — synced across machines,
  separate from code, consistent with rules 2 and 4.
- Reuses the mature dispatch engine and the `save-url-source` / Browse file-card
  patterns — minimal new surface, low risk.

### Negative

- `/ingest` gains a mode flag — slightly more command surface.
- A new atomic op (`save-prompt`) and a new path helper to maintain.
- The placeholder parser and mini-form are genuinely new dashboard code requiring
  unit tests and real-browser verification (rule 28).

### Neutral

- Vault prompts and skill prompts coexist in the Prompts tab, distinguished by a
  `source` badge.
- `{{placeholder}}` becomes a lightweight convention users can adopt but are never
  forced to.

## Implementation Order

**Phase 1 — Storage + atomic op (no UI):**
1. `get_vault_prompts_dir()` path helper in `src/config/paths.py`.
2. `save-prompt` atomic MCP op — persists `<vault>/prompts/<slug>.md`, assembles
   frontmatter, extracts placeholders, content-hash dedupe; register in
   `config/system/capability_exposure.yaml`.
3. Shared placeholder utility — `{{slot}}` extraction + substitution, tested.

**Phase 2 — Ingest branch:**
4. `--as-prompt` branch in `shared-vault/skills/ingest/commands/ingest.md` — agent
   fetches via the existing pipeline, extracts the prompt text, calls `save-prompt`.

**Phase 3 — Discovery:**
5. Extend `list_prompts_impl` to scan `get_vault_prompts_dir()` with a `source`
   discriminator.
6. Browse prompts transform surfaces the `source` badge on the card.

**Phase 4 — Trigger UX:**
7. Trigger action on the prompt card / `BrowseDetailPanel`, wired to the existing
   dispatch engine.
8. Placeholder mini-form component; on submit substitute + dispatch; the
   no-placeholder path dispatches directly.

**Phase 5 — Verification:**
9. Unit tests: path helper, `save-prompt` dedupe, placeholder parser; run via the
   pytest auto-loop.
10. Real-browser verification of Browse → Prompts (rule 28): a vault prompt
    appears with its `source` badge; triggering a placeholder prompt opens the
    form; triggering a placeholder-free prompt dispatches directly.

## Alternatives Considered

1. **New dedicated `/prompt` command namespace** (`/prompt save <url>`,
   `/prompt list`). Rejected: the user chose extending `/ingest`; "capture a prompt
   from a URL" is conceptually a flavor of URL capture, and `/ingest` already owns
   the fetch pipeline. A `/prompt` namespace would duplicate fetch logic for
   marginal benefit.
2. **Store user prompts in a repo-committed skill's `prompts/` directory.**
   Rejected: user-authored prompts are user data (rule 4); committing them to the
   code repo is wrong and they would not sync via the vault repo.
3. **Free-text-input-box trigger UX** (append the user's input at the end of the
   prompt). Rejected: many prompts need the input *in the middle* ("Given my goal:
   ___, produce a plan"); end-concatenation cannot express that. Placeholder-fill
   subsumes it.
4. **Plain inline-paste only, no placeholders.** Rejected as the *sole* model — too
   weak for reusable structured prompts — but preserved as the graceful-degradation
   path for placeholder-free prompts.
5. **Auto-detect whether a page is a prompt.** Rejected: unreliable; an explicit
   `--as-prompt` flag is clearer and matches the user's described workflow.

## References

- ADR-130 — Action Button Dispatch Modes
- ADR-144 — Chat Dispatch Mode
- ADR-146 — IDE Dispatch Continuity (Structured Prompts)
- ADR-160 — Oneshot Agent Bubbles (Visible CLI Execution in Chat Window)
- ADR-530 — LLM CLI Dispatch by Default
- ADR-414 — Browse Categories Expansion
- `shared-vault/skills/ingest/commands/ingest.md` — the command being extended
- `src/mcp/augur_framework/tools/infrastructure/browse/skills.py` — `list_prompts_impl`
- `apps/dashboard/lib/browse/transforms.ts` — Browse prompts transform
- `apps/dashboard/lib/prompt-adapter.ts`, `apps/dashboard/lib/remote-dispatch.ts` — dispatch engine
- CLAUDE.md rules 2 (decentralization), 4 (data separation), 25 (vault sync), 32 (Browse signals ride cards)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "/ingest gains an --as-prompt mode (additive; default behavior unchanged)"
    - "list-prompts MCP tool additionally scans <vault>/prompts/ and emits a source discriminator"
    - "new save-prompt atomic MCP op"
  patterns_deprecated: []
  files_affected:
    - src/config/paths.py
    - shared-vault/skills/ingest/commands/ingest.md
    - src/mcp/augur_framework/tools/infrastructure/browse/skills.py
    - config/system/capability_exposure.yaml
    - apps/dashboard/lib/browse/transforms.ts
    - apps/dashboard/components/shared/BrowseCard.tsx
    - apps/dashboard/components/shared/BrowseDetailPanel.tsx
```

## Implementation Prompt

Use this prompt in a fresh implementation session (`/adr implement ADR-748`):

```text
Implement ADR-748 in ~/Projects/Augur.

Read these files first:
- docs/adrs/ADR-748-url-to-prompt-capture-and-triggerable-prompt-cards.md
- AGENTS.md
- shared-vault/skills/ingest/commands/ingest.md
- src/mcp/augur_framework/tools/infrastructure/browse/skills.py
- apps/dashboard/lib/browse/transforms.ts
- apps/dashboard/lib/prompt-adapter.ts and apps/dashboard/lib/remote-dispatch.ts (dispatch engine — reuse, do not rebuild)
- docs/agent-topics/DASHBOARD.md if dashboard/MCP boundaries are unclear
- docs/agent-topics/WORKFLOWS.md if command/verification routing is unclear

Required workflow:
- Use superpowers:using-git-worktrees before implementation.
- Use superpowers:subagent-driven-development to execute phase by phase.
- Use superpowers:test-driven-development for every code-changing task.
- Use superpowers:verification-before-completion before reporting completion.
- Do not push or merge without explicit user approval.

TeamCreate:
- Objective: implement URL-to-prompt capture and triggerable prompt cards from ADR-748.
- Review cadence: one phase at a time, local review after each phase.
- Safety: reuse the existing dispatch engine and save-url-source pattern; user
  prompts live in the vault, never in a committed skill; never invoke raw
  test/build/dev-server commands — use the auto-loops and slash commands
  (rules 19, 29).

TaskCreate (follow ADR-748 Implementation Order):
- Task 1, developer, medium: get_vault_prompts_dir() helper + save-prompt atomic
  MCP op (content-hash dedupe, frontmatter assembly, placeholder extraction) +
  capability_exposure.yaml entry. Phase 1 of the ADR. PARALLEL with Task 2.
- Task 2, developer, low: shared {{slot}} placeholder parser + substitution
  utility, fully unit-tested. Phase 1. PARALLEL with Task 1.
- Task 3, developer, medium: --as-prompt branch in the /ingest command policy
  doc. Phase 2. Depends on Task 1.
- Task 4, developer, medium: extend list_prompts_impl to scan the vault prompts
  dir with a source discriminator; surface the source badge in the Browse
  transform. Phase 3. Depends on Task 1.
- Task 5, frontend developer, high: Trigger action on the prompt card /
  BrowseDetailPanel wired to the existing dispatch engine, plus the placeholder
  mini-form (graceful degradation when no placeholders). Phase 4. Depends on
  Tasks 2 and 4.
- Task 6, validator, high: unit tests via the pytest auto-loop + real-browser
  verification of Browse -> Prompts per rule 28. Phase 5. Depends on all prior.

Execution gates:
- Reuse the dispatch engine — zero new dispatch paths.
- After each phase, run the narrowest relevant auto-loop, then commit the
  verified checkpoint.
- Final verification must include /auto-test-pytest, /auto-test-dashboard,
  /auto-lint, /dev-build, and a real browser check of /browse Prompts against
  the correct checkout/port. The browser closeout must name the URL, confirm a
  vault prompt renders with its source badge, and confirm both trigger paths
  (with and without placeholders).
- ADR-748 has an Impact Manifest — scan for zero stale references before
  declaring done (rule 23).
```
