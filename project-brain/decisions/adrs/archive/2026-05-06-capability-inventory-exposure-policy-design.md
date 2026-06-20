---
title: Capability Inventory And Exposure Policy
date: 2026-05-06
status: proposed
scope: design
---

# Capability Inventory And Exposure Policy

## Purpose

Augur currently has capability blowout across AI clients: the same or similar skills, MCP servers, MCP tools, commands, and workflows can appear in several places at once. The immediate problem is not just duplicate files. It is that there is no single resolved view answering:

- what capability exists;
- who owns it;
- where it is currently exposed;
- where it is intended to be exposed;
- whether Augur generators are allowed to export it to a client.

This spec defines v1 of a hybrid capability inventory and exposure policy. Discovery remains live and scanner-driven. Intent is stored in a small policy overlay. Augur-generated exports obey the resolved policy. External and manually installed global surfaces are reported, not deleted.

The operating rule is:

> Browse shows all inventory, but only the intended execution surface gets direct generated exposure.

## Scope

V1 covers these capability types:

- skills, including Augur-owned, external, and adopted skills;
- MCP servers;
- MCP tools;
- commands and generated command wrappers;
- workflows and workflow definitions;
- Augur CLI-backed capabilities.

V1 does not include:

- the full Browse launcher or shell broker;
- active AI session monitoring;
- runtime log observability beyond drift/status fields;
- destructive uninstall of external or global skills;
- Obsidian-specific migration cleanup.

Those are follow-up specs after the inventory source of truth is stable.

## Decisions

- Use a hybrid source of truth: scanners discover current state, and a checked-in policy overlay stores intentional exposure decisions.
- Treat missing policy as `classification_status: unclassified`.
- Unclassified capabilities are visible in Browse and blocked from new Augur-generated exports.
- Existing external or manual global installs are report-only in v1.
- Enforce v1 only in Augur-managed generators: generated skill wrappers, command wrappers, plugin bundles, and generated MCP client config.
- Never delete, rename, or edit external/global capability folders from the v1 enforcement path.
- Model Augur-owned and external capabilities separately. Examples:
  - `geo-*` skills are external/unmanaged and preferred for Claude only.
  - `superpowers:*` skills are external/unmanaged and preferred for Codex only.
  - `ui-ux-pro-max` requires an explicit external/adopted decision before new Augur export.
  - Augur technical MCP tools should often resolve to CLI, AGENTS.md, or Browse-only exposure instead of direct client MCP exposure.
- Make Browse the primary user-visible inventory and drift review surface.

## Architecture

### Discovery Layer

Discovery continues to read live state from existing sources:

- repo skills under `skills/`;
- vault/user skills where configured;
- client skill folders and generated wrappers;
- MCP server config and active tool declarations;
- command sources and generated command wrappers;
- workflow definitions;
- Augur CLI manifests or command metadata.

Discovery produces factual records only. A discovered record can say "this capability is present in Claude global skills and Codex plugin cache"; it does not decide whether that is intended.

### Policy Overlay

The policy overlay stores intent and exceptions. It does not duplicate every discovered field. It records only decisions that humans or migration code should review:

- ownership;
- management model;
- preferred client or execution surface;
- allowed generated export targets;
- classification status;
- deprecation or block decisions.

The overlay lives at `config/system/capability_exposure.yaml`. This keeps exposure policy beside other system-level client and MCP configuration, versioned and reviewed like other generator policy.

### Resolver

A resolver merges discovery records with overlay decisions into normalized `CapabilityRecord` objects. Resolved records drive:

- Browse filters and details;
- duplicate and drift reports;
- generator export decisions;
- migration review lists.

The resolver is responsible for defaulting missing policy to `unclassified`, computing duplicate exposure, and identifying mismatch between current and intended state.

### Export Enforcement

Augur generators must consult resolved inventory before writing generated client surfaces.

The enforcement boundary is intentionally narrow:

- Augur-generated exports can be skipped, added, or removed according to policy.
- External/global installs are never modified by enforcement.
- Existing unmanaged duplicates are reported as drift.

This gives real reduction for Augur-owned blowout without surprising the user by deleting manually installed capabilities.

### Browse Visibility

Browse consumes resolved inventory, not raw scanner output alone. The page should show both:

- current exposure: what is installed or loaded today;
- intended exposure: what policy says should be generated or preferred.

Browse remains the human control plane for review. It can suggest cleanup, but v1 does not perform destructive cleanup.

## Data Model

### CapabilityRecord

Resolved records use these fields:

| Field | Meaning |
|---|---|
| `id` | Stable id such as `skill:geo-audit`, `mcp-tool:augur-framework/config-read`, or `command:dev-build`. |
| `type` | `skill`, `mcp-server`, `mcp-tool`, `command`, `workflow`, or `cli`. |
| `owner_kind` | `augur`, `external`, or `adopted`. |
| `management` | `generated`, `managed-policy`, or `unmanaged`. |
| `scope` | `project`, `global`, or `mixed`. |
| `primary_surface` | `skill`, `mcp`, `cli`, `command`, `workflow`, `agents_md`, or `browse_only`. |
| `preferred_client` | `claude`, `codex`, `gemini`, `opencode`, `augur`, `shell`, or `none`. |
| `export_to` | List of clients or surfaces allowed to receive generated exposure. |
| `classification_status` | `approved`, `unclassified`, `deprecated`, or `blocked`. |
| `source_paths` | Discovered files or config paths that define or expose the capability. |
| `current_exposure` | Resolved list of clients/surfaces where the capability appears today. |
| `drift` | Computed flags such as `duplicate`, `unexpected_client`, `missing_expected_export`, or `unclassified_export`. |

### Policy Overlay Example

```yaml
capabilities:
  skill:geo-audit:
    owner_kind: external
    management: unmanaged
    scope: global
    primary_surface: skill
    preferred_client: claude
    export_to: [claude]
    classification_status: approved

  mcp-server:augur-framework:
    owner_kind: augur
    management: generated
    scope: project
    primary_surface: mcp
    preferred_client: augur
    export_to: [codex]
    classification_status: approved

  workflow:loop-quality:
    owner_kind: augur
    management: generated
    scope: project
    primary_surface: cli
    preferred_client: shell
    export_to: [agents_md, browse]
    classification_status: approved
```

The overlay stores intent. The resolver computes `current_exposure`, duplicates, drift, and source paths from scanners.

## Enforcement Rules

Generators apply these rules:

| Policy state | Generator behavior |
|---|---|
| `classification_status: approved` and target in `export_to` | Export is allowed. |
| `classification_status: approved` and target not in `export_to` | Do not generate this capability for that target. |
| `classification_status: unclassified` | Show in inventory and block new generated exports. |
| `classification_status: blocked` | Do not export and show a high-severity warning if current exposure exists. |
| `classification_status: deprecated` | Do not export to new targets; show deprecation state where already present. |
| `owner_kind: external` and `management: unmanaged` | Report only; never delete or modify source. |

The generator must distinguish "skip writing this generated output" from "remove a user's manual install." V1 allows only the first.

## Browse Behavior

Browse should add filters and badges for:

- owner: Augur, External, Adopted;
- management: Generated, Managed Policy, Unmanaged;
- exposure status: Approved, Unclassified, Blocked, Deprecated;
- surface: Skill, MCP, CLI, Command, Workflow;
- client: Claude, Codex, Gemini, OpenCode, Augur, Shell.

Capability detail should show:

- current exposure versus intended exposure;
- source paths;
- duplicate installs;
- preferred execution surface;
- generator owner;
- drift warnings;
- suggested cleanup action.

Suggested cleanup actions in v1 are advisory. They do not delete external/global folders.

## Rollout

Roll out in five phases:

1. Add the resolver and policy overlay with internal report-only output.
2. Add Browse visibility and drift reporting.
3. Enforce policy for Augur-generated skill and command exports.
4. Enforce policy for generated MCP client config.
5. Run a pruning review for external/global duplicates, with explicit user approval before any uninstall.

This order prevents blind cleanup. The inventory becomes visible before generators start pruning, and generated enforcement lands before manual/global cleanup.

## Testing

Minimum verification:

- Resolver tests for discovered-only, policy-only, merged, unclassified, blocked, deprecated, duplicate, and drift states.
- Scanner tests for skills, MCP servers, MCP tools, commands, workflows, and CLI capabilities.
- Generator tests showing approved exports still appear and unclassified exports are blocked.
- Tests proving unmanaged external capabilities are never deleted or modified.
- Client output tests for Claude, Codex, Gemini, and OpenCode.
- Browse tests for filters, badges, detail fields, duplicate display, and drift display.
- Browser verification for `/browse?category=skills` plus relevant development-mode MCP/tool views.
- Regression checks for Gemini/OpenCode constraints that motivated this work: tool count limits and provider schema validity.

## Safety

- Do not remove external/global skill folders in v1.
- Do not make Obsidian migration decisions in this spec.
- Do not hide broken data behind empty fallbacks. If scanners fail, Browse should show an inventory error or stale-status warning.
- Do not hardcode local paths in the resolver or generators. Use existing path helpers and configured client adapter paths.
- Do not change dashboard execution semantics. Browse may display and route future launch intent, but v1 does not implement a direct shell or AI-client launcher.
- Do not mix this work with unrelated Gemini/OpenCode repair changes already present in the worktree.

## Open Follow-Ups

These are intentionally outside v1:

- Browse internal chat launcher and controlled shell/AI-client broker.
- Runtime session observability for active Claude/Codex/Gemini/OpenCode/shell sessions.
- Automated external/global uninstall workflows.
- Obsidian-specific migration cleanup.
- A full PC hub inventory covering arbitrary external apps and logs.
