---
title: Track 2 — Vault Server Split (Design)
date: 2026-04-29
status: proposed
scope: design
related:
  - 2026-04-28-cross-client-bundle-architecture-design.md
  - 2026-04-28-cross-client-bundle-migration-design.md
---

# Track 2 — Vault Server Split (Design)

## Purpose

Layer 4 of the cross-client bundle architecture migration described Track 2 conceptually as "vault server split — bundle-atomic moves, 5 PRs (one per bundle), simplest first." This design spec fills in the architectural decisions Layer 4 deferred:

- The shape of a per-bundle MCP stdio server entry point.
- The transition strategy between monolith-hosted and per-bundle-hosted tools.
- The mechanism for updating user-tier client configs without disrupting live AI sessions.

## Decisions

- **Per-bundle entry point: generic launcher** — `python -m augur_mcp.bundle_server <bundle-name>`. Bundles continue to provide `scripts/mcp/__init__.py:register_tools(mcp, interceptor, metrics)` exactly as today. The launcher loads one bundle and runs its FastMCP stdio loop.
- **Transition strategy: hybrid** — PR 1 validates the per-bundle launcher pattern in isolation (server runs but is NOT yet registered in client configs). PRs 2-6 use atomic switches (manifest update + monolith exclusion in one commit per bundle) once the pattern is proven.
- **Client config update mechanism: CLI tool + manifest** — a new `augur-cli config sync` command reads `config/system/mcp_servers.yaml` and writes idempotent updates to user configs (Claude / Codex / Gemini). Users run the sync explicitly after pulling each PR; the tool backs up existing configs before writing.
- **Track 2 ships 7 PRs total**: PR 0 (CLI + manifest infrastructure), PR 1 (apple validation), PRs 2-6 (apple, lifestyle, file-manager, obsidian, ingest atomic switches).
- **No allowlist retirements in Track 2** — the architecture-test allowlist entries that survived Track 1 (`("ingest", "ai")`, `("ingest", "rag")`, `("knowledge", "rag")`) retire in Track 3a, where the monolith fully splits into augur-core + augur-framework.
- **Project bundles stay in the monolith for Track 2** — only vault bundles get per-bundle servers in this track. Track 3a multiplexes project-tier bundles' tools into augur-core + augur-framework.

## Architecture

### Two server tiers

After Track 2 completes, the runtime topology is:

| Tier | Server | Hosts |
|---|---|---|
| Project | `augur` (monolith, unchanged in Track 2) | All project-tier bundles' tools (daemon, rag, knowledge, ingest until PR 6, platform-admin, etc.) + Track 1 src/lib/* tools |
| Vault | `augur-apple` | apple's tools only |
| Vault | `augur-lifestyle` | lifestyle's tools only |
| Vault | `augur-file-manager` | file-manager's tools only |
| Vault | `augur-obsidian` | obsidian's tools only |
| Vault | `augur-ingest` | ingest's tools only |

The `augur` monolith continues running with project bundles' tools until Track 3a splits it into `augur-core` + `augur-framework`. Track 4 then deletes the visibility filter that masks the monolith's tool count.

### Bundle format remains universal

Per the Layer 1 spec, **the bundle format is universal**. A bundle authored by the user, a bundle pulled from a future marketplace, and a bundle copied from a friend's zip file all have the same shape:

```
<bundle>/
├── SKILL.md              # frontmatter + description
├── dashboard.yaml        # optional; dashboard contributions
├── loops.yaml            # optional; daemon loop registration
├── commands/             # optional; slash commands
├── scripts/
│   ├── mcp/
│   │   └── __init__.py   # exports register_tools(mcp, interceptor, metrics)
│   └── *.py              # bundle-internal CLI / library code
└── augur/                # tests, library code (per skill convention)
```

What differs between project-tier and vault-tier bundles is **server topology**, not bundle shape:

- **Project bundles**: tools multiplexed into 1-2 framework servers (1 monolith pre-Track-3a; `augur-core` + `augur-framework` post-Track-3a).
- **Vault bundles**: 1 server per bundle (`augur-<bundle>`).

The asymmetry is justified by registry/discovery tools (in `augur-core`) needing efficient cross-bundle reach across project bundles, while vault bundles benefit from per-bundle isolation (user can enable/disable individually; private tool surfaces don't pollute project tools).

### Per-bundle launcher (`augur_mcp.bundle_server`)

New module at `src/mcp/augur_mcp/bundle_server.py`:

```python
"""Per-bundle MCP stdio server.

Usage: python -m augur_mcp.bundle_server <bundle-name>

Resolves the bundle dir via existing _collect_skill_dirs(), creates a
fresh FastMCP, and calls just that bundle's register_tools().
"""
import sys
from mcp.server.fastmcp import FastMCP
from .plugin_tools import _collect_skill_dirs, _pin_mcp_sdk_package, _load_bundle_mcp_module
from .interceptor import mcp_tool_interceptor
from .metrics import metrics


def run(bundle_name: str) -> int:
    _pin_mcp_sdk_package()
    skill_entries = {sd.name: sd for _, sd in _collect_skill_dirs()}
    if bundle_name not in skill_entries:
        print(f"Bundle '{bundle_name}' not found in any registered skill dir", file=sys.stderr)
        return 1

    skill_dir = skill_entries[bundle_name]
    mcp_init = skill_dir / "scripts" / "mcp" / "__init__.py"
    if not mcp_init.exists():
        print(f"Bundle '{bundle_name}' has no scripts/mcp/__init__.py", file=sys.stderr)
        return 1

    mcp = FastMCP(f"augur-{bundle_name}")
    module = _load_bundle_mcp_module(skill_dir)
    if not hasattr(module, "register_tools"):
        print(f"Bundle '{bundle_name}' has no register_tools()", file=sys.stderr)
        return 1

    module.register_tools(mcp, mcp_tool_interceptor, metrics)
    mcp.run()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m augur_mcp.bundle_server <bundle-name>", file=sys.stderr)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
```

The bundle-loading machinery (synthetic parent package for relative-import resolution, etc.) already exists in `plugin_tools.py:register_plugin_tools()`. PR 0 extracts the per-bundle loading into a reusable `_load_bundle_mcp_module()` helper that both the monolith's scan and the per-bundle launcher consume.

### Manifest format

New file at `config/system/mcp_servers.yaml`:

```yaml
# Augur MCP server topology manifest.
# Source-of-truth for what client configs should register.
# Used by `augur-cli config sync` to keep ~/.claude/, ~/.codex/, ~/.gemini/ in sync.

# Project-tier servers (always registered; ship with Augur framework).
project_tier:
  - id: augur
    description: Project-tier monolith MCP server
    command: python
    args: [-m, augur_mcp]
    cwd_required: true  # must launch from Augur checkout (project.yaml present)
    env:
      PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"

# Vault-tier per-bundle servers (added incrementally as Track 2 PRs land).
vault_tier: []
  # PR 2 appends:
  # - id: augur-apple
  #   bundle: apple
  #   bundle_path: ~/Projects/Au-vault/skills/apple
  #   command: python
  #   args: [-m, augur_mcp.bundle_server, apple]

# Bundles excluded from the monolith's skill scan because they're
# served by per-bundle vault-tier servers now.
monolith_exclusions: []
  # PR 2 appends: apple
```

The manifest is the source-of-truth. Each Track 2 PR appends to `vault_tier` and `monolith_exclusions` in the same commit. The CLI reads the manifest; the monolith's `_collect_skill_dirs()` reads the manifest for exclusions.

### CLI tool (`augur-cli config sync`)

New package at `src/cli/augur_cli/`:

```
src/cli/augur_cli/
├── __init__.py
├── __main__.py              # entry point; routes subcommands
├── config_sync.py           # main sync logic
├── adapters/
│   ├── __init__.py
│   ├── base.py              # protocol: read/write client config
│   ├── claude.py            # ~/.claude/settings.json (or wherever Claude reads MCP)
│   ├── codex.py             # ~/.codex/config.toml
│   └── gemini.py            # ~/.gemini/settings.json
└── manifest.py              # load + validate config/system/mcp_servers.yaml
```

Commands:

- `augur-cli config sync` — read manifest, write configs for all 3 clients (idempotent).
- `augur-cli config sync --dry-run` — print intended diffs without writing.
- `augur-cli config sync --client codex` — sync just one client.
- `augur-cli config status` — show current client-vs-manifest drift.

Behavior:

- Backs up each client's config to `<file>.bak.<UTC-timestamp>` before writing.
- Atomic write: write to `<file>.tmp`, rename. Never partial-write.
- Idempotent: running twice produces no further changes.
- Conservative scope: only manages MCP server entries with id matching `augur*` prefix. Other servers in the user's configs (e.g., `context7`, `claude-in-chrome`) are preserved verbatim.

The CLI is invoked via console_scripts entry in `pyproject.toml` so `augur-cli` is on PATH after `uv sync`.

### Per-bundle PR shape (PRs 2-6)

For each vault bundle migration, the PR contains:

1. **Manifest update** — append to `vault_tier` and `monolith_exclusions` in `config/system/mcp_servers.yaml`.
2. **Bundle move** (PRs 4-6 only) — `git mv skills/<bundle>/ ` from Augur to Au-vault, in coordinated commits across both repos.
3. **Tests** — verify the per-bundle server starts and exposes the correct tools (`pytest tests/cli/test_bundle_server.py`).
4. **User instruction** — commit message includes the post-merge command: `augur-cli config sync && <reload AI clients>`.

The user's responsibility per PR:

- After merging, run `augur-cli config sync`.
- Reload Claude Code / Codex / Gemini (close + reopen sessions).
- Verify the bundle's tools are reachable via `tools/list` against `augur-<bundle>`.

### Cross-repo coordination (PRs 4-6)

For `file-manager`, `obsidian`, `ingest`:

- Augur-side commit removes `skills/<bundle>/`. Tests in Augur that depend on the bundle either get deleted or migrated to Au-vault as well.
- Au-vault-side commit adds `skills/<bundle>/`.
- Both commits land before the user runs `augur-cli config sync`.
- Plan documents both git operations as atomic prerequisites.

The implementation plan will treat each cross-repo PR as a single logical unit (one Augur PR + one Au-vault commit). A failure between the two creates partial state — the plan must handle this with a verification gate before pushing the Augur PR.

### Verification per PR

Each PR's verification checklist:

- `augur-cli config sync --dry-run` shows the expected manifest diff.
- After (manual) sync, `python -m augur_mcp.bundle_server <bundle>` starts a stdio server.
- A test-script connects to that server and runs `tools/list`, returning the bundle's tools (count and shape match expectations).
- The monolith's `tools/list` no longer advertises the bundle's tools (verifies exclusion-list works).
- Dashboard browse page renders the bundle's data correctly (test via Chrome MCP or screenshot).
- Architecture tests still pass (`pytest tests/architecture/`). No allowlist retirements in this track.

### Scope guardrails

What Track 2 does NOT do:

- Project-tier server split (Track 3a).
- Dashboard hub-routing redesign (Track 3b).
- Visibility filter removal (Track 4).
- Auto-sync on Augur git pull (would couple Augur's CI to user-tier configs; deferred).
- Bundle versioning, marketplace, or distribution mechanism (out of migration scope entirely).

## Order of bundles (PRs 2-6)

Per Layer 4's "simplest first" principle:

1. **PR 2 — apple** (already in Au-vault; only topology change). Validates the proven launcher pattern under the atomic-switch path.
2. **PR 3 — lifestyle** (already in Au-vault; same shape as apple). Smoke-tests that two per-bundle servers can coexist.
3. **PR 4 — file-manager** (`git mv` newcomer; per audit, 0 incoming Python importers — cleanest). First cross-repo PR.
4. **PR 5 — obsidian** (`git mv` newcomer; small surface).
5. **PR 6 — ingest** (`git mv` newcomer; most-coupled — depends on rag, ai/sync_agents). Last because cross-skill couplings have been progressively retired by Tracks 1 and the earlier Track 2 PRs.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Per-bundle launcher fails to start in PR 1 | Medium | Validation PR runs the server in isolation; tests verify `tools/list`. No client-config exposure until pattern proven. |
| User forgets to run `augur-cli config sync` after merging a PR | High | Commit message includes the command + reload instruction. PR description repeats it. |
| `augur-cli` itself has bugs in adapter logic for one of the clients | Medium | `--dry-run` flag for review before write. Backups created automatically. PR 0's tests cover all 3 client adapters. |
| Cross-repo PR (4-6) lands Augur side before Au-vault side | Medium | Plan requires Au-vault commit + push before Augur PR merge. Verification step checks Au-vault HEAD matches expected commit. |
| Monolith exclusion list drifts from manifest | Low | `_collect_skill_dirs()` reads the same manifest. Test verifies parity. |
| Two MCP servers expose duplicate tool names mid-transition (atomic-switch race) | Low | Atomic switch happens in single commit. The brief gap between commit + sync + reload is bounded; user can roll back the sync if needed. |
| User has unrelated MCP servers in client configs and CLI deletes them | High if not handled | CLI scope is restricted to entries with id matching `augur*` — others are preserved. Test fixture verifies preservation. |

## Track 2 ADR

After Track 2 ships, write `track2-vault-server-split.md` ADR recording:

- The CLI + manifest as the canonical client-config-management mechanism (binding decision for Track 3a's project-tier reshuffle and any future server-topology changes).
- The atomic-switch transition pattern (PRs 2-6).
- Apple's role as the validation bundle (PR 1).
- The 7 PRs landed and their dates.
- The 5 architecture-test allowlist entries still pending Track 3a retirement.

## Done criteria for Track 2

1. `config/system/mcp_servers.yaml` exists with all 5 vault bundles registered and all 5 monolith exclusions listed.
2. `augur-cli config sync` correctly populates `~/.claude/...`, `~/.codex/config.toml`, `~/.gemini/...` with per-bundle entries.
3. `tools/list` against each `augur-<bundle>` returns the bundle's expected tools.
4. The `augur` monolith's `tools/list` no longer advertises any of the 5 vault bundles' tools.
5. `file-manager`, `obsidian`, `ingest` are physically moved to `~/Projects/Au-vault/skills/` (no longer in Augur repo).
6. Dashboard browse page renders all 5 bundles' data normally.
7. All Augur tests still pass; architecture-test allowlist unchanged from Track 1's end state.
8. ADR written and committed in `get_adr_dir()`.
