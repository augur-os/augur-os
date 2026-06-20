---
title: How should Documentation And Repo Maintenance Commands be used?
summary: Guidance for path, docs, and repository-structure maintenance work.
tags:
- how-should-documentation-and-repo-maintenance-commands-be-used
- documentation-and-repo-maintenance-commands
- query
- adaptive
- documentation
- repo
- maintenance
- commands
related:
- '[[documentation-and-repo-maintenance-commands]]'
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
- command:skills/loop-docs/commands/auto-claude-md-audit.md
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
source_fingerprint: 8df6e257f1307ab0031b1e6a9db41aecd374c617f74ac0d9c610d5144b21051b
sources:
- command:skills/loop-docs/commands/auto-claude-md-audit.md
updated: '2026-05-03T13:17:12Z'
_cites:
- '[[command:skills/loop-docs/commands/auto-claude-md-audit.md]]'
_mentions:
- '[[concepts/documentation-and-repo-maintenance-commands]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
- '[[concepts/testing-and-quality-command-loops]]'
_relates_to:
- '[[adaptive]]'
- '[[commands]]'
- '[[documentation-and-repo-maintenance-commands]]'
- '[[documentation]]'
- '[[maintenance]]'
- '[[query]]'
- '[[repo]]'
---


# How should Documentation And Repo Maintenance Commands be used?

## Summary

Guidance for path, docs, and repository-structure maintenance work.

## Answer

Use this family when the problem is trust drift between the live system and the docs or repository layout around it. Reach for these commands after migrations, path changes, generated-surface rewires, or vault cleanup work. They help repair stale references, missing help coverage, frontmatter issues, and structural growth problems. If the task is primarily a test, build, release, or interactive debug flow, route instead to [[concepts/platform-admin-and-skill-quality-commands]] or [[concepts/testing-and-quality-command-loops]].

## Evidence

- `command:skills/loop-docs/commands/auto-claude-md-audit.md`: Validate instruction docs against actual project state.

## Related

- [[concepts/documentation-and-repo-maintenance-commands]]
