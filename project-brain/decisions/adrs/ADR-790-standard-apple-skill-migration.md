---
status: Implemented
date: 2026-05-29
deciders:
  - gsannikov
related:
  - ADR-080
  - ADR-158
  - ADR-421
  - ADR-423
  - ADR-424
  - ADR-435
  - ADR-735
  - ADR-788
  - ADR-789
hub: life
tags:
  - skills
  - apple
  - hermes
  - standard-skills
  - migration
  - reactive
  - local-first
superseded_by: null
spec_file: 2026-05-29-standard-apple-skill-migration-design.md
plan_file: 2026-05-29-standard-apple-skill-migration.md
---

# ADR-790: Standard Apple Skill Migration

## Decision summary

Augur will replace its Augur-shaped staged Apple skill with a 100% standard, Hermes-compatible Apple skill while moving Augur-specific MCP, dashboard, sync projection, and governance behavior into an external adapter layer.

## Status notes

Proposed on 2026-05-29 after comparing the staged Augur Apple skill with NousResearch Hermes Apple skills. Backfilled with a superpowers design spec on 2026-05-29 so ADR-790 follows the `/adr write` rule that every ADR write has a spec. Implementation plan added on 2026-05-29.

Implemented on 2026-05-29. The canonical standard Apple bundle now lives at `~/Projects/Au-vault/capabilities/skills/apple` with portable subskills for Notes, Reminders, Calendar, Voice Memos, Find My, iMessage, and macOS computer use. The canonical source has no `x-augur-*` metadata, no Augur imports, and no hosted LLM dependency. Apple Mail moved to the project ingest skill through `email_adapters.py`, `email_apple_mail.py`, and `email_live_consume.py`. Augur projection support now discovers standard bundle subskills through `standard_skill_projection.py`, approves the Apple subskills in capability exposure policy, and projects them into generated local client skill folders without modifying the private Apple source.

Local verification on this machine found `imsg`, `memo`, `osascript`, `peekaboo`, `remindctl`, `swift`, and `whisper` available. Real-data checks returned local Notes, Reminder lists, Calendar events, an empty-but-readable Apple Mail `Augur` mailbox result, and no accessible Voice Memos files in the default recordings folder. Focused and relevant broad tests passed; pytest still emits unrelated cleanup warnings for stale temporary `.codex/skills/ask` directories.

## Context

Augur currently has a staged Apple skill under the private vault draft staging area. It is useful, but it mixes several responsibilities:

- Apple domain logic: Notes, Reminders, Calendar, Apple Mail, voice memos, screenshots, and macOS automation.
- Augur integration: `x-augur-*` metadata, dashboard blocks and pages, action/modal declarations, MCP tool wrappers, and Augur path helper imports.
- Sync implementation: vault-to-Apple Notes and vault-to-Apple Reminders sync engines, conflict handling, state snapshots, and tests.
- Demo/workflow logic: inbox triage, quick capture, voice transcription, reminders routing, and local action wiring.

Hermes takes a different shape. Its Apple skill is a portable collection of normal agent skills such as Apple Notes, Apple Reminders, Find My, iMessage, and macOS computer use. These skills are not authored as Augur plugins. They describe local CLI and device operations directly and can make sense outside Augur.

The migration goal is therefore not to paste Hermes instructions into an Augur-specific skill. The goal is to prove the product claim that Augur can run, govern, and project standard skills without requiring authors to write Augur-shaped capabilities.

The user constraint is explicit:

- Apple, email, and note-taking skills should stay standard.
- New skills must obey Augur's reactive architecture.
- New skills must not use hidden or external LLM calls.
- It is acceptable for skills to install and call new local CLIs on the device.
- Email and note-taking migration can proceed through the already agreed boundaries: email belongs to ingest/Brain Inbox, and note-taking belongs to the vault/Obsidian layer.

This ADR focuses on Apple.

## Decision

### 1. Make The Canonical Apple Skill 100% Standard

The canonical Apple skill must be portable and understandable without Augur.

It must not require:

- `x-augur-*` frontmatter fields
- Augur dashboard YAML
- Augur MCP wrapper modules
- imports from `src.config.paths`
- Augur-specific generated client directories
- hardcoded Augur project, vault, runtime, log, or cache paths

The canonical shape should follow a Hermes-compatible standard skill layout:

```text
apple/
  DESCRIPTION.md
  apple-notes/SKILL.md
  apple-reminders/SKILL.md
  apple-calendar/SKILL.md
  voice-memos/SKILL.md
  findmy/SKILL.md
  imessage/SKILL.md
  macos-computer-use/SKILL.md
  scripts/
  references/
  tests/
```

`apple-calendar` and `voice-memos` are not deferred. They are migrated as standard Apple subskills if they remain in scope.

### 2. Treat Hermes As The Behavioral Baseline

Hermes Apple skills supply the behavioral model:

- Apple Notes uses a local notes CLI such as `memo` for normal create, search, edit, delete, move, and export workflows.
- Apple Reminders uses `remindctl` with JSON output where possible.
- Find My and macOS computer-use flows use local UI automation and screenshots as observable device operations.
- iMessage operations require explicit user confirmation before sending.

Augur may add local scripts or adapters only when they remain standard and portable. A script may be included in the standard Apple skill when it depends only on macOS, local CLIs, standard configuration, and explicit user permissions.

### 3. Move Augur Integration To Projection, Not Canonical Skill Source

Augur-specific behavior moves outside the canonical skill:

```text
standard Apple skill
  -> Augur skill scanner/importer
  -> Augur projection/adapters
  -> MCP tools, dashboard actions, Browse cards, client exports
```

The projection layer may generate or maintain:

- MCP tool wrappers
- dashboard blocks and actions
- capability exposure metadata
- skill health and trust findings
- Browse metadata
- generated client skill exports
- Augur runtime state and cache pointers

Those artifacts must not become required source files inside the canonical standard Apple skill.

### 4. Preserve Only Portable Logic From The Old Staged Skill

The migration may salvage old Apple implementation only after each piece passes a portability check.

Keep or rewrite as standard:

- Reminders sync algorithms, if they can run from normal file paths and local config.
- Apple Notes sync concepts, if backed by a portable local CLI path instead of Augur-only MCP contracts.
- Calendar/EventKit helpers as `apple-calendar`.
- Voice memo listing and local transcription as `voice-memos`.
- AppleScript timeout and permissions handling.
- Tests that validate CLI contracts and local file transformations.

Do not keep as canonical skill source:

- `x-augur-*` metadata
- dashboard blocks, pages, modals, and action declarations
- Augur MCP registration files
- direct imports from Augur repo modules
- Augur inbox markers as the default Apple Notes model
- Apple Mail intake inside the Apple skill

Apple Mail moves to the email/ingest boundary as a local feeder into Brain Inbox.

### 5. Enforce Reactive And Local-Only Execution

The standard Apple skill may install and call local CLIs on device. Examples include:

- `memo`
- `remindctl`
- `imsg`
- `peekaboo`
- local Whisper CLI or another on-device transcription command
- Swift/EventKit helpers
- `osascript`

The standard Apple skill must not embed hidden provider calls or external LLM calls. It must not require OpenAI, Anthropic, Google, or other hosted model APIs for normal operation.

Agent judgment stays in the active AI client. Skill scripts and Augur MCP tools should perform deterministic local operations: read, list, create, update, delete, transform, validate, probe, and return structured output. If a workflow needs reasoning, the skill should expose the local evidence and instructions; the AI client reasons over that evidence.

### 6. Approval-Gate Destructive And Outbound Actions

The standard Apple skill must mark or document sensitive actions clearly:

- sending iMessages
- deleting notes
- deleting reminders
- completing reminders in bulk
- moving or archiving user content
- capturing screenshots of private UI
- reading location-related Find My data

Augur's projection layer must preserve those safety boundaries when exposing the skill through MCP, dashboard actions, or generated client exports.

### 7. Integrate With Skill Supply-Chain Guardrails

This migration must align with ADR-788 and ADR-789:

- imported Hermes-derived content records upstream provenance
- local CLI dependencies are declared
- required authorities are explicit
- projection fails or flags when authority metadata and observed behavior disagree
- no runtime sandboxing is claimed unless implemented by a separate enforcement layer

This ADR does not implement a public registry, signing, provenance, or runtime sandbox. It uses the guardrail direction to keep adopted skills honest.

## Consequences

### Positive

- Augur proves it can consume and govern standard skills instead of requiring proprietary skill authoring.
- The Apple skill becomes easier to compare with Hermes and other agent ecosystems.
- Augur-specific behavior becomes an adapter/projection concern, which reduces lock-in.
- Local CLI use stays compatible with offline and AI PC positioning.
- The old staged Apple work is not discarded blindly; portable logic and tests can be salvaged.

### Negative

- The migration is more work than simply copying the staged Apple skill into the private vault.
- Existing dashboard and MCP surfaces cannot be treated as canonical skill source anymore.
- Some staged behavior may need to be rewritten because it imports Augur modules or assumes Augur paths.
- Projection generation must become strong enough to recover the user experience previously embedded in the skill.

### Neutral

- Email and note-taking are intentionally separated: Apple Mail feeds ingest/Brain Inbox, while Obsidian/note-taking folds into the vault layer.
- Local CLI installation is allowed, but every dependency must be declared and probed.
- This ADR changes the skill source boundary, not the broader runtime trust model.

## Implementation Order

### Phase 1: Inventory And Classification

1. Inventory Hermes Apple subskills and staged Augur Apple files.
2. Classify each staged file as standard portable logic, Augur projection logic, ingest/email logic, vault/note-taking logic, or discard.
3. Produce a migration matrix with keep/rewrite/drop decisions.
4. Record local CLI dependencies and authority classes for each subskill.

### Phase 2: Canonical Standard Apple Skill

1. Create the standard Apple skill layout.
2. Import or adapt Hermes Apple Notes and Apple Reminders instructions.
3. Add `apple-calendar` and `voice-memos` as standard subskills using portable local scripts only.
4. Add optional Find My, iMessage, and macOS computer-use subskills with explicit safety gates.
5. Remove Augur metadata from the canonical skill source.

### Phase 3: Portable Script Migration

1. Rewrite portable reminders sync logic to use skill-local config and normal paths.
2. Rewrite Apple Notes sync only if a local CLI path provides reliable structured behavior.
3. Move Apple Mail code into ingest/Brain Inbox feeder scope.
4. Keep local transcription and EventKit helpers only when they do not import Augur modules.
5. Add CLI probes for every dependency.

### Phase 4: Augur Projection Layer

1. Teach Augur's scanner/importer to recognize the standard Apple skill layout.
2. Generate Augur-facing MCP wrappers and dashboard/action metadata outside the canonical skill.
3. Preserve safety annotations for read-only, destructive, idempotent, and outbound actions.
4. Surface trust, dependency, and authority findings through existing Browse and skill health mechanisms.

### Phase 5: Verification Against Real Data

1. Verify Notes operations against a real test Apple Notes folder or a documented dry-run mode when local permissions are unavailable.
2. Verify Reminders operations against a real test Reminders list.
3. Verify Calendar listing against the user's local Calendar permissions.
4. Verify voice memo listing/transcription against a real local recording or fixture explicitly marked as local test media.
5. Verify generated Augur projection produces usable MCP/dashboard/client surfaces without modifying the canonical standard skill.

## Alternatives Considered

### Alternative 1: Keep The Staged Augur Apple Skill And Paste Hermes Logic Into It

Rejected. This preserves the fastest path to existing MCP/dashboard behavior, but it weakens the product claim. The skill remains Augur-proprietary because authors must understand `x-augur-*` metadata, Augur paths, and MCP/dashboard wiring to author the canonical source.

### Alternative 2: Drop All Staged Apple Code And Use Hermes Unmodified

Rejected. Hermes provides a strong behavioral baseline, but it does not include all Augur-relevant Apple surfaces such as Calendar, voice memos, sync state, conflict handling, and Augur projection requirements. Using Hermes unmodified would lose useful tested local integration logic and would not prove Augur can project standard skills into its control plane.

### Alternative 3: Keep Calendar And Voice Memos As Augur-Only Extensions

Rejected. The user explicitly does not want Apple behavior split into "standard Hermes" and "Augur proprietary" parts. Calendar and voice memos should either become standard Apple subskills or be removed from Apple scope; they should not justify keeping a proprietary Apple skill.

## References

- ADR-080: Apple Hardening
- ADR-158: Seamless Note Editing Integration
- ADR-421: Apple Reminders Bidirectional Sync
- ADR-423: Remote Control via Apple Reminders
- ADR-424: Apple Notes Bidirectional Sync Adapter
- ADR-435: Unified Attention System with Apple Reminders Sync
- ADR-735: Enterprise Policy Mode
- ADR-788: Augur Skill Supply-Chain Guardrails
- ADR-789: Trusted Skill Registry And Runtime Trust Model
- NousResearch Hermes Apple skills: <https://github.com/NousResearch/hermes-agent/tree/main/skills/apple>
- Augur architecture LLM boundary: `docs/agent-topics/ARCHITECTURE.md`

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: ~/Projects/Au-vault/drafts/staging/r1/skills/apple
      to: ~/Projects/Au-vault/capabilities/skills/apple
      note: "Target path only if implementation promotes the standard Apple skill into the private vault."
  apis_changed:
    - "Apple skill canonical source no longer exposes Augur MCP/dashboard metadata directly."
    - "Augur projection/scanner must generate MCP/dashboard/client surfaces from standard skill source."
  patterns_deprecated:
    - "Authoring canonical skills with required x-augur-* metadata."
    - "Putting Apple Mail intake inside the Apple skill instead of ingest/Brain Inbox."
    - "Treating dashboard YAML and MCP wrappers as canonical skill source."
    - "Embedding hidden external LLM/provider calls in skill scripts."
  files_affected:
    - "~/Projects/Au-vault/drafts/staging/r1/skills/apple/"
    - "~/Projects/Au-vault/capabilities/skills/apple/"
    - "~/Projects/Au-vault/capabilities/skills/vault/"
    - "~/Projects/Au-vault/drafts/staging/r1/skills/ingest/"
    - "project-brain/capabilities/skills/ai/scripts/sync_agents/"
    - "project-brain/capabilities/skills/plugin-pack/"
    - "project-brain/capabilities/skills/auto-skill-quality/"
    - "config/system/capability_exposure.yaml"
    - "docs/generated/skill-manifest.json"
    - "docs/architecture-skills.md"
```

## Implementation Prompt

Use this ADR to implement the standard Apple skill migration. Work in an isolated implementation worktree unless the active session already owns one. Preserve unrelated user changes.

### Team

- architect: owns migration boundary, file classification, and projection contract
- developer: migrates standard Apple skill source and portable scripts
- integration engineer: implements Augur projection/adapters outside canonical skill source
- security reviewer: checks authority, destructive actions, provider-call absence, and supply-chain metadata
- validator: runs real-data checks and confirms standard skill portability

### Tasks

1. Inventory Hermes Apple and staged Augur Apple files.
   - Model tier: medium
   - Dependencies: none
   - Output: migration matrix with keep/rewrite/drop decisions
2. Create standard Apple skill source.
   - Model tier: medium
   - Dependencies: task 1
   - Output: portable `apple/` skill layout with subskills and local dependency docs
3. Migrate portable local logic.
   - Model tier: high
   - Dependencies: task 2
   - Output: standard scripts/tests for Notes, Reminders, Calendar, and voice memos without Augur imports
4. Move non-Apple boundaries.
   - Model tier: medium
   - Dependencies: task 1
   - Output: Apple Mail routed to ingest/Brain Inbox, note-taking routed to vault
5. Build Augur projection/adapters.
   - Model tier: high
   - Dependencies: tasks 2 and 3
   - Output: generated MCP/dashboard/client projection outside canonical skill source
6. Add guardrails and verification.
   - Model tier: high
   - Dependencies: tasks 3 and 5
   - Output: authority metadata, dependency probes, no external LLM checks, destructive-action safety annotations, real-data validation report

### Parallelism

Tasks 3 and 4 may run in parallel after task 2 if they touch disjoint files. Task 5 must wait for canonical skill structure to stabilize. Task 6 must run last.

### Completion Gate

Do not mark the ADR Implemented until:

- the canonical Apple skill can be read and used without Augur-specific metadata
- Augur projection is generated outside the canonical skill source
- Notes, Reminders, Calendar, and voice memo flows are represented as standard subskills or explicitly removed
- Apple Mail is outside Apple skill scope
- no hidden external LLM/provider call exists in the skill runtime path
- local CLI dependencies are declared and probed
- destructive and outbound actions require explicit user approval
- verification uses real local Apple data or a clearly labeled local test fixture where OS permissions block live access
