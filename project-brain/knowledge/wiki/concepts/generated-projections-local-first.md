---
title: Generated Projections / Local-First Model
summary: Augur's local-first model keeps the brain on-prem and git-versioned while
  projecting client-native views (CLAUDE.md, AGENTS.md, Gemini config) from a single
  source of truth. Projections are outputs, not sources — editing them directly is
  a known anti-pattern.
tags:
- local-first
- projection
- architecture
- brain-stack
aliases:
- generated projections
- local-first brain
- projection model
related:
- '[[brain-stack-and-active-brain-resolution]]'
- '[[agent-separation-mcp-skill-claude]]'
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
_relates_to:
- '[[agent-separation-mcp-skill-claude]]'
- '[[architecture]]'
- '[[brain-stack-and-active-brain-resolution]]'
- '[[brain-stack]]'
- '[[local-first]]'
- '[[projection]]'
---


# Generated Projections / Local-First Model

## Compiled truth

Augur's local-first model places the brain on-prem, git-versioned, and owned by the
organization — raw private data is processed in-memory and discarded; only
PII-scrubbed learning is persisted. The projection layer converts brain-source
instructions and skill declarations into client-native formats: repo-root `CLAUDE.md`
for Claude Code, `AGENTS.md` for Codex, `GEMINI.md` and `.gemini/skills/` for
Gemini. These generated files are projections, not sources — editing them directly
is the canonical anti-pattern. Durable changes go into `project-brain/AGENTS.md`
(the portable brain source) or the mapped-sources declared in
`project-brain/config/mapped-sources.yaml`, then re-projected via `sync_agents`.
The CLAUDE.md critical rules explicitly require reading folder README files before
editing, using path helpers from `src.config.paths` instead of hardcoding local
paths, and keeping data separated: code in `src/`, config in `config/`, user data
in the external vault, runtime state in `~/Library/Application Support/Augur/state`.

The local-first constraint is also an architectural guarantee: because the brain is
git-versioned and vendor-agnostic, switching AI clients or model providers forfeits
nothing. The CLAUDE.md-generated projection, the AGENTS.md projection, and the
Gemini-generated projection all read from the same project-brain source — the model
or agent is a swappable commodity input, the brain is the durable investment. This
mirrors the venture thesis exactly: wrong-layer bets on model selection stall; the
brain is the layer that endures and appreciates.

## Timeline

- 2026-05-31 — Concept seeded from CLAUDE.md and project-brain/AGENTS.md.
