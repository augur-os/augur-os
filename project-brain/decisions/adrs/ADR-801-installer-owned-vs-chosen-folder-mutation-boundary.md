---
status: Accepted
date: 2026-06-05
deciders:
  - gsannikov
related:
  - ADR-770
  - ADR-771
  - ADR-791
  - ADR-794
  - ADR-797
  - ADR-798
  - ADR-799
hub: brain
tags:
  - onboarding
  - installer
  - mutation-boundary
  - project-brain
  - open-source
  - trust
superseded_by: null
spec_file: 2026-06-04-fast-launch-open-source-design.md
plan_file: null
---

# ADR-801: Installer-Owned Writes Are Separate From Chosen-Folder Writes

## Decision summary

Fast launch reports and enforces two different write domains: installer-owned Augur setup may update Augur/client integration surfaces, while the user's chosen folder stays inventory-only except for `project-brain/` metadata unless the user explicitly approves a separate chosen-folder mutation.

## Spec

- [`docs/superpowers/specs/2026-06-04-fast-launch-open-source-design.md`](../superpowers/specs/2026-06-04-fast-launch-open-source-design.md)

## Context

ADR-797 defines inventory-only folder init. This ADR narrows the mutation reporting boundary because public launch has two kinds of writes that can otherwise sound contradictory:

1. Installers may need to install or refresh Augur itself, client integration config, plugin cache, generated Augur exports, or runtime setup state.
2. The user chose a folder that may already contain vendor files such as `AGENTS.md`, client skills, prompts, MCP config, Cursor rules, Copilot instructions, or generated profiles.

Those are not the same permission. Installing Augur does not authorize Augur to rewrite the chosen folder.

## Decision

### 1. Every launch write is classified

Fast-launch logs, CLI/MCP payloads, and dashboard setup summaries must classify writes into one of three categories:

```text
installer_owned
chosen_folder_metadata
chosen_folder_opt_in
```

`installer_owned` writes are Augur setup or integration writes outside the selected project content boundary.

`chosen_folder_metadata` writes are the default inventory-only folder writes, limited to `project-brain/` metadata and generated inventory files.

`chosen_folder_opt_in` writes are explicit post-inventory actions that can touch existing project or vendor files only after a preview and user approval.

### 2. Installer-owned writes do not grant chosen-folder permission

Installers may update:

- Augur checkout or installed package files.
- Augur plugin cache.
- Supported AI-client integration config.
- Generated Augur-owned client exports.
- MCP/client setup entries.
- Runtime setup state, logs, cache, and inventory state.

These writes do not permit adoption, rewrite, merge, cleanup, projection, or deletion inside the chosen folder.

### 3. Default chosen-folder writes stay inside `project-brain/`

Default folder init may create or update:

```text
<chosen-folder>/project-brain/
<chosen-folder>/project-brain/BRAIN.yaml
<chosen-folder>/project-brain/config/inventory/
```

It must not modify existing vendor files, instruction files, skills, prompts, MCP config, source files, or docs in the chosen folder.

### 4. Opt-in chosen-folder writes need a preview

Any workflow that writes outside `project-brain/` in the chosen folder must show:

- exact paths to be written
- whether each path is created, overwritten, merged, deleted, or projected
- source of the proposed content
- rollback or backup behavior when applicable
- approval gate before mutation

The opt-in action may be CLI, MCP, or chat-driven, but the write classification and preview requirements are the same.

### 5. Browse and chat remain read-first

Browse problem badges, detail-panel evidence, and chat action drafts can recommend next steps. They do not become mutation approval by themselves. A chat draft must ask for approval before executing any chosen-folder write.

## Non-Goals

- No full installer specification.
- No cross-client secret migration.
- No automatic cleanup of existing AI-client files.
- No broad "fix all problems" button for launch.
- No hidden dashboard process execution.

## Consequences

Positive:

- Launch copy can honestly say Augur installs itself while still saying the chosen folder is inventory-only.
- Users can inspect an existing folder without fear that Augur will rewrite vendor files.
- Future adoption/sync workflows have a clear permission model and audit trail.

Tradeoffs:

- Installer logs and UI payloads need a little more structure.
- Some users will need one extra approved step before getting cleanup or projection.
- Tests must cover byte-for-byte preservation of existing chosen-folder files.

## Verification

Acceptance requires:

- Empty folder init writes only `project-brain/` metadata and inventory.
- Existing folder init preserves pre-existing vendor files byte-for-byte.
- Installer/setup outputs label installer-owned writes separately from chosen-folder metadata writes.
- Browse and chat drafts can suggest action items but include the no-mutation approval gate.
- Any future sync/adoption command lists exact chosen-folder paths before writing them.

## Status notes

Accepted on 2026-06-05 as a launch trust boundary that refines ADR-797. It can move to `Implemented` after installer, CLI/MCP, and dashboard launch summaries consistently emit write classifications and real-data tests prove chosen-folder files are preserved.

## Related

- ADR-797: Fast launch is inventory-only folder init.
- ADR-799: Inventory problems ride existing Browse cards.
- ADR-798: Browse folder context is the primary multi-project switcher.
- ADR-794: Standard brain workspace files.
- ADR-791: Brain-scoped standard skill source.
- ADR-771: Brain client projections and write routing.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "fast-launch setup outputs classify writes as installer_owned/chosen_folder_metadata/chosen_folder_opt_in"
  patterns_deprecated:
    - "treating installer approval as permission to mutate chosen project files"
    - "unclassified launch write summaries"
  files_affected:
    - "project-brain/capabilities/skills/onboard/install.md"
    - "src/lib/brain_init.py"
    - "src/lib/ai_artifact_inventory.py"
    - "src/mcp/augur_core/tools/core/brain_discovery.py"
    - "apps/dashboard/app/(views)/browse/useBrowseState.ts"
```
