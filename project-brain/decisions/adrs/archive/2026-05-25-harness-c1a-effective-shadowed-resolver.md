# Harness Layering — C1a: Effective/Shadowed Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the pure effective/shadowed resolver (ADR-781 §2d shared infra) — given the layered brain stack, compute per-capability `name → (winning tier/path, shadowed[])` with most-specific-wins and coincident-root dedupe — the single source of truth reused by projection (C1), `verify-harness` (C1b), and the manager UI (C4).

**Architecture:** A new pure module `src/lib/brain_effective.py` over `LayeredProjection` (C1 foundation, already built). It iterates the per-tier layers general→specific; for each capability's roots it enumerates entries (skills = subdirs containing `SKILL.md`), the most-specific tier wins each name, and earlier tiers become its `shadowed` list. Coincident physical roots (the Augur-repo D10 Global==Project case) are enumerated once (attributed to the first/general tier). No filesystem writes, no client contact — pure computation.

**Tech Stack:** Python 3.11+, frozen dataclasses, `src/lib/brain_layered_projection.py` (`LayeredProjection`, `LayeredCapabilitySource`), `src/lib/brain_stack.py`. Implements ADR-781 §2d / first slice of ADR-782 (C1). TDD inner loop `uv run pytest <nodeid>`.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `src/lib/brain_effective.py` | **NEW** — `EffectiveEntry`, `EffectiveSet`, `_compute_effective`, `compute_effective_skills`, `effective_summary` | Create |
| `tests/unit/test_brain_effective.py` | **NEW** — unit tests | Create |

---

## Task 1: `EffectiveEntry` / `EffectiveSet` + `compute_effective_skills`

**Files:** Create `src/lib/brain_effective.py`. Test: `tests/unit/test_brain_effective.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_brain_effective.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.lib.brain_context import ActiveBrainContext
from src.lib.brain_layered_projection import resolve_layered_projection
from src.lib.brain_registry_models import (
    Brain,
    BrainType,
    GitArrangement,
    GitConfig,
)
from src.lib.brain_stack import BrainStack, resolve_global_brain


def _brain(brain_id: str, brain_type: BrainType, root: Path, project: Path | None = None) -> Brain:
    git = (
        GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project)
        if brain_type is BrainType.PROJECT and project is not None
        else GitConfig(arrangement=GitArrangement.UNTRACKED)
    )
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=root,
        git=git,
        auto_activate_cwd_under=(project,) if project is not None else (),
    )


def _skill(brain_root: Path, name: str) -> None:
    d = brain_root / "capabilities" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")


def _stack(tmp_path: Path) -> BrainStack:
    core = tmp_path / "core"
    _skill(core, "shared")          # appears in global
    _skill(core, "core-only")
    vault = tmp_path / "vault"
    _skill(vault, "user-only")
    project = tmp_path / "repo"
    pbrain = project / "project-brain"
    _skill(pbrain, "shared")        # project overrides "shared"
    _skill(pbrain, "proj-only")
    return BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=_brain("personal", BrainType.PERSONAL, vault),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BrainType.PROJECT, pbrain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )


def test_compute_effective_skills_most_specific_wins_and_records_shadowed(tmp_path: Path) -> None:
    from src.lib.brain_effective import compute_effective_skills
    from src.lib.brain_registry_models import BrainType as BT

    eff = compute_effective_skills(resolve_layered_projection(_stack(tmp_path)))

    # "shared" defined in global + project -> project wins, global shadowed
    shared = eff.entries["shared"]
    assert shared.winner_tier is BT.PROJECT
    assert shared.winner.name == "shared"
    assert [tier for tier, _ in shared.shadowed] == [BT.GLOBAL]

    # tier-exclusive skills win at their own tier with no shadow
    assert eff.entries["core-only"].winner_tier is BT.GLOBAL
    assert eff.entries["core-only"].shadowed == ()
    assert eff.entries["user-only"].winner_tier is BT.PERSONAL
    assert eff.entries["proj-only"].winner_tier is BT.PROJECT

    assert set(eff.names()) == {"shared", "core-only", "user-only", "proj-only"}
    assert eff.shadowed_names() == ["shared"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_brain_effective.py::test_compute_effective_skills_most_specific_wins_and_records_shadowed -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.lib.brain_effective'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/lib/brain_effective.py`:

```python
"""Effective/shadowed resolution across the layered brain stack (ADR-781 §2d).

Pure computation over a ``LayeredProjection``: for each capability, the most
specific tier wins a given entry name and earlier tiers become its ``shadowed``
list. Coincident physical roots (the Augur-repo D10 Global==Project case) are
enumerated once, attributed to the first (most general) tier that holds them.
No filesystem writes, no client contact.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.lib.brain_layered_projection import (
    LayeredCapabilitySource,
    LayeredProjection,
)
from src.lib.brain_registry_models import BrainType


@dataclass(frozen=True)
class EffectiveEntry:
    name: str
    winner: Path
    winner_tier: BrainType
    shadowed: tuple[tuple[BrainType, Path], ...]  # (tier, path) general -> more specific


@dataclass(frozen=True)
class EffectiveSet:
    entries: dict[str, EffectiveEntry]

    def names(self) -> list[str]:
        return list(self.entries.keys())

    def shadowed_names(self) -> list[str]:
        return [name for name, e in self.entries.items() if e.shadowed]


def _is_skill_dir(path: Path) -> bool:
    return path.is_dir() and (path / "SKILL.md").is_file()


def _compute_effective(
    layers: Sequence[LayeredCapabilitySource],
    *,
    roots_of: Callable[[LayeredCapabilitySource], tuple[Path, ...]],
    is_entry: Callable[[Path], bool],
) -> EffectiveSet:
    entries: dict[str, EffectiveEntry] = {}
    seen_roots: set[Path] = set()
    for layer in layers:  # general (global) -> specific (project)
        for root in roots_of(layer):
            resolved = Path(root).resolve()
            if resolved in seen_roots:  # D10 coincident root: count once, as the general tier
                continue
            seen_roots.add(resolved)
            if not Path(root).is_dir():
                continue
            for child in sorted(Path(root).iterdir()):
                if not is_entry(child):
                    continue
                name = child.name
                prior = entries.get(name)
                shadowed = (
                    prior.shadowed + ((prior.winner_tier, prior.winner),)
                    if prior is not None
                    else ()
                )
                entries[name] = EffectiveEntry(
                    name=name,
                    winner=child,
                    winner_tier=layer.tier,
                    shadowed=shadowed,
                )
    return EffectiveSet(entries=entries)


def compute_effective_skills(layered: LayeredProjection) -> EffectiveSet:
    return _compute_effective(
        layered.layers,
        roots_of=lambda layer: layer.sources.skill_roots,
        is_entry=_is_skill_dir,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_brain_effective.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_effective.py tests/unit/test_brain_effective.py
git commit -m "feat(brain): effective/shadowed resolver for skills (ADR-781 §2d / C1a)"
```

---

## Task 2: Coincident-root dedupe (D10) test

**Files:** Test: `tests/unit/test_brain_effective.py`. (Implementation already handles it via `seen_roots`; this locks the behavior.)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_brain_effective.py`:

```python
def test_compute_effective_skills_dedupes_coincident_global_project_root(tmp_path: Path) -> None:
    from src.lib.brain_effective import compute_effective_skills
    from src.lib.brain_registry_models import BrainType as BT

    project = tmp_path / "repo"
    pbrain = project / "project-brain"
    _skill(pbrain, "shared")  # the single coincident root holds "shared"
    vault = tmp_path / "vault"
    _skill(vault, "user-only")

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=pbrain),  # Global root == project brain root
        user_brain=_brain("personal", BT.PERSONAL, vault),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BT.PROJECT, pbrain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    eff = compute_effective_skills(resolve_layered_projection(stack))

    # "shared" came from the coincident root once, attributed to the general tier (GLOBAL),
    # NOT shadowed by itself
    assert eff.entries["shared"].winner_tier is BT.GLOBAL
    assert eff.entries["shared"].shadowed == ()
    assert eff.entries["user-only"].winner_tier is BT.PERSONAL
    assert eff.shadowed_names() == []
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_brain_effective.py -v`
Expected: PASS (the `seen_roots` dedupe already implements this — this test locks it in).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_brain_effective.py
git commit -m "test(brain): lock coincident-root dedupe in effective resolver (C1a)"
```

---

## Task 3: `effective_summary(stack)` convenience + real-data gate

**Files:** Modify `src/lib/brain_effective.py`. Test: `tests/unit/test_brain_effective.py`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_brain_effective.py`:

```python
def test_effective_summary_reports_skill_counts(tmp_path: Path) -> None:
    from src.lib.brain_effective import effective_summary

    summary = effective_summary(_stack(tmp_path))

    assert summary["skills"]["effective"] == 4          # shared, core-only, user-only, proj-only
    assert summary["skills"]["shadowed"] == ["shared"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_brain_effective.py::test_effective_summary_reports_skill_counts -v`
Expected: FAIL — `ImportError: cannot import name 'effective_summary'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/lib/brain_effective.py` (add `from src.lib.brain_stack import BrainStack` and `from src.lib.brain_layered_projection import resolve_layered_projection` to the imports):

```python
def effective_summary(stack: BrainStack, *, project_root: Path | None = None) -> dict[str, dict]:
    """Compact effective/shadowed summary per capability for verify-harness / UI / CLI."""
    layered = resolve_layered_projection(stack, project_root=project_root)
    skills = compute_effective_skills(layered)
    return {
        "skills": {
            "effective": len(skills.names()),
            "shadowed": skills.shadowed_names(),
        }
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_brain_effective.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_effective.py tests/unit/test_brain_effective.py
git commit -m "feat(brain): effective_summary convenience for verify/UI/CLI (C1a)"
```

---

## Completion Gate (C1a)

- [ ] `uv run pytest tests/unit -q` green.
- [ ] **Real-data value validation (rule 34):** from the live repo, compute the effective skill set across the real stack:

```bash
uv run python -c "
from pathlib import Path
from src.lib.brain_stack import resolve_active_stack
from src.lib.brain_effective import effective_summary, compute_effective_skills
from src.lib.brain_layered_projection import resolve_layered_projection
from src.config.paths import get_brain_registry_path
stack = resolve_active_stack(cwd=Path.cwd(), registry_path=get_brain_registry_path())
print('summary:', effective_summary(stack))
eff = compute_effective_skills(resolve_layered_projection(stack))
for name in sorted(eff.names()):
    e = eff.entries[name]
    tag = f' (shadows {[t.value for t,_ in e.shadowed]})' if e.shadowed else ''
    print(f'  {name}: {e.winner_tier.value}{tag}')
"
```

Expected: the real effective set merges the 20 core/project skills (project-brain, deduped Global==Project) + the 3 personal skills (`books`, `file-manager`, `vault`) = ~23 effective names, each attributed to its winning tier, with any same-named overrides shown as shadows. If personal skills are missing or the project-brain root is double-counted, that's a finding to fix — not to paper over.

---

## Self-Review

**Spec coverage (ADR-781 §2d / ADR-782 C1 effective-shadowed):** the pure `name → (winning tier, shadowed[])` resolver with most-specific-wins + D10 dedupe is implemented (Tasks 1–2) and exposed via `effective_summary` for reuse by C1b/`verify-harness` and C4/UI (Task 3). ✔ Commands/agents/MCP effective-sets extend the same generic `_compute_effective` (different `roots_of`/`is_entry`) in a later C1 slice — out of scope here.

**Placeholder scan:** none — every step has concrete code + commands.

**Type consistency:** `EffectiveEntry(name, winner: Path, winner_tier: BrainType, shadowed: tuple[(BrainType, Path)])`; `EffectiveSet.entries: dict[str, EffectiveEntry]`, `.names()`, `.shadowed_names()`; `_compute_effective(layers, roots_of, is_entry)`; `compute_effective_skills(layered)`; `effective_summary(stack) -> {"skills": {"effective": int, "shadowed": [str]}}` — consistent across tasks.

---

## Follow-on (rest of C1, later plans)
- **C1b** — `verify-harness`: diff expected-effective (this resolver) vs what each real client received.
- **C1c** — source unification + per-call multi-tier resolution in `sync_agents` + parity check.
- **C1d** — 3→2 collapse + **gated** home-dir writes (outward-facing; explicit go required).
