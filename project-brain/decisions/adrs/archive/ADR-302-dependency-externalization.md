---
status: Implemented
date: '2026-03-12'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- dependency
- externalization
- pnpm
superseded_by: null
---

# ADR-302: Dependency Externalization — pnpm + uv

## Context

The Augur source tree is ~1.15GB on disk, with ~1.13GB being installed dependencies (`node_modules/` at ~822MB, `.venv/` at ~325MB). While gitignored, these sit inside the project directory alongside source code — violating Augur's data separation principle (code in `src/`/`plugins/`, state in `~/Library/Application Support/Augur/`, caches in `~/Library/Caches/Augur/`).

Problems:
- **Disk bloat**: Every clone carries its own full copy of all dependencies
- **IDE noise**: File watchers and search indexes traverse large dependency trees
- **Turbopack overhead**: `outputFileTracingExcludes` needed to prevent `.venv/` traversal
- **No cross-project sharing**: Multiple Node.js/Python projects each store their own copies

### Current State

The migration is partially started:
- `pnpm-workspace.yaml` already exists with `packages: ["apps/*"]`
- `uv.lock` already exists at root (and at `src/mcp/uv.lock`, `plugins/dev/skills/devops/uv.lock`)
- `package-lock.json` still exists (npm lock file still active)
- Root `package.json` still has `"workspaces"` field and no `"packageManager"` field
- `node_modules/` contains full npm flat copies (not pnpm symlinks)
- CI workflows reference stale `src/dashboard/` path (should be `apps/dashboard/`) and use `npm ci`

## Decision

Replace npm with **pnpm** (via corepack) and pip/venv with **uv** to externalize dependency caches into global content-addressable stores.

| Layer | Before | After | Store location |
|-------|--------|-------|----------------|
| Node.js | npm (flat copy into `node_modules/`) | pnpm via corepack (symlink tree → global store) | Platform-dependent (`pnpm store path`) |
| Python | pip + venv (full copy into `.venv/`) | uv (hardlinks → global cache) | `~/Library/Caches/uv/` (macOS) / `~/.cache/uv/` (Linux) |

### pnpm (Node.js)

- **Activation**: `corepack enable` — built into Node.js, zero external install
- **Global store**: Content-addressable, platform-dependent (resolve via `pnpm store path`; typically `~/Library/pnpm/store` on macOS, `~/.local/share/pnpm/store` on Linux)
- **Local `node_modules/`**: Thin symlink tree (~5MB) pointing into the store
- **Workspace config**: `pnpm-workspace.yaml` with `packages: ["apps/*"]`
- **Lock file**: `pnpm-lock.yaml` (committed, replaces `package-lock.json`)
- **Guard**: `"packageManager": "pnpm@10.x.x"` in root `package.json` blocks accidental `npm install`

### uv (Python)

- **Install**: `curl -LsSf https://astral.sh/uv/install.sh | sh` (~8MB static binary)
- **Global cache**: Content-addressable at `~/Library/Caches/uv/` (macOS) / `~/.cache/uv/` (Linux)
- **Local `.venv/`**: Hardlinks from cache (~15MB when cache and project share the same filesystem; falls back to full copy on cross-filesystem setups)
- **Config**: `pyproject.toml` `[project.dependencies]` (PEP 621 standard)
- **Lock file**: `uv.lock` (committed, replaces `requirements.txt`)

### Turbopack compatibility

No changes needed to `next.config.ts`. pnpm's `node_modules/.pnpm/` symlink structure resolves identically to npm's flat layout. The existing `outputFileTracingRoot` and `turbopack.root` set to monorepo root continue to work.

### Native module compatibility

`node-pty` has a postinstall script that `chmod`s prebuilt binaries. Under pnpm's strict layout, native modules need hoisting. An `.npmrc` with `public-hoist-pattern[]=*node-pty*` ensures `node-pty` is hoisted to the root `node_modules/` so postinstall resolves correctly.

### Per-plugin requirements.txt

Four plugins have their own `requirements.txt` (finance, channels, validator, mcp-app-factory). These are **out of scope** — they remain as `uv pip install -r` targets for skill-level isolation, consistent with the existing CI `skill-tests` job pattern.

### Shell config

- **pnpm**: No shell changes. Corepack shims live inside Node.js's bin directory, already on `$PATH`.
- **uv**: Installer adds `~/.local/bin` to `$PATH` in `.zshrc` (one line). If already present, nothing changes.

Zero shell overhead — no `source activate`, no `nvm use`, no `eval` hooks.

## Consequences

### Positive

- **~1.13GB disk savings** per clone (822MB node_modules + 310MB .venv)
- **Cross-project cache sharing** — multiple Node.js/Python projects share the same global store
- **Phantom dependency detection** — pnpm strict mode catches undeclared imports
- **Faster installs** — pnpm: ~5s (symlinks), uv: ~3s (hardlinks) vs npm: ~30s, pip: ~20s
- **Deterministic builds** — both tools use lock files with `--frozen` CI mode
- **Simpler onboarding** — `corepack enable && pnpm install && uv sync` (three commands)

### Negative

- **New tool for contributors** — developers must learn `pnpm` commands (minor: `pnpm X` vs `npm run X`)
- **uv requires one-time install** — `curl` or `brew install uv` (~8MB)
- **pnpm strict mode may break undeclared imports** — existing phantom dependencies surface as errors during migration (this is a feature, but requires upfront fixing)

### Neutral

- `apps/` directory structure unchanged
- `next.config.ts` unchanged
- Per-plugin `requirements.txt` files unaffected
- `.gitignore` entries for `node_modules/` and `.venv/` remain the same

## Alternatives Considered

### Alternative 1: Symlink node_modules to external cache

Move `node_modules/` to `~/Library/Caches/Augur/node_modules` and symlink back. Achieves disk separation but does not provide content-addressable deduplication, phantom dependency detection, or cross-project sharing. Fragile with native modules and postinstall scripts. Rejected because pnpm provides the same benefit with additional advantages and is the industry standard.

### Alternative 2: Poetry for Python

Poetry is a mature Python dependency manager with lock file support. Rejected because: (1) Poetry uses its own non-standard `[tool.poetry]` config vs PEP 621 standard, (2) no global content-addressable cache — each project gets full copies, (3) uv is ~80x faster and uses standard `pyproject.toml` `[project]` format.

### Alternative 3: Keep npm + pip, just externalize via UV_PROJECT_ENVIRONMENT

Use `UV_PROJECT_ENVIRONMENT` to place `.venv/` in `~/Library/Caches/Augur/` and keep npm as-is. Addresses Python disk usage but not Node.js (~822MB), and loses pnpm's phantom dependency detection and cross-project deduplication. Rejected as a half-measure.

## References

- Design spec: `docs/superpowers/specs/2026-03-12-dependency-externalization-design.md`
- Augur data separation principle: ADR-270
- pnpm documentation: https://pnpm.io
- uv documentation: https://docs.astral.sh/uv/
- PEP 621 (pyproject.toml metadata): https://peps.python.org/pep-0621/

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated:
    - grep: "npm (ci|install|run|exec)"
      replacement: "pnpm (install|X|dlx)"
    - grep: "pip install"
      replacement: "uv add / uv sync"
    - grep: "python -m venv"
      replacement: "uv sync"
    - grep: "package-lock\\.json"
      replacement: "pnpm-lock.yaml"
    - grep: "requirements\\.txt"
      replacement: "pyproject.toml [project.dependencies]"
  files_affected:
    - glob: "package.json"
    - glob: ".github/workflows/*.yml"
    - glob: "scripts/**/*.sh"
    - glob: "*.md"
```

## Testing

| ID | Test | Validation |
|----|------|------------|
| T1 | pnpm install from clean clone | `rm -rf node_modules && pnpm install` succeeds, `node_modules/.pnpm` exists |
| T2 | Dashboard builds with pnpm | `pnpm --filter dashboard build` exits 0 |
| T3 | Dashboard tests pass | `pnpm --filter dashboard test` — all tests green |
| T4 | node-pty postinstall works | `ls node_modules/node-pty/prebuilds/` shows platform binaries |
| T5 | uv sync from clean state | `rm -rf .venv && uv sync` succeeds, `.venv/bin/python` exists |
| T6 | Python tests pass | `uv run pytest` — all tests green |
| T7 | Phantom dep detection | Add undeclared import → `pnpm install` fails or runtime error |
| T8 | npm install blocked | `npm install` prints corepack error, does not modify node_modules |
| T9 | CI frozen install | `pnpm install --frozen-lockfile && uv sync --frozen` succeed |
| T10 | Rollback to npm | `rm pnpm-lock.yaml && npm install` restores flat node_modules |

## Implementation Prompt

**Team name**: `adr-302-dependency-externalization`

### Phase 1: Node.js Migration (npm → pnpm)
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend | low | `corepack enable`, add `"packageManager"` to root `package.json` | `package.json` |
| 1.2 | backend | medium | Run `pnpm import` to convert lock file, remove `package-lock.json` | `pnpm-lock.yaml`, `package-lock.json` |
| 1.3 | backend | low | Remove `workspaces` from `package.json`, create `.npmrc` with `public-hoist-pattern[]=*node-pty*` | `package.json`, `.npmrc` |
| 1.4 | backend | medium | Run `pnpm install`, verify symlink tree, verify `node-pty` postinstall | `node_modules/` |
| 1.5 | backend | medium | Update all script references: `npm run` → `pnpm`, `npx` → `pnpm dlx` | `scripts/**/*.sh`, `*.md`, `CLAUDE.md` |

### Phase 2: Python Migration (pip → uv)
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | backend | low | Verify uv installed, run `uv sync` | `.venv/` |
| 2.2 | backend | low | Remove root `requirements.txt` / `requirements-dev.txt` if present | `requirements*.txt` |
| 2.3 | backend | low | Update script references: `pip install` → `uv add/sync`, `python -m venv` → `uv sync` | `scripts/**/*.sh`, `*.md` |

### Phase 3: CI Updates
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | medium | Fix stale `src/dashboard/` → `apps/dashboard/` paths in all CI workflows | `.github/workflows/*.yml` |
| 3.2 | devops | medium | Replace `npm ci` with `corepack enable && pnpm install --frozen-lockfile` in CI | `.github/workflows/*.yml` |
| 3.3 | devops | medium | Replace `pip install` with `uv sync --frozen` in CI, add cache keys | `.github/workflows/*.yml` |

### Phase 4: Cleanup
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | backend | low | Update `.gitignore` if needed (pnpm-lock.yaml committed, uv.lock committed) | `.gitignore` |
| 4.2 | backend | low | Update onboarding docs and `/onboard` skill | `CLAUDE.md`, skill files |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run T1–T10 from Testing section |
| V.2 | validator | low | `pnpm --filter dashboard build` succeeds |
| V.3 | validator | low | `uv run pytest` succeeds |
| V.4 | architect | low | Verify no `npm ci`, `npm install`, `pip install`, `python -m venv` remain in scripts or CI |

### Completion Criteria
- [ ] All phases executed
- [ ] `pnpm install --frozen-lockfile` succeeds
- [ ] `uv sync --frozen` succeeds
- [ ] Dashboard builds and tests pass
- [ ] Python tests pass
- [ ] No `npm`/`pip`/`venv` references remain in scripts or CI
- [ ] `npm install` blocked by corepack guard
- [ ] ADR status updated to Implemented
