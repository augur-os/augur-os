---
title: How should Autonomous Maintenance And Repair Actions be used?
summary: Guidance for using action-layer repair and cleanup workflows.
tags:
- how-should-autonomous-maintenance-and-repair-actions-be-used
- autonomous-maintenance-and-repair-actions
- query
- command
- autonomous
- maintenance
- repair
- actions
related:
- '[[autonomous-maintenance-and-repair-actions]]'
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
- action:skills/daemon/augur/actions/auto-security-scan-overview.md
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
source_fingerprint: 1039adc7352a054c6215b54f528c3c726bbfff72a020e4ecf7e0123191e3c0ef
sources:
- action:skills/daemon/augur/actions/auto-security-scan-overview.md
updated: '2026-05-03T13:17:12Z'
_cites:
- '[[action:skills/daemon/augur/actions/auto-security-scan-overview.md]]'
_mentions:
- '[[concepts/autonomous-maintenance-and-repair-actions]]'
_relates_to:
- '[[actions]]'
- '[[autonomous-maintenance-and-repair-actions]]'
- '[[autonomous]]'
- '[[command]]'
- '[[maintenance]]'
- '[[query]]'
- '[[repair]]'
---


# How should Autonomous Maintenance And Repair Actions be used?

## Summary

Guidance for using action-layer repair and cleanup workflows.

## Answer

Use this concept when the user needs a repair-oriented workflow but not the underlying command syntax. These actions expose self-heal, security, skill hygiene, stale-reference cleanup, duplication cleanup, and general tidy/fix surfaces as stable operational entrypoints. If the issue needs deeper ownership or verification reasoning, step from here into the corresponding daemon, docs, or platform-admin command family.

## Evidence

- `action:skills/daemon/augur/actions/auto-security-scan-overview.md`: View the absorbed security-scan workflow from the consolidated daemon surface.

## Related

- [[concepts/autonomous-maintenance-and-repair-actions]]
