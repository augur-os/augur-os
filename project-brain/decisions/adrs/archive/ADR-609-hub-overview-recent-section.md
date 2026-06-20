---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-609: Hub Overview Recent Section

## Decision summary

Add a hub-agnostic `RecentSection` component to `HubOverviewPage` slotted between Tools and Notes. Show the latest notes and documents from all skills in the hub, sorted by modification time, capped at 10 items overall and 2 per skill. Implement a new MCP tool `list-hub-recent-files` that reads...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
