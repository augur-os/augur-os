---
title: How should Knowledge Automation Command Loops be used?
summary: A reusable answer for applying [[concepts/knowledge-automation-command-loops]].
tags:
- how-should-knowledge-automation-command-loops-be-used
- knowledge-automation-command-loops
- agent-learning-compounding-pipeline
- query
- brain
- knowledge
- automation
- command
related:
- '[[knowledge-automation-command-loops]]'
- '[[agent-learning-compounding-pipeline]]'
created: '2026-05-03T13:17:12Z'
_page_type:
- e
- q
- r
- u
- y
_hub:
- a
- b
- i
- n
- r
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
_source_fingerprint:
- '0'
- '1'
- '2'
- '3'
- '4'
- '5'
- '6'
- '7'
- '8'
- '9'
- a
- b
- c
- d
- e
- f
_compiler_version:
- '-'
- '3'
- a
- c
- e
- i
- l
- n
- o
- p
- r
- t
- v
_updated:
- '-'
- '0'
- '1'
- '2'
- '3'
- '5'
- '6'
- '8'
- ':'
- T
- Z
compiler_version: concept-article-v3
hub: brain
page_type: query
source_fingerprint: b782d072fed1e6ab5aa096bdac13cd4b5b99fabee9f17c78e12aa1f0a4c9f48b
sources:
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
updated: '2026-05-03T13:36:28Z'
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
- '[[concepts/knowledge-automation-command-loops]]'
_relates_to:
- '[[agent-learning-compounding-pipeline]]'
- '[[automation]]'
- '[[brain]]'
- '[[command]]'
- '[[knowledge-automation-command-loops]]'
- '[[knowledge]]'
- '[[query]]'
---


# How should Knowledge Automation Command Loops be used?

## Summary

A reusable answer for applying [[concepts/knowledge-automation-command-loops]].

## Answer

Knowledge automation command loops keep search, memory, freshness, audits, and compiled wiki knowledge aligned.

Use [[concepts/knowledge-automation-command-loops]] as the source-backed synthesis page before returning to raw evidence.

## Evidence

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

## Related

- [[concepts/knowledge-automation-command-loops]]
- [[concepts/agent-learning-compounding-pipeline]]
