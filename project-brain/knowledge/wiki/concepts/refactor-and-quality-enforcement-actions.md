---
title: Refactor And Quality Enforcement Actions
summary: Action surfaces that expose lint, formatting, refactor, debt, alignment,
  and test enforcement workflows.
tags:
- refactor-and-quality-enforcement-actions
- documentation-and-repo-maintenance-commands
- platform-admin-and-skill-quality-commands
- testing-and-quality-command-loops
- adaptive
- refactor
- quality
- enforcement
aliases: []
related:
- '[[documentation-and-repo-maintenance-commands]]'
- '[[platform-admin-and-skill-quality-commands]]'
- '[[testing-and-quality-command-loops]]'
created: '2026-04-23T10:46:56Z'
_page_type: concept
_hub: adaptive
_sources:
- action:skills/loop-ops/augur/actions/auto-plugin-lint-overview.md
- action:skills/loop-quality/augur/actions/auto-format-overview.md
- action:skills/loop-quality/augur/actions/auto-lint-overview.md
- action:skills/loop-repo/augur/actions/auto-dir-alignment-overview.md
- action:skills/loop-repo/augur/actions/auto-vault-hygiene-overview.md
- action:skills/loop-test/augur/actions/auto-test-webmcp-overview.md
- action:skills/platform-admin/augur/actions/auto-refactor-overview.md
- action:skills/platform-admin/augur/actions/auto-tech-debt-overview.md
_source_fingerprint: 2c9f84ff04718a2a38fb976d8000d68f372555579c16c9e65c95fb571a0e6ec7
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:17:12Z'
_cites:
- '[[action:skills/loop-ops/augur/actions/auto-plugin-lint-overview.md]]'
- '[[action:skills/loop-quality/augur/actions/auto-format-overview.md]]'
- '[[action:skills/loop-quality/augur/actions/auto-lint-overview.md]]'
- '[[action:skills/loop-repo/augur/actions/auto-dir-alignment-overview.md]]'
- '[[action:skills/loop-repo/augur/actions/auto-vault-hygiene-overview.md]]'
- '[[action:skills/loop-test/augur/actions/auto-test-webmcp-overview.md]]'
- '[[action:skills/platform-admin/augur/actions/auto-refactor-overview.md]]'
- '[[action:skills/platform-admin/augur/actions/auto-tech-debt-overview.md]]'
_mentions:
- '[[concepts/documentation-and-repo-maintenance-commands]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
- '[[concepts/testing-and-quality-command-loops]]'
_relates_to:
- '[[adaptive]]'
- '[[documentation-and-repo-maintenance-commands]]'
- '[[enforcement]]'
- '[[platform-admin-and-skill-quality-commands]]'
- '[[quality]]'
- '[[refactor]]'
- '[[testing-and-quality-command-loops]]'
_entity_tier: 3
---

# Refactor And Quality Enforcement Actions

## Compiled truth

### Current Thesis

This action family exposes the enforcement side of Augur’s quality system. These actions package formatting, linting, alignment, refactor, debt, and test-oriented quality workflows into stable handles that can be used before or alongside the deeper command surface.

### What This Page Knows

The sources here cover format and lint overviews, directory alignment, vault hygiene, WebMCP validation, plugin lint, refactor workflows, and technical-debt inspection. The shared rule is standard enforcement. These actions turn codebase quality expectations into accessible runtime surfaces, so quality work is not just an internal loop concern but a visible part of how the system maintains itself.

### Key Dimensions

- Alignment and hygiene checks that keep repo and vault structure within expected boundaries.
- Formatting and lint enforcement as explicit action-layer quality surfaces.
- Refactor, plugin-lint, and technical-debt actions that surface structural quality work before large edits happen.
- Test and protocol enforcement actions that connect local quality work to broader integration expectations such as WebMCP behavior.

### Recent Shifts

- More quality behavior is now exposed as stable action surfaces instead of living only in auto-loop internals.
- Structural quality work such as refactor and debt handling is becoming part of ordinary operational workflow rather than exceptional cleanup.

### Open Tensions

- Action-level enforcement can start the work, but merge-critical confidence still requires the corresponding command-level proofs and verification discipline.
- Quality enforcement is useful only if these actions remain scoped enough to guide work instead of becoming another generic maintenance bucket.

### How to Use This

Use this page when the task is quality enforcement or controlled structural cleanup: lint, format, refactor, technical debt, alignment, plugin shape, vault hygiene, or protocol validation. These actions are a good entrypoint when the user needs a named quality surface before deciding how deep the repair should go.

### Open Questions

- How should structural quality actions expose blast radius so refactor and debt work remain intentional instead of casually destructive?
- Which enforcement actions should stay lightweight entrypoints and which should be merged more tightly with the corresponding command workflows?

### Source Basis

- `action:skills/loop-ops/augur/actions/auto-plugin-lint-overview.md`: Review plugin structural issues and lint validation results from the consolidated loop-ops surface.
- `action:skills/loop-quality/augur/actions/auto-format-overview.md`: View Run prettier formatting on source files to enforce consistent style for adaptive engine and self-healing automation.
- `action:skills/loop-quality/augur/actions/auto-lint-overview.md`: View lint scan coverage, autofix stages, and the current operator summary.
- `action:skills/loop-repo/augur/actions/auto-dir-alignment-overview.md`: Review directory alignment status from the consolidated loop-repo surface.
- `action:skills/loop-repo/augur/actions/auto-vault-hygiene-overview.md`: Review vault structure violations and auto-fix guidance from the consolidated loop-repo surface.
- `action:skills/loop-test/augur/actions/auto-test-webmcp-overview.md`: View Validate WebMCP tool registration and health across all 9 phases.
- `action:skills/platform-admin/augur/actions/auto-refactor-overview.md`: View the absorbed auto-refactor workflow from the consolidated platform-admin surface.
- `action:skills/platform-admin/augur/actions/auto-tech-debt-overview.md`: View the absorbed technical-debt workflow from the consolidated platform-admin surface.

### Related Concepts

- [[concepts/documentation-and-repo-maintenance-commands]]
- [[concepts/platform-admin-and-skill-quality-commands]]
- [[concepts/testing-and-quality-command-loops]]

## Timeline

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-ops/augur/actions/auto-plugin-lint-overview.md
  Review plugin structural issues and lint validation results from the consolidated loop-ops surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-quality/augur/actions/auto-format-overview.md
  View Run prettier formatting on source files to enforce consistent style for adaptive engine and self-healing automation.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-quality/augur/actions/auto-lint-overview.md
  View lint scan coverage, autofix stages, and the current operator summary.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-repo/augur/actions/auto-dir-alignment-overview.md
  Review directory alignment status from the consolidated loop-repo surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-repo/augur/actions/auto-vault-hygiene-overview.md
  Review vault structure violations and auto-fix guidance from the consolidated loop-repo surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-test/augur/actions/auto-test-webmcp-overview.md
  View Validate WebMCP tool registration and health across all 9 phases.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/platform-admin/augur/actions/auto-refactor-overview.md
  View the absorbed auto-refactor workflow from the consolidated platform-admin surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/platform-admin/augur/actions/auto-tech-debt-overview.md
  View the absorbed technical-debt workflow from the consolidated platform-admin surface.
