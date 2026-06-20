---
description: Detect dashboard memory leaks from polling, unbounded caches, and interval accumulation
visibility: auto
---

# auto-memory-leak

Detect dashboard memory leaks from polling, unbounded caches, and interval accumulation.

## What it scans

| Pattern | Severity | Description |
|---------|----------|-------------|
| `setInterval-without-cleanup` | high | `setInterval` in useEffect without `clearInterval` in cleanup |
| `aggressive-polling` | medium | Polling intervals under 10 seconds |
| `hmr-unsafe-interval` | high | Module-level `setInterval` without `globalThis` singleton guard |
| `unbounded-cache` | medium | Module-level `Map`/`Set`/`object` without size limits |
| `autorefresh-default-true` | low | `autoRefresh` state defaulting to `true` (opt-in is safer) |

## What it fixes

- Inserts `TODO_BUG` markers at the offending line with pattern name and suggested fix
- Removes stale markers when the issue no longer reproduces
