---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- sync
- agents
- refactor
superseded_by: null
---

# ADR-186: Sync Agents Refactor

**Date:** 2026-02-28
**Source:** `/learn refactor` analysis (344 learnings, 7-day window)

## Context

`sync_agents.py` (2869 lines) is the second-highest priority infrastructure area from the refactor analysis — 265 points with 5 real issues over the last 7 days. It is the single-file engine that generates IDE adapter configs for 10+ targets (Claude Code, Cursor, Windsurf, Gemini, OpenCode, Copilot, Kimi, Antigravity, Cline, Codex).

### Structural Weaknesses

### 1. Monolithic Single File (2869 Lines)

All adapter logic, template rendering, command discovery, and file generation lives in one file. Adding a new IDE adapter means adding another class to an already massive file. The `BaseAdapter` defines 9 sync methods; each concrete adapter overrides a subset with copy-paste-modify implementations.

### 2. Hardcoded Source Paths

Lines 78-81 define `SOURCE_RULES`, `SOURCE_WORKFLOWS`, `SOURCE_SKILLS`, `SOURCE_TOPICS` as hardcoded paths to `plugins/ai/skills/ai_bridge/`. If the ai_bridge plugin is renamed or moved, all paths break silently — no validation that these paths exist at startup.

### 3. Distributed Command Dedup by Name Only

ADR-178 introduced distributed command discovery via `scan_distributed_commands()` scanning `plugins/*/skills/*/augur.yaml`. The merge logic (lines 154-168) deduplicates by command name alone:

```python
if name in seen_names:
    continue
```

If two skills in different hubs define a command with the same name but different behavior, the first one found (filesystem iteration order) wins silently. No warning, no compound key (hub+skill+name).

### 4. Fragile Placeholder Resolution

Template rendering uses a string-replace loop (lines 362-376) where each placeholder like `{{SKILLS_TABLE}}` is replaced via regex. If a placeholder name appears in generated content (e.g., a skill description mentioning `{{COMMANDS}}`), it gets accidentally replaced. No escaping or context boundary.

### 5. Template Format Changes Touch 10+ Adapters

Each adapter class has its own `sync_*()` methods that format output. When the header template (`HEADER_TEMPLATE`, line 107) or section format changes, every adapter must be updated. There is no centralized formatting layer — adapters directly compose strings.

### Evidence from Daily Logs

| Date | Issue |
|------|-------|
| 2026-02-28 | sync_agents --fix mode design: run --check first, if drift detected run full sync then stage |
| 2026-02-28 | ADR-178 decentralized slash commands — 52 commands migrated, scan_distributed_commands() canonical |
| 2026-02-27 | ADR-175 command naming alignment — 11 of 37 commands renamed, sync_agents regenerated all configs |
| 2026-02-27 | Historical memory entries should NOT be updated during command renames |
| 2026-02-19 | Post-merge sync_agents must stage only generated outputs, never blanket-add |

## Decision

### Phase 1: Split Into Package (M effort)

Restructure `sync_agents.py` into a package:

```
plugins/ai/skills/ai_bridge/scripts/sync_agents/
├── __init__.py          # CLI entry point (argparse, --all, --check, --fix)
├── engine.py            # Core sync orchestration
├── discovery.py         # Command, skill, topic discovery (scan_distributed_commands)
├── templates.py         # Centralized template rendering with safe placeholder resolution
├── adapters/
│   ├── base.py          # BaseAdapter with shared formatting
│   ├── claude_code.py   # Claude Code / CLAUDE.md
│   ├── cursor.py        # Cursor / .cursorrules
│   ├── windsurf.py      # Windsurf / .windsurfrules
│   ├── gemini.py        # Gemini / .gemini/GEMINI.md
│   ├── copilot.py       # Copilot / .github/copilot-instructions.md
│   ├── codex.py         # Codex / CODEX.md
│   ├── kimi.py          # Kimi / .kimi
│   ├── opencode.py      # OpenCode / AGENTS.md
│   └── cline.py         # Cline / .clinerules
└── constants.py         # Source paths, header templates, placeholder names
```

The CLI entry point remains `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py` via `__init__.py` or a wrapper script for backwards compatibility.

### Phase 2: Compound Command Dedup (S effort)

Replace name-only dedup with compound key:

```python
# Current (broken for cross-hub name collisions):
if name in seen_names:
    continue

# Proposed:
dedup_key = f"{cmd.hub}:{cmd.skill}:{cmd.name}"
if dedup_key in seen_keys:
    continue
# For CLAUDE.md display, deduplicate by name only but warn on collision:
if cmd.name in seen_display_names:
    logger.warning(f"Command name collision: {cmd.name} in {cmd.skill} vs {seen_display_names[cmd.name]}")
```

### Phase 3: Safe Template Rendering (S effort)

Replace the regex string-replace loop with a context-aware renderer:

```python
class TemplateRenderer:
    """Renders templates with safe placeholder resolution."""

    DELIMITER = "{{"  # configurable if content uses {{ }}

    def render(self, template: str, context: dict[str, str]) -> str:
        """Replace placeholders only in designated slots, not in content."""
        result = template
        for key, value in context.items():
            placeholder = f"{self.DELIMITER}{key}}}"
            # Only replace if placeholder is on its own line or at section boundary
            result = result.replace(placeholder, value)
        return result
```

Additionally, validate that no placeholder strings remain in the final output — a simple `assert "{{" not in result` catches accidental leaks.

### Phase 4: Path Discovery via augur.yaml (S effort)

Replace hardcoded `SOURCE_*` paths with discovery:

```python
# Current:
SOURCE_RULES = "plugins/ai/skills/ai_bridge/augur/data/agent-rules.md"

# Proposed: discover from augur.yaml
def discover_source_paths() -> dict[str, Path]:
    """Find canonical source files by scanning ai_bridge's augur.yaml."""
    ai_bridge_yaml = find_skill_yaml("ai_bridge")
    return {
        "rules": ai_bridge_yaml.parent / ai_bridge_yaml["contributions"]["agent_rules"],
        "topics": ai_bridge_yaml.parent / ai_bridge_yaml["contributions"]["agent_topics"],
        # etc.
    }
```

## Consequences

### Positive

- Package structure makes adding new IDE adapters a single-file addition
- Compound dedup prevents silent command shadowing across hubs
- Safe template rendering eliminates accidental placeholder expansion
- Path discovery via augur.yaml aligns with Critical Rule #1 (decentralization)

### Negative

- Package split changes import paths — any external scripts importing from `sync_agents` need updating
- The backwards-compatible CLI wrapper adds one level of indirection

### Neutral

- Generated output files (CLAUDE.md, .cursorrules, etc.) remain identical — no behavioral change
- The `--fix` mode (run check → full sync → stage) works the same, just orchestrated from `engine.py`

## Impact Manifest

```yaml
paths_renamed:
  - from: "plugins/ai/skills/ai_bridge/scripts/sync_agents.py"
    to: "plugins/ai/skills/ai_bridge/scripts/sync_agents/ (package)"

apis_changed:
  - function: "_get_all_workflow_metadata()"
    change: "moved to sync_agents/discovery.py"
  - function: "BaseAdapter and all subclasses"
    change: "moved to sync_agents/adapters/"

files_affected:
  - plugins/ai/skills/ai_bridge/scripts/sync_agents.py → package
  - plugins/ai/skills/ai_bridge/scripts/sync_agents/__init__.py
  - plugins/ai/skills/ai_bridge/scripts/sync_agents/engine.py
  - plugins/ai/skills/ai_bridge/scripts/sync_agents/discovery.py
  - plugins/ai/skills/ai_bridge/scripts/sync_agents/templates.py
  - plugins/ai/skills/ai_bridge/scripts/sync_agents/constants.py
  - plugins/ai/skills/ai_bridge/scripts/sync_agents/adapters/*.py

patterns_deprecated:
  - pattern: "name-only command dedup"
    replacement: "compound key (hub:skill:name) dedup"
  - pattern: "regex string-replace for template placeholders"
    replacement: "TemplateRenderer with boundary-aware replacement"
  - pattern: "hardcoded SOURCE_* paths"
    replacement: "augur.yaml-driven path discovery"
```

## References

- ADR-178: Decentralized slash command discovery
- ADR-175: Command naming alignment
- ADR-171: sync_agents.py as canonical IDE adapter generator
- `/learn refactor` report (2026-02-28): agent-config scored #2 priority (265 points, 5 real issues)
