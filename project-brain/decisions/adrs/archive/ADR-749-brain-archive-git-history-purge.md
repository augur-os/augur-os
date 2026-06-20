---
status: Implemented
date: '2026-05-14'
deciders:
- gsannikov
related:
- ADR-732
- ADR-736
hub: brain
tags:
- archive
- sweep
- vault
- multi-brain
- git-history
- loop-hygiene
superseded_by: null
spec_file: 2026-05-14-brain-archive-git-history-purge-design.md
plan_file: 2026-05-14-brain-archive-git-history-purge.md
---

# ADR-749: Brain Archive Git-History Purge

> **ADR-749 is an index file.** The substantive design lives in the linked spec, and implementation is driven by the linked plan.

## Status

Implemented.

## Context

Browse Sweep already has a git-aware path for retiring vault notes, source cards, page definitions, and user/team-owned skills. The current model moves swept git-managed payloads into `archive/sweep/...` inside the same repository and leaves them there for later manual commit or recovery.

That keeps recovery simple, but it also leaves cold payloads in the active brain tree. The user considered archive submodules and separate archive repositories, then selected a simpler v1: keep recovery in the owning brain repo's git history, keep the ledger in the active tree, and delete archived payloads only after the archive move has been committed and pushed.

The design applies to brain-owned content and brain-owned skills. Core Augur product skills remain part of the Augur repo and are retired through product git history, not through brain archive sweep.

## Decision Summary

Adopt `git-history-purge` as the v1 archive mode for brain-owned sweep targets: move payloads into `archive/sweep/...`, commit and push that archive move, then purge the payload while preserving `archive/_ledger/sweep.jsonl` with recovery metadata based on the pushed archive commit.

## Decision

### 1. Keep v1 same-repo

Do not introduce archive submodules or a global archive repository for the first implementation. Each configured brain repo owns its own archive lifecycle.

```text
<brain-root>/
  archive/
    _ledger/
      sweep.jsonl
    sweep/
      <source-tab>/<YYYY-MM-DD>/<original-relative-path>
```

The archive payload exists in `archive/sweep/...` long enough to be committed and pushed. The final active tree usually retains only `archive/_ledger/sweep.jsonl`; recovery uses git history.

### 2. Use a push-gated two-commit lifecycle

The archive lifecycle is two commits and two pushes:

1. Move swept payload into `archive/sweep/...`.
2. Append an `archive_prepared` event to `archive/_ledger/sweep.jsonl`.
3. Commit and push the archive move.
4. Only after that push succeeds, delete the archived payload under `archive/sweep/...`.
5. Append a `purged` event containing the pushed archive commit SHA and recovery hint.
6. Commit and push the purge.

The invariant is strict: never delete archive payloads before the archive move commit has been pushed.

### 3. Store recovery metadata as append-only ledger events

The ledger is append-only JSONL under `archive/_ledger/sweep.jsonl`. It records one logical `archive_record_id` across events. The `purged` event stores the pushed `archive_commit`, which is the recovery-critical value. The purge commit SHA is not embedded in the same commit that creates it; it can be reported by the sweep command or derived later from git history.

### 4. Resolve archive ownership by brain

Archive follows the owner of the swept target:

- private vault note -> private vault archive;
- private vault skill -> private vault archive;
- shared/team vault note -> that shared brain repo's archive;
- shared/team vault skill -> that shared brain repo's archive;
- core Augur product skill -> refused by this flow.

This implies a future multi-brain config where each mounted brain declares its path, git remote/branch, and archive policy.

### 5. Browse Archive reads purged entries

Browse Archive should read `archive/_ledger/sweep.jsonl` from each configured brain repo and fold `archive_prepared` plus `purged` events into one Archive record. A purged entry remains visible even though the payload is absent from the working tree; its detail panel shows the recovery command.

## Consequences

### Positive

- Avoids submodule complexity in the first implementation.
- Keeps private/team archive boundaries aligned with brain ownership.
- Keeps active brain trees light after purge while preserving recovery through git history.
- Gives Browse a stable ledger surface even after payload deletion.
- Makes destructive behavior push-gated and auditable.

### Negative

- Archived payloads still live in the brain repo's git history, so repository size can grow over time.
- Recovery requires git commands, not a simple file move from the working tree.
- The sweep flow must own commit and push behavior for this mode, which is more operationally sensitive than the current move-only git-aware archive.

### Neutral

- Archive submodules remain a possible v2 if repository size or storage isolation becomes painful.
- Purge commit SHA is operational metadata, not a required field in the ledger event itself.

## Implementation Order

1. Add brain archive policy resolution for private and shared brain repos.
2. Extend the loop-hygiene git-aware archive primitive to support `git-history-purge`.
3. Add append-only ledger event writing under `archive/_ledger/sweep.jsonl`.
4. Add commit and push gates for the archive move.
5. Add safe purge that refuses anything outside `archive/sweep/` and preserves `archive/_ledger/`.
6. Add commit and push gates for the purge.
7. Extend Browse Archive indexing to read ledger roots from every configured brain.
8. Add focused tests for push-gated deletion, ledger preservation, owner routing, product-skill refusal, failure states, and recovery hints.

## Alternatives Considered

### Archive submodule from day one

Rejected for v1. Submodules would move cold payloads out of the parent repo history, but they add checkout, commit, push, and missing-submodule UX complexity before the simpler git-history model has proven insufficient.

### One global archive repository

Rejected. A global archive repo mixes private and team ownership boundaries and makes access policy harder to reason about.

### Leave payloads in `archive/sweep/...` forever

Rejected as the target behavior. It is simple and recoverable, but it keeps cold payloads in the active brain tree. The selected lifecycle keeps recoverability while ending with only the ledger in the working tree.

## Spec (canonical)

- [docs/superpowers/specs/2026-05-14-brain-archive-git-history-purge-design.md](../superpowers/specs/2026-05-14-brain-archive-git-history-purge-design.md)

## Plan (canonical, drives `/adr implement`)

- [docs/superpowers/plans/2026-05-14-brain-archive-git-history-purge.md](../superpowers/plans/2026-05-14-brain-archive-git-history-purge.md)

## Status Notes

Proposed on 2026-05-14 after the user approved the v1 same-repo git-history purge model and explicitly chose to keep the ledger inside `archive/_ledger/` while ensuring purge never deletes it. Implementation plan written on 2026-05-14 and linked in `plan_file`.

Implemented on 2026-05-14 in commits `1cfcc7b9c`, `f8c909123`, `1951b74fa`, `0d4bd19fa`, and `02f13506a`. Verification included focused loop-hygiene regression tests, `auto-test-pytest` via the Ops wrapper, `auto-lint`, and `auto-test-dashboard`.

## Related

- ADR-732
- ADR-736
- docs/superpowers/specs/2026-05-13-browse-sweep-design.md

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated:
    - "git-aware sweep archive as move-only storage for brain-owned targets"
  files_affected:
    - "shared-vault/skills/loop-hygiene/scripts/git_archive.py"
    - "shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py"
    - "shared-vault/skills/loop-hygiene/scripts/archive_index.py"
    - "src/mcp/augur_framework/tools/infrastructure/browse/index.py"
    - "config/system/vault.yaml"
```

## Implementation Prompt

Use the canonical spec and plan above as the source of truth. Implementation should follow the plan through the repo's normal `/adr implement` workflow, including tests for push-gated purge behavior and Browse Archive ledger folding.
