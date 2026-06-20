# Harness Layering — C4: Harness Manager Surface Implementation Plan

> **For agentic workers:** superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`). **Prerequisite: C1–C3 landed** (the data it visualizes). Implements ADR-785. **UI-touching → mandatory real-browser verification (rules 27/28); dashboard data flows via MCP only (rule 11); this is the sanctioned rule-32 manager-surface exception.**

**Goal:** A VS-Code-settings-style harness manager: a tier filter (Global / User / Project / Effective), per-capability rows showing owner badge + tier + effective/shadowed status, and Promote/Demote actions — so the layering is legible and manageable in one place.

**Architecture:** Two layers. **Data** (groundable now): an MCP tool `harness-manager-snapshot` backed by a new `harness_manager_snapshot(stack)` that assembles, per capability type, the per-tier entries + winner + shadowed (reusing `compute_effective_skills` from C1a and `verify_harness_summary` from C1b) and extends `build_discovery_snapshot`. **UI** (against that contract): a dashboard manager page rendering tier columns + effective/shadowed badges, with Promote/Demote actions that call MCP tools. Promote/Demote mutate via the C1 projection/promotion path (client-native ↔ Augur-managed); they ship after the read-only view is verified.

**Tech Stack:** Python 3.11+ (`src/lib/brain_discovery.py`, MCP tool), Next.js 14 dashboard (App Router, Tailwind + shadcn/ui), the dashboard MCP client. Implements ADR-785. TDD inner loop `uv run pytest <nodeid>` for the data layer; real-browser check for the UI.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `src/lib/brain_manager_snapshot.py` | **NEW** — `harness_manager_snapshot(stack)` (per-capability per-tier effective/shadowed) | Create |
| `tests/unit/test_brain_manager_snapshot.py` | **NEW** | Create |
| `src/mcp/.../harness_manager.py` (skill-owned MCP tool) | **NEW** — `harness-manager-snapshot` MCP tool wrapping the snapshot | Create |
| `project-brain/capabilities/skills/<owner>/augur/pages/harness-manager.yaml` or `augur/dashboard/...` | **NEW** — manager page (config-driven per ADR-491, or TSX) | Create |

> Capability owner: the harness manager belongs to the `ai` or `platform-admin` skill (decide at implement time by where the snapshot MCP tool best fits); the page is skill-owned per rule 2.

---

## Task 1: `harness_manager_snapshot(stack)` data assembler

**Files:** Create `src/lib/brain_manager_snapshot.py`. Test: `tests/unit/test_brain_manager_snapshot.py`.

- [ ] **Step 1: failing test** — `tests/unit/test_brain_manager_snapshot.py`: for a stack with skills across tiers (incl. a shadowed override), `harness_manager_snapshot(stack)` returns `{"skills": {"entries": [{name, winner_tier, shadowed:[tiers], owner:"augur"}], "effective": N, "shadowed": [names]}, "tiers": ["global","user","project"]}`. Assert the override row carries `winner_tier` + non-empty `shadowed`, and `tiers` reflects the active stack.

```python
def test_manager_snapshot_reports_per_capability_effective_shadowed(tmp_path):
    from src.lib.brain_manager_snapshot import harness_manager_snapshot
    snap = harness_manager_snapshot(_stack(tmp_path))  # _stack as in effective tests
    assert snap["tiers"] == ["global", "user", "project"]
    rows = {r["name"]: r for r in snap["skills"]["entries"]}
    assert rows["shared"]["winner_tier"] == "project"
    assert "global" in rows["shared"]["shadowed"]
    assert rows["core-only"]["winner_tier"] == "global"
    assert snap["skills"]["effective"] >= 4
```

- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement** — create `src/lib/brain_manager_snapshot.py`:

```python
"""Harness manager snapshot: per-capability per-tier effective/shadowed (ADR-785)."""

from __future__ import annotations

from pathlib import Path

from src.lib.brain_effective import compute_effective_skills
from src.lib.brain_layered_projection import resolve_layered_projection
from src.lib.brain_stack import BrainStack


def harness_manager_snapshot(stack: BrainStack, *, project_root: Path | None = None) -> dict:
    layered = resolve_layered_projection(stack, project_root=project_root)
    tiers = [layer.tier.value for layer in layered.layers]
    skills = compute_effective_skills(layered)
    entries = [
        {
            "name": name,
            "winner_tier": e.winner_tier.value,
            "shadowed": [t.value for t, _ in e.shadowed],
            "owner": "augur",
        }
        for name, e in sorted(skills.entries.items())
    ]
    return {
        "tiers": tiers,
        "skills": {
            "entries": entries,
            "effective": len(entries),
            "shadowed": skills.shadowed_names(),
        },
    }
```

- [ ] **Step 4: Run → PASS**. **Step 5: Commit** `feat(brain): harness_manager_snapshot data assembler (ADR-785 C4)`

---

## Task 2: `harness-manager-snapshot` MCP tool

**Files:** Create the skill-owned MCP tool wrapping `harness_manager_snapshot` (per rule 11 — dashboard reads via MCP). Test: the skill's `augur/tests/`.

- [ ] **Step 1: failing test** — the MCP tool, invoked with no args, resolves the real active stack and returns the snapshot dict (mock the stack in the test). Follow the Augur skill-test convention (`spec_from_file_location`, namespaced module).
- [ ] **Step 2: Run → FAIL**. **Step 3: Implement** — a `@mcp.tool`-decorated function `harness_manager_snapshot_tool()` that calls `resolve_active_stack(...)` + `harness_manager_snapshot(stack)`; register it in the owning skill's MCP module + `capability_exposure.yaml` (with `mcp via dashboard` surface, and a `command:`/exposure entry). **Step 4: PASS**. **Step 5: Commit** `feat(mcp): harness-manager-snapshot tool (ADR-785 C4)`

---

## Task 3: Manager dashboard page (read-only view first)

**Files:** Create the skill-owned page (`augur/pages/harness-manager.yaml` config-driven per ADR-491, or `augur/dashboard/.../page.tsx`).

- [ ] **Step 1:** Declare the page (config-driven YAML preferred). It calls the `harness-manager-snapshot` MCP tool via `POST /api/mcp/tool` and renders: a **tier filter** (Global/User/Project/Effective), and a table grouped by capability type with columns `name | owner badge | winning tier | shadowed (override indicator)`. Use the VS-Code-settings mental model (effective value + override links). No bespoke fetch/exec in the page (rule 11).
- [ ] **Step 2: Build + client-load verification (rules 27/28, MANDATORY):** rebuild via `/dev-build`, then load the page in a real browser / screenshot tool at the worktree's dashboard port; confirm it renders to interactive state (not a chunk-load error boundary), shows the real effective/shadowed rows, and the tier filter works. HTTP 200 / SSR is NOT sufficient.
- [ ] **Step 3: Commit** `feat(dashboard): harness manager read-only view (ADR-785 C4)`

---

## Task 4: Promote / Demote actions

**Files:** Skill-owned MCP tools `harness-promote` / `harness-demote` + wire the page action buttons.

- [ ] **Step 1: failing test** — `promote(capability, name, target_tier)` moves a client-native capability into the Augur brain at the matching tier (per the 781 ladder: personal→User, repo→Project); `demote` ejects an Augur-managed capability to a single client. Assert the file move + that a subsequent `harness_manager_snapshot` reflects the new owner/tier. (Depends on the C1 projection path; use fixtures.)
- [ ] **Step 2: Run → FAIL**. **Step 3: Implement** — the promote/demote MCP tools call the C1 promotion path (move source into the brain's `capabilities/skills/`, re-run the relevant sync); demote reverses it. Re-use the migration harness (count-check) for the move. **Step 4: PASS** + real-browser action test. **Step 5: Commit** `feat(dashboard): harness promote/demote actions (ADR-785 C4)`

---

## Completion Gate (C4)
- [ ] `uv run pytest tests/unit <skill tests> -q` green.
- [ ] **Real-browser verification (rule 28, MANDATORY):** the manager page loads to interactive state at the real dashboard port, shows the **real** effective/shadowed rows for the live stack (the 23-skill effective set with any overrides flagged), the tier filter switches views, and Promote/Demote round-trip is reflected by `verify_harness_summary`. Screenshot evidence. No empty/placeholder/error state (rule 31).

## Self-Review
**Spec coverage (ADR-785):** snapshot data (T1) + MCP tool (T2) + read-only manager view (T3) + promote/demote (T4). ✔ **Placeholder scan:** data layer (T1–T2) is fully concrete; UI tasks (T3–T4) are grounded against the snapshot contract + dashboard conventions and require real-browser verification (inherent to UI work, not a placeholder). **Type consistency:** `harness_manager_snapshot(stack)->{"tiers":[str], "skills":{"entries":[{name,winner_tier,shadowed,owner}], "effective":int, "shadowed":[str]}}` consumed identically by the MCP tool + page.

## Follow-on
On C4 green, the family's user-facing surface is complete; C5 runs the whole-family closeout.
