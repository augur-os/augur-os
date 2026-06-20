---
status: Implemented
date: '2026-04-20'
deciders:
- Gur Sannikov
related:
- ADR-186
- ADR-404
- ADR-430
- ADR-503
- ADR-522
hub: command
tags:
- sync-agents
- purge
- clients
- state
- cleanup
superseded_by: null
implemented_date: '2026-04-15'
implementation_commits:
- 4cb28b0a83
- 650f3ce20e
- d0ce1e85f6
- 65f5cdab1a
- 084d6b2dd3
- 37abb354ec
- 169eb18c99
- f926c905de
- 4fe7310926
- 6814d8cf99
- 47c334473b
---

# ADR-555: Supported Client State Purge

## Context

`sync all --purge` removes Augur-managed artifacts from AI client surfaces. That is the right default for uninstalling Augur exports, but it is not a full client state reset. Supported clients can still retain conversation history, transcripts, caches, indexes, runtime memory, and temporary session state after Augur-managed files are removed.

Users need an explicit stronger reset mode that is visibly different from Augur artifact purge and that preserves settings, trusted folders, MCP configuration, and other user-authored preferences.

## Decision

Add `sync all --purge-state` as a separate destructive mode in the sync-agents CLI. The mode is dry-run by default, requires `--confirm` to delete state, and supports `--clients` for narrowing the selected supported clients.

The mode is only valid with `sync all`. It is mutually exclusive with `--purge`, and `--clients` is valid only with `--purge-state`.

Adapters gain a second cleanup contract:

- `get_managed_files()` and `cleanup()` remain Augur-owned artifact cleanup.
- `get_state_files()` and `cleanup_state()` represent disposable client-owned runtime state.

Supported adapters define their own state surfaces so path ownership stays near client-specific knowledge. The implementation deletes runtime state and caches while preserving explicit config/settings files.

## Consequences

Positive:

- Users get a clear dry-run-first way to reset supported client runtime state.
- Augur-managed artifact cleanup and client-owned state cleanup remain separate.
- Per-client state paths stay adapter-owned rather than centralized in CLI logic.
- Tests cover preservation of user settings for each supported client.

Negative:

- Sync adapter maintenance now includes two cleanup surfaces per client.
- State path ownership must stay conservative to avoid deleting user-authored config.

Neutral:

- `sync all --purge` behavior is unchanged.
- Unsupported clients are rejected instead of guessed.

## Implementation Evidence

Key implementation files:

- `skills/ai/scripts/sync_agents/__init__.py`
- `skills/ai/scripts/sync_agents/modes.py`
- `skills/ai/scripts/sync_agents/adapters/base.py`
- `skills/ai/scripts/sync_agents/adapters/claude_code.py`
- `skills/ai/scripts/sync_agents/adapters/codex.py`
- `skills/ai/scripts/sync_agents/adapters/cursor.py`
- `skills/ai/scripts/sync_agents/adapters/gemini.py`
- `skills/ai/scripts/sync_agents/adapters/antigravity.py`
- `skills/ai/scripts/sync_agents/adapters/opencode.py`
- `skills/ai/scripts/sync_agents/adapters/kimi.py`
- `skills/ai/scripts/sync_agents/adapters/windsurf.py`
- `skills/ai/scripts/sync_agents/adapters/cowork.py`
- `skills/ai/commands/sync-agents.md`

Representative tests:

- `tests/sync_agents/test_purge.py`

## Alternatives Considered

### Extend `sync all --purge` To Delete Client State

Rejected. `--purge` already means Augur-managed outputs. Widening it would make an existing cleanup mode much more destructive.

### Centralize All Client State Paths In The CLI

Rejected. Client state locations belong with each adapter because adapters already model client-specific installation and cleanup behavior.

### Add A Generic Filesystem Scavenger

Rejected. State reset must be supported-client only and fail closed on unknown paths.

## References

Absorbed transient artifacts:

- `docs/superpowers/specs/2026-04-15-supported-client-state-purge-design.md`
- `docs/superpowers/plans/2026-04-15-supported-client-state-purge.md`

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - skills/ai/scripts/sync_agents/__init__.py: sync all accepts --purge-state and --clients
  - skills/ai/scripts/sync_agents/adapters/base.py: adapters expose get_state_files and cleanup_state
patterns_deprecated:
  - using sync all --purge for client-owned runtime state reset
files_affected:
  - skills/ai/scripts/sync_agents/__init__.py
  - skills/ai/scripts/sync_agents/modes.py
  - skills/ai/scripts/sync_agents/adapters/base.py
  - skills/ai/scripts/sync_agents/adapters/claude_code.py
  - skills/ai/scripts/sync_agents/adapters/codex.py
  - skills/ai/scripts/sync_agents/adapters/cursor.py
  - skills/ai/scripts/sync_agents/adapters/gemini.py
  - skills/ai/scripts/sync_agents/adapters/antigravity.py
  - skills/ai/scripts/sync_agents/adapters/opencode.py
  - skills/ai/scripts/sync_agents/adapters/kimi.py
  - skills/ai/scripts/sync_agents/adapters/windsurf.py
  - skills/ai/scripts/sync_agents/adapters/cowork.py
  - tests/sync_agents/test_purge.py
  - skills/ai/commands/sync-agents.md
```
