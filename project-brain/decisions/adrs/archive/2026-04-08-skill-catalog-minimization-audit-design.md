# Skill Catalog Minimization Audit

**Date:** 2026-04-08
**Status:** Draft
**Scope:** Define the review model for reducing the Augur skill set to the minimum required core while separating internal-only skills from public standalone skills.

## Problem

The current `skills/` tree mixes several different concerns:

- user-facing standalone skills
- Augur-internal support skills
- imported or lightly modified external skills that may not belong in Augur ownership
- overlapping skills that may need deletion, merger, or consolidation

This makes the skill catalog noisy and weakens standalone installation.

The objective is not to make hubs match skills. Hubs are cross-skill user workspaces and should remain independent from skill packaging decisions.

## Goals

1. Keep the standalone catalog understandable in terms of direct user value.
2. Carve out a single explicit internal-only catalog category: `augur-internal`.
3. Review whether each skill is truly Augur-owned, adopted external, or a candidate to leave Augur ownership.
4. Identify skills that should be kept, moved, merged, deleted, or externalized.
5. Minimize the Augur-owned core to the smallest coherent set required.

## Non-Goals

- Replacing hubs with a skill taxonomy
- Designing a large public category tree
- Physically reorganizing the repository in this pass
- Automatically deciding ambiguous ownership cases without user input

## Core Model

The audit uses two independent axes.

### 1. Catalog Axis

- `public`
- `augur-internal`

Rules:

- `x-augur-category: augur-internal` means the skill is internal-only and should be hidden from the public standalone catalog.
- Missing category means the skill is public by default.
- No broader public category system is introduced in this pass.

### 2. Ownership Axis

- `augur`
- `adopted`
- `external-candidate`

Rules:

- `augur`: clearly created or materially shaped by Augur
- `adopted`: external origin but intentionally maintained in Augur
- `external-candidate`: looks downloaded, lightly patched, or otherwise not meaningfully Augur-owned

If ownership is ambiguous, the audit does not decide automatically. It is marked `ask-user`.

## Internal Skill Boundary

The default `augur-internal` bucket includes:

- `auto-*`
- `runbook-*`
- `*-patterns`
- templates
- scaffolds/setup helpers
- low-level ops/dev plumbing

These may still remain in the repository, but they should not be treated as first-class standalone catalog products.

## Public Skill Boundary

Public skills are anything outside `augur-internal` that can deliver standalone value, including:

- personal workflow skills
- professional/business skills
- technical/developer/operator applications
- integrations that make sense as user-installable products

Borderline developer/operator skills such as `validator`, `plugin-pack`, `llmfit`, `system-cleanup`, `remote-access`, and `updater` are treated as public standalone candidates unless later evidence shows they should be internal.

## Review Record Per Skill

Each skill gets one audit row with:

- `skill`
- `current hub`
- `category`
- `ownership`
- `recommended action`
- `reason`
- `confidence`

### Confidence Values

- `clear`
- `ask-user`

## Allowed Actions

- `keep`
- `move-hub`
- `merge`
- `delete`
- `externalize`

Action meanings:

- `keep`: leave in repo with current role
- `move-hub`: skill remains but hub metadata should change
- `merge`: consolidate into another skill
- `delete`: remove because redundant or obsolete
- `externalize`: no longer treated as Augur-owned core

## Audit Order

The audit runs in this order:

1. `clear internal`
2. `clear public keep`
3. `clear external-candidate`
4. `merge/delete candidates`
5. `needs user decision`

This keeps the first pass focused on obvious reductions before ambiguous cases.

## Initial Overlap Clusters

The audit should explicitly inspect these clusters for merge/delete pressure:

- knowledge/search: `ask`, `search`, `knowledge`, `rag`, `commands`, `discovery`
- dev / validation / observability: `validator`, `verify`, `observe`, `ops-audit`, `ops-perf`, `runbook-dashboard`, `runbook-mcp`
- import / packaging / distribution: `import`, `skillstore`, `plugin-pack`, `ops-pkg`, `augur-upgrade`, `onboard`
- orchestration / execution: `orchestration`, `executor`, `guide`, `load-context`, `thread-hardening`
- personal workflow: `lifestyle`, `reading-list`, `eisenhower`, `attention`, `apple`, `google-workspace`
- business / professional: `venture-augur`, `linkedin-writer`, `career-ops`, `growth`
- system / maintenance / operator tools: `updater`, `remote-access`, `system-cleanup`, `kill-augur`, `reload-dashboard`

This cluster list is for review targeting only. It does not pre-commit any mergers.

## Deliverable

The first pass produces a grouped audit table with sections:

- `clear internal`
- `clear public keep`
- `clear external-candidate`
- `merge/delete candidates`
- `needs user decision`

The second pass, after user review, applies metadata changes and any approved structural cleanup.

## Architectural Follow-Ups Found During Audit

Some skills initially flagged as weak boundaries may still own real runtime behavior.
When that happens, the migration should prefer moving ownership and wiring to the
correct skill rather than treating the problem as catalog-only cleanup.

### Review Queue Ownership

The dependency pass found that the review queue is not a true core-domain feature.

- `src/mcp/augur_mcp/domain/reviews.py` is a thin shim that dynamically loads
  `skills/channels/augur/lib/registry.py`
- the actual review registry, persistence, and attention bridge live in the
  `channels` skill
- the migration plan should therefore move MCP registration for
  `get-reviews-summary` and `manage-reviews` fully into `channels`
- tool names may stay stable during the migration, but the dynamic shim in
  `src/mcp/augur_mcp/domain/reviews.py` should be retired

This cleanup should be tracked as part of the skill minimization work because it
clarifies that `channels` is a real Augur-internal infrastructure skill, not a
stub candidate.

## Recommended Next Step

Run the first audit pass starting with the `clear internal` bucket and only escalate to the user when ownership or consolidation intent is ambiguous.
