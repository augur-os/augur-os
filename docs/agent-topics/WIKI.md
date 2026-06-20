# Wiki & Knowledge Compounding

Load this when handling durable knowledge work, session-end compounding, URL ingest, or `/ask` retention.

See also [architecture-wiki.md](../architecture-wiki.md) for the contributor-facing wiki compounding architecture.

## Wiki Compounding

- Shared long-term knowledge lives in `get_wiki_dir()` (`Au-vault/wiki/`).
- Before broad knowledge work, prefer reading `wiki/overview.md` and `wiki/index.md` when they exist.
- `wiki-reindex` only refreshes browse/search indexing for existing wiki pages; it does not rebuild wiki content.
- `wiki-rebuild` prepares a concept-first extraction batch from current Augur knowledge sources when the shared wiki needs a usable base.
- `wiki-update` prepares an incremental concept-first extraction batch for changed sources and retained `/ask` outcomes.
- `wiki-apply-concept-batch` applies agent-produced concept JSON to compiler state and concept/query wiki pages.
- Concept pages use the ADR-740 body split: `## Compiled truth` is human-owned and changed only by an explicit rewrite-proposal apply step; `## Timeline` is machine-owned and append-only with `_at:` and `_source:` on every entry.
- `wiki-update` and `wiki-apply-concept-batch` may create a new concept page with initial compiled truth, but for an existing v4 concept page they preserve compiled truth and append cited observations to the timeline.
- Wiki pages should be compound idea articles, not source pages: target roughly 10-15 sources per durable concept page; fewer than 3 sources is thin/pending unless the source is unusually authoritative and high confidence.
- Prefer strengthening or merging existing concept pages over creating new pages. Use `post_apply_status.compounding_health` to inspect average sources per page, thin pages, orphan pages, and duplicate concept clusters.
- When a conversation produces a durable synthesis, call `save-synthesis`; it stores reusable source material for later wiki maintenance, but does not mutate wiki pages directly.
- During knowledge-heavy user interactions, prefer compiled wiki context first: read `wiki/overview.md`, `wiki/index.md`, `wiki-status`, or targeted wiki pages/search before falling back to raw sources when the wiki is likely relevant.
- At session end, if durable learning, research, retained `/ask` outcomes, or content ingestion happened, check `wiki-status`. If it recommends `wiki-update` and there is enough context/time, run a bounded agent-orchestrated `wiki-update` -> extraction -> `wiki-apply-concept-batch` -> `wiki-reindex`/`wiki-lint` -> `wiki-log` cycle.
- If immediate compilation is not safe or feasible, leave the runtime `wiki/needs-update.flag` in place for the next agent or nightly loop. Clients with lifecycle hooks must run `node scripts/hooks/run-hook.mjs session-wiki-flag` as a SessionEnd safety net.
- Retained `/ask` outcomes after retention routing are part of session-end compounding and should be considered wiki inputs.
- second-brain interactions may strengthen the wiki later, and `/ask` is the strongest second-brain compounding surface.

## URL Ingest and Agent-Orchestrated Wiki Execution

- Use `/ingest <url>` for durable URL capture instead of ad hoc notes. The agent picks the right fetcher per `docs/references/agent-fetch-primitives.md`, then writes via the `save-url-source` atomic op.
- URL captures are saved as vault source cards, normally under `sources/web/`, with YAML frontmatter and Obsidian-native callouts.
- Preserve source-card metadata when summarizing, tagging, or compiling captures.
- Deterministic routing must use current Augur hubs and skill metadata; agent judgment may refine summaries and actions, but should not erase routing evidence.
- Wiki synthesis is agent-orchestrated by default: tools prepare batches/prompts and apply agent-produced results through the active native AI client.
- Do not hand-write compiled wiki pages under `wiki/concepts/` or `wiki/queries/`; use `wiki-update` and `wiki-apply-concept-batch`.
- Use Obsidian-native markdown conventions for user-facing vault and wiki files: frontmatter, wikilinks where helpful, callouts for summary/routing/action review, and checkbox actions for follow-up work.
