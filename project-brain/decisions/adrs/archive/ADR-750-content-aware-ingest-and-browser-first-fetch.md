---
status: Implemented
date: 2026-05-14
deciders:
  - gsannikov
related:
  - ADR-748
hub: brain
tags:
  - ingest
  - prompts
  - fetch
  - browser
  - vendor-neutral
superseded_by: null
spec_file: null
plan_file: 2026-05-14-content-aware-ingest-and-browser-first-fetch.md
---

# ADR-750: Content-Aware Prompt Detection and Browser-First Ingest Fetching

## Status

Implemented (2026-05-15). Both Decision parts shipped as policy/reference-doc
edits across 3 tasks (subagent-driven, spec + doc-quality review per task, plus
a final whole-implementation review), stacked on the `adr-748-url-to-prompt-capture`
branch since ADR-750 builds on ADR-748's `--as-prompt` branch in `ingest.md`:

- **Browser-first fetch** — `docs/references/agent-fetch-primitives.md`'s
  decision table now makes the client's browser-automation capability the
  default web-page fetcher (HTTP demoted to fallback for trivially-static
  content), with an explicit session-only privacy rule; `ingest.md`'s
  URL-ingestion fetch step and Classify bullets match.
- **Content-aware prompt detection** — `ingest.md` gained a detect-then-confirm
  step in URL ingestion: a clearly prompt-shaped page (placeholder slots,
  system/role framing, unwrapped imperative prompt text) triggers a yes/no
  question before being saved as a prompt card; `--as-prompt` remains the
  explicit skip-the-question override.

Verification (doc-only ADR — no code, no tests): each task structurally
reviewed twice with fix loops closed; `sync_agents sync commands all`
regenerated the `/ingest` command surface and it was confirmed to carry the
new policy; the 4-case behavioral walkthrough (prompt page asks → prompt card;
article does not ask → source card; `--as-prompt` skips the question;
JS-gated page fetches via the browser path) routes correctly; the Impact
Manifest's two `files_affected` docs were the only source files touched.

## Context

ADR-748 shipped URL-to-prompt capture: `/ingest <url> --as-prompt` fetches a
page, extracts the reusable prompt text, and saves it to `<vault>/prompts/`.
Two deliberate constraints in ADR-748 have turned out to be friction points in
real use:

1. **The `--as-prompt` flag is mandatory.** ADR-748 listed "no auto-detection
   of 'is this page a prompt?'" as a **Non-Goal**, and rejected auto-detection
   as Alternative 5, "Auto-detect whether a page is a prompt" (*"unreliable;
   an explicit flag is clearer"*). In practice,
   a user who pastes a prompt URL into `/ingest` and forgets the flag silently
   gets a **source card** instead of a prompt — the wrong artifact type, in the
   wrong Browse tab, with no signal that anything went sideways. The reliability
   objection was sound for *silent auto-classification*, but it does not apply
   to a **detect-then-confirm** model: a wrong guess costs exactly one yes/no
   question, never a bad silent write.

2. **The default fetcher is a plain HTTP GET.** `docs/references/agent-fetch-primitives.md`
   makes the generic HTTP fetcher the preferred fetcher for "static HTML" and
   escalates to a browser only for known SPA hosts. But many prompt sources —
   gists behind rendering proxies, JS-gated pages, anything that looks static
   but needs a session — return a shell or a login wall to a bare GET. The user
   wants `/ingest` to fetch pages **the way they see them in their own browser**:
   authenticated, JS-rendered, real DOM.

Both changes amend decisions ADR-748 (and `agent-fetch-primitives.md`) made on
the record, so they go through this ADR rather than a quiet edit (CLAUDE.md
rule 12). ADR-748's core feature — capture, vault home, triggerable cards — is
unchanged and stays Implemented; ADR-750 **extends** it.

## Decision

### 1. Content-aware prompt detection on plain `/ingest <url>` (detect + confirm)

Extend the `/ingest` command policy doc so that on a plain `/ingest <url>` (no
`--as-prompt`), after the page is fetched and validated, the agent **inspects
the content**. If the content is prompt-shaped — it reads as a reusable
instruction/template a user would want to trigger later, especially if it
contains `{{placeholder}}`-style slots or imperative "use this prompt to…"
framing — the agent **asks the user** before persisting:

> "This page looks like a reusable prompt rather than a reference article.
> Save it as a Prompt card (triggerable) instead of a Source card?"

- **User confirms** → route to Prompt ingestion (the ADR-748 `save-prompt`
  path).
- **User declines** → save as a Source card (the existing default).
- **`--as-prompt` is still honored as the explicit override** — passing the
  flag skips the question entirely and goes straight to Prompt ingestion. The
  flag becomes "I already know; don't ask," not the only door.
- The detection is **agent judgment**, not a classifier or heuristic engine —
  no new code, no new MCP tool. It is L2 policy text in `ingest.md` instructing
  the agent when to ask. The confirm step is what makes ADR-748's "unreliable"
  objection moot.

This overturns ADR-748's "No auto-detection" Non-Goal and its rejected
"Auto-detect whether a page is a prompt" alternative — explicitly,
because the *detect-then-confirm* shape is materially different from the
*silent auto-detect* that ADR-748 rejected.

### 2. Browser-first default fetching

Invert the fetch-strategy default in `agent-fetch-primitives.md` and the
`/ingest` URL-ingestion policy:

- The **client's browser-automation capability** becomes the **default
  fetcher** for web URLs — it loads the page as the user's real, authenticated,
  JS-rendering browser would, so `/ingest` captures what the user actually sees.
- The **generic HTTP fetcher** is demoted to a **fallback** — used when no
  browser-automation capability is available to the active client, or as a
  fast path the agent may still choose for known-trivially-static content
  (RSS, JSON APIs, raw text files) where a browser adds nothing.
- Content-type routing is unchanged for the non-HTML rows of the decision
  table: PDFs/EPUBs still go to the extraction MCP, YouTube/podcasts to their
  summarizers, `augur://` URLs to MCP resource reads. Only the **web-page**
  default flips.
- **Vendor neutrality is preserved** (CLAUDE.md, and `ingest.md`'s own layering
  invariant): the doc says "the client's browser-automation capability," never
  a specific client tool name. Each AI client (Claude Code, Codex, Gemini,
  OpenCode) maps that category to whatever browser capability it has; a client
  with none falls back to HTTP.
- **Privacy boundary (explicit):** browser-first means `/ingest` drives the
  user's logged-in session by default. The agent must still honor the
  user-privacy rules — it never bypasses an auth wall the session itself
  doesn't already satisfy, never captures content the user isn't logged into,
  and surfaces (rather than works around) any login/captcha gate. "As the user
  does" means "with the session the user already has," not "acquire access."

## Non-Goals

- **No prompt classifier model or scoring engine.** Detection is agent
  judgment expressed as policy text — consistent with ADR-748's "no
  auto-detection *engine*" spirit; only the *mandatory-flag* constraint is
  lifted.
- **No change to `save-prompt`, `save-url-source`, or the vault layout.**
  ADR-748's atomic ops and `<vault>/prompts/` home are untouched.
- **No silent reclassification.** A plain `/ingest` never writes a prompt card
  without an explicit user "yes" (or the explicit `--as-prompt` flag).
- **No auth-wall bypassing.** Browser-first uses the user's existing session
  only; it never acquires access the user doesn't already have.
- **No new client-specific tooling.** Both changes are policy-doc edits plus
  reference-doc edits — they ride the existing agent-fetch-primitives menu and
  the existing `/ingest` dispatch.

## Consequences

### Positive

- A user who forgets `--as-prompt` is caught by a one-question prompt instead
  of silently getting the wrong artifact — closes the most likely real-world
  failure mode of ADR-748.
- `/ingest` captures pages as the user actually sees them — far fewer "fetched
  the SPA shell" / "got a login wall" failures, and prompt sources behind
  rendering proxies or JS gates become reachable.
- Both changes are policy/reference-doc edits — no new code, no new MCP tools,
  low implementation risk; the heavy lifting is agent judgment, which is where
  Augur's architecture already puts it (L2/L3).

### Negative

- `/ingest` on a genuinely ambiguous page now sometimes asks a question that
  the user finds obvious — a small friction cost, mitigated by `--as-prompt`
  (skip the question) and by keeping the detection bar high (only ask when the
  page is clearly prompt-shaped).
- Browser-first fetching is heavier than an HTTP GET and drives the user's
  session on every web ingest — slower, and a larger privacy surface that the
  policy doc must bound explicitly.
- Two reference surfaces (`ingest.md`, `agent-fetch-primitives.md`) now have a
  decision that diverges from ADR-748's original text — the ADR trail must make
  the amendment legible so a future reader doesn't think it's drift.

### Neutral

- `--as-prompt` keeps working exactly as ADR-748 specified — it just changes
  meaning from "the only way" to "the explicit, skip-the-question way."
- The agent-fetch-primitives decision table keeps all its non-HTML rows; only
  the web-page default and its fallback column change.

## Implementation Order

**Phase 1 — Fetch default (reference doc):**
1. `docs/references/agent-fetch-primitives.md` — flip the web-page rows of the
   decision table to browser-first / HTTP-fallback; add an explicit
   privacy-boundary note; keep vendor-neutral category language.

**Phase 2 — Ingest command policy:**
2. `shared-vault/skills/ingest/commands/ingest.md` — (a) in URL ingestion,
   make the browser-automation capability the default fetch step with HTTP as
   fallback; (b) add a "content-aware prompt detection" step after fetch/
   validate that inspects the content and asks the user before routing to
   Prompt ingestion; (c) update the layering invariants to record both
   amendments and the privacy boundary.

**Phase 3 — Surface regeneration + verification:**
3. Run `sync_agents sync commands all` so the generated `/ingest` command
   surface reflects the new policy (the doc-source edit alone does not
   regenerate the client-facing command surface).
4. Verify: a plain `/ingest <prompt-url>` asks the confirm question and, on
   yes, produces a vault prompt card; `/ingest <article-url>` does not ask and
   produces a source card; `--as-prompt` still skips straight to prompt
   capture; a JS-gated page that a bare GET would miss now fetches via the
   browser path.

## Alternatives Considered

1. **Keep `--as-prompt` mandatory (ADR-748 status quo).** Rejected: the
   silent-wrong-artifact failure mode is real and confusing; the confirm step
   removes the reliability objection that justified the original constraint.
2. **Silent auto-classification (ADR-748's rejected "Auto-detect whether a page
   is a prompt" alternative, re-examined).**
   Still rejected as the *sole* model — a misclassification writing the wrong
   artifact with no user check is exactly what ADR-748 warned about. Detect +
   confirm keeps the upside (catches the forgotten flag) without the downside.
3. **Save as both a source card and a prompt card on a prompt-shaped page.**
   Rejected: produces near-duplicate artifacts in two Browse tabs for every
   prompt page, pushing dedupe and clutter onto the user. The confirm step
   lets the user pick the one correct artifact.
4. **Browser-first only for known SPA/auth hosts (escalation model).**
   Rejected as the default: a host that looks static but needs a session
   (rendering proxies, JS-gated gists) still fails. Browser-first-with-HTTP-
   fallback catches those while still allowing the agent a fast HTTP path for
   trivially-static content.
5. **A dedicated prompt-classifier MCP tool.** Rejected: over-engineering —
   detection is judgment, judgment is the agent's job (L3), and a classifier
   tool would be a workflow-shaped god-tool the architecture explicitly avoids.

## References

- ADR-748 — URL-to-Prompt Capture and Triggerable Prompt Cards (the ADR this
  one extends; this overturns its "No auto-detection" Non-Goal and rejected
  "Auto-detect whether a page is a prompt" alternative)
- `shared-vault/skills/ingest/commands/ingest.md` — the command policy doc edited
- `docs/references/agent-fetch-primitives.md` — the vendor-neutral fetch menu edited
- `docs/references/surface-decision-matrix.md` — L2 policy / L3 orchestration layering
- CLAUDE.md rules 12 (ADR canonical), 19 (agent-orchestrated execution), and the
  user-privacy section (browser-session boundary)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "/ingest <url> (no flag) now inspects content and may ask to save as a prompt (detect + confirm); default-on-decline behavior unchanged"
    - "agent-fetch-primitives.md: web-page default fetcher flips from generic HTTP to the client's browser-automation capability; HTTP demoted to fallback"
  patterns_deprecated:
    - "ADR-748's 'No auto-detection' Non-Goal and rejected 'Auto-detect whether a page is a prompt' alternative — superseded by the detect-then-confirm model in this ADR"
  files_affected:
    - docs/references/agent-fetch-primitives.md
    - shared-vault/skills/ingest/commands/ingest.md
```

## Implementation Prompt

Use this prompt in a fresh implementation session (`/adr implement ADR-750`):

```text
Implement ADR-750 in ~/Projects/Augur.

Read these files first:
- docs/adrs/ADR-750-content-aware-ingest-and-browser-first-fetch.md
- docs/adrs/ADR-748-url-to-prompt-capture-and-triggerable-prompt-cards.md (the ADR this extends)
- shared-vault/skills/ingest/commands/ingest.md (the command policy doc — already has the --as-prompt branch from ADR-748)
- docs/references/agent-fetch-primitives.md (the vendor-neutral fetch menu)
- docs/agent-topics/WORKFLOWS.md if command/surface-regeneration routing is unclear

Required workflow:
- Use superpowers:using-git-worktrees before implementation.
- Use superpowers:subagent-driven-development to execute phase by phase.
- Use superpowers:verification-before-completion before reporting completion.
- This is a policy/reference-doc change — no new code, no new tests expected;
  verification is a structural read-through plus a sync_agents command-surface
  regeneration and a behavioral walkthrough.
- Do not push or merge without explicit user approval.

Execution (follow ADR-750 Implementation Order):
- Phase 1: flip the web-page rows of the agent-fetch-primitives.md decision
  table to browser-first / HTTP-fallback; add the explicit privacy-boundary
  note; keep vendor-neutral category language (no client-specific tool names).
- Phase 2: in shared-vault/skills/ingest/commands/ingest.md — make the
  browser-automation capability the default fetch step (HTTP as fallback); add
  a content-aware "prompt detection → ask the user" step after fetch/validate
  in plain URL ingestion; record both amendments + the privacy boundary in the
  Layering invariants section. Keep --as-prompt as the explicit skip-the-
  question override.
- Phase 3: run `sync_agents sync commands all` so the generated /ingest command
  surface reflects the new policy. Then walk through the four verification
  cases in the ADR's Implementation Order step 4.

Execution gates:
- Vendor neutrality: zero client-specific tool names in either doc body.
- The detect step is agent judgment expressed as policy text — do NOT add a
  classifier, scoring heuristic, or new MCP tool.
- Browser-first must NOT bypass auth walls — it uses the user's existing
  session only; surface login/captcha gates rather than working around them.
- ADR-750 has an Impact Manifest — confirm the two amended docs are the only
  files_affected and that ADR-748's atomic ops / vault layout are untouched.
```
