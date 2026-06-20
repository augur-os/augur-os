# Track 3a — Framework Split + Cleanup + Hardcode Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Worktree required:** Before starting, use `superpowers:using-git-worktrees` to create a worktree off `main` with branch name `track3a-framework-split`.

> **HIGH-BLAST-RADIUS PR**: PR 6 (atomic switchover) replaces the `augur` monolith with `augur-core` + `augur-framework` in user-tier client configs. Document rollback in commit body. The user runs `aug config sync` post-merge.

**Goal:** Split the `augur` monolith MCP server into `augur-core` (29 registry/discovery tools) + `augur-framework` (~114 operational tools), retire 23 dormant tools, fix 11 src/ vault-private hardcodes, dismantle the `augur_mcp/` namespace, and drive the architecture-test allowlist to empty.

**Architecture:** Per Track 3a design spec (`docs/superpowers/specs/2026-04-29-track3a-framework-split-design.md`). New packages `src/mcp/augur_core/`, `src/mcp/augur_framework/`, `src/mcp/augur_shared/`. The `augur_mcp/` namespace is fully retired.

**Tech Stack:** Python 3.11+, FastMCP (existing), pytest, uv. No new dependencies.

**Related specs:**
- Layer 1: `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- Layer 4 migration: `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- Track 3a design: `docs/superpowers/specs/2026-04-29-track3a-framework-split-design.md`
- Tool audit: `/tmp/track3a-tool-audit.md`
- Tool inventory: `/tmp/track3a-tool-map.txt`

## Critical execution rules

- **Never** use `--no-verify` on `git commit`. Pre-commit failures get a NEW commit with the fix.
- **Worktree pollution check** before every commit: `git status --short` must show only expected paths. Restore drift with `git checkout HEAD --` before committing.
- **Track 2 invariant**: at every PR, the 5 vault-tier per-bundle servers (augur-apple, augur-lifestyle, augur-file-manager, augur-obsidian, augur-ingest) must keep launching. PRs 1-6 keep `augur_mcp.bundle_server` working via re-export shim. PR 7 updates the manifest's vault-tier `args` to `augur_shared.bundle_server` and removes the shim.
- **Cross-PR dependency**: PR 1's re-export shims must remain through PR 6. PR 7 deletes them.
- **PR 6 is irreversible-ish** — augur monolith deletion is structural. Document rollback steps (timestamped backups via `aug config sync`) in commit body.

## File Structure

### Packages added

| Path | Created in PR | Purpose |
|---|---|---|
| `src/mcp/augur_shared/` | PR 1 | Cross-server utilities (bundle_server, plugin_tools, mcp_sdk, client_surface, compat, skill_registry) |
| `src/mcp/augur_shared/skill_registry.py` | PR 3 | `is_vault_skill()` and `is_known_skill()` helpers |
| `src/mcp/augur_core/` | PR 4 | 29 registry/discovery tools |
| `src/mcp/augur_framework/` | PR 5 | ~114 operational tools |

### Package retired

| Path | Retired in PR | Notes |
|---|---|---|
| `src/mcp/augur_mcp/self_update/` | PR 2 | Entire directory (9 dormant tools) |
| `src/mcp/augur_mcp/tools/hubs/scrape_and_save_idea.py` | PR 2 | Hardcoded to lifestyle |
| `src/mcp/augur_mcp/infrastructure/freeze.py` | PR 2 | freeze-overview retired |
| `src/mcp/augur_mcp/` (entire dir) | PR 7 | Dismantled after switchover |

### Files to delete vs migrate (full table by tool — see PRs 4-5)

Tool inventory at `/tmp/track3a-tool-map.txt`. Migration mapping per the design spec's "Server topology" table.

---

## Task 1: PR 1 — `src/mcp/augur_shared/` setup (additive)

**Goal:** Move shared infrastructure files. Re-export shims at original locations keep existing imports working.

### Step 1.1: Verify branch + state

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git branch --show-current && git status --short
```
Expected: `track3a-framework-split`, clean. STOP if not.

### Step 1.2: Create `src/mcp/augur_shared/__init__.py`

```python
"""Cross-server utilities shared by augur-core and augur-framework.

After Track 3a, the legacy src/mcp/augur_mcp/ namespace is fully
retired. This package hosts the bundle launcher (used by Track 2's
per-bundle vault-tier servers), the skill scanner / plugin loader,
the MCP SDK pinning logic, and the client surface (visibility filter
slated for deletion in Track 4).
"""
```

### Step 1.3: Move `bundle_server.py` (with shim)

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  cp src/mcp/augur_mcp/bundle_server.py src/mcp/augur_shared/bundle_server.py
```

Inside the copied `src/mcp/augur_shared/bundle_server.py`, update import paths:
- `from src.mcp.augur_mcp.plugin_tools` → `from src.mcp.augur_shared.plugin_tools`
- `from src.mcp.augur_mcp.server` → `from src.mcp.augur_shared.mcp_sdk`

Replace `src/mcp/augur_mcp/bundle_server.py` with a re-export shim:

```python
"""Re-export from augur_shared. DEPRECATED — will be removed in PR 7.

Track 2's manifest vault-tier args still reference this path.
PR 7 updates the manifest to augur_shared.bundle_server and deletes this shim.
"""
from src.mcp.augur_shared.bundle_server import main, run  # noqa: F401

__all__ = ["main", "run"]


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

### Step 1.4: Move `plugin_tools.py` (with shim)

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  cp src/mcp/augur_mcp/plugin_tools.py src/mcp/augur_shared/plugin_tools.py
```

Replace `src/mcp/augur_mcp/plugin_tools.py` with shim:

```python
"""Re-export from augur_shared. DEPRECATED — will be removed in PR 7."""
from src.mcp.augur_shared.plugin_tools import (  # noqa: F401
    _collect_skill_dirs,
    _load_bundle_mcp_module,
    _pin_mcp_sdk_package,
    register_plugin_tools,
)
```

### Step 1.5: Move `compat.py` and `client_surface.py`

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  cp src/mcp/augur_mcp/compat.py src/mcp/augur_shared/compat.py && \
  cp src/mcp/augur_mcp/client_surface.py src/mcp/augur_shared/client_surface.py
```

Replace each original with a star-import shim:
```python
"""Re-export from augur_shared. DEPRECATED — will be removed in PR 7."""
from src.mcp.augur_shared.<modname> import *  # noqa: F401, F403
```

### Step 1.6: Extract `mcp_sdk.py` from `server.py`

`src/mcp/augur_mcp/server.py` contains both tool definitions (kept until PR 6) AND SDK setup (move now). Extract these symbols to `src/mcp/augur_shared/mcp_sdk.py`:

- `_pin_mcp_sdk_package` (function)
- `metrics` (global)
- `mcp_tool_interceptor` (decorator)
- FastMCP setup helper functions (anything not bound to specific tools)

Read `src/mcp/augur_mcp/server.py` to identify the exact symbols. Write `src/mcp/augur_shared/mcp_sdk.py` with the extracted code. Update `src/mcp/augur_mcp/server.py` to import these symbols from the new location (keeping the tool definitions in place):

```python
# Top of src/mcp/augur_mcp/server.py — add re-import
from src.mcp.augur_shared.mcp_sdk import (
    _pin_mcp_sdk_package,
    metrics,
    mcp_tool_interceptor,
)
```

### Step 1.7: Run full test cascade

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/cli/ tests/architecture/ tests/lib/ 2>&1 | tail -5
```
Expected: pass (modulo pre-existing failures in `tests/cli/test_action.py`, `test_get.py`, `test_list.py` documented in `/tmp/track3a-research.md`).

### Step 1.8: Verify Track 2 vault servers still launch

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/cli/test_bundle_server_apple.py tests/cli/test_bundle_server_lifestyle.py tests/cli/test_bundle_server_file_manager.py tests/cli/test_bundle_server_obsidian.py tests/cli/test_bundle_server_ingest.py 2>&1 | tail -5
```
Expected: 5 passed (or skipped if Au-vault not present).

### Step 1.9: Worktree pollution check + commit

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git status --short | head -10
```

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git add src/mcp/augur_shared/ src/mcp/augur_mcp/ && \
  git commit -m "$(cat <<'EOF'
feat(track3a): add src/mcp/augur_shared/ (additive)

PR 1 of Track 3a. Moves cross-server utilities from augur_mcp/ to
new augur_shared/ package; original locations get re-export shims
that PR 7 will remove.

Files moved:
- bundle_server.py (used by Track 2 vault-tier servers)
- plugin_tools.py (skill scan + bundle module loader)
- compat.py, client_surface.py
- mcp_sdk.py (extracted from server.py: _pin_mcp_sdk_package,
  metrics, mcp_tool_interceptor)

augur_mcp.bundle_server still works via shim — Track 2's manifest
vault-tier args remain valid through PR 6. PR 7 updates manifest
to augur_shared.bundle_server.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: PR 2 — Cleanup (retire 23 dormant tools)

**Goal:** Delete 23 dead-or-dormant tools BEFORE the server split. Per audit at `/tmp/track3a-tool-audit.md`.

### Step 2.1: Delete `self_update/` package (9 tools)

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  rm -rf src/mcp/augur_mcp/self_update/
```

### Step 2.2: Delete `scrape_and_save_idea.py`

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  rm src/mcp/augur_mcp/tools/hubs/scrape_and_save_idea.py
```

### Step 2.3: Delete `freeze.py`

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  rm src/mcp/augur_mcp/infrastructure/freeze.py
```

### Step 2.4: Remove tool registrations from surviving files

For each tool, find the `@mcp.tool(name="<tool>")` decorator + the function it decorates + any tests/imports referencing it, and delete:

- `infrastructure/config.py`: remove `get-augur-mode`, `set-augur-mode`, `get-batch-presets` decorators
- `infrastructure/workflow.py`: remove `enhance-dashboard`, `create-dashboard-wizard` decorators
- `infrastructure/mcp_management.py`: remove `switch-mcp-tool-groups` decorator
- `infrastructure/system.py`: remove `record-voice` decorator
- `infrastructure/chains_ext.py`: remove `run-intelligence-prompt` decorator (entire file may be deletable — check)
- `infrastructure/files.py`: remove `match-content-to-skill` decorator
- `core/__init__.py`: remove `vault-file-read`, `vault-file-write` decorators
- `infrastructure/skill_scorer.py`: remove `skill-score` decorator (entire file may be deletable)

Read each file before editing to find the exact decorator line ranges. Use the Edit tool with sufficient context.

### Step 2.5: Remove dashboard references

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  grep -rn "freeze-overview\|get-augur-mode\|set-augur-mode\|get-batch-presets\|enhance-dashboard\|create-dashboard-wizard\|switch-mcp-tool-groups\|record-voice\|run-intelligence-prompt\|match-content-to-skill\|vault-file-read\|vault-file-write\|skill-score\|scrape-and-save-idea-overview\|apply-patch\|diff-module\|update-module\|rollback-module\|list-backups\|learn-pattern\|list-patterns\|mark-pattern-applied\|propose-update" \
    --include="*.ts" --include="*.tsx" --include="*.yaml" --include="*.json" \
    apps/dashboard/lib/server/toolFilter.ts \
    apps/dashboard/app/api/mcp/capabilities/route.ts \
    config/dashboard/mcp_tools.yaml 2>&1 | head -30
```

For each match, remove the line. Update affected files:
- `apps/dashboard/lib/server/toolFilter.ts`: remove deleted tool names from `OPERATION_MODE_HIDDEN`, `OPERATION_HIDDEN`, `TOOL_GROUPS`
- `apps/dashboard/app/api/mcp/capabilities/route.ts`: remove from `CORE_TOOLS` array
- `config/dashboard/mcp_tools.yaml`: remove `self-update` category and any other deleted-tool category mentions

### Step 2.6: Update `skills/auto-skill-quality/SKILL.md`

Read the file; find any `skill-score` mention in the MCP tool list or capability section; remove. Preserve all other content.

### Step 2.7: Audit grep — confirm zero remaining references

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  grep -rn "freeze-overview\|get-augur-mode\|set-augur-mode\|get-batch-presets\|enhance-dashboard\|create-dashboard-wizard\|switch-mcp-tool-groups\|record-voice\|run-intelligence-prompt\|match-content-to-skill\|vault-file-read\|vault-file-write\|skill-score\|scrape-and-save-idea-overview\|apply-patch\|diff-module\|update-module\|rollback-module\|list-backups\|learn-pattern\|list-patterns\|mark-pattern-applied\|propose-update" \
    --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yaml" --include="*.json" \
    src/ apps/ tests/ scripts/ skills/ config/ .github/ 2>&1 | grep -v "__pycache__\|node_modules\|/.worktrees/"
```

Acceptable remaining matches: `docs/superpowers/`, `Au-docs/adrs/`, comments in plan/spec files, this plan itself. Real code matches → STOP and remove.

### Step 2.8: Run test cascade + dashboard build

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/cli/ tests/architecture/ tests/lib/ tests/packages/augur-mcp/ 2>&1 | tail -5
```

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  pnpm --filter dashboard build 2>&1 | tail -10
```

If dashboard build regenerated `apps/dashboard/lib/plugin-runtime/assembled-hubs.json` or `apps/dashboard/lib/tabs/generated-registry.ts`, restore them with `git checkout HEAD --` before committing.

### Step 2.9: Commit

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git add -A src/mcp/augur_mcp/ apps/dashboard/lib/server/toolFilter.ts \
          apps/dashboard/app/api/mcp/capabilities/route.ts \
          config/dashboard/mcp_tools.yaml \
          skills/auto-skill-quality/SKILL.md && \
  git commit -m "$(cat <<'EOF'
refactor(track3a): retire 23 dormant tools

PR 2 of Track 3a. Pre-migration cleanup so the server split doesn't
carry junk forward. Audit at /tmp/track3a-tool-audit.md confirms
each tool below has zero real call sites.

DELETED PACKAGES:
- src/mcp/augur_mcp/self_update/ (entire dir; 9 tools experimental
  self-modifying-code surface that was never wired up)
- src/mcp/augur_mcp/tools/hubs/scrape_and_save_idea.py (1 tool;
  entire module hardcoded to lifestyle — covered by hardcode list)
- src/mcp/augur_mcp/infrastructure/freeze.py (1 tool; freeze-overview
  zero callers)

DELETED TOOL REGISTRATIONS (12 more tools):
- get-augur-mode, set-augur-mode, get-batch-presets (config.py)
- enhance-dashboard, create-dashboard-wizard (workflow.py)
- switch-mcp-tool-groups (mcp_management.py)
- record-voice (system.py — vault note explicitly says not implemented)
- run-intelligence-prompt (chains_ext.py)
- match-content-to-skill (files.py)
- vault-file-read, vault-file-write (core/__init__.py)
- skill-score (skill_scorer.py)

UPDATED CONSUMERS:
- apps/dashboard/lib/server/toolFilter.ts (remove from hidden lists)
- apps/dashboard/app/api/mcp/capabilities/route.ts (remove from CORE_TOOLS)
- config/dashboard/mcp_tools.yaml (remove self-update category)
- skills/auto-skill-quality/SKILL.md (remove skill-score reference)

Total: 23 tools retired. Surface drops from 166 to 143.
Verified: zero remaining references in production code.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: PR 3 — Hardcode removal + skill_registry helper

**Goal:** Replace 10 src/ vault-private hardcodes with dynamic registry lookups. (The 11th, scrape_and_save_idea.py, was deleted in PR 2.)

### Step 3.1: Create `src/mcp/augur_shared/skill_registry.py`

```python
"""Skill registry helpers — dynamic discovery to replace hardcoded lists.

Replaces hardcoded vault-private skill names (apple, lifestyle, etc.)
across src/. Backed by the same skill scanner used by Track 2's
plugin_tools._collect_skill_dirs().
"""
from __future__ import annotations

import functools
from pathlib import Path

from src.mcp.augur_shared.plugin_tools import _collect_skill_dirs


@functools.lru_cache(maxsize=1)
def _all_skill_dirs() -> list[Path]:
    return [skill_dir for _plugin_id, skill_dir in _collect_skill_dirs(apply_exclusions=False)]


@functools.lru_cache(maxsize=1)
def _all_skill_names() -> frozenset[str]:
    return frozenset(sd.name for sd in _all_skill_dirs())


@functools.lru_cache(maxsize=1)
def _vault_skill_names() -> frozenset[str]:
    """Names of skills whose source dir lives outside the Augur repo (vault-tier)."""
    from src.config.paths import get_project_root

    project_root = get_project_root().resolve()
    out: set[str] = set()
    for sd in _all_skill_dirs():
        try:
            sd.resolve().relative_to(project_root)
        except ValueError:
            out.add(sd.name)
    return frozenset(out)


def is_known_skill(name: str) -> bool:
    """True if `name` is a registered skill (vault-tier or project-tier)."""
    return name in _all_skill_names()


def is_vault_skill(name: str) -> bool:
    """True if `name` is a vault-tier skill (resides outside the Augur repo)."""
    return name in _vault_skill_names()


def all_known_skills() -> frozenset[str]:
    return _all_skill_names()


def all_vault_skills() -> frozenset[str]:
    return _vault_skill_names()
```

### Step 3.2: Fix `src/config/mcp_tools.py:386-387`

Read lines 380-395 first. The `vertical_skills` set literal is a hardcoded list. Replace:

```python
vertical_skills = {"career", "lifestyle", ...}  # hardcoded
```

with a dynamic call:

```python
from src.mcp.augur_shared.skill_registry import all_known_skills

# Filter to skills classified as vertical (consumer-facing user surfaces).
# Implementation: load each SKILL.md frontmatter and check x-augur-type,
# OR maintain a category mapping in config/system/hubs.yaml (Track 3b).
vertical_skills = _resolve_vertical_skills()  # helper below
```

Add helper function `_resolve_vertical_skills()` that reads each skill's `SKILL.md` frontmatter and returns the set of skills with `x-augur-type` matching the legacy vertical classification, OR (preferred) consults `config/system/hubs.yaml` (added by Track 3b — coordinate with Track 3b on whether this lookup is available).

If Track 3b's `hubs.yaml` is not yet committed when Track 3a PR 3 runs, fall back to dynamic SKILL.md scanning.

### Step 3.3: Fix `src/mcp/augur_mcp/infrastructure/mcp_management.py:289`

Read lines 285-295. Replace `"lifestyle"` heuristic with `is_known_skill(skill_name)` check from `skill_registry`.

### Step 3.4: Fix `src/mcp/augur_mcp/infrastructure/config.py:730-742`

Replace the `valid_bundles` hardcoded list:

```python
# Before:
valid_bundles = ["apple", "lifestyle", "obsidian", "file-manager", "ingest", ...]
# (11 hardcoded names)

# After:
from src.mcp.augur_shared.skill_registry import all_known_skills

def _get_valid_bundles() -> frozenset[str]:
    return all_known_skills()

# Replace usages:
if bundle not in _get_valid_bundles():
    raise ValueError(...)
```

This subsumes line 736 (which was just one of the hardcoded names in the list).

### Step 3.5: Fix `src/mcp/augur_mcp/domain/plugins.py:218`

Read line 215-225. Remove the `bundle: str = "lifestyle"` default parameter. Make `bundle` required. If callers passed `bundle=None` previously and relied on the default, fix the call sites to pass an explicit bundle.

Audit grep for callers:
```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  grep -rn "<function_name_here>" --include="*.py" src/ apps/ tests/
```
Update each caller to pass an explicit bundle.

### Step 3.6: Fix `src/mcp/augur_mcp/tools/hubs/capabilities.py:24`

Read lines 20-30. The hardcoded `"apple"` capability description should move to skill metadata. Each skill's SKILL.md `x-augur-mcp-tools` field declares its capability descriptions. The capabilities tool reads them at runtime:

```python
# Before:
CAPABILITIES = {"apple": "Apple ecosystem integration", ...}

# After:
def _load_capabilities() -> dict[str, str]:
    from src.mcp.augur_shared.plugin_tools import _collect_skill_dirs
    out: dict[str, str] = {}
    for _plugin_id, skill_dir in _collect_skill_dirs(apply_exclusions=False):
        # Read SKILL.md frontmatter; pull x-augur-capabilities or description
        ...
    return out
```

### Step 3.7: Fix `src/mcp/augur_mcp/infrastructure/browse/dev.py:98`

Read lines 95-105. Replace `"lifestyle"` literal in the list with a dynamic discovery call (same pattern as Step 3.4 — query the registry).

### Step 3.8: Fix `src/mcp/augur_mcp/infrastructure/mcp_management.py:318`

Read lines 315-325. The `lifestyle` reference is in a category-description string. Generalize:

```python
# Before:
"description": "Lifestyle category — health, habits, etc.",

# After: derive from skill metadata, or remove the description if it's per-bundle.
```

### Step 3.9: Fix `src/mcp/augur_mcp/infrastructure/browse/cli.py:308`

Read lines 305-315. Replace:

```python
if integration_type == "vault" and skill == "obsidian":
```

with:

```python
from src.mcp.augur_shared.skill_registry import is_vault_skill

if integration_type == "vault" and is_vault_skill(skill):
```

### Step 3.10: Add architecture test

Save `tests/architecture/test_no_vault_skill_refs.py`:

```python
"""Verify no string literals matching vault-tier skill names remain in src/.

Track 3a verification gate: replaces hardcoded skill enumerations
with dynamic discovery via src.mcp.augur_shared.skill_registry.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.config.paths import get_project_root

# Vault-tier skills per Track 2. These names should NOT appear as
# string literals in src/ (use is_vault_skill() / is_known_skill() instead).
VAULT_SKILL_NAMES = ["apple", "lifestyle", "file-manager", "obsidian", "ingest"]

# Files allowed to contain these names (registry, helpers, comments,
# test fixtures, generated artifacts):
ALLOWED_FILES = {
    "src/mcp/augur_shared/skill_registry.py",
    "src/mcp/augur_shared/plugin_tools.py",
    # Add other principled exceptions here.
}


def _scan_python_files() -> list[Path]:
    src = get_project_root() / "src"
    return [p for p in src.rglob("*.py") if "__pycache__" not in str(p)]


@pytest.mark.parametrize("skill_name", VAULT_SKILL_NAMES)
def test_no_vault_skill_string_literals_in_src(skill_name: str) -> None:
    pattern = re.compile(rf'"\'})["\']')
    violations: list[tuple[Path, int]] = []

    project_root = get_project_root()
    for path in _scan_python_files():
        rel = path.relative_to(project_root).as_posix()
        if rel in ALLOWED_FILES:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if pattern.search(line):
                # Skip comments
                stripped = line.split("#", 1)[0]
                if pattern.search(stripped):
                    violations.append((path.relative_to(project_root), lineno))

    assert not violations, (
        f"Vault skill name {skill_name!r} found as string literal in src/:\n"
        + "\n".join(f"  {p}:{ln}" for p, ln in violations)
    )
```

### Step 3.11: Run tests + commit

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/architecture/test_no_vault_skill_refs.py -v 2>&1 | tail -10
```
Expected: 5 parametrized cases pass.

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/cli/ tests/architecture/ tests/lib/ 2>&1 | tail -5
```

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git status --short | head -20
```

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git add src/mcp/augur_shared/skill_registry.py \
          src/config/mcp_tools.py \
          src/mcp/augur_mcp/infrastructure/mcp_management.py \
          src/mcp/augur_mcp/infrastructure/config.py \
          src/mcp/augur_mcp/domain/plugins.py \
          src/mcp/augur_mcp/tools/hubs/capabilities.py \
          src/mcp/augur_mcp/infrastructure/browse/dev.py \
          src/mcp/augur_mcp/infrastructure/browse/cli.py \
          tests/architecture/test_no_vault_skill_refs.py && \
  git commit -m "$(cat <<'EOF'
refactor(track3a): replace 11 src/ vault-private hardcodes with dynamic discovery

PR 3 of Track 3a. Replaces hardcoded skill-name string literals in
framework code with calls to a new skill_registry module that queries
the live skill scanner.

NEW HELPER:
- src/mcp/augur_shared/skill_registry.py — is_known_skill(),
  is_vault_skill(), all_known_skills(), all_vault_skills()

SITES FIXED (10):
- src/config/mcp_tools.py:386 — vertical_skills set literal
- src/mcp/augur_mcp/infrastructure/mcp_management.py:289,318
- src/mcp/augur_mcp/infrastructure/config.py:730-742 — valid_bundles
- src/mcp/augur_mcp/domain/plugins.py:218 — required bundle param
- src/mcp/augur_mcp/tools/hubs/capabilities.py:24 — capability map
- src/mcp/augur_mcp/infrastructure/browse/dev.py:98
- src/mcp/augur_mcp/infrastructure/browse/cli.py:308 — obsidian check

The 11th site (tools/hubs/scrape_and_save_idea.py) was deleted with
the entire module in PR 2.

VERIFICATION:
- New tests/architecture/test_no_vault_skill_refs.py asserts no
  vault-skill string literals remain in src/ (5 parametrized cases).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: PR 4 — `src/mcp/augur_core/` setup (additive)

**Goal:** New augur-core server with 29 registry/discovery tools. Monolith continues running alongside during this PR.

### Step 4.1: Create package skeleton

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  mkdir -p src/mcp/augur_core/tools && \
  touch src/mcp/augur_core/tools/__init__.py
```

### Step 4.2: Write `src/mcp/augur_core/__init__.py`

```python
"""augur-core: registry/discovery MCP server.

Hosts 29 tools that span all bundles' metadata: skill listings,
hub indexes, ADR/agent/script/test enumerations, scheduled execution
details, capability advertisements.

Per Track 3a design, this server multiplexes registry tools across
all project- and vault-tier bundles via dynamic skill discovery.
"""
```

### Step 4.3: Write `src/mcp/augur_core/__main__.py`

```python
"""Entry point: python -m augur_core."""
from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.mcp.augur_shared.mcp_sdk import (
    _pin_mcp_sdk_package,
    metrics,
    mcp_tool_interceptor,
)
from src.mcp.augur_core.tools import register_core_tools


def run() -> int:
    _pin_mcp_sdk_package()
    mcp = FastMCP("augur-core")
    register_core_tools(mcp, mcp_tool_interceptor, metrics)
    mcp.run()
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
```

### Step 4.4: Write `src/mcp/augur_core/tools/__init__.py`

```python
"""Wire the 29 augur-core tools into a FastMCP instance.

Tool definitions live in their existing files under src/mcp/augur_mcp/.
Track 3a doesn't move them in this PR — only the registration entrypoint
does. The actual tool functions are imported and re-registered.

Tools registered (29 total):
- 24 from src/mcp/augur_mcp/core/__init__.py: cross-skill, find-skill,
  get-skill, get-skill-doc, get-skill-health, list-skills,
  list-skill-actions, list-hub-recent-files, list-hub-vault-notes,
  list-skill-vault-notes, health, metrics, get-context, load-module,
  load-reference, update-skill-doc, save-synthesis, cache-control,
  get-config, get-design-standards, get-preferences, update-preference,
  ask-retain
- 13 from src/mcp/augur_mcp/infrastructure/browse/__init__.py:
  browse-index, get-scheduled-execution-detail, list-api-routes,
  list-adrs, list-agents, list-cli-commands, list-integrations,
  list-prompts, list-scripts, list-tests, list-vault-items,
  get-skill-cli-help, cli-help
- 2 from src/mcp/augur_mcp/tools/hubs/: agent-registry,
  augur-list-capabilities
- 1 from src/mcp/augur_mcp/tools/internal/vault_status.py: vault-status

Total: 29 (after Track 3a PR 2 retired vault-file-read,
vault-file-write, skill-score, etc.)
"""
from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]


def register_core_tools(
    mcp: FastMCP,
    interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    # Each block re-imports the existing register_X_tools functions
    # from augur_mcp/ and calls them against the augur-core FastMCP
    # instance.
    from src.mcp.augur_mcp.core import register_core_tools as _reg_core
    _reg_core(mcp, interceptor, metrics)

    from src.mcp.augur_mcp.infrastructure.browse import register_browse_tools as _reg_browse
    _reg_browse(mcp, interceptor, metrics)

    from src.mcp.augur_mcp.tools.hubs.agent_registry import register_agent_registry_tool as _reg_agent
    _reg_agent(mcp, interceptor, metrics)

    from src.mcp.augur_mcp.tools.hubs.capabilities import register_capabilities_tool as _reg_cap
    _reg_cap(mcp, interceptor, metrics)

    from src.mcp.augur_mcp.tools.internal.vault_status import register_vault_status_tool as _reg_vs
    _reg_vs(mcp, interceptor, metrics)
```

(NOTE: actual function names may differ from what's shown — read each source file to find the right register_X function. If functions don't exist or are scoped differently, adapt accordingly.)

The browse `register_browse_tools` may register all 17 browse tools. To register only the 13 listing tools (and exclude the 4 operational ones for augur-framework), either split `browse/__init__.py` into a `register_browse_listings` and `register_browse_operations` pair, OR pass a flag. Pick whichever is cleaner; if the existing browse registration is monolithic, split it now.

### Step 4.5: Verify augur-core starts

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run python -c "
import asyncio
from src.mcp.augur_core import __main__ as core_main
print('augur-core import OK')
"
```

Then a stdio smoke test (similar to Track 2's bundle server tests):

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | timeout 10 uv run python -m augur_core 2>&1 | head -5
```

Expected: returns tools/list response with ~29 tools.

### Step 4.6: Add manifest entry

Edit `config/system/mcp_servers.yaml`. Append to `project_tier`:

```yaml
  - id: augur-core
    description: Project-tier registry/discovery server (Track 3a)
    command: python
    args: [-m, augur_core]
    cwd_required: true
    env:
      PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"
    per_client_args:
      claude: ["--client-id", "claude"]
      codex: ["--client-id", "codex"]
      gemini: ["--client-id", "gemini"]
```

(`per_client_args` matches existing augur entry.)

### Step 4.7: Verify manifest + tests

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run python -c "from src.cli_config.manifest import load_manifest; m = load_manifest(); print([e.id for e in m.project_tier])"
```
Expected: `['augur', 'augur-core']`.

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/cli/ tests/architecture/ tests/lib/ 2>&1 | tail -5
```

### Step 4.8: Add `tests/cli/test_augur_core_server.py`

Mirror of Track 2's `test_bundle_server_apple.py`:

```python
"""Smoke test: launch augur-core stdio server and verify tools/list."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def test_augur_core_server_starts_and_lists_tools() -> None:
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{project_root}:{project_root}/src/mcp:{env.get('PYTHONPATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "augur_core"],
        cwd=str(project_root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
        ls = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        assert proc.stdin and proc.stdout
        proc.stdin.write((json.dumps(init) + "\n").encode())
        proc.stdin.write((json.dumps(ls) + "\n").encode())
        proc.stdin.flush()

        deadline = time.monotonic() + 10.0
        responses: list[dict] = []
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                responses.append(json.loads(line.decode()))
            except json.JSONDecodeError:
                continue
            if any(r.get("id") == 2 for r in responses):
                break

        tools = next((r for r in responses if r.get("id") == 2), None)
        assert tools is not None, f"no tools/list response; got {responses!r}"
        n = len(tools["result"]["tools"])
        assert 25 <= n <= 32, f"expected ~29 tools, got {n}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
```

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/cli/test_augur_core_server.py -v 2>&1 | tail -10
```

### Step 4.9: Commit

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git add src/mcp/augur_core/ config/system/mcp_servers.yaml tests/cli/test_augur_core_server.py && \
  git commit -m "$(cat <<'EOF'
feat(track3a): add src/mcp/augur_core/ (additive)

PR 4 of Track 3a. Adds the augur-core server package: a stdio MCP
server that hosts 29 registry/discovery tools spanning all bundles'
metadata.

Tools registered (29 from existing definitions in augur_mcp/):
- 24 core registry tools (list-skills, find-skill, get-skill, etc.)
- 13 browse-listing tools (list-adrs, list-agents, browse-index, etc.)
- 2 hub registry tools (agent-registry, augur-list-capabilities)
- 1 vault-status tool

Manifest entry added to config/system/mcp_servers.yaml project_tier.
The augur monolith continues registering these tools too — atomic
switchover happens in PR 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: PR 5 — `src/mcp/augur_framework/` setup (additive)

**Goal:** New augur-framework server with ~114 operational tools.

### Step 5.1: Create package skeleton

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  mkdir -p src/mcp/augur_framework/tools && \
  touch src/mcp/augur_framework/tools/__init__.py
```

### Step 5.2: Write `src/mcp/augur_framework/__init__.py`

```python
"""augur-framework: project-tier operational MCP server.

Hosts ~114 tools across file ops, plugins, jobs, IDE control,
MCP management, settings, system, performance, workflow, templates,
widgets, paths, backend/clients, actions, and src/lib/* libraries.
"""
```

### Step 5.3: Write `src/mcp/augur_framework/__main__.py`

Same shape as augur-core's, except importing `register_framework_tools` from `src.mcp.augur_framework.tools` and naming the FastMCP `"augur-framework"`.

### Step 5.4: Write `src/mcp/augur_framework/tools/__init__.py`

Register all ~114 operational tools. The tools are imported from their existing files in `src/mcp/augur_mcp/`. List per the design spec:

- `domain/cowork.py` (3): classify-collateral, get-cowork-status, sync-cowork-results
- `domain/ide.py` (7): client-test, get-ide-history, get-ide-status, ide-integrations, ide-lifecycle, run-oneshot-cli, send-ide-prompt
- `domain/plugins.py` (8): get-plugin-load-status, install-plugin, list-plugins, plugin-health, reload-plugin, toggle-plugin, toggle-skill, uninstall-plugin
- `infrastructure/__init__.py` (5): get-local-backend-status, list-available-clients, resolve-client, set-client-override, toggle-airplane-mode
- `infrastructure/actions.py` (3): execute-fast-action, list-action-buttons, skill-action
- `infrastructure/auto_index_notes.py` (1): auto-index-notes-status
- `infrastructure/browse/__init__.py` (4 operational): open-file, reveal-in-finder, cli-install, cli-status
- `infrastructure/config.py` (after retirement, 7): get-chat-session, update-chat-session, get-features, get-intelligence-stats, get-usage-stats, clear-system-cache, export-skill-plugin
- `infrastructure/documents.py` (1): sync-bugs
- `infrastructure/files.py` (12 after retirement): file-delete, file-edit, file-info, file-list, file-move, file-read, file-read-multi, file-search, file-write, file-write-binary, resolve-asset-path (and others — match the file)
- `infrastructure/harness.py` (2): get-brain-harness-snapshot, refresh-brain-harness-snapshot
- `infrastructure/jobs.py` (3): cancel-job, get-job-status, list-jobs
- `infrastructure/mcp_management.py` (after retirement, 9): configure-mcp-server, discover-augur, get-api-route-stats, get-mcp-context-stats, get-mcp-diagnostics, list-mcp-tools, preload-mcp-context, switch-mcp-context, test-mcp-connection
- `infrastructure/paths.py` (5): cleanup-path, get-path-config, get-path-sizes, update-path-config, validate-paths
- `infrastructure/performance.py` (7): get-daily-summary, get-dashboard-data, get-dashboard-groups, get-factory-status, get-performance-metrics, get-system-health, save-performance-metric
- `infrastructure/settings/__init__.py` (2): get-settings, set-config
- `infrastructure/system.py` (after retirement, 9): analyze-import, apply-import, list-services, open-client-runtime-folder, repair-mcp-configs, service-status, system-open, system-open-file (and others)
- `infrastructure/workflow.py` (after retirement, 4): emit-execution-event, generate-skill, get-focused-tools, query-audit-log
- `tools/hubs/widgets.py` (4): delete-widget, list-widgets, pin-widget, render-widget
- `tools/internal/template_resolver.py` (5): activate-template, list-templates-catalog, read-active-templates, resolve-template, save-template-override

Total: ~89-114 (depending on exact post-retirement counts in `infrastructure/files.py` and `infrastructure/system.py`).

Pattern for each block:
```python
from src.mcp.augur_mcp.domain.cowork import register_cowork_tools as _reg
_reg(mcp, interceptor, metrics)
```

Read each source file to find the actual `register_*` function names.

### Step 5.5: Verify augur-framework starts

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run python -c "from src.mcp.augur_framework import __main__; print('OK')"
```

Stdio smoke test (similar to augur-core):

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | timeout 10 uv run python -m augur_framework 2>&1 | head -5
```

### Step 5.6: Add manifest entry

Append to `project_tier` in `config/system/mcp_servers.yaml`:

```yaml
  - id: augur-framework
    description: Project-tier operational server (Track 3a)
    command: python
    args: [-m, augur_framework]
    cwd_required: true
    env:
      PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"
    per_client_args:
      claude: ["--client-id", "claude"]
      codex: ["--client-id", "codex"]
      gemini: ["--client-id", "gemini"]
```

### Step 5.7: Add `tests/cli/test_augur_framework_server.py`

Mirror of `test_augur_core_server.py`. Expected tool count: 95-120 (allow generous range — exact count depends on post-retirement state of files.py and system.py).

### Step 5.8: Run tests + commit

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/cli/ tests/architecture/ tests/lib/ 2>&1 | tail -5
```

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git add src/mcp/augur_framework/ config/system/mcp_servers.yaml tests/cli/test_augur_framework_server.py && \
  git commit -m "$(cat <<'EOF'
feat(track3a): add src/mcp/augur_framework/ (additive)

PR 5 of Track 3a. Adds the augur-framework server package: a stdio
MCP server hosting ~114 project-tier operational tools.

Tools registered span: file ops, plugins, jobs, IDE control, MCP
management, settings, system, performance, workflow, templates,
widgets, paths, backend/clients, actions, src/lib/* libraries.

Manifest entry added. Atomic switchover in PR 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: PR 6 — Atomic switchover (HIGH BLAST RADIUS)

**Goal:** Replace the `augur` monolith entry in the manifest with the augur-core + augur-framework pair. After this PR + user's `aug config sync`, the monolith is no longer registered with AI clients.

### Step 6.1: Pre-switchover verification

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/cli/test_augur_core_server.py tests/cli/test_augur_framework_server.py tests/cli/test_bundle_server_apple.py -v 2>&1 | tail -10
```
All must pass before proceeding. STOP if any fail.

### Step 6.2: Edit `config/system/mcp_servers.yaml`

Remove the `augur` entry from `project_tier`. The file should now have ONLY `augur-core` and `augur-framework` in `project_tier`:

```yaml
project_tier:
  - id: augur-core
    description: Project-tier registry/discovery server (Track 3a)
    # ... existing config from PR 4 ...

  - id: augur-framework
    description: Project-tier operational server (Track 3a)
    # ... existing config from PR 5 ...

# vault_tier: unchanged (5 entries from Track 2)
# monolith_exclusions: unchanged
```

### Step 6.3: Delete `src/mcp/augur_mcp/server.py` (the monolith entrypoint)

The file is the `python -m augur_mcp` entrypoint. Other files in `augur_mcp/` continue to exist (they get dismantled in PR 7) but the entrypoint is gone.

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  rm src/mcp/augur_mcp/server.py 2>/dev/null || echo "already gone"
```

### Step 6.4: Verify `aug config sync --dry-run`

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run aug config sync --dry-run 2>&1 | head -25
```

Expected diff:
- Each client (claude/codex/gemini): `- augur` (removed) + `+ augur-core` and `+ augur-framework` (added).
- Vault entries unchanged.

### Step 6.5: Run all tests + dashboard build

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/cli/ tests/architecture/ tests/lib/ tests/packages/ 2>&1 | tail -10
```

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  pnpm --filter dashboard build 2>&1 | tail -10
```

If dashboard regenerated artifacts, restore with `git checkout HEAD --` before commit.

### Step 6.6: Commit

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git add config/system/mcp_servers.yaml src/mcp/augur_mcp/server.py 2>/dev/null; \
  git status --short && \
  git commit -m "$(cat <<'EOF'
feat(track3a): atomic switchover — augur monolith → core + framework

PR 6 of Track 3a (HIGH BLAST RADIUS). Replaces the augur monolith
entry in config/system/mcp_servers.yaml with augur-core + augur-framework
(added in PRs 4-5). Deletes the monolith entrypoint
(src/mcp/augur_mcp/server.py).

POST-MERGE STEPS REQUIRED BY USER:
  1. cd ~/Projects/Augur (main checkout)
  2. git pull
  3. uv run aug config sync   (rewrites all 3 client configs)
  4. Reload Claude Code, Codex, Gemini sessions
  5. Verify: tools/list against augur-core shows 29 tools;
     tools/list against augur-framework shows ~114 tools;
     no augur server in tools/list any more.

ROLLBACK PATH (if augur-core or augur-framework fails to start):
  - Each client config has a timestamped backup at <file>.bak.<TS>
  - cp ~/.codex/config.toml.bak.<TS> ~/.codex/config.toml
  - Reload sessions
  - File a bug; investigate before retrying

Vault-tier servers (apple/lifestyle/file-manager/obsidian/ingest)
unchanged — they continue to launch via augur_mcp.bundle_server until
PR 7 updates the manifest to augur_shared.bundle_server.

Track 4 (visibility filter removal) ships immediately after Track 3a.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: PR 7 — Dismantle `src/mcp/augur_mcp/` namespace

**Goal:** After PR 6's switchover, no code should import from `augur_mcp.*`. Audit, migrate any stragglers, then delete.

### Step 7.1: Audit grep

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  grep -rn "from augur_mcp\|import augur_mcp\|from src\.mcp\.augur_mcp\|src\.mcp\.augur_mcp" \
    --include="*.py" . 2>&1 | grep -v "__pycache__\|/.worktrees/" | head -40
```

Acceptable matches: docstrings, plan/spec comments, ADRs.
Real imports → migrate to `augur_core`, `augur_framework`, or `augur_shared`. Each migration is a 1-line edit.

### Step 7.2: Migrate stragglers (case by case)

For each real import found in Step 7.1:
- If it's a tool definition that moved to augur_core — change to `from src.mcp.augur_core...`
- If it's a tool definition that moved to augur_framework — change to `from src.mcp.augur_framework...`
- If it's a shared utility — change to `from src.mcp.augur_shared...`

### Step 7.3: Update manifest's vault-tier args

Edit `config/system/mcp_servers.yaml`. For each of the 5 vault-tier entries, replace:

```yaml
    args: [-m, augur_mcp.bundle_server, <bundle>]
```

with:

```yaml
    args: [-m, augur_shared.bundle_server, <bundle>]
```

### Step 7.4: Delete the namespace

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  rm -rf src/mcp/augur_mcp/ && \
  ls src/mcp/
```
Expected: `augur_core/`, `augur_framework/`, `augur_shared/`. NOT `augur_mcp/`.

### Step 7.5: Run full cascade + dashboard build

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/ skills/ 2>&1 | tail -10
```

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  pnpm --filter dashboard build 2>&1 | tail -10
```

If anything regenerates, restore.

### Step 7.6: Verify all 5 vault servers still launch

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/cli/test_bundle_server_apple.py tests/cli/test_bundle_server_lifestyle.py tests/cli/test_bundle_server_file_manager.py tests/cli/test_bundle_server_obsidian.py tests/cli/test_bundle_server_ingest.py -v 2>&1 | tail -10
```
Expected: 5 passed (or skipped if Au-vault missing).

### Step 7.7: Commit

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git status --short | head -20 && \
  git add -A && \
  git commit -m "$(cat <<'EOF'
refactor(track3a): dismantle src/mcp/augur_mcp/ namespace

PR 7 of Track 3a. Deletes src/mcp/augur_mcp/ entirely. All shared
utilities live in augur_shared/; all tool definitions live in
augur_core/ or augur_framework/.

MANIFEST UPDATE: vault-tier args now reference augur_shared.bundle_server
instead of augur_mcp.bundle_server. After merge:
  uv run aug config sync && reload AI clients

After this PR, the augur_mcp namespace is fully retired. The migration
spec's "no monolith" goal is met.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: PR 8 — Architecture allowlist retirement + ADR

**Goal:** Drive the architecture-test allowlist to empty. Write Track 3a ADR.

### Step 8.1: Read current allowlist

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  grep -B2 -A1 "ALLOWED_CROSS_SKILL_IMPORTS\|, \"ai\")\|, \"rag\")" tests/architecture/test_no_cross_skill_imports.py | head -20
```

### Step 8.2: Edit the allowlist to empty

In `tests/architecture/test_no_cross_skill_imports.py`, replace the populated `ALLOWED_CROSS_SKILL_IMPORTS` set with:

```python
ALLOWED_CROSS_SKILL_IMPORTS: frozenset[tuple[str, str]] = frozenset()
"""Empty after Track 3a (2026-04-29).

Previously held entries that retired across the migration:
- ("ingest", "ai"): retired Track 3a (sync_agents path migrated;
  ingest now vault-tier per Track 2).
- ("ingest", "rag"): retired Track 3a (rag bundle MCP consumes
  src/lib/index/ from Track 1; ingest now vault-tier per Track 2).
- ("knowledge", "rag"): retired Track 3a (knowledge consumes
  src/lib/index/ directly from Track 1).

Goal: ZERO cross-skill imports across project bundles. Vault bundles
may import project-tier libraries via src.lib.* but not skills.<other>.
"""
```

### Step 8.3: Run the architecture test

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/architecture/ -v 2>&1 | tail -15
```

Expected: pass with zero allowlist entries.

If the test fails because a real cross-skill import is now caught, that's a regression to fix in this PR (or a deferred allowlist that needs documenting). Investigate each violation.

### Step 8.4: Run full final test cascade + dashboard build

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  uv run pytest tests/ skills/ 2>&1 | tail -10
```

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  pnpm --filter dashboard build 2>&1 | tail -10
```

### Step 8.5: Write ADR `track3a-framework-split.md`

Save to `~/Documents/Augur/adrs/ADR-XXX-track3a-framework-split.md` (use the next ADR number — check `~/Documents/Augur/adrs/` for the latest). Augur ADRs use frontmatter; check `docs/agent-topics/CODING.md` for the format.

Body:

```markdown
---
adr: NNN
status: Implemented
title: Track 3a — Framework Server Split + Cleanup + Hardcode Removal
date: 2026-04-29
tags:
  - architecture
  - mcp
  - migration
related:
  - cross-client-bundle-architecture (Layer 1)
  - cross-client-bundle-migration (Layer 4)
  - track1-library-extraction
  - track2-vault-server-split
---

## Context

Layer 4 of the cross-client bundle architecture migration described
Track 3a as splitting the `augur` monolith MCP server into augur-core
(registry/discovery) and augur-framework (operational), and removing
10 known src/ vault-private hardcodes. Tracks 1 and 2 had already
landed; Track 3a closes the project-tier server reorganization.

## Decision

Implemented per `docs/superpowers/specs/2026-04-29-track3a-framework-split-design.md`:

- Two project-tier servers: augur-core (29 tools) + augur-framework (~114 tools)
- New `src/mcp/augur_shared/` package for cross-server utilities
- 23 dormant tools retired before migration (166 → 143)
- 11 src/ vault-private hardcodes replaced with dynamic discovery
- `src/mcp/augur_mcp/` namespace fully retired
- Architecture-test allowlist drove to empty

## Consequences

- Per-client tool surface naturally bounded by per-server registration
- Track 4 (visibility filter removal) ready to ship as a single PR
- Future per-bundle server splits (project-tier or vault-tier) follow
  the proven pattern in augur_shared.bundle_server.
- The skill registry helpers in augur_shared.skill_registry can be
  reused by future code that needs vault/project skill discrimination.

## PRs landed

PR 1: src/mcp/augur_shared/ setup (additive)
PR 2: Retire 23 dormant tools
PR 3: Hardcode removal + skill_registry helper
PR 4: src/mcp/augur_core/ setup
PR 5: src/mcp/augur_framework/ setup
PR 6: Atomic switchover
PR 7: Dismantle src/mcp/augur_mcp/ namespace
PR 8: Allowlist retirement + this ADR

(SHAs filled in at merge time.)
```

### Step 8.6: Commit

```bash
cd ~/Projects/Augur/.worktrees/track3a-framework-split && \
  git add tests/architecture/test_no_cross_skill_imports.py && \
  git commit -m "$(cat <<'EOF'
refactor(track3a): retire architecture-test allowlist; ADR

PR 8 of Track 3a (final). Drives ALLOWED_CROSS_SKILL_IMPORTS to empty:
3 entries retire (("ingest","ai"), ("ingest","rag"), ("knowledge","rag")).

The retirement preconditions:
- ingest is vault-tier (Track 2)
- ai is src/lib/ai/ (Track 1 Library 5)
- rag is src/lib/index/ (Track 1 Library 4)
- knowledge is src/lib/knowledge/ (Track 1 Library 2)
- src/mcp/augur_mcp/ is dismantled (Track 3a PR 7)

After this PR, no project bundle imports from another project bundle's
internals. Vault-tier bundles may import src/lib/* but not skills/<other>.

ADR written separately to ~/Documents/Augur/adrs/.

Track 3a complete. Track 4 (visibility filter removal) ready to ship.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Then commit the ADR separately (Au-docs is not in this Augur repo; commit there if applicable).

---

## Done criteria

Track 3a is complete when:

1. ✅ `src/mcp/augur_core/` exists; `python -m augur_core` exposes 29 tools
2. ✅ `src/mcp/augur_framework/` exists; `python -m augur_framework` exposes ~114 tools
3. ✅ `src/mcp/augur_shared/` exists with cross-server utilities
4. ✅ `src/mcp/augur_mcp/` directory deleted
5. ✅ `ALLOWED_CROSS_SKILL_IMPORTS` is empty
6. ✅ 23 dormant tools retired; zero references in production code
7. ✅ 11 src/ vault-private hardcodes replaced with dynamic discovery
8. ✅ `tests/architecture/test_no_vault_skill_refs.py` passes
9. ✅ `aug config sync` writes 2 project-tier servers + 5 vault-tier servers
10. ✅ Dashboard builds clean
11. ✅ All 5 vault-tier per-bundle servers still launch (Track 2 invariant)
12. ✅ ADR `track3a-framework-split.md` written
13. ✅ All 8 PRs merged

After Track 3a ships, dispatch Track 4 (visibility filter removal — single PR).
