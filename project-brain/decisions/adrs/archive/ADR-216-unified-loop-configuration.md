---
status: Implemented
date: '2026-03-04'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- unified
- loop
- configuration
- decentralized
superseded_by: null
---

# ADR-216: Unified Loop Configuration (Decentralized)

## Context

All adaptive loop timing, severity filters, CLI parameters, and service intervals were hardcoded across 15+ Python files. Changing any value required code edits and a daemon restart. There was no single view of all settings, no UI to edit them, and no hot-reload.

Per ADR-163, module-level config MUST live in each plugin's `augur.yaml`, not in a centralized file. The central `config/system/adaptive_loops.yaml` holds only engine-level settings.

## Decision

Implement a two-layer configuration system:

### Layer 1: Plugin-level (decentralized)

Each auto-command's `loop:` section in its plugin's `augur.yaml` gets a `config:` block with module-specific settings (timeouts, max turns, severity filters). Discovery assembles these into the registry.

### Layer 2: Central (engine-level only)

`config/system/adaptive_loops.yaml` holds engine orchestration settings (`poll_interval_seconds`), per-loop budgets, and service intervals (`services.continuous_executor`, `services.insight_scanner`). No per-module config.

## Implementation

### Plumbing
- `OpsContext` gains `config: dict` (per-module) and `loop_config: dict` (engine-level) fields
- `AutoCommandEntry` gains `config: dict` field
- `discover_auto_commands()` extracts `loop.config` from augur.yaml
- Engine's `run_auto_cycle()` passes both configs into OpsContext
- `adaptive_loop_executor.py` hot-reloads config each cycle and reads `poll_interval_seconds`

### Module Migration
Seven ops modules replaced hardcoded values with `ctx.config.get("key", DEFAULT)`:
- `build_health.py`: scan_timeout, fix_timeout, max_turns
- `self_heal.py`: min_severity
- `plugin_lint.py`: fix_timeout, max_turns
- `stale_paths.py`: fix_timeout, max_turns
- `todo_cleanup.py`: scan_timeout, fix_timeout, max_turns
- `todo_outdated.py`: scan_timeout, fix_timeout, max_turns
- `lint.py`: scan_timeout, fix_timeout, max_turns

### Service Config
- `continuous_executor.py`: reads `services.continuous_executor` from adaptive_loops.yaml, merges with DEFAULT_CONFIG
- `insight_scanner.py`: reads `services.insight_scanner.interval_hours` from adaptive_loops.yaml

### Dashboard
- Loops API returns assembled module configs, services config, and configPath
- New "Configuration" tab shows engine settings, services config, loop budgets, and per-module config table

## Consequences

- Config changes take effect next cycle (hot-reload) without daemon restart
- All settings are visible in one dashboard tab
- Backward compatible: empty `ctx.config` falls back to current defaults
- Per ADR-163, module config stays decentralized in plugin augur.yaml files
