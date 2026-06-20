---
name: ai
x-augur-type: domain
x-augur-group: augur_core
x-augur-release: mvp
x-augur-tags: []
description: AI integration layer for connecting Augur to LLMs through various interfaces
  (CLI, IDE, API, SDK)
x-augur-tab: agents
x-augur-routine:
  id: auto-agent-digest
  execution: tiered
  policy: adaptive
  callable: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop: auto-agent-digest
  hub: workspace
  description: Agent directive and violation digest routine.
x-augur-commands:
- id: harden
  type: workflow
  visibility: ops
  description: Audit a skill or hub, identify gaps, and drive hardening follow-up
    work
- id: reindex-rag
  type: workflow
  visibility: auto
  description: Rebuild centralized RAG indexes for skills with plugin-local or vault-backed
    markdown content
  callable: scripts/ops/rag_reindex.py
  protocol: scan-fix
  loop:
    name: knowledge-enrichment
    tier: 0
    trigger: nightly
- id: reindex-project
  type: workflow
  visibility: auto
  description: Rebuild the master project index of skills, pages, actions, and commands
  callable: scripts/ops/project_index.py
  protocol: scan-fix
  loop:
    name: knowledge-enrichment
    tier: 0
    trigger: nightly
- id: auto-index-notes
  type: workflow
  visibility: auto
  description: Detect notes markdown files missing from skill index caches and rebuild
  callable: scripts/ops/index_notes.py
  protocol: scan-fix
  loop:
    name: knowledge-enrichment
    tier: 1
    trigger: nightly
- id: auto-analytics
  type: workflow
  visibility: auto
  description: Generate usage analytics from LLM execution logs via nightly maintenance
  callable: scripts/ops/analytics.py
  protocol: scan-fix
  loop:
    name: knowledge-enrichment
    tier: 1
    trigger: nightly
- id: sync-agents
  type: workflow
  visibility: auto
  description: Detect IDE config drift and regenerate agent configs via the sync_agents
    package entrypoint
  callable: scripts/ops/agent_sync.py
  protocol: scan-fix
  loop:
    name: knowledge-enrichment
    tier: 1
    trigger: post-execution
- id: auto-command-evolution
  type: workflow
  visibility: auto
  description: Scan command execution logs and evolve SKILL.md files with learned
    improvements
  callable: scripts/ops/command_evolution.py
  protocol: scan-fix
  loop:
    name: command-evolution
    tier: 0
    trigger: post-execution
- id: auto-memory-sync
  type: workflow
  visibility: auto
  description: Curate daily logs to MEMORY.md and distribute to all agent targets
  callable: scripts/ops/memory_sync_ops.py
  protocol: scan-fix
  loop:
    name: knowledge-enrichment
    tier: 1
    trigger: nightly
- id: auto-agent-digest
  type: workflow
  visibility: auto
  description: Compile violation signals into Hot/Warm digest sections prepended to
    MEMORY.md
  callable: scripts/ops/agent_digest/compile_digest.py
  protocol: scan-fix
  loop:
    name: auto-agent-digest
    tier: 1
    trigger: nightly
- id: flag
  type: workflow
  visibility: ops
  description: Record a directive violation for the next agent digest run
- id: auto-doc-freshness
  type: workflow
  visibility: auto
  description: Detect stale docs and broken internal links across docs/ and SKILL.md
    files
  callable: scripts/ops/doc_freshness.py
  protocol: scan-fix
  loop:
    name: knowledge-enrichment
    tier: 2
    trigger: nightly
- id: auto-skill-enhance
  type: workflow
  visibility: auto
  description: Scan command logs and generate missing descriptions for skill improvement
  callable: scripts/ops/skill_enhance_ops.py
  protocol: scan-fix
  loop:
    name: knowledge-enrichment
    tier: 2
    trigger: nightly
x-augur-license: MIT
x-augur-metadata:
  version: 1.0.0
  author: Augur
  mcp-server: augur
x-augur-requires-platform: true
x-augur-mcp-tools:
- get-ai-status
- get-sync-status
- list-agent-capabilities
- list-client-skills
- list-commands
- manage-cli-agents
x-augur-dashboard-pages:
- route: /workspace/agents
  title: Agents
x-augur-data-dir: ai
x-augur-env:
- name: AUGUR_LLM_API_KEY
  description: LLM API key
- name: AUGUR_LLM_API_KEY_ENV
  description: Name of env var holding LLM key
- name: AUGUR_LLM_BASE_URL
  description: LLM API base URL
- name: AUGUR_LLM_MODEL
  description: LLM model name
- name: AUGUR_LLM_PROFILE
  description: LLM config profile
x-augur-evolution:
  last_updated: 2026-03-21 22:59:09.564859+00:00
  improvements_applied: 1
x-augur-config-file: config.yaml
---













<!-- ADR-102 Evolution: 2026-03-21T22:59:09.564859+00:00 - fix_error_pattern: Self-repair needed for auto-adr-lifecycle (formerly auto-orphan-plans) -->


# AI Bridge

The AI Bridge skill provides the integration layer between Augur and Large Language Models (LLMs) through various interfaces.

## Capabilities

- **IDE Bridge Health Checks** - Verify Claude Code, Cursor, VS Code Copilot, and related integrations are configured and reachable.
- **MCP Registration Audit** - Validate MCP server wiring, tool discovery, and config consistency before plugin operations run.
- **Command Surface Listing** - Expose `list-commands` as the MCP-owned command inventory. It reports canonical native slash exports separately from auto-loop/internal command docs so clients do not show retired subcommand wrappers as primary slash commands.
- **Agent Instruction Sync** - Regenerate and validate IDE instruction artifacts (`CLAUDE.md`, `CODEX.md`, workflows, manifests).
- **Audit Remediation Workflow** - Drive `/harden` and related fix loops for skills failing compliance checks on `/ai/mcp-app-factory/audit`.
- **CLI/API Execution Layer** - Route command and API-based AI operations through Augur's bridge abstraction.
- **SDK Integration Support** - Provide developer-facing primitives for extending Augur AI execution safely.

## Components

### Adapters (`adapters/`)

IDE-specific adapters for different development environments:

| Adapter | IDE/Tool |
|---------|----------|
| `claude_code.py` | Claude Code CLI |
| `cursor.py` | Cursor IDE |
| `vscode_copilot.py` | VS Code with Copilot |
| `codex_cli.py` | Codex CLI |
| `claude_desktop.py` | Claude Desktop |
| `ollama.py` | Ollama local models |

### Library (`lib/`)

Core functionality:

| Module | Purpose |
|--------|---------|
| `client.py` | LLM client abstraction |
| `config.py` | Configuration management |
| `ide_detector.py` | Detect active IDE |
| `ide_health.py` | IDE health monitoring |
| `usage_tracker.py` | Token/API usage tracking |
| `instruction_generator.py` | Generate IDE instructions |
| `mcp_config_controller.py` | MCP configuration |

### Scripts (`scripts/`)

Configuration and setup scripts:

| Script | Purpose |
|--------|---------|
| `setup_cursor_mcp.py` | Cursor-specific MCP setup |
| `ide_integration_health.py` | Validate IDE bridge and MCP setup health |
| `ide_bridge.py` | IDE communication bridge |
| `PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents` | Canonical generator for IDE instruction files, workflows, and skill manifests |
| `send_to_ide.py` | Send prompts to connected IDE integrations |
| `manage_tools_catalog.py` | Read and update the Agentic Tools Catalog |

### Hooks (`hooks/`)

Event hooks for LLM interactions.

## Usage

```bash
# Configure Cursor MCP bridge
python3 project-brain/capabilities/skills/ai/scripts/setup_cursor_mcp.py

# Regenerate all agent instruction artifacts (CLAUDE.md, CODEX.md, workflows, manifests)
PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync all

# Validate generated artifacts are current (CI/pre-commit check)
PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents check
```

## Related

- MCP Server (`src/mcp/augur_mcp/`) - Central execution gateway
- `channels` skill - User notifications (Telegram, macOS)

## Additional resources
- [assets/seeds/prompts/ide-prompt-.md](assets/seeds/prompts/ide-prompt-.md)
- [scripts/markdown_flavors.py](scripts/markdown_flavors.py)
- [references/docs/BACKLOG.md](references/docs/BACKLOG.md)


### Known Issue (ADR-102)

**Pattern:** self-repair plan from hardening--auto-adr-lifecycle.json (formerly knowledge-enrichment--auto-orphan-plans); stagnation_streak=3; fingerprints=55d1b8a82318d6b0, 6e21cb12859c56fa, 940f0dcd7edecf64, a175bf6c75df985f, ff65f5b816a4eb74

**Resolution:** inspect recurring actionable fingerprints for stale heuristics
- [evals/rank.json](evals/rank.json)
