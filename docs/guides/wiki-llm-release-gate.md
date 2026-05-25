---
title: Wiki LLM Release Gate
description: Production-readiness checks for the concept-first wiki and user-facing LLM wiki surfaces.
---

# Wiki LLM Release Gate

Use this before calling the wiki LLM surface ready for open-source release. The gate covers the compiler, retained chat/file inputs, dashboard surfaces, and browser smoke checks.

## User-Exposed Surface Ranking

| Rank | Surface | User value | Release risk to verify |
|------|---------|------------|------------------------|
| 1 | `/brain/inbox` | Turns messy Desktop/Downloads-style folders into routed, renamed, indexed knowledge inputs. | Scan, Consume, and Purge to Trash must use MCP tools, preserve valuable files, report skipped files, and leave wiki/RAG update signals. |
| 2 | `/brain/insights` | Gives the next useful action after ingestion or retained `/ask` outcomes. | Wiki freshness, retained ask clusters, inbox run history, errors, and `Prepare wiki update` must be live data, not placeholder copy. |
| 3 | `/browse?category=wiki` | Lets users inspect compiled wiki pages and take the most likely action quickly. | Wiki cards need useful tags, a primary `Read Wiki` action, and secondary actions in the overflow menu without the first-run banner blocking the page. |
| 4 | `/brain` | Gives first-run users an obvious route into Brain workflows. | Brain Inbox and Brain Insights must be visible first-level actions with no duplicate page headings or nested-tab confusion. |
| 5 | `/ask` and chat retention hooks | Converts durable chat outcomes into future wiki inputs. | Retained outcomes should set wiki update signals and be visible through Brain Insights without turning chat into a noisy logging UI. |
| 6 | Wiki MCP commands | Gives agents a deterministic maintenance path. | `wiki-status`, `wiki-update`, `wiki-apply-concept-batch`, `wiki-reindex`, `wiki-lint`, and `wiki-log` must remain callable and honest about pending work. |

## Manual User Journey

1. Start the dashboard and open `/brain`.
2. Confirm Brain Inbox and Brain Insights are top-level cards.
3. Open `/brain/inbox`, add Desktop or Downloads, and run Scan.
4. Inspect the counts for new files, document candidates, trash candidates, and failures.
5. Run Consume on a folder with safe test files. Confirm the run reports moved, routed, skipped, and failed files.
6. Run Purge to Trash only after Scan identifies disposable candidates. Confirm valuable documents are skipped.
7. Open `/brain/insights`. Confirm the latest inbox run, wiki status, ask-retention signals, and next actions reflect the run.
8. Open `/browse?category=wiki`. Confirm compiled wiki cards have useful tags, a primary action, and overflow actions.
9. Resize to mobile width and repeat the main actions without horizontal overflow or clipped button text.

## Handoff Workflow

1. Call `wiki-status`.
2. If `actions` includes `wiki-update`, call `wiki-update` with the provided `inputs.limit`.
3. If `wiki-update` returns `status: current` and `batch.count: 0`, run `wiki-status` again. A stale `needs-update.flag` should be cleared by the no-op update.
4. If `batch.count > 0`, read `batch.batch_file`. Use each item prompt and `source_cluster` to extract durable concept JSON keyed by `source_id`.
5. Include retained `/ask` outcomes when they are durable by calling `ask-sync-data` and `ask-sync-clusters`, then merging relevant cluster evidence into the same concept payload discipline.
6. Call `wiki-apply-concept-batch` with `payloads_json`. Do not hand-write files under `wiki/concepts/` or `wiki/queries/`.
7. Inspect `post_apply_status.compiler.sources_pending_or_changed`, `post_apply_status.compounding_health`, and `post_apply_status.actions`.
8. Repeat bounded `wiki-update` -> extract -> `wiki-apply-concept-batch` cycles until `sources_pending_or_changed` is `0` and no update action remains.
9. Run `wiki-reindex`, `wiki-lint`, `wiki-status`, and `wiki-log` with the pages/concepts written and any deferred sources.

## Ready Criteria

- `wiki-status.healthy` is `true`.
- `wiki-status.actions` is empty.
- `wiki-lint` returns success with no missing links, orphan pages, legacy pages, or schema violations.
- Concept compounding remains healthy: no thin pages, no orphan concept pages, and average sources per concept page stays within the target band.
- Dashboard surfaces load and expose useful actions:
  - `/brain/insights` shows wiki status, retained ask outcomes, ask clusters, and a working `Prepare wiki update` action when needed.
  - `/brain/inbox` supports adding watched folders and running scan, consume, and purge actions through MCP.
  - `/browse?category=wiki` shows wiki pages with a primary `Read Wiki` action and secondary actions in the overflow menu.
- Binary and document intake is deep enough for release claims: supported PDFs, Office files, images/OCR candidates, audio/video transcript candidates, and unsupported binaries must be classified honestly, routed through the document extractor when supported, and surfaced as skipped/failed instead of silently dropped.
- Chat and file interactions compound through hooks or retained state: retained `/ask` outcomes and consumed files should both leave visible wiki/RAG update signals.
- Browser smoke passes on desktop and mobile with no horizontal overflow.

## Verification Commands

```bash
pnpm --filter dashboard lint
pnpm --filter dashboard typecheck
pnpm --filter dashboard build
pytest skills/ingest/augur/tests/test_inbox_consume.py skills/ingest/augur/tests/test_inbox_mcp_tools.py skills/ingest/augur/tests/test_inbox_store.py skills/ingest/augur/tests/test_inbox_trash.py -q
pytest skills/ingest/augur/tests/test_wiki_tools.py skills/ingest/augur/tests/test_wiki_concept_pages.py skills/ingest/augur/tests/test_wiki_concept_compiler.py -q
pytest tests/unit/test_path_resolution.py tests/unit/test_path_discovery.py -q
cd apps/dashboard && ./node_modules/.bin/playwright test wiki-llm-surface.spec.ts --reporter=line
```

The Playwright smoke suite stubs MCP responses and validates user-visible behavior. A final live browser pass should still be run against the local dashboard when the release candidate includes visual changes.
