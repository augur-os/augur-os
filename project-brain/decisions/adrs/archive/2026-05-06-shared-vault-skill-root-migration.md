# Shared Vault Skill Root Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the shared/private vault migration by retiring repo-root `skills/` and making `shared-vault/skills/` plus the configured private vault `skills/` the only canonical skill roots.

**Architecture:** Keep the physical source of team skills under the repo-local shared vault, and keep personal skills under the configured private vault. Runtime discovery, generated client exports, MCP tool loading, dashboard scanners, and adaptive loops must resolve canonical skill roots through path helpers instead of assuming `PROJECT_ROOT / "skills"`. During the migration, Python's top-level `skills.*` package may continue to resolve only through the canonical `shared-vault` parent on `PYTHONPATH`; there must be no repo-root compatibility directory or symlink.

**Tech Stack:** Python 3.11+, pathlib, YAML, Augur path helpers, Augur adaptive loop commands, Next.js/TypeScript dashboard generators, MCP server manifests.

---

## Governing Design

Use `docs/superpowers/specs/2026-05-03-shared-vault-enterprise-overlay-design.md` as the product contract.

This plan implements Phase 4 and Phase 5 from that spec:

- inventory every current repo-root skill,
- classify content before moving it,
- move canonical team skill bundles to `shared-vault/skills/`,
- update discovery and generated surfaces to use shared/private roots,
- remove repo-root `skills/` assumptions,
- block the repo-root `skills/` directory from returning.

This plan deliberately does not move private-vault skills into the repo. Private skills remain in the configured vault repo, currently resolved from `config/system/vault.yaml`.

## Migration Rules

- Do not create `skills -> shared-vault/skills` symlinks.
- Do not leave an empty repo-root `skills/` directory.
- Do not keep root-skill compatibility fallbacks in runtime code.
- Do not move generated client exports into `shared-vault/skills/`.
- Do not manually edit generated registries except through their generators.
- Use `git mv` for tracked skill directories so file history stays reviewable.
- Keep `shared-vault/skills/README.md` as the root explainer; move skill bundles under it.
- Keep runtime state, cache, logs, `.codex/`, `.claude/`, `.gemini/`, and build output outside vault roots.

## File Structure

| Path | Action | Responsibility |
| --- | --- | --- |
| `scripts/check_skill_root_migration.py` | Create | Static guard for forbidden repo-root `skills/` assumptions and migration inventory. |
| `tests/test_shared_vault_skill_root_migration.py` | Create | Regression tests for the guard and final root contract. |
| `src/config/paths.py` | Modify | Retarget canonical skill root helpers to shared/private roots. |
| `src/plugins/skill_discovery.py` | Modify | Classify shared-vault skills as canonical shared skills and private-vault skills as user/private skills. |
| `src/lib/index/_indexer_helpers.py` | Modify | Remove repo-root skill source metadata and keep shared/private provenance. |
| `src/lib/index/_scanners_structural.py` | Modify | Scan scripts, MCP tools, pages, commands, actions, and workflows through managed skill roots. |
| `src/lib/index/_scanners_knowledge.py` | Modify | Scan skill docs, prompts, actions, workflows, and commands through managed skill roots. |
| `src/lib/index/unified_indexer.py` | Modify | Update comments and callers to reflect shared/private canonical roots. |
| `src/lib/index/unified_search.py` | Modify | Resolve skill search through managed shared/private roots instead of `get_skills_dir()` only. |
| `src/mcp/augur_shared/config.py` | Modify | Treat `shared-vault/skills` as the project skill landmark. |
| `src/mcp/augur_shared/plugin_tools.py` | Modify | Load skill MCP modules from managed roots. |
| `src/mcp/augur_shared/adapters/filesystem_registry.py` | Modify | Scan shared/private skill roots, not repo-root `skills`. |
| `src/mcp/augur_framework/tools/domain/plugins.py` | Modify | Install/adopt team skills into `shared-vault/skills`. |
| `src/mcp/augur_core/tools/core/skill_lifecycle.py` | Modify | Adopt external skills into `shared-vault/skills`. |
| `apps/dashboard/lib/server/skillsLookup.ts` | Modify | Look up skills through `shared-vault/skills` and private-vault metadata when available. |
| `apps/dashboard/lib/server/skillsScanning.ts` | Modify | Replace root `skills/` scanning with configured canonical roots. |
| `apps/dashboard/scripts/mount-plugins.ts` | Modify | Mount pages/config from shared/private skill roots. |
| `apps/dashboard/scripts/generate_registry.py` | Modify | Generate skill registry from shared/private roots. |
| `apps/dashboard/scripts/rebuild-plugins.ts` | Modify | Regenerate from shared-vault skill source. |
| `apps/dashboard/scripts/block-registry-gen.ts` | Modify | Emit source labels under `shared-vault/skills`. |
| `apps/dashboard/scripts/yaml-page-gen.ts` | Modify | Emit source labels under `shared-vault/skills`. |
| `skills/` | Move/Delete | Move every tracked child directory to `shared-vault/skills/`; remove the root directory. |
| `shared-vault/skills/*` | Move | New home for team skill bundles. |
| `AGENTS.md`, `CODEX.md`, `CLAUDE.md`, generated client surfaces | Regenerate | Reflect shared-vault canonical roots after sync. |
| `docs/agent-topics/*.md` | Modify through source docs only | Replace repo-root skill guidance with shared/private root guidance. |
| `docs/generated/*` | Regenerate | Skill registry, manifests, ADR/RAG indexes if touched by generators. |

## Verification Commands

Use the repo-owned loop commands, not raw `pytest`, `pnpm`, or `pnpm dev`.

```bash
python skills/daemon/scripts/adaptive_loop_executor.py --run testing
python skills/daemon/scripts/adaptive_loop_executor.py --run code-quality
python skills/daemon/scripts/adaptive_loop_executor.py --run hardening
python skills/daemon/scripts/adaptive_loop_executor.py --registry
python skills/daemon/scripts/adaptive_loop_executor.py --status
```

After Task 6 moves `skills/`, the same commands must be invoked through the new shared-vault path:

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --run testing
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --run code-quality
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --run hardening
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --registry
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --status
```

If any loop command still requires the old path after Task 6, that is a migration bug.

### Task 1: Migration Guard And Inventory

**Files:**
- Create: `scripts/check_skill_root_migration.py`
- Create: `tests/test_shared_vault_skill_root_migration.py`

- [ ] **Step 1: Create the migration guard test file**

Create `tests/test_shared_vault_skill_root_migration.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_guard(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", "scripts/check_skill_root_migration.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_guard_inventory_outputs_root_skills_before_migration():
    result = run_guard("--inventory")
    assert result.returncode == 0
    assert "root_skill_dirs:" in result.stdout
    assert "shared_vault_skill_dirs:" in result.stdout


def test_guard_final_contract_fails_while_repo_root_skills_exists():
    result = run_guard("--final-contract")
    assert result.returncode != 0
    assert "repo-root skills directory still exists" in result.stdout
```

- [ ] **Step 2: Create the guard implementation**

Create `scripts/check_skill_root_migration.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_SKILLS = ROOT / "skills"
SHARED_SKILLS = ROOT / "shared-vault" / "skills"

SCAN_GLOBS = [
    "src/**/*.py",
    "src/**/*.ts",
    "src/**/*.tsx",
    "apps/dashboard/**/*.py",
    "apps/dashboard/**/*.ts",
    "apps/dashboard/**/*.tsx",
    "scripts/**/*.py",
    ".github/**/*.py",
    "config/**/*.yaml",
    "config/**/*.yml",
]

FORBIDDEN_FINAL_PATTERNS = [
    'PROJECT_ROOT / "skills"',
    "PROJECT_ROOT / 'skills'",
    'project_root / "skills"',
    "project_root / 'skills'",
    'root / "skills"',
    "root / 'skills'",
    'Path("skills")',
    "Path('skills')",
    'glob("skills/*',
    "glob('skills/*",
]

ALLOWED_FINAL_FILES = {
    "scripts/check_skill_root_migration.py",
    "tests/test_shared_vault_skill_root_migration.py",
}


def _skill_dirs(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    return sorted(child.name for child in path.iterdir() if child.is_dir() and not child.name.startswith("."))


def inventory() -> int:
    print("root_skill_dirs:")
    for name in _skill_dirs(ROOT_SKILLS):
        print(f"  - {name}")
    print("shared_vault_skill_dirs:")
    for name in _skill_dirs(SHARED_SKILLS):
        print(f"  - {name}")
    return 0


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for pattern in SCAN_GLOBS:
        files.extend(ROOT.glob(pattern))
    return sorted({path for path in files if path.is_file()})


def final_contract() -> int:
    issues: list[str] = []
    if ROOT_SKILLS.exists():
        issues.append(f"repo-root skills directory still exists: {ROOT_SKILLS.relative_to(ROOT)}")

    for path in _iter_scan_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED_FINAL_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in FORBIDDEN_FINAL_PATTERNS:
            if pattern in text:
                issues.append(f"{rel}: forbidden root-skill pattern {pattern!r}")

    if issues:
        print("skill root migration contract failed:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("skill root migration contract passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--final-contract", action="store_true")
    args = parser.parse_args()

    if args.inventory:
        return inventory()
    if args.final_contract:
        return final_contract()

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Verify the initial guard behavior**

Run:

```bash
python scripts/check_skill_root_migration.py --inventory
python scripts/check_skill_root_migration.py --final-contract
```

Expected:

- inventory prints current root skills and the existing shared-vault scaffold,
- final contract fails because `skills/` still exists.

- [ ] **Step 4: Commit the guard**

```bash
git add scripts/check_skill_root_migration.py tests/test_shared_vault_skill_root_migration.py
git commit -m "test(vault): add skill root migration guard"
```

### Task 2: Canonical Skill Root Path Helpers

**Files:**
- Modify: `src/config/paths.py`
- Modify: `tests/src/test_paths.py`

- [ ] **Step 1: Add path helper tests**

Add these tests to `tests/src/test_paths.py` near the existing shared-vault helper tests:

```python
def test_get_skills_dir_returns_shared_vault_skills_after_root_migration(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    project_root.mkdir()
    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    paths.invalidate_project_cache()

    assert paths.get_skills_dir() == project_root / "shared-vault" / "skills"


def test_managed_skill_source_dirs_omits_repo_root_skills(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    shared_skills = project_root / "shared-vault" / "skills"
    private_skills = tmp_path / "private-vault" / "skills"
    root_skills = project_root / "skills"
    for path in (shared_skills, private_skills, root_skills):
        path.mkdir(parents=True)

    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    monkeypatch.setattr(paths, "get_vault_skills_dir", lambda: private_skills)
    paths.invalidate_project_cache()

    assert paths.get_managed_skill_source_dirs(project_root) == [shared_skills, private_skills]
```

- [ ] **Step 2: Update canonical helpers**

Change `src/config/paths.py` so:

```python
def get_skills_dir() -> Path:
    """Canonical shared/team skills directory."""
    return get_shared_vault_skills_dir()
```

Update `get_adaptive_loop_skill_dirs()` to consider:

```python
for candidate in (get_shared_vault_skills_dir(root), get_configured_vault_skills_dir(root)):
```

Update `get_managed_skill_source_dirs()` to consider:

```python
candidates = [
    get_shared_vault_skills_dir(root),
    get_configured_vault_skills_dir(root),
]
```

Keep the existing live-root dedupe block for `get_vault_skills_dir()` so a configured live private vault still appears when it differs from `get_configured_vault_skills_dir(root)`.

- [ ] **Step 3: Verify path helper behavior**

Run:

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --status
```

Before Task 6 this command may fail because the daemon skill has not moved yet. If it fails with file-not-found, run the old path only until Task 6:

```bash
python skills/daemon/scripts/adaptive_loop_executor.py --status
```

Expected after Task 2: status command still runs through one of the two paths, and no path helper tests depend on `PROJECT_ROOT / "skills"` as canonical.

- [ ] **Step 4: Commit path helper changes**

```bash
git add src/config/paths.py tests/src/test_paths.py
git commit -m "feat(paths): make shared-vault skills canonical"
```

### Task 3: Runtime Discovery And Indexing Root Updates

**Files:**
- Modify: `src/plugins/skill_discovery.py`
- Modify: `src/lib/index/_indexer_helpers.py`
- Modify: `src/lib/index/_scanners_structural.py`
- Modify: `src/lib/index/_scanners_knowledge.py`
- Modify: `src/lib/index/unified_indexer.py`
- Modify: `src/lib/index/unified_search.py`

- [ ] **Step 1: Update managed-root classification**

In `src/plugins/skill_discovery.py`, change `_classify_managed_root()` to classify canonical roots by helper identity:

```python
def _classify_managed_root(skills_dir: Path) -> tuple[str, str, str | None]:
    """Return source_root, origin/source tag, and ownership override."""
    resolved_dir = skills_dir.resolve()
    shared_skills_dir = get_shared_vault_skills_dir(get_project_root()).resolve()
    private_skills_dir = get_configured_vault_skills_dir(get_project_root()).resolve()
    live_private_skills_dir = get_vault_skills_dir().resolve()

    if resolved_dir == shared_skills_dir:
        return "shared-vault", "shared-vault", None
    if resolved_dir in {private_skills_dir, live_private_skills_dir}:
        return "private-vault", "private-vault", "user"
    return "external-client", "external-client", None
```

Import `get_shared_vault_skills_dir`, `get_configured_vault_skills_dir`, and `get_vault_skills_dir` from `src.config.paths`.

- [ ] **Step 2: Update source-root priority**

In `src/plugins/skill_discovery.py`, change `_source_root_priority()` to:

```python
priorities = {
    "shared-vault": 40,
    "private-vault": 35,
    "vault": 30,
    "plugin-cache": 20,
    "external-client": 10,
}
```

- [ ] **Step 3: Remove repo-root metadata from index helpers**

In `src/lib/index/_indexer_helpers.py`, update `_skill_overlay_metadata()` so the first parent is `get_shared_vault_skills_dir(root)` and returns:

```python
{
    "vault_scope": "shared",
    "vault_root": "shared-vault",
    "promotion_state": "integrated",
    "source_root": "shared-vault",
}
```

Remove the `repo_skills = (root / "skills").resolve()` parent and its `"source_root": "repo"` metadata.

- [ ] **Step 4: Replace direct root-skill scans with managed-root scans**

For every scanner function that currently starts from `root / "skills"`, use:

```python
for skills_dir in get_managed_skill_source_dirs(root):
    if not skills_dir.is_dir():
        continue
    for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
        ...
```

Apply that pattern in:

- `src/lib/index/_scanners_structural.py`
- `src/lib/index/_scanners_knowledge.py`
- `src/lib/index/unified_search.py`

When emitting user-visible source labels, use `path.relative_to(root)` if possible; otherwise use `path.as_posix()`. Shared-vault labels should look like `shared-vault/skills/<skill>/...`.

- [ ] **Step 5: Verify discovery from old and new roots during transition**

Run before the physical move:

```bash
python - <<'PY'
from src.plugins.skill_discovery import discover_all_skills
records = discover_all_skills(tiers=(0,))
print(len(records))
print(sorted({record.source_root for record in records}))
PY
```

Expected before Task 6: managed discovery may be sparse if only the shared-vault scaffold exists, but the code must not crash.

- [ ] **Step 6: Commit discovery/index changes**

```bash
git add src/plugins/skill_discovery.py src/lib/index/_indexer_helpers.py src/lib/index/_scanners_structural.py src/lib/index/_scanners_knowledge.py src/lib/index/unified_indexer.py src/lib/index/unified_search.py
git commit -m "feat(skills): discover shared and private skill roots"
```

### Task 4: MCP And Runtime Loader Updates

**Files:**
- Modify: `config/system/mcp_servers.yaml`
- Modify: `src/mcp/augur_shared/config.py`
- Modify: `src/mcp/augur_shared/plugin_tools.py`
- Modify: `src/mcp/augur_shared/adapters/filesystem_registry.py`
- Modify: `src/mcp/augur_framework/tools/domain/plugins.py`
- Modify: `src/mcp/augur_core/tools/core/skill_lifecycle.py`
- Modify: `skills/daemon/scripts/service_healer.py`
- Modify: `skills/onboard/scripts/windows_one_click.py`
- Modify: `skills/platform-admin/scripts/setup_wizard.py`

- [ ] **Step 1: Add shared-vault to project-tier MCP PYTHONPATH**

In `config/system/mcp_servers.yaml`, update the project-tier `PYTHONPATH` values:

```yaml
PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/shared-vault:${AUGUR_ROOT}/src/mcp"
```

Keep vault-tier per-bundle entries using `${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp` unless their loader requires top-level `skills.*` imports.

- [ ] **Step 2: Update project-root landmark checks**

In `src/mcp/augur_shared/config.py`, replace checks that require `skills/` at repo root with checks for either:

```python
(root / "shared-vault" / "skills").is_dir()
```

or generic project landmarks:

```python
(root / "pyproject.toml").is_file() and (root / "shared-vault").is_dir()
```

- [ ] **Step 3: Update MCP plugin scanning**

In `src/mcp/augur_shared/plugin_tools.py` and `src/mcp/augur_shared/adapters/filesystem_registry.py`, import and use `get_managed_skill_source_dirs(project_root)` instead of `project_root / "skills"`.

When loading Python modules from a shared-vault skill bundle, inject the canonical parent:

```python
shared_vault_parent = project_root / "shared-vault"
if str(shared_vault_parent) not in sys.path:
    sys.path.insert(0, str(shared_vault_parent))
```

Do not inject `project_root / "skills"`.

- [ ] **Step 4: Retarget skill install/adopt destinations**

In `src/mcp/augur_framework/tools/domain/plugins.py` and `src/mcp/augur_core/tools/core/skill_lifecycle.py`, change install/adopt destination helpers to write to:

```python
get_shared_vault_skills_dir(project_root) / skill_name
```

Update response text from `skills/{name}/` to `shared-vault/skills/{name}/`.

- [ ] **Step 5: Update daemon and onboarding launch paths**

Update launch references that point to root skill scripts:

```python
repo_root / "skills" / "daemon" / "scripts" / "service_healer.py"
repo_root / "skills" / "daemon" / "scripts" / "unified_daemon.py"
repo_root / "skills" / "daemon" / "assets" / "plists"
```

to:

```python
repo_root / "shared-vault" / "skills" / "daemon" / "scripts" / "service_healer.py"
repo_root / "shared-vault" / "skills" / "daemon" / "scripts" / "unified_daemon.py"
repo_root / "shared-vault" / "skills" / "daemon" / "assets" / "plists"
```

- [ ] **Step 6: Verify runtime loader imports**

Run:

```bash
python - <<'PY'
from src.mcp.augur_shared.config import find_project_root
from src.mcp.augur_shared.adapters.filesystem_registry import FilesystemSkillRegistry
root = find_project_root()
print(root)
print(type(FilesystemSkillRegistry))
PY
```

Expected: imports complete without reading repo-root `skills/`.

- [ ] **Step 7: Commit MCP/runtime loader changes**

```bash
git add config/system/mcp_servers.yaml src/mcp/augur_shared/config.py src/mcp/augur_shared/plugin_tools.py src/mcp/augur_shared/adapters/filesystem_registry.py src/mcp/augur_framework/tools/domain/plugins.py src/mcp/augur_core/tools/core/skill_lifecycle.py skills/daemon/scripts/service_healer.py skills/onboard/scripts/windows_one_click.py skills/platform-admin/scripts/setup_wizard.py
git commit -m "feat(runtime): load skills from shared vault roots"
```

### Task 5: Dashboard And Generator Root Updates

**Files:**
- Modify: `apps/dashboard/lib/server/skillsLookup.ts`
- Modify: `apps/dashboard/lib/server/skillsScanning.ts`
- Modify: `apps/dashboard/scripts/mount-plugins.ts`
- Modify: `apps/dashboard/scripts/generate_registry.py`
- Modify: `apps/dashboard/scripts/rebuild-plugins.ts`
- Modify: `apps/dashboard/scripts/block-registry-gen.ts`
- Modify: `apps/dashboard/scripts/yaml-page-gen.ts`
- Modify: `apps/dashboard/lib/browse/scan-workflows.ts`
- Modify: `apps/dashboard/lib/plugin-discovery/paths.ts`
- Modify: `apps/dashboard/app/globals.css`

- [ ] **Step 1: Add a dashboard skill-root utility**

Where the dashboard server-side utilities currently compute `repoRoot / "skills"`, replace with a shared utility returning:

```ts
export function getSharedVaultSkillsRoot(repoRoot: string): string {
  return path.join(repoRoot, "shared-vault", "skills");
}
```

If the file already has a central path helper, add the function there instead of creating a duplicate.

- [ ] **Step 2: Update server skill scanning**

In `apps/dashboard/lib/server/skillsLookup.ts` and `apps/dashboard/lib/server/skillsScanning.ts`, scan:

```ts
path.join(repoRoot, "shared-vault", "skills")
```

and remove fallback scans of:

```ts
path.join(repoRoot, "skills")
```

Error text should say `shared-vault/skills/`.

- [ ] **Step 3: Update dashboard generators**

In `apps/dashboard/scripts/mount-plugins.ts`, `apps/dashboard/scripts/generate_registry.py`, `apps/dashboard/scripts/rebuild-plugins.ts`, `apps/dashboard/scripts/block-registry-gen.ts`, and `apps/dashboard/scripts/yaml-page-gen.ts`, replace canonical scans of root `skills/*` with `shared-vault/skills/*`.

Generated source labels should use `shared-vault/skills/<skill>/SKILL.md`.

- [ ] **Step 4: Update CSS content source**

In `apps/dashboard/app/globals.css`, replace:

```css
@source "../../../skills/dashboard";
```

with:

```css
@source "../../../shared-vault/skills/dashboard";
```

If there is no dashboard skill under `shared-vault/skills/dashboard`, remove the line only after confirming no generated classes depend on it.

- [ ] **Step 5: Commit dashboard/generator changes**

```bash
git add apps/dashboard
git commit -m "feat(dashboard): scan shared vault skill roots"
```

### Task 6: Physical Skill Move

**Files:**
- Move: `skills/*` to `shared-vault/skills/*`
- Delete: `skills/` root after all children move

- [ ] **Step 1: Confirm destination is scaffold-only**

Run:

```bash
find shared-vault/skills -mindepth 1 -maxdepth 1 -print | sort
```

Expected before move: `shared-vault/skills/README.md` plus no skill directory conflicts. If a directory conflict exists, compare contents before moving and stop on non-identical files.

- [ ] **Step 2: Move every root skill directory**

Run:

```bash
for skill_dir in skills/*; do
  [ -d "$skill_dir" ] || continue
  git mv "$skill_dir" "shared-vault/skills/"
done
```

- [ ] **Step 3: Remove the root directory if empty**

Run:

```bash
rmdir skills
```

Expected: succeeds. If it fails, inspect remaining files and classify them before proceeding.

- [ ] **Step 4: Verify no root skills directory remains**

Run:

```bash
test ! -e skills
python scripts/check_skill_root_migration.py --inventory
```

Expected: `test ! -e skills` exits 0 and inventory lists all team skills under `shared-vault/skills`.

- [ ] **Step 5: Verify top-level Python package imports resolve from shared-vault**

Run:

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python - <<'PY'
import skills.ai.scripts.sync_agents.constants as constants
import skills.daemon.scripts.adaptive_loop_executor as executor
print(constants.PROJECT_ROOT)
print(executor.__name__)
PY
```

Expected: imports succeed and no repo-root `skills/` path is required.

- [ ] **Step 6: Commit the physical move**

```bash
git add -A skills shared-vault/skills
git commit -m "refactor(skills): move team skills into shared vault"
```

### Task 7: Replace Remaining Root-Skill References

**Files:**
- Modify: `docs/agent-topics/ARCHITECTURE.md`
- Modify: `docs/agent-topics/SKILLS.md`
- Modify: `docs/agent-topics/WORKFLOWS.md`
- Modify: `docs/agent-topics/agent-rules.md`
- Modify: `docs/creating-skills.md`
- Modify: `.github/scripts/generate_skill_registry.py`
- Modify: `.github/scripts/validate_structure.py`
- Modify: `.github/workflows/ci-lint.yml`
- Modify any remaining files reported by the guard.

- [ ] **Step 1: Run the final contract and collect remaining references**

Run:

```bash
python scripts/check_skill_root_migration.py --final-contract
```

Expected after Task 6: fails only on textual or scanner references, not because `skills/` exists.

- [ ] **Step 2: Update instruction source docs**

Update `docs/agent-topics/agent-rules.md` and topic docs so the canonical layout says:

```text
shared-vault/skills/  # shared/team skills and capability bundles
private-vault/skills/ # personal/private skills
```

Do not edit generated `AGENTS.md`, `CODEX.md`, or `CLAUDE.md` directly.

- [ ] **Step 3: Update repository validation scripts**

In `.github/scripts/generate_skill_registry.py` and `.github/scripts/validate_structure.py`, scan `shared-vault/skills` as the team skill root. Keep client-generated directories and private-vault roots separate.

- [ ] **Step 4: Update CI lint allowlists**

In `.github/workflows/ci-lint.yml`, replace root `skills` scan paths with `shared-vault/skills` when the scan is about canonical team skills. Keep `plugins/*/skills` checks only for external plugin cache/layout validation.

- [ ] **Step 5: Re-run final contract**

Run:

```bash
python scripts/check_skill_root_migration.py --final-contract
```

Expected: `skill root migration contract passed`.

- [ ] **Step 6: Commit reference cleanup**

```bash
git add docs .github scripts src apps config
git commit -m "refactor(skills): remove repo-root skill assumptions"
```

### Task 8: Regenerate Client And Dashboard Surfaces

**Files:**
- Regenerate: `AGENTS.md`
- Regenerate: `CODEX.md`
- Regenerate: `CLAUDE.md`
- Regenerate: `.claude/commands/*`
- Regenerate: `.codex/skills/*` where tracked
- Regenerate: `apps/dashboard/config/generated/*`
- Regenerate: `apps/dashboard/lib/blocks/generated-block-registry.ts`
- Regenerate: `docs/generated/skill-registry.md`
- Regenerate: `docs/generated/skill-manifest.json`

- [ ] **Step 1: Run agent/client sync from the new path**

Run:

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python -m skills.ai.scripts.sync_agents sync agents all
```

Expected: generated files reference `shared-vault/skills` as canonical source where relevant.

- [ ] **Step 2: Regenerate dashboard registries**

Run the repo-owned generation path used by `/dev-build`. If invoking directly is required before `/dev-build` can run, run only generator scripts that do not start the dashboard server:

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python apps/dashboard/scripts/generate_registry.py
```

Then run the canonical build command:

```bash
/dev-build
```

Expected: dashboard generated registries no longer require root `skills/`.

- [ ] **Step 3: Regenerate skill indexes**

Run:

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python src/lib/index/unified_indexer.py --category skills
```

Expected: indexed skill source paths point to `shared-vault/skills` and private-vault skills, not repo-root `skills`.

- [ ] **Step 4: Commit generated surfaces**

```bash
git add AGENTS.md CODEX.md CLAUDE.md .claude .codex apps/dashboard/config/generated apps/dashboard/lib/blocks docs/generated
git commit -m "chore(generated): refresh shared vault skill surfaces"
```

### Task 9: Full Verification

**Files:**
- No planned source edits unless verification exposes blockers.

- [ ] **Step 1: Run migration guard**

```bash
python scripts/check_skill_root_migration.py --final-contract
```

Expected: pass.

- [ ] **Step 2: Verify adaptive loop registry and status from new path**

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --registry
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --status
```

Expected: both commands run and list loop state without requiring root `skills/`.

- [ ] **Step 3: Run canonical test loop**

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --run testing
```

Expected: testing loop succeeds or reports concrete failures. Fix any blockers before continuing.

- [ ] **Step 4: Run canonical quality loop**

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --run code-quality
```

Expected: quality loop succeeds or reports concrete failures. Fix any blockers before continuing.

- [ ] **Step 5: Run canonical hardening loop**

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python shared-vault/skills/daemon/scripts/adaptive_loop_executor.py --run hardening
```

Expected: hardening loop succeeds or reports concrete failures. Fix any blockers before continuing.

- [ ] **Step 6: Verify dashboard in browser**

Use `/dev-build` to rebuild/start the dashboard. Then verify these pages in a screenshot-capable browser tool:

- `/browse`
- `/adaptive`
- `/command`
- `/brain`
- `/dev`

Expected: pages load to interactive state with no chunk-load error boundary and skill cards show shared/private provenance.

- [ ] **Step 7: Commit verification fixes**

If verification required source fixes:

```bash
git add -A
git commit -m "fix(skills): close shared vault migration verification gaps"
```

If no fixes were needed, skip this commit.

### Task 10: Merge Readiness Report

**Files:**
- No source edits unless a generated report is intentionally added.

- [ ] **Step 1: Summarize final root state**

Run:

```bash
git status -sb
git log --oneline --decorate -n 12
find shared-vault/skills -mindepth 1 -maxdepth 1 -type d -print | sort
test ! -e skills
```

Expected: branch is clean, recent commits are the migration commits, shared-vault skills list includes the former root skills, and root `skills/` is absent.

- [ ] **Step 2: Report verification evidence**

Prepare the handoff with:

- migration guard result,
- adaptive loop registry/status result,
- testing/code-quality/hardening loop results,
- `/dev-build` and browser verification result,
- any remaining references intentionally left as historical docs or generated external examples.

- [ ] **Step 3: Stop before merge**

Do not push, merge, or run `/dev-merge` without explicit user approval.

## Self-Review

- Spec coverage: Phase 4 and Phase 5 acceptance criteria are covered by Tasks 1-9.
- Root directory risk: Task 6 removes `skills/`; Task 1/7/9 block it from returning.
- Runtime risk: Tasks 3-5 update Python, MCP, dashboard, and generated-surface discovery before final verification.
- Verification risk: Task 9 uses Augur loop commands and browser verification, not raw test/build shortcuts.
- Scope risk: This plan does not migrate private-vault skills or hosted enterprise behavior; those are not part of finishing repo-root skill retirement.
