---
status: Implemented
date: '2026-02-04'
deciders:
- Augur Team
related: []
hub: null
tags:
- portable
- plugin
- template
- standard
superseded_by: null
---

# ADR-040: Portable Plugin Template Standard

**Supersedes**: ADR-022 (Plugin Standardization and Compliance Audit)
**Extends**: ADR-029 (4-Bundle Architecture), ADR-008 (Plugin System)

## Context

The Augur plugin system has evolved through three major ADRs:
- **ADR-008** established the plugin concept (bundles, hooks, commands)
- **ADR-022** mandated 24 required files per plugin for standardization
- **ADR-029** organized plugins into 4 bundles (crew, orchestrator, services, apps)

Three problems remain:

**1. One-size-fits-all is impractical.** ADR-022 requires 24 files for every plugin — including `api/health/route.ts`, `schemas/`, `package.json`, and `backlog/` directories — even for agent-only skills like `developer` or `architect` that have no UI, no API routes, and no data schemas. Most plugins don't comply because the bar is artificially high.

**2. No portability.** Augur plugins mix standard MCP-compatible elements (tool definitions, Python handlers, SKILL.md metadata) with Augur-specific extensions (dashboard UI, chains, tiers, safety config) in the same structure with no clear boundary. Exporting a plugin for use outside Augur requires ad-hoc stripping. The existing `skill_exporter.py` only handles crew skills and uses brittle string matching to remove Augur references.

**3. Terminology is ambiguous.** "Plugin", "skill", and "bundle" are used inconsistently across documentation and code. Some files use "plugin" to mean a single skill; others use it to mean an entire bundle. There is no formal definition of what constitutes a portable, distributable unit.

## Decision

### 1. Terminology — Clear Boundaries

| Term | Definition | Contains | Example |
|------|-----------|----------|---------|
| **Skill** | The atomic capability unit. A SKILL.md file plus its handlers (scripts, modules, or MCP tools). | SKILL.md + code | `developer`, `career`, `ai-bridge` |
| **Plugin** | A skill packaged for the Augur system. Includes the skill core plus Augur-specific extensions (UI, chains, config). | Skill + Augur extensions | `plugins/career/skills/career/` |
| **Bundle** | A collection of related plugins grouped by responsibility. | Plugins | `crew/`, `services/`, `apps/`, `orchestrator/` |
| **Package** | An exported plugin with Augur extensions stripped. Portable and compatible with standard tooling (Claude Code plugins, standalone MCP servers, Python plugins). | Skill core only | `augur-career-v1.0.0.tar.gz` |

**Key principle**: `Plugin = Skill Core + Augur Extensions`. Export strips extensions to produce a Package.

### 2. Two-Layer Architecture

Every plugin consists of two clearly separated layers:

#### Layer 1 — Standard Core (Portable)

Elements that follow industry standards and survive export. These map directly to Anthropic's MCP tool format or standard Python/Claude Code packaging.

```
{skill}/
├── SKILL.md              # Tool metadata (name, version, description, triggers)
├── scripts/              # Python tool handlers
├── requirements.txt      # Python dependencies
├── README.md             # Developer documentation
└── tests/                # Test files (pytest, jest)
```

**SKILL.md Standard Core frontmatter:**
```yaml
---
# === Standard Core (Layer 1) ===
name: career
version: 1.0.0
description: Job search and interview preparation

triggers:
  - job search
  - interview prep
  - resume review

dependencies:
  python: [requests, beautifulsoup4]
  npm: []
---
```

These fields map to standard formats:
- `name` + `description` → MCP tool `name` + `description`
- `version` → semver, standard across ecosystems
- `triggers` → Claude Code command triggers / MCP tool discovery hints
- `dependencies.python` / `dependencies.npm` → `requirements.txt` / `package.json`

#### Layer 2 — Augur Extensions (Stripped on Export)

Augur-specific elements marked with `# @augur` comments. These provide the rich system integration that makes Augur powerful but are not needed for standalone operation.

**Extension directories:**
```
{skill}/
├── dashboard.yaml        # @augur: Hub UI configuration
├── dashboard/            # @augur: React/Next.js UI components
│   ├── page.tsx
│   ├── layout.tsx
│   ├── loading.tsx
│   └── tabs/
├── chains/               # @augur: Multi-step workflow definitions
├── modules/              # @augur: AI context loading documentation
├── references/           # @augur: Deep-dive guides and workflows
├── mcp/                  # @augur: Augur MCP gateway tool registration
├── api/                  # @augur: Next.js API routes
├── schemas/              # @augur: YAML data validation schemas
├── backlog/              # @augur: Bug/feature/improvement tracking
├── lib/                  # @augur: Shared Python libraries (Augur-specific)
├── config/               # @augur: Augur configuration files
└── version.yaml          # @augur: Augur version metadata
```

**SKILL.md Extension frontmatter:**
```yaml
---
# === Standard Core (Layer 1) ===
name: career
version: 1.0.0
description: Job search and interview preparation
triggers:
  - job search
  - interview prep
dependencies:
  python: [requests]
  npm: []

# === Augur Extensions (Layer 2) ===       # @augur-start
category: business                          # @augur
mode: operation                             # @augur

tiers:                                      # @augur
  low:                                      # @augur
    capability: fast                        # @augur
    mode: advisory                          # @augur
  high:                                     # @augur
    capability: reasoning                   # @augur
    mode: executor                          # @augur

safety:                                     # @augur
  read_only_mode: false                     # @augur
  protected_areas: [payments]               # @augur

dependencies:                               # @augur
  plugins: [knowledge]                      # @augur
  mcp_servers: [brightdata]                 # @augur
  context_provides: [search_jobs]           # @augur
  context_requires:                         # @augur
    - from: knowledge                       # @augur
      data: [semantic_search]               # @augur
# @augur-end
---
```

**Marker convention:**
- `# @augur` on individual lines — marks that line as Augur-specific
- `# @augur-start` / `# @augur-end` — marks a block of Augur-specific content
- Exporter strips all lines/blocks with these markers
- Markers are YAML comments, so they don't break parsing

### 3. Plugin Profiles (Replace 24-File Mandate)

Instead of requiring 24 files for every plugin, define three profiles based on plugin complexity. Profile is **auto-detected** based on directory contents.

#### Minimal Profile

**For**: Agent-only skills with no UI (crew agents, orchestrator skills)
**Auto-detect**: No `dashboard.yaml` file present

**Required:**
| File | Purpose |
|------|---------|
| `SKILL.md` | Valid frontmatter with `name`, `version`, `description` |
| One of: `scripts/`, `modules/`, `mcp/` | At least one capability implementation |

**Recommended:**
| File | Purpose |
|------|---------|
| `README.md` | Developer documentation (can be auto-generated from SKILL.md) |
| `version.yaml` | Version tracking |
| `tests/` | At least one test file |

**Examples**: `crew/developer`, `crew/architect`, `crew/validator`, `orchestrator/router`

#### Standard Profile

**For**: Skills with dashboard UI but no complex data layer
**Auto-detect**: `dashboard.yaml` exists, no `api/` directory

**Required (everything in Minimal plus):**
| File | Purpose |
|------|---------|
| `dashboard.yaml` | Hub configuration (tabs, actions) |
| `dashboard/page.tsx` | Main page component |
| `dashboard/layout.tsx` | Layout with tabs |
| `dashboard/loading.tsx` | Suspense loading skeleton |
| `tests/` | At least one test file (Python or TypeScript) |

**Recommended:**
| File | Purpose |
|------|---------|
| `dashboard/tabs/OverviewTab.tsx` | Default overview tab |
| `chains/` | Workflow definitions |

**Examples**: `services/ai-bridge`, `services/channels`, `crew/mcp-app-factory`

#### Full Profile

**For**: User-facing apps with data persistence, API routes, and MCP tools
**Auto-detect**: `api/` directory exists

**Required (everything in Standard plus):**
| File | Purpose |
|------|---------|
| `api/health/route.ts` | Health check endpoint |
| `mcp/__init__.py` | MCP tool registration |
| `mcp/tools.py` | MCP tool implementations |
| `version.yaml` | Version and metadata tracking |
| `requirements.txt` | Python dependencies (can be empty) |

**Recommended:**
| File | Purpose |
|------|---------|
| `schemas/{name}.schema.yaml` | Data validation schema |
| `chains/{name}.yaml` | At least one workflow |
| `backlog/BACKLOG.md` | Improvement tracking |
| `lib/` | Shared utility code |

**Examples**: `apps/career`, `apps/health`, `apps/finance`, `services/knowledge`

#### Profile Detection Logic

```python
def detect_profile(skill_path: Path) -> str:
    """Auto-detect plugin profile from directory contents."""
    if (skill_path / "api").is_dir():
        return "full"
    elif (skill_path / "dashboard.yaml").exists():
        return "standard"
    else:
        return "minimal"
```

### 4. Export Mechanism

Enhance the existing `skill_exporter.py` to support structured, marker-based export across all bundles.

#### Export Targets

| Target | Output | Use Case |
|--------|--------|----------|
| `claude-code` | `.claude-plugin/` directory with plugin.json, skills/, agents/, commands/ | Distribute as Claude Code plugin |
| `mcp-server` | Standalone MCP server with `server.py`, tool definitions, requirements.txt | Run as independent MCP server |
| `python-package` | `pyproject.toml` + `src/` layout with tool functions | Publish to PyPI |

#### Export Process

```
1. Parse SKILL.md → split Layer 1 (standard) from Layer 2 (@augur markers)
2. Copy Layer 1 files (scripts/, tests/, requirements.txt, README.md)
3. Strip @augur markers from SKILL.md frontmatter
4. Skip Layer 2 directories (dashboard/, chains/, modules/, api/, etc.)
5. Generate target-specific packaging (plugin.json, server.py, or pyproject.toml)
```

#### What Changes in `skill_exporter.py`

| Current Behavior | New Behavior |
|-----------------|-------------|
| Only exports `crew/` skills | Exports any bundle |
| Ad-hoc string matching to strip Augur references | Structured `# @augur` marker stripping |
| Only `claude-code` target | Three export targets |
| Brittle section-name matching | Marker-based, deterministic |

### 5. SKILL.md Schema (Strict Definition)

#### Required Fields (All Profiles)

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Skill identifier (kebab-case, matches directory name) |
| `version` | string | Semantic version (x.y.z) |
| `description` | string | One-line description (<100 chars) |

#### Optional Standard Fields (Layer 1)

| Field | Type | Description |
|-------|------|-------------|
| `triggers` | list[string] | Activation phrases for skill discovery |
| `dependencies.python` | list[string] | Python package dependencies |
| `dependencies.npm` | list[string] | Node.js package dependencies |

#### Optional Augur Extension Fields (Layer 2, marked `# @augur`)

| Field | Type | Description |
|-------|------|-------------|
| `category` | enum | `system`, `productivity`, `personal`, `business` |
| `mode` | enum | `all`, `dev`, `operation` |
| `status` | enum | `active`, `deprecated` |
| `tiers` | object | Agent capability tiers (`low`, `medium`, `high`) |
| `safety` | object | Safety constraints (`read_only_mode`, `protected_areas`, `circuit_breaker`) |
| `alignment` | object | Design alignment flags |
| `dependencies.plugins` | list[string] | Other Augur plugins |
| `dependencies.mcp_servers` | list[string] | External MCP servers |
| `dependencies.context_provides` | list[string] | Capabilities exposed to other skills |
| `dependencies.context_requires` | list[object] | Capabilities needed from other skills |

### 6. Validation Rules (Per-Profile)

Update `plugin-spec.yaml` and `audit.py` to validate per-profile:

```yaml
validation:
  all_profiles:
    - "SKILL.md exists with valid frontmatter"
    - "name, version, description are present"
    - "name matches directory name"
    - "No hardcoded paths"
    - "No print() in library code"
    - "Uses augur_logging if logging"

  minimal:
    - "At least one of: scripts/, modules/, mcp/"

  standard:
    - "Everything in minimal"
    - "dashboard.yaml has required hub fields"
    - "dashboard/page.tsx exists"
    - "dashboard/layout.tsx exists"
    - "dashboard/loading.tsx exists"
    - "At least one test file"

  full:
    - "Everything in standard"
    - "api/health/route.ts exists"
    - "mcp/__init__.py exists"
    - "version.yaml exists"
```

### 7. Bundle-to-Profile Mapping (Guidance)

| Bundle | Typical Profile | Rationale |
|--------|----------------|-----------|
| `crew/` | Minimal | Agents don't need UI or API routes |
| `orchestrator/` | Minimal | Coordination logic, no user-facing UI |
| `services/` | Standard | Infrastructure with monitoring dashboards |
| `apps/` | Full | User-facing applications with data and APIs |

These are defaults — exceptions are fine. A service with complex data (like `knowledge`) can be Full. A crew skill with a management UI (like `mcp-app-factory`) can be Standard or Full.

## Consequences

### Positive

- **Portability**: Any Augur plugin can be exported to Claude Code, standalone MCP server, or Python package by stripping Layer 2
- **Lower barrier**: Minimal profile requires only 2-3 files vs. 24 — new skills are easy to create
- **Clear boundaries**: Terminology is unambiguous; Layer 1 vs Layer 2 is explicit in the code via `# @augur` markers
- **Gradual adoption**: Existing plugins can add `# @augur` markers incrementally without restructuring
- **Ecosystem alignment**: Layer 1 follows Anthropic MCP standard exactly; Augur additions are clearly marked as extensions
- **Self-documenting**: `# @augur` markers make it obvious which parts are Augur-specific when reading any file

### Negative

- **Marker maintenance**: Every Augur-specific frontmatter field needs `# @augur` comments; forgetting them breaks export
- **ADR-022 superseded**: Teams familiar with the 24-file standard need to learn the profile system
- **Export tooling**: `skill_exporter.py` needs significant enhancement to support all targets and bundles

### Neutral

- The 4-bundle architecture (ADR-029) is unchanged
- Existing plugin directory structure is unchanged — this adds markers and removes mandatory file requirements
- The central MCP server architecture (ADR-008) is unchanged
- `dashboard.yaml` schema (from `plugin-spec.yaml`) is unchanged

## Migration Plan

### Phase 1: Marker Convention (Low effort)
- Add `# @augur` markers to SKILL.md extension fields in all 30+ plugins
- No functional change; purely documentation

### Phase 2: Profile-Based Validation
- Update `plugin-spec.yaml` to define profiles instead of flat required_files
- Update `audit.py` to auto-detect profile and validate accordingly
- Existing Full-profile plugins still pass; Minimal plugins stop failing

### Phase 3: Exporter Enhancement
- Extend `skill_exporter.py` to handle all bundles (not just crew)
- Implement `# @augur` marker stripping (replace brittle string matching)
- Add `mcp-server` and `python-package` export targets

### Phase 4: Template Update
- Update `SKILL.md.template` to include Layer 1 / Layer 2 sections with markers
- Update `plugin-spec.yaml` templates section to show profile-specific templates
- Update factory pipeline (`skill_generator.py`) to generate profile-appropriate scaffolding

## Alternatives Considered

### Alternative 1: Separate Standard and Extension Files

Keep standard metadata in `SKILL.md` and Augur extensions in a separate `AUGUR.yaml` file. Rejected because:
- Two files to maintain instead of one
- Frontmatter fields that affect skill behavior (tiers, safety) would be disconnected from the skill definition
- More complex tooling to merge/split

### Alternative 2: Keep 24-File Mandate with Exceptions

Add "exception" flags to `plugin-spec.yaml` for skills that don't need all files. Rejected because:
- Exception-based systems accumulate technical debt
- Every new skill would need to declare exceptions
- Profiles are a cleaner abstraction that matches real usage patterns

### Alternative 3: Per-Bundle Templates

Define different templates for crew, services, apps, orchestrator. Rejected because:
- Bundle doesn't determine complexity (a service can be simple or complex)
- Profile-based detection is more accurate than bundle-based
- Would create 4 templates to maintain instead of 3 profiles on one template

## Distribution

Exported plugins are distributed as individual tarballs via GitHub Releases.
Export is triggered manually via the `export-plugins.yml` workflow
(`Actions → Export Plugins → Run workflow`). Each tarball contains a
self-contained Claude Code plugin with `plugin.json` manifest.

Exported plugins are NOT committed to the repository. The previous
`plugins/claude-plugins/` directory has been removed and gitignored.

## References

- [ADR-008: Plugin System for IDE Agents](./ADR-008-plugin-system.md) — Original plugin architecture
- [ADR-022: Plugin Standardization and Compliance Audit](./ADR-022-plugin-standardization.md) — Superseded by this ADR
- [ADR-029: Plugin Architecture Refactoring (4-Bundle)](./ADR-029-plugin-architecture-refactoring.md) — Bundle structure (unchanged)
- `plugins/ai/skills/mcp-app-factory/plugin-spec.yaml` — Current plugin specification (to be updated)
- `plugins/ai/skills/mcp-app-factory/scripts/audit.py` — Current compliance audit (to be updated)
- `plugins/ai/skills/mcp-app-factory/scripts/skill_exporter.py` — Current exporter (to be enhanced)
- `plugins/ai/skills/mcp-app-factory/templates/SKILL.md.template` — Current SKILL.md template (to be updated)
- [Anthropic MCP Specification](https://modelcontextprotocol.io/) — Standard that Layer 1 aligns to
