---
title: How should Runtime Control And Access Actions be used?
summary: Guidance for using action-layer runtime access and control surfaces.
tags:
- how-should-runtime-control-and-access-actions-be-used
- daemon-maintenance-command-loops
- knowledge-automation-command-loops
- platform-admin-and-skill-quality-commands
- runtime-control-and-access-actions
- query
- command
- runtime
related:
- '[[daemon-maintenance-command-loops]]'
- '[[knowledge-automation-command-loops]]'
- '[[platform-admin-and-skill-quality-commands]]'
- '[[runtime-control-and-access-actions]]'
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
- action:skills/augur-core/augur/actions/ask-overview.md
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
- '4'
- '5'
- '6'
- '7'
- ':'
- T
- Z
compiler_version: concept-article-v3
hub: command
page_type: query
source_fingerprint: 68228c0e4ae6ce87ded4bb410ecacfe3580f04f26a004b5666502cebf1900cc4
sources:
- action:skills/augur-core/augur/actions/ask-overview.md
updated: '2026-05-03T13:27:14Z'
_cites:
- '[[action:skills/augur-core/augur/actions/ask-overview.md]]'
_mentions:
- '[[concepts/daemon-maintenance-command-loops]]'
- '[[concepts/knowledge-automation-command-loops]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
- '[[concepts/runtime-control-and-access-actions]]'
_relates_to:
- '[[command]]'
- '[[daemon-maintenance-command-loops]]'
- '[[knowledge-automation-command-loops]]'
- '[[platform-admin-and-skill-quality-commands]]'
- '[[query]]'
- '[[runtime-control-and-access-actions]]'
- '[[runtime]]'
---


# How should Runtime Control And Access Actions be used?

## Summary

Guidance for using action-layer runtime access and control surfaces.

## Answer

Use this concept when the first need is visibility: ask what Augur knows, search indexed knowledge, inspect onboarding, check daemon or loop status, understand remote access, or route a document into extraction. These actions should orient the user before deeper repair or mutation. Once the boundary is clear, move into the relevant command family such as [[concepts/daemon-maintenance-command-loops]], [[concepts/knowledge-automation-command-loops]], or [[concepts/platform-admin-and-skill-quality-commands]].

## Evidence

- `action:skills/augur-core/augur/actions/ask-overview.md`: View reflective `/ask` workflows from augur-core.

## Related

- [[concepts/daemon-maintenance-command-loops]]
- [[concepts/knowledge-automation-command-loops]]
- [[concepts/platform-admin-and-skill-quality-commands]]
- [[concepts/runtime-control-and-access-actions]]
