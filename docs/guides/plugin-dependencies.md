# Plugin Dependencies

Plugins can depend on other plugins and share context through a flat dependency system.

## Dependency Declaration

In your `SKILL.md` frontmatter:

```yaml
---
name: my-skill
dependencies:
  # Other Augur plugins this skill requires
  plugins:
    - notifications    # For alerts
    - knowledge        # For document search

  # Context this skill needs from dependencies
  context_requires:
    - from: knowledge
      data:
        - recent_documents
        - search_capability
    - from: notifications
      data:
        - send_notification

  # Context this skill provides to other plugins
  context_provides:
    - job_matches       # Career skill provides job match data
    - company_profiles  # Career skill provides company research

  # External dependencies
  mcp_servers: []
  python:
    - pyyaml
  npm: []
---
```

## How It Works

1. **Discovery**: When a skill is loaded, its dependencies are resolved
2. **Context Injection**: Dependencies provide their context data
3. **Flat Architecture**: No horizontal/vertical distinction - any plugin can depend on any other

## Example: Career Skill

```yaml
dependencies:
  plugins:
    - knowledge        # For document indexing
    - notifications    # For job alerts
    - capture          # For importing job postings

  context_requires:
    - from: knowledge
      data: [index_document, search_documents]
    - from: notifications
      data: [send_notification, raise_review]

  context_provides:
    - job_pipeline_status
    - company_research
    - interview_preparation
```

## Example: Health Skill

```yaml
dependencies:
  plugins:
    - notifications    # For health reminders
    - wearables        # For health data

  context_requires:
    - from: wearables
      data: [heart_rate, sleep_data, activity]
    - from: notifications
      data: [schedule_reminder]

  context_provides:
    - health_summary
    - medication_schedule
```

## Context Resolution

When a skill requests context from a dependency:

```python
from src.plugins.context import get_plugin_context

# Get context from a specific plugin
knowledge_ctx = get_plugin_context("knowledge")
results = knowledge_ctx.search_documents("job interview tips")

# Get context from all dependencies
all_ctx = get_plugin_context_for_skill("career")
```

## Providing Context to Others

If your plugin provides context to other plugins, create a `context.py` file:

```python
# plugins/{bundle}/skills/{skill}/context.py
from typing import Any

def get_provided_context() -> dict[str, Any]:
    """Return the context this plugin provides to others."""
    from plugins.{bundle}.skills.{skill}.lib.core import (
        my_function,
        another_function,
    )

    return {
        "my_function": my_function,
        "another_function": another_function,
    }
```

The keys in the returned dict must match what's declared in `context_provides` in SKILL.md.

### Scaffolding with Context Support

When creating a new plugin that will provide context:

```bash
python apps/dashboard/scripts/skill-scripts/scaffold.py \
    --name my-plugin \
    --category business \
    --description "My plugin" \
    --features mcp,dashboard,context
```

The `context` feature generates a `context.py` template automatically.

## External MCP Server Dependencies

Plugins can declare optional external MCP servers as dependencies. These are third-party
MCP servers (e.g., Bright Data for web scraping, Context7 for library docs) that extend
a plugin's capabilities when available.

### Declaring External MCP Servers

In your `SKILL.md` frontmatter, add `mcp_servers` at the top level or under `dependencies`:

```yaml
---
name: career
mcp_servers:
  - brightdata  # LinkedIn job scraping via Bright Data proxies
---
```

Or under dependencies:

```yaml
---
name: knowledge
dependencies:
  plugins: []
  mcp_servers:
    - context7  # Versioned library documentation
---
```

### How It Works

1. Available servers are defined in `config/integrations/external_mcp_registry.yaml`
2. Plugins declare which servers they need via `mcp_servers: [...]`
3. `configure_mcp.py` scans all SKILL.md files and includes matching servers in IDE configs
4. Servers with missing env vars are silently skipped (never fatal)
5. All external MCPs are **optional** - plugins must work without them

### API Keys and Secrets

External MCP servers that require API keys use env var resolution:

1. Copy `.env.mcp.example` to `.env.mcp` in `config/integrations/`
2. Fill in your API keys
3. Run `configure_mcp.py --apply` to update IDE configs
4. The `.env.mcp` file is gitignored

### CLI Commands

```bash
# List all available external MCP servers
python3 configure_mcp.py --list-external

# Validate declarations match registry
python3 configure_mcp.py --validate

# Configure without external servers
python3 configure_mcp.py --apply --no-external
```

### When to Declare an External MCP Server

Only declare `mcp_servers` when there's a genuine capability gap:
- Career skill needs `brightdata` because there's no other way to scrape LinkedIn
- Knowledge/Developer skills use `context7` for versioned library docs not available locally

Do **not** declare external MCPs when existing tools cover the need (e.g., `gh` CLI already
handles GitHub operations, so crew skills don't need a GitHub MCP).

### Registry Schema

Each server in `external_mcp_registry.yaml` has:

| Field | Description |
|-------|-------------|
| `name` | Display name |
| `description` | What the server does |
| `tier` | 1 (recommended), 2 (useful), 3 (specialized) |
| `cost` | free, paid, or existing (uses existing subscription) |
| `enabled` | Whether to include globally (even if no plugin requires it) |
| `command` | Command to run (e.g., `npx`) |
| `args` | Command arguments |
| `env` | Environment variables with `${VAR}` placeholders |
| `env_required` | List of required env vars with descriptions |

## Benefits Over Horizontal/Vertical Wiring

1. **Simpler**: No artificial horizontal/vertical categorization
2. **Flexible**: Any plugin can depend on any other
3. **Explicit**: Dependencies declared in SKILL.md, not external config
4. **Discoverable**: Easy to see what a plugin needs and provides
