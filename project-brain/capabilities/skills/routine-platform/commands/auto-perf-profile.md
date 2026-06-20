---
description: Check response times, disk bloat, stale files, cache size, and performance regressions
visibility: auto
---

# auto-perf-profile

Check response times, disk bloat, stale files, cache size, and flag IO/performance regressions.

## Scan

Profiles system performance metrics including disk usage, cache sizes, inactive dashboard worktree caches, stale file counts, and response times.

## Fix

Cleans up stale files, trims owned bloated caches, and reports performance regressions. Inactive dashboard worktree cache bloat is reported with a `/dev-clean` recommendation because `/dev-clean` owns the live-lock safety guard for those external caches.
