---
title: Autonomous Maintenance And Repair Actions
summary: Action surfaces that expose self-heal, stale-reference repair, skill hygiene,
  and absorbed maintenance workflows without dropping into raw commands.
tags:
- autonomous-maintenance-and-repair-actions
- daemon-maintenance-command-loops
- documentation-and-repo-maintenance-commands
- platform-admin-and-skill-quality-commands
- adaptive
- autonomous
- maintenance
- repair
aliases: []
related:
- '[[daemon-maintenance-command-loops]]'
- '[[documentation-and-repo-maintenance-commands]]'
- '[[platform-admin-and-skill-quality-commands]]'
created: '2026-04-23T10:46:56Z'
_page_type: concept
_hub: adaptive
_sources:
- action:skills/daemon/augur/actions/auto-security-scan-overview.md
- action:skills/daemon/augur/actions/auto-self-heal-overview.md
- action:skills/daemon/augur/actions/auto-skill-md-overview.md
- action:skills/daemon/augur/actions/auto-skill-refs-overview.md
- action:skills/loop-docs/augur/actions/auto-stale-refs-overview.md
- action:skills/platform-admin/augur/actions/auto-duplication-overview.md
- action:skills/platform-admin/augur/actions/auto-fix-overview.md
- action:skills/platform-admin/augur/actions/auto-tidy-overview.md
_source_fingerprint: 90e78fdedf52827b2ccf00ce10b2f0c2f5d44c363daac1d2b6b499329b37f97c
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:17:12Z'
_cites:
- '[[action:skills/daemon/augur/actions/auto-security-scan-overview.md]]'
- '[[action:skills/daemon/augur/actions/auto-self-heal-overview.md]]'
- '[[action:skills/daemon/augur/actions/auto-skill-md-overview.md]]'
- '[[action:skills/daemon/augur/actions/auto-skill-refs-overview.md]]'
- '[[action:skills/loop-docs/augur/actions/auto-stale-refs-overview.md]]'
- '[[action:skills/platform-admin/augur/actions/auto-duplication-overview.md]]'
- '[[action:skills/platform-admin/augur/actions/auto-fix-overview.md]]'
- '[[action:skills/platform-admin/augur/actions/auto-tidy-overview.md]]'
_mentions:
- '[[concepts/daemon-maintenance-command-loops]]'
- '[[concepts/documentation-and-repo-maintenance-commands]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
_relates_to:
- '[[adaptive]]'
- '[[autonomous]]'
- '[[daemon-maintenance-command-loops]]'
- '[[documentation-and-repo-maintenance-commands]]'
- '[[maintenance]]'
- '[[platform-admin-and-skill-quality-commands]]'
- '[[repair]]'
_entity_tier: 3
---

# Autonomous Maintenance And Repair Actions

## Compiled truth

### Current Thesis

These actions are the action-layer front door to Augur’s self-repair behavior. They expose absorbed maintenance workflows so users and agents can inspect or trigger repair-oriented surfaces without having to reconstruct which command pack owns the underlying fix.

### What This Page Knows

The cluster combines self-heal and security action overviews from daemon, skill-doc and skill-reference repair, stale-reference repair, duplication cleanup, generic fix workflows, and TODO cleanup/tidy surfaces. The common role is repair exposure. These actions are not broad architecture concepts by themselves; they are the stable runtime handles for recurring maintenance jobs that keep references, skills, and operational surfaces from silently decaying.

### Key Dimensions

- A bridge between daemon-owned or admin-owned maintenance logic and user-visible operational controls.
- Generic fix, duplication, and tidy flows that package recurring cleanup patterns into named actions.
- Reference and skill-hygiene repair actions that keep generated and documented surfaces aligned.
- Self-heal and security repair surfaces exposed at the action layer.

### Recent Shifts

- More maintenance behavior has been absorbed into consolidated surfaces, so the action layer now matters for discoverability and control.
- Repair actions increasingly encode productized maintenance entrypoints instead of leaving cleanup as hidden internal scripts.

### Open Tensions

- A repair action can be discoverable and useful, but it still has to avoid promising autonomous fixes that the underlying workflow cannot safely perform.
- Consolidated action surfaces reduce fragmentation, but they can hide which subsystem truly owns the maintenance burden.

### How to Use This

Use this page when the task is a recurring repair pattern: self-heal, stale-reference cleanup, skill hygiene, duplication cleanup, or absorbed maintenance work that now lives behind a stable action surface. These actions are the right start when the user wants repair behavior but not the raw command grammar behind it.

### Open Questions

- How much autonomous repair should stay exposed as a named action before it becomes too easy to run without understanding blast radius?
- Which absorbed repair workflows still need clearer ownership cues so users know whether a daemon, docs, or admin subsystem is doing the work?

### Source Basis

- `action:skills/daemon/augur/actions/auto-security-scan-overview.md`: View the absorbed security-scan workflow from the consolidated daemon surface.
- `action:skills/daemon/augur/actions/auto-self-heal-overview.md`: View the absorbed auto-self-heal workflow from the consolidated daemon surface.
- `action:skills/daemon/augur/actions/auto-skill-md-overview.md`: View Validate and generate SKILL.
- `action:skills/daemon/augur/actions/auto-skill-refs-overview.md`: View Validate and fix SKILL.
- `action:skills/loop-docs/augur/actions/auto-stale-refs-overview.md`: View Detect and fix stale page and path references across actions and codebase.
- `action:skills/platform-admin/augur/actions/auto-duplication-overview.md`: View Detect duplicate internal auto-command implementations and collapse safe mirrors into wrappers from the platform-admin surface.
- `action:skills/platform-admin/augur/actions/auto-fix-overview.md`: View the absorbed auto-fix workflow from the consolidated platform-admin surface.
- `action:skills/platform-admin/augur/actions/auto-tidy-overview.md`: View the absorbed TODO-marker cleanup workflow from the consolidated platform-admin surface.

### Related Concepts

- [[concepts/daemon-maintenance-command-loops]]
- [[concepts/documentation-and-repo-maintenance-commands]]
- [[concepts/platform-admin-and-skill-quality-commands]]

## Timeline

- _at: 2026-05-03T13:17:12Z  _source: action:skills/daemon/augur/actions/auto-security-scan-overview.md
  View the absorbed security-scan workflow from the consolidated daemon surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/daemon/augur/actions/auto-self-heal-overview.md
  View the absorbed auto-self-heal workflow from the consolidated daemon surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/daemon/augur/actions/auto-skill-md-overview.md
  View Validate and generate SKILL.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/daemon/augur/actions/auto-skill-refs-overview.md
  View Validate and fix SKILL.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-docs/augur/actions/auto-stale-refs-overview.md
  View Detect and fix stale page and path references across actions and codebase.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/platform-admin/augur/actions/auto-duplication-overview.md
  View Detect duplicate internal auto-command implementations and collapse safe mirrors into wrappers from the platform-admin surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/platform-admin/augur/actions/auto-fix-overview.md
  View the absorbed auto-fix workflow from the consolidated platform-admin surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/platform-admin/augur/actions/auto-tidy-overview.md
  View the absorbed TODO-marker cleanup workflow from the consolidated platform-admin surface.
