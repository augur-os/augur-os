---
status: Deprecated
date: ''
deciders: []
related: []
hub: null
tags:
- community
- plugin
- extraction
- guide
superseded_by: null
---

# ADR-012: Community Plugin Extraction Guide

This guide documents the complete refactoring patterns established during ADR-012 implementation. Use it when extracting new plugins or auditing existing code for hardcoded references.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Checklist](#component-checklist)
3. [Refactoring Patterns](#refactoring-patterns)
4. [Best Practices](#best-practices)
5. [Anti-Patterns](#anti-patterns)

---

## Architecture Overview

### Two-Repository Structure

```
augur/                    # Core framework (pip-installable)
├── plugins/                  # Core + community plugins
│   ├── factory-*/           # Core factory bundles
│   ├── vertical-*/          # Community vertical bundles
│   └── services-*/          # Service bundles
├── plugins/
│   └── augur-mcp/       # Standalone MCP server
└── src/
    └── dashboard/           # Next.js dashboard

augur-data/              # User data (not in git)
├── career/                  # Career skill data
├── health/                  # Health skill data
└── config/                  # User configuration
```

### Plugin Discovery Order

1. **Core plugins** (`augur/plugins/`)
2. **User plugins** (`augur-plugins/`) - override core

### Plugin Bundles

```
PLUGIN_BUNDLES = [
    'dev',                # Core: developer, devops, frontend, validator, advisor
    'ai',                 # AI: ai_bridge, knowledge, mcp-app-factory, install, scraper
    'career',             # Career: career, content, growth, linkedin-writer
    'finance',            # Finance: finance, wealth
    'health',             # Health: health, wearables
    'lifestyle',          # Lifestyle: lifestyle
    'orchestration',      # Orchestration: executor, router, swarm
    'observability',      # Observability: daemon, metrics, observe
    'admin',              # Admin: channels, settings, updater
]
```

---

## Component Checklist

When extracting a plugin or removing hardcoded references, check ALL of these files:

### Python Files

| File | What to Check | Pattern |
|------|---------------|---------|
| `src/config/paths.py` | `SKILL_TO_DATA_BUNDLE` | Use `_discover_skill_to_bundle_mapping()` |
| `src/mcp/augur_mcp/context_injector.py` | Hub-to-skill mapping | Use `_discover_hub_to_skill_mapping()` |
| `src/mcp/augur_mcp/domain/*.py` | Hardcoded tool registrations | Move to plugin `mcp/__init__.py` |
| `src/config/mcp_tools.py` | Skill references in descriptions | Make generic or remove |
| `src/mcp/augur_mcp/tool_filter.py` | Skill name checks | Use pattern matching, not hardcoded names |

### TypeScript Files

| File | What to Check | Pattern |
|------|---------------|---------|
| `src/dashboard/lib/paths.ts` | `DATA_PATHS` | Use Proxy with plugin discovery |
| `src/dashboard/lib/tabs/registry.ts` | Hub fallbacks | Remove - let plugins provide |
| `src/dashboard/app/api/wizard/dashboards/route.ts` | `knownHubs` | Discover from dashboard.yaml |
| `src/dashboard/components/DashboardSelector.tsx` | `KNOWN_DASHBOARDS` | Fetch from API |
| `src/dashboard/app/actions.ts` | Skill-specific server actions | Move to plugin or remove |
| `src/dashboard/lib/services/*.ts` | Skill-specific services | Delete if unused |

### Configuration Files

| File | What to Check |
|------|---------------|
| `plugins/*/skills/*/dashboard.yaml` | Hub UI configuration |
| `plugins/*/skills/*/mcp/__init__.py` | MCP tool registration |
| `plugins/*/skills/*/tests/` | Plugin-specific tests |

---

## Refactoring Patterns

### Pattern 1: Python Auto-Discovery

**Before (hardcoded):**
```python
SKILL_TO_DATA_BUNDLE = {
    'career': 'career',
    'health': 'health',
}

def get_skill_bundle(skill_name: str) -> str | None:
    return SKILL_TO_DATA_BUNDLE.get(skill_name)
```

**After (auto-discovery):**
```python
PLUGIN_BUNDLES = [
    'dev', 'ai', 'career', 'finance', 'health',
    'lifestyle', 'orchestration', 'observability', 'admin',
]

_skill_to_bundle_cache: dict[str, str] | None = None

def _discover_skill_to_bundle_mapping() -> dict[str, str]:
    global _skill_to_bundle_cache
    if _skill_to_bundle_cache is not None:
        return _skill_to_bundle_cache

    mapping: dict[str, str] = {}
    for plugins_dir in get_all_plugin_dirs():
        for bundle in PLUGIN_BUNDLES:
            skills_dir = plugins_dir / bundle / 'skills'
            if not skills_dir.exists():
                continue
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith('.'):
                    mapping[skill_dir.name] = bundle

    _skill_to_bundle_cache = mapping
    return mapping

def get_skill_bundle(skill_name: str) -> str | None:
    return _discover_skill_to_bundle_mapping().get(skill_name)
```

### Pattern 2: TypeScript Strict Discovery (No Fallbacks)

**Before (hardcoded):**
```typescript
export const DATA_PATHS = {
  career: path.join(AUGUR_DATA_DIR, 'career/job-analyzer'),
  recipes: path.join(AUGUR_DATA_DIR, 'lifestyle/recipes/recipe-manager/recipes'),
};
```

**After (strict discovery - throws on missing):**
```typescript
/**
 * STRICT: Only skills with dashboard.yaml data_dir are accessible.
 * Throws error on unknown skills - no silent fallbacks.
 */
export const DATA_PATHS = new Proxy({} as Record<string, string>, {
  get(_target, prop: string): string {
    if (prop === 'dataRoot') return AUGUR_DATA_DIR;

    // Strict: only discovered skills are accessible
    return getSkillDataPath(prop);  // throws if not found
  },

  ownKeys(): string[] {
    return ['dataRoot', ...getDiscoveredSkills()];
  },

  has(_target, prop: string): boolean {
    if (prop === 'dataRoot') return true;
    return hasSkillDataPath(prop);
  },
});

// getSkillDataPath throws if skill not found:
export function getSkillDataPath(skillName: string): string {
  const mapping = discoverSkillDataPaths();
  const dataDir = mapping.get(skillName);

  if (dataDir) {
    return dataDir;
  }

  throw new Error(
    `[paths] Skill '${skillName}' not found. ` +
    `Ensure the skill has a dashboard.yaml with data_dir configured.`
  );
}
```

### Pattern 3: Plugin-Provided MCP Tools

**Before (core registration):**
```python
# src/mcp/augur_mcp/domain/careers.py
def register_career_tools(mcp, interceptor, metrics):
    @mcp.tool()
    async def get_career_jobs(): ...
```

**After (plugin-provided):**
```python
# plugins/career/skills/career/mcp/__init__.py
def register_tools(mcp, interceptor, metrics):
    @mcp.tool()
    async def get_career_jobs(): ...
```

**Core loader:**
```python
# src/mcp/augur_mcp/plugin_tools.py
def register_plugin_tools(mcp, interceptor, metrics) -> int:
    count = 0
    for plugins_dir in get_all_plugin_dirs():
        for bundle in PLUGIN_BUNDLES:
            skills_dir = plugins_dir / bundle / 'skills'
            if not skills_dir.exists():
                continue
            for skill_dir in skills_dir.iterdir():
                mcp_init = skill_dir / 'mcp' / '__init__.py'
                if mcp_init.exists():
                    module = load_module_from_path(mcp_init)
                    if hasattr(module, 'register_tools'):
                        module.register_tools(mcp, interceptor, metrics)
                        count += 1
    return count
```

### Pattern 4: Dashboard.yaml for Hub Configuration

**Plugin provides:**
```yaml
# plugins/career/skills/career/augur.yaml
hub:
  id: career
  title: Career
  subtitle: Job search and interview preparation
  icon: Briefcase

tabs:
  - id: overview
    label: Overview
    default: true
    icon: LayoutDashboard
  - id: pipeline
    label: Pipeline
    icon: GitBranch
```

**Core discovers:**
```typescript
// src/dashboard/lib/plugin-schema/loader.ts
export async function discoverPluginDashboards(): Promise<PluginDashboard[]> {
  const dashboards: PluginDashboard[] = [];
  for (const pluginsDir of getAllPluginDirs()) {
    for (const bundle of PLUGIN_BUNDLES) {
      const skillsDir = path.join(pluginsDir, bundle, 'skills');
      // ... scan for dashboard.yaml
    }
  }
  return dashboards;
}
```

### Pattern 5: Remove Fallbacks (Expose Bugs)

**Before (hides bugs):**
```typescript
// If plugin not found, use hardcoded fallback
const config = pluginConfig || HARDCODED_FALLBACKS[hubKey];
```

**After (exposes bugs):**
```typescript
// No fallback - if plugin missing, feature doesn't appear
const config = await loadPluginDashboardByHubId(hubKey);
if (!config) {
  console.warn(`Hub '${hubKey}' not found - no plugin provides it`);
  return null;
}
```

### Pattern 6: Move Tests to Plugins

**Before:**
```
src/tests/integration/test_career_flow.py
```

**After:**
```
plugins/career/skills/career/tests/test_career_flow.py
```

Tests stay with the plugin but are executed by the central test framework:
```bash
pytest plugins/career/skills/career/tests/
```

---

## Best Practices

### 1. Use Environment Variables for Plugin Paths

```python
# Python
def get_all_plugin_dirs() -> list[Path]:
    dirs = []
    if os.environ.get('AUGUR_PLUGINS'):
        dirs.append(Path(os.environ['AUGUR_PLUGINS']))
    else:
        dirs.append(get_project_root() / 'plugins')
    # ... user plugins
    return dirs
```

```typescript
// TypeScript
function getAllPluginDirs(): string[] {
  const dirs: string[] = [];
  if (process.env.AUGUR_PLUGINS) {
    dirs.push(process.env.AUGUR_PLUGINS);
  } else {
    dirs.push(path.join(AUGUR_ROOT, 'plugins'));
  }
  return dirs;
}
```

### 2. Cache Discovery Results

```python
_cache: dict[str, str] | None = None

def discover_mappings() -> dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    # ... expensive discovery
    _cache = result
    return result

def invalidate_cache():
    global _cache
    _cache = None
```

### 3. Use dashboard.yaml for All Plugin Config

```yaml
# dashboard.yaml
hub:
  id: career
  title: Career
  subtitle: Job search

# REQUIRED: data directory configuration (no fallbacks)
data_dir: career  # relative to data repo

tabs: [...]
widgets: [...]
modals: [...]
```

**STRICT MODE**: `data_dir` is required for TypeScript discovery. Skills without it will throw errors when accessed.

### 4. Document Plugin Interfaces

Every plugin interface should be documented:

```python
# plugins/career/skills/career/mcp/__init__.py
"""
MCP Tools for Career Plugin.

Required function:
    register_tools(mcp, interceptor, metrics) -> None

This function is called by the core MCP server during startup.
"""
def register_tools(mcp, interceptor, metrics):
    ...
```

---

## Anti-Patterns

### 1. Hardcoded Skill Names

```python
# BAD
if skill_name == 'career':
    return 'career'

# GOOD
return _discover_skill_to_bundle_mapping().get(skill_name)
```

### 2. Hardcoded Hub Lists

```typescript
// BAD
const KNOWN_HUBS = ['career', 'health', 'lifestyle'];

// GOOD
const hubs = await discoverPluginDashboards();
```

### 3. Fallbacks of Any Kind

```typescript
// BAD - hides missing plugin
const config = pluginConfig || HARDCODED_FALLBACK;

// BAD - silent default
const dataDir = mapping.get(skill) || path.join(DATA_DIR, skill);

// GOOD - exposes missing plugin with clear error
if (!pluginConfig) {
  throw new Error(`Plugin not found: ${hubId}`);
}

// GOOD - explicit error
const dataDir = mapping.get(skill);
if (!dataDir) {
  throw new Error(`Skill '${skill}' not found. Add data_dir to dashboard.yaml.`);
}
```

### 4. Tests Outside Plugin

```
# BAD
src/tests/integration/test_career_flow.py

# GOOD
plugins/career/skills/career/tests/test_career_flow.py
```

### 5. Core Knowing Plugin Internals

```python
# BAD - core knows plugin's internal structure
career_jobs_path = data_dir / 'job-analyzer' / 'jobs' / 'inbox'

# GOOD - plugin provides its paths
from careers.paths import get_jobs_inbox_path
```

---

## Verification Checklist

After extracting a plugin, verify:

- [ ] No hardcoded references to plugin name in core
- [ ] Plugin provides its own MCP tools via `mcp/__init__.py`
- [ ] Plugin provides its own UI via `dashboard.yaml`
- [ ] Plugin has `data_dir` in `dashboard.yaml` (REQUIRED for TypeScript)
- [ ] Plugin has its own tests under `tests/`
- [ ] Core discovers plugin at runtime
- [ ] Missing plugin causes **ERROR** (not warning, not fallback)
- [ ] Environment variables allow path override
- [ ] Discovery results are cached for performance
- [ ] No legacy/backwards compatibility mappings

---

## Files Modified During ADR-012

| File | Change |
|------|--------|
| `src/config/paths.py` | Auto-discovery of skill-to-bundle mapping |
| `src/dashboard/lib/paths.ts` | Proxy-based DATA_PATHS with discovery |
| `src/dashboard/lib/tabs/registry.ts` | Removed career/health fallbacks |
| `src/mcp/augur_mcp/context_injector.py` | Hub-to-skill auto-discovery |
| `src/mcp/augur_mcp/plugin_tools.py` | Plugin MCP tool loader |
| `src/dashboard/app/api/wizard/dashboards/route.ts` | Plugin dashboard discovery |
| `src/dashboard/components/.../DashboardSelector.tsx` | API-based dashboard list |
| `src/dashboard/app/actions.ts` | Removed dead career code |
| `plugins/career/skills/career/mcp/__init__.py` | Plugin-provided MCP tools |
| `plugins/health/skills/health/mcp/__init__.py` | Plugin-provided MCP tools |
