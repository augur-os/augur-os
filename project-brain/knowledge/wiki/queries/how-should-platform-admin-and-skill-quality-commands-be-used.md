---
title: How should Platform Admin And Skill Quality Commands be used?
summary: Guidance for build-debug-merge, release, migration, and skill-quality command
  routing.
tags:
- how-should-platform-admin-and-skill-quality-commands-be-used
- platform-admin-and-skill-quality-commands
- query
- adaptive
- platform
- admin
- skill
- quality
related:
- '[[platform-admin-and-skill-quality-commands]]'
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
- command:skills/auto-skill-quality/commands/auto-seed-data.md
_source_fingerprint:
- '0'
- '1'
- '2'
- '3'
- '4'
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
source_fingerprint: 12af98d3f0a73f7a0df8a003a7bcd6164eff2e7839179a8dbbd33861931cae68
sources:
- command:skills/auto-skill-quality/commands/auto-seed-data.md
updated: '2026-05-03T13:17:12Z'
_cites:
- '[[command:skills/auto-skill-quality/commands/auto-seed-data.md]]'
_mentions:
- '[[concepts/platform-admin-and-skill-quality-commands]]'
_relates_to:
- '[[adaptive]]'
- '[[admin]]'
- '[[platform-admin-and-skill-quality-commands]]'
- '[[platform]]'
- '[[quality]]'
- '[[query]]'
- '[[skill]]'
---


# How should Platform Admin And Skill Quality Commands be used?

## Summary

Guidance for build-debug-merge, release, migration, and skill-quality command routing.

## Answer

Use this family when the task changes repository state in a coordinated way. Start here for `dev-build`, `dev-debug`, `dev-merge`, release staging or porting, migration safety, code review, coverage analysis, or skill-quality repair. These commands are for administrative control and verified change management, not just passive inspection. If the immediate need is proof, choose testing loops first; if the problem is runtime diagnosis, choose observability or daemon maintenance surfaces.

## Evidence

- `command:skills/auto-skill-quality/commands/auto-seed-data.md`: Run the absorbed seed-data hardening loop under `auto-skill-quality`.

## Related

- [[concepts/platform-admin-and-skill-quality-commands]]
