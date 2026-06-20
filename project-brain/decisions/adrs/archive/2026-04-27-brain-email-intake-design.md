---
title: Brain Email Intake Design
date: 2026-04-27
status: proposed
scope: design
---

# Brain Email Intake Design

## Purpose

Augur should let the user save useful emails into a local mail drop folder and consume them through the same Brain Inbox workflow that already handles Desktop and Downloads folders.

The first useful version is intentionally folder-first. Augur reads email files that already exist on disk, parses them as packets, routes useful body text, links, and attachments into the existing ingest/document/wiki paths, and records a clear run history. How Gmail, Apple Mail, Outlook, scripts, rules, AI agents, or manual user actions place email files into that folder is outside the core consume path.

The product promise is: **save or export an email into the Augur mail folder, or ask a connected AI agent to export Augur-marked mail there; click Consume in Brain Inbox; and Augur routes the email packet into durable knowledge, indexed documents, and wiki-ready source material.**

## Decisions

- Use a local mail drop folder as the v1 email intake source.
- Keep the core email intake contract inside the Brain Inbox and ingest architecture, not inside Apple, Gmail, or Outlook provider skills.
- Allow provider skills and connected AI-agent app integrations to remain external/private. Apple, Gmail, Outlook, Gemini, Codex, or other client helpers can write email files into the drop folder later, but they are feeders rather than required core dependencies.
- Treat the folder as the boundary for this ADR. Producing files in the folder is feeder responsibility, whether the feeder is a native app helper, a provider API, a connected AI agent, or a manual export.
- Support the mail artifacts produced by Apple Mail, Gmail/Google Takeout, and Outlook: `.eml`, `.msg`, `.oft`, `.mbox` files, Apple `.mbox` bundles, `.pst` exports, and archives such as `.zip`, `.tgz`, `.tar`, and `.tar.gz` that contain those files.
- Accept rendered/non-native exports such as `.pdf`, `.txt`, `.html`, `.htm`, `.mht`, and `.mhtml` as degraded body-only document inputs when full email metadata cannot be recovered.
- Treat each saved email as one packet: metadata, body-derived text, extracted links, and attachments.
- Support tags/categories/labels as upstream selection mechanisms, but only after the provider-specific or AI-agent-native feeder exists. The folder parser does not need to know whether the email came from a self-sent rule, Gmail label, Outlook category, Apple mailbox, Gemini/Codex connector export, or manual drag/export.
- Default batch limit is 5 files.
- Support newest-first and oldest-first ordering based on file timestamp, defaulting to newest-first.
- Scan is preview-only and never mutates mail files, vault files, documents, indexes, or wiki state.
- Consume moves successfully processed source files to a processed folder and failed files to a failed/quarantine folder unless the source config says to leave them in place.
- Do not save every raw email as a permanent vault source card by default.
- Save successfully consumed external article/resource links as vault source cards through the existing URL ingest flow.
- Route the email body as a note/document only when it has standalone value beyond provenance.
- Route attachments through the same document intake path used by folder consume.
- Default wiki behavior is mark-needed, with an explicit `Prepare Wiki Update` action available from the dashboard.

## Architecture

Email intake is a Brain Inbox source type backed by a local file folder.

The high-level flow is:

```text
mail drop folder -> email file parser -> email packet -> ingest consume -> RAG/wiki signals -> file aftercare
```

`/brain/inbox` owns the user workflow: source list, scan, consume, batch settings, latest status, run history, and wiki update actions.

The ingest layer owns durable routing and indexing: email file parsing, link extraction, attachment staging, document extraction, filename normalization, destination routing, RAG indexing, wiki update flags, run records, idempotency, and user-visible failure reasons.

Provider-specific systems are feeders into the folder, not blockers for v1:

- Apple Mail can later export selected mail or mailbox contents into `.eml` files, `.mbox` files, or Apple `.mbox` bundles.
- Gmail CLI/API, Google Takeout, or a private Google Workspace skill can later export labelled messages into `.eml`, `.mbox`, `.zip`, `.tgz`, or `.tar.gz` artifacts.
- Outlook on Windows can use manual save/drag/export into the folder, or a later Classic Outlook COM feeder that writes `.msg`, `.eml`, `.oft`, `.pst`, `.pdf`, `.txt`, `.html`, `.mht`, or archive artifacts.
- Microsoft Graph can exist as a later enterprise/cloud adapter, but it is not required for the local folder-first path.
- AI-agent-native feeders can use whatever app connectors the active client already has. For example, the user can ask Gemini to find mail marked `Augur`, export or save the matching Gmail or Outlook messages into the configured mail drop folder in a supported format, and then run Brain Inbox scan/consume.

This keeps the first implementation useful without Augur's core runtime owning tenant admin approval, provider auth, or platform-specific mail automation. A connected agent may still use provider auth when the user has already granted it.

## Source Registry

Email sources should be stored in the Brain Inbox runtime store beside watched folders, with a typed source record.

Example source:

```yaml
id: local-mail-drop
type: email_drop_folder
display_name: Mail Drop
enabled: true
path: "{get_documents_dir()}/inbox/email"
formats:
  - eml
  - msg
  - oft
  - mbox
  - pst
  - zip
  - tgz
  - tar
  - tar.gz
  - pdf
  - txt
  - html
  - htm
  - mht
  - mhtml
batch:
  limit: 5
  order: newest_first
after_success:
  action: move_file
  target: processed
after_failure:
  action: move_file
  target: failed
wiki:
  default_mode: mark_needed
```

The source contract must avoid hardcoded local paths. Defaults and configured paths must resolve through Augur path helpers for documents, runtime, vault, logs, and cache locations.

## Folder Contract

The mail drop folder is the integration boundary.

Accepted email-native inputs:

- `.eml` files, usually from Apple Mail, Gmail export, Thunderbird, Outlook export, or provider scripts.
- `.msg` files, usually from Classic Outlook on Windows.
- `.oft` Outlook template files when a user saves a message/template in Outlook format. These should parse through the Outlook-message parser where possible and degrade gracefully where metadata is incomplete.
- `.mbox` files, usually from Gmail/Google Takeout, Apple Mail mailbox export, Thunderbird, or other standards-based mail clients.
- Apple Mail `.mbox` bundles/directories, which may contain mailbox data inside a package-style folder.
- `.pst` Outlook data exports, including folder exports from new or classic Outlook when the user cannot save individual messages.

Accepted archive inputs:

- `.zip`
- `.tgz`
- `.tar`
- `.tar.gz`

Archive files are containers, not packets. Scan should inspect their manifest safely and report the number and types of email artifacts inside. Consume should extract into controlled runtime staging, parse supported contained artifacts, reject path traversal entries, enforce size/file-count limits, and keep archive-level provenance in every run record.

Accepted degraded inputs:

- `.pdf`
- `.txt`
- `.html`
- `.htm`
- `.mht`
- `.mhtml`

These formats are common save/print/export outputs, especially from Outlook. They should be accepted so users are not blocked, but they are body/document fallbacks rather than full-fidelity email packets. Augur should route them through document intake, extract links where possible, and clearly show that sender/recipient/message-id metadata may be missing.

Folder layout:

```text
email/
  inbox/        # user or feeder places files here
  processed/    # successful consume moves files here by default
  failed/       # failed or partial files move here when configured
  staging/      # temporary archive and attachment extraction during consume
```

The source may also point directly at one configured folder if the user wants a simpler layout. In that mode, processed and failed folders are created beside the source folder.

## Scan Behavior

Scan is a preview operation. It should not mutate source files, vault files, documents, RAG indexes, or wiki state.

Scan returns:

- matching file count
- supported, degraded, archive, and unsupported file counts
- estimated attachment count
- contained message count for archives and mailbox bundles when cheap to compute
- article/resource link count when cheap to compute
- newest and oldest file timestamps
- source path and file format summary
- source health state
- parser or permission errors

Scan must report unsupported files as skipped with reasons, not as empty success.

## Consume Behavior

Consume processes matching email files in chunks. The default chunk size is 5, with selectable newest-first or oldest-first ordering.

Each email-native file or mailbox-contained message becomes an email packet:

```text
file metadata + email headers + body text/html-derived text + extracted links + extracted attachments
```

Each degraded input becomes a document-like packet:

```text
file metadata + extracted text/html/pdf content + extracted links + limited provenance
```

Packet processing order:

1. Fingerprint the source file before processing.
2. If the source is an archive, safely extract supported contained artifacts into runtime staging.
3. If the source is a mailbox bundle or mailbox file, enumerate contained messages while preserving mailbox/archive provenance.
4. Parse email metadata where available: subject, sender, recipients, sent/received timestamps, message id, body, links, and attachments.
5. For degraded inputs, extract body text and links and mark metadata as partial.
6. Classify links as article/resource, downloadable file, internal/app link, or noisy/unsupported.
7. Capture article/resource links through the existing URL ingest source-card flow.
8. Treat downloadable file links as remote attachment candidates only when a safe fetcher is available.
9. Stage local attachments and route them through the existing document intake pipeline.
10. Route body text as a note/document only when it has standalone value beyond being provenance.
11. Write one run record tying all outputs back to the source artifact, contained path, and message id when present.
12. Move the source artifact to processed only after packet success.
13. Move the source artifact to failed/quarantine when configured and processing fails.

The raw email body is runtime provenance and routing context by default. It becomes durable vault content only when the classifier decides the body itself is useful as a note/document. External articles linked from the email are durable source material and should be captured as vault source cards when consumed successfully.

## Link Analysis

Saved emails often contain links where the link is the real source, not the email. Link analysis must therefore be first-class.

The link classifier should separate:

- `article_resource`: web articles, posts, docs, papers, and pages suitable for URL ingest.
- `downloadable_file`: PDF, Office, image, audio, video, or archive URLs that can be treated as remote attachments when a safe fetcher exists.
- `internal_app`: mail, calendar, cloud-app, issue tracker, or local app URLs that should remain references unless a specific integration owns them.
- `unsupported_or_noisy`: tracking links, unsubscribe links, login redirects, empty links, and low-confidence URLs.

The consume run should report links found, articles captured, remote files consumed, and skipped links with reasons. Unsupported links should stay in run details and not pollute the vault.

## Provider Feeders

Provider feeders are explicitly out of scope for the v1 implementation, but the ADR leaves a clean path for them.

Future feeders may include:

- Apple Mail local helper: export messages from an `Augur` mailbox or smart mailbox into the mail drop folder.
- Gmail helper: export messages with label `Augur` into `.eml` files.
- Classic Outlook local helper: export messages with category `Augur` into `.msg` or `.eml` files.
- Microsoft Graph helper: export messages with category `Augur` into `.eml` files where the tenant permits Graph access.
- AI-agent-native Gmail/Outlook feeder: a connected AI client receives a user request such as "download all my Augur-marked email", uses its Gmail or Outlook connector to find the marked messages, writes supported artifacts into the mail drop folder, and optionally triggers Brain Inbox scan/consume.
- Bulk export feeders may write `.zip`, `.tgz`, `.mbox`, or `.pst` artifacts to the folder instead of one file per message.

These feeders all share the same contract: they only write files into the configured mail drop folder. Brain Inbox scan/consume remains unchanged.

## Aftercare

Folder-first aftercare is file aftercare, not mailbox aftercare.

After successful packet consume, Augur can:

- move the source file to `processed/`
- leave it in place and mark it consumed in the runtime ledger
- delete nothing by default

After a failed packet, Augur can:

- leave the file in place for retry
- move it to `failed/` with the run id in metadata

Provider mailbox aftercare, such as applying `Augur Consumed` in Gmail or Outlook, belongs to future provider feeder work and is outside this ADR.

## Wiki Compounding

Email Consume should default to marking wiki update needed. It should not run the full concept extraction and apply cycle inline.

The source material visible to wiki compounding is:

- captured article/resource source cards
- routed notes/documents from valuable body text
- routed attachments
- document extraction output

The email packet run record remains runtime provenance. It helps explain why sources arrived together, but it is not itself a compiled wiki page.

`Prepare Wiki Update` should be a visible follow-up action in `/brain/inbox`, using the existing `wiki-update` path. Compiled wiki pages must still be produced through the concept-first wiki flow and `wiki-apply-concept-batch`, not by hand-writing pages during email consume.

## Dashboard UX

`/brain/inbox` should include a Mail Drop source section beside watched folders.

Each mail drop source row should show:

- source name
- source path
- supported formats
- pending email file count
- archive/mailbox artifact count
- skipped/unsupported file count
- estimated attachment count
- article link count when available
- batch limit and ordering
- last scan time
- last consume status
- source health
- buttons: Scan, Consume, Prepare Wiki Update

Latest run details should show:

- processed email files
- processed archive/mailbox entries
- captured article links
- routed attachments
- routed body notes/documents
- skipped links and reasons
- skipped attachments and reasons
- parser failures by file
- file aftercare actions taken or blocked

This should feel like the same intake workflow as Desktop and Downloads, not a separate Apple, Gmail, or Outlook dashboard.

## Safety And Idempotency

Safety rules:

- Scan never mutates source files or vault state.
- Consume is idempotent by source artifact fingerprint, contained path/index, and message id when available.
- Attachments and article links get their own fingerprints so retries skip already-consumed items.
- The source file is only moved to processed after packet success.
- Partial success blocks processed-file aftercare unless the config explicitly allows partial aftercare.
- One failed file does not fail the whole chunk.
- Duplicate links and attachments are skipped with explicit reasons.
- Archive extraction rejects absolute paths, parent-directory traversal, symlinks, and entries above configured size/count limits.
- Unsupported links are retained in runtime run details only.
- Permission and parser failures are source health errors, not empty-success results.
- Raw source email files are never permanently deleted by default.

## Error Handling

Run records should support partial success and file/link/message-level failures.

Each packet item result should include:

- source file path
- archive/container path when applicable
- contained entry path or message ordinal when applicable
- source message id when available
- packet item type
- source identifier or attachment name
- output path or source-card path when applicable
- status
- stage
- error
- skipped reason
- wiki relevance
- aftercare eligibility

Dashboard notices should distinguish source health failures, scan failures, consume partial success, and file aftercare blocked by packet failures.

## Testing

Core tests should be deterministic and fixture-based:

- mail drop source registry create/list/update behavior
- scan contract for folders with `.eml`, `.msg`, `.oft`, `.mbox`, Apple `.mbox` bundles, `.pst`, archives, degraded exports, unsupported files, duplicates, and malformed files
- packet extraction from plain text, HTML, links, and attachments
- archive safety checks for zip-slip/path traversal, excessive file counts, and size limits
- link classification
- URL ingest capture candidate creation for article links
- attachment routing through the document intake interface
- idempotency on repeated files, message ids, and fingerprints
- file aftercare blocking on partial success
- run history serialization
- dashboard MCP calls and visible counts/actions

Provider feeder behavior should be tested in separate provider-specific ADRs or plans. This ADR only tests that already-saved email files are consumed correctly.

## Phasing

### Phase 1: Local Mail Drop Folder

- Add typed mail drop sources to Brain Inbox runtime state.
- Add artifact parser interfaces for `.eml`, `.msg`, `.oft`, `.mbox`, Apple `.mbox` bundles, `.pst`, archive containers, and degraded document exports with fixture-backed tests.
- Add MCP tools for source list/add/scan/consume.
- Process chunks of 5 by default.
- Route article links through URL ingest capture.
- Route attachments through document intake.
- Mark wiki update needed.
- Add dashboard Mail Drop section.
- Record run history and block processed-file aftercare on partial success.

### Phase 2: Optional Provider Feeders

- Apple Mail feeder writes selected mailbox/smart-mailbox messages to the mail drop folder.
- Gmail feeder writes labelled `Augur` messages to the mail drop folder.
- Classic Outlook feeder writes categorized `Augur` messages to the mail drop folder.
- Microsoft Graph feeder writes categorized `Augur` messages to the mail drop folder where tenant policy allows it.
- AI-agent-native Gmail/Outlook feeder writes user-requested marked messages to the mail drop folder when the active AI client has the needed mailbox connector and file-write path.
- Feeders do not change the Brain Inbox consume contract.

### Phase 3: Stronger Compounding Controls

- Add source-level wiki mode controls.
- Add richer link policy controls.
- Show email-derived source clusters in Brain Insights.
- Support scoped Prepare Wiki Update from recent email runs if the broader wiki backlog makes that useful.

## Open Implementation Notes

- The first implementation should not require Apple, Gmail, Outlook, or Microsoft Graph integration skills.
- Apple, Google Workspace, Outlook, Microsoft Graph, and AI-agent-native mailbox skills may remain active private/client capabilities when they become useful. They do not have to become core Augur skills unless the product intentionally ships provider automation as a shared feature.
- The agent-native flow works only if the active AI client can both read the relevant mailbox and write supported email artifacts into the configured local or synced mail drop folder. If a connector can only summarize messages but cannot export files, a feeder must add the missing export/write step before Brain Inbox consume can run.
- Windows users who cannot get IT approval can still use the folder-first path by saving or dragging emails into the local mail drop folder.
- New Outlook for Windows should not be assumed to expose a reliable local automation API. Classic Outlook COM and Microsoft Graph are optional feeder paths, not v1 blockers.
- The current Brain Inbox folder consume already marks wiki updates and stores run history. Email intake should reuse that mental model and extend the store carefully rather than duplicating a separate run system.
- The implementation must keep dashboard execution MCP-based. Dashboard code calls MCP tools and must not run local scripts directly.
