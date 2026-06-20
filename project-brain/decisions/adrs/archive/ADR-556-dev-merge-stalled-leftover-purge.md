---
status: Implemented
date: '2026-04-20'
deciders:
- Gur Sannikov
related:
- ADR-101
- ADR-195
- ADR-404
hub: command
tags:
- dev-merge
- worktrees
- cleanup
- salvage
- purge
superseded_by: null
implemented_date: '2026-04-15'
implementation_commits:
- c92f7532dc
- 354499d0c3
---

# ADR-556: Dev-Merge Stalled Leftover Purge

## Context

`/dev-merge` already has a salvage-first contract for merging useful work and cleaning up completed branches/worktrees. Stalled leftovers can still accumulate when a worktree was abandoned, its useful commits already landed elsewhere, or the only remaining dirt is generated or operational residue.

A cleanup mode is useful only if it cannot delete meaningful work. The system must prove that no merge-worthy commits remain and that any dirty paths are explicitly technical leftovers.

## Decision

Add `/dev-merge --purge` as a technical-leftovers-only cleanup mode. It scans leftover worktrees and branches, classifies commit state, classifies dirty paths, and removes a leftover only when all safety checks pass.

A leftover is purgeable only when:

- commit classes contain no `clean_salvage`, `unknown`, or unproven work
- dirty paths are all `technical_leftover`
- the branch/worktree can be removed as one unit

Meaningful repo files, docs, tests, source changes, skill changes, dashboard pages, ADRs, and ambiguous paths block purge. The command reports exact skip reasons instead of guessing from age or branch name.

## Consequences

Positive:

- Stale generated/client-local worktree residue can be removed without manual branch archaeology.
- `/dev-merge` keeps its salvage-before-discard rule.
- Purge decisions are explainable through structured statuses.
- Codex thread state is repaired when removed worktrees were referenced by session metadata.

Negative:

- The purge allowlist must stay conservative and deliberately maintained.
- Some leftovers that are probably safe will still be skipped when evidence is incomplete.

Neutral:

- `--purge` does not replace normal merge, salvage, or conflict handling.
- The main checkout is never purgeable.

## Implementation Evidence

Key implementation files:

- `skills/platform-admin/scripts/dev_merge_purge.py`
- `skills/platform-admin/commands/dev-merge.md`
- `docs/agent-topics/WORKFLOWS.md`
- `docs/agent-topics/agent-rules.md`

Representative tests:

- `skills/platform-admin/augur/tests/test_dev_merge_purge.py`
- `skills/platform-admin/augur/tests/test_dev_merge_docs.py`
- `skills/platform-admin/augur/tests/test_codex_thread_state.py`

## Alternatives Considered

### Purge Branches Based On Age

Rejected. Age does not prove that work is stale or already salvaged.

### Delete Dirty Worktrees After Commits Are In Main

Rejected. Dirty paths may contain meaningful uncommitted work. Commit equivalence alone is insufficient.

### Leave Leftovers For Manual Cleanup Only

Rejected. That preserves clutter and contradicts `/dev-merge`'s no-leftovers workflow when safe proof exists.

## References

Absorbed transient artifacts:

- `docs/superpowers/specs/2026-04-15-dev-merge-purge-stalled-leftovers-design.md`
- `docs/superpowers/plans/2026-04-15-dev-merge-purge-stalled-leftovers.md`

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - skills/platform-admin/commands/dev-merge.md: documents --purge behavior
patterns_deprecated:
  - leaving safe stale worktree leftovers for manual cleanup
files_affected:
  - skills/platform-admin/scripts/dev_merge_purge.py
  - skills/platform-admin/commands/dev-merge.md
  - docs/agent-topics/WORKFLOWS.md
  - docs/agent-topics/agent-rules.md
  - skills/platform-admin/augur/tests/test_dev_merge_purge.py
  - skills/platform-admin/augur/tests/test_dev_merge_docs.py
  - skills/platform-admin/augur/tests/test_codex_thread_state.py
```
