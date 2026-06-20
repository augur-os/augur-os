---
title: Augur Harness Layer Design
date: 2026-04-19
status: draft-approved
branch: codex/harness-layer-design
source_article: https://www.linkedin.com/posts/akshay-pachaar_a-harnessed-llm-agent-and-why-llm-is-a-share-7451280005042704384-ff0_
---

# Augur Harness Layer Design

## Summary

Augur should add a Brain hub control-plane page at `/brain/harness` that explains and operates the "harness" around Augur's second brain. The page is not a replacement for Browse. Browse answers "what exists?" as a catalog. Brain Harness answers "how does Augur think and act?" by showing capability inventory, relationships, diagnostics, provenance, and safe next actions.

The first MVP is a snapshot-backed Harness Map with balanced starter diagnostics and trigger buttons. The snapshot is generated runtime/cache state assembled from decentralized sources. It must not become a new central registry.

## Product Decisions

- Placement: Brain hub.
- Route: `/brain/harness`.
- First deliverable: Harness Map.
- MVP depth: inventory plus diagnostics.
- Diagnostic strategy: balanced shallow starter set across structural integrity, dashboard/MCP wiring, and knowledge quality.
- Action model: safe direct triggers plus IDE-dispatched repair actions.
- Architecture: snapshot-backed control plane.

## Problem

Augur already has many second-brain ingredients: skills, memory, wiki, ADRs, MCP tools, dashboard pages, autoloops, commands, and action dispatch. The user can browse many of these pieces, but there is no single surface that explains how they form an operating harness.

This creates several user-facing gaps:

- The user cannot quickly see what makes up Augur's second brain.
- The user cannot distinguish catalog metadata from operational readiness.
- The user cannot easily tell whether a page is stale, disconnected, or missing provenance.
- The user cannot see the recommended next action when a harness component is unhealthy.
- Repairs are easy to imagine but risky unless they route through the existing agent/IDE action model.

## Goals

- Show a coherent map of Augur's harness components.
- Preserve plugin decentralization: facts stay in skill frontmatter, MCP registrations, docs, runtime state, and scanner outputs.
- Give the Brain hub a control-plane surface distinct from Browse.
- Surface shallow but useful diagnostics across structure, wiring, and knowledge quality.
- Offer safe direct triggers for refresh/reindex/open-source actions.
- Route code-changing repair work through IDE-dispatched agent actions.
- Make every warning traceable to a source path, scanner, or runtime state item.

## Non-Goals

- Do not add a new central source-of-truth registry.
- Do not duplicate Browse search/filter/catalog UX.
- Do not directly execute LLM calls from the dashboard.
- Do not run Python scripts directly from dashboard code.
- Do not add direct dashboard repair buttons that edit files.
- Do not build full agent run tracing in the MVP.
- Do not require a visual graph in the MVP.

## Architecture

The Harness Map uses a snapshot-backed control-plane architecture:

1. Decentralized sources remain canonical:
   - `skills/*/SKILL.md` `x-augur-*` frontmatter
   - MCP `@mcp.tool(name=...)` registrations
   - dashboard page discovery outputs
   - command/action metadata
   - ADR/wiki/index metadata
   - loop/ops scanner outputs
   - runtime state where relevant
2. A Python snapshot assembler reads those sources and produces generated state under Augur's external runtime/cache paths via `src.config.paths`.
3. MCP tools expose the current snapshot, refresh status, and safe operations.
4. The `/brain/harness` dashboard page reads the snapshot through MCP hooks.
5. Safe operations use MCP mutations or `mcpCall`.
6. Code-changing repairs use the central action infrastructure with `dispatch: ide`.

The snapshot is a view, not authority. If a fact cannot be traced back to a decentralized source, scanner output, or runtime state, it does not belong in the snapshot.

## Snapshot Model

The snapshot should contain five top-level sections.

### Capabilities

Capabilities are the things Augur can know, show, call, or run.

Initial capability types:

- `memory`
- `skill`
- `mcp_tool`
- `dashboard_page`
- `command`
- `protocol`
- `loop`
- `document_surface`

Each capability should include:

- `id`
- `type`
- `label`
- `hub`
- `owner_skill` when known
- `source_path` when available
- `summary`
- `tags`
- `status`

### Relationships

Relationships explain how capabilities connect.

Initial relationship kinds:

- `skill_declares_tool`
- `skill_declares_command`
- `skill_owns_page`
- `page_calls_tool`
- `loop_scans_source`
- `protocol_governs_action`
- `memory_surface_indexes_source`

Each relationship should include:

- `from_id`
- `to_id`
- `kind`
- `source_path`
- `confidence`

### Diagnostics

Diagnostics explain what needs attention.

Diagnostic severities:

- `info`
- `warning`
- `error`

Every warning or error must include:

- human-readable reason
- affected capability IDs
- source path or scanner source
- recommended next action
- whether the action is safe/direct or IDE-dispatched

### Actions

Actions define what the user can do from the page.

Initial action classes:

- `refresh_snapshot`
- `rerun_diagnostics`
- `reindex_knowledge`
- `reindex_browse`
- `open_source`
- `dispatch_ide_repair`

Safe direct actions may call MCP mutations. Repair actions must dispatch an IDE agent task and must not directly mutate files from dashboard code.

### Provenance

Provenance explains why the snapshot is trustworthy.

The snapshot should include:

- `generated_at`
- `generator_version`
- `source_counts`
- `scanner_versions` when available
- source paths for each emitted fact
- optional source hashes for stale detection
- partial failure details when a scanner fails

## Starter Diagnostics

The MVP includes shallow checks from three families.

### Structural Integrity

Examples:

- missing or unparsable `SKILL.md` frontmatter
- missing `x-augur-hub`
- hub alignment issues
- missing owner/source information
- evidence of central registry drift

### Dashboard and MCP Wiring

Examples:

- dashboard page references an MCP tool that is not registered
- declared skill tool is missing from MCP registrations
- page discovery mismatch
- stale generated tab/page metadata
- response-shape risk where a page expects a shape different from the tool family

### Knowledge Quality

Examples:

- missing source provenance for a memory/document surface
- stale wiki or project index timestamp
- missing ADR reference for architectural decisions
- knowledge source exists but is not discoverable through expected indexes

## UI Design

The `/brain/harness` page should feel like a control plane.

Primary sections:

1. Harness readiness summary
   - mapped capability count
   - warnings/errors
   - snapshot freshness
   - last scan status
2. Capability map
   - grouped by capability type
   - source path/provenance visible
   - links to Browse detail pages where useful
3. Diagnostics
   - balanced starter set
   - severity, affected capability, source, recommended action
4. Trigger panel
   - refresh snapshot
   - reindex knowledge/Browse
   - open source file
   - ask IDE agent to repair

The page should not duplicate Browse's catalog search/filter experience. Browse remains the place to discover and open individual catalog items. Brain Harness is for readiness, trust, and repair.

## Error Handling

The page must be honest about failure states.

- No snapshot: explain that the Harness Map has not been generated and show one safe generate action.
- Stale snapshot: show snapshot age and refresh action.
- Partial scan: show the scanner that failed, preserve valid partial results, and avoid pretending the page is fully healthy.
- Missing source: show a warning instead of dropping the row silently.
- Repair needed: route to IDE-dispatched action, not direct dashboard mutation.

## Implementation Boundary

The implementation should likely add:

- a Python harness snapshot assembler in the MCP/core or domain layer
- MCP tools for reading and refreshing the snapshot
- a Brain hub dashboard page at `apps/dashboard/features/pages/brain/harness/page.tsx`
- page metadata contribution through an existing Brain skill's `SKILL.md`, most likely `skills/knowledge/SKILL.md` or `skills/ai/SKILL.md`, without adding central dashboard config
- focused tests for snapshot assembly, diagnostic classification, dashboard rendering, and action wiring

The exact file placement should be finalized in the ADR and implementation plan after checking current MCP registration conventions.

## Verification

Implementation is not complete until the following pass:

- Python unit tests for snapshot assembly and diagnostic classification.
- Dashboard component tests for render states and action wiring.
- `pnpm run mount-plugins` from `apps/dashboard/` reports no orphan page issues.
- Dashboard build succeeds through the project-approved lifecycle/build path.
- Browser verification opens `/brain/harness` on the correct checkout and confirms real capability data appears.
- Safe triggers are verified in browser.
- IDE repair actions are verified to dispatch through the action runner rather than directly mutating files.

## Success Criteria

A user can open `/brain/harness` and answer:

- What makes up my Augur second brain?
- Which pieces are stale, broken, or weakly connected?
- Where did each fact come from?
- What safe next action should I take?
- When a repair is needed, how will Augur route that work through an agent?

## Follow-Up Sequence

Because this is architectural work, this spec should be absorbed into an ADR before implementation planning. After the ADR is accepted, write a granular implementation plan and build in the `codex/harness-layer-design` worktree.
