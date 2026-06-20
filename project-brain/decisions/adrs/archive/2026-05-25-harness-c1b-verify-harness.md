# Harness Layering — C1b: verify-harness Correctness Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the `verify-harness` correctness gate (ADR-781 §2a) — diff the C1a effective skill set against what each real AI client actually has projected, reporting per-client `missing` skills — so every later child (C1c/C1d, C5) can prove no client gets an incomplete harness.

**Architecture:** A new pure module `src/lib/brain_verify_harness.py` over C1a's `compute_effective_skills` (the expected set) and `get_client_skill_dirs()` (what each client received). For each client it enumerates the projected skill subdir names across that client's `{client}-local` + `{client}-global` dirs and diffs against the effective names. `missing = expected − received` is the gap the projection must close. No writes, no client mutation — read-only verification. Run against today's (pre-layered) projection it honestly reports the current gap; run after C1c/C1d it proves the gap closed.

**Tech Stack:** Python 3.11+, frozen dataclasses, `src/lib/brain_effective.py` (`compute_effective_skills`), `src/lib/brain_layered_projection.py` (`resolve_layered_projection`), `src/lib/brain_stack.py`, `src/config/paths.py` (`get_client_skill_dirs`). Implements ADR-781 §2a / second slice of ADR-782 (C1). TDD inner loop `uv run pytest <nodeid>`.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `src/lib/brain_verify_harness.py` | **NEW** — `ClientHarnessReport`, `client_received_skills`, `verify_harness_skills`, `verify_harness_summary` | Create |
| `tests/unit/test_brain_verify_harness.py` | **NEW** — unit tests | Create |

> Scope note: this slice covers **skills** for the subdir-clients (claude/codex/gemini), the capability C1a's resolver already models. Commands/subagents/MCP verification extend the same shape (different received-enumeration) in a later slice. "Stale" detection (Augur-managed but no longer effective) needs Augur-managed-marker detection and is deferred; this slice does the **missing** check, the core "no incomplete harness" gate.

---

## Task 1: `ClientHarnessReport` + `client_received_skills`

**Files:** Create `src/lib/brain_verify_harness.py`. Test: `tests/unit/test_brain_verify_harness.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_brain_verify_harness.py`:

```python
from __future__ import annotations

from pathlib import Path


def _make_client_skill(dirpath: Path, *names: str) -> None:
    for name in names:
        (dirpath / name).mkdir(parents=True, exist_ok=True)


def test_client_received_skills_unions_local_and_global_subdirs(tmp_path: Path) -> None:
    from src.lib.brain_verify_harness import client_received_skills

    client_dirs = {
        "claude-local": tmp_path / "repo" / ".claude" / "skills",
        "claude-global": tmp_path / "home" / ".claude" / "skills",
        "codex-local": tmp_path / "repo" / ".codex" / "skills",
    }
    _make_client_skill(client_dirs["claude-local"], "ai", "proj-skill")
    _make_client_skill(client_dirs["claude-global"], "ai", "books")  # "ai" overlaps -> set dedupes
    _make_client_skill(client_dirs["codex-local"], "ai")

    received = client_received_skills("claude", client_dirs=client_dirs)

    assert received == {"ai", "proj-skill", "books"}  # claude local+global only; codex ignored


def test_client_received_skills_empty_when_no_dirs(tmp_path: Path) -> None:
    from src.lib.brain_verify_harness import client_received_skills

    received = client_received_skills(
        "gemini",
        client_dirs={"gemini-local": tmp_path / "nope" / ".gemini" / "skills"},
    )
    assert received == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_brain_verify_harness.py -k client_received -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.lib.brain_verify_harness'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/lib/brain_verify_harness.py`:

```python
"""verify-harness: cross-client correctness gate (ADR-781 §2a).

Read-only verification that each AI client actually received the effective
capability set the layered stack promises. ``missing = expected - received`` is
the gap the projection (C1c/C1d) must close. No writes, no client mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClientHarnessReport:
    client: str
    expected: tuple[str, ...]
    received: tuple[str, ...]
    missing: tuple[str, ...]

    def ok(self) -> bool:
        return not self.missing


def client_received_skills(client: str, *, client_dirs: dict[str, Path]) -> set[str]:
    """Skill names a client has projected, unioned across its local + global dirs.

    A projected skill is a subdirectory of the client's skill dir (subdir-clients:
    claude/codex/gemini/opencode). Only ``{client}-local`` and ``{client}-global``
    are considered (vendor dirs like ``codex-global-superpowers`` are excluded).
    """
    names: set[str] = set()
    for tag in (f"{client}-local", f"{client}-global"):
        path = client_dirs.get(tag)
        if path is None or not Path(path).is_dir():
            continue
        names.update(child.name for child in Path(path).iterdir() if child.is_dir())
    return names
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_brain_verify_harness.py -k client_received -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_verify_harness.py tests/unit/test_brain_verify_harness.py
git commit -m "feat(brain): client_received_skills for verify-harness (ADR-781 §2a / C1b)"
```

---

## Task 2: `verify_harness_skills` — per-client expected-vs-received diff

**Files:** Modify `src/lib/brain_verify_harness.py`. Test: `tests/unit/test_brain_verify_harness.py`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_brain_verify_harness.py`:

```python
from src.lib.brain_context import ActiveBrainContext
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


def _src_skill(brain_root: Path, name: str) -> None:
    d = brain_root / "capabilities" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")


def _stack(tmp_path: Path) -> BrainStack:
    core = tmp_path / "core"
    _src_skill(core, "ai")
    vault = tmp_path / "vault"
    _src_skill(vault, "books")
    project = tmp_path / "repo"
    pbrain = project / "project-brain"
    _src_skill(pbrain, "proj-skill")
    return BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=_brain("personal", BrainType.PERSONAL, vault),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BrainType.PROJECT, pbrain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )


def test_verify_harness_skills_flags_missing_per_client(tmp_path: Path) -> None:
    from src.lib.brain_verify_harness import verify_harness_skills

    # claude has ai + proj-skill but NOT books (the personal skill not projected yet)
    claude_local = tmp_path / "repo" / ".claude" / "skills"
    _make_client_skill(claude_local, "ai", "proj-skill")
    # codex has all three
    codex_local = tmp_path / "repo" / ".codex" / "skills"
    _make_client_skill(codex_local, "ai", "books", "proj-skill")
    client_dirs = {"claude-local": claude_local, "codex-local": codex_local}

    reports = verify_harness_skills(
        _stack(tmp_path), clients=("claude", "codex"), client_dirs=client_dirs
    )
    by_client = {r.client: r for r in reports}

    assert set(by_client["claude"].expected) == {"ai", "books", "proj-skill"}
    assert by_client["claude"].missing == ("books",)
    assert by_client["claude"].ok() is False
    assert by_client["codex"].missing == ()
    assert by_client["codex"].ok() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_brain_verify_harness.py::test_verify_harness_skills_flags_missing_per_client -v`
Expected: FAIL — `ImportError: cannot import name 'verify_harness_skills'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/lib/brain_verify_harness.py` (add imports at top: `from collections.abc import Sequence`, `from src.lib.brain_effective import compute_effective_skills`, `from src.lib.brain_layered_projection import resolve_layered_projection`, `from src.lib.brain_stack import BrainStack`):

```python
def verify_harness_skills(
    stack: BrainStack,
    *,
    clients: Sequence[str] = ("claude", "codex", "gemini"),
    client_dirs: dict[str, Path] | None = None,
    project_root: Path | None = None,
) -> list[ClientHarnessReport]:
    """Diff the effective skill set against what each client received."""
    if client_dirs is None:
        from src.config.paths import get_client_skill_dirs

        client_dirs = get_client_skill_dirs()
    effective = set(compute_effective_skills(resolve_layered_projection(stack, project_root=project_root)).names())
    expected = tuple(sorted(effective))
    reports: list[ClientHarnessReport] = []
    for client in clients:
        received = client_received_skills(client, client_dirs=client_dirs)
        missing = tuple(sorted(effective - received))
        reports.append(
            ClientHarnessReport(
                client=client,
                expected=expected,
                received=tuple(sorted(received)),
                missing=missing,
            )
        )
    return reports
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_brain_verify_harness.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_verify_harness.py tests/unit/test_brain_verify_harness.py
git commit -m "feat(brain): verify_harness_skills per-client missing diff (ADR-781 §2a / C1b)"
```

---

## Task 3: `verify_harness_summary` convenience + real-data gate

**Files:** Modify `src/lib/brain_verify_harness.py`. Test: `tests/unit/test_brain_verify_harness.py`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_brain_verify_harness.py`:

```python
def test_verify_harness_summary_reports_ok_and_missing(tmp_path: Path) -> None:
    from src.lib.brain_verify_harness import verify_harness_summary

    claude_local = tmp_path / "repo" / ".claude" / "skills"
    _make_client_skill(claude_local, "ai", "proj-skill")  # missing books
    client_dirs = {"claude-local": claude_local}

    summary = verify_harness_summary(
        _stack(tmp_path), clients=("claude",), client_dirs=client_dirs
    )

    assert summary["claude"]["ok"] is False
    assert summary["claude"]["missing"] == ["books"]
    assert summary["all_ok"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_brain_verify_harness.py::test_verify_harness_summary_reports_ok_and_missing -v`
Expected: FAIL — `ImportError: cannot import name 'verify_harness_summary'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/lib/brain_verify_harness.py`:

```python
def verify_harness_summary(
    stack: BrainStack,
    *,
    clients: Sequence[str] = ("claude", "codex", "gemini"),
    client_dirs: dict[str, Path] | None = None,
    project_root: Path | None = None,
) -> dict:
    """Compact per-client ok/missing summary for the gate (C1c/C1d, C5, CLI)."""
    reports = verify_harness_skills(
        stack, clients=clients, client_dirs=client_dirs, project_root=project_root
    )
    summary: dict = {
        r.client: {"ok": r.ok(), "missing": list(r.missing)} for r in reports
    }
    summary["all_ok"] = all(r.ok() for r in reports)
    return summary
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_brain_verify_harness.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_verify_harness.py tests/unit/test_brain_verify_harness.py
git commit -m "feat(brain): verify_harness_summary gate convenience (ADR-781 §2a / C1b)"
```

---

## Completion Gate (C1b)

- [ ] `uv run pytest tests/unit -q` green.
- [ ] **Real-data baseline (rule 34):** run the gate against the real stack + real client dirs to capture the *honest current gap* (the layered projection isn't built yet, so this reveals which effective skills each real client is still missing — the baseline C1c/C1d must drive to zero):

```bash
uv run python -c "
from pathlib import Path
from src.lib.brain_stack import resolve_active_stack
from src.lib.brain_verify_harness import verify_harness_summary
from src.config.paths import get_brain_registry_path
stack = resolve_active_stack(cwd=Path.cwd(), registry_path=get_brain_registry_path())
import json
print(json.dumps(verify_harness_summary(stack), indent=2))
"
```

Expected: a per-client report. Interpret honestly — `all_ok: true` means the current projection already covers the effective set for those clients; `missing: [...]` names the real gap (likely the personal skills `books`/`file-manager`/`vault` if the client dirs don't carry them yet). Either way it is the truthful baseline; do NOT tweak the resolver to force green — the gap is C1c/C1d's job to close.

---

## Self-Review

**Spec coverage (ADR-781 §2a / ADR-782 C1 verify-harness):** the read-only `verify-harness` gate diffing expected-effective (C1a) vs per-client received, with `missing` per client and an `all_ok` rollup, is implemented (Tasks 1–3) and exposed via `verify_harness_summary` for reuse by C1c/C1d and C5. ✔ Commands/subagents/MCP verification + "stale" (Augur-managed-but-not-effective) detection extend the same shape later — out of scope here.

**Placeholder scan:** none — every step has concrete code + commands.

**Type consistency:** `ClientHarnessReport(client, expected, received, missing: tuple[str,...])` + `.ok()`; `client_received_skills(client, *, client_dirs) -> set[str]`; `verify_harness_skills(stack, *, clients, client_dirs, project_root) -> list[ClientHarnessReport]`; `verify_harness_summary(...) -> {client: {ok, missing}, all_ok}` — consistent across tasks and with C1a's `compute_effective_skills(...).names()`.

---

## Follow-on (rest of C1)
- **C1c** — source unification + per-call multi-tier resolution in `sync_agents` + parity check; drives the C1b `missing` set toward empty.
- **C1d** — 3→2 collapse + **gated** home-dir writes (outward-facing; explicit go required); verify-harness must be `all_ok` after.
