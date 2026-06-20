---
status: Implemented
date: '2026-03-07'
deciders:
- Gur Sannikov
- Claude
related: []
hub: null
tags:
- standalone
- cli
- package
superseded_by: null
---

# ADR-258: Standalone CLI Package

**Related ADRs**: ADR-254 (Phase 2)

## Context

The `aug` CLI already exists (`src/cli.py`) and wraps all MCP tools with `aug discover`, `aug <tool-name>`, and `aug --list-tools`. A `pyproject.toml` with `[project.scripts] aug = "src.cli:main"` is in place. However, the CLI currently requires a full clone of the Augur repo because:

1. **Path bootstrapping** — `src/cli.py` lines 29-44 manually manipulate `sys.path` using `Path(__file__).parent.parent` to find `src/mcp/augur_mcp`. This only works from the repo checkout.
2. **No clean stdout** — Output includes ANSI colors and logging noise when piped. The `--json` flag exists but isn't consistently applied across all tool output paths.
3. **Plugin data dependency** — `discover` and tool registration read `augur.yaml` files from `plugins/`, which aren't shipped in a pip package.
4. **Runtime directory assumption** — The CLI assumes `runtime/` exists adjacent to the project root for focus state, sessions, and logs.

An external agent wanting to use Augur must currently clone the entire repo and set up the Python environment. `pip install augur-cli && aug discover` would make Augur instantly usable by any agent or script.

## Decision

### 1. Package Structure

Restructure for clean pip packaging while maintaining the editable-install development workflow:

```
pyproject.toml              # Already exists, needs refinement
src/
  cli.py                    # Entry point (already exists)
  mcp/
    augur_mcp/              # MCP package (already exists)
      domain/
        discovery.py        # Manifest assembly
        sessions.py         # Session lifecycle
```

**Key change**: `src/cli.py` must resolve `AUGUR_ROOT` without hardcoding paths:
- If `AUGUR_ROOT` env var is set → use that (already supported)
- If running from editable install → use `importlib.resources` to find package data
- If running from pip install → use `~/.augur/` as default project root with auto-setup

### 2. Clean Stdout Contract

| Mode | Trigger | Behavior |
|------|---------|----------|
| Human | `sys.stdout.isatty()` | ANSI colors, markdown formatting, progress indicators |
| Machine | piped, or `--json` flag | Pure JSON to stdout, warnings/errors to stderr only |

Specific fixes:
- Move all `logging.*` calls to stderr
- Ensure `aug discover` returns valid JSON when piped (already partially done)
- Add `--format json|text|markdown` flag to all output commands
- Suppress ANSI escape codes when `NO_COLOR` env var is set (de facto standard)

### 3. Minimal Install Mode

When installed via `pip install augur-cli` without a full repo:

```python
# ~/.augur/ auto-created on first run
~/.augur/
  config/          # Minimal config (auto-generated)
  runtime/         # Sessions, focus state
  plugins/         # Empty initially; populated by aug install <skill>
```

- `aug discover` works immediately — returns the manifest with 0 skills if no plugins installed
- `aug install career` fetches and installs a skill from the registry
- `AUGUR_ROOT=/path/to/augur aug discover` uses a full repo checkout if available

### 4. pyproject.toml Updates

```toml
[project]
name = "augur-cli"
version = "0.2.0"
description = "Agent-native CLI for the Augur personal knowledge system"

[project.scripts]
aug = "src.cli:main"

[project.entry-points."augur.plugins"]
# Future: plugin discovery via entry points

[tool.hatch.build.targets.wheel]
packages = ["src"]
# Only include src/cli.py and src/mcp/ — NOT plugins/ or config/
exclude = ["src/dashboard", "src/scripts"]
```

### 5. Testing

- CI: `pip install -e . && aug discover --format json | python -c "import sys,json; json.load(sys.stdin)"` — validates clean JSON output
- CI: `pip install . --no-deps && aug --help` — validates non-editable install
- Unit: test `AUGUR_ROOT` resolution with and without env var
- Unit: test stdout/stderr separation when piped

## Consequences

### Positive
- Any agent can `pip install augur-cli && aug discover` without cloning the repo
- Clean machine-readable output enables piping into other tools
- `pipx install augur-cli` gives a global `aug` command
- Editable install (`pip install -e .`) preserves current development workflow

### Negative
- Minimal install mode has reduced functionality (no plugins = no skill tools)
- Must maintain two path resolution modes (repo checkout vs pip install)
- Version management adds release engineering overhead

### Neutral
- `pyproject.toml` already exists — this is refinement, not greenfield
- MCP server still requires the full repo (this only packages the CLI wrapper)

## Alternatives Considered

### Alternative 1: Ship as Docker container
`docker run augur aug discover` — zero Python dependency.
Rejected: Too heavy for agent integration. Agents want `pip install`, not container orchestration.

### Alternative 2: Compile to single binary with PyInstaller
Distribute as a single `aug` binary.
Rejected: Loses plugin extensibility. Can't `aug install` new skills into a frozen binary. Also, Python ecosystem agents already have pip.

## References

- ADR-254: Agent Discovery Protocol (parent roadmap)
- `pyproject.toml` (current, partially scaffolded)
- `src/cli.py` (current CLI implementation)
- [PEP 621](https://peps.python.org/pep-0621/) — pyproject.toml metadata
- `NO_COLOR` convention: https://no-color.org/

## Implementation Order

### Phase 1: Clean Stdout (PARALLEL)
| Step | Task | Files |
|------|------|-------|
| 1.1 | Route all logging to stderr, respect `NO_COLOR` | `src/cli.py` |
| 1.2 | Validate JSON output for all `aug` commands when piped | `src/cli.py`, `tests/cli/test_stdout.py` |
| 1.3 | Add `--format` flag with json/text/markdown modes | `src/cli.py` |

### Phase 2: Path Resolution (PIPELINE)
| Step | Task | Files |
|------|------|-------|
| 2.1 | Extract path bootstrapping into `src/cli_bootstrap.py` | `src/cli.py`, `src/cli_bootstrap.py` |
| 2.2 | Implement `~/.augur/` auto-setup for non-repo installs | `src/cli_bootstrap.py` |
| 2.3 | Test both editable and non-editable install paths | `tests/cli/test_bootstrap.py` |

### Phase 3: Package & Publish (PIPELINE)
| Step | Task | Files |
|------|------|-------|
| 3.1 | Refine pyproject.toml: wheel excludes, version bump | `pyproject.toml` |
| 3.2 | CI job: build wheel, install in clean venv, run smoke tests | `.github/workflows/cli-package.yml` |
| 3.3 | Publish to private PyPI or GitHub Packages | CI config |

### Completion Criteria
- [ ] `pip install augur-cli && aug discover --format json` returns valid JSON in a clean venv
- [ ] `aug discover | jq .manifest.name` outputs `"augur"` (clean stdout)
- [ ] `aug --list-tools 2>/dev/null` produces no stderr output in normal operation
- [ ] Editable install (`pip install -e .`) still works for development
- [ ] `AUGUR_ROOT` env var overrides default path resolution
- [ ] CI smoke test passes on fresh install
