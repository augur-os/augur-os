---
title: How should Daemon Maintenance Command Loops be used?
summary: Routing guidance for daemon-owned maintenance and loop-control commands.
tags:
- how-should-daemon-maintenance-command-loops-be-used
- daemon-maintenance-command-loops
- query
- command
- daemon
- maintenance
- loops
related:
- '[[daemon-maintenance-command-loops]]'
created: '2026-04-23T10:19:48Z'
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
- command:skills/daemon/commands/auto-code-health.md
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
source_fingerprint: bbca6403ae9c98edfbe59096df725d4a2542a12b6d2d14265ea7de078a02ba8f
sources:
- command:skills/daemon/commands/auto-code-health.md
updated: '2026-05-03T13:17:12Z'
_cites:
- '[[command:skills/daemon/commands/auto-code-health.md]]'
_mentions:
- '[[concepts/daemon-maintenance-command-loops]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
_relates_to:
- '[[command]]'
- '[[daemon-maintenance-command-loops]]'
- '[[daemon]]'
- '[[loops]]'
- '[[maintenance]]'
- '[[query]]'
---


# How should Daemon Maintenance Command Loops be used?

## Summary

Routing guidance for daemon-owned maintenance and loop-control commands.

## Answer

Use this family when the job is to keep Augur's background runtime healthy rather than to debug one feature by hand. Start with daemon lifecycle or loop inspection commands to see which service or maintenance category owns the problem, then move into the specific hygiene loop for MCP naming, self-heal validation, repo sync, performance, or security. If the work is primarily an interactive build, release, or code-review task, route instead to [[concepts/platform-admin-and-skill-quality-commands]].

## Evidence

- `command:skills/daemon/commands/auto-code-health.md`: Unified code health monitoring — TypeScript build errors and API route health.

## Related

- [[concepts/daemon-maintenance-command-loops]]
