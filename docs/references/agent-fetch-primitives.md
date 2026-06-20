---
title: "Agent Fetch Primitives"
status: accepted
date: 2026-05-13
tags: [architecture, fetch, agent, mcp, vendor-neutral]
---

# Agent Fetch Primitives

Vendor-neutral menu of fetch options for AI agents working inside Augur. Lives at **L3 ORCHESTRATION** in the [surface decision matrix](./surface-decision-matrix.md): the agent picks the right fetch tool, then hands the parsed content to an L4 atomic op for persistence.

If you only read one section, read [Decision table by content type](#decision-table-by-content-type).

## Why this exists

Different content types require different fetch strategies. A single MCP tool that wraps one fetcher cannot handle all of them cleanly — it would either fail on the hardest cases (JS-rendered SPAs, auth-walled content, scanned PDFs) or balloon into a workflow-shaped god-tool that violates the architecture. Per [agent-vs-mcp-examples.md](./agent-vs-mcp-examples.md) Example 2, the agent decides the extraction strategy; atomic ops only persist the result.

This doc gives every Augur agent the same menu so that `/ingest <url>` (or any other fetch-driven workflow) behaves consistently across Claude Code, Codex, Gemini, and OpenCode.

## Vendor neutrality

Tool categories below are named by **capability**, not by client name. Each AI client has a different concrete tool set; the agent maps the category to whatever it has available. Per [[feedback-vendor-neutral-design]], policy docs never name a specific vendor or model in workflow steps.

| Category | Examples of concrete tools agents may have |
|---|---|
| **Generic HTTP fetcher** | `WebFetch` (Claude Code); built-in `fetch`/`curl` via Bash; equivalent generic HTTP tools in other clients |
| **Browser-automation capability** | `mcp__claude-in-chrome__*` (Chrome extension MCP); `mcp__playwright__*` (Playwright MCP); other browser-control MCPs |
| **Agent-built-in web search** | Claude Code `WebSearch`; Codex web tool; Gemini grounding; any client-native search capability |
| **Augur extraction MCP** | `ingest-extract` (atomic, file-based — for PDFs, EPUBs, audio, images that need OCR/transcription) |
| **Authenticated provider MCPs** | Service-specific MCPs the user has installed (Google Workspace, GitHub via `gh` CLI, Slack, etc.) |

## Decision table by content type

| Content type | Preferred fetcher | Why | Fallback |
|---|---|---|---|
| Static HTML — blog posts, news, docs, GitHub README, marketing pages | **The client's browser-automation capability** | Loads the page authenticated + JS-rendered, as the user sees it | Generic HTTP fetcher (for trivially-static content — feeds, plain JSON, raw text where a session adds nothing — or when no browser capability is available) |
| **JS-rendered SPAs** — x.com, twitter.com, instagram.com, threads.net, linkedin.com, facebook.com, tiktok.com, most dashboards | **The client's browser-automation capability** | Generic fetchers return the SPA shell, not the rendered content. The browser-automation capability executes JS and reads the DOM as the user sees it | If no browser-automation capability is available, surface to user with the URL and a note that capture failed — never write a stub source card |
| **PDFs / EPUBs / scanned documents** | **Augur extraction MCP** (`ingest-extract`) | Designed for binary docs; handles OCR via the two-mode pattern when the PDF is scanned (see [llm-assisted-mcp-pattern.md](./llm-assisted-mcp-pattern.md)) | Generic fetcher only if you just need metadata, not content |
| **YouTube / podcasts / audio** | `knowledge-summarize-podcast` or `knowledge-summarize-youtube` (atomic MCP) | Augur owns the transcription + summarization contract for these | Manual transcript paste if the atomic op fails |
| **Authenticated content** — private GitHub issues, Google Docs, Confluence, paid news | **Authenticated provider MCP** if the user has it installed; otherwise **STOP and ask the user** | Per CLAUDE.md user-privacy rules, never bypass auth walls or use cached / archive copies of restricted content | None — escalate to user |
| **API endpoints returning JSON** | **Generic HTTP fetcher** with appropriate headers; or a service-specific MCP if one exists | JSON doesn't need browser rendering; structured already | None needed |
| **RSS / Atom feeds** | **Generic HTTP fetcher** | XML, statically served | None needed |
| **Image URLs** (when the goal is OCR or visual analysis) | **Augur extraction MCP** with the image, or agent's native vision tool | Two-mode pattern handles OCR via the agent's vision capability | Skip if the agent has no vision |
| **Local files (absolute path)** | Agent's file-read tool (e.g. `Read`) or `aug` CLI file ops | No fetch needed — direct read | None |
| **Internal Augur URLs** (`augur://...`) | Augur MCP resource read (`mcp__augur-core__*` resources) | These are MCP resources, not web URLs | None |

## Operational rules

1. **Detect the host class first.** Before picking a fetcher, classify the URL: SPA host (table row 2), static HTML (row 1), binary doc (row 3), media (row 4), auth-walled (row 5), API (row 6). The classification determines the tool, not the user's request phrasing.

2. **Don't fall through silently.** If the preferred fetcher returns a body shorter than ~200 chars for a content URL (the rough length of an HTML stub or error page), treat it as a fetch failure and try the fallback. If the fallback also fails, surface the failure to the user — do not persist a stub source card. This is per CLAUDE.md rule 1 (user-visible correctness first) and rule 5 (no workaround fixes).

3. **Auth-walled content is never bypassed.** Archive.today, the Wayback Machine, Google Cache, paywall bypassers, and similar workarounds are forbidden per the user-privacy and harmful-content sections in client instructions. If content is behind auth, either use an authenticated provider MCP that the user has installed and approved, or escalate.

4. **Browser-first uses the user's existing session only.** Defaulting to the browser-automation capability means fetching as the user's logged-in browser would. It never acquires access the user does not already have: it does not log in, does not bypass an auth wall the session itself doesn't satisfy, and surfaces (rather than works around) any login/captcha gate. "As the user sees it" means "with the session the user already has."

5. **Respect host rate limits.** The browser-automation capability and generic fetchers should not retry aggressively. One try → fallback → escalate.

6. **Bot-detection systems (CAPTCHA, etc.) are never bypassed.** If a fetch hits a CAPTCHA, surface it to the user.

7. **Privacy.** Never send URLs with embedded sensitive data (tokens, session IDs) through any fetcher without explicit user confirmation. Strip query strings that look like credentials.

8. **The agent decides "is this worth saving?"** before calling the L4 atomic save op. Empty bodies, error pages, paywall placeholders, and login screens are not worth saving — they should be discarded with a user-visible note.

## Examples

### Example A — Twitter/X status URL

```
URL: https://x.com/garrytan/status/2042925773300908103
1. Classify: SPA host (x.com matches row 2).
2. Use the client's browser-automation capability:
   - mcp__claude-in-chrome__navigate to the URL
   - read_page or get_page_text to extract DOM-rendered tweet text + author + timestamp
3. Parse: { title: "<author>: <first 60 chars of tweet>", body: <tweet text + media refs>, canonical_url: <input> }
4. Decide: is this worth saving? (yes — user explicitly requested ingest)
5. Call atomic save: aug save-url-source --url ... --title ... --body ...
```

### Example B — Substack blog post

```
URL: https://example.substack.com/p/some-post
1. Classify: static HTML (row 1).
2. Use the client's browser-automation capability (browser-first per row 1).
   Fast-path: if no browser capability is available, fall back to a generic HTTP fetcher.
3. Parse: { title: <h1>, body: <article body>, canonical_url: <input> }
4. Decide: save.
5. aug save-url-source ...
```

### Example C — GitHub private issue

```
URL: https://github.com/org/private-repo/issues/123
1. Classify: authenticated content (row 5).
2. Use gh CLI (the user-installed authenticated provider): `gh issue view org/private-repo#123`.
3. Parse + save as above.
```

### Example D — Scanned PDF dropped into the inbox

```
File: <vault>/inbox/2026-05-13/report.pdf
1. Classify: binary doc (row 3).
2. Call ingest-extract atomic MCP tool.
3. If returns {needs_llm: true, image_data: ...} — run two-mode pattern: agent OCRs the image, calls submit-ingest-extract-result.
4. Parse merged result.
5. Call inbox-consume-folder or aug save-document-source ...
```

## Cross-references

- [Surface Decision Matrix](./surface-decision-matrix.md) — where this layer sits in the architecture
- [Agent vs MCP Checklist](./agent-vs-mcp-checklist.md) — what belongs in agent vs MCP code
- [Agent vs MCP Examples](./agent-vs-mcp-examples.md) — concrete good/bad examples
- [LLM-Assisted MCP Pattern](./llm-assisted-mcp-pattern.md) — two-mode pattern for content needing LLM help (OCR, transcription)
- [AI Client Execution Model](./ai-client-execution-model.md) — Augur as harness
