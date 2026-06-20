# Harness Layering — C1d: 3→2 Collapse + Gated Home-Dir Writes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. **This slice is OUTWARD-FACING — it writes the user's real `~/.claude`/`~/.codex`/`~/.gemini`. Home writes ship behind an explicit gate, OFF by default.**

**Goal:** Project the layered skill set into clients with the 3→2 collapse — Global⊕User skills → client **HOME** (`{client}-global`), Project skills → client **REPO** (`{client}-local`) — gated so no home-dir write happens without explicit opt-in; flip only after `assert_skill_parity` passes and `verify_harness_summary` is `all_ok`.

**Architecture:** `skill_sync._sync_skill_stubs` writes skills into client dirs resolved by `_resolve_client_skill_dirs` (local + global per client). Today everything lands REPO (`{client}-local`). C1d partitions the layered effective skills by **winning tier** (from `compute_effective_skills`): Project-tier winners → `{client}-local`; Global/User-tier winners → `{client}-global` — but only when `home_sync_enabled()` is true (env `AUGUR_HOME_SYNC=1` or `config/preferences.yaml: home_sync.enabled`). Default OFF → behaves like today (REPO only), so the slice is safe to land before the user opts in. Sync-safety unchanged (header markers / managed-files; non-Augur entries untouched).

**Tech Stack:** Python 3.11+, `sync_agents/skill_sync.py`, `src/lib/brain_effective.py`, `src/lib/brain_parity.py`, `src/lib/brain_verify_harness.py`, `src/config/paths.py`. Implements ADR-781 D5 / fourth (final) slice of ADR-782 (C1). TDD inner loop `uv run pytest <nodeid>`.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `src/lib/brain_home_sync.py` | **NEW** — `home_sync_enabled()`, `partition_skills_by_target(stack)` | Create |
| `tests/unit/test_brain_home_sync.py` | **NEW** | Create |
| `project-brain/capabilities/skills/ai/scripts/sync_agents/skill_sync.py` | skill projection | Route Global/User-tier skills to `{client}-global` when gate on; Project-tier → `{client}-local` |
| `project-brain/.../sync_agents/tests/test_skill_sync_targets.py` | **NEW** | Create |

---

## Task 1: `home_sync_enabled()` gate

**Files:** Create `src/lib/brain_home_sync.py`. Test: `tests/unit/test_brain_home_sync.py`.

- [ ] **Step 1: failing test** — create `tests/unit/test_brain_home_sync.py`:

```python
from __future__ import annotations


def test_home_sync_disabled_by_default(monkeypatch):
    from src.lib import brain_home_sync
    monkeypatch.delenv("AUGUR_HOME_SYNC", raising=False)
    monkeypatch.setattr(brain_home_sync, "_pref_home_sync", lambda: None)
    assert brain_home_sync.home_sync_enabled() is False


def test_home_sync_enabled_via_env(monkeypatch):
    from src.lib import brain_home_sync
    monkeypatch.setenv("AUGUR_HOME_SYNC", "1")
    assert brain_home_sync.home_sync_enabled() is True
```

- [ ] **Step 2: Run → FAIL** (`ModuleNotFoundError`).
- [ ] **Step 3: Implement** — create `src/lib/brain_home_sync.py`:

```python
"""Gate + target partition for outward-facing home-dir projection (ADR-781 D5).

Home-dir writes (Global/User tier -> client HOME) are OFF by default. They turn
on only via env AUGUR_HOME_SYNC=1 or config/preferences.yaml home_sync.enabled.
"""

from __future__ import annotations

import os


def _pref_home_sync() -> bool | None:
    try:
        from src.config.paths import get_project_root
        import yaml

        prefs = get_project_root() / "config" / "preferences.yaml"
        if not prefs.is_file():
            return None
        data = yaml.safe_load(prefs.read_text(encoding="utf-8")) or {}
        block = data.get("home_sync") or {}
        val = block.get("enabled")
        return bool(val) if val is not None else None
    except Exception:
        return None


def home_sync_enabled() -> bool:
    env = os.environ.get("AUGUR_HOME_SYNC")
    if env is not None:
        return env.strip().lower() in {"1", "true", "yes", "on"}
    pref = _pref_home_sync()
    return bool(pref)
```

- [ ] **Step 4: Run → PASS**. **Step 5: Commit** `feat(brain): home_sync_enabled gate, OFF by default (ADR-781 D5 / C1d)`

---

## Task 2: `partition_skills_by_target(stack)` — HOME vs REPO

**Files:** Modify `src/lib/brain_home_sync.py`. Test: `tests/unit/test_brain_home_sync.py`.

- [ ] **Step 1: failing test** — append:

```python
def test_partition_skills_by_target_splits_by_winning_tier(tmp_path):
    from pathlib import Path
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_registry_models import Brain, BrainType, GitArrangement, GitConfig
    from src.lib.brain_stack import BrainStack, resolve_global_brain
    from src.lib.brain_home_sync import partition_skills_by_target

    def _skill(root, name):
        d = root / "capabilities" / "skills" / name
        d.mkdir(parents=True); (d / "SKILL.md").write_text("---\nname: %s\n---\n" % name)

    core = tmp_path / "core"; _skill(core, "core-only")
    vault = tmp_path / "vault"; _skill(vault, "user-only")
    project = tmp_path / "repo"; pbrain = project / "project-brain"; _skill(pbrain, "proj-only")
    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=Brain(id="personal", type=BrainType.PERSONAL, data_root=vault, git=GitConfig(arrangement=GitArrangement.UNTRACKED)),
        project=ActiveBrainContext(
            active_brain=Brain(id="project-repo", type=BrainType.PROJECT, data_root=pbrain, git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project), auto_activate_cwd_under=(project,)),
            attached_project=project, source="nearest-project-brain"),
    )

    home, repo = partition_skills_by_target(stack)
    assert home == {"core-only", "user-only"}   # Global + User -> HOME
    assert repo == {"proj-only"}                 # Project -> REPO
```

- [ ] **Step 2: Run → FAIL**. **Step 3: Implement** — append:

```python
def partition_skills_by_target(stack, *, project_root=None):
    """Return (home_skills, repo_skills) name-sets partitioned by winning tier.

    Global/User winners -> client HOME; Project winners -> client REPO.
    """
    from src.lib.brain_effective import compute_effective_skills
    from src.lib.brain_layered_projection import resolve_layered_projection
    from src.lib.brain_registry_models import BrainType

    eff = compute_effective_skills(resolve_layered_projection(stack, project_root=project_root))
    home: set[str] = set()
    repo: set[str] = set()
    for name, entry in eff.entries.items():
        if entry.winner_tier is BrainType.PROJECT:
            repo.add(name)
        else:
            home.add(name)
    return home, repo
```

- [ ] **Step 4: Run → PASS**. **Step 5: Commit** `feat(brain): partition_skills_by_target HOME/REPO by tier (ADR-781 D5 / C1d)`

---

## Task 3: Route skill projection to HOME/REPO in skill_sync (gated)

**Files:** Modify `sync_agents/skill_sync.py` (`_sync_skill_stubs` and its client-dir selection). Test: new `sync_agents/tests/test_skill_sync_targets.py`.

- [ ] **Step 1: failing test** — create `project-brain/capabilities/skills/ai/scripts/sync_agents/tests/test_skill_sync_targets.py` asserting: with `home_sync_enabled()` patched True and a stack whose effective set splits as in Task 2, `_target_dirs_for_skill(name, client, stack)` returns the `{client}-global` dir for a Global/User skill and `{client}-local` for a Project skill; with the gate False, all skills route to `{client}-local`. (Use `patch("...brain_home_sync.home_sync_enabled")` and a fixture stack.)

```python
import sys
from pathlib import Path
from unittest.mock import patch
scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path: sys.path.insert(0, str(scripts_dir))

def test_skill_target_dir_respects_gate_and_tier(tmp_path):
    from sync_agents import skill_sync
    client_dirs = {"claude-local": tmp_path/"repo"/".claude"/"skills", "claude-global": tmp_path/"home"/".claude"/"skills"}
    home_skills, repo_skills = {"user-only"}, {"proj-only"}
    with patch("src.lib.brain_home_sync.home_sync_enabled", return_value=True):
        assert skill_sync._skill_target_dir("user-only", "claude", client_dirs, home_skills, repo_skills) == client_dirs["claude-global"]
        assert skill_sync._skill_target_dir("proj-only", "claude", client_dirs, home_skills, repo_skills) == client_dirs["claude-local"]
    with patch("src.lib.brain_home_sync.home_sync_enabled", return_value=False):
        assert skill_sync._skill_target_dir("user-only", "claude", client_dirs, home_skills, repo_skills) == client_dirs["claude-local"]
```

- [ ] **Step 2: Run → FAIL** (`_skill_target_dir` missing).
- [ ] **Step 3: Implement** — add `_skill_target_dir(name, client, client_dirs, home_skills, repo_skills)` in `skill_sync.py`: when `home_sync_enabled()` and `name in home_skills`, return `client_dirs[f"{client}-global"]`; else `client_dirs[f"{client}-local"]`. Then call it from `_sync_skill_stubs` where it currently picks the per-client dir (replacing the unconditional local-dir write). Preserve the existing header-marker write + managed-files cleanup (sync-safety).
- [ ] **Step 4: Run → PASS** + `uv run pytest tests/unit "project-brain/capabilities/skills/ai/scripts/sync_agents/tests/" -q`.
- [ ] **Step 5: Commit** `feat(sync): gated HOME/REPO skill projection by tier (ADR-781 D5 / C1d)`

---

## Completion Gate (C1d)

- [ ] `uv run pytest tests/unit "project-brain/capabilities/skills/ai/scripts/sync_agents/tests/" -q` green.
- [ ] **Gate-OFF safety (default):** with `AUGUR_HOME_SYNC` unset, run `sync skills` and confirm **no writes under `~/.claude`/`~/.codex`/`~/.gemini`** (compare `find ~/.claude/skills -newer <marker>` before/after = empty); behavior identical to pre-C1d.
- [ ] **Gate-ON real-data (rule 34, explicit opt-in only):** ONLY after the user explicitly opts in, `AUGUR_HOME_SYNC=1 sync skills`, then run `verify_harness_summary` and assert `all_ok` (Global/User skills now in `{client}-global`, Project in `{client}-local`); confirm parity (`assert_skill_parity`) held before the flip and non-Augur entries in those home dirs are untouched. Report the exact home paths written.

---

## Self-Review
**Spec coverage (ADR-782 C1d / ADR-781 D5):** 3→2 collapse by winning tier (Tasks 2–3), gated home writes OFF-by-default (Task 1), parity-before / verify-after gates (Completion). ✔ **Placeholder scan:** none (Task 3 references `_sync_skill_stubs` call site — the implementer wires `_skill_target_dir` into the existing per-client loop). **Type consistency:** `home_sync_enabled()->bool`; `partition_skills_by_target(stack)->(set,set)`; `_skill_target_dir(name,client,client_dirs,home,repo)->Path`. **Outward-facing:** home writes are gated; default path writes nothing new.

## Follow-on
C1 complete after C1d. Next: C2 (CLI/MCP tiering). Commands/subagents/MCP projection extend the same HOME/REPO partition.
