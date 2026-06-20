---
title: How should Plugin, Client, And Skill Distribution Governance be used?
summary: Guidance for architecture questions about skill packaging, registries, plugin
  packs, and client projections.
tags:
- how-should-plugin-client-and-skill-distribution-governance-be-used
- plugin-client-and-skill-distribution-governance
- query
- command
- plugin
- client
- skill
- distribution
related:
- '[[plugin-client-and-skill-distribution-governance]]'
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
- adr:adrs/ADR-008-plugin-system.md
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
source_fingerprint: 51303ee91ec2a15d10ab41f60b278d4b6423faacabed3acd5145e091314aafeb
sources:
- adr:adrs/ADR-008-plugin-system.md
updated: '2026-05-03T13:17:12Z'
_cites:
- '[[adr:adrs/ADR-008-plugin-system.md]]'
_mentions:
- '[[concepts/platform-admin-and-skill-quality-commands]]'
- '[[concepts/plugin-client-and-skill-distribution-governance]]'
_relates_to:
- '[[client]]'
- '[[command]]'
- '[[distribution]]'
- '[[plugin-client-and-skill-distribution-governance]]'
- '[[plugin]]'
- '[[query]]'
- '[[skill]]'
---


# How should Plugin, Client, And Skill Distribution Governance be used?

## Summary

Guidance for architecture questions about skill packaging, registries, plugin packs, and client projections.

## Answer

Use this concept when the issue is not one command failing but the way a capability is packaged and exposed across clients. Reach for it when deciding where a contract belongs, how a client wrapper should be generated, how lifecycle or scoring gates should work, or how managed state should be separated from user-owned client state. If the problem is operational verification or merge safety, route next to [[concepts/platform-admin-and-skill-quality-commands]].

## Evidence

- `adr:adrs/ADR-008-plugin-system.md`: Augur had 39 skills spread across `plugins/{factory,vertical,services}/` directories, each with SKILL.

## Related

- [[concepts/plugin-client-and-skill-distribution-governance]]
