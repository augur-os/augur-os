---
status: Implemented
date: 2026-04-27
deciders:
  - Gur Sannikov
related: []
hub: brain
tags: []
superseded_by: null
spec_file: 2026-04-27-brain-email-intake-design.md
plan_file: 2026-04-27-brain-email-intake.md
---

# ADR-595: Brain Email Intake

> **ADR-595 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Use a folder-first Email Intake source model inside `/brain/inbox`: Augur consumes already-saved mail artifacts from a local mail drop folder, including individual messages, mailbox bundles, Outlook data exports, provider archive downloads, and files exported by connected AI-agent-native Gmail or Outlook workflows; provider-specific Apple, Gmail, and Outlook feeders remain optional follow-ups.

## Spec (canonical)

- [`docs/superpowers/specs/2026-04-27-brain-email-intake-design.md`](../superpowers/specs/2026-04-27-brain-email-intake-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-04-27-brain-email-intake.md`](../superpowers/plans/2026-04-27-brain-email-intake.md)

## Status notes

Accepted 2026-05-14 - refactored to a local mail drop folder v1. Apple, Gmail, Outlook, Microsoft Graph, and AI-agent-native capture into that folder are feeder paths rather than core Brain Inbox consume dependencies, so they no longer block the first implementation slice.

Implemented 2026-05-14 - delivered folder-first Mail Drop source/store/parser/consume/MCP/dashboard flow; real-data validation consumed a native `.eml` from the configured documents Mail Drop, wrote a vault source card, moved the source file to processed, and marked wiki update needed.

## Related

- None.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated: []
  files_affected: []
```
