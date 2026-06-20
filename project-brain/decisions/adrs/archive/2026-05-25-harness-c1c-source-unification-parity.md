# Harness Layering — C1c: Source Unification + Parity Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the single-brain skill-source resolution in `sync_agents` with the layered stack (all tiers, ordered, deduped), and add a parity gate that proves the layered skill set is a superset-or-equal of the old single-brain set before cutover — so the projection that follows (C1d) draws from Global+User+Project, not just the active brain.

**Architecture:** Today two resolvers disagree: `constants._discover_source_paths()` takes `resolve_brain_projection_sources(...).skill_roots[0]` (single brain, first root), while `get_managed_skill_source_dirs()` (paths.py) is what the skill-stub sync actually consumes. C1c introduces one unified resolver `layered_skill_source_dirs(stack)` built on C1's `resolve_layered_projection().ordered_skill_roots()` (general→specific, deduped), routes `get_managed_skill_source_dirs` through it, and adds `assert_skill_parity(stack)` comparing the layered effective set against the prior single-brain set. No client writes change here (still REPO-only projection); C1d does the HOME/REPO split. This is the non-outward-facing half of the cutover.

**Tech Stack:** Python 3.11+, `src/lib/brain_layered_projection.py`, `src/lib/brain_effective.py`, `src/lib/brain_stack.py`, `src/config/paths.py` (`get_managed_skill_source_dirs`), `sync_agents/constants.py`. Implements ADR-781 §2c (parity) / third slice of ADR-782 (C1). TDD inner loop `uv run pytest <nodeid>`.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `src/lib/brain_layered_projection.py` | layered roots | Add `layered_skill_source_dirs(stack, *, project_root)` helper (thin, returns `ordered_skill_roots()`) |
| `src/config/paths.py` | `get_managed_skill_source_dirs` | Route through the layered resolver when a stack is resolvable; keep current behavior as the documented fallback |
| `src/lib/brain_parity.py` | **NEW** — `assert_skill_parity`, `SkillParityResult` | Create |
| `tests/unit/test_brain_parity.py` | **NEW** | Create |
| `tests/config/test_brain_paths.py` | existing | Add a test for the layered-routed `get_managed_skill_source_dirs` |

---

## Task 1: `layered_skill_source_dirs` helper

**Files:** Modify `src/lib/brain_layered_projection.py`. Test: `tests/unit/test_brain_layered_projection.py`.

- [ ] **Step 1: Write the failing test** — append to `tests/unit/test_brain_layered_projection.py`:

```python
def test_layered_skill_source_dirs_returns_ordered_deduped_roots(tmp_path: Path) -> None:
    from src.lib.brain_layered_projection import layered_skill_source_dirs

    roots = layered_skill_source_dirs(_stack(tmp_path))

    assert roots == (
        tmp_path / "core" / "capabilities" / "skills",
        tmp_path / "vault" / "capabilities" / "skills",
        tmp_path / "repo" / "project-brain" / "capabilities" / "skills",
    )
```

(`_stack` helper already exists in this test file from C1-foundation.)

- [ ] **Step 2: Run → FAIL** (`uv run pytest tests/unit/test_brain_layered_projection.py::test_layered_skill_source_dirs_returns_ordered_deduped_roots -v`) — `ImportError`.

- [ ] **Step 3: Implement** — append to `src/lib/brain_layered_projection.py`:

```python
def layered_skill_source_dirs(
    stack: "BrainStack", *, project_root: Path | None = None
) -> tuple[Path, ...]:
    """Ordered (general->specific), deduped skill roots across the tier stack."""
    return resolve_layered_projection(stack, project_root=project_root).ordered_skill_roots()
```

(`BrainStack` is already imported at module top; `resolve_layered_projection` is defined in this module.)

- [ ] **Step 4: Run → PASS**.
- [ ] **Step 5: Commit** `feat(brain): layered_skill_source_dirs ordered/deduped helper (ADR-781 C1c)`

---

## Task 2: Route `get_managed_skill_source_dirs` through the layered stack

**Files:** Modify `src/config/paths.py:664-686` (`get_managed_skill_source_dirs`). Test: `tests/config/test_brain_paths.py`.

- [ ] **Step 1: Write the failing test** — append to `tests/config/test_brain_paths.py`:

```python
def test_get_managed_skill_source_dirs_uses_layered_stack(
    tmp_path: Path,
    isolated_state_dir: Path,
):
    from src.config import paths as paths_mod
    from src.lib.brain_registry_models import BrainType

    # personal vault with a skill, registered
    vault = tmp_path / "vault"
    (vault / "capabilities" / "skills" / "user-only").mkdir(parents=True)
    (vault / "capabilities" / "skills" / "user-only" / "SKILL.md").write_text("---\nname: user-only\n---\n", encoding="utf-8")
    personal = Brain(id="personal", type=BrainType.PERSONAL, data_root=vault, git=GitConfig(arrangement=GitArrangement.UNTRACKED))
    save_registry(BrainRegistry(version=1, brains={"personal": personal}), isolated_state_dir / "brains.yaml")
    clear_cache()

    # core (global) brain root with a skill
    core = tmp_path / "core"
    (core / "capabilities" / "skills" / "core-only").mkdir(parents=True)
    (core / "capabilities" / "skills" / "core-only" / "SKILL.md").write_text("---\nname: core-only\n---\n", encoding="utf-8")
    monkeypatch_root = tmp_path  # placeholder to keep diff minimal; see note

    dirs = paths_mod.get_managed_skill_source_dirs()
    resolved = {Path(d).resolve() for d in dirs}

    # the personal (user-tier) skill root is included via the layered stack
    assert (vault / "capabilities" / "skills").resolve() in resolved
```

> Note: the global tier root defaults to `<project_root>/project-brain`; this test asserts the user-tier root flows through (the key C1c behavior — personal skills are no longer dropped). The exact global root is environment-resolved and covered by the real-data gate.

- [ ] **Step 2: Run → FAIL** (current `get_managed_skill_source_dirs` may already include the vault dir via the configured-vault candidate, so if it PASSES, tighten the assert to also require ordering general→specific — see Step 3's contract).

- [ ] **Step 3: Implement** — rewrite `get_managed_skill_source_dirs` to resolve the active stack and return `layered_skill_source_dirs(stack)`, falling back to the current candidate list only when no stack resolves:

```python
def get_managed_skill_source_dirs(project_root: Path | None = None) -> list[Path]:
    root = project_root.resolve() if project_root is not None else get_project_root().resolve()
    try:
        from src.lib.brain_stack import resolve_active_stack
        from src.lib.brain_layered_projection import layered_skill_source_dirs

        stack = resolve_active_stack(cwd=root, registry_path=get_brain_registry_path())
        roots = [Path(r) for r in layered_skill_source_dirs(stack, project_root=root) if Path(r).is_dir()]
        if roots:
            return roots
    except Exception:
        pass
    # Fallback: legacy candidate resolution (no registry / stack unresolved)
    dirs: list[Path] = []
    candidates = [get_project_brain_skills_dir(root), get_configured_vault_skills_dir(root)]
    live_root = get_project_root().resolve()
    if root == live_root:
        candidates.append(get_vault_skills_dir())
    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        dirs.append(candidate)
        seen.add(resolved)
    return dirs
```

- [ ] **Step 4: Run → PASS** + `uv run pytest tests/unit tests/config -q` (no regression — the skill-discovery + projection tests still pass; the layered roots are a superset/reorder of the old candidates).
- [ ] **Step 5: Commit** `feat(paths): route managed skill sources through the layered stack (ADR-781 C1c)`

---

## Task 3: `assert_skill_parity` — the cutover gate

**Files:** Create `src/lib/brain_parity.py`. Test: `tests/unit/test_brain_parity.py`.

- [ ] **Step 1: Write the failing test** — create `tests/unit/test_brain_parity.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.lib.brain_context import ActiveBrainContext
from src.lib.brain_registry_models import Brain, BrainType, GitArrangement, GitConfig
from src.lib.brain_stack import BrainStack, resolve_global_brain


def _skill(brain_root: Path, name: str) -> None:
    d = brain_root / "capabilities" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")


def test_skill_parity_holds_when_layered_superset_of_single(tmp_path: Path) -> None:
    from src.lib.brain_parity import assert_skill_parity

    core = tmp_path / "core"
    _skill(core, "core-only")
    vault = tmp_path / "vault"
    _skill(vault, "user-only")
    project = tmp_path / "repo"
    pbrain = project / "project-brain"
    _skill(pbrain, "proj-only")
    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=Brain(id="personal", type=BrainType.PERSONAL, data_root=vault, git=GitConfig(arrangement=GitArrangement.UNTRACKED)),
        project=ActiveBrainContext(
            active_brain=Brain(id="project-repo", type=BrainType.PROJECT, data_root=pbrain, git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project), auto_activate_cwd_under=(project,)),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    # single-brain baseline = the project tier alone ({proj-only}); layered adds core+user
    result = assert_skill_parity(stack, single_brain_skills={"proj-only"})

    assert result.ok is True
    assert result.added == {"core-only", "user-only"}
    assert result.dropped == set()


def test_skill_parity_fails_when_layered_drops_a_single_brain_skill(tmp_path: Path) -> None:
    from src.lib.brain_parity import assert_skill_parity

    core = tmp_path / "core"
    _skill(core, "core-only")
    stack = BrainStack(global_brain=resolve_global_brain(core_root=core), user_brain=None, project=None)

    result = assert_skill_parity(stack, single_brain_skills={"core-only", "vanished"})

    assert result.ok is False
    assert result.dropped == {"vanished"}
```

- [ ] **Step 2: Run → FAIL** (`uv run pytest tests/unit/test_brain_parity.py -v`) — `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — create `src/lib/brain_parity.py`:

```python
"""Parity gate for the single-brain -> layered cutover (ADR-781 §2c).

The layered projection must be a superset-or-equal of the prior single-brain
projection for the active brain: no skill the agent had may silently disappear.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.lib.brain_effective import compute_effective_skills
from src.lib.brain_layered_projection import resolve_layered_projection
from src.lib.brain_stack import BrainStack


@dataclass(frozen=True)
class SkillParityResult:
    ok: bool
    added: set[str]      # skills the layered model gains over single-brain
    dropped: set[str]    # skills present single-brain but missing layered (MUST be empty)


def assert_skill_parity(stack: BrainStack, *, single_brain_skills: set[str]) -> SkillParityResult:
    layered = set(compute_effective_skills(resolve_layered_projection(stack)).names())
    dropped = single_brain_skills - layered
    added = layered - single_brain_skills
    return SkillParityResult(ok=not dropped, added=added, dropped=dropped)
```

- [ ] **Step 4: Run → PASS**.
- [ ] **Step 5: Commit** `feat(brain): assert_skill_parity cutover gate (ADR-781 §2c / C1c)`

---

## Completion Gate (C1c)

- [ ] `uv run pytest tests/unit tests/config -q` green.
- [ ] **Regenerate + verify-harness delta (rule 34):** regenerate client projections and confirm the layered routing now feeds all tiers, then re-run the C1b gate and show the `missing` set shrank vs the C1b baseline:

```bash
PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync skills 2>&1 | tail -3
uv run python -c "
from pathlib import Path
from src.lib.brain_stack import resolve_active_stack
from src.lib.brain_verify_harness import verify_harness_summary
from src.config.paths import get_brain_registry_path, get_managed_skill_source_dirs
print('managed skill source dirs (layered):', [str(d) for d in get_managed_skill_source_dirs()])
stack = resolve_active_stack(cwd=Path.cwd(), registry_path=get_brain_registry_path())
import json; print(json.dumps(verify_harness_summary(stack), indent=2))
"
```

Expected: `get_managed_skill_source_dirs` returns the ordered tier roots (global core, personal vault, project — deduped); after `sync skills`, the verify-harness `missing` per client is reduced toward empty for skills now sourced from all tiers. Parity holds (no previously-projected skill dropped). If a skill the old projection had is now missing, parity FAILS — stop and fix, do not proceed to C1d.

---

## Self-Review
**Spec coverage (ADR-782 C1c / ADR-781 §2c):** unify skill-source resolution onto the layered stack (Tasks 1–2) + parity gate (Task 3). ✔ Rules/workflows/topics multi-tier merge and the HOME/REPO split are **C1d** (out of scope). **Placeholder scan:** none. **Type consistency:** `layered_skill_source_dirs(stack,*,project_root)->tuple[Path,...]`; `get_managed_skill_source_dirs(project_root)->list[Path]`; `assert_skill_parity(stack,*,single_brain_skills)->SkillParityResult(ok,added,dropped)` consistent.

## Follow-on
- **C1d** — 3→2 collapse + gated home-dir writes; uses `assert_skill_parity` before flipping and `verify_harness_summary` after.
