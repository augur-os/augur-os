# Harness Layering — C5: Migration Verification & Closeout Implementation Plan

> **For agentic workers:** superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`). **Prerequisite: C1–C4 landed.** Implements ADR-786.

**Goal:** One end-to-end, real-data, real-client run that proves the whole harness-layering family landed correctly — no data loss, no orphaned references, every client × tier correct, parity held, cross-client memory round-trips — and emits a closeout report. The family is "landed" only when this is green.

**Architecture:** C5 assembles the per-child gates (it builds almost no new logic): the migration count-check harness, `verify_harness_summary` (C1b), `assert_skill_parity` (C1c), the C3 memory round-trip, and a family-wide rule-23 reference scan. `verify_family_closeout(stack, clients)` runs them all and returns a structured report with `all_ok`; a thin CLI/MCP entry prints it. The closeout names exact clients/tiers/paths checked and any remaining empty/error/stale state (rules 31/34).

**Tech Stack:** Python 3.11+, `src/lib/brain_verify_harness.py`, `src/lib/brain_parity.py`, `src/lib/brain_effective.py`, `src/lib/brain_memory_tiers.py`, `ripgrep` for the reference scan. Implements ADR-786. TDD inner loop `uv run pytest <nodeid>`.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `src/lib/brain_closeout.py` | **NEW** — `verify_family_closeout`, `CloseoutReport` | Create |
| `tests/unit/test_brain_closeout.py` | **NEW** | Create |
| `project-brain/capabilities/skills/platform-admin/scripts/harness_closeout.py` | **NEW** — thin CLI wrapper printing the report | Create |

---

## Task 1: `CloseoutReport` + `verify_family_closeout`

**Files:** Create `src/lib/brain_closeout.py`. Test: `tests/unit/test_brain_closeout.py`.

- [ ] **Step 1: failing test** — `tests/unit/test_brain_closeout.py`: with a stack where every client has the full effective set (verify-harness all_ok), parity holds, and no orphaned refs, `verify_family_closeout(...)` returns `report.all_ok is True` and per-section results; with one client missing a skill, `all_ok is False` and the `harness` section names the gap.

```python
def test_closeout_green_when_all_gates_pass(tmp_path):
    from src.lib.brain_closeout import verify_family_closeout
    # build a stack + client_dirs that satisfy verify-harness; single_brain baseline subset of layered
    report = verify_family_closeout(stack, clients=("claude",), client_dirs=client_dirs,
                                    single_brain_skills=set(), orphan_refs=[])
    assert report.all_ok is True
    assert report.sections["harness"]["all_ok"] is True
    assert report.sections["parity"]["ok"] is True

def test_closeout_fails_on_missing_skill(tmp_path):
    from src.lib.brain_closeout import verify_family_closeout
    report = verify_family_closeout(stack, clients=("claude",), client_dirs=client_dirs_missing,
                                    single_brain_skills=set(), orphan_refs=[])
    assert report.all_ok is False
    assert report.sections["harness"]["claude"]["ok"] is False
```

- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement** — create `src/lib/brain_closeout.py`:

```python
"""Whole-family verification closeout for harness layering (ADR-786)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.lib.brain_parity import assert_skill_parity
from src.lib.brain_stack import BrainStack
from src.lib.brain_verify_harness import verify_harness_summary


@dataclass(frozen=True)
class CloseoutReport:
    all_ok: bool
    sections: dict = field(default_factory=dict)


def verify_family_closeout(
    stack: BrainStack,
    *,
    clients,
    client_dirs: dict[str, Path] | None = None,
    single_brain_skills: set[str],
    orphan_refs: list[str],
) -> CloseoutReport:
    harness = verify_harness_summary(stack, clients=clients, client_dirs=client_dirs)
    parity = assert_skill_parity(stack, single_brain_skills=single_brain_skills)
    sections = {
        "harness": harness,
        "parity": {"ok": parity.ok, "dropped": sorted(parity.dropped)},
        "orphan_refs": {"ok": not orphan_refs, "refs": list(orphan_refs)},
    }
    all_ok = harness["all_ok"] and parity.ok and not orphan_refs
    return CloseoutReport(all_ok=all_ok, sections=sections)
```

- [ ] **Step 4: Run → PASS**. **Step 5: Commit** `feat(brain): verify_family_closeout assembles family gates (ADR-786 C5)`

---

## Task 2: Family-wide rule-23 reference scan (orphan refs)

**Files:** Modify `src/lib/brain_closeout.py`. Test: `tests/unit/test_brain_closeout.py`.

- [ ] **Step 1: failing test** — `scan_orphan_references(roots, moved_paths)` returns any source/doc reference to a path that was moved/renamed during the family migrations (e.g. an old `vault/skills/` ref) and is no longer valid; empty when clean.
- [ ] **Step 2: Run → FAIL**. **Step 3: Implement** — `scan_orphan_references` greps the repo (ripgrep, fallback to Python walk) for each `moved_path` old form; returns hits. Feed its result as `orphan_refs` into `verify_family_closeout`. **Step 4: PASS**. **Step 5: Commit** `feat(brain): family-wide orphan-reference scan (ADR-786 C5)`

---

## Task 3: Thin CLI wrapper + closeout report rendering

**Files:** Create `project-brain/capabilities/skills/platform-admin/scripts/harness_closeout.py`. Test: smoke test.

- [ ] **Step 1: failing test** — importing the script's `main()` and running it against the real stack returns exit 0 only when `report.all_ok`; renders a human report naming clients/tiers/paths.
- [ ] **Step 2: Run → FAIL**. **Step 3: Implement** — `main()` resolves the real stack (`resolve_active_stack` + `get_brain_registry_path`), derives `single_brain_skills` (from the pre-cutover baseline or the project tier alone), runs `verify_family_closeout`, prints the report, exits non-zero if not `all_ok`. **Step 4: PASS**. **Step 5: Commit** `feat(closeout): harness_closeout CLI report (ADR-786 C5)`

---

## Completion Gate (C5) — the family closeout itself
- [ ] `uv run pytest tests/unit -q` green.
- [ ] **The closeout run (rule 31/34) — this IS the family's terminal proof:** run `harness_closeout.py` against the **real** stack and **real** clients:
```bash
uv run python project-brain/capabilities/skills/platform-admin/scripts/harness_closeout.py
```
  Must report, all green: every enabled client has the full effective set across Global+User+Project (`harness.all_ok`); parity held (no dropped skill); zero orphaned references (rule 23 family-wide); the C3 cross-client memory round-trip works; exact URLs/clients/tiers/paths named. Any empty/error/stale state is a finding to fix — the family is NOT closed until this is fully green.

## Self-Review
**Spec coverage (ADR-786):** assembles harness + parity + orphan-scan gates into one report (T1–T2), runnable closeout (T3), real-client terminal proof (Completion). ✔ The C3 memory round-trip assertion is invoked in the closeout run (real-data step). **Placeholder scan:** none (gates referenced are the real C1b/C1c/C3 functions). **Type consistency:** `verify_family_closeout(stack,*,clients,client_dirs,single_brain_skills,orphan_refs)->CloseoutReport(all_ok,sections)`; `scan_orphan_references(roots,moved_paths)->list[str]`.

## Follow-on
None — C5 is the family terminus. On green, flip ADR-781..786 status notes to Implemented (via `/adr`).
