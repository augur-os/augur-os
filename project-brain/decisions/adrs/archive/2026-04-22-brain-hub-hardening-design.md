---
title: Brain Hub Hardening Design
date: 2026-04-22
status: draft-approved
scope: Brain hub button, data freshness, live page, and staged surface hardening
---

# Brain Hub Hardening Design

## Summary

Brain hardening should make the hub trustworthy as a user-facing control surface. Every visible button should either perform a useful action or explain why it is unavailable. Every displayed value should come from current, real data and should make its source, freshness, and next useful action clear.

The implementation should use a contract-driven survival audit. The five live Brain pages are hardened first, while staged Brain surfaces are audited and promoted only when they meet the same standards. Staged code should not become live just because it exists.

## Goals

- Make every button on Brain pages useful, wired to a real MCP tool or central IDE action, and visibly successful or failed.
- Make every displayed data value current, source-backed, and paired with clear stale, empty, and error states.
- Preserve the flat Brain information architecture: `/brain/memory`, `/brain/search`, `/brain/daily-logs`, `/brain/profile`, and `/brain/workspace`.
- Audit staged Brain AI, harness, RAG, schedule, and OCR/import surfaces through an explicit survival gate.
- Promote only staged surfaces that have distinct Brain value and do not duplicate Browse, Settings, or existing live Brain pages.
- Verify the result in browser on the worktree-owned dashboard port before calling the work complete.

## Non-Goals

- Promoting every staged Brain page in one pass.
- Reintroducing nested Brain tab stacks or `/brain/knowledge/memory` style nested routes.
- Adding fake fallback data, beta mock output, or empty-success responses to make pages appear healthy.
- Moving provider configuration or generic inventory browsing back into Brain.
- Replacing the Brain IA with a broad cockpit before the current pages are trustworthy.

## Recommended Approach

Use a **Contract-Driven Survival Audit**.

This approach has two tracks:

1. Harden the five live Brain pages against shared action and data contracts.
2. Run each staged Brain surface through a survival gate before deciding whether to promote, rework, or leave it staged.

This is stricter than a normal page cleanup because it treats user value as the acceptance criterion. A staged surface that has many controls but unclear ownership should remain staged until its user job is obvious and verified.

Alternative approaches were considered:

- **Revive the whole Brain cockpit:** promotes Agent Control Center, Harness, RAG pages, schedules, and OCR at once. This is too broad and risks duplicate ownership, stale wiring, and nested navigation.
- **Live pages first, staged backlog second:** safest for the current five pages, but it leaves the selected staged-surface scope unresolved.

## Architecture

Brain remains a set of flat routes. Page components use MCP-backed dashboard hooks for data and mutations, while agentic work goes through the central action runner.

Shared contracts sit across the live pages and any staged surface selected for promotion:

- **Action contract:** target, loading state, disabled state, visible success, visible failure, and user-facing result.
- **Data contract:** source, last updated or generated-at metadata where available, stale state, empty state, and next useful action.
- **Survival gate:** distinct Brain value, exact MCP wiring, compatible response shapes, no fake fallback content, clear ownership, tests, and browser verification.

Dashboard code must not call Python scripts directly, import `fs`, spawn processes, or run direct LLM/API calls. If a primary MCP call fails, the UI should show the failure and recovery action instead of silently substituting placeholder data.

## Live Page Contracts

### Memory

The Memory overview should show decisions, patterns, preferences, search entry points, curation state, and wiki maintenance status.

Required behavior:

- `Curate Memory` runs the real `memory-curate` tool.
- Completion reports what changed, including processed logs and entries added when available.
- Curation refreshes affected stats, categories, recent decisions, and freshness state.
- Wiki maintenance data comes from real wiki MCP tools and exposes load, error, and refresh states.
- Navigation cards to Workspace, Profile, and Daily Logs remain useful summaries, not duplicate fake widgets.

### Search

Search is the dedicated memory lookup surface.

Required behavior:

- Manual queries and suggested queries call `memory-search`.
- Results show source, date, relevance or confidence, category, and file path when present.
- Empty states offer concrete next actions such as trying a narrower topic, curating memory, or checking source freshness.
- Search failures are visible on the page and not console-only.

### Daily Logs

Daily Logs should help the user inspect recent session history.

Required behavior:

- Calendar dates reflect real log or commit-backed data and make the source clear.
- Selecting a date loads real content with loading and error states.
- Open-in-editor uses the real daily-log open tool and reports success or the exact failure.
- Last-curated and log freshness are visible enough for the user to judge whether data is stale.

### Profile

Profile should make the Human API profile inspectable and safely editable.

Required behavior:

- Read, save, and regenerate use real memory profile MCP tools.
- Saves preserve frontmatter structure and validate success before leaving edit mode.
- Regeneration refreshes profile data and related workspace metadata.
- Failures are visible and actionable.

### Workspace

Workspace should expose canonical memory files and the generated memory report.

Required behavior:

- File open buttons use real workspace-open MCP calls and report success or failure.
- Refresh updates workspace files and report metadata together.
- Missing files explain what action would create or restore them.
- Report preview loads only real report content and keeps failure visible.
- Report regeneration uses a valid central action or is hidden until a valid action definition exists.

## Staged Surface Survival Gate

Staged pages remain outside the live product unless they pass this checklist:

- The page has a distinct Brain job that is not already Browse, Settings, or a live Brain page.
- Every MCP tool name exists and the UI expects the real response shape.
- Every mutation or action has visible loading, success, failure, and recovery states.
- Data has source and freshness context.
- The page has focused component or contract tests.
- The page can be browser-verified with real data on the correct worktree dashboard.

Initial classification:

| Surface | Decision | Rationale |
| --- | --- | --- |
| Agent Control Center | Promote if wiring audit passes | Distinct value: execution routing, client health, provider readiness, and dispatch clarity. |
| Brain Harness | Promote if wiring audit passes | Distinct value: capability wiring diagnostics and repair workflow. |
| RAG and knowledge staged pages | Rework before promote | May duplicate Search, Workspace, or Browse unless scoped to a clear Brain job and freshness model. |
| Schedule surfaces | Rework before promote | Needs clear user value, ownership, and action outcomes before becoming a Brain route. |
| OCR/import | Do not promote yet | Current staged surface includes beta/mock extracted text and a non-MCP endpoint pattern. |

## Error Handling

Error handling should preserve trust.

- No silent console-only failures for user-triggered actions.
- No fake success states when a backend call fails.
- No fallback content that makes broken data look current.
- Disabled controls should explain the missing requirement when practical.
- Empty states should distinguish between genuinely empty data and failed data loading.

## Testing And Verification

Testing should prove user-visible behavior, not only component rendering.

Required checks:

- Wiring audit for every Brain page: each `useMcpQuery`, `useMcpMutation`, `useMcpPoll`, and `mcpCall` tool name matches a real MCP registration and expected response shape.
- Component tests for critical controls: curate, search, profile save/regenerate, workspace open/report preview, daily log select/open, wiki update, staged Agent Control Center, and Brain Harness.
- MCP contract tests for freshness/source fields where the dashboard depends on them.
- Generated registry checks: `mount-plugins` and `generate-tabs` must show Brain routes mounted cleanly with no orphan routes.
- Browser verification on the actual worktree-owned dashboard port.
- Promoted staged pages must pass the same browser checks before becoming live tabs.

Completion standard:

- Each live Brain page has at least one real data value verified in browser.
- Each live Brain page has at least one meaningful action verified in browser.
- Each promoted staged page satisfies the survival gate.
- Each non-promoted staged page has a recorded reason.

## Acceptance Criteria

- The five live Brain pages render real data and do not rely on fake fallbacks.
- Every visible button on those pages has an audited target and visible outcome.
- Freshness/source context is visible for key data panels.
- Agent Control Center and Brain Harness are either promoted with verified value or left staged with specific blockers.
- RAG, schedule, and OCR staged pages are classified with promotion, rework, or do-not-promote reasons.
- Dashboard build, focused tests, mount/generate registry checks, and browser verification pass before implementation is considered complete.

## Risks

- Staged pages may look close to ready but depend on tools with drifted names or response shapes.
- Browser verification may reveal that live MCP data is missing even when tests pass.
- Promoting Agent Control Center could overlap Settings if provider configuration actions are not carefully routed.
- Promoting RAG pages could duplicate Search or Workspace unless their scope is narrowed.

## Implementation Planning Notes

The implementation plan should proceed in bounded increments:

1. Build the Brain action/data audit inventory.
2. Harden shared live-page hooks and visible action outcomes.
3. Patch each live page against the shared contracts.
4. Run the staged survival audit and promote only approved surfaces.
5. Add tests and browser verification evidence.
6. Regenerate tabs/mounts and commit verified checkpoints.
