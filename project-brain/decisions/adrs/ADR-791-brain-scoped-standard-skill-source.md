---
status: Implemented
date: 2026-05-29
deciders:
  - gsannikov
related:
  - ADR-770
  - ADR-781
  - ADR-783
  - ADR-790
hub: dev
tags:
  - skills
  - brain-stack
  - standard-skills
  - projection
  - local-first
superseded_by: null
spec_file: 2026-05-29-brain-scoped-standard-skills-design.md
plan_file: 2026-05-29-brain-scoped-standard-skills.md
---

# ADR-791: Brain-Scoped Standard Skill Source

## Decision summary

Augur treats canonical brain-authored skill source as standard and generic by default. Augur-specific metadata, MCP tools, dashboard pages, Browse metadata, commands, policies, runtime state, and generated client files are projection or adapter concerns unless the skill is explicitly an Augur platform skill.

## Context

ADR-790 proved the pattern with the Apple migration: the personal Apple bundle can be a standard multi-skill source while Augur discovers, governs, and projects it externally. That pattern is now the default architecture for all brain-authored skills.

The active stack is Project > Personal > Global. The repo-local `project-brain/` in the Augur checkout is only the project brain attached to the Augur core repository. Other projects can have their own `project-brain/`. The personal brain is the configured personal vault. Global is Augur core: the read-only platform baseline that owns projection engines, default policies, scanner logic, and built-in adapters.

Team brains are out of scope for this decision.

## Decision

Canonical standard skill source lives under a brain root at:

```text
<brain-root>/capabilities/skills/<skill>/
```

A standard skill may include `DESCRIPTION.md`, subskill `SKILL.md` files, `scripts/`, `references/`, `assets/`, `examples/`, `tests/`, local CLI dependency probes, and local configuration contracts.

A standard skill must not require `x-augur-*` metadata, direct imports from Augur modules, hardcoded Augur paths, dashboard page source, MCP wrapper source, generated client folders, or hidden provider-hosted LLM calls.

Augur resolves Global + Personal + Project brain roots, discovers standard skills from each root, computes an effective skill set with Project > Personal > Global precedence, and projects client-native skill exports from the effective set. Shadow reporting must name the roots that lost precedence.

Runtime integrations remain Augur surfaces. For this migration, `email/himalaya` is a standard personal skill while Augur ingest remains the Brain Inbox integration. `note-taking/obsidian` is a standard personal skill while the Augur `vault` skill remains the vault health, MCP, Browse, and path-helper integration.

## Consequences

Augur can prove that authored brains are portable across clients and projects while still acting as a control plane around projection, policy, MCP, Browse, quality, and runtime behavior. Mixed skills must be split into generic source plus projection/runtime adapters. Platform skills remain allowed, but they must be classified as Augur platform skills instead of being treated as portable standard source.

## Status notes

Accepted on 2026-05-29 after ADR-790 proved the standard-skill migration
pattern with the personal Apple bundle.

Implemented on 2026-05-31. Augur now resolves effective standard skills across
the brain stack, reports shadowing, classifies standard-source contracts, and
projects personal `email/himalaya` and `note-taking/obsidian` skill source
without requiring Augur-specific metadata in the canonical skill files.
