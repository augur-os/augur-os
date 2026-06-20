---
status: Accepted
date: 2026-06-09
deciders:
  - gsannikov
related:
  - ADR-796
  - ADR-788
hub: null
tags:
  - dev
  - cli
  - autonomy
  - sdlc
superseded_by: null
spec_file: 2026-06-09-sdlc-autonomy-design.md
plan_file: 2026-06-09-sdlc-autonomy.md
---

# ADR-810: Agent-callable dev surface (`aug dev build`) + post-spec SDLC autonomy

> **ADR-810 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

`aug dev build` is the agent-callable dev-cycle entrypoint, sharing one engine
(`src/lib/dev_build.py`) with the `/dev build` slash command — ADR-796's user `/dev <verb>`
surface is unchanged. The engine performs a launchd-safe, instance-scoped restart (only the
target instance's port + its `dashboard-`-prefixed MCP children, via
`scoped_restart.py`; never a broad `pgrep`, never a launchd unload). With the **approved spec as
the authorization boundary**, agents run plan → code → test → build → browser-verify →
ff-merge+push autonomously: force-push / history rewrite are never allowed, raw destructive
deletes and external publish/deploy always confirm, vault/secrets stay out of scope, and merges
follow a no-loss stash → resolve → unstash → inspect → commit protocol.

## Spec (canonical)

- [`docs/superpowers/specs/2026-06-09-sdlc-autonomy-design.md`](../superpowers/specs/)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-06-09-sdlc-autonomy.md`](../superpowers/plans/)

## Status notes

Accepted 2026-06-09. Complements ADR-796 (user `/dev <verb>` slash surface) — does not supersede
it. The macOS-scoped restart primitive (`ps -E` based) is posix/Darwin-only today; cross-OS
extension is a follow-up.

## Related

- ADR-796 (`/dev <verb>` is the canonical dev-command surface)
- ADR-788 (skill supply-chain guardrails — dependency changes confirm unless named in the spec)
