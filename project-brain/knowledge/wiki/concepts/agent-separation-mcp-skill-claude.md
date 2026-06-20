---
title: 'Agent Separation: MCP · SKILL.md · CLAUDE.md'
summary: Augur enforces a hard three-layer separation — MCP tools own atomic
  operations, SKILL.md defines portable skill contracts, and CLAUDE.md/AGENTS.md
  carry generated agent instructions projected from the brain. Each layer has
  a distinct owner, lifespan, and write path.
tags:
- agent-separation
- architecture
- mcp
- projection
aliases:
- agent separation
- MCP skill agent layers
- three-layer agent architecture
related:
- '[[brain-stack-and-active-brain-resolution]]'
created: '2026-05-31T00:00:00Z'
_page_type: concept
_hub: dev
_sources:
- repo:CLAUDE.md
- repo:project-brain/AGENTS.md
_cites:
- '[[repo:CLAUDE.md]]'
- '[[repo:project-brain/AGENTS.md]]'
_compiler_version: concept-article-v4
_updated: '2026-05-31T00:00:00Z'
---

# Agent Separation: MCP · SKILL.md · CLAUDE.md

## Compiled truth

Augur enforces a hard separation across three layers that must never merge upward.
MCP tools own atomic operations — they are the only layer allowed to read files,
call APIs, write runtime state, or run scripts; dashboard code never owns hidden
LLM calls, direct Python scripts, `fs`, `spawn`, or `exec`. SKILL.md defines the
portable skill contract: name, type, group, release, tags, description, MCP tool
list, config shape, and callable entry point — no hardcoded Augur paths, no direct
Augur module imports, no dashboard source. The CLAUDE.md and AGENTS.md at the repo
root are generated projections: they must not be edited directly; durable instruction
changes belong in the project-brain source files or mapped-sources declared in
`project-brain/config/mapped-sources.yaml`, then projected through `sync_agents`.
The `project-brain/AGENTS.md` is the portable brain source; the repo-root `CLAUDE.md`
is the harness-generated client view.

The practical rule: agents own judgment and orchestration; MCP tools own atomic
operations; docs/commands own policy; daemons schedule only. This decoupling is what
allows agents (Claude Code, Codex, Gemini) and models (cloud or local) to be swapped
freely without losing the brain's accumulated context. A skill-owned shared config,
metadata, data, types, pages, and tools all live inside the skill directory; nothing
skill-specific lives in central config. Agents are swappable; the brain layer is
the durable context the agent reads — the key claim from the Intel AI Edge pitch
that the PC validated at scale.

## Timeline

- 2026-05-31 — Concept seeded from CLAUDE.md critical rules and project-brain/AGENTS.md.
