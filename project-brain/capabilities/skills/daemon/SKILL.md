---
name: daemon
x-augur-type: domain
x-augur-group: augur_admin
x-augur-release: mvp
x-augur-tags:
- daemon
- launchd
- task-scheduler
- self-heal
- monitoring
- autoloops
description: Use when managing background services, checking daemon status, configuring autoloops, debugging self-heal pipeline issues, or controlling the unified daemon via macOS launchd or Windows Task Scheduler.
x-augur-tab: monitor
x-augur-callable: project-brain/capabilities/skills/daemon/scripts/routine_orchestrator/orchestrator.py
x-augur-data-deps:
- career
- venture
- lifestyle
- apple
- channels
x-augur-commands:
- id: a-loops
  type: workflow
  visibility: dev
  description: List, run, report, and inspect unified routines
- id: auto-self-heal
  type: workflow
  visibility: auto
  description: Scan external Augur logs for errors and delegate fixes to ai_self_healer
  callable: scripts/ops/self_heal.py
  protocol: scan-fix
  loop:
    name: self-heal
    tier: 0
    trigger: continuous
    config:
      min_severity: high
- id: auto-page-mounts
  type: workflow
  visibility: auto
  description: Verify contributions.pages source files exist for all mounted plugins
  callable: scripts/ops/page_mounts.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 0
    trigger: nightly
- id: auto-security-scan
  type: workflow
  visibility: auto
  description: Scan for hardcoded secrets, npm vulnerabilities, and known CVEs
  callable: scripts/ops/security_scan.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 4
    trigger: nightly
- id: auto-stale-paths
  type: workflow
  visibility: auto
  description: Detect ADR-270 folder/path drift across active code, workflows, and operational references
  callable: scripts/ops/stale_paths.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 1
    trigger: nightly
    config:
      max_issues: 250
- id: auto-code-health
  type: workflow
  visibility: auto
  description: Scan TypeScript build errors and API route health failures
  callable: scripts/ops/build_health.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 0
    trigger: nightly
- id: auto-skill-md
  type: workflow
  visibility: auto
  description: Validate and generate SKILL.md files per Claude Code skills standard
  callable: scripts/ops/skill_standards_md.py
  protocol: scan-fix
  loop:
    name: skill-standards
    tier: 0
    trigger: nightly
- id: auto-skill-refs
  type: workflow
  visibility: auto
  description: Validate and fix SKILL.md file references and folder structure
  callable: scripts/ops/skill_standards_refs.py
  protocol: scan-fix
  loop:
    name: skill-standards
    tier: 2
    trigger: nightly
- id: auto-heal-validate
  type: workflow
  visibility: auto
  description: Validate self-heal daemon health and clear stuck journal entries
  callable: scripts/ops/heal_validate.py
  protocol: scan-fix
  loop:
    name: self-heal
    tier: 1
    trigger: nightly
- id: auto-mcp-hygiene
  type: workflow
  visibility: auto
  description: Per-plugin MCP tool naming, registration, dead-tool, and duplicate audit
  callable: scripts/ops/mcp_hygiene.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 1
    trigger: nightly
x-augur-license: MIT
x-augur-metadata:
  version: 0.3.0
  author: Augur
  mcp-server: augur
x-augur-requires-platform: true
x-augur-mcp-tools:
- list-notifications
- list-routines
x-augur-dashboard-pages: []
x-augur-data-dir: daemon
x-augur-config-file: config.yaml
x-augur-env:
- name: AUGUR_ATTENTION_SYNC_INTERVAL
  description: Attention sync frequency
x-augur-evolution:
  last_updated: 2026-03-22 23:52:40.236998+00:00
  improvements_applied: 1
x-augur-loops:
- id: self-heal
  skill: daemon
  automation:
    trigger: nightly
    runner: auto
    discover: scripts/routine_orchestrator/orchestrator.py
  loop_name: self-heal
  memory:
    trust: adaptive
- id: goal-loop
  skill: daemon
  automation:
    trigger: nightly
    runner: auto
    discover: commands/goal-loop.md
  memory:
    trust: oneshot
---

















<!-- ADR-102 Evolution: 2026-03-23T08:38:13.247978+00:00 - fix_error_pattern: Self-repair needed for auto-stale-paths -->

# Daemon

## Gotchas

### 1. Never run unified_daemon.py directly -- always use launchd
Running `python3 unified_daemon.py start` directly spawns the daemon inside Claude Code's process tree. When Claude Code exits, the daemon dies. Additionally, the self-healer cannot spawn CLI tools from within a nested process. Always use `launchctl load/unload` to manage the daemon as an OS-level service.

### 2. Dashboard lifecycle gate must be used for all dashboard state changes
Per CLAUDE.md rule 18, never run `npm run dev`, `npm run build`, or `cleanup_processes.py --port 3000` directly. All dashboard state changes go through `dashboard_lifecycle.request_action()` or via `/dev-build`. Direct manipulation bypasses crash-loop protection and breaks coordination between concurrent agents.

### 3. Stale .pyc cache prevents daemon code changes from taking effect
After modifying adaptive engine modules or daemon scripts, clear `__pycache__` directories before restarting the daemon. Python bytecode cache serves stale compiled code even after source edits. The daemon restart alone does not trigger recompilation.

### 4. Launchd plist paths are resolved at install time and go stale on project moves
If the project directory is moved, the daemon's launchd plist (`~/Library/LaunchAgents/com.augur.daemon.plist`) still references the old path. Run `service_healer.py heal` to regenerate the plist with current paths, or `service_healer.py install` to reinstall from scratch.

## Overview

Unified background service management for Augur. Manages all background processes
as child subprocesses with health monitoring, automatic restart, mode-aware
self-healing, and AI-powered error classification and auto-fix capabilities.

Daemon is the canonical owner for the legacy `/ops-self-heal-test` command surface. Keep self-heal verification guidance with the daemon and self-heal runtime, not in a separate top-level wrapper skill.
Daemon is also the canonical owner for the adaptive loop engine surfaced through `/a-loops`. Keep adaptive loop operations, implementation notes, and overview actions with the daemon runtime instead of a separate wrapper skill.
Daemon also owns the ADR-755 routine orchestrator. `scripts/routine_orchestrator/` provides the session-aware scan, mechanical-fix, semantic bucket, pending-escalation, and subagent-dispatch path used by the new `aug a-loops` CLI and by marked auto-commands such as `routine-vault/auto-frontmatter-lint`.

## Capabilities

See [Capabilities](references/capabilities.md) for details.

## Mode-Aware Behavior

| Mode | Dashboard Monitor | MCP Health Monitor | Runtime Scanner | AI Self-Healer |
|------|-------------------|-------------------|-----------------|----------------|
| **Production** | Auto-restart with recovery | Auto-kill stalled PIDs | Silent logging | Classify + auto-fix |
| **Dev** | Notify only | Notify only | Notify + log | Classify + auto-fix |

Set mode via:
- Environment: `AUGUR_MODE=dev` or `AUGUR_MODE=production`
- Settings: `config/system/settings.yaml` → `mode: dev`

## Usage

> See [references/launchd-usage.md](references/launchd-usage.md) for full launchd commands (start/stop/restart/heal/status), configuration, and output file locations.

**Quick reference**: `launchctl list com.augur.daemon` (status), `launchctl load -w ~/Library/LaunchAgents/com.augur.daemon.plist` (start), `launchctl unload` (stop). Default action: status.

### Adaptive Loop Engine

Manage the Adaptive Loop Engine directly from the daemon. Use `/a-loops` for loop status, registry inspection, heal/diagnose flows, and autonomous multi-cycle runs (the former `/dev-loops` alias was retired in ADR-758).

See [references/routines-implementation.md](references/routines-implementation.md) for executor details.

### Monitor Sidecar Mode

Runs inside an AI client session as a persistent monitoring loop. The daemon spawns the AI client as a sidecar process with an explicit monitor prompt — do NOT invoke this mode manually or depend on a generated `/daemon --monitor` slash command being present in the client.

**How it works:**
1. AI calls `ai_monitor_watcher.py --status` to load current state
2. AI enters loop: calls `--wait-for-event --timeout 300` (blocks until error or timeout)
3. On error: acquires fix lock, investigates, fixes, commits with `fix(self-heal):` prefix, records fix
4. On timeout: runs `--vault-check` for vault health, then loops

**Configuration:** `config/system/daemon.yaml` — `ai_monitor` section.

**Requires:** An AI client (Claude Code, Codex, or Gemini) installed and configured.

## Dependencies

- Python 3.11+
- PyYAML (for settings)
- psutil (optional, for enhanced process monitoring)
- ripgrep (optional, falls back to Python re)

## Modules

| Topic | Load |
|-------|------|
| MCP health monitoring | `modules/mcp-health-monitor.md` |
| AI self-healing | `modules/ai-self-heal.md` |

## References

- ADR-038: Unified Daemon Process
- ADR-041: Daemon Production Monitoring & Self-Healing
- ADR-076: Daemon AI-Powered Self-Healing

## Additional resources

See [Additional resources](references/additional-resources.md) for details.
- [commands/loop-history.md](commands/loop-history.md)
- [commands/loop-status.md](commands/loop-status.md)
- [commands/run-loop-cycle.md](commands/run-loop-cycle.md)
- [commands/a-loops.md](commands/a-loops.md)
- [assets/seeds/_seed.yaml](assets/seeds/_seed.yaml)
- [assets/seeds/example-routines.yaml](assets/seeds/example-routines.yaml)
- [assets/seeds/plugin-events.json](assets/seeds/plugin-events.json)
- [evals/rank.json](evals/rank.json)
- [references/additional-resources.md](references/additional-resources.md)
- [references/routines-implementation.md](references/routines-implementation.md)
- [references/usage.md](references/usage.md)


### Known Issue (ADR-102)

**Pattern:** self-repair plan from hardening--auto-memory-leak.json; stagnation_streak=2; module=skills/routine-vault/scripts/memory_leak.py; fingerprints=27fe8c20a800d94d, 4cc2521aa423c9a7, 7e2f0d3a97ad591b, a6d3dabb7c8598f1

**Resolution:** inspect recurring actionable fingerprints for stale heuristics



### Known Issue (ADR-102)

**Pattern:** self-repair plan from hardening--auto-memory-leak.json; stagnation_streak=3; module=skills/routine-vault/scripts/memory_leak.py; fingerprints=27fe8c20a800d94d, 4cc2521aa423c9a7, 7e2f0d3a97ad591b, a6d3dabb7c8598f1

**Resolution:** inspect recurring actionable fingerprints for stale heuristics
