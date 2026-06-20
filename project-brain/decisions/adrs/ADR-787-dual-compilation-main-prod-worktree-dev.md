---
status: Accepted
date: 2026-05-25
deciders:
- gsannikov
related:
- ADR-737
- ADR-759
hub: dev
tags:
- dashboard
- dev-workflow
- production
- worktree
- daemons
- performance
---

# ADR-787: Dual Compilation — Main Checkout Runs Production, Worktrees Run Dev

## Context

The dashboard only had a dev runner (`start-dev.mjs` → `next dev --turbopack` on
:3000). The Turbopack dev server is heavy on Windows (~2 GB across ~11 node
workers, HMR-induced chunk drift, and HMR console events that destabilized the
MCP bridge). For a demo we want a **stable** image — production build, immutable
chunks, no HMR — while still being able to develop in parallel.

Augur is already worktree-first (rule 33): worktrees get isolated dashboard
instances on registry-assigned ports (ADR-737). That existing isolation makes a
simpler split possible than running two instances on one checkout.

Separately, the stack spawns ~9 background `--loop` daemons (≈18 processes); with
multiple instances that fleet would multiply, and `plugin_watcher` alone burned
~4.5% of a core continuously.

## Decision

**The main checkout serves the production build on :3000; worktrees run the dev
(Turbopack) server on their own ports.**

- **Part A — Production runner for main.** Add a `--prod` mode to the dashboard
  start orchestrator that reuses the existing prebuild + MCP-bridge + port
  resolution, but replaces the server step with `next build` (via `build:safe`)
  followed by `next start --port 3000`. Triggered on demand
  (`/dev-build --prod` / `pnpm prod`) before a demo. :3000 is reserved for the
  main production instance; worktree dev instances must not claim it.

- **Part B — Daemon supervisor.** Replace the ~9 separately-spawned `--loop`
  daemons with one supervisor process that runs each daemon's poll loop as a
  scheduled task. Shared across the main-prod instance and any worktree-dev
  instances (started once; runners ensure it is up rather than each spawning a
  fleet). ~18 daemon processes → ~1–2.

- **Bridge** stays per-instance (stdio child of each Next.js process). Daemons —
  the heavy, multiplying part — are what gets shared.

- **Part B.1 — Role-scoped daemon profiles.** The full fleet is 9 polling loops;
  most are dev-time or act on shared state. The supervisor now runs a lean,
  role-scoped set instead of all 9:
  - *Singleton, shared-state daemons* (notifications, log/self-heal feed,
    adaptive/overnight loops; also cron, job queue) act globally and run on
    exactly one owner — the **main/prod** supervisor. The default prod set is
    `notification_service`, `log_monitor`, `adaptive_loop_executor`
    (`PROD_DAEMONS`). `schedule_executor`, `continuous_executor`,
    `mcp_health_monitor`, `dashboard_monitor`, `insight_scanner` are off by
    default (opt in per deployment).
  - *Per-instance dev daemons* (`plugin_watcher`) belong to **worktree/dev**
    (`DEV_DAEMONS`). In practice the dashboard's `start-dev` already runs
    `mount-plugins --watch` for live skill regen, so a worktree needs no prod
    fleet at all.
  - Role is auto-detected (main checkout = `.git` dir; worktree = gitdir file);
    override with `AUGUR_SUPERVISOR_DAEMONS="name1,name2"` (empty = none).
  This drops the main supervisor from 9 daemons to 3, with worktrees carrying
  none of the shared-state fleet (avoids double-firing cron/notifications).

Part A ships first (demo-critical and independent); Part B follows (the CPU win).

## Consequences

- Development moves to worktrees (already the norm); the main checkout is the
  stable production surface. Editing on main no longer hot-reloads — that is the
  point.
- The demo image is insulated from HMR/chunk drift and from dev-server restarts.
- Cross-OS parity (rule 30): the `--prod` mode lands in the shell-neutral
  orchestrator with both the Windows (`start-dev.mjs`) and POSIX (`start-dev.sh`)
  adapters; the initial implementation targets the Windows path with the POSIX
  adapter following.
- Part B changes daemon lifecycle; runners must coordinate on the single
  supervisor (start-once, ensure-up) instead of spawning per-instance.
