---
name: routine-coverage
x-augur-type: autoloop
x-augur-group: augur_autoloops
x-augur-release: mvp
x-augur-license: MIT
description: Scheduled coverage routines that keep Augur's hubs, commands, and skills wired and discoverable — fixing stale hub references, validating command help sections, enforcing skill standards, and surfacing skill-usage signals for under- and over-used capabilities.
x-augur-tab: coverage
x-augur-tags:
- routine
- autoloop
- coverage
- hubs
- commands
- usage
x-augur-dashboard-pages: []
x-augur-data-dir: routine-coverage
x-augur-commands:
- id: auto-adaptive-hub-coverage
  type: workflow
  visibility: auto
  description: Repair stale adaptive-hub references to live skill and workflow paths.
  callable: scripts/adaptive_hub_coverage_ops.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 2
    trigger: nightly
- id: auto-brain-hub-coverage
  type: workflow
  visibility: auto
  description: Repair stale brain-hub references to live skill, docs, and RAG paths.
  callable: scripts/brain_hub_coverage_ops.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 2
    trigger: nightly
- id: auto-command-help-coverage
  type: workflow
  visibility: auto
  description: Validate and repair missing command help sections for command-hub slash commands.
  callable: scripts/command_help_coverage_ops.py
  protocol: scan-fix
  loop:
    name: command-evolution
    tier: 1
    trigger: nightly
- id: auto-command-hub-coverage
  type: workflow
  visibility: auto
  description: Repair stale command-hub references to live skill, command, and daemon paths.
  callable: scripts/command_hub_coverage_ops.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 2
    trigger: nightly
- id: auto-life-hub-coverage
  type: workflow
  visibility: auto
  description: Repair stale life-hub references to live skill data and channel paths.
  callable: scripts/life_hub_coverage_ops.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 2
    trigger: nightly
- id: auto-skill-usage
  type: workflow
  visibility: auto
  description: Analyze skill invocation logs for underused, overused, and popular skills.
  callable: scripts/auto_skill_usage_ops.py
  protocol: scan-fix
  loop:
    name: skill-standards
    tier: 5
    trigger: nightly
- id: auto-studio-hub-coverage
  type: workflow
  visibility: auto
  description: Repair stale studio-hub skill path references inside markdown and workflow docs.
  callable: scripts/studio_hub_coverage_ops.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 2
    trigger: nightly
x-augur-config:
  contributions:
    commands:
    - id: auto-adaptive-hub-coverage
      type: workflow
      visibility: auto
      description: Repair stale adaptive-hub references to live skill and workflow paths.
      callable: scripts/adaptive_hub_coverage_ops.py
      protocol: scan-fix
    - id: auto-brain-hub-coverage
      type: workflow
      visibility: auto
      description: Repair stale brain-hub references to live skill, docs, and RAG paths.
      callable: scripts/brain_hub_coverage_ops.py
      protocol: scan-fix
    - id: auto-command-help-coverage
      type: workflow
      visibility: auto
      description: Validate and repair missing command help sections for command-hub slash commands.
      callable: scripts/command_help_coverage_ops.py
      protocol: scan-fix
    - id: auto-command-hub-coverage
      type: workflow
      visibility: auto
      description: Repair stale command-hub references to live skill, command, and daemon paths.
      callable: scripts/command_hub_coverage_ops.py
      protocol: scan-fix
    - id: auto-life-hub-coverage
      type: workflow
      visibility: auto
      description: Repair stale life-hub references to live skill data and channel paths.
      callable: scripts/life_hub_coverage_ops.py
      protocol: scan-fix
    - id: auto-skill-usage
      type: workflow
      visibility: auto
      description: Analyze skill invocation logs for underused, overused, and popular skills.
      callable: scripts/auto_skill_usage_ops.py
      protocol: scan-fix
    - id: auto-studio-hub-coverage
      type: workflow
      visibility: auto
      description: Repair stale studio-hub skill path references inside markdown and workflow docs.
      callable: scripts/studio_hub_coverage_ops.py
      protocol: scan-fix
x-augur-loops:
- id: skill-standards
  skill: routine-coverage
  automation:
    trigger: nightly
    runner: auto
    discover: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop_name: skill-standards
  memory:
    trust: adaptive
- id: command-evolution
  skill: routine-coverage
  automation:
    trigger: nightly
    runner: auto
    discover: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop_name: command-evolution
  memory:
    trust: adaptive
---

# routine-coverage

Coverage routines for hub reference coverage, command help coverage, and skill usage signals.

## Commands

- [commands/auto-adaptive-hub-coverage.md](commands/auto-adaptive-hub-coverage.md)
- [commands/auto-brain-hub-coverage.md](commands/auto-brain-hub-coverage.md)
- [commands/auto-command-help-coverage.md](commands/auto-command-help-coverage.md)
- [commands/auto-command-hub-coverage.md](commands/auto-command-hub-coverage.md)
- [commands/auto-life-hub-coverage.md](commands/auto-life-hub-coverage.md)
- [commands/auto-skill-usage.md](commands/auto-skill-usage.md)
- [commands/auto-studio-hub-coverage.md](commands/auto-studio-hub-coverage.md)

## Scope

Use this routine skill for cross-cutting hub, command, and skill usage coverage previously split across retired hub-coverage and documentation loop skills.

## When to use

Use `routine-coverage` to keep Augur's hubs, commands, and skills wired and discoverable — after adding or moving skills, renaming commands, or on the nightly schedule.

## What it covers

- **Hub references** — repairs stale adaptive-, brain-, command-, life-, and studio-hub paths.
- **Command help** — validates and repairs missing command help sections.
- **Skill standards** — enforces skill structure and metadata standards.
- **Usage signals** — analyzes invocation logs for under-used, over-used, and popular skills.

## How it runs

Each coverage workflow in `scripts/` runs as a nightly scan-fix process that reports stale references and repairs the safe ones automatically.

## Examples

```bash
# Repair stale hub references on demand
aug a-loops scan-only --loop code-quality
```
