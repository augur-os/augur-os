---
status: Accepted
date: 2026-06-05
deciders:
  - gsannikov
related:
  - ADR-770
  - ADR-771
  - ADR-781
  - ADR-791
  - ADR-794
  - ADR-796
hub: brain
tags:
  - onboarding
  - open-source
  - fast-launch
  - inventory
  - project-brain
  - browse
  - no-mutation
superseded_by: null
spec_file: 2026-06-04-fast-launch-open-source-design.md
plan_file: null
---

# ADR-797: Fast Launch Is Inventory-Only Folder Init

## Decision summary

Augur's public launch path is desktop-chat or script install, choose a folder, create or attach `project-brain/`, inventory AI/project artifacts read-only, and show the result in Browse without adopting, rewriting, deleting, or projecting into the chosen folder.

## Spec (canonical)

- [`docs/superpowers/specs/2026-06-04-fast-launch-open-source-design.md`](../superpowers/specs/2026-06-04-fast-launch-open-source-design.md)

## Context

The launch week direction is deliberately narrower than full onboarding. The user should not need to understand Augur's complete command catalog, skill registry, migration system, routines, or governance model before seeing value.

The first useful moment is:

1. The user starts from an AI desktop/chat client or an install script.
2. Augur asks for one folder.
3. The folder can be empty or can already contain AI-client artifacts from multiple vendors.
4. Augur creates or attaches the canonical `project-brain/` metadata folder.
5. Augur inventories existing AI/project artifacts without mutating them.
6. Browse shows the inventory through existing card surfaces and folder context filters.

This launch boundary protects user trust. Existing vendor files in the chosen folder are the user's files. Augur may observe and explain them, but it must not take ownership of them during first run.

## Decision

### 1. Public launch starts with folder init

The primary public path is:

```text
desktop AI chat prompt or install script -> choose folder -> aug init --project <folder> -> inventory -> Browse
```

Every supported launch entrypoint must converge on this same contract. Platform-specific installers may differ in prerequisite setup, but the chosen-folder behavior must not differ by client or operating system.

### 2. `project-brain/` is the metadata boundary

Initialized folders use `project-brain/` as the Augur metadata folder. Augur does not introduce a lighter `.augur/` metadata folder for launch.

For an empty folder, init creates the project-brain skeleton and records an empty inventory. For an existing folder with a valid `project-brain/`, init attaches and refreshes inventory. For an invalid `BRAIN.yaml`, init fails clearly before modifying anything else.

### 3. First-run inventory is read-only

The inventory scanner reads AI/project artifacts only. It must not scan arbitrary user documents, source dependency folders, media libraries, build outputs, or private data outside the selected folder except for already-supported global client roots needed for source attribution.

The inventory output is generated metadata at:

```text
project-brain/config/inventory/ai-artifacts.json
```

The file can be refreshed atomically. User edits to this generated inventory are outside the contract.

### 4. Chosen-folder mutation is forbidden by default

During default fast launch, Augur must not:

- adopt vendor instructions into brain-authored files
- rewrite or normalize `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `GEMINI.md`, Cursor rules, Copilot instructions, MCP configs, skills, prompts, or agent profiles
- delete stale or duplicate client files
- merge vendor skills into Augur skills
- project generated client files into the chosen folder
- run cleanup, migration, or sync over the chosen folder

Projection or adoption is explicit opt-in after inventory. The opt-in surface is separate, visible, and must say what files it will write before it writes them.

### 5. Installer-owned updates are separate from chosen-folder writes

Installers may update Augur-owned install surfaces, such as the Augur checkout, plugin cache, MCP/client integration config, generated Augur client exports, or installer state.

Those installer-owned updates do not grant permission to mutate the user's chosen project folder. The chosen folder remains inventory-only unless the user opts into a later write workflow.

### 6. Browse is the first product surface

Inventory records surface as existing Browse cards, badges, filters, and detail-panel metadata. The launch does not create a separate inventory-only app, bespoke problem page, or parallel command dashboard.

Browse must support folder context so the user can distinguish personal/global/project artifacts and switch between registered project folders.

## Non-Goals

- No public skill registry or marketplace.
- No supply-chain trust expansion beyond recording inventory warnings.
- No automatic skill adoption or projection sync.
- No team-brain governance.
- No migration wizard for all existing client artifacts.
- No broad dashboard redesign.
- No new top-level slash commands for launch.

## Consequences

Positive:

- The launch story is simple enough to explain in one prompt.
- Existing folders are safe to try because first-run writes are constrained to `project-brain/`.
- Browse becomes the proof surface for value, not a setup checklist.
- Future adoption and cleanup workflows get real inventory data without being smuggled into first run.

Tradeoffs:

- Users who want immediate cleanup or projection need a second explicit step.
- Inventory-only can expose duplicate or stale artifacts without fixing them immediately.
- The installer must be careful to distinguish Augur-owned writes from chosen-folder writes in logs and UI copy.

## Verification

Acceptance requires real-data proof, not only tests:

- Empty folder init creates `project-brain/`, registers the project, and reports inventory count `0`.
- Existing folder init preserves existing AI-client files byte-for-byte while creating or attaching `project-brain/`.
- Real Augur checkout inventory reports actual artifacts such as agent profiles, instruction files, skill folders, and MCP/client config.
- Browse shows inventory records as normal cards with project root, brain id, vendor/client, artifact type, generated/source/unknown classification, and warnings.
- Browse folder context can distinguish Personal, Current Project, All Projects, and named project folders when more than one project is registered.
- Default init does not run projection sync. Sync/adoption requires explicit opt-in and separate verification.

## Status notes

Accepted on 2026-06-05 to lock the open-source launch boundary before writing follow-up ADRs for Browse folder context and command/project/private split.

## Related

- ADR-770: Project-brain physical migration.
- ADR-771: Brain client projections and write routing.
- ADR-781: Harness layering and capability merge across global/user/project brains.
- ADR-791: Brain-scoped standard skill source.
- ADR-794: Standard brain workspace files.
- ADR-796: Canonical `/dev <verb>` command surface.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "aug init --project <folder>: default behavior is inventory-only for the chosen folder"
    - "brain-init MCP tool: default chosen-folder behavior is inventory-only"
  patterns_deprecated:
    - "treating first-run onboarding as broad setup before showing Browse value"
    - "mutating existing vendor files during default project init"
  files_affected:
    - "project-brain/capabilities/skills/onboard/install.md"
    - "docs/superpowers/specs/2026-06-04-fast-launch-open-source-design.md"
    - "src/lib/brain_init.py"
    - "src/lib/brain_manifest.py"
    - "src/lib/ai_artifact_inventory.py"
```
