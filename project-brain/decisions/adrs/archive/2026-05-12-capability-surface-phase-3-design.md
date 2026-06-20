---
title: "Capability Surface Phase 3: Cleanup Closure, Drift Guardrails, and Browse Control Hub"
date: 2026-05-12
status: accepted
scope: design
related:
  - ADR-635
  - ADR-638
  - ADR-728
---

# Capability Surface Phase 3: Cleanup Closure, Drift Guardrails, and Browse Control Hub

## Purpose

ADR-635 established the capability inventory and exposure policy. ADR-638 made Browse the control-plane direction for reviewing capability exposure. The broad cleanup pass reduced direct client/MCP exposure and classified most capabilities, but the remaining risk is operational: without a final closure phase, duplicated skills, generated wrappers, MCP tools, CLI entries, and stale staged leftovers can drift back into Claude, Codex, Gemini, OpenCode, AGENTS.md, and Browse.

Phase 3 closes that loop. It defines the remaining cleanup, the guardrails that prevent future blowout, and the Browse behavior that lets the user understand and operate the machine from one place.

The operating rule remains:

> Policy is the intended state, scanners are the observed state, Browse is the user-facing control hub, and generators must not recreate capability blowout.

## Current State

The live policy is no longer empty. `config/system/capability_exposure.yaml` contains hundreds of classified capability entries. Most Augur technical capabilities now prefer `cli`, `agents-md`, and `browse` instead of direct broad MCP exposure. Direct MCP/client exposure is intentionally smaller than the full inventory.

What remains is not another broad classification pass. It is the closure layer:

- prove the reduced generated surfaces stay reduced;
- finish handling duplicate external/global skill exposure;
- keep stale staged/draft leftovers visible only where they belong;
- add drift checks so new generated exports cannot quietly re-expand;
- make Browse the practical PC hub for current state, intended state, launch, and cleanup review.

## Goals

- Close remaining duplicate skill, MCP, CLI, command, and workflow exposure across supported AI clients.
- Preserve a single inventory across Augur-owned, external, adopted, and user-owned capabilities.
- Keep unmanaged external/global folders report-only unless an explicit cleanup action is approved.
- Make generated Augur exports strictly policy-derived.
- Add guardrails that catch future direct MCP/client blowout before it lands.
- Make Browse the human-facing "bashrc/control hub" for capability observability, launch, and reviewed policy actions.
- Keep staged or draft leftovers visible in the Draft tab, not as active dashboard or generated-client surfaces.
- Provide a clean new-session implementation boundary.

## Non-Goals

- Do not re-open the unrelated system-config integrity work.
- Do not physically delete unmanaged external/global skills without explicit user approval.
- Do not build a new terminal multiplexer.
- Do not make dashboard code edit `capability_exposure.yaml` directly.
- Do not require every external capability to be adopted by Augur.
- Do not hide scanner failures with empty fallbacks.
- Do not split Augur and external inventory into separate pages.

## Decision

Adopt a single Phase 3 ADR with three coordinated tracks:

1. **Cleanup Closure** finishes the remaining reduction work.
2. **Drift Guardrails** makes the reduction durable.
3. **Browse Control Hub** gives the user one operational place to inspect, launch, and manage capability exposure.

These tracks are one architectural decision because each depends on the others. Cleanup without guardrails regresses. Guardrails without Browse are opaque. Browse without cleanup and policy enforcement becomes another inventory viewer instead of a control hub.

## Track 1: Cleanup Closure

Cleanup starts from live scanners and the policy overlay. It must classify the difference between current exposure and intended exposure before changing anything.

Required scan dimensions:

- external/global skills duplicated across clients;
- Augur-generated skill wrappers still present where policy says blocked, CLI-only, AGENTS.md-only, or Browse-only;
- MCP tools directly exposed to AI clients where policy says CLI, AGENTS.md, Browse, or dashboard MCP only;
- generated command wrappers duplicated as skills when AGENTS.md and Browse are sufficient;
- stale staged, draft, or migration leftovers that should appear only in Browse Drafts;
- client-specific generated surfaces for Claude, Codex, Gemini, OpenCode, and any enabled adjacent clients.

Cleanup rules:

- Augur-generated files may be removed or regenerated according to policy.
- External unmanaged source folders are report-only until a user-approved cleanup action exists.
- Adopted external capabilities must have explicit `owner_kind: adopted` and a managed policy entry before Augur modifies generated exposure.
- Blocked capabilities must not be regenerated into clients.
- Draft/staged leftovers must not appear as active hubs, tabs, dashboards, or client skills.
- Cleanup batches must report what changed by capability id, owner, management model, and client/surface.

Representative decisions from prior cleanup remain valid:

- external geo/location skills should default to Claude-only unless policy explicitly approves other clients;
- superpowers-style external runtime skills should stay in the client that owns that workflow, not be cloned into every client;
- Augur operational and technical MCP tools should generally prefer CLI plus AGENTS.md/Browse over broad direct MCP exposure;
- Gemini and OpenCode should be protected from broad generated skill/tool surfaces because they are sensitive to tool-count and schema blowout.

## Track 2: Drift Guardrails

Phase 3 adds a repeatable drift report and thresholds that keep the cleanup from decaying.

The drift report merges:

- discovered current exposure from scanners;
- intended exposure from `config/system/capability_exposure.yaml`;
- generated client outputs;
- MCP runtime/server/tool exposure;
- AGENTS.md/CODEX/Claude/Gemini/OpenCode generated instruction surfaces;
- Browse category and Draft-tab visibility.

Guardrail dimensions:

| Dimension | Failure or warning condition |
|---|---|
| Direct MCP exposure | New Augur-generated direct MCP export without policy allowing `mcp`. |
| Unclassified export | Any generated client export for `classification_status: unclassified`. |
| Blocked present | Any Augur-generated surface for `classification_status: blocked`. |
| Unexpected client | Capability appears in a generated client surface not listed in `export_to`. |
| Duplicate external skill | External unmanaged skill appears in more than one client without explicit multi-client approval. |
| Draft leakage | Staged/draft leftover appears outside Browse Drafts or approved docs. |
| AGENTS drift | Generated AGENTS.md capability table disagrees with policy. |
| Gemini/OpenCode blowout | Direct generated tool/skill count increases beyond the configured budget. |

The guardrail should fail for Augur-generated regressions and warn for unmanaged external drift. This distinction matters: Augur controls its generated outputs, but should not mutate a user's manual external installs without approval.

Guardrails belong in tests or auto-loops that can run in a new session without a browser. Browse UI verification remains separate and must use a real browser when UI changes land.

## Track 3: Browse Control Hub

Browse becomes the user's practical control hub for capability exposure. It is still one unified inventory, not separate Augur and external pages.

Browse must show:

- owner: Augur, External, Adopted, User;
- management: Generated, Managed Policy, Unmanaged;
- status: Approved, Blocked, Deprecated, Unclassified;
- current exposure versus intended exposure;
- drift badges and duplicate clusters;
- dev versus operational mode;
- source paths in development mode;
- policy-backed primary surface and preferred client;
- last inventory refresh time and policy revision/hash;
- Draft tab entries for staged/stale leftovers.

Browse actions are reviewed and mediated:

- "Open in Claude", "Open in Codex", "Open in Gemini", "Open in OpenCode", or "Open shell" appear only when the supported launcher path exists.
- "Move to CLI only", "Keep only in Claude", "Block from Gemini/OpenCode", "Approve multi-client", "Mark unmanaged external", and "Adopt under Augur policy" are draft/apply policy actions.
- Dashboard must call MCP or existing CLI/action infrastructure for draft/apply. It must not write policy files directly.
- Any action that could remove generated exposure shows an impact preview first.
- Any action touching unmanaged external source paths requires explicit approval and remains outside automatic cleanup.

Browse is also the user-facing answer to "what is going on on this PC?" It should expose enough state to understand installed tools and generated AI-client surfaces without forcing the user to inspect shell config, client config files, MCP JSON, or generated instruction files.

## New-Session Implementation Boundary

The next session should implement this ADR in batches. It should start by refreshing live state, not by assuming the current policy counts are still accurate.

Recommended batch order:

1. Re-run capability inventory and produce a "what remains" report.
2. Add drift guardrail tests/reporting for generated Augur surfaces.
3. Close generated-surface cleanup for blocked and unexpected Augur exports.
4. Classify or report remaining external/global duplicate skills.
5. Make Draft-tab behavior explicit for staged/stale leftovers.
6. Add or harden Browse control-hub fields and actions.
7. Verify generated client outputs for Claude, Codex, Gemini, and OpenCode.
8. Run browser verification for Browse if UI changes land.

Each batch should commit a verified checkpoint. Do not mix unrelated config integrity, dashboard routing, or system YAML remediation into this work.

## Verification

Minimum verification for implementation:

- Policy parser/resolver tests still pass.
- Drift guardrail tests cover generated MCP, generated client skill wrappers, AGENTS.md capability table, blocked capabilities, unexpected clients, duplicate external skills, and Draft leakage.
- Export-filter tests prove generated outputs match `export_to`.
- Scanner/report tests show current versus intended exposure for representative Augur, external, adopted, and user-owned capabilities.
- Gemini/OpenCode exposure counts are measured before and after cleanup.
- Claude/Codex/Gemini/OpenCode generated config surfaces are inspected or tested after regeneration.
- Browse unit tests cover owner/status/drift filters, Draft tab entries, duplicate clusters, and control-hub action visibility.
- Browser verification confirms `/browse` loads interactively and the affected tabs/actions render without client errors.

## Safety

- Never delete unmanaged external/global skill folders automatically.
- Never hide scanner failures behind empty inventory.
- Never expose blocked capabilities through generated outputs.
- Never let unclassified capabilities get new generated client exposure.
- Never make dashboard direct filesystem writes for policy.
- Never use broad compatibility shims to keep stale active pages alive.
- Preserve unrelated local changes, especially user/client config changes not owned by this cleanup.

## Success Criteria

- Remaining generated capability surfaces match policy.
- Direct MCP exposure remains intentionally small and policy-backed.
- Gemini/OpenCode do not regain broad generated tool or skill exposure.
- External duplicates are either explicitly classified for one client, approved as multi-client, adopted under Augur, or reported as unmanaged drift.
- Staged/draft leftovers appear in Browse Drafts and do not create active dashboards or client skills.
- Browse answers what exists, where it is exposed, how to launch it, and what cleanup remains.
- A new session can pick up the ADR and write an implementation plan without reconstructing this discussion.
