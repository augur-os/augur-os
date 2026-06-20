---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- mcp
- package
- architecture
- single
- source
superseded_by: null
---

# ADR-107: MCP Package Architecture — Single Source, Dual Distribution

**Date:** 2026-02-16
**Supersedes:** ADR-024 (MCP Package Decoupling)
**Related:** ADR-005 (MCP Gateway), ADR-106 (MCP Migration to src/)

## Context

ADR-024 established `plugins/augur-mcp/` as a standalone PyPI package with its own source tree. ADR-106 moved the source to `src/mcp/augur_mcp/` for monorepo development ergonomics but left `plugins/augur-mcp/` as a build shim with a symlink.

**Current state is incoherent:**

| Location | Contains | Purpose |
|----------|----------|---------|
| `src/mcp/augur_mcp/` | All source code (20k LOC, 70 files) | Development |
| `plugins/augur-mcp/pyproject.toml` | Build metadata | PyPI publishing |
| `plugins/augur-mcp/src/augur_mcp` | **Symlink** → `src/mcp/augur_mcp` | Hatch build hack |
| `plugins/augur-mcp/tests/` | 3 orphaned test files | Unclear |
| `plugins/augur-mcp/README.md` | Package documentation | PyPI page |

**Problems:**

1. **Symlink fragility** — `plugins/augur-mcp/src/augur_mcp → ../../../src/mcp/augur_mcp`. Breaks on Windows, confuses some git clients, invisible in GitHub UI.
2. **Split metadata** — Package identity (name, version, deps) lives in `plugins/` while code lives in `src/`. Two places to update on version bumps.
3. **Orphaned tests** — 3 test files in `plugins/augur-mcp/tests/` disconnected from the main `tests/mcp/` suite.
4. **ADR-024 is stale** — Still says "In Progress" with Phase 4 describing a `plugins/augur-mcp/src/augur_mcp/` layout that no longer exists.
5. **Build path confusion** — `pyproject.toml` says `plugins = ["src/augur_mcp"]` which only resolves via the symlink. Developers unfamiliar with the setup cannot reason about the build.

## Decision

### Consolidate everything under `src/mcp/` with a single `pyproject.toml`

```
src/mcp/
├── augur_mcp/              # Package source (already here)
│   ├── __init__.py         # Contains __version__
│   ├── server.py
│   ├── compat.py           # Kernel compatibility layer (keep)
│   ├── config.py
│   ├── core/
│   ├── tools/
│   └── ...
├── pyproject.toml          # ← MOVE from plugins/augur-mcp/
├── README.md               # ← MOVE from plugins/augur-mcp/
└── tests/                  # ← MERGE from plugins/augur-mcp/tests/
    ├── test_cli_args.py
    ├── test_cli_bridge.py
    └── test_cli_bridge_registration.py
```

### Delete `plugins/augur-mcp/` entirely

No symlinks, no shims. The package lives where the code lives.

### Update `pyproject.toml` paths

```toml
[tool.hatch.build.targets.wheel]
plugins = ["augur_mcp"]    # Direct — no symlink needed

[tool.hatch.build.targets.sdist]
include = ["/augur_mcp", "/tests", "/README.md"]
```

### Publishing workflow

```bash
cd src/mcp
python -m build          # Builds from src/mcp/pyproject.toml
twine upload dist/*      # Publishes augur-mcp to PyPI
```

### Monorepo integration

`src/cli.py` and `src/api.py` already set `sys.path.insert(0, "src/mcp")` — no change needed. The import `from augur_mcp import server` continues to work in both contexts:
- **Monorepo**: via sys.path manipulation in entry points
- **Standalone**: via `pip install augur-mcp` (or `pip install -e src/mcp`)

### Keep the compatibility layer

`compat.py` with `KERNEL_AVAILABLE` stays. It's the correct pattern for dual-mode operation. The 3 files with `from src.*` imports (`compat.py`, `logging.py`, `context_injector.py`) remain behind the try/except guard.

### Merge orphaned tests

Move the 3 package-specific tests into `tests/mcp/` alongside existing MCP tests. Delete `plugins/augur-mcp/tests/`.

## Implementation

| Step | Action | Files |
|------|--------|-------|
| 1 | Move `plugins/augur-mcp/pyproject.toml` → `src/mcp/pyproject.toml` | 1 |
| 2 | Update `[tool.hatch.build]` paths (remove `src/` prefix) | 1 |
| 3 | Move `plugins/augur-mcp/README.md` → `src/mcp/README.md` | 1 |
| 4 | Move `plugins/augur-mcp/tests/*.py` → `tests/mcp/` | 3 |
| 5 | Delete `plugins/augur-mcp/` directory entirely | - |
| 6 | Remove symlink at `plugins/augur-mcp/src/augur_mcp` | - |
| 7 | Update CI workflows referencing `plugins/augur-mcp/` | Varies |
| 8 | Update ADR-024 status to "Superseded by ADR-107" | 1 |
| 9 | Update `Makefile` / build scripts if they reference `plugins/` | Varies |

## Consequences

### Positive

- **Single source of truth** — code, metadata, tests, docs all in `src/mcp/`
- **No symlinks** — works on all platforms, clear in git
- **Simpler mental model** — `src/mcp/` IS the package. Period.
- **PyPI publishing preserved** — `cd src/mcp && python -m build` works identically
- **Standalone install preserved** — `pip install -e src/mcp` or `pip install augur-mcp` from PyPI
- **Compatibility layer preserved** — `compat.py` continues enabling dual-mode operation

### Negative

- **Non-standard monorepo layout** — most monorepos put plugins in `plugins/`. This puts it in `src/mcp/`. Acceptable because Augur has exactly one extractable package, not N.
- **`src/mcp/` serves double duty** — both a monorepo module and a standalone package root. Documented clearly in README.

### Neutral

- Monorepo developers see no change in imports or behavior
- CI pipeline needs minor path updates

## Alternatives Considered

### A: Keep the symlink approach (status quo)

Rejected. Symlinks are fragile, confuse tooling, and obscure the real layout.

### B: Move source back to `plugins/augur-mcp/src/augur_mcp/`

Rejected. ADR-106 moved it to `src/mcp/` for good reason — monorepo development is the primary workflow. Moving it back would regress daily developer experience for the sake of a cleaner package boundary that only matters at publish time.

### C: Use a monorepo build tool (Hatch workspaces, PDM, etc.)

Overkill for one extractable package. Adds tooling complexity for no practical benefit.

### D: Abandon standalone distribution entirely

Rejected. PyPI distribution is needed for open-source adoption (ADR-024's core thesis remains valid).
