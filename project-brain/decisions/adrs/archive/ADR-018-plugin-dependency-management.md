---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- plugin
- dependency
- management
superseded_by: null
---

# ADR-018: Plugin Dependency Management

## Date
2026-01-23

## Context

The Augur system uses a plugin architecture where skills are self-contained modules. Each plugin may have Python dependencies beyond the core requirements. Previously, all dependencies were managed in the root `requirements.txt`, which caused issues:

1. **Scalability**: As plugins grow, the root requirements file becomes bloated with dependencies many users don't need
2. **Isolation**: Plugin-specific dependencies should be managed by the plugin, not globally
3. **User Experience**: Users installing the core system shouldn't need heavy ML libraries (sentence-transformers, chromadb) unless they enable those plugins
4. **Portability**: Plugins should be independently deployable

## Decision

### 1. Core vs Plugin Dependencies

**Core dependencies** (`requirements.txt` at repo root):
- Framework essentials: `mcp`, `pyyaml`, `pydantic`, `pydantic-settings`
- Common utilities: `requests`, `aiohttp`, `httpx`, `python-dotenv`
- Development tools: `pytest`, `ruff`

**Plugin dependencies** (in plugin folder):
- Stored in `plugins/{bundle}/skills/{skill}/requirements.txt` OR `pyproject.toml`
- Only installed when user enables the plugin
- Example: `psutil` for brain/system-cleanup, `playwright` for webapp-testing

### 2. Dependency File Format

Plugins can use either:

```
# requirements.txt (simple)
psutil>=5.9.0

# OR pyproject.toml (for complex plugins with entry points)
[project]
dependencies = ["chromadb>=0.4.22", "sentence-transformers>=2.2.2"]
```

### 3. Plugin Enable Flow

When a user enables a plugin with dependencies:

1. Dashboard detects `requirements.txt` or `pyproject.toml` in plugin folder
2. UI shows "This plugin requires additional dependencies" prompt
3. User clicks "Install Dependencies"
4. System runs: `pip install -r plugins/{bundle}/skills/{skill}/requirements.txt`
5. Plugin is marked as "ready"

### 4. Plugin Folder Structure

```
plugins/{bundle}/skills/{skill}/
├── SKILL.md              # Documentation
├── requirements.txt      # OR pyproject.toml
├── scripts/              # Python scripts
├── dashboard/            # UI components (optional)
├── api/                  # API routes (optional)
└── mcp/                  # MCP tools (optional)
```

### 5. Current Plugin Dependency Status

| Plugin | External Deps | Dep File |
|--------|--------------|----------|
| brain | psutil | requirements.txt |
| ocr | pytesseract, pdf2image, pypdf, Pillow | requirements.txt |
| rag | pydantic, pyyaml | requirements.txt |
| webapp-testing | playwright | requirements.txt |
| devops | (uses core deps only) | pyproject.toml |

## Consequences

### Positive
- Smaller core install (~5 plugins vs 20+)
- Users only install what they need
- Plugins are independently deployable
- Clear ownership of dependencies

### Negative
- More complexity for plugin authors
- Potential version conflicts between plugins
- Need to implement dependency detection in UI

### Implementation Notes

1. **Python path resolution**: The dashboard uses `AUGUR_PYTHON` env var or auto-discovers `.venv/bin/python3`
2. **Agent instructions**: Updated to enforce plugin self-containment
3. **No system Python reliance**: All plugins should work with venv-installed dependencies

## Related
- ADR-012: Community Package Extraction
- ADR-015: Three-Tier Plugin Architecture
