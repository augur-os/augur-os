---
title: Knowledge Automation Command Loops
summary: Knowledge automation command loops keep search, memory, freshness, audits,
  and compiled wiki knowledge aligned.
tags:
- knowledge-automation-command-loops
- agent-learning-compounding-pipeline
- brain
- knowledge
- automation
- command
- loops
aliases:
- Automation loop commands
- Knowledge command loops
- knowledge manager audits
related:
- '[[agent-learning-compounding-pipeline]]'
created: '2026-05-03T13:17:12Z'
_page_type: concept
_hub: brain
_sources:
- command:skills/ai/commands/auto-agent-digest.md
- command:skills/ai/commands/auto-analytics.md
- command:skills/ai/commands/auto-command-evolution.md
- command:skills/ai/commands/auto-doc-freshness.md
- command:skills/ai/commands/auto-index-notes.md
- command:skills/ai/commands/auto-memory-sync.md
- command:skills/ai/commands/auto-project-index.md
- command:skills/ai/commands/auto-rag-reindex.md
- command:skills/ai/commands/auto-skill-enhance.md
- command:skills/ai/commands/commands.md
- command:skills/ai/commands/dev-sync.md
- command:skills/ai/commands/flag.md
- command:skills/ai/commands/harden.md
- vault:config/knowledge/README.md
_source_fingerprint: b782d072fed1e6ab5aa096bdac13cd4b5b99fabee9f17c78e12aa1f0a4c9f48b
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:36:28Z'
_cites:
- '[[command:skills/ai/commands/auto-agent-digest.md]]'
- '[[command:skills/ai/commands/auto-analytics.md]]'
- '[[command:skills/ai/commands/auto-command-evolution.md]]'
- '[[command:skills/ai/commands/auto-doc-freshness.md]]'
- '[[command:skills/ai/commands/auto-index-notes.md]]'
- '[[command:skills/ai/commands/auto-memory-sync.md]]'
- '[[command:skills/ai/commands/auto-project-index.md]]'
- '[[command:skills/ai/commands/auto-rag-reindex.md]]'
- '[[command:skills/ai/commands/auto-skill-enhance.md]]'
- '[[command:skills/ai/commands/commands.md]]'
- '[[command:skills/ai/commands/dev-sync.md]]'
- '[[command:skills/ai/commands/flag.md]]'
- '[[command:skills/ai/commands/harden.md]]'
- '[[vault:config/knowledge/README.md]]'
_mentions:
- '[[concepts/agent-learning-compounding-pipeline]]'
_relates_to:
- '[[agent-learning-compounding-pipeline]]'
- '[[automation]]'
- '[[brain]]'
- '[[command]]'
- '[[knowledge]]'
- '[[loops]]'
_entity_tier: 2
---

# Knowledge Automation Command Loops

## Compiled truth

### Current Thesis

Knowledge automation is the maintenance layer that keeps Augur search, memory, source freshness, and compiled wiki knowledge aligned.

### What This Page Knows

The command sources cover analytics, agent digests, command evolution, document freshness, project indexing, memory sync, RAG reindexing, skill enhancement, synchronization, flagging, and hardening. They share a maintenance pattern: scan the relevant surface, classify what matters, make or queue the smallest useful change, then report whether coverage genuinely improved. The commands become durable when they feed the agent's next decision rather than merely producing files. The existing command sources cover reindexing, memory sync, agent digest work, and documentation freshness. The knowledge manager source adds explicit audits for health, stale files, broken links, skill coverage, and missing documentation. Together they separate raw source hygiene from compiled wiki synthesis, so the system can be searchable without turning every audit result into a wiki page.

### Key Dimensions

- Classification: command outputs should separate actionable defects, stale data, generated churn, and evolution opportunities.
- Freshness checks protect compiled knowledge from source drift.
- Gap reports turn missing docs and broken links into actionable maintenance work.
- Honest green states: a clean run should still surface untested areas, missing source classes, or next evolution gaps when they exist.
- Regeneration: commands that change knowledge or client surfaces must refresh the relevant indexes and generated wrappers.
- Scan discipline: each loop starts by gathering current state from the owning source, index, or generated surface.
- Search indexing and wiki compounding are separate jobs that must stay coordinated.
- Skill coverage matters because knowledge is spread across skills, actions, notes, commands, and generated surfaces.

### Recent Shifts

- Agent digest and memory sync commands increasingly matter as inputs to future interactions, not just session logs.
- Command evolution and hardening loops now need acceptance tests that prove behavior, not only snapshots of generated docs.
- Knowledge automation is moving from index rebuilding toward editorial compounding, where sources become durable wiki concepts only after clustering.
- The knowledge manager source makes periodic audit outputs explicit.

### Open Tensions

- Audits should expose debt without polluting durable wiki pages with raw inventory.
- Automation can keep indexes fresh, but it can also normalize weak content if quality gates do not fail editorially bad output.
- Broad commands are convenient for operators but can blur skill ownership unless generated outputs trace back to source skills.
- Memory and RAG loops need to be aggressive enough to stay useful without rewriting or deleting user-owned context unexpectedly.

### How to Use This

Use this when deciding whether a knowledge task belongs to indexing, freshness, broken-link cleanup, skill coverage, memory sync, or wiki compilation.

### Open Questions

- How should ignored drafts and archives stay searchable without becoming operational inputs?
- Where should evolution gaps be ranked so the next agent can pick the highest-value hardening loop?
- Which audit outputs should become dashboard actions?
- Which automation commands should emit wiki-source cards for durable learning instead of only operational logs?

### Source Basis

- `command:skills/ai/commands/auto-agent-digest.md`: Compile violation signals into layered digest sections that get prepended to This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/auto-analytics.md`: Delegates to `nightly_maintainer.generate_analytics()` to produce usage This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/auto-command-evolution.md`: Analyzes command execution logs in external state under This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/auto-doc-freshness.md`: Scan documentation for broken internal links and stale content that hasn't been This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/auto-index-notes.md`: Scans skill `notes/` directories in external vault data for `.md` files that This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/auto-memory-sync.md`: Detect uncurated daily session logs and sync curated memory to all agent This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/auto-project-index.md`: Alias for `/reindex-project`. This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/auto-rag-reindex.md`: Alias for `/reindex-rag`. This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/auto-skill-enhance.md`: Unified skill improvement — evolve commands from execution logs and generate missing SKILL.md descriptions. Daemon-managed. This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/commands.md`: Display the full slash command reference below. This is the canonical list — generated from distributed command metadata in `plugins/*/skills/*/commands/*` and `augur/augur.yaml` contributions. This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/dev-sync.md`: Inspect Augur client sync status and discover client-native skills across Claude This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
- `command:skills/ai/commands/flag.md`: Manually flag when an agent violated a known decision. The violation is This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

### Related Concepts

- [[concepts/agent-learning-compounding-pipeline]]

## Timeline

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/auto-agent-digest.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/auto-analytics.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/auto-command-evolution.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/auto-doc-freshness.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/auto-index-notes.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/auto-memory-sync.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/auto-project-index.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/auto-rag-reindex.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/auto-skill-enhance.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/commands.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/dev-sync.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.

- _at: 2026-05-03T13:36:28Z  _source: command:skills/ai/commands/flag.md
  This command source contributes to the repeatable maintenance loop that scans, classifies, updates, and reports knowledge-system state.
