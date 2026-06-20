# Content-Aware Prompt Detection and Browser-First Ingest Fetching — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Amend the `/ingest` command policy and the agent-fetch-primitives reference so that (1) plain `/ingest <url>` inspects fetched content and *asks* before saving a prompt-shaped page as a prompt card (detect + confirm), and (2) the client's browser-automation capability becomes the default web-page fetcher with generic HTTP demoted to fallback.

**Architecture:** Policy/reference-doc change only — no code, no MCP tools, no tests. Both edits are L2-policy / L3-orchestration text that AI agents read at runtime. Detection is *agent judgment expressed as policy text*, not a classifier. Both changes amend decisions ADR-748 and `agent-fetch-primitives.md` made on the record.

**Tech Stack:** Markdown policy docs; `sync_agents` for command-surface regeneration.

**Source of truth:** `docs/adrs/ADR-750-content-aware-ingest-and-browser-first-fetch.md`. This plan stacks on the `adr-748-url-to-prompt-capture` branch (ADR-750 builds on ADR-748's `--as-prompt` branch in `ingest.md`).

**Test policy:** No executable code → no unit tests. Verification per task is a **structural read-through** (the ADR-748 plan's Task 4 used the same shape). Phase 3 adds a `sync_agents` command-surface regeneration and a 4-case behavioral walkthrough.

---

## File Structure

- `docs/references/agent-fetch-primitives.md` — decision table web-page rows flipped to browser-first; privacy-boundary operational rule added.
- `shared-vault/skills/ingest/commands/ingest.md` — URL-ingestion fetch step made browser-first; new content-aware prompt-detection step added; URL-ingestion list renumbered sequentially; Prompt-ingestion cross-reference updated; layering invariants extended.
- *(no test files — doc-only change)*

---

## Phase 1 — Browser-first fetch default (reference doc)

### Task 1: `agent-fetch-primitives.md` — browser-first decision table + privacy rule

**Files:**
- Modify: `docs/references/agent-fetch-primitives.md`

This is a reference-doc edit (no code, no test). Verification is a structural read-through.

- [ ] **Step 1: Flip the web-page rows of the decision table to browser-first**

In the `## Decision table by content type` table:
- **Row 1 "Static HTML"** — change **Preferred fetcher** from `**Generic HTTP fetcher**` to `**The client's browser-automation capability**` (vendor-neutral wording — do NOT name a specific client tool). Change the **Why** column to reflect "loads the page authenticated + JS-rendered, as the user sees it." Change the **Fallback** column to `Generic HTTP fetcher (for trivially-static content, or when no browser capability is available)`.
- **Row 2 "JS-rendered SPAs"** — already browser-first; leave **Preferred** as is, but align the **Fallback** wording with row 1's vendor-neutral phrasing if needed (keep its existing "surface to user / never write a stub" intent).
- **Rows for "API endpoints returning JSON" and "RSS / Atom feeds"** — leave **Preferred** as `Generic HTTP fetcher` (these are trivially-static, structured, and a browser adds nothing — this is the explicitly-allowed fast path from ADR-750 Decision part 2).
- **All other rows** (PDFs/EPUBs, YouTube/podcasts, authenticated content, images, local files, internal `augur://` URLs) — **unchanged**.

- [ ] **Step 2: Add a privacy-boundary operational rule**

In the `## Operational rules` numbered list, add a new rule (after the existing rule 3 about auth-walled content, or as a new final rule — pick the position that reads best):

> **Browser-first uses the user's existing session only.** Defaulting to the browser-automation capability means fetching as the user's logged-in browser would. It never acquires access the user does not already have: it does not log in, does not bypass an auth wall the session itself doesn't satisfy, and surfaces (rather than works around) any login/captcha gate. "As the user sees it" means "with the session the user already has."

- [ ] **Step 3: Verify structurally**

Read the edited file top-to-bottom. Confirm: the decision table is still coherent (every row has Preferred/Why/Fallback), the web-page rows are browser-first with HTTP as fallback, the non-web rows are untouched, the new privacy rule is present, and **no client-specific tool name was introduced in the table or operational rules** (the pre-existing `mcp__claude-in-chrome__*` references in the `## Examples` section are out of scope — leave them; do not add new ones).

- [ ] **Step 4: Commit**

```bash
git add docs/references/agent-fetch-primitives.md
git commit -m "docs(fetch): browser-first default for web pages + session privacy rule (ADR-750)"
```

---

## Phase 2 — Ingest command policy

### Task 2: `ingest.md` — browser-first fetch + content-aware prompt detection

**Files:**
- Modify: `shared-vault/skills/ingest/commands/ingest.md`

Policy-doc edit (no code, no test). Verification is a structural read-through. Depends on Task 1 (the fetch-strategy language must stay consistent with `agent-fetch-primitives.md`).

- [ ] **Step 1: Make the URL-ingestion fetch step browser-first**

In `## URL ingestion`, the current step labelled **3** ("Fetch with the matching category from your client's toolkit...") — rewrite it so the **client's browser-automation capability is the default** and the generic HTTP fetcher is the **fallback**. Keep it vendor-neutral (categories, not client tool names — per this file's own "Vendor neutrality" layering invariant). It should read approximately:

> **Fetch the page.** Default to your client's browser-automation capability — it loads the page authenticated and JS-rendered, the way the user sees it. Fall back to a generic HTTP fetcher for trivially-static content (raw text, RSS, JSON) or when no browser capability is available. Pick one path; do not invent multiple retries. Never bypass an auth wall — the browser path uses the user's existing session only.

(The `## Prompt ingestion` section's shared-fetch reference must continue to resolve — see Step 3.)

- [ ] **Step 2: Add the content-aware prompt-detection step**

In `## URL ingestion`, insert a **new step between "Decide whether the content is worth saving" and "Persist via the atomic op"**: a content-aware prompt-detection / confirm step. It should read approximately:

> **Check whether the content is a reusable prompt.** If the content reads as a reusable prompt or template a user would want to trigger later — especially if it contains `{{placeholder}}`-style fill-in slots or imperative "use this prompt to…" framing — rather than a reference article, **ask the user** before persisting:
> > "This page looks like a reusable prompt rather than a reference article. Save it as a Prompt card (triggerable) instead of a Source card?"
> - If the user confirms → route to **Prompt ingestion** step 2 (Extract just the prompt) onward; do not also write a source card.
> - If the user declines → continue to **Persist via the atomic op** below (source card, the default).
> - This is **agent judgment**, not a classifier — only ask when the page is clearly prompt-shaped; when in doubt, default to the source card without asking.
> - `/ingest <url> --as-prompt` skips this question entirely — the flag is the explicit "I already know; save it as a prompt" override.

- [ ] **Step 3: Renumber the URL-ingestion list + fix the Prompt-ingestion cross-reference**

The `## URL ingestion` list currently has a pre-existing numbering gap (`1, 3, 4, 5, 6, 7` — no item 2). Since this task restructures the section by inserting a step, **renumber the whole `## URL ingestion` list to be sequential** (1, 2, 3, …) with the new detection step in its logical position. Resulting order: Classify → Fetch → Validate the parse → Decide whether worth saving → Check whether it's a reusable prompt → Persist via the atomic op → Mode-2 note.

Then update `## Prompt ingestion` step 1 — it currently says *"run its **Classify the URL**, **Fetch**, **Validate the parse**, and **Decide** steps (items 1, 3–5 of that section)"*. The bold-label names stay valid; update the parenthetical item numbers to match the new sequential numbering (the four fetch/validate/decide stages).

- [ ] **Step 4: Extend the layering invariants**

In `## Layering invariants for this command`, add bullets recording both amendments:

```markdown
- **Browser-first fetch, user's session only.** URL ingestion defaults to the client's browser-automation capability (authenticated, JS-rendered — "as the user sees it"); the generic HTTP fetcher is the fallback. The browser path never bypasses an auth wall — it uses the session the user already has. See agent-fetch-primitives.md. (Amends ADR-748's HTTP-default fetch policy — see ADR-750.)
- **Plain `/ingest <url>` detects prompts and asks.** If a fetched page is clearly a reusable prompt, the agent asks before saving it as a Prompt card instead of a Source card — detect, then confirm. A wrong guess costs one question, never a silent wrong write. `--as-prompt` is the explicit skip-the-question override. (Overturns ADR-748 Non-Goal #4 / rejected Alternative #5 — see ADR-750.)
```

- [ ] **Step 5: Verify structurally**

Read the edited file top-to-bottom. Confirm: the `## URL ingestion` list is sequentially numbered with no gap and the detection step sits between Decide and Persist; the fetch step is browser-first with HTTP fallback; the detection step is detect-then-**confirm** (always asks, never silently reclassifies) and names `--as-prompt` as the override; `## Prompt ingestion`'s cross-reference resolves to the right steps; the two new layering invariants are present; the default `/ingest <url>` → source-card path still works when the user declines; **no client-specific tool names** appear in the body; no AI vendor/model names.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/commands/ingest.md
git commit -m "feat(ingest): browser-first fetch + content-aware prompt detection (ADR-750)"
```

---

## Phase 3 — Surface regeneration + verification

### Task 3: Regenerate the `/ingest` command surface + behavioral walkthrough

**Files:** generated command-surface output only (no source files).

- [ ] **Step 1: Regenerate the command surfaces**

The source `ingest.md` edit alone does not regenerate the client-facing `/ingest` command surface. Run:

```bash
PYTHONPATH=".:shared-vault" .venv/bin/python -m skills.ai.scripts.sync_agents sync commands all
```

(`sync agents all` does NOT regenerate command surfaces — `sync commands all` is required. If it errors on import, confirm `PYTHONPATH` includes both the project root and `shared-vault`.)

- [ ] **Step 2: Confirm the regenerated surface reflects the new policy**

Inspect the generated `/ingest` command surface (the auto-generated copy the harness loads). Confirm it now contains: the browser-first fetch step, the content-aware prompt-detection step, the renumbered URL-ingestion list, and the two new layering invariants. If the generated surface still shows the old policy, the regeneration did not pick up the source edit — investigate before proceeding.

- [ ] **Step 3: Behavioral walkthrough (the 4 ADR cases)**

Walk through each case against the regenerated policy text and confirm the policy routes correctly:
1. Plain `/ingest <prompt-url>` on a clearly prompt-shaped page → the policy directs the agent to **ask** the confirm question; on "yes" it routes to Prompt ingestion (vault prompt card).
2. Plain `/ingest <article-url>` on a reference article → the policy directs the agent **not** to ask; it produces a source card.
3. `/ingest <url> --as-prompt` → still skips straight to Prompt ingestion, no question.
4. A JS-gated / proxy-wrapped / session-needing page → the policy directs the agent to the browser-automation capability by default, so the page fetches as the user sees it (HTTP fallback only for trivially-static content).

- [ ] **Step 4: Commit the regenerated surface**

```bash
git add -A
git commit -m "chore(ingest): regenerate /ingest command surface for ADR-750"
```

(If `sync commands all` produced no tracked changes — the generated surface was already current — skip the commit and note that in the run summary.)

---

## Self-Review

**1. Spec coverage** — ADR-750 Decision parts mapped to tasks:
- Part 1 (content-aware prompt detection, detect + confirm) → Task 2 Steps 2–4. ✓ — always asks; `--as-prompt` stays as the explicit override; agent judgment, no classifier.
- Part 2 (browser-first default fetch) → Task 1 (reference doc) + Task 2 Step 1 (ingest policy). ✓ — browser-first default, HTTP fallback, trivially-static fast path preserved, privacy boundary explicit.

**2. ADR amendment legibility** — Task 1 and Task 2 Step 4 both record, in-doc, that these changes amend ADR-748 / `agent-fetch-primitives.md` and point at ADR-750, so a future reader sees the amendment trail rather than thinking it's drift (ADR-750 Consequences "Neutral" bullet).

**3. Vendor neutrality** — every fetch-capability reference is a category ("the client's browser-automation capability"), never a client tool name. Task 1 Step 3 and Task 2 Step 5 both explicitly verify this. The pre-existing client-specific names in `agent-fetch-primitives.md`'s `## Examples` section are pre-existing debt, explicitly out of scope (noted in Task 1 Step 3).

**4. No scope creep** — exactly 2 source files touched (`agent-fetch-primitives.md`, `ingest.md`) + the regenerated command surface. ADR-748's atomic ops (`save-prompt`, `save-url-source`) and the `<vault>/prompts/` layout are untouched. No code, no MCP tools, no tests — matches ADR-750's Impact Manifest `files_affected`.

**5. Privacy** — both docs state the browser-first path uses the user's existing session only and never bypasses auth walls — consistent with the client user-privacy rules and `agent-fetch-primitives.md`'s existing operational rule 3.

**Known follow-up (out of scope):** `agent-fetch-primitives.md`'s `## Examples` section names `mcp__claude-in-chrome__*` tools — a pre-existing vendor-neutrality violation in that doc, not introduced or fixed here. Worth a separate cleanup pass.
