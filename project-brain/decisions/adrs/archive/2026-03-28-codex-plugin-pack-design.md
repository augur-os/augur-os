# Codex Plugin Support & Plugin-Pack Skill

**Date:** 2026-03-28
**Status:** Draft
**Extends:** ADR-503 (Distribution Plugin Architecture)

## Summary

Codex now has a plugin system (`.codex-plugin/plugin.json`, marketplace discovery, skills bundling). Augur should be a first-class Codex plugin. This design renames `cowork` to `plugin-pack`, refactors the assembler into a shared pipeline with per-target formatters, adds a Codex formatter, and updates the onboarding flow to support installation from within Codex.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Skill strategy | Extend cowork, rename to `plugin-pack` | Avoids duplication; cowork already solves discovery + transformation |
| Architecture | Single assembler + target formatters | 2 targets today, more coming; formatter pattern handles format differences cleanly |
| Skill filtering | Configurable per target | Codex is a dev CLI (includes dev skills), Claude Desktop is consumer (curated only) |
| Marketplace install | Global + repo-scoped | Global ensures availability everywhere; repo-scoped for Augur project context |
| Onboarding entry | install.sh + Codex-native bootstrapper | Shell script is reliable; bootstrapper makes it seamless from within Codex |
| Backward compat | None (rule 14) | Clean rename, no aliases or redirects |

## Section 1: Skill Rename & Shared Assembly Pipeline

### Directory Structure

```
skills/plugin-pack/
├── SKILL.md
├── scripts/
│   ├── plugin_assembler.py      # Shared pipeline
│   ├── formatters/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseFormatter ABC
│   │   ├── cowork.py            # Claude Desktop formatter
│   │   └── codex.py             # Codex plugin formatter
│   └── profiles.py              # Target filter profiles
├── assets/
│   └── templates/               # Hub-specific SKILL.md templates
└── augur/
    ├── dashboard/
    └── tests/
```

### Shared Pipeline (`plugin_assembler.py`)

Four-stage pipeline:

1. **`discover_skills(profile)`** -- scan `skills/*/SKILL.md`, filter by profile (hubs, prefix exclusions, explicit exclusions)
2. **`transform_skills(skills, templates_dir)`** -- apply SKILL.md transformations (strip paths, bash snippets, apply template overrides)
3. **`assemble(target, output_dir)`** -- orchestrate: discover -> transform -> format -> write
4. **`install(target, plugin_dir)`** -- install to platform-specific location

### Filter Profiles (`profiles.py`)

```python
@dataclass
class FilterProfile:
    name: str
    hubs: frozenset[str]
    excluded_prefixes: tuple[str, ...]
    excluded_skills: frozenset[str]
    commands: dict[str, dict]  # name -> {description, body}

COWORK_PROFILE = FilterProfile(
    name="cowork",
    hubs=frozenset({"brain", "career", "life", "studio"}),
    excluded_prefixes=("auto-", "dev-", "client-"),
    excluded_skills=frozenset({
        "ai", "commands", "rag", "scraper", "advisor", "developer",
        "frontend", "renderer", "page-builder", "dashboard", "daemon",
        "kill-augur", "system-cleanup", "test-client", "test-ui",
        "validator", "mcp-app-factory", "devops", "nightly",
        "reindex-project", "auto-rag-reindex", "sync-agents", "onboard",
        "updater", "remote-access", "executor", "discovery", "workflows",
        "file-manager", "observe", "metrics", "enterprise", "plugin-pack",
    }),
    commands={
        "ask": {"description": "Ask your second brain any question", "body": "..."},
        "search": {"description": "Search knowledge across all sources", "body": "..."},
        "save": {"description": "Save information to your knowledge base", "body": "..."},
    },
)

CODEX_PROFILE = FilterProfile(
    name="codex",
    hubs=frozenset({"brain", "career", "life", "studio", "command"}),
    excluded_prefixes=("auto-", "client-"),
    excluded_skills=frozenset({
        "ai", "commands", "rag", "scraper", "advisor",
        "frontend", "renderer", "page-builder", "dashboard", "daemon",
        "kill-augur", "system-cleanup", "test-client", "test-ui",
        "validator", "mcp-app-factory", "devops", "nightly",
        "reindex-project", "auto-rag-reindex", "sync-agents",
        "updater", "remote-access", "executor", "discovery", "workflows",
        "file-manager", "observe", "metrics", "enterprise", "plugin-pack",
        "reload-dashboard", "deploy-website",
    }),
    commands={
        "ask": {"description": "Ask your second brain any question", "body": "..."},
        "search": {"description": "Search knowledge across all sources", "body": "..."},
        "save": {"description": "Save information to your knowledge base", "body": "..."},
    },
)
```

Key differences: Codex profile includes `command` hub and allows `dev-*` prefixed skills (dev-test, dev-merge, dev-build, etc.).

### BaseFormatter ABC

```python
class BaseFormatter(ABC):
    @abstractmethod
    def write_manifest(self, output_dir: Path, version: str) -> None: ...

    @abstractmethod
    def write_mcp_config(self, output_dir: Path, project_root: Path, python_path: str) -> None: ...

    @abstractmethod
    def write_marketplace(self, output_dir: Path, version: str) -> None: ...

    @abstractmethod
    def write_skills(self, output_dir: Path, skills: dict[str, str]) -> None: ...

    @abstractmethod
    def install(self, plugin_dir: Path, version: str) -> bool: ...
```

## Section 2: Codex Plugin Formatter

### Output Structure

```
build/codex/
├── .agents/
│   └── plugins/
│       └── marketplace.json
└── plugins/
    └── augur/
        ├── .codex-plugin/
        │   └── plugin.json
        ├── skills/
        │   ├── ask/SKILL.md
        │   ├── search/SKILL.md
        │   └── .../SKILL.md
        ├── .mcp.json
        └── assets/
            └── icon.png
```

### plugin.json (Codex format)

```json
{
  "name": "augur",
  "version": "0.20260328.0",
  "description": "Your second brain -- personal knowledge, career, finance, health, and productivity powered by Augur",
  "author": { "name": "Gur Sannikov" },
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "interface": {
    "displayName": "Augur",
    "shortDescription": "Personal knowledge system & second brain",
    "category": "Productivity",
    "capabilities": ["Read", "Write"]
  }
}
```

### .mcp.json (Codex format)

```json
{
  "mcpServers": {
    "augur": {
      "command": "/path/to/.venv/bin/python3",
      "args": ["-m", "augur_mcp", "--client-id", "codex"],
      "cwd": "/path/to/Augur",
      "env": {
        "AUGUR_ROOT": "/path/to/Augur",
        "PYTHONPATH": "/path/to/Augur:/path/to/Augur/src/mcp",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### marketplace.json

```json
{
  "name": "augur-local",
  "interface": { "displayName": "Augur Local" },
  "plugins": [{
    "name": "augur",
    "source": { "source": "local", "path": "./plugins/augur" },
    "policy": { "installation": "INSTALLED_BY_DEFAULT", "authentication": "ON_INSTALL" },
    "category": "Productivity"
  }]
}
```

### Install Locations

| Target | Path |
|--------|------|
| Plugin cache | `~/.codex/plugins/cache/augur-local/augur/{version}/` |
| Global marketplace | `~/.agents/plugins/marketplace.json` (merge augur entry) |
| Repo marketplace | `{project_root}/.agents/plugins/marketplace.json` (full manifest) |
| MCP wiring | Existing `config.toml` entry via `configure_mcp.py` (unchanged) |

The global marketplace install must merge into an existing file (other plugins may be registered). Read existing entries, add/update augur, write back.

## Section 3: Onboarding Flow Updates

### 3a. install.sh Additions

After the existing `configure_mcp.py --client codex` step:

```bash
# Install Codex plugin (after MCP wiring)
if [[ "$CONFIGURE_CLIENTS" == *"codex"* ]] || [[ "$INSTALL_SOURCE" == "codex" ]]; then
    log_info "Installing Codex plugin..."
    "$VENV_PYTHON" skills/plugin-pack/scripts/plugin_assembler.py \
        --target codex --install
fi
```

### 3b. Codex Bootstrap Skill

A standalone SKILL.md that can be dropped into `~/.codex/skills/augur-bootstrap/`:

```
skills/onboard/assets/codex-bootstrap/SKILL.md
```

Contents: instructions for the Codex agent to check Augur installation state, clone + run `install.sh --from codex` if needed, or run plugin assembly if Augur exists but the plugin is missing.

Distribution one-liner:

```bash
mkdir -p ~/.codex/skills/augur-bootstrap && \
  curl -o ~/.codex/skills/augur-bootstrap/SKILL.md \
  https://raw.githubusercontent.com/augur-os/augur-os/main/skills/onboard/assets/codex-bootstrap/SKILL.md
```

### 3c. onboard --status Update

Extend status check to report Codex plugin state:

```
codex-mcp:    configured (config.toml)
codex-plugin: installed v0.20260328.0 (~/.codex/plugins/cache/augur-local/augur/)
codex-marketplace-global: present (~/.agents/plugins/marketplace.json)
codex-marketplace-repo:   present (.agents/plugins/marketplace.json)
```

## Section 4: Reference Updates & Migration

### Rename Migration Checklist

| Location | Change |
|----------|--------|
| `skills/cowork/` | Move to `skills/plugin-pack/` |
| `cowork_assembler.py` | Rename to `plugin_assembler.py` |
| `_COWORK_EXCLUDED_SKILLS` | Remove "cowork", add "plugin-pack" |
| `--client-id cowork` in MCP args | Keep as-is (client identity, not skill name) |
| SKILL.md frontmatter | Update name, description |
| Hub config references | Update skill name in `x-augur-*` refs |
| CLAUDE.md slash commands | `/cowork` -> `/plugin-pack` |
| Dashboard pages referencing cowork | Update imports/routes |
| Test files | Update paths and imports |
| `install.sh` | Replace "cowork" skill references |
| Generated registries | Re-run generators after rename |

Per CLAUDE.md rule 14: no backward-compatibility stubs. Clean rename.

Per CLAUDE.md rule 23: exhaustive path migration with system grep + split-segment search.

### ADR

Write ADR extending ADR-503 to capture:
- Why: Codex plugin system support
- What: Rename cowork to plugin-pack, add Codex target, update onboarding
- Decision: Single assembler with per-target formatters

## Section 5: Scope & Non-Goals

### In Scope

- Rename `cowork` to `plugin-pack` with full reference migration
- Refactor assembler into shared pipeline + formatter pattern
- `CodexFormatter` producing Codex-native plugin structure
- Per-target filter profiles
- Install to `~/.codex/plugins/cache/` + both marketplace locations
- `install.sh --from codex` triggers plugin assembly + install
- Codex bootstrap SKILL.md for onboarding from within Codex
- `onboard --status` reports Codex plugin state
- ADR documenting the decision

### Not In Scope (Future Work)

- Gemini/Cursor/Windsurf plugin formatters
- Publishing to Codex public plugin directory
- `.app.json` generation for Codex apps (OAuth integrations)
- Plugin auto-update mechanism
- Dashboard UI for plugin management
