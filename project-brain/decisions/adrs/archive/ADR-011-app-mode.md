---
status: Implemented
date: '2026-01-19'
deciders:
- '@gsannikov'
related: []
hub: null
tags:
- app
- mode
- focus
- mode
- lightweight
superseded_by: null
---

# ADR-011: App Mode (Focus Mode for Lightweight Builds)

## Context

Augur dashboard is a full-featured "second brain" UI that compiles all applications into a single Next.js bundle. This causes issues for:

1. **Corporate laptops** with limited RAM/CPU - Build times exceed 5+ minutes, HMR is slow.
2. **Consultants** working on a single client project (e.g., "Terminal Automation") - They only need pages relevant to that project, not the entire brain/venture/lifestyle ecosystem.
3. **Embedded deployments** where Augur is used as a project management tool, not a personal productivity system.

### Problem Statement

The current build process compiles **all 19+ applications** (brain, career, health, venture, etc.) regardless of user needs. This wastes:
- Build time (compiling unused routes)
- Memory (loading unused MCP tools)
- CPU cycles (rendering unused React components)

## Decision

Introduce **App Mode** - a configuration-driven system that:

1. **Defines all dashboard applications** in a central config file (`augur-config/app_mode.yaml`)
2. **Enables/disables applications** by commenting/uncommenting lines
3. **Conditionally compiles** only enabled applications during `next build` / `next dev`
4. **Loads only relevant MCP tools** for enabled applications
5. **Hides navigation** for disabled applications

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       APP MODE SYSTEM                           │
│              src/config/app_mode.yaml                        │
├─────────────────────────────────────────────────────────────────┤
│  enabled: true                                                  │
│  applications:                                                  │
│    - brain                                                      │
│    # - career  (commented = disabled)                           │
│    - client-terminal-automation                                  │
│    ...                                                          │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BUILD-TIME FILTERING                         │
│              next.config.ts / turbo.json                        │
├─────────────────────────────────────────────────────────────────┤
│  • Reads app_mode.yaml                                          │
│  • If enabled=true AND applications list is defined:            │
│    - Dynamically sets pageExtensions or redirects               │
│    - Excludes disabled apps from compilation                    │
│  • If enabled=false: Full build (all apps)                      │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RUNTIME FILTERING                            │
│              lib/mcp/ToolController.ts                          │
├─────────────────────────────────────────────────────────────────┤
│  • Reads app_mode.yaml at startup                               │
│  • Filters MCP tool registration to enabled apps only           │
│  • Sidebar navigation hides disabled apps                       │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration File Schema

```yaml
# src/config/app_mode.yaml
# App Mode Configuration
# Set enabled: true to compile only listed applications
# Comment out any application to disable it

enabled: false  # Set to true to activate App Mode

# ═══════════════════════════════════════════════════════════════
# CORE APPLICATIONS
# ═══════════════════════════════════════════════════════════════

applications:
  # ─────────────────────────────────────────────────────────────
  # HOME & OVERVIEW
  # ─────────────────────────────────────────────────────────────
  - home                    # Root page (/)
  - inbox                   # Unified inbox

  # ─────────────────────────────────────────────────────────────
  # KNOWLEDGE & MEMORY (Brain Vertical)
  # ─────────────────────────────────────────────────────────────
  - brain                   # Notes, knowledge base
  - memory                  # Archived memories

  # ─────────────────────────────────────────────────────────────
  # WORK & CAREER (Work Vertical)
  # ─────────────────────────────────────────────────────────────
  - career                  # Career tracking, job applications
  - organizations           # Companies, contacts

  # ─────────────────────────────────────────────────────────────
  # OPERATIONS & SYSTEM (Factory Vertical)
  # ─────────────────────────────────────────────────────────────
  - operations              # Sprints, tasks, bugs
  - control                 # System control panel
  - settings                # User preferences
  - help                    # Documentation

  # ─────────────────────────────────────────────────────────────
  # SENSES & INPUTS (Sense Vertical)
  # ─────────────────────────────────────────────────────────────
  - sense                   # Vision, voice, location

  # ─────────────────────────────────────────────────────────────
  # LIFE & WELLNESS (Life Vertical)
  # ─────────────────────────────────────────────────────────────
  - health                  # Health tracking
  - lifestyle               # Recipes, routines

  # ─────────────────────────────────────────────────────────────
  # BUSINESS & VENTURES (Venture Vertical)
  # ─────────────────────────────────────────────────────────────
  - venture                 # Side projects, business ideas

  # ─────────────────────────────────────────────────────────────
  # CLIENT PROJECTS
  # ─────────────────────────────────────────────────────────────
  - projects                # Project hub
  # - client-terminal-automation    # Terminal Automation project (enable for focus)
  # - client-smb-design            # SMB Design Office project

# ═══════════════════════════════════════════════════════════════
# MCP TOOL FILTERING
# ═══════════════════════════════════════════════════════════════
# When App Mode is enabled, only tools tagged with enabled apps are loaded.
# Tool-to-app mapping is defined in each tool's metadata.

mcp_minimal_core:
  # These tools are always loaded regardless of App Mode
  - list-skills
  - get-skill
  - execute-chain
  - list-chains
  - switch-mcp-context
```

### How to Use

**Full Mode (Default):**
```yaml
enabled: false  # All apps compiled and loaded
```

**Focus on Terminal Automation Project:**
```yaml
enabled: true
applications:
  - client-terminal-automation
  - control  # System control panel (optional)
```

**Minimal Personal Mode:**
```yaml
enabled: true
applications:
  - home
  - inbox
  - brain
  - settings
```

## Consequences

### Positive

- **Fast builds** on weak hardware (compile 5 routes instead of 100+)
- **Low memory** - MCP server loads only required tools
- **Clean UX** - Users see only relevant navigation
- **Easy toggle** - Comment/uncomment lines in YAML
- **Project focus** - Consultants can have "client mode"

### Negative

- **Configuration overhead** - Users must edit YAML to switch modes
- **Build-time only** - Cannot switch modes at runtime without rebuild
- **Complexity** - Adds conditional logic to next.config.ts

### Neutral

- Full mode remains the default (no behavior change for existing users)
- App Mode is opt-in via `enabled: true`

## Alternatives Considered

### Alternative 1: Environment Variable Only

Use `AUGUR_FOCUS_PROJECT=client-terminal-automation` without a config file.

**Rejected because**: Too limited - can only focus on one project. Config file allows fine-grained control over which core apps to include.

### Alternative 2: Multiple Build Targets

Create separate `next.config.terminal-automation.ts` files for each mode.

**Rejected because**: Configuration explosion - hard to maintain.

### Alternative 3: Runtime-Only Filtering

Keep compiling all apps, just hide them in the UI.

**Rejected because**: Doesn't solve build time issue on weak hardware.

## Implementation Plan

1. [x] Create ADR (this document)
2. [ ] Create `src/config/app_mode.yaml` with all applications
3. [ ] Create `src/config/loadAppMode.ts` utility to read YAML
4. [ ] Modify `next.config.ts` to exclude disabled apps from compilation
5. [ ] Modify `MCPBridge.ts` / `ToolController` to filter tools by app
6. [ ] Modify `Sidebar.tsx` to hide disabled navigation items
7. [ ] Add `/reload-dashboard` step to re-read config on restart
8. [ ] Document in `docs/user-guide.md`

## References

- Dashboard app directory: `src/dashboard/app/`
- MCP Tool Controller: `src/mcp/augur_mcp/tool_controller.py`
- Existing context-based filtering: ADR-005 (MCP Execution Gateway)
- Related optimization: Lazy RAG Dependencies (`requirements-rag.txt`)
