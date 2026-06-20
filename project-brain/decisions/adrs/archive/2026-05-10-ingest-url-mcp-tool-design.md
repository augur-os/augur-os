---
title: Ingest URL MCP Tool — Design
type: spec
status: draft
created: 2026-05-10
authors:
  - gsannikov
related:
  - shared-vault/skills/ingest/scripts/source_cards.py
  - shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
  - shared-vault/skills/ingest/scripts/wiki_scanner.py
  - shared-vault/skills/knowledge/scripts/mcp/tools_summarize.py
  - src/config/paths.py
  - docs/adrs/archive/ADR-624-obsidian-native-ingest-url-wiki-mvp.md
governance:
  next_step: ADR-724 (Accepted, ready for implementation)
  supersedes: ADR-624 (Cancelled)
tags:
  - ingest
  - mcp
  - wiki
  - url-capture
---

# Ingest URL MCP Tool — Design

A single MCP mutation, `ingest-url`, registered on the existing `ingest` skill that captures one URL into the source-card pipeline so the wiki compounder picks it up on its next scan. The tool fetches, extracts, canonicalizes, hashes, and persists — synchronously, idempotently, and without touching any other skill.

This ADR is the surviving track of the cancelled ADR-624. ADR-624's Track A (creating an `obsidian` skill with 7 vault-* MCP tools) was redundant with the existing `vault` skill at `~/Projects/Au-vault/skills/vault/` that already registers those tools. Track B — the focused `ingest-url` mutation — was the only genuine value-add. It is now ADR-724.

## Problem

Users need a way to capture a URL into the second brain so the wiki compounder pulls signal out of it. Today the workflow is manual:

1. Copy the URL.
2. Open a markdown editor.
3. Paste the URL into a file under `<vault>/sources/urls/...`.
4. Add frontmatter by hand (title, tags, hash).
5. Save and pray the wiki scanner accepts the shape.

This breaks down in three ways:

- **Friction** — every step is a chance to abandon the capture.
- **Frontmatter drift** — hand-written cards diverge from the shape `wiki_scanner.py` expects (`source_type`, `content_hash`, `captured_at`).
- **Duplication** — re-capturing the same URL yields a second card, and the wiki extractor double-counts the source.

The agent surface (Claude / Codex / Gemini) lacks any "save this URL into the brain" tool. `knowledge-summarize-url` returns a summary string but does **not** persist anything to the vault — it conflates summarization with capture.

## Decision

Register a new MCP tool `ingest-url(url, tags=None, note=None) -> json` on the existing `ingest` skill at `shared-vault/skills/ingest/`. The tool performs five steps synchronously inside the MCP call:

1. **Fetch** with `httpx.Client(follow_redirects=True, timeout=20)`. Send a real `User-Agent` so most sites return prose; reject non-HTML content types with a clear error.
2. **Extract** with `trafilatura` (primary) and BeautifulSoup (fallback). Pull title and prose body; reject empty extractions with a clear error.
3. **Canonicalize** the URL: drop scheme casing, lowercase host, strip `utm_*` / `fbclid` / `gclid` / `mc_cid` / `mc_eid` / `igshid` / `ref` / `ref_src` query keys, strip hash fragments, strip trailing slashes (except on root path), sort remaining query keys.
4. **Hash** with `sha256(canonical_url + "\n" + body)` for idempotency. If a card with that hash already exists under `<vault>/sources/urls/`, return `{"success": true, "deduplicated": true, "path": <existing>, "sha256": ...}` and skip the write.
5. **Persist** a markdown source card at `<vault>/sources/urls/<YYYY-MM-DD>-<slug>.md` using frontmatter shape `{title, source_type: "url", canonical_url, tags, content_hash, captured_at, note?}`. Filename slug is derived from the URL path and is collision-safe (the existing `_unique_card_path` helper handles `-2`, `-3` suffixes).

The wiki scanner already walks `<vault>/sources/` recursively under `source_surface="vault"` and accepts markdown sources, so no scanner change is required. The compounder runs on its existing cadence and the new card flows through unchanged.

## Architecture

Single-file flow, five pure stages, one persistence call:

```
ingest-url(url, tags?, note?)
        │
        ▼
┌──────────────────┐
│  fetch_and_      │   httpx.get(url, follow_redirects=True, timeout=20)
│  extract(url)    │   → trafilatura.extract → fallback BeautifulSoup
└────────┬─────────┘   → {title, body}
         │
         ▼
┌──────────────────┐
│ canonicalize_url │   strip utm_*/fbclid/gclid/hash/trailing-slash, sort query
└────────┬─────────┘   → "https://example.com/a/b?id=1"
         │
         ▼
┌──────────────────┐
│ compute_content_ │   sha256(canonical_url + "\n" + body)
│ hash             │   → "sha256:abc123…"
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ dedup check      │   scan <vault>/sources/urls/*.md frontmatter
│ (idempotency)    │   if content_hash matches → return early
└────────┬─────────┘
         │   (no match)
         ▼
┌──────────────────┐
│ write_url_       │   slug = slugify_url(canonical_url)
│ source_card      │   path = <vault>/sources/urls/<YYYY-MM-DD>-<slug>.md
└────────┬─────────┘   → write_vault_frontmatter(path, meta, body)
         │
         ▼
   {success, path, sha256, deduplicated}
```

The five helper functions live in a new module `shared-vault/skills/ingest/scripts/url_ingest.py`. The MCP registration lives in a new module `shared-vault/skills/ingest/scripts/mcp/url_tools.py`, wired into `shared-vault/skills/ingest/scripts/mcp/__init__.py` next to `register_inbox_tools` and `register_wiki_tools`.

## Alternatives Considered

### Alt 1: Use `inbox-consume-folder` with a URL-placeholder file

**Idea:** drop a `.url` shortcut file in an inbox folder; let `inbox-scan-folder` discover it and `inbox-consume-folder` route it.

**Rejected because:**

- The inbox pipeline is **asynchronous + heuristic-routed** — files land, the router decides a `RouteDecision`, OCR/audio extractors fan out. URLs don't need any of that machinery and the routing decision is trivial ("it's a URL").
- The inbox shape writes to `<vault>/sources/files/` and embeds a `RouteDecision` in frontmatter. URLs need a distinct directory (`sources/urls/`) and a simpler frontmatter.
- Synchronous in-call response matters: agents want to know "did the capture stick?" within the same MCP turn so they can cite the resulting wikilink. The inbox flow can't promise that.

### Alt 2: Extend `knowledge-summarize-url` to also write a card

**Idea:** keep the single existing URL tool; add a `persist=True` flag.

**Rejected because:**

- **Conflates summary with persistence.** Summary is a transient string; persistence is a durable vault write. The tools have different costs, different failure modes, and different audit trails.
- `knowledge-summarize-url` shells out to a third-party CLI (`summarize`). The capture path must not depend on an external binary — `httpx + trafilatura` is in-process Python.
- `knowledge` is the wrong skill for source-card mutations. Source cards are an `ingest` concern: the wiki compounder lives there, the scanner lives there, the existing `write_source_card` helper lives there.

### Alt 3: Make `ingest-url` async / background-queue

**Idea:** enqueue the fetch into the daemon, return immediately, let a worker write the card.

**Rejected because:**

- Fetches that complete in <20s synchronously are simpler than any queue. The 99th-percentile page parses fast enough.
- Async breaks the idempotency contract — two concurrent calls with the same URL would race; the synchronous version dedupes before any IO commits.
- Background workers add ops surface (queue health, retry budget, dead-letter) that this ADR does not need.

## Consequences

### Positive

- **One MCP call captures one URL** — agents, CLI users, and dashboard widgets share a single contract.
- **Idempotent by construction** — re-running is free; bulk imports can naïvely retry on partial failure.
- **No new persistence layer** — reuses `write_vault_frontmatter`, the existing `<vault>/sources/` tree, and the existing scanner.
- **No new dashboard surface required** — the existing `/brain/vault` browse pages already render the new cards.
- **Forward-compatible with archive snapshots** — `content_hash` is the natural primary key for future "did this URL change since I last saw it?" probes.

### Negative / costs

- **New dependencies:** `trafilatura` and `beautifulsoup4` join `pyproject.toml`. Both are pure-Python with no native compilation, so install impact is small.
- **No rate-limiting** — out of scope. A polite caller is the contract.
- **No robots.txt respect** — out of scope. The user is asking us to fetch a specific URL on their behalf; treat it as a manual browser request.
- **Trafilatura quality is content-dependent** — some sites (JS-rendered, heavy SPA) yield empty extractions. The fallback to BeautifulSoup catches some of these; the rest return a clear error rather than persisting an empty card.

### Risks and mitigations

| Risk | Mitigation |
|---|---|
| Fetch hangs indefinitely | `httpx` timeout of 20s; raises a clean error on exceed |
| Non-HTML URL (PDF, image) | Reject early via `Content-Type` check; user can pipe to the document-extractor skill |
| Site blocks default User-Agent | Send a real-browser UA string; document workaround in `--help` |
| Body extracts as empty | Return error before writing card; never persist empty content |
| Filename collision on same-day duplicates with different bodies | `_unique_card_path` adds `-2`, `-3` suffixes already |
| `httpx` dependency drift between client / server processes | `httpx>=0.25.0` is already pinned in `pyproject.toml` |

## Non-goals (explicit)

- **No vault skill creation.** The existing vault skill at `~/Projects/Au-vault/skills/vault/` already provides browse/edit/search via 7 MCP tools (`vault-read`, `vault-write`, `vault-search`, `vault-status`, `vault-scaffold`, `vault-convert`, `vault-health-repairs`). ADR-624 Track A is permanently retired.
- **No `/brain/vault` page redesign.** Out of scope.
- **No bulk-URL ingest.** Single URL per call. Rerunning is cheap thanks to idempotency, so a caller that wants 50 URLs simply loops 50 times.
- **No background URL fetching.** Synchronous within the MCP call.
- **No rate-limiting / per-domain auth / robots.txt.** Future hardening ADR if needed.
- **No HTML archive snapshot.** We persist the extracted prose body, not the raw HTML. A future ADR could add `<vault>/sources/urls/_raw/<sha256>.html.gz` if the use case appears.

## References

- ADR-624 (Cancelled) — original two-track proposal; this ADR carries Track B forward.
- ADR-559 — wiki signal priority and tiered scanning (the scanner this card flows into).
- `shared-vault/skills/ingest/scripts/source_cards.py` — existing source-card writer; `_compute_content_hash` and `_unique_card_path` are the reusable primitives.
- `shared-vault/skills/ingest/scripts/wiki_scanner.py:138` — `_scan_dir(self._vault_dir, source_surface="vault")` already covers `<vault>/sources/urls/`.
- `shared-vault/skills/ingest/scripts/mcp/__init__.py` — the `register_tools` entry point that the new `register_url_tools` joins.
- `src/lib/frontmatter_utils.py:112` — `write_vault_frontmatter` for persistence.
- `src/config/paths.py:468` — `get_vault_dir` for vault root resolution.
