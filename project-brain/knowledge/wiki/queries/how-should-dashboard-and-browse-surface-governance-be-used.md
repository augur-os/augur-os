---
title: How should Dashboard And Browse Surface Governance be used?
summary: Guidance for architectural questions about dashboard composition, browse
  UX, and MCP-backed page boundaries.
tags:
- how-should-dashboard-and-browse-surface-governance-be-used
- dashboard-and-browse-surface-governance
- query
- command
- dashboard
- browse
- surface
- governance
related:
- '[[dashboard-and-browse-surface-governance]]'
created: '2026-04-23T10:46:56Z'
_page_type:
- e
- q
- r
- u
- y
_hub:
- a
- c
- d
- m
- n
- o
_sources:
- adr:adrs/ADR-450-template-driven-dashboard.md
_source_fingerprint:
- '0'
- '1'
- '2'
- '3'
- '4'
- '5'
- '6'
- '7'
- '8'
- '9'
- a
- b
- c
- d
- e
- f
_compiler_version:
- '-'
- '3'
- a
- c
- e
- i
- l
- n
- o
- p
- r
- t
- v
_updated:
- '-'
- '0'
- '1'
- '2'
- '3'
- '5'
- '6'
- '7'
- ':'
- T
- Z
compiler_version: concept-article-v3
hub: command
page_type: query
source_fingerprint: a35d4b34203eafa6a1ff72c8590c0f1eb97291bed3b2d9142e3e0008f2701af4
sources:
- adr:adrs/ADR-450-template-driven-dashboard.md
updated: '2026-05-03T13:17:12Z'
_cites:
- '[[adr:adrs/ADR-450-template-driven-dashboard.md]]'
_mentions:
- '[[concepts/dashboard-and-browse-surface-governance]]'
- '[[concepts/operational-audit-and-observability-commands]]'
_relates_to:
- '[[browse]]'
- '[[command]]'
- '[[dashboard-and-browse-surface-governance]]'
- '[[dashboard]]'
- '[[governance]]'
- '[[query]]'
- '[[surface]]'
---


# How should Dashboard And Browse Surface Governance be used?

## Summary

Guidance for architectural questions about dashboard composition, browse UX, and MCP-backed page boundaries.

## Answer

Use this concept when the problem concerns how information is presented, mounted, grouped, or fetched in the dashboard and browse surfaces. Start here when deciding whether a page belongs in YAML or TSX, whether a browse view is exposing the right inventory dimensions, or whether a route is failing because the tool boundary is wrong. For runtime audits after the architecture is chosen, connect to [[concepts/operational-audit-and-observability-commands]].

## Evidence

- `adr:adrs/ADR-450-template-driven-dashboard.md`: The current dashboard architecture couples UI pages to individual skills.

## Related

- [[concepts/dashboard-and-browse-surface-governance]]
