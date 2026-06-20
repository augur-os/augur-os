---
title: Platform Admin And Skill Quality Commands
summary: Administrative command surfaces for build-debug-merge workflows, release
  management, code review, coverage, migrations, and skill-quality repair.
tags:
- platform-admin-and-skill-quality-commands
- documentation-and-repo-maintenance-commands
- testing-and-quality-command-loops
- adaptive
- platform
- admin
- skill
- quality
aliases: []
related:
- '[[documentation-and-repo-maintenance-commands]]'
- '[[testing-and-quality-command-loops]]'
created: '2026-04-23T10:19:48Z'
_page_type: concept
_hub: adaptive
_sources:
- adr:adrs/ADR-550-windows-hardening-support.md
- command:skills/auto-skill-quality/commands/auto-seed-data.md
- command:skills/auto-skill-quality/commands/auto-skill-migrate.md
- command:skills/auto-skill-quality/commands/auto-skill-structure.md
- command:skills/platform-admin/commands/auto-code-review.md
- command:skills/platform-admin/commands/auto-duplication.md
- command:skills/platform-admin/commands/auto-test-coverage.md
- command:skills/platform-admin/commands/dev-build.md
- command:skills/platform-admin/commands/dev-debug.md
- command:skills/platform-admin/commands/dev-merge.md
- command:skills/platform-admin/commands/port-release.md
- command:skills/platform-admin/commands/release.md
- command:skills/platform-admin/commands/remote-access.md
- command:skills/platform-admin/commands/stage-release.md
_source_fingerprint: cc9ec75a03a1884071ce32b6d9fae3b95f66f80d12b9d5a63ae32a0bd1077be7
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:17:12Z'
_cites:
- '[[adr:adrs/ADR-550-windows-hardening-support.md]]'
- '[[command:skills/auto-skill-quality/commands/auto-seed-data.md]]'
- '[[command:skills/auto-skill-quality/commands/auto-skill-migrate.md]]'
- '[[command:skills/auto-skill-quality/commands/auto-skill-structure.md]]'
- '[[command:skills/platform-admin/commands/auto-code-review.md]]'
- '[[command:skills/platform-admin/commands/auto-duplication.md]]'
- '[[command:skills/platform-admin/commands/auto-test-coverage.md]]'
- '[[command:skills/platform-admin/commands/dev-build.md]]'
- '[[command:skills/platform-admin/commands/dev-debug.md]]'
- '[[command:skills/platform-admin/commands/dev-merge.md]]'
- '[[command:skills/platform-admin/commands/port-release.md]]'
- '[[command:skills/platform-admin/commands/release.md]]'
- '[[command:skills/platform-admin/commands/remote-access.md]]'
- '[[command:skills/platform-admin/commands/stage-release.md]]'
_mentions:
- '[[concepts/daemon-maintenance-command-loops]]'
- '[[concepts/documentation-and-repo-maintenance-commands]]'
- '[[concepts/operational-audit-and-observability-commands]]'
- '[[concepts/testing-and-quality-command-loops]]'
_relates_to:
- '[[adaptive]]'
- '[[admin]]'
- '[[documentation-and-repo-maintenance-commands]]'
- '[[platform]]'
- '[[quality]]'
- '[[skill]]'
- '[[testing-and-quality-command-loops]]'
_entity_tier: 2
---

# Platform Admin And Skill Quality Commands

## Compiled truth

### Current Thesis

Platform admin and skill quality commands define the repo-wide change-management surface. They are the commands you reach for when work crosses build integrity, merge discipline, release boundaries, migration safety, or the quality of a skill contract itself.

### What This Page Knows

This cluster combines the interactive admin workflows such as `dev-build`, `dev-debug`, `dev-merge`, release staging and porting, remote access, and Augur-aware refactors with analytical commands for code review, duplication, coverage, simplification, migration safety, and absorbed skill-quality hardening loops. The shared pattern is coordinated change. These commands do not just inspect the repo; they control how meaningful edits are validated, merged, released, or applied to skill-owned surfaces without losing system integrity.

### Key Dimensions

- Analytical review surfaces for duplication, coverage, simplification, and structured code review findings.
- Safety checks for migrations and large structural changes that can ripple across paths and generated surfaces.
- Skill-quality remediation when the broken unit is the skill contract, documentation, or owned workflow rather than one isolated source file.
- Visibility-first admin workflows for build, debug, merge, and release transitions.

### Recent Shifts

- Merge and debug workflows increasingly encode worktree safety, ownership checks, and verification discipline instead of acting as thin wrappers around git commands.
- Skill-quality repair now sits beside platform administration because many quality failures are rooted in command and skill contracts rather than only in application code.

### Open Tensions

- The cluster risks becoming another catch-all if release/admin workflows and skill-quality loops are not kept conceptually separate from testing or daemon maintenance.
- These commands must stay forceful enough to complete end-to-end admin work while remaining conservative around active worktrees, generated outputs, and user-owned state.

### How to Use This

Use this page when the work changes repository state in a coordinated way: reproducing build/debug issues, preparing a safe merge, staging or porting a release, checking migration safety, or repairing the quality of a skill-owned surface. If you only need proof that something works, route first to [[concepts/testing-and-quality-command-loops]]. If you are primarily tracking runtime health, use [[concepts/operational-audit-and-observability-commands]] or [[concepts/daemon-maintenance-command-loops]].

### Open Questions

- How far should skill-quality repair go before it stops being a contract fix and becomes a broader product or architecture change?
- Which admin workflows should stay explicitly interactive because they encode user intent, and which can be made safely more autonomous?

### Source Basis

- `adr:adrs/ADR-550-windows-hardening-support.md`: Augur's hardening process currently mixes cross-platform checks, platform-sensitive checks, and GitHub CI smoke coverage without a single Windows support contract.
- `command:skills/auto-skill-quality/commands/auto-seed-data.md`: Run the absorbed seed-data hardening loop under `auto-skill-quality`.
- `command:skills/auto-skill-quality/commands/auto-skill-migrate.md`: Run the absorbed skill-migration hardening loop under `auto-skill-quality`.
- `command:skills/auto-skill-quality/commands/auto-skill-structure.md`: Run the absorbed structure-validation loop under `auto-skill-quality`.
- `command:skills/platform-admin/commands/auto-code-review.md`: Run an automated review pass on recent changes.
- `command:skills/platform-admin/commands/auto-duplication.md`: Scan internal scan-fix implementations for duplicate logic and rewrite safe.
- `command:skills/platform-admin/commands/auto-test-coverage.md`: Run the coverage diagnostics used by the nightly code-quality loop.
- `command:skills/platform-admin/commands/dev-build.md`: Clean all caches, rebuild the dashboard UI, and validate pages have no build issues.
- `command:skills/platform-admin/commands/dev-debug.md`: Use when debugging any issue in the dashboard, MCP, or codebase.
- `command:skills/platform-admin/commands/dev-merge.md`: Commit, merge into the target branch, push, and clean up worktrees/branches.
- `command:skills/platform-admin/commands/port-release.md`: Port a staged release payload from `staging/rX/` into canonical locations on `main`.
- `command:skills/platform-admin/commands/release.md`: Sync the current private repo state to the public `augur-os/augur-os` GitHub repo with clean history.

### Related Concepts

- [[concepts/documentation-and-repo-maintenance-commands]]
- [[concepts/testing-and-quality-command-loops]]

## Timeline

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-550-windows-hardening-support.md
  Augur's hardening process currently mixes cross-platform checks, platform-sensitive checks, and GitHub CI smoke coverage without a single Windows support contract.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/auto-skill-quality/commands/auto-seed-data.md
  Run the absorbed seed-data hardening loop under `auto-skill-quality`.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/auto-skill-quality/commands/auto-skill-migrate.md
  Run the absorbed skill-migration hardening loop under `auto-skill-quality`.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/auto-skill-quality/commands/auto-skill-structure.md
  Run the absorbed structure-validation loop under `auto-skill-quality`.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/platform-admin/commands/auto-code-review.md
  Run an automated review pass on recent changes.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/platform-admin/commands/auto-duplication.md
  Scan internal scan-fix implementations for duplicate logic and rewrite safe.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/platform-admin/commands/auto-test-coverage.md
  Run the coverage diagnostics used by the nightly code-quality loop.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/platform-admin/commands/dev-build.md
  Clean all caches, rebuild the dashboard UI, and validate pages have no build issues.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/platform-admin/commands/dev-debug.md
  Use when debugging any issue in the dashboard, MCP, or codebase.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/platform-admin/commands/dev-merge.md
  Commit, merge into the target branch, push, and clean up worktrees/branches.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/platform-admin/commands/port-release.md
  Port a staged release payload from `staging/rX/` into canonical locations on `main`.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/platform-admin/commands/release.md
  Sync the current private repo state to the public `augur-os/augur-os` GitHub repo with clean history.
