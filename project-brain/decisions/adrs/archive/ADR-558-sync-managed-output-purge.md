---
status: Implemented
date: '2026-04-20'
deciders:
- Gur Sannikov
related:
- ADR-186
- ADR-404
- ADR-430
- ADR-555
hub: command
tags:
- sync-agents
- purge
- clients
- cleanup
- generated-artifacts
superseded_by: null
implemented_date: '2026-04-15'
implementation_commits:
- aef9d14690
- ed3b33497a
- 0347473bee
- 7a6cb2916b
- f5442ecdac
---

# ADR-558: Sync Managed Output Purge

## Context

Augur writes generated files into several AI client surfaces. Before this decision, removing Augur from those surfaces required manual cleanup across project-local files, global client directories, generated MCP configs, plugin-pack installs, and orphaned exports from clients that might no longer be enabled.

That made uninstall, reset, and failed-sync recovery risky. Users needed a dry-run-first command that showed exactly which Augur-managed outputs would be removed and that kept user-owned client settings out of scope.

ADR-555 later added `sync all --purge-state` for supported client runtime state. This ADR records the earlier and narrower `sync all --purge` decision: delete Augur-managed generated outputs, not client-owned state.

## Decision

Add `sync all --purge` to the sync-agents CLI as a dry-run-first managed-output cleanup mode. Without `--confirm`, it reports the files, directories, and surgical config edits that would be applied. With `--confirm`, it executes the deletion/edit pass.

The implementation reuses adapter ownership. Each adapter declares the artifacts it manages through `get_managed_files()` and implements client-specific cleanup where a simple file delete would be unsafe. The command iterates all adapters, including disabled or orphan surfaces, because disabled clients can still contain old Augur-generated files.

The cleanup contract is intentionally separate from state cleanup:

- `cleanup(dry_run=...)` removes Augur-managed generated outputs.
- `cleanup_state(dry_run=...)` removes supported client runtime state from ADR-555.

## Consequences

Positive:

- Users can inspect Augur client cleanup before deleting anything.
- Augur-managed exports have one cleanup surface instead of scattered manual instructions.
- Adapter-local cleanup keeps ownership close to client-specific file knowledge.
- JSON/config files with mixed ownership can be edited surgically instead of deleted.

Negative:

- Every new adapter must maintain an accurate managed-output list.
- The purge report is only as complete as adapter ownership metadata.

Neutral:

- `sync all --purge` does not remove client conversation history, caches, or runtime state. That is handled by ADR-555's `--purge-state`.
- Missing files are skipped so repeated cleanup remains idempotent.

## Implementation Evidence

Key implementation files:

- `skills/ai/scripts/sync_agents/__init__.py`
- `skills/ai/scripts/sync_agents/modes.py`
- `skills/ai/scripts/sync_agents/adapters/base.py`
- `skills/ai/scripts/sync_agents/adapters/cursor.py`
- `skills/ai/scripts/sync_agents/adapters/opencode.py`
- `skills/ai/scripts/sync_agents/adapters/codex.py`
- `skills/ai/scripts/sync_agents/adapters/claude_code.py`
- `skills/ai/scripts/sync_agents/adapters/cowork.py`
- `tests/sync_agents/test_purge.py`
- `skills/ai/commands/sync-agents.md`

Representative behaviors:

- `sync all --purge` routes to `purge_mode(dry_run=True)`.
- `sync all --purge --confirm` routes to `purge_mode(dry_run=False)`.
- `BaseAdapter.cleanup(dry_run=True)` reports managed paths without deleting them.
- Cursor orphan cleanup includes `~/.cursor/skills-cursor/`.
- OpenCode cleanup edits mixed config files instead of deleting user-owned config.

## Alternatives Considered

### Manual Per-Client Cleanup

Rejected. It is too easy to miss global or orphaned Augur files, and it gives users no consistent dry-run report.

### Delete Whole Client Directories

Rejected. Client directories can contain user-owned settings, non-Augur extensions, and history. Managed-output purge must delete only Augur-owned artifacts or perform targeted config edits.

### Fold Runtime State Into `--purge`

Rejected. Managed output cleanup and client runtime state reset have different risk profiles. ADR-555 adds `--purge-state` for the latter.

## References

Absorbed transient artifacts:

- `docs/superpowers/specs/2026-04-15-sync-purge-design.md`
- `docs/superpowers/plans/2026-04-15-sync-purge.md`

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - skills/ai/scripts/sync_agents/__init__.py: sync all accepts --purge and --confirm
  - skills/ai/scripts/sync_agents/adapters/base.py: cleanup accepts dry_run
patterns_deprecated:
  - manual per-client Augur artifact cleanup
files_affected:
  - skills/ai/scripts/sync_agents/__init__.py
  - skills/ai/scripts/sync_agents/modes.py
  - skills/ai/scripts/sync_agents/adapters/base.py
  - skills/ai/scripts/sync_agents/adapters/cursor.py
  - skills/ai/scripts/sync_agents/adapters/opencode.py
  - tests/sync_agents/test_purge.py
```
