# Harness Layering — Phase 1: Stack-Resolution Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the three-tier brain stack (`Global ⊏ User ⊏ Project`) at the resolution layer — a synthesized read-only Global (Augur-core) brain, an ordered `BrainStack`, and registry cardinality enforcement — without yet touching the projection pipeline.

**Architecture:** Today `resolve_active_context()` returns exactly one `ActiveBrainContext`, and the registry knows only `personal` + project brains; Global (Augur-core) is implicit. This phase adds `BrainType.GLOBAL` and a `read_only` write policy, synthesizes the Global brain from the install root, builds a `BrainStack` value object that orders the tiers general→specific, and adds a `resolve_active_stack()` resolver that reuses the existing project/personal resolution. It also adds a mechanical cardinality gate (≤1 personal, ≤1 global; projects unlimited; team left dormant) in `BrainRegistry.__post_init__`. No projection, no write-routing, no dashboard changes — those are later phases. This is the foundation every later phase consumes.

**Tech Stack:** Python 3.11+, frozen dataclasses, `pytest` (run targeted tests with `uv run pytest`), existing `src/lib/brain_*` modules. Implements ADR-781 Phase 1.

**Testing convention (Augur rules 19/29):** the TDD inner loop runs a single test node with `uv run pytest <nodeid> -v` (targeted execution is required for red/green TDD and is not "the test loop"). The closing full-suite regression gate uses `/auto-test-pytest`, never a raw full `pytest` run.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `src/lib/brain_registry_models.py` | Brain/registry value objects + validation | Add `BrainType.GLOBAL`, add `"read_only"` to valid write policies, add cardinality validation to `BrainRegistry.__post_init__` |
| `src/lib/brain_stack.py` | **NEW** — Global-brain synthesis, `BrainStack` value object, `resolve_active_stack()` | Create |
| `tests/unit/test_brain_registry_models.py` | Unit tests for models + cardinality | Add tests |
| `tests/unit/test_brain_stack.py` | **NEW** — unit tests for stack resolution | Create |

Rationale: stack resolution is a new responsibility, so it gets its own module (`brain_stack.py`) rather than swelling `brain_context.py`, which stays focused on single-active-brain resolution. `brain_stack.py` *depends on* `brain_context.py` (delegates project/personal resolution to it), preserving the existing API for all current callers.

---

## Task 1: Add `BrainType.GLOBAL` and the `read_only` write policy

**Files:**
- Modify: `src/lib/brain_registry_models.py:9-12` (BrainType enum), `src/lib/brain_registry_models.py:47` (`_VALID_WRITE_POLICIES`)
- Test: `tests/unit/test_brain_registry_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_brain_registry_models.py`:

```python
from pathlib import PurePosixPath

from src.lib.brain_registry_models import (
    Brain,
    BrainType,
    GitArrangement,
    GitConfig,
)


def test_global_brain_type_and_read_only_policy_construct() -> None:
    brain = Brain(
        id="augur-core",
        type=BrainType.GLOBAL,
        data_root=PurePosixPath("/opt/augur"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
        write_policy="read_only",
    )

    assert brain.type is BrainType.GLOBAL
    assert brain.type.value == "global"
    assert brain.write_policy == "read_only"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_brain_registry_models.py::test_global_brain_type_and_read_only_policy_construct -v`
Expected: FAIL — `AttributeError: GLOBAL` (enum member missing) or `ValueError: unknown write_policy: read_only`.

- [ ] **Step 3: Write minimal implementation**

In `src/lib/brain_registry_models.py`, add the `GLOBAL` member to the enum:

```python
class BrainType(str, Enum):
    GLOBAL = "global"
    PERSONAL = "personal"
    TEAM = "team"
    PROJECT = "project"
```

And extend the valid write-policy set:

```python
_VALID_WRITE_POLICIES = frozenset({"free", "packets_only", "read_only"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_brain_registry_models.py::test_global_brain_type_and_read_only_policy_construct -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_registry_models.py tests/unit/test_brain_registry_models.py
git commit -m "feat(brain): add GLOBAL brain type and read_only write policy (ADR-781 P1)"
```

---

## Task 2: Registry cardinality enforcement (≤1 personal, ≤1 global)

**Files:**
- Modify: `src/lib/brain_registry_models.py:98-103` (`BrainRegistry.__post_init__`)
- Test: `tests/unit/test_brain_registry_models.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_brain_registry_models.py`:

```python
import pytest

from src.lib.brain_registry_models import BrainRegistry


def _brain(brain_id: str, brain_type: BrainType) -> Brain:
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=PurePosixPath(f"/data/{brain_id}"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )


def test_registry_rejects_two_personal_brains() -> None:
    with pytest.raises(ValueError, match="at most one personal"):
        BrainRegistry(
            version=1,
            brains={
                "personal": _brain("personal", BrainType.PERSONAL),
                "personal-2": _brain("personal-2", BrainType.PERSONAL),
            },
        )


def test_registry_rejects_two_global_brains() -> None:
    with pytest.raises(ValueError, match="at most one global"):
        BrainRegistry(
            version=1,
            brains={
                "augur-core": _brain("augur-core", BrainType.GLOBAL),
                "augur-core-2": _brain("augur-core-2", BrainType.GLOBAL),
            },
        )


def test_registry_allows_one_personal_many_projects_and_team() -> None:
    registry = BrainRegistry(
        version=1,
        brains={
            "personal": _brain("personal", BrainType.PERSONAL),
            "team-core": _brain("team-core", BrainType.TEAM),
            "project-a": _brain("project-a", BrainType.PROJECT),
            "project-b": _brain("project-b", BrainType.PROJECT),
        },
    )

    assert registry.get("personal") is not None
    assert len([b for b in registry.brains.values() if b.type is BrainType.PROJECT]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_brain_registry_models.py -k "rejects_two or allows_one_personal" -v`
Expected: the two `rejects_*` tests FAIL (no `ValueError` raised); `allows_one_personal...` PASSES already.

- [ ] **Step 3: Write minimal implementation**

Replace `BrainRegistry.__post_init__` in `src/lib/brain_registry_models.py`:

```python
    def __post_init__(self) -> None:
        for key, brain in self.brains.items():
            if key != brain.id:
                raise ValueError(
                    f"registry key '{key}' does not match brain id '{brain.id}'"
                )
        self._enforce_singleton_tier(BrainType.PERSONAL, "personal")
        self._enforce_singleton_tier(BrainType.GLOBAL, "global")

    def _enforce_singleton_tier(self, brain_type: BrainType, label: str) -> None:
        matches = [b.id for b in self.brains.values() if b.type is brain_type]
        if len(matches) > 1:
            raise ValueError(
                f"registry must hold at most one {label} brain, found: {sorted(matches)}"
            )
```

> Team and project tiers are intentionally unconstrained: team is dormant (ADR-781 defers it), projects are unbounded by design.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_brain_registry_models.py -v`
Expected: PASS (all, including the existing model tests).

- [ ] **Step 5: Run the existing brain suite to confirm no regression**

Run: `uv run pytest tests/unit/test_brain_context.py tests/unit/test_brain_init.py tests/unit/test_brain_registry.py tests/unit/test_brain_registry_io.py tests/unit/test_brain_registry_bootstrap.py -v`
Expected: PASS — existing fixtures use exactly one personal (the `team-core` explicit-brain test pairs one personal with one team, which the new gate allows).

- [ ] **Step 6: Commit**

```bash
git add src/lib/brain_registry_models.py tests/unit/test_brain_registry_models.py
git commit -m "feat(brain): enforce ≤1 personal and ≤1 global brain in registry (ADR-781 P1)"
```

---

## Task 3: Synthesize the Global (Augur-core) brain

**Files:**
- Create: `src/lib/brain_stack.py`
- Test: `tests/unit/test_brain_stack.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_brain_stack.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.lib.brain_registry_models import BrainType, GitArrangement
from src.lib.brain_stack import resolve_global_brain


def test_resolve_global_brain_uses_explicit_core_root(tmp_path: Path) -> None:
    core_root = tmp_path / "augur-install"
    core_root.mkdir()

    brain = resolve_global_brain(core_root=core_root)

    assert brain.id == "augur-core"
    assert brain.type is BrainType.GLOBAL
    assert Path(brain.data_root) == core_root.resolve()
    assert brain.write_policy == "read_only"
    assert brain.git.arrangement is GitArrangement.UNTRACKED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_brain_stack.py::test_resolve_global_brain_uses_explicit_core_root -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.lib.brain_stack'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/lib/brain_stack.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.lib.brain_registry_models import (
    Brain,
    BrainType,
    GitArrangement,
    GitConfig,
)

GLOBAL_BRAIN_ID = "augur-core"


def resolve_global_brain(*, core_root: Path | None = None) -> Brain:
    """Synthesize the read-only Global (Augur-core) brain.

    The Global tier is the installed Augur platform; it is never stored in the
    registry and is never a write target (write_policy=read_only). Its data_root
    is the Augur installation root — in the Augur dev repo this coincides with
    the project-augur source (ADR-781 D10).
    """
    root = (core_root if core_root is not None else _default_core_root()).resolve()
    return Brain(
        id=GLOBAL_BRAIN_ID,
        type=BrainType.GLOBAL,
        data_root=root,
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
        write_policy="read_only",
        description="Augur core (installed platform)",
    )


def _default_core_root() -> Path:
    from src.config.paths import get_project_root

    return get_project_root()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_brain_stack.py::test_resolve_global_brain_uses_explicit_core_root -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_stack.py tests/unit/test_brain_stack.py
git commit -m "feat(brain): synthesize read-only Global (augur-core) brain (ADR-781 P1)"
```

---

## Task 4: `BrainStack` model + `resolve_active_stack()`

**Files:**
- Modify: `src/lib/brain_stack.py`
- Test: `tests/unit/test_brain_stack.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_brain_stack.py`:

```python
from src.lib.brain_manifest import (
    BrainManifest,
    ensure_brain_skeleton,
    write_brain_manifest,
)
from src.lib.brain_registry_io import save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    GitConfig,
)
from src.lib.brain_stack import BrainStack, resolve_active_stack


def _personal(path: Path) -> Brain:
    return Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=path,
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )


def _write_registry_with_personal(tmp_path: Path) -> Path:
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(version=1, brains={"personal": _personal(tmp_path / "personal")}),
        registry_path,
    )
    return registry_path


def test_stack_personal_mode_has_global_and_user_only(tmp_path: Path) -> None:
    core_root = tmp_path / "augur-install"
    core_root.mkdir()
    registry_path = _write_registry_with_personal(tmp_path)

    stack = resolve_active_stack(
        cwd=tmp_path / "outside",
        registry_path=registry_path,
        core_root=core_root,
    )

    ordered = stack.ordered()
    assert [b.type for b in ordered] == [BrainType.GLOBAL, BrainType.PERSONAL]
    assert stack.project is None
    assert stack.most_specific().type is BrainType.PERSONAL


def test_stack_project_mode_adds_project_tier(tmp_path: Path) -> None:
    core_root = tmp_path / "augur-install"
    core_root.mkdir()
    project = tmp_path / "repo"
    nested = project / "src"
    nested.mkdir(parents=True)
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
        ),
    )
    registry_path = _write_registry_with_personal(tmp_path)

    stack = resolve_active_stack(
        cwd=nested,
        registry_path=registry_path,
        core_root=core_root,
    )

    ordered = stack.ordered()
    assert [b.type for b in ordered] == [
        BrainType.GLOBAL,
        BrainType.PERSONAL,
        BrainType.PROJECT,
    ]
    assert stack.project is not None
    assert stack.project.active_brain.id == "project-repo"
    assert stack.most_specific().id == "project-repo"


def test_stack_to_header_dict_emits_tier_blocks(tmp_path: Path) -> None:
    core_root = tmp_path / "augur-install"
    core_root.mkdir()
    registry_path = _write_registry_with_personal(tmp_path)

    stack = resolve_active_stack(
        cwd=tmp_path / "outside",
        registry_path=registry_path,
        core_root=core_root,
    )
    header = stack.to_header_dict()

    assert header["augur_stack"]["global"]["id"] == "augur-core"
    assert header["augur_stack"]["user"]["id"] == "personal"
    assert "project" not in header["augur_stack"]
    assert isinstance(stack, BrainStack)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_brain_stack.py -k "stack_" -v`
Expected: FAIL — `ImportError: cannot import name 'BrainStack'` / `resolve_active_stack`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/lib/brain_stack.py` (add imports at top: `from dataclasses import dataclass`, `from src.lib.brain_context import ActiveBrainContext, resolve_active_context`, `from src.lib.brain_registry_io import load_registry`, `from src.lib.brain_registry_models import BrainRegistry`):

```python
@dataclass(frozen=True)
class BrainStack:
    global_brain: Brain
    user_brain: Brain | None
    project: ActiveBrainContext | None

    def ordered(self) -> tuple[Brain, ...]:
        """Tiers from least specific (global) to most specific (project)."""
        tiers: list[Brain] = [self.global_brain]
        if self.user_brain is not None:
            tiers.append(self.user_brain)
        if self.project is not None:
            tiers.append(self.project.active_brain)
        return tuple(tiers)

    def most_specific(self) -> Brain:
        return self.ordered()[-1]

    def to_header_dict(self) -> dict[str, object]:
        stack: dict[str, object] = {
            "global": _tier_block(self.global_brain),
        }
        if self.user_brain is not None:
            stack["user"] = _tier_block(self.user_brain)
        if self.project is not None:
            stack["project"] = _tier_block(self.project.active_brain)
        return {"augur_stack": stack, "generated_projection": True}


def resolve_active_stack(
    *,
    cwd: Path | None = None,
    registry_path: Path | None = None,
    explicit_brain: str | None = None,
    explicit_project: Path | None = None,
    core_root: Path | None = None,
) -> BrainStack:
    global_brain = resolve_global_brain(core_root=core_root)
    registry = _load_registry_if_present(registry_path)
    user_brain = _find_personal(registry) if registry is not None else None

    project_ctx: ActiveBrainContext | None = None
    try:
        ctx = resolve_active_context(
            cwd=cwd,
            registry_path=registry_path,
            explicit_brain=explicit_brain,
            explicit_project=explicit_project,
        )
    except KeyError:
        ctx = None
    if ctx is not None and ctx.active_brain.type is BrainType.PROJECT:
        project_ctx = ctx

    return BrainStack(
        global_brain=global_brain,
        user_brain=user_brain,
        project=project_ctx,
    )


def _tier_block(brain: Brain) -> dict[str, str]:
    return {
        "id": brain.id,
        "type": brain.type.value,
        "root": str(brain.data_root),
    }


def _find_personal(registry: BrainRegistry) -> Brain | None:
    for brain in registry.brains.values():
        if brain.type is BrainType.PERSONAL:
            return brain
    return None


def _load_registry_if_present(registry_path: Path | None) -> BrainRegistry | None:
    if registry_path is None or not registry_path.is_file():
        return None
    return load_registry(registry_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_brain_stack.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_stack.py tests/unit/test_brain_stack.py
git commit -m "feat(brain): add BrainStack and resolve_active_stack tier resolver (ADR-781 P1)"
```

---

## Completion Gate (Phase 1)

- [ ] **Full-suite regression via the Augur loop (NOT raw pytest):**

Run: `/auto-test-pytest`
Expected: green, with the four new/changed test files included. If the loop reports coverage gaps, report them honestly (rule 8) — do not claim complete coverage.

- [ ] **Value validation against real data (rule 34):** from the live Augur repo, resolve the stack and confirm it returns the real three tiers (Global = the Augur install root, User = the real personal brain from `~/.augur/brains.yaml`, Project = `project-augur`):

```bash
uv run python -c "
from pathlib import Path
from src.lib.brain_stack import resolve_active_stack
from src.config.paths import get_brain_registry_path
stack = resolve_active_stack(cwd=Path.cwd(), registry_path=get_brain_registry_path())
for b in stack.ordered():
    print(b.type.value, b.id, b.data_root)
print('most_specific:', stack.most_specific().id)
"
```

Expected: prints `global augur-core <install-root>`, `personal personal <vault path>`, and `project project-augur <repo>/project-brain`, with `most_specific: project-augur`. If the personal tier is missing or the project tier is wrong, that is a finding to fix, not paper over.

---

## Self-Review

**Spec coverage (ADR-781 Phase 1 = "Stack resolution (foundation)"):**
- "Refactor `resolve_active_context()` → `resolve_active_stack()` returning the ordered `[global, user, project?]`" → Task 4 (additive: `resolve_active_context` is retained and delegated to, so no caller breaks; the ordered stack is the new surface). ✔
- "keep a single-brain accessor" → `BrainStack.most_specific()` (Task 4) + the untouched `resolve_active_context`. ✔
- "Add cardinality enforcement to the registry layer" → Task 2. ✔
- Global tier as platform-managed/read-only (D3) → Tasks 1 + 3 (`BrainType.GLOBAL`, `write_policy="read_only"`). ✔
- `aug brain init` cardinality enforcement → **deferred to the Phase-1 CLI follow-up below** (the registry-level gate in Task 2 already blocks a second personal at construction time, which is the mechanical guarantee; surfacing a friendly CLI error is a thin wrapper handled when Phase 3 touches the CLI).

**Out of scope (later phases, by design):** projection/envelope changes (Phase 2), `aug` subcommand + exposure tiering (Phase 3), data-capability merges (Phase 4), dashboard manager (Phase 5). This plan deliberately does not touch `brain_projection.py`, `sync_agents/`, `cli.py`, `capability_exposure.yaml`, or `memory_store.py`.

**Placeholder scan:** none — every step has concrete code and commands.

**Type consistency:** `BrainStack.project` is `ActiveBrainContext | None`; `.ordered()` and `.most_specific()` return `Brain`; `resolve_global_brain` and `resolve_active_stack` are keyword-only and accept `core_root` for test injection consistently across Tasks 3–4. `GLOBAL_BRAIN_ID = "augur-core"` is the single source for the global id used in tests.

---

## Follow-on plans (not part of this plan)

Each later ADR-781 phase gets its own plan, written after its surface is explored to stay placeholder-free:
- **Phase 2** — projection of client-native-capable capabilities (3→2 collapse in `sync_agents`, envelope emits the full stack, effective/shadowed computation).
- **Phase 3** — Augur-only capabilities (tier-aware `aug` subcommand discovery; tier-scoped `capability_exposure.yaml` / `mcp_servers.yaml`) + the `aug brain init` friendly cardinality error.
- **Phase 4** — data-capability runtime merges (memory read-union/write-most-specific, profile overlay, federated knowledge search).
- **Phase 5** — harness manager dashboard surface.
- **Phase 6** — real-data validation across Global + personal + ≥2 project brains.
