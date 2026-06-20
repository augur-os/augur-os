---
status: Implemented
date: 2026-03-15
deciders:
  - Gur Sannikov
related:
  - ADR-421
hub: productivity
tags:
  - apple
  - reminders
  - remote-access
superseded_by: null
---

# ADR-423: Remote Control via Apple Reminders

## Context

When using Claude Code remotely, the connection link must be manually copied and transferred to the remote device. Apple Reminders syncs across all Apple devices via iCloud, making it a natural transport for connection links.

## Decision

Wrapper around Claude Code's built-in remote connection feature that stores the connection link in Apple Reminders:

- **`/apple remote` command** — generates remote connection link, creates a reminder in "remote control" list with the link in the notes field
- **`SessionEnd` hook** — marks the reminder complete when session ends
- **`SessionStart` stale cleanup** — if state file is >24 hours old, marks reminder complete (handles crashes)
- **Manual start (Option B)** — only creates reminders when remote access is intentionally needed, not on every session

### Reminder Format

- Title: `Claude: {repo_name} ({branch})`
- Notes: raw connection link
- Due date: 24 hours from creation (visual staleness indicator)

### State File

JSON at `$AUGUR_STATE/remote-control.json` with `chmod 600` (link is a bearer token). Contains `reminder_id`, `title`, `link`, `repo`, `branch`, `created_at`.

## Consequences

### Positive

- Connection link available on any Apple device within seconds
- Automatic cleanup on session end
- Stale cleanup handles crashes gracefully

### Negative

- Requires "remote control" Reminders list to exist (manual creation)
- macOS-only (AppleScript dependency)

## References

- Design doc: `docs/superpowers/specs/2026-03-15-remote-control-apple-reminders-design.md`
