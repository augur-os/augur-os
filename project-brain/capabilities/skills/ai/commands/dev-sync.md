---
description: Inspect and repair Augur client sync status across supported AI clients.
visibility: dev
x-augur-export-command: false
---

# /dev-sync

Inspect Augur client sync status and discover client-native skills across Claude
Code, Codex, Gemini, and OpenCode.

## Usage

```bash
/dev-sync
/dev-sync --check
/dev-sync --fix
/dev-sync --inventory
```

## Notes

- Read-only inventory/status checks can run on the main worktree.
- Promotion or sync-changing operations should run in a git worktree.
