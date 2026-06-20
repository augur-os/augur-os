---
description: Auto-generated from plugins/ai/skills/ai/augur/ide-integration/workflows/sync-agents.md
visibility: ops
---

# /sync-agents

## ⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
#
# Source: plugins/ai/skills/ai/augur/ide-integration/workflows/sync-agents.md
# To edit: Modify the source file, then run /sync-agents
#

# /sync-agents

Synchronize all IDE instruction files from local repository structure.

## What it does

1. Scans `plugins/` directory for available plugins
2. Scans distributed command sources under `plugins/*/skills/*/commands/`
3. Generates instruction files for all IDEs:
   - `CLAUDE.md` (Claude Code)
   - `CODEX.md` (Codex CLI)
   - `.cursorrules` (Cursor)
   - `.windsurfrules` (Windsurf)
   - `.cursor/rules/augur.mdc`
   - `.antigravity/instructions.md`
   - `.vscode/augur-instructions.md`
   - `.github/copilot-instructions.md`
4. Syncs Claude command skills into `skills/*/SKILL.md`

## Usage

```bash
# Via Python
PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync all

# Via MCP tool
# Use the sync-agents MCP tool
```

## When to run

- After adding new plugins to `plugins/`
- After adding or updating command specs under `plugins/*/skills/*/commands/` and `augur/augur.yaml` contributions
- After updating critical rules in `get_vault_config_dir()/ai/agent-rules.md`

## Files affected

### Generated files (all IDEs get same content)
- `CLAUDE.md`
- `CODEX.md`
- `.cursorrules`
- `.windsurfrules`
- `.cursor/rules/augur.mdc`
- `.antigravity/instructions.md`
- `.vscode/augur-instructions.md`
- `.github/copilot-instructions.md`

### Claude command skills
- `skills/{command}/SKILL.md`

## Source

The generator script is at `skills/ai/scripts/sync_agents.py`.
It works standalone without any external data repository dependency.

## Verification

```bash
# Check generated files exist
ls -la CLAUDE.md .cursorrules .windsurfrules

# Check Claude command skill output
ls -la skills/ops-sync/SKILL.md
```
