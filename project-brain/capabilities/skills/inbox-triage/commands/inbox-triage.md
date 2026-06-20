---
description: Daily vault-inbox auto-triage routine — files capture cards into vault domains.
visibility: user
protocol: routine
---

# inbox-triage routine

A daily pass that empties the vault inbox by filing each capture card into the
right vault domain. Run inside your own session; Augur owns no scheduling and
makes no LLM call.

## Phase 1 — List (deterministic)

Call `inbox-triage-list`. If `count` is 0, skip to Phase 4 and write a
"0 cards" report.

## Phase 2 — Classify (your judgment, inline)

For each card, read `title` + `excerpt` and choose ONE destination using this
precedence:

1. An **existing** top-level vault domain that clearly fits.
2. An **existing** subdomain (`career/interview/`) when a more specific home fits.
3. A **new** domain or subdomain — only for a coherent recurring theme not
   covered by any existing domain. Prefer reusing a close-match existing domain
   over minting a near-duplicate.
4. `general/` — the drain for genuine one-offs that fit no domain.

Inspect the current domains first (the vault root folders) so you reuse real
ones rather than inventing duplicates.

## Phase 3 — File (deterministic, auto)

For each classified card, call `inbox-triage-file` with `card_path`, `target`
(the chosen domain or `domain/subdomain`), and a one-line `reason`. This is
auto-file: no confirmation gate. Collect each tool result.

## Phase 4 — Report + graph refresh

Call `inbox-triage-report` with the JSON array of filed entries (each:
`title`, `filed_to`, `reason`, `created_folder`). Then run one graph rebuild
for the whole vault so moved-card edges are correct: `aug graph rebuild`
(or the `graph` skill's rebuild tool). Report the daily report path and the
count filed.
