---
id: ADR-513
title: One-Click Onboarding Multi-Downstream Install
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [onboarding, install, skills-pack, multi-platform]
related: [ADR-437, ADR-438]
---

# ADR-513: One-Click Onboarding Multi-Downstream Install

## Context

Augur could only be installed by cloning the repo and running install.sh. Users from Obsidian, IDEs, or AI agents had no native install path. The onboarding needed to support one-click installation from any platform.

## Decision

Create a universal install prompt (`dist/skills-pack/install.md`) that works in any AI agent:
1. **Auto-detect platform** — check for `.claude/`, `.codex/`, `.gemini/`, `.cursor/`, etc.
2. **Two install modes**: Skills pack (curated set of standalone skills, zero setup) or Full system (complete Augur with vault, dashboard, background agents)
3. **Skills pack** — cloned subset of skills that work without MCP server, data persists in seed folders
4. **Full system** — `curl install.sh | bash` with `--from <platform>` flag
5. **Upgrade path** — skills pack data carries over to full system install

Install matrix: Terminal (full), Obsidian (full), IDE (full), AI agent (choice of skills-only or full).

## Consequences

### Positive
- Any AI agent user can install Augur by pasting a single prompt
- Skills pack provides low-friction entry point (standalone skills, no setup)
- Upgrade preserves all user data from standalone mode

### Negative
- Skills pack is a subset — users may expect full functionality
- Multi-platform detection heuristics may need updates as new AI agents emerge

## References

- Spec: `docs/superpowers/specs/2026-03-23-one-click-onboarding-design.md`
- Install prompt: `dist/skills-pack/install.md`
