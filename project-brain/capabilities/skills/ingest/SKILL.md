---
name: ingest
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
x-augur-license: MIT
description: Local-first Brain Inbox ingestion for files, URLs, email drops, prompts, recordings, and thought capture. Use when scanning watched folders, routing packets, consuming source material, writing source cards, refreshing Browse or RAG indexes, or checking Inbox, Wiki, and Brain Insights surfaces.
x-augur-tab: inbox
x-augur-requires-platform: true
x-augur-commands:
- id: run-pending-enrichment
  type: workflow
  visibility: auto
  description: Drain ADR-753 pending-enrichment queue through the LLM-Assisted MCP
    Mode 2 dispatcher.
  callable: augur/scripts/run_pending_enrichment.py
  protocol: daemon-job
  loop:
    name: knowledge-enrichment
    tier: 1
    trigger: continuous
    scheduler: daemon
    config:
      interval_seconds: 300
      max_per_run: 10
x-augur-mcp-tools:
- url-extract
- save-url-source
- save-prompt
- note-classification-update
- enrich-article
- submit-enrich-article-result
- inbox-source-lanes
- inbox-discover-vaults
- inbox-register-vault
- inbox-stage-packet
- inbox-pending-packet
- inbox-route-packets
- inbox-consume-packets
- inbox-runs
- inbox-folders
- inbox-scan-folder
- inbox-consume-folder
- inbox-purge-folder
- email-drop-sources
- email-drop-scan-source
- email-drop-consume-source
- inbox-run-history
- inbox-run-detail
- brain-insights
x-augur-dashboard-pages:
- route: /workspace/inbox
  title: Inbox
  icon: Inbox
  order: 1
  keywords:
  - inbox
  - intake
  - source-lanes
  - vaults
  - routing
- route: /workspace/insights
  title: Insights
---

# Ingest

Local-first Brain Inbox workflow for turning user-provided sources into durable
Augur knowledge without losing provenance, routing, or Browse visibility.

## Scope

Use this skill when the work is about source intake, source-card creation,
Inbox packet lifecycle, URL capture, email-drop capture, thought or prompt
capture, meeting memory, wiki compounding inputs, or the Brain Inbox dashboard
pages. Keep the surface local-first: agent policy decides what should happen,
MCP tools and scripts perform atomic reads or writes, and generated dashboard
pages consume those results through the MCP bridge.

Do not write vault notes, source cards, or runtime state by hand. Route writes
through the existing ingest helpers so frontmatter, content hashes, destination
brain resolution, deduplication, and Browse/RAG refresh behavior stay aligned.

## Workflow

Step 1. Identify the source type from the user request: URL, file, folder,
audio, image, thought, reusable prompt, email drop, pending enrichment item, or
Inbox packet.

Step 2. Select the canonical policy or helper:

- `commands/note.md` documents the retained capture policy behind `/keep` and
  the retired `/note` alias.
- `scripts/url_ingest.py`, `scripts/source_cards.py`, and
  `scripts/prompt_cards.py` handle durable source-card and prompt writes.
- `scripts/inbox_scan.py`, `scripts/inbox_consume.py`, `scripts/inbox_store.py`,
  and `scripts/inbox_packet_*.py` handle watched folders and packet routing.
- `scripts/email_drop_*.py` handles email-drop discovery, parsing, storage, and
  consumption.
- `scripts/mcp/` exposes atomic MCP tools for dashboard and agent calls.
- `augur/scripts/run_pending_enrichment.py` drains the pending enrichment queue.

Step 3. Preserve provenance and routing data. Use configured path helpers and
brain resolution instead of hardcoded local paths. Surface the resolved brain,
saved path, deduplication status, content hash, and indexing status when the
helper returns them.

Step 4. Refresh or verify the user-facing index after writes. For captured
notes and source cards, verify that Browse, the relevant Inbox run detail, or
the RAG/wiki status reflects the new artifact instead of relying only on a file
write or command exit code.

Step 5. Report failures at the real boundary. If extraction, transcription,
TCC access, email access, routing, dedupe, or indexing fails, surface that
specific failure and do not create placeholder notes.

## Dashboard And MCP

The Workspace surface pages `/workspace/inbox` and `/workspace/insights` are
user-facing consumers of this skill. Dashboard code should call the listed MCP
tools through `POST /api/mcp/tool`; it should not spawn local scripts or read
files directly. New ingest signals should ride existing Browse item metadata or
Inbox run-detail records unless the feature is a genuine interactive manager.

When adding or changing MCP behavior, keep agent judgment outside the atomic
tool. The tool should extract, persist, route, list, or report deterministic
state. Classification that needs judgment should follow the LLM-assisted MCP
callback pattern and submit the final result through a dedicated response tool.

## Examples

Example URL capture: classify the URL, run the URL capture helper or the
`url-extract` plus `save-url-source` MCP sequence, then report the saved title,
summary, path, canonical URL, and dedupe status.

Example folder intake: scan the folder first, inspect the proposed packet
routes, consume only when the user asked for consume semantics, then verify the
Inbox run history or packet detail includes the consumed files.

Example audio intake: transcribe with the audio extraction surface, classify
voice memo versus meeting, persist through the audio ingest writer, then report
the note path, Augur-owned audio path, provider metadata, and attendee slugs
when present.

## Verification Checklist

- [ ] Confirm the helper or MCP tool used the real configured brain or inbox
  lane, not a temporary fixture path.
- [ ] Confirm the output includes real saved paths, hashes, run ids, source
  counts, or extracted content rather than only a zero/empty stats response.
- [ ] Confirm the relevant Browse, Inbox, wiki, or Brain Insights surface can
  see the new or updated artifact when the task promises user-visible value.
- [ ] Confirm no placeholder note, fallback-only data, direct dashboard file
  read, or hand-built vault path was introduced.

## References

Load these files only when the task needs that detail:

- `commands/note.md` for capture dispatch, legacy `/note` semantics, and `/keep`
  policy.
- `scripts/mcp/` for tool names and atomic MCP request/response contracts.
- `augur/tests/test_inbox*.py`, `augur/tests/test_url*.py`, and
  `augur/tests/test_email*.py` for expected ingest behavior.
- Wiki engine and compounding resources live in the `wiki` skill.
