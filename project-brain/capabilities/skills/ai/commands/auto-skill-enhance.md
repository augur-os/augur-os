---
description: Auto-improve skill commands and generate missing descriptions
visibility: auto
---

# auto-skill-enhance

Unified skill improvement — evolve commands from execution logs and generate missing SKILL.md descriptions. Daemon-managed.

## Command Evolution (Tier 0)

Scan command execution logs and apply auto-safe improvements to SKILL.md files using ADR-102 infrastructure.

### Scan

Reads the most recent execution log for each command in external state under `~/Library/Application Support/Augur/state/command-evolution/`. Detects failed phases (generates timeout hints) and captured learnings (generates hint additions).

### Fix

Calls `apply_improvement_to_skill` from ADR-102 for each improvement, commits changes per file.

### Usage

Run automatically by the daemon at `tier: 0` after each command execution (`trigger: post-execution`). Can also be invoked manually via `/a-loops`.

### Protocol

Implements the `OpsCommand` protocol (`scan-fix`). Dry run supported — pass `dry_run=True` to scan without writing.

### Implementation

`skills/ai/scripts/ops/command_evolution.py`

---

## Description Generation (Tier 2)

Generate missing SKILL.md descriptions for skills using headless Claude CLI.

### Scan

Returns empty — description issues are provided externally (e.g. when a new skill is discovered without a SKILL.md). No spontaneous generation.

### Fix

Runs `claude --print --max-turns 8` with allowed tools `Read,Write,Grep,Glob` for each issue, asking Claude to analyze the skill directory and write a description.

### Usage

Run automatically by the daemon at `tier: 2` (`trigger: nightly`) in the `knowledge-enrichment` loop when external issues are queued. Can also be invoked manually via `/a-loops`.

### Protocol

Implements the `OpsCommand` protocol (`scan-fix`). Dry run supported — pass `dry_run=True` to report which skills would receive descriptions without running the CLI.

### Implementation

`skills/ai/scripts/ops/skill_enhance_ops.py`
