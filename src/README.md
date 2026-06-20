# src/

**Purpose**: Framework code src/lib across the monorepo.

## Contents

### Core (per original design)

- `config/` - Path resolution and configuration
- `scripts/` - Python utilities (sync, audit, generate)
- `tests/` - Python tests (unit, integration, e2e)

### Framework Modules

- `augur_logging/` - Centralized logging configuration
- `boundaries/` - Import boundary enforcement
- `llm/` - LLM integration (hooks, IDE adapters)
- `mcp/` - Canonical MCP server packages (`augur_core`, `augur_framework`, `augur_shared`)
- `modules/` - Shared Python modules (retrospective, etc.)
- `plugins/` - Agent definitions and integration packaging
- `reviews/` - Code review utilities
- `search/` - Search functionality

### Assets

- `native/` - macOS app bundle for permission dialogs
- `templates/` - Configuration templates (llm.yaml.example)

## Rules

- CODE ONLY - no user data, no runtime files
- Runtime state, logs, and caches live outside the repo via
  `src.config.paths` (for example `state/`, `logs/`, and `cache/` under the
  platform app-support root), not in a repo-local runtime tree
- Configuration goes to `config/`
- Agent definitions and integration packaging live in `plugins/`, NOT here
- Project/team skills with `SKILL.md` live in `project-brain/capabilities/skills/`, NOT here

## Dashboard Note

The Next.js dashboard now lives in `apps/dashboard/`.
Files in `apps/dashboard/app/{hub}/` are **auto-generated** from skill-owned
dashboard sources. Edit project/team source files in
`project-brain/capabilities/skills/{skill}/augur/dashboard/` or
`project-brain/capabilities/skills/{skill}/augur/pages/` instead.

## Cleanup Notes

- `__pycache__/` directories should be gitignored
- Dashboard test/build artifacts live under `apps/dashboard/` and are gitignored
