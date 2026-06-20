---
title: Obsidian-Native Ingest URL Wiki MVP — Design
type: spec
status: draft
created: 2026-05-10
authors:
  - gsannikov
related:
  - shared-vault/skills/ingest/SKILL.md
  - shared-vault/skills/ingest/scripts/source_cards.py
  - shared-vault/skills/ingest/scripts/wiki_scanner.py
  - shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
  - shared-vault/skills/knowledge/scripts/mcp/tools_summarize.py
  - src/mcp/augur_core/tools/core/vault_ops.py
  - src/mcp/augur_framework/tools/internal/vault_status.py
governance:
  next_step: ADR-624 already adopted (Accepted); proceed to /adr implement via the linked plan.
tags:
  - skills
  - vault
  - obsidian
  - wiki
  - ingest
  - mcp
---

# Obsidian-Native Ingest URL Wiki MVP — Design

A two-track delivery that turns the user's Obsidian vault into the
**primary editing/browsing surface** for source cards and compiled wiki
pages, then adds the smallest possible URL-ingest path so the user can
go from "I read a thing on the web" to "it's a source card the wiki
compiler will pick up" in one MCP call.

The two tracks ship as one ADR because they only deliver value
together: an Obsidian-native vault skill without URL ingest leaves the
user with nothing new to *put* in the vault from a browser; a URL
ingest tool without Obsidian ergonomics dumps cards into a folder the
user has no convenient way to read or organize.

## Context

### Current state

- The repo ships an Obsidian **plugin** (`plugins/obsidian/`) but no
  Augur **skill** named `obsidian` or `vault`. The capability table in
  `CLAUDE.md` lists seven `mcp-tool:vault-*` entries — `vault-read`,
  `vault-write`, `vault-search`, `vault-status`, `vault-scaffold`,
  `vault-convert`, `vault-health-repairs`, plus `vault-status` already
  registered in `src/mcp/augur_framework/tools/internal/vault_status.py`
  and a generic `vault_file_read_impl` / `vault_file_write_impl` pair
  in `src/mcp/augur_core/tools/core/vault_ops.py`. The capability
  contracts exist; the skill does not.

- Source cards (the unit of "I captured something") are written by
  `shared-vault/skills/ingest/scripts/source_cards.py::write_source_card`
  into `<vault>/sources/files/<stem>.md`. Each card is a Markdown file
  with YAML frontmatter (`title`, `source_type`, `route`, `tags`,
  `content_hash`, etc.) and a body containing a `> [!summary]` callout
  plus routing/processing-evidence sections.

- The wiki compiler (`shared-vault/skills/ingest/scripts/wiki_scanner.py`
  + `wiki_concept_compiler.py`) walks the vault looking for source
  cards and curated repo docs. Only files that match the source-card
  layout (frontmatter + recognizable structure) are picked up; anything
  else is ignored. The compiler is therefore the contract the new
  URL-ingest tool must satisfy.

- `shared-vault/skills/knowledge/scripts/mcp/tools_summarize.py`
  registers a `knowledge-summarize-url` tool that runs an external
  summarizer CLI against a URL. It does *not* persist anything to the
  vault — it returns a summary string.

- There is **no** MCP mutation today that takes a URL and produces a
  source card. The user must currently save a webpage to disk, drop
  it into the inbox, wait for `inbox-consume-folder` to extract it,
  and accept whatever route the heuristic picks. That is too many
  steps for the "I read an article and want it captured" workflow.

### Constraints

1. **The wiki compiler input contract is fixed.** Source cards must
   live under `<vault>/sources/...` with the existing frontmatter
   shape; otherwise the compiler will skip them and the captured URL
   never compounds into a wiki page.

2. **Vault path resolution goes through `src.config.paths`** (CLAUDE.md
   rule 3). No hardcoded `~/Obsidian` or `os.environ["VAULT"]` shortcuts.

3. **Plugins ≠ skills.** `plugins/obsidian/` is the user's
   Obsidian-side TypeScript companion and is governed by ADR-559. The
   new `obsidian` skill lives under `shared-vault/skills/obsidian/`
   and exposes Augur-side MCP tools; it does *not* replace or talk to
   `plugins/obsidian/`.

4. **MVP, not parity.** "Promote the staged obsidian skill" in the
   decision summary describes capability *contracts* (read, write,
   search, status, scaffold, convert) that are already partially
   covered by code in `src/mcp/augur_core/tools/core/vault_ops.py` and
   `src/mcp/augur_framework/tools/internal/vault_status.py`. The MVP
   is to wire those impls into a real skill manifest with seven
   registered tools — not to invent new vault primitives.

5. **No skipped tests, no fallback bodies.** Per CLAUDE.md rule 5,
   the URL-ingest tool either captures a real article or returns a
   structured error; it never writes a stub source card with empty
   body to make a green path look real.

## Decision

### Track A — Promote the staged Obsidian skill

Create `shared-vault/skills/obsidian/` as a real skill with a `SKILL.md`
manifest and a registered MCP-tools module. Reuse the existing
implementations from `src/mcp/augur_core/tools/core/vault_ops.py` and
`src/mcp/augur_framework/tools/internal/vault_status.py`; the new skill
is mostly registration glue plus three small additions (`search`,
`scaffold`, `convert`).

The seven tools the skill registers:

| Tool | Implementation source | Notes |
|---|---|---|
| `vault-read` | `vault_ops.vault_file_read_impl` (existing) | Read a vault file by skill + relative path. |
| `vault-write` | `vault_ops.vault_file_write_impl` (existing) | Write/update with frontmatter merge. |
| `vault-status` | `vault_status` module (existing) | Git status, sync state, health summary. |
| `vault-search` | New — `obsidian/scripts/vault_search.py` | Markdown grep with frontmatter-aware filters (tags, source_type). |
| `vault-scaffold` | New — `obsidian/scripts/vault_scaffold.py` | Idempotently create the canonical folder layout (`sources/{files,urls}/`, `wiki/`, `prompts/`, `scratch/`) with seed READMEs. |
| `vault-convert` | New — `obsidian/scripts/vault_convert.py` | Frontmatter-aware format conversion: legacy `.md` (no frontmatter) → ADR-571-compliant frontmatter; `.txt` → `.md` with seed frontmatter. |
| `vault-health-repairs` | Delegate to existing platform-admin healers | One-line wrapper that calls the existing health-repair entrypoint and surfaces it as an MCP tool the obsidian skill owns. |

The skill manifest:

```yaml
name: obsidian
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
description: Obsidian-native browsing and editing surface for vault source cards and compiled wiki pages.
x-augur-hub: brain
x-augur-tab: vault
x-augur-mcp-tools:
  - vault-read
  - vault-write
  - vault-search
  - vault-status
  - vault-scaffold
  - vault-convert
  - vault-health-repairs
```

`x-augur-hub: brain` is correct — the "brain" hub is where compounded
knowledge lives, and the obsidian skill is its file-level surface.
The dashboard tab `vault` is new (no existing `/brain/vault` page); we
ship a minimal config-driven page (ADR-491 yaml-pages) that lists
recent source cards and links into Obsidian via `obsidian://` URIs.

### Track B — `ingest-url` MCP mutation

Add a single new MCP tool on the existing `ingest` skill:

```
ingest-url(url: str, tags: str = "", note: str = "") -> JSON
```

The tool:

1. Fetches the URL with `httpx` (10 s timeout, single redirect follow).
2. Extracts main content via `trafilatura` (preferred) with a fallback
   to a tiny BeautifulSoup `<article>` / `<main>` heuristic.
3. Pulls metadata: title (`<title>` or first `<h1>`), publish date
   (JSON-LD `datePublished`, `<meta property="article:published_time">`,
   or `Last-Modified` header), author (JSON-LD `author.name` if
   present), and a slug derived from the URL path.
4. Computes a stable `content_hash` (sha256 of canonical-URL + body)
   so re-ingesting the same URL is idempotent.
5. Writes a source card to `<vault>/sources/urls/<YYYY-MM-DD>-<slug>.md`
   using `write_source_card`'s patterns — frontmatter shape extended
   with three new keys:
   - `source_type: "url"` (currently only `"file"` and `"inbox-file"` exist)
   - `source_url: "<canonical url>"`
   - `fetched_at: "<utc-iso>"`
6. Returns JSON: `{success: true, path: "<rel>", title: "...",
   content_hash: "...", reused: false}` (or `reused: true` if the same
   `content_hash` was already on disk).

Optional `tags` and `note` arguments let the caller seed user tags and
prepend a one-paragraph "why I saved this" note above the article body.
Both are user-supplied strings; trim, split tags on commas, dedupe.

### Sub-decisions

1. **`source_type: "url"` is a new enum value, not a generic
   `external` bucket.** `"url"` is unambiguous and lets the wiki
   scanner / RAG indexer treat URL-sourced cards differently from
   inbox files (e.g., highlight the `source_url` link in the wiki
   page footer; never re-extract them on the inbox path).

2. **URL cards live in `sources/urls/`, not `sources/files/`.** Two
   reasons: (a) the file-naming pattern is different (date + slug,
   not stem-of-original-filename); (b) it makes the user's Obsidian
   tree readable — "things I saved from the web" vs "things I
   dropped in inbox".

3. **No HTML rendering, no images, no inline assets.** MVP captures
   prose text only. If `trafilatura` returns empty body (paywall,
   JS-only page, login wall), the tool fails with a structured
   error and writes nothing. The user can still save the article
   manually and drop it in the inbox; we do not silently write a
   broken card.

4. **Content hash includes the canonical URL, not the page text
   alone.** This ensures `https://example.com/post` and
   `https://example.com/post/` resolve to the same hash even when
   trafilatura extracts identical bodies. Canonicalization rules:
   strip fragment, strip tracking params (`utm_*`, `fbclid`,
   `gclid`), collapse trailing slash on path.

5. **Idempotent writes.** Re-ingesting the same canonical URL with
   the same content_hash returns `reused: true` and the existing
   path; it does not append a `-2` suffix. If the body changed
   (article was updated), we **overwrite** the card and bump
   `fetched_at`, but preserve user-edited fields by reading the
   existing frontmatter and merging non-system keys.

6. **Trafilatura over Readability.** Trafilatura has better main-
   content detection on news/blog posts and ships with a permissive
   license. We declare it as a hard dependency in `pyproject.toml`.
   The BeautifulSoup fallback is for environments where trafilatura
   import fails for any reason; it is not a quality fallback, only
   a "did the import succeed at all" guard.

7. **The `obsidian` skill does not handle URL ingest.** URL ingest is
   a knowledge-capture workflow that belongs on the `ingest` skill
   alongside the existing inbox-consume flow. The `obsidian` skill
   is the editing/browsing layer; it reads what `ingest` writes.

8. **Capability exposure is `cli via shell` for `ingest-url`,
   matching the rest of the wiki tools.** The dashboard does NOT
   expose `ingest-url` directly. A future ADR can promote it to
   `mcp via dashboard` once we have a "save URL" UI, but MVP keeps
   it CLI-only via the AI client.

## Architecture

### Components

```
                                ┌────────────────────────────────────┐
                                │  shared-vault/skills/obsidian/     │
                                │   SKILL.md                         │
                                │   scripts/                         │
                                │     vault_search.py    (new)       │
                                │     vault_scaffold.py  (new)       │
                                │     vault_convert.py   (new)       │
                                │     mcp/                           │
                                │       __init__.py    (register_)   │
                                │       vault_tools.py (new — 7 tools│
                                │         delegating to vault_ops &  │
                                │         vault_status & new scripts)│
                                │   augur/                           │
                                │     dashboard/      (yaml page)    │
                                │     pages/vault.yaml               │
                                │     tests/                         │
                                │       test_vault_search.py         │
                                │       test_vault_scaffold.py       │
                                │       test_vault_convert.py        │
                                │       test_vault_tools_register.py │
                                └────────────────────────────────────┘
                                              │
                                              │ writes/reads
                                              ▼
                                ┌────────────────────────────────────┐
                                │  <vault>/                          │
                                │   sources/                         │
                                │     files/    ← inbox-consume      │
                                │     urls/     ← ingest-url (new)   │
                                │   wiki/       ← wiki_compiler      │
                                │   prompts/                         │
                                │   scratch/                         │
                                └────────────────────────────────────┘
                                              ▲
                                              │ reads → wiki pages
                                              │
                                ┌────────────────────────────────────┐
                                │  shared-vault/skills/ingest/       │
                                │    scripts/                        │
                                │      url_ingest.py     (new)       │
                                │      source_cards.py   (extend)    │
                                │      mcp/wiki_tools.py (new tool)  │
                                │    augur/tests/                    │
                                │      test_url_ingest.py            │
                                │      test_source_card_url.py       │
                                └────────────────────────────────────┘
```

### Interfaces

**Track A — `obsidian` skill MCP tools**

```
vault-read(skill: str, path: str) -> JSON       # delegates to vault_ops
vault-write(skill: str, path: str, title: str, body: str, metadata: object) -> JSON
vault-status() -> JSON                          # delegates to vault_status
vault-search(query: str, *, hub: str = "", source_type: str = "", tags: str = "", limit: int = 20) -> JSON
vault-scaffold(skill: str = "") -> JSON         # idempotent
vault-convert(path: str, target: str = "frontmatter") -> JSON
vault-health-repairs(action: str = "report") -> JSON
```

All tools return `{success: bool, ...}` JSON, matching the existing
pattern in `wiki_tools.py`.

**Track B — `ingest-url` MCP tool (registered on `ingest` skill)**

```
ingest-url(url: str, tags: str = "", note: str = "") -> JSON
```

Returns:

```json
{
  "success": true,
  "path": "sources/urls/2026-05-10-pat-research-paper-on-attention.md",
  "title": "Research paper on attention",
  "source_url": "https://example.com/papers/attention",
  "content_hash": "sha256:abcdef...",
  "fetched_at": "2026-05-10T14:30:00Z",
  "reused": false,
  "tags": ["research", "ml"]
}
```

On failure (HTTP error, paywall, empty extraction):

```json
{
  "success": false,
  "error": "Empty extraction (likely paywall or JS-rendered page)",
  "url": "https://example.com/...",
  "stage": "extract"   // "fetch" | "extract" | "write"
}
```

**Source-card frontmatter (URL flavor)**

```yaml
---
title: <article title>
source_type: url
source_url: https://example.com/path
fetched_at: 2026-05-10T14:30:00Z
publish_date: 2025-12-01           # if extracted
author: Jane Doe                   # if extracted
tags: [research, ml]               # user-supplied + automatic
content_hash: sha256:...
---
```

Body:

```markdown
# <Article title>

> [!summary]
> <First 800 chars of extracted prose>

<note from caller, if provided>

## Article

<full extracted prose>

## Source

- URL: [Visit original](https://example.com/path)
- Author: Jane Doe
- Published: 2025-12-01
- Fetched: 2026-05-10T14:30:00Z
```

This shape passes the wiki compiler's existing source-card detection
because: (a) it begins with frontmatter; (b) `source_type` is set;
(c) the `> [!summary]` callout matches the inbox-card pattern.

### Data flow

1. User says to AI client: *"ingest this article: https://…"*.
2. AI client calls `ingest-url(url=…)`.
3. Tool fetches, extracts, computes hash, writes
   `<vault>/sources/urls/<date>-<slug>.md`.
4. Wiki compiler picks up the new card on next run (manual via
   `wiki-rebuild` or auto via daemon).
5. Compiled wiki pages live in `<vault>/wiki/<hub>/<page>.md`.
6. User browses both source cards and compiled wiki pages in
   Obsidian; the `obsidian` skill's `vault-read`/`vault-search`
   tools provide the same view to AI clients.

## Alternatives Considered

### A. Use `knowledge-summarize-url` and call it a day

Reuse the existing `knowledge-summarize-url` tool; teach the wiki
compiler to ingest summary strings. Rejected because:

- The summary tool returns a string, not a vault file. Persisting it
  would require every caller to handle filesystem writes themselves,
  defeating the "one MCP call to capture" goal.
- The summary is lossy by design (300-word digest); the wiki
  compiler benefits from full prose to extract concepts.
- Two responsibilities (summarize and capture) collapse into one
  tool; harder to reason about.

### B. Write URL cards to `sources/files/` alongside inbox files

Drop the `sources/urls/` separation. Rejected because:

- `sources/files/` filenames are derived from the original filename
  (`<stem>.md`); URLs do not have a meaningful stem. Forcing a
  shared folder leads to collisions and ugly filenames.
- The user's mental model in Obsidian benefits from the split — a
  folder of "things I saved from the web" is distinct from "things
  I dropped in inbox" and supports different review workflows.

### C. Build the `obsidian` skill as a vendor/external upstream

Pull from a community Obsidian-vault MCP server. Rejected because:

- No existing community server matches the source-card layout we
  need; we would need to fork and maintain anyway.
- The capability contracts already live in `src/mcp/augur_core/`
  and `src/mcp/augur_framework/`; promotion is registration work,
  not new code.
- Vendor tier is reserved for SHA-bumpable upstreams (per the user's
  external-skill strategy); this is a first-party concern.

## Consequences

### Positive

- One MCP call captures a webpage as a source card the wiki
  compiler will compound. Removes the "save HTML, drop in inbox,
  wait for OCR" friction.
- Obsidian becomes a first-class browsing surface: the user opens
  their vault and sees source cards, wiki pages, prompts in
  organized folders, with the option to call `vault-search` from
  any AI client to query across them.
- Re-asserts the wiki-compiler input contract by making it
  literally executable in tests (`tests/test_url_ingest.py`
  asserts the written card passes `wiki_scanner.scan_sources`).
- `vault-scaffold` gives new users a one-call "set up my vault
  layout" path that is currently spread across docs.
- All seven `mcp-tool:vault-*` capability-table entries gain a real
  registration site (the `obsidian` skill), removing a long-standing
  TODO.

### Negative

- New external dependencies (`trafilatura`, `httpx` if not already
  present) are added to `pyproject.toml`. `httpx` is already a
  transitive dep, but `trafilatura` is genuinely new and pulls
  `lxml`. Disk and install-time cost.
- More frontmatter shapes to keep in sync with ADR-571 vault-
  frontmatter conventions. Each new field (`source_url`,
  `fetched_at`, `publish_date`, `author`) must be classified as
  system vs user.
- The `obsidian` skill's `vault-search` overlaps with the
  knowledge skill's `unified-search` and `wiki-search`. We need
  to carve a clean boundary in the SKILL.md description so AI
  clients know which to call when. (Decision: `vault-search` is
  filesystem-grep-style; `unified-search` is RAG-backed; `wiki-search`
  is wiki-page-only.)

### Neutral

- The Obsidian *plugin* (`plugins/obsidian/`) is unchanged — the
  new skill lives on the Augur side and reads/writes the same vault
  the plugin renders.
- The dashboard gains a new `/brain/vault` tab via a config-driven
  YAML page (ADR-491). Implementation is a thin list view; the
  feature is value-bearing because it links to Obsidian via
  `obsidian://` URIs.
- The existing `inbox-consume-folder` flow keeps writing to
  `sources/files/`. URL ingest writes to `sources/urls/`. No
  collisions.

## References

- ADR-624 (this) — Obsidian-Native Ingest URL Wiki MVP
- ADR-559 — Obsidian plugin and Augur-side compatibility
- ADR-560 — Semantic Wiki Page Compiler (the consumer of source cards)
- ADR-563 — Vault-Owned User Skills, Pages, and Draft Staging
- ADR-571 — Vault Frontmatter Conventions: System Fields and
  Relationship Discovery (governs the new frontmatter keys)
- `shared-vault/skills/ingest/scripts/source_cards.py` — pattern this
  ADR extends with `source_type: "url"`.
- `shared-vault/skills/ingest/scripts/wiki_scanner.py` — the input
  contract the new tool's output must satisfy.
- `src/mcp/augur_core/tools/core/vault_ops.py` — the read/write impls
  the `obsidian` skill registers as MCP tools.
- `src/mcp/augur_framework/tools/internal/vault_status.py` — the
  status impl the `obsidian` skill exposes as `vault-status`.
- CLAUDE.md capability-policy table rows for `vault-*` tools and
  rule 13 (`x-augur-hub` ownership), rule 23 (exhaustive migrations).
