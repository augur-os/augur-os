---
title: Open-Source Brain Inbox and Wiki Insights Design
date: 2026-04-24
status: proposed
scope: design
---

# Open-Source Brain Inbox and Wiki Insights Design

## Purpose

Augur's open-source first-use journey should serve a local knowledge worker who wants a personal app that turns messy local folders, files, and reflective chats into organized knowledge, searchable context, cross-source insights, and next actions.

The first release should optimize for a concrete outcome: a user adds folders such as Desktop or Downloads, clicks **Consume**, and Augur automatically organizes files, extracts useful content, updates search/wiki inputs, and explains what changed.

## User Journey

1. The user opens the Brain hub and sees Inbox as a clear starting point.
2. The user adds local folders such as Desktop, Downloads, or any folder they choose.
3. Each folder row shows new files, likely documents, duplicates or trash candidates, last scan, last consume run, and last purge run.
4. The user clicks **Consume**.
5. Augur scans the folder, deeply understands files, classifies destinations, renames files, routes them into Augur-managed vault/documents locations, indexes RAG, marks or runs wiki compounding work, and writes an activity record.
6. The result view explains the value in user terms: moved files, indexed files, new or strengthened insights, next actions, files skipped, and failures needing attention.
7. The user clicks **Purge to Trash** when they want cleanup. Augur sends disposable or duplicate files to the OS trash, never permanently deletes them, and records what happened.

The product promise is not "files were processed." The promise is: **drop messy local files into Augur and get organized knowledge, searchability, new insights, and next actions.**

## Product Shape

The recommended shape is **Inbox Command Center with an insight payoff**.

The primary Brain page should route users toward Inbox when folders need attention and toward Insights when Augur has learned something new. `/brain/inbox` is the first-use action surface. `/brain/insights` is the payoff surface: what Augur inferred, what changed in the wiki, and what the user should do next.

This should avoid a dense expert workbench for the first release. A unified workbench can come later after the user journey is proven.

## Architecture

### Folder Registry

Add an MCP-backed folder registry for user-configured inbox folders.

Each folder record should include:

- folder id
- display name
- absolute path
- enabled state
- safety settings
- last scan time
- last consume run id
- last purge run id
- aggregate counts from the latest scan

The registry must use Augur path helpers and external runtime/vault storage. It must not hardcode local machine paths.

### Consume Pipeline

Promote folder consume into a first-class MCP workflow instead of relying only on ambient import internals.

The pipeline should run:

`folder -> scan -> extraction and understanding -> classification -> route and rename -> RAG reindex -> wiki update flag or batch -> insights and actions summary -> activity log`

The implementation should reuse existing building blocks where possible:

- `TrackedFolderScanner`
- `IngestPipeline`
- `ambient_import_worker`
- `document_understanding`
- `document-extractor`
- `unified_indexer`
- wiki status/update/apply tools

The new behavior is the product workflow and run record around those pieces.

### Deep File Understanding

Binary and rich documents must produce structured understanding, not only body text.

For PDFs, images, Office files, spreadsheets, audio where supported, and other indexable documents, the result should include:

- document kind
- title
- summary
- key sections
- key insights
- action candidates
- extraction method
- extraction confidence
- OCR or visual assistance status
- LLM assistance status when used
- extraction errors or low-signal warnings

Escalation should remain need/complexity based. Large files should not escalate only because they are large; weak extraction, scanned/visual complexity, or missing structure should drive escalation.

### Wiki And Insight Compiler

Every consume run should answer: **what is new because these files were seen together?**

The run summary should surface:

- new or strengthened wiki concepts
- cross-source patterns
- contradictions or tensions
- missing context
- practical next actions
- source coverage changes
- pending wiki update state

Compiled wiki pages must remain concept-first articles. The consume pipeline should create or update source material and trigger concept-first wiki compounding. It must not hand-write compiled wiki pages under `wiki/concepts/` or `wiki/queries/`.

### Chat And Interaction Compounding

`/ask` and chat retention should stay conversational and silent by default. Retained outcomes already mark the wiki update flag; the Brain Insights page should expose the resulting operational state without turning chat into a logging UI.

Brain Insights should show:

- pending wiki update flag
- recent retained syntheses
- retained ask clusters waiting for compounding
- last applied wiki batch
- source families with low coverage
- actions recommended by wiki status

Session-end hooks remain a safety net, but the product should also make the state visible and actionable.

## Brain UI

### `/brain/inbox`

The Inbox page should include:

- add folder control
- watched folder list
- folder health and count summaries
- primary **Consume** action per folder
- **Purge to Trash** action per folder
- recent run activity
- per-run details
- failed file list
- open destination or reveal actions
- undo/restore affordance where supported by the activity log

Consume should be the primary action. Purge to Trash should be explicit and secondary.

### `/brain/insights`

The Insights page should include:

- new cross-source insights
- next actions
- wiki health metrics
- pending wiki update status
- source coverage
- recent file/chat signals
- latest consume run insight summary
- main action: **Run Wiki Update** when wiki status recommends it

This page should show real MCP-backed data. It should not be a placeholder or proof-of-life page.

### Brain Overview

The Brain overview should become a routing surface:

- show Inbox when folders have new files or recent failures
- show Insights when new insights, next actions, or wiki update work exists
- preserve Memory/Profile/Workspace links without nesting Brain pages inside tabs

## Browse Wiki Hardening

The Browse wiki category should follow the quality direction already applied to Skills cards.

Wiki cards should show:

- cleaned semantic tags, not generic `wiki` or `concept` noise
- page type tag: concept, query, overview
- source density or source count when available
- quality/status tag when available
- freshness or modified date when useful
- one context-aware primary action
- overflow actions for lower-frequency operations

Primary action rules:

- concept/query page with path: **Open**
- page with rewrite debt: **Review**
- wiki backlog state: **Update Wiki**
- source-linked item: **Open Source**

Overflow actions should include appropriate choices such as Reveal in Finder, Copy Path, Open Source, Run Rewrite, Reindex Wiki, and Search Related.

The Browse wiki description should be corrected away from "Auto-generated AI summary pages and knowledge digests." A better label is: **Compiled concept pages and reusable answers from Augur knowledge sources.**

## Safety Model

The default consume model is fully automatic after the user clicks **Consume**.

Safety rules:

- files are never permanently deleted
- Purge sends files to OS trash
- active downloads are skipped
- directories are skipped by purge
- recently modified files are skipped by purge
- unsupported files are skipped by purge
- valuable or ambiguous files are skipped from purge
- failed extraction does not cause deletion or routing
- one failed file does not fail the whole consume run
- all moves, renames, trash operations, and skips are logged

Consume can move and rename files automatically. The activity log and destination paths are the audit surface.

## Error Handling

Consume runs should support partial success.

File-level failures should record:

- source path
- stage
- error
- whether the source was moved
- whether extracted markdown was written
- whether RAG indexing happened
- whether wiki work was marked pending

Wiki compounding failure must not roll back file organization or RAG indexing. It should leave a visible pending update state in Brain Insights.

RAG indexing failure should not roll back file movement. It should mark the run as partially successful and show retry/reindex actions.

Purge failures should leave the file in place and record the OS trash error.

## Data Contracts

### Folder Record

```json
{
  "id": "downloads",
  "name": "Downloads",
  "path": "/Users/example/Downloads",
  "enabled": true,
  "last_scan_at": "2026-04-24T10:00:00Z",
  "last_consume_run_id": "run_123",
  "last_purge_run_id": "purge_456",
  "counts": {
    "new_files": 12,
    "document_candidates": 9,
    "trash_candidates": 3,
    "failed": 0
  }
}
```

### Consume Run Record

```json
{
  "id": "run_123",
  "folder_id": "downloads",
  "started_at": "2026-04-24T10:01:00Z",
  "completed_at": "2026-04-24T10:03:00Z",
  "status": "partial_success",
  "files_seen": 12,
  "files_moved": 9,
  "files_indexed": 9,
  "files_skipped": 2,
  "files_failed": 1,
  "wiki_update_marked": true,
  "wiki_batch_created": false,
  "insights": [
    {
      "title": "Insurance paperwork is accumulating in health documents",
      "summary": "Two recent PDFs and one scan point to the same reimbursement workflow.",
      "sources": ["file_a.pdf", "file_b.pdf", "scan_c.png"],
      "next_actions": ["Review missing claim receipt"]
    }
  ]
}
```

### File Result

```json
{
  "source_path": "/Users/example/Downloads/Form 17.pdf",
  "final_path": "/Users/example/Documents/Augur/health/maccabi-form-17.pdf",
  "extracted_markdown_path": "/Users/example/Documents/Augur/health/maccabi-form-17.extracted.md",
  "content_type": "pdf",
  "document_kind": "medical_form",
  "extraction_method": "document-extractor:1",
  "extraction_confidence": "medium",
  "ocr_applied": true,
  "llm_assisted": true,
  "route": "health",
  "renamed_to": "2026-04-24-maccabi-form-17.pdf",
  "rag_indexed": true,
  "wiki_relevant": true,
  "status": "success"
}
```

## MCP Surface

Add or harden MCP tools around:

- `inbox-folders` for list/add/update/remove folders
- `inbox-scan-folder` for scan preview
- `inbox-consume-folder` for automatic consume
- `inbox-purge-folder` for OS trash cleanup
- `inbox-run-history` for activity log
- `inbox-run-detail` for per-run and per-file results
- `brain-insights` for insight summaries, wiki status, retained interaction signals, and next actions

Dashboard components must call these through `POST /api/mcp/tool` and MCP hooks. They must not directly run local scripts, `fs`, `spawn`, or `exec`.

## Verification Plan

Backend tests:

- folder registry CRUD
- scan counts and missing-folder behavior
- consume run dry-run and full-run records
- move/rename collision handling
- extraction confidence and binary understanding fields
- failed extraction partial success
- RAG reindex invocation
- wiki update flag and batch handoff
- OS trash abstraction with test double
- purge exclusions
- activity log persistence

Frontend tests:

- Brain Inbox empty, configured, running, success, partial-success, failure states
- Brain Insights pending wiki update, clean wiki, retained chat signals, and no-data states
- Browse wiki card tags/actions
- Brain overview routing cards

Live verification:

- `/brain/inbox`
- `/brain/insights`
- `/brain`
- `/browse?category=wiki`
- mobile-width screenshots for new Brain pages
- real MCP-backed data visible after load
- no console errors
- all visible buttons produce a useful outcome or clear error

## Deferred Work

The first implementation should not include:

- permanent delete
- daemon-based live file watching
- background auto-consume without a user click
- complex per-folder policy DSL
- full graph visualization
- cloud sync
- multi-user folder sharing

These can be added after the click-to-consume journey is proven.

## Open-Source Release Impact

This design raises user value for open-source users because it gives them:

- an immediate local workflow they understand
- a safe way to clean Downloads/Desktop
- a visible outcome after every run
- deep extraction for real-world binary files
- a wiki that provides synthesis across sources instead of summaries of individual files
- confidence that chats and files compound into the same long-term knowledge layer

It also gives evaluators a credible technical story: local-first file handling, MCP-backed dashboard actions, reusable ingest/extraction/RAG/wiki primitives, and visible quality/status surfaces.
