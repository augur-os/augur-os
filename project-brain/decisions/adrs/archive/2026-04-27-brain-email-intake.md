# Brain Email Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build folder-first Brain Inbox email intake. Augur consumes already-saved mail artifacts from a local mail drop folder, including `.eml`, `.msg`, `.oft`, `.mbox`, Apple `.mbox` bundles, `.pst`, and archives such as `.zip`, `.tgz`, `.tar`, and `.tar.gz` that contain email artifacts. It routes body text, links, and attachments through existing ingest/document/wiki paths and records useful run history. Provider-specific capture from Gmail, Apple Mail, Outlook, Microsoft Graph, or AI-agent-native mailbox connectors is feeder work outside the core Brain Inbox consume implementation.

**Architecture:** Add mail-drop source, parser, packet, run, store, link-classifier, and consume modules under `shared-vault/skills/ingest/scripts/`. Register MCP tools from `shared-vault/skills/ingest/scripts/mcp/ingest_tools.py`, then extend `/brain/inbox` to show mail drop sources beside watched folders. Keep dashboard execution MCP-only and keep durable routing in the ingest layer.

**Tech Stack:** Python dataclasses/pytest for ingest tools, Python stdlib `email` and `mailbox` parsing for `.eml`/`.mbox`, zip/tar archive handling with traversal guards, dependency-isolated `.msg`/`.oft`/`.pst` adapters, Next.js/React dashboard tests, existing MCP client helpers, existing URL ingest, document intake, RAG, and wiki flag patterns.

---

## Scope

In scope:

- Local mail drop source configuration.
- Scan and consume for `.eml`, `.msg`, `.oft`, `.mbox`, Apple `.mbox` bundles, `.pst`, and archive files already present on disk.
- Degraded intake for `.pdf`, `.txt`, `.html`, `.htm`, `.mht`, and `.mhtml` exports when full email metadata cannot be recovered.
- Body/link/attachment packet parsing.
- URL ingest for article links.
- Document intake for attachments.
- File aftercare: move to processed or failed folders.
- Brain Inbox dashboard visibility and actions.

Out of scope:

- Apple Mail automation that exports emails to the folder.
- Gmail CLI/API automation that exports labelled messages to the folder.
- Outlook Classic COM automation that exports categorized messages to the folder.
- Microsoft Graph authentication or tenant-approved mailbox access.
- AI-agent-native Gmail/Outlook automation that reads marked mail through a connected client and writes supported artifacts to the folder.
- Applying provider-side labels/categories such as `Augur Consumed`.

Provider feeders can be added later without changing the folder consume contract.

---

## File Structure

- Create `shared-vault/skills/ingest/scripts/email_drop_models.py`: dataclasses for mail drop sources, scan summaries, packet items, and run records.
- Create `shared-vault/skills/ingest/scripts/email_drop_store.py`: JSON persistence for mail drop sources and runs under `get_runtime_dir() / "brain" / "inbox"`.
- Create `shared-vault/skills/ingest/scripts/email_artifact_parser.py`: parser interface plus `.eml`, `.msg`, `.oft`, `.mbox`, Apple `.mbox` bundle, `.pst`, archive, and degraded document parser implementations.
- Create `shared-vault/skills/ingest/scripts/email_link_classifier.py`: deterministic URL extraction and classification, reusable for future provider feeders.
- Create `shared-vault/skills/ingest/scripts/email_drop_consume.py`: scan and consume orchestration, idempotency, link capture, attachment/body routing, wiki flagging, and file aftercare gating.
- Modify `shared-vault/skills/ingest/scripts/mcp/ingest_tools.py`: register `email-drop-sources`, `email-drop-scan-source`, `email-drop-consume-source`, and include mail drop data in Brain Inbox responses.
- Modify `shared-vault/skills/ingest/SKILL.md`: document new MCP tools.
- Create tests under `shared-vault/skills/ingest/augur/tests/` for models/store, parsers, link classification, consume orchestration, and MCP tools.
- Modify `apps/dashboard/features/pages/brain/inbox/types.ts`: add mail drop source/summary types.
- Modify `apps/dashboard/features/pages/brain/inbox/hooks.ts`: query mail drop sources and call email drop MCP tools.
- Modify `apps/dashboard/features/pages/brain/inbox/page.tsx`: render the Mail Drop section with Scan, Consume, and Prepare Wiki Update.
- Modify `tests/dashboard/brain/inbox-page.test.tsx`: dashboard behavior for mail drop sources.
- Modify dashboard visual smoke fixtures only if the affected Brain Inbox route needs mocked MCP responses.
- Regenerate dashboard MCP/registry outputs only if local generator checks require it.

---

### Task 1: Mail Drop Models And Store

**Files:**
- Create: `shared-vault/skills/ingest/scripts/email_drop_models.py`
- Create: `shared-vault/skills/ingest/scripts/email_drop_store.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_email_drop_store.py`

- [ ] Write failing tests for default source creation, scan state persistence, run history persistence, and forward-compatible JSON reads.
- [ ] Implement dataclasses for source config, batch settings, aftercare settings, counts, packet item results, and run records.
- [ ] Implement a JSON file store under the Brain Inbox runtime directory.
- [ ] Ensure source paths are stored as configured values but resolved through path helpers at execution time.
- [ ] Verify unsupported future fields are ignored rather than crashing older clients.
- [ ] Run the focused store tests through the repo's auto-test path.

Acceptance:

- A default Mail Drop source can be created.
- Scan counts and health state persist.
- Run history records body/link/attachment item results.
- No hardcoded user-local path appears in the implementation.

---

### Task 2: Email Artifact Parsers

**Files:**
- Create: `shared-vault/skills/ingest/scripts/email_artifact_parser.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_email_artifact_parser.py`
- Fixtures: `shared-vault/skills/ingest/augur/tests/fixtures/email/`

- [ ] Add `.eml` fixtures covering plain text, HTML, links, and attachments.
- [ ] Add `.msg` and `.oft` fixtures or minimal parser fixture abstractions that can be exercised without Outlook installed.
- [ ] Add `.mbox` fixtures and Apple `.mbox` bundle directory fixtures.
- [ ] Add `.pst` fixtures or a dependency-isolated adapter fixture so tests can validate control flow without requiring Outlook.
- [ ] Add `.zip`, `.tgz`, `.tar`, and `.tar.gz` fixtures containing nested `.eml`, `.msg`, `.mbox`, unsupported files, and traversal attempts.
- [ ] Add degraded `.pdf`, `.txt`, `.html`, `.htm`, `.mht`, and `.mhtml` fixtures.
- [ ] Write failing tests for metadata extraction, body extraction, link extraction input, attachment staging, archive manifest scanning, malformed files, degraded inputs, and unsupported file formats.
- [ ] Implement parser selection by extension and directory bundle shape.
- [ ] Implement `.eml` parsing with Python's standard email parser.
- [ ] Implement `.mbox` parsing with Python's mailbox support where possible.
- [ ] Implement Apple `.mbox` bundle parsing by discovering the contained mailbox file(s) without assuming one fixed internal filename.
- [ ] Implement archive expansion into runtime staging with zip-slip/path traversal, symlink, size, and file-count guards.
- [ ] Implement `.msg`, `.oft`, and `.pst` parsing behind small adapters so dependencies can be swapped or skipped cleanly where unavailable.
- [ ] Implement degraded document extraction for `.pdf`, `.txt`, `.html`, `.htm`, `.mht`, and `.mhtml` using existing document extraction where practical.
- [ ] Return structured packet data rather than raw parser objects.

Acceptance:

- Email-native artifacts produce the same normalized packet shape.
- Archive artifacts preserve source archive and contained-entry provenance.
- Degraded exports produce document-like packets with partial metadata clearly marked.
- Malformed or unsupported files produce explicit skip/failure reasons.
- Attachments are staged into a controlled temporary directory, not the project root.

---

### Task 3: Link Classification

**Files:**
- Create or update: `shared-vault/skills/ingest/scripts/email_link_classifier.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_email_link_classifier.py`

- [ ] Write failing tests for article/resource links, downloadable files, internal/app links, tracking/noisy links, duplicates, and empty links.
- [ ] Implement deterministic URL extraction from plain text and HTML-derived text.
- [ ] Classify links into `article_resource`, `downloadable_file`, `internal_app`, and `unsupported_or_noisy`.
- [ ] Preserve skipped links with reasons in run details.

Acceptance:

- Useful links are promoted to URL ingest candidates.
- Noisy links are visible in run details but do not pollute the vault.

---

### Task 4: Consume Orchestration

**Files:**
- Create: `shared-vault/skills/ingest/scripts/email_drop_consume.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_email_drop_consume.py`

- [ ] Write failing tests for scan preview, successful consume, partial consume, archive-contained consume, degraded document consume, idempotent retry, duplicate links/attachments, and file aftercare blocking.
- [ ] Implement scan without mutations.
- [ ] Implement consume in configurable chunks, default 5.
- [ ] Fingerprint source artifacts, contained entries, and packet items.
- [ ] Route article/resource links through the existing URL ingest path.
- [ ] Route attachments through existing document intake.
- [ ] Route body text only when it has standalone value.
- [ ] Mark wiki update needed when any useful source material is routed.
- [ ] Move source files to processed only after packet success.
- [ ] Move failed files to failed/quarantine only when configured.
- [ ] Record run history with clear per-file and per-item status.

Acceptance:

- Scan never changes files or indexes.
- Consume is retry-safe.
- One bad email file does not fail the whole batch.
- Partial success is visible and blocks processed-file aftercare by default.

---

### Task 5: MCP Tools

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/ingest_tools.py`
- Modify: `shared-vault/skills/ingest/SKILL.md`
- Test: `shared-vault/skills/ingest/augur/tests/test_email_drop_mcp.py`

- [ ] Add failing MCP registration tests for `email-drop-sources`, `email-drop-scan-source`, and `email-drop-consume-source`.
- [ ] Implement `email-drop-sources` to list configured mail drop sources and latest run summaries.
- [ ] Implement `email-drop-scan-source` as preview-only.
- [ ] Implement `email-drop-consume-source` as the mutation path.
- [ ] Include mail drop source summaries in the existing Brain Inbox response if that is the established local pattern.
- [ ] Document the tools in `shared-vault/skills/ingest/SKILL.md`.

Acceptance:

- Dashboard can retrieve source data through MCP only.
- Tools return useful errors for missing folders, permission problems, malformed files, unsafe archives, degraded metadata, and unsupported formats.
- No dashboard code directly reads local files.

---

### Task 6: Brain Inbox Dashboard

**Files:**
- Modify: `apps/dashboard/features/pages/brain/inbox/types.ts`
- Modify: `apps/dashboard/features/pages/brain/inbox/hooks.ts`
- Modify: `apps/dashboard/features/pages/brain/inbox/page.tsx`
- Test: `tests/dashboard/brain/inbox-page.test.tsx`

- [ ] Add failing dashboard tests for rendering Mail Drop sources.
- [ ] Add tests for Scan, Consume, and Prepare Wiki Update actions.
- [ ] Add types for mail drop source summaries and run status.
- [ ] Wire hooks to MCP tools.
- [ ] Render a Mail Drop section beside watched folders.
- [ ] Show path, pending files, archive/mailbox artifacts, degraded inputs, supported formats, attachments, links, health, last scan, and last consume.
- [ ] Keep UI copy concise and operational.

Acceptance:

- The Brain Inbox page shows useful data for the mail drop folder.
- Buttons call MCP tools and surface success, partial success, and error notices.
- No direct local filesystem or process execution exists in dashboard code.

---

### Task 7: Verification And Browser Smoke

**Files:**
- Modify dashboard visual fixtures only if needed by the changed route.

- [ ] Run focused ingest tests through the repo auto-test path.
- [ ] Run focused dashboard tests through the repo auto-test path.
- [ ] Run dashboard typecheck/build gates through the repo's auto-loop path.
- [ ] If any dashboard UI changed, verify `/brain/inbox` in a real browser or screenshot-capable browser tool.
- [ ] Verify the page shows non-placeholder Mail Drop data from mocked or fixture-backed MCP responses.
- [ ] Verify no generated registry drift remains unless intentionally regenerated.

Acceptance:

- Tests cover parser, consume, MCP, and dashboard behavior.
- Browser verification proves the page mounts interactively and displays useful Mail Drop data.

---

## Provider Feeder Follow-Ups

Provider feeders should be separate ADRs or later implementation plans.

Potential follow-ups:

- Apple Mail feeder: export selected `Augur` mailbox or smart mailbox messages into the mail drop folder.
- Gmail feeder: export labelled `Augur` messages into `.eml`, `.mbox`, `.zip`, or `.tgz` artifacts.
- Classic Outlook feeder: export categorized `Augur` messages into `.msg`, `.eml`, `.pst`, or rendered fallback files using local Outlook profile automation.
- Microsoft Graph feeder: export categorized `Augur` messages where tenant policy allows Graph access.
- AI-agent-native Gmail/Outlook feeder: let a connected client such as Gemini find user-requested `Augur`-marked messages, export supported mail artifacts into the configured mail drop folder, and optionally trigger Brain Inbox scan/consume.
- Bulk export feeder: move downloaded provider archives into the mail drop folder without unpacking them first.

All feeders must obey the same boundary: they write mail artifacts into the configured folder and do not change the Brain Inbox consume contract.

---

## Final Verification

- [ ] Store/model tests pass.
- [ ] Parser tests pass for `.eml`, `.msg`, `.oft`, `.mbox`, Apple `.mbox` bundles, `.pst`, archives, degraded exports, malformed, unsupported, and attachment cases.
- [ ] Consume orchestration tests pass.
- [ ] MCP registration and behavior tests pass.
- [ ] Dashboard tests pass.
- [ ] Typecheck/build gates pass through the repo's auto-loop commands.
- [ ] Browser verification passes for `/brain/inbox` if UI files changed.
- [ ] Documentation explains that provider and AI-agent-native capture into the folder is feeder work outside the core consume implementation.

---

## Self-Review Notes

- Spec coverage: folder-first source, individual message files, mailbox bundles, provider archive downloads, degraded document exports, packet consume, link analysis, attachment/body routing, file aftercare, wiki mark-needed flow, dashboard UX, safety/idempotency, error handling, tests, and phasing.
- Scope boundary: provider-specific and AI-agent-native capture are explicitly feeder work outside the core consume implementation. This keeps v1 local, simple, and independent of Augur owning IT approval or provider auth.
- Windows risk: `.msg`/`.oft`/`.pst` parsing must be fixture-backed and dependency-isolated. New Outlook local automation is not assumed.
- Integration risk: dashboard must remain MCP-only, and the ingest layer must reuse existing document, URL ingest, RAG, and wiki paths.
