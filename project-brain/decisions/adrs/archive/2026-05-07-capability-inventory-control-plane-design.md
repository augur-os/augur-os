---
title: Capability Inventory Control Plane
date: 2026-05-07
status: proposed
scope: design
related:
  - 2026-05-06-capability-inventory-exposure-policy-design.md
  - ../plans/2026-05-06-capability-inventory-exposure-policy.md
---

# Capability Inventory Control Plane

## Purpose

Augur now has the first layer of capability inventory plumbing: scanners discover skills, MCP servers, MCP tools, commands, workflows, and CLI-backed capabilities; the resolver can merge discovered state with `config/system/capability_exposure.yaml`; Browse can display capability metadata; and generators can consult policy before writing managed exports.

The next problem is operational. The policy file is intentionally empty, so all discovered capabilities remain unclassified until a human or workflow makes explicit exposure decisions. Browse must become the safe management surface for those decisions without directly editing files or deleting user-owned capabilities.

This design defines phase 2: a reviewed-apply capability control plane. Browse shows the live inventory, explains drift, drafts policy changes through MCP, previews impact, and only applies changes after review.

## Goals

- Make Browse the unified place to understand and manage AI-client capability exposure.
- Keep Augur-owned and external capabilities visible in one inventory while clearly separating them by owner, management model, scope, and source.
- Provide actionable drift reports for duplicate skills, unclassified exports, unexpected client exposure, and missing expected exports.
- Let the user choose policy actions such as "keep only in Claude", "move to CLI only", "block from Gemini", and "approve multi-client".
- Require a reviewed diff and impact summary before any policy write.
- Preserve external and unmanaged skills; phase 2 governs exposure policy, not destructive uninstall.
- Prefer CLI plus `AGENTS.md` exposure for Augur operational or technical capabilities that do not need direct MCP/tool exposure in every client.
- Make Gemini/OpenCode tool-count reduction measurable before and after policy changes.

## Non-Goals

- Do not physically uninstall external/global skills from Claude, Codex, Gemini, OpenCode, or other client home folders.
- Do not move Obsidian/vault folders as part of this phase.
- Do not replace the existing dashboard internal chat or shell surface with a new terminal system.
- Do not make dashboard code write `capability_exposure.yaml` directly.
- Do not make policy application automatic on first click.
- Do not require every capability to be classified before Browse remains usable.

## Decisions

- Use one unified Browse inventory. Do not split Augur and external items into separate pages.
- Represent Augur, External, and Adopted as an Owner filter, grouping, badge, and report dimension.
- Use Reviewed Apply for every write: draft first, show diff and impact, then apply.
- Treat `config/system/capability_exposure.yaml` as the source of intended exposure.
- Treat scanners and generated indexes as the source of current exposure.
- Route all policy draft/apply operations through MCP.
- Keep existing generated exports unless policy explicitly blocks or moves them.
- Never delete or mutate unmanaged external source folders from Browse actions.
- Record policy decisions in versioned YAML so changes are reviewable in git.

## User Model

The user sees Browse as a PC hub: part inventory, part control plane, part observability surface. It should answer:

- What capabilities exist on this machine?
- Which clients can currently see each capability?
- Which capabilities are duplicated across clients?
- Which items are Augur-generated versus external or unmanaged?
- What will happen if I keep a skill only in Claude or move an Augur MCP tool to CLI-only?
- Which supported AI CLI or shell should I open to use this capability?

Browse should keep the inventory human-readable first. Technical fields are available in detail views and development mode, not forced into every card.

## Inventory Model

Each item is represented as a resolved `CapabilityRecord` with these user-facing dimensions:

| Dimension | Meaning |
|---|---|
| Type | `skill`, `mcp-server`, `mcp-tool`, `command`, `workflow`, or `cli`. |
| Owner | `augur`, `external`, or `adopted`. |
| Management | `generated`, `managed-policy`, or `unmanaged`. |
| Scope | `project`, `global`, or `mixed`. |
| Current exposure | Clients or surfaces where the capability appears now. |
| Intended exposure | Clients or surfaces policy allows. |
| Drift | Computed flags such as `duplicate`, `unclassified_export`, `unexpected_client`, and `missing_expected_export`. |
| Recommended action | Suggested next step such as keep, consolidate, move to CLI, block, approve multi-client, or review. |

Owner separation is not a hard route split. It appears as:

- a segmented Owner filter: All, Augur, External, Adopted;
- grouping in reconciliation reports;
- badges on cards and details;
- action rules that differ by owner and management.

This keeps one answer to "why is a client overloaded?" while preserving different governance rules for Augur and external capabilities.

## Browse UX

Browse remains one unified surface with layered controls.

Primary controls:

- Mode: Operational, Development.
- Type: Skills, MCP, Commands, Workflows, CLI.
- Owner: All, Augur, External, Adopted.
- Status: Unclassified, Approved, Deprecated, Blocked.
- Drift: Duplicates, Unexpected client, Missing expected export, Unclassified export.
- Client/surface: Claude, Codex, Gemini, OpenCode, Browse, AGENTS.md, MCP, CLI.

Each capability detail view should show:

- display name and stable capability id;
- owner, management, scope, type, and primary surface;
- current exposure;
- intended exposure;
- source paths;
- duplicate cluster, when present;
- recommended action;
- policy diff preview after an action is selected;
- impact summary before apply;
- link or action to open the relevant AI CLI, internal chat, or shell when supported.

Suggested actions:

- Keep only in Claude.
- Keep only in Codex.
- Keep only in Gemini.
- Keep only in OpenCode.
- Approve multi-client.
- Move to CLI only.
- Block from selected clients.
- Mark as external unmanaged.
- Adopt under Augur policy.
- Leave unclassified.

Action availability depends on owner and management. For example, "move to CLI only" is valid for Augur generated technical capabilities, but not for an unmanaged external skill folder. External items can be governed by policy and reported as drift, but Browse does not uninstall them in this phase.

## Reviewed Apply Flow

Policy writes use a three-step flow.

1. Inventory report:
   - Browse requests resolved inventory and summary counts.
   - The report groups items by owner, type, status, drift, and client exposure.
   - Duplicate clusters and high-impact Gemini/OpenCode surfaces are highlighted.

2. Policy draft:
   - User selects an action on one item or a bounded group.
   - Dashboard sends the action to MCP.
   - MCP returns a proposed YAML patch, a normalized policy entry, and an impact summary.
   - No file is written during draft.

3. Policy apply:
   - User reviews the diff and impact.
   - Dashboard sends the accepted draft id or patch fingerprint to MCP.
   - MCP validates the current policy file is still based on the same content.
   - MCP writes the policy update atomically.
   - MCP returns post-apply inventory status and verification hints.

If the policy file changed between draft and apply, the apply request fails with a stale-draft error and Browse asks for a fresh draft.

## Backend Contract

Add MCP-backed operations around the existing `src/lib/capabilities/` resolver.

### Inventory Report

Input:

- optional filters for type, owner, status, client, surface, and drift;
- optional `include_source_paths` flag for development mode.

Output:

- resolved records;
- grouped counts;
- duplicate clusters;
- drift counts;
- external unmanaged summary;
- Augur generated summary;
- Gemini/OpenCode exposure counts;
- recommended action per record where deterministic.

### Policy Draft

Input:

- action id;
- capability ids;
- action parameters such as target client or blocked clients;
- current policy revision or content hash.

Output:

- draft id or patch fingerprint;
- proposed policy entries;
- YAML diff;
- impact summary;
- affected clients and surfaces;
- expected drift changes;
- expected Gemini/OpenCode count change when relevant;
- validation errors, if the action is invalid for the selected capability.

### Policy Apply

Input:

- draft id or patch fingerprint;
- expected policy revision or content hash.

Output:

- write result;
- new policy revision or content hash;
- post-apply record summary;
- verification commands or checks;
- stale-draft error when the policy changed after draft.

The dashboard may call these operations through existing MCP request infrastructure. It must not use direct filesystem access for policy writes.

## Recommended Actions

Recommendations are deterministic hints, not automatic writes.

| Condition | Recommended action |
|---|---|
| External unmanaged skill exposed in more than one AI client | Consolidate to one client or approve multi-client. |
| External skill named like geo/location work | Prefer Claude-only unless already explicitly approved elsewhere. |
| External superpowers skill | Keep in the client that owns that runtime workflow; avoid cross-client generated duplication. |
| Augur generated MCP tool used for operational or technical maintenance | Consider CLI plus `AGENTS.md`/Browse exposure instead of direct client MCP exposure. |
| Augur command or workflow already visible through `AGENTS.md` and Browse | Usually approve those surfaces and avoid duplicating as client skill wrappers. |
| Gemini/OpenCode exposure contributes to high tool count | Prefer removal from that client unless the capability is essential there. |
| Capability has no current exposure | Leave unclassified or approve only after explicit user decision. |

The exact list of geo, superpowers, and UI/UX skills is discovered from live inventory. The design does not hardcode those names into UI code.

## Safety Rules

- Preview is the default. Applying requires a second explicit user action.
- Dashboard cannot edit policy files directly.
- MCP validates action compatibility before producing a draft.
- MCP validates policy revision before applying a draft.
- Policy writes are atomic.
- External unmanaged source paths are never deleted or rewritten.
- Existing generated exports are preserved unless the applied policy explicitly removes the target.
- Bulk actions are bounded by visible filters and require impact preview.
- Actions affecting Gemini/OpenCode show expected count changes.
- Source paths are visible before any action that could remove generated exposure.
- Failed apply leaves the previous policy file unchanged.

## Observability

Browse should surface:

- total capabilities by type;
- unclassified count;
- duplicate count;
- external unmanaged count;
- current Gemini/OpenCode exposure count;
- top duplicate clusters;
- policy drift after apply;
- last inventory refresh time;
- policy revision hash.

Development mode may include source paths, raw metadata, scanner sources, and resolver diagnostics. Operational mode should show concise labels and impacts.

## Relationship To AI CLI And Shell

Browse is also the launch point for using capabilities. This phase should connect inventory records to existing internal chat, AI CLI, and shell launch paths where already supported.

Examples:

- An external Claude-only geo skill shows "Open in Claude" when Claude CLI support exists.
- An Augur CLI-only workflow shows "Open shell" or "Run via internal chat" when the action is available.
- A blocked or unclassified capability can still show documentation, but direct generated exposure is not added.

This phase does not implement a new terminal multiplexer. It adds inventory context and launch affordances to the existing supported surfaces.

## Verification

Implementation must verify:

- resolver/report tests for grouping, duplicate clusters, and recommended actions;
- policy draft tests for each supported action;
- stale draft and invalid action tests;
- policy apply tests with atomic write behavior;
- export-filter tests showing generated clients match policy;
- dashboard state tests for owner/drift/status filters and preview flow;
- browser verification on `/browse` showing interactive load, filters, detail preview, and no client-side errors;
- Gemini/OpenCode count reporting before and after a representative policy change.

Verification should not rely on HTTP 200 alone for Browse. Browser or screenshot-capable verification is required for dashboard changes.

## Rollout

1. Add reconciliation/report layer over existing capability records.
2. Add policy draft/apply helpers and tests.
3. Expose report, draft, and apply through MCP.
4. Add Browse filters, detail impact preview, and reviewed apply UI.
5. Run a first policy cleanup batch focused on external duplicate skills and Gemini/OpenCode overload.

The first cleanup batch should be small and reviewed. It should classify representative examples across Augur and external capabilities before applying broad rules.

## Success Criteria

- Browse can show all capability inventory with owner, status, drift, and exposure filters.
- A user can draft and apply "keep only in Claude" for an external duplicate skill without direct YAML editing.
- A user can draft "move to CLI only" for an Augur generated technical capability and see the generated exposure impact before applying.
- Policy writes are reviewable in git.
- Gemini/OpenCode exposure counts are visible and can be reduced by policy.
- No external/global skill source folder is deleted by this workflow.
- Browse remains usable in both Operational and Development modes.
