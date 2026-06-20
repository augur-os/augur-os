---
title: "Brain Archive Git-History Purge"
date: 2026-05-14
status: draft
scope: design
authors:
  - gsannikov
related:
  - ADR-732
  - ADR-736
  - docs/superpowers/specs/2026-05-13-browse-sweep-design.md
  - shared-vault/skills/loop-hygiene/scripts/git_archive.py
  - shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py
  - shared-vault/skills/loop-hygiene/scripts/archive_index.py
tags:
  - archive
  - sweep
  - vault
  - multi-brain
  - git-history
  - loop-hygiene
---

# Brain Archive Git-History Purge

## 1. Problem

Browse Sweep can retire stale vault notes, source cards, page definitions, and
team or private skills. The current git-aware archive design moves tracked files
inside the same repository under `archive/sweep/...` and leaves them there until a
human commits or restores them.

That is recoverable, but it keeps cold payloads in the active tree. The user wants
a simpler v1 than submodules: keep archive recovery in the owning brain repo's git
history, keep a durable ledger in the active tree, and remove archived payloads
from the final working tree automatically after the archive commit has been pushed.

## 2. Goals

- Keep v1 same-repo and avoid archive submodules.
- Make archive behavior follow the owning brain repository.
- Preserve recovery through git history with explicit commit SHAs.
- Keep a machine-readable sweep ledger in the active tree.
- Delete archived payload files as part of the sweep only after the archive move
  commit has been created and pushed.
- Keep the ledger under `archive/_ledger/` and guarantee purge never removes it.
- Support private brain repos and multiple shared brain repos with the same
  archive lifecycle.
- Exclude core Augur product skills from brain archive purging.

## 3. Non-goals

- Do not introduce archive git submodules in v1.
- Do not move swept payloads into a global archive repository.
- Do not auto-purge before the archive move has been pushed.
- Do not treat purge as data destruction without recovery metadata. Recovery must
  remain explicit in the ledger.
- Do not retire core Augur product skills through brain archive. Product skills
  are governed by Augur release history, ADRs, and normal product git history.

## 4. Terms

- **Brain repo**: a git-backed vault mounted by Augur, such as a private vault or
  a team firmware vault.
- **Payload**: the swept file or directory contents that were removed from the
  active area.
- **Archive move**: the first phase, where the payload is moved under
  `archive/sweep/...`.
- **Purge**: the second phase, where the payload is deleted from `archive/sweep/...`
  after the archive move commit has been pushed.
- **Ledger**: append-only JSONL event stream under `archive/_ledger/sweep.jsonl`.

## 5. Approved V1 Shape

Each brain repo owns its own archive folder:

```text
<brain-root>/
  notes/
  skills/
  archive/
    _ledger/
      sweep.jsonl
    sweep/
      notes/<date>/...
      skills/<date>/...
```

The final post-sweep state should usually retain only:

```text
<brain-root>/
  archive/
    _ledger/
      sweep.jsonl
```

The `archive/sweep/...` payload files exist briefly during the archive move commit
and then disappear in the purge commit. Recovery uses git history.

## 6. Lifecycle

The sweep archive lifecycle is two commits and two pushes.

1. Resolve the target path to the owning brain repo.
2. Move the payload into a deterministic archive path:

   ```text
   archive/sweep/<source-tab>/<YYYY-MM-DD>/<original-relative-path>
   ```

3. Append an `archive_prepared` event to `archive/_ledger/sweep.jsonl`.
4. Commit the archive move and ledger event.
5. Push the archive commit. If push fails, stop and report that payloads remain
   present under `archive/sweep/...`.
6. Delete the archived payload paths under `archive/sweep/...`.
7. Preserve `archive/_ledger/` and `archive/_ledger/sweep.jsonl`.
8. Append a `purged` event with the pushed archive commit SHA and recovery
   instructions.
9. Commit the purge and ledger event.
10. Push the purge commit. If push fails, stop and report that the purge commit is
    local but not remote.

The load-bearing invariant is:

```text
Never delete archive payloads before the archive move commit has been pushed.
```

## 7. Ledger Model

Use append-only JSONL events, not mutable in-place records. Each logical archive
item has a stable `archive_record_id`. Browse and recovery tools fold the event
stream into the latest state.

Example `archive_prepared` event:

```json
{
  "event": "archive_prepared",
  "archive_record_id": "run123-note1",
  "brain_id": "private",
  "source_kind": "vault-notes",
  "source_tab": "notes",
  "original_path": "notes/topic/page.md",
  "archived_path": "archive/sweep/notes/2026-05-14/notes/topic/page.md",
  "reason": "superseded",
  "artifact_group": "uart-debug",
  "apply_run_id": "run123",
  "archived_at": "2026-05-14T12:00:00Z"
}
```

Example `purged` event:

```json
{
  "event": "purged",
  "archive_record_id": "run123-note1",
  "brain_id": "private",
  "archived_path": "archive/sweep/notes/2026-05-14/notes/topic/page.md",
  "archive_commit": "abc123",
  "archive_pushed": true,
  "purged_at": "2026-05-14T12:02:00Z",
  "recovery_hint": "git restore --source=abc123 -- archive/sweep/notes/2026-05-14/notes/topic/page.md"
}
```

Required `archive_prepared` fields:

- `event`
- `archive_record_id`
- `brain_id`
- `source_kind`
- `source_tab`
- `original_path`
- `archived_path`
- `reason`
- `artifact_group`
- `apply_run_id`
- `archived_at`

Required `purged` fields:

- `event`
- `archive_record_id`
- `brain_id`
- `archived_path`
- `archive_commit`
- `archive_pushed`
- `purged_at`
- `recovery_hint`

The purge commit SHA is intentionally not embedded in the purged event that it
commits. A commit cannot contain its own final SHA without an additional metadata
commit. The sweep command should report the purge commit after it is created and
pushed, and Browse can derive it from git history if needed. Recovery depends on
`archive_commit`, not on `purge_commit`.

## 8. Ownership Rules

Archive follows the owner of the swept target:

- Private vault note -> private vault `archive/`.
- Private vault skill -> private vault `archive/`.
- Shared/team vault note -> that shared brain repo's `archive/`.
- Shared/team vault skill -> that shared brain repo's `archive/`.
- Core Augur product skill -> excluded from this flow.

Augur should resolve the target to a configured brain before applying archive
behavior. It should not infer ownership only from the current global vault path.

Future multi-brain config can model each mounted repo explicitly:

```yaml
brains:
  - id: private
    path: ~/Projects/Au-vault
    git:
      remote: origin
      branch: main
    archive:
      mode: git-history-purge
      root: archive
      ledger: archive/_ledger/sweep.jsonl

  - id: firmware-team
    path: ~/Projects/Firmware-vault
    git:
      remote: origin
      branch: main
    archive:
      mode: git-history-purge
      root: archive
      ledger: archive/_ledger/sweep.jsonl
```

## 9. Recovery Semantics

Recovery is a visible git operation, not a hidden undo.

Two recovery levels are supported:

1. Restore payload to archive path:

   ```bash
   git restore --source=<archive_commit> -- <archived_path>
   ```

2. Restore payload to original active path:

   ```bash
   git restore --source=<archive_commit> -- <archived_path>
   git mv <archived_path> <original_path>
   git commit -m "restore: <summary>"
   git push
   ```

The exact recovery command should be generated from ledger fields and shown in
Browse Archive detail metadata.

## 10. Failure Handling

Failure states must be honest and resumable.

| Failure | Required behavior |
|---|---|
| Archive move fails | Leave source in place. No purge. Record refusal in command result. |
| Ledger append fails before archive commit | Roll back move or refuse before commit. |
| Archive commit fails | Leave staged/worktree state for operator review. No purge. |
| Archive push fails | Stop. Payload remains in `archive/sweep/...`. Ledger shows archive not pushed. |
| Payload delete fails | Stop after pushed archive commit. Ledger keeps recoverable archive state. |
| Purge ledger append fails | Do not commit purge. Keep payload delete state visible for operator review. |
| Purge commit fails | Do not push. Report local state. |
| Purge push fails | Report the local purge commit SHA. Recovery still uses the pushed archive commit. |

The purge operation must refuse any target outside `archive/sweep/` and must never
delete `archive/_ledger/`, `.git`, `.gitmodules`, or repository config files.

## 11. Browse Archive Behavior

Browse Archive should read `archive/_ledger/sweep.jsonl` from each configured
brain repo and fold events by `archive_record_id`.

Entries should show:

- owning brain
- source kind and source tab
- original path
- archived path
- archive commit
- purge commit when derivable or returned by the sweep command
- pushed state
- reason and artifact group
- recovery hint

A purged entry still appears in Archive. Its detail panel should make clear that
the payload is no longer present in the working tree and must be restored from git
history.

## 12. Integration Boundary

This design extends the existing loop-hygiene git-aware sweep path. It should not
replace the whole sweep classifier or Browse selection flow.

For this `git-history-purge` mode, the archive primitive intentionally supersedes
the earlier move-only assumption for git-aware sweep targets. The classifier and
selection flow still decide what should be swept; this design changes how approved
git-backed brain targets are committed, pushed, purged, and recorded.

Likely integration points:

- `shared-vault/skills/loop-hygiene/scripts/git_archive.py`: evolve from
  move-only archive to two-phase archive and purge for configured brains.
- `shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py`: route selected
  git-aware targets through the new brain archive lifecycle.
- `shared-vault/skills/loop-hygiene/scripts/archive_index.py`: read
  `archive/_ledger/sweep.jsonl` and expose purged entries as Archive records.
- Browse archive indexing: include ledger roots for every configured brain, not
  only the current project and current vault.

## 13. Testing

Focused tests should cover:

- archive move commit happens before purge delete;
- purge refuses before archive push proof;
- `archive/_ledger/sweep.jsonl` is preserved during purge;
- purge only deletes under `archive/sweep/`;
- failed archive push leaves payload present and recoverable;
- failed purge push reports local-only purge state;
- private brain and shared brain targets route to the correct owning repo;
- core Augur product skills are refused;
- Browse Archive folds archive_prepared and purged events into one record;
- recovery hints use the archive commit SHA and archived path.

## 14. Decision

Adopt `git-history-purge` as the v1 brain archive mode. Each brain repo keeps an
`archive/` folder with permanent `archive/_ledger/sweep.jsonl`, temporarily stores
swept payloads under `archive/sweep/...`, pushes the archive move, then deletes
the payload in a purge commit. Submodules remain a future optimization for large
archives or stricter storage isolation.
