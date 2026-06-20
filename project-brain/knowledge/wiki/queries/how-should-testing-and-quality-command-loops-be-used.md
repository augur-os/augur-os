---
title: How should Testing And Quality Command Loops be used?
summary: Operational guidance for choosing the right verification command family.
tags:
- how-should-testing-and-quality-command-loops-be-used
- testing-and-quality-command-loops
- query
- adaptive
- testing
- quality
- command
- loops
related:
- '[[testing-and-quality-command-loops]]'
created: '2026-04-23T10:19:48Z'
_page_type:
- e
- q
- r
- u
- y
_hub:
- a
- d
- e
- i
- p
- t
- v
_sources:
- command:skills/loop-quality/commands/auto-format.md
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
hub: adaptive
page_type: query
source_fingerprint: 7a8cded4086023fd3a55a51981ad0db860ec44e289ff114365f1e2c4f6060bd3
sources:
- command:skills/loop-quality/commands/auto-format.md
updated: '2026-05-03T13:17:12Z'
_cites:
- '[[command:skills/loop-quality/commands/auto-format.md]]'
_mentions:
- '[[concepts/operational-audit-and-observability-commands]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
- '[[concepts/testing-and-quality-command-loops]]'
_relates_to:
- '[[adaptive]]'
- '[[command]]'
- '[[loops]]'
- '[[quality]]'
- '[[query]]'
- '[[testing-and-quality-command-loops]]'
- '[[testing]]'
---


# How should Testing And Quality Command Loops be used?

## Summary

Operational guidance for choosing the right verification command family.

## Answer

Use this family to prove correctness in layers. Start with formatting, lint, YAML, and route-level checks when you need cheap signal, then move to API, MCP, build, Python, or dashboard tests as the blast radius grows. Finish with end-to-end command loops when the change touches real user workflows or write paths. If the problem is not verification but repository administration or runtime ownership, route to [[concepts/platform-admin-and-skill-quality-commands]] or [[concepts/operational-audit-and-observability-commands]].

## Evidence

- `command:skills/loop-quality/commands/auto-format.md`: Run Prettier formatting on source files.

## Related

- [[concepts/testing-and-quality-command-loops]]
