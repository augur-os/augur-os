---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-585
hub: null
tags: []
superseded_by: null
spec_file: 2026-05-06-windows-daemon-self-heal-design.md
plan_file: 2026-05-06-windows-daemon-self-heal-reliability.md
---

# ADR-636: Windows Daemon Self-Heal Reliability

## Decision summary

Keep the existing public surface: `service_healer.py` for OS registration, `unified_daemon.py` as the supervisor, `notification_service.py` for notifications; add a focused daemon diagnostics helper for centralized status checks. Require Task Scheduler registration plus a fresh...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
