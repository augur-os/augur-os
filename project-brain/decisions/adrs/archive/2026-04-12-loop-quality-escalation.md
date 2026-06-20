# Loop Quality Escalation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade adaptive loops so fix quality improves through explicit finding classification, selective wiki/ADR context escalation, design-gated structural fixes, and richer verification/reporting outcomes.

**Architecture:** Keep the existing adaptive engine entrypoints and insert a focused escalation layer inside the fix pipeline. Add three small modules: one for classifying findings and outcomes, one for targeted context collection, and one for writing design-gate artifacts. Then thread their outputs through `engine_fix_phase.py`, `reporting.py`, and the CLI/report surfaces so loops can stay fast for mechanical work while escalating correctly for structural changes.

**Tech Stack:** Python 3.13, pytest, existing adaptive engine modules under `skills/daemon/scripts/adaptive/`, wiki helpers from `skills/ingest/scripts/wiki_pages.py`, frontmatter utilities, runtime state under `~/Library/Application Support/Augur/state`

---

## File Structure

**Create**

- `skills/daemon/scripts/adaptive/engine_quality.py`
  - finding-band classifier (`mechanical`, `local-semantic`, `structural`)
  - richer outcome constants
  - escalation trigger helpers
- `skills/daemon/scripts/adaptive/engine_context.py`
  - targeted context collection from nearby docs, ADRs, wiki pages, and recent reports
- `skills/daemon/scripts/adaptive/engine_design_gate.py`
  - write ADR-backed or runtime-note-backed design artifacts before structural fixes
- `skills/daemon/augur/tests/test_engine_quality.py`
  - unit tests for classification and outcome mapping
- `skills/daemon/augur/tests/test_engine_context.py`
  - unit tests for selective context loading and priority ordering
- `skills/daemon/augur/tests/test_engine_design_gate.py`
  - unit tests for ADR/runtime design-note creation

**Modify**

- `skills/daemon/scripts/adaptive/engine_fix_phase.py`
  - integrate classification, context escalation, and design gating before structural fixes
- `skills/daemon/scripts/adaptive/reporting.py`
  - add new outcome taxonomy and reporting columns/summary counts
- `skills/daemon/scripts/adaptive/loop_reporter.py`
  - map new outcome values into manual/report/design/failure buckets
- `skills/daemon/scripts/adaptive/run_inspection.py`
  - surface design-gated outcomes and “context insufficient” cases in the post-run analysis
- `skills/daemon/commands/dev-loops.md`
  - document the new escalation and design-gate behavior
- `skills/daemon/references/dev-loops-implementation.md`
  - document the runtime design-note path and outcome semantics
- `docs/superpowers/specs/2026-04-12-loop-quality-escalation-design.md`
  - update status/links if implementation shape shifts during execution

**Existing tests to extend**

- `skills/daemon/augur/tests/test_adaptive_loop_executor.py`
- `skills/daemon/augur/tests/test_run_inspection.py`

---

### Task 1: Add Finding Bands And Outcome Taxonomy

**Files:**
- Create: `skills/daemon/scripts/adaptive/engine_quality.py`
- Modify: `skills/daemon/scripts/adaptive/reporting.py`
- Modify: `skills/daemon/scripts/adaptive/engine_fix_phase.py`
- Test: `skills/daemon/augur/tests/test_engine_quality.py`

- [ ] **Step 1: Write the failing tests for classification and outcome mapping**

```python
from skills.daemon.scripts.adaptive.engine_quality import (
    classify_finding_band,
    classify_fix_outcome,
)


def test_classify_finding_band_marks_cross_subsystem_issue_structural():
    issue = {
        "path": "skills/daemon/scripts/adaptive_loop_executor.py",
        "detail": "Move scheduled ownership from daemon to codex",
        "loop": "observability",
        "scheduler_change": True,
    }

    assert classify_finding_band(issue) == "structural"


def test_classify_finding_band_keeps_tool_name_mismatch_mechanical():
    issue = {
        "path": "apps/dashboard/components/foo.tsx",
        "detail": "Tool name typo",
        "tool_name_mismatch": True,
    }

    assert classify_finding_band(issue) == "mechanical"


def test_classify_fix_outcome_marks_structural_fix_without_design_blocked():
    outcome = classify_fix_outcome(
        success=False,
        changes=[],
        fix_result={"actions": []},
        finding_band="structural",
        design_gate_written=False,
        reverted=False,
        context_insufficient=False,
    )

    assert outcome == "blocked-needs-design"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `pytest skills/daemon/augur/tests/test_engine_quality.py -q`

Expected: FAIL with import or assertion errors because `engine_quality.py` and the new outcome rules do not exist yet.

- [ ] **Step 3: Implement the minimal classification module and reporting constants**

```python
# skills/daemon/scripts/adaptive/engine_quality.py
from __future__ import annotations


MECHANICAL = "mechanical"
LOCAL_SEMANTIC = "local-semantic"
STRUCTURAL = "structural"

OUTCOMES = {
    "auto-fixed",
    "report-only",
    "blocked-needs-design",
    "design-written",
    "design-gated-fixed",
    "verification-failed-reverted",
    "context-insufficient",
    "clean",
    "broken",
}


def classify_finding_band(issue: dict) -> str:
    if issue.get("scheduler_change") or issue.get("ownership_change"):
        return STRUCTURAL
    if issue.get("cross_subsystem") or issue.get("design_ambiguous"):
        return STRUCTURAL
    if issue.get("tool_name_mismatch") or issue.get("path_fix"):
        return MECHANICAL
    return LOCAL_SEMANTIC


def classify_fix_outcome(
    *,
    success: bool,
    changes: list,
    fix_result: dict | None,
    finding_band: str,
    design_gate_written: bool,
    reverted: bool,
    context_insufficient: bool,
) -> str:
    if context_insufficient:
        return "context-insufficient"
    if reverted:
        return "verification-failed-reverted"
    if finding_band == STRUCTURAL and not design_gate_written:
        return "blocked-needs-design"
    if success and changes and finding_band == STRUCTURAL:
        return "design-gated-fixed"
    if success and changes:
        return "auto-fixed"
    return "report-only" if success else "broken"
```

- [ ] **Step 4: Thread the new outcome values into reporting**

```python
# skills/daemon/scripts/adaptive/reporting.py
DISPLAY_OUTCOMES = {
    "auto-fixed": "auto-fixed",
    "design-gated-fixed": "design-fixed",
    "blocked-needs-design": "needs-design",
    "design-written": "design-written",
    "verification-failed-reverted": "reverted",
    "context-insufficient": "no-context",
    "report-only": "report-only",
    "clean": "clean",
    "broken": "broken",
}
```

- [ ] **Step 5: Run the focused tests and confirm they pass**

Run: `pytest skills/daemon/augur/tests/test_engine_quality.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add \
  skills/daemon/scripts/adaptive/engine_quality.py \
  skills/daemon/scripts/adaptive/reporting.py \
  skills/daemon/scripts/adaptive/engine_fix_phase.py \
  skills/daemon/augur/tests/test_engine_quality.py
git commit -m "feat(adaptive): add loop quality bands and outcomes"
```

---

### Task 2: Add Targeted Context Escalation

**Files:**
- Create: `skills/daemon/scripts/adaptive/engine_context.py`
- Modify: `skills/daemon/scripts/adaptive/engine_fix_phase.py`
- Test: `skills/daemon/augur/tests/test_engine_context.py`

- [ ] **Step 1: Write the failing tests for selective context loading**

```python
from pathlib import Path

from skills.daemon.scripts.adaptive.engine_context import collect_context


def test_collect_context_skips_wiki_for_mechanical_issue(tmp_path: Path):
    issue = {"path": "apps/dashboard/page.tsx", "tool_name_mismatch": True}
    context = collect_context(issue=issue, project_root=tmp_path, loop_name="testing")
    assert context["sources"] == []


def test_collect_context_loads_adr_and_wiki_for_structural_issue(tmp_path: Path):
    docs = tmp_path / "docs" / "decisions"
    docs.mkdir(parents=True)
    (docs / "ADR-999-test.md").write_text("---\nstatus: proposed\n---\nownership\n", encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "dev-boundaries.md").write_text("---\ntitle: Boundaries\n---\nCodex owns schedules\n", encoding="utf-8")

    issue = {"ownership_change": True, "design_ambiguous": True}
    context = collect_context(
        issue=issue,
        project_root=tmp_path,
        loop_name="observability",
        adr_dir=docs,
        wiki_dir=wiki,
    )

    assert any(item["kind"] == "adr" for item in context["sources"])
    assert any(item["kind"] == "wiki" for item in context["sources"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest skills/daemon/augur/tests/test_engine_context.py -q`

Expected: FAIL because `collect_context()` does not exist yet.

- [ ] **Step 3: Implement the context collector**

```python
# skills/daemon/scripts/adaptive/engine_context.py
from __future__ import annotations

from pathlib import Path

from .engine_quality import MECHANICAL, classify_finding_band


def collect_context(
    *,
    issue: dict,
    project_root: Path,
    loop_name: str,
    adr_dir: Path | None = None,
    wiki_dir: Path | None = None,
) -> dict:
    band = classify_finding_band(issue)
    if band == MECHANICAL:
        return {"band": band, "sources": []}

    sources: list[dict] = []
    if adr_dir and adr_dir.exists():
        for path in sorted(adr_dir.glob("ADR-*.md"))[:3]:
            sources.append({"kind": "adr", "path": str(path)})
    if wiki_dir and wiki_dir.exists() and band == "structural":
        for path in sorted(wiki_dir.glob("*.md"))[:3]:
            sources.append({"kind": "wiki", "path": str(path)})

    return {"band": band, "sources": sources}
```

- [ ] **Step 4: Integrate context collection only for escalated findings**

```python
# skills/daemon/scripts/adaptive/engine_fix_phase.py
context = collect_context(
    issue=issue,
    project_root=engine.project_root,
    loop_name=loop_name,
    adr_dir=get_adr_dir(),
    wiki_dir=get_wiki_dir(),
)
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `pytest skills/daemon/augur/tests/test_engine_context.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add \
  skills/daemon/scripts/adaptive/engine_context.py \
  skills/daemon/scripts/adaptive/engine_fix_phase.py \
  skills/daemon/augur/tests/test_engine_context.py
git commit -m "feat(adaptive): add targeted context escalation"
```

---

### Task 3: Add Design-Gate Artifact Writing For Structural Fixes

**Files:**
- Create: `skills/daemon/scripts/adaptive/engine_design_gate.py`
- Modify: `skills/daemon/scripts/adaptive/adr_writer.py`
- Modify: `skills/daemon/scripts/adaptive/engine_fix_phase.py`
- Test: `skills/daemon/augur/tests/test_engine_design_gate.py`

- [ ] **Step 1: Write the failing tests for design-gate artifacts**

```python
from pathlib import Path

from skills.daemon.scripts.adaptive.engine_design_gate import write_design_gate


def test_write_design_gate_creates_runtime_note_for_narrow_structural_fix(tmp_path: Path):
    out = write_design_gate(
        issue={"detail": "Split loop family"},
        loop_name="skill-quality",
        project_root=tmp_path,
        context={"sources": [{"kind": "wiki", "path": "wiki/dev/autoloops.md"}]},
        use_adr=False,
    )

    assert out["written"] is True
    assert out["path"].endswith(".md")


def test_write_design_gate_uses_adr_for_ownership_change(tmp_path: Path):
    out = write_design_gate(
        issue={"detail": "Move ownership from daemon to codex", "ownership_change": True},
        loop_name="observability",
        project_root=tmp_path,
        context={"sources": []},
        use_adr=True,
    )

    assert out["written"] is True
    assert "ADR-" in out["path"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest skills/daemon/augur/tests/test_engine_design_gate.py -q`

Expected: FAIL because the design-gate writer does not exist yet.

- [ ] **Step 3: Implement the runtime-note and ADR-backed gate writer**

```python
# skills/daemon/scripts/adaptive/engine_design_gate.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.lib.frontmatter_utils import write_frontmatter


def write_design_gate(*, issue: dict, loop_name: str, project_root: Path, context: dict, use_adr: bool) -> dict:
    if use_adr:
        path = project_root / "docs" / "decisions" / f"ADR-LOOP-{loop_name}.md"
    else:
        path = project_root / "docs" / "generated" / "adaptive-design-gates" / f"{loop_name}.md"

    body = (
        f"# Design Gate for {loop_name}\n\n"
        f"- issue: {issue.get('detail', 'unknown')}\n"
        f"- context sources: {len(context.get('sources', []))}\n"
    )
    write_frontmatter(
        path,
        {
            "title": f"Design Gate: {loop_name}",
            "type": "design-gate",
            "updated": datetime.now(timezone.utc).isoformat(),
        },
        body,
    )
    return {"written": True, "path": str(path)}
```

- [ ] **Step 4: Require the design gate before structural code changes proceed**

```python
# skills/daemon/scripts/adaptive/engine_fix_phase.py
if finding_band == "structural":
    gate = write_design_gate(
        issue=issue,
        loop_name=loop_name,
        project_root=engine.project_root,
        context=context,
        use_adr=issue.get("ownership_change", False),
    )
    design_gate_written = gate["written"]
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `pytest skills/daemon/augur/tests/test_engine_design_gate.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add \
  skills/daemon/scripts/adaptive/engine_design_gate.py \
  skills/daemon/scripts/adaptive/engine_fix_phase.py \
  skills/daemon/augur/tests/test_engine_design_gate.py
git commit -m "feat(adaptive): add design gate for structural fixes"
```

---

### Task 4: Integrate Richer Verification And Report Surfaces

**Files:**
- Modify: `skills/daemon/scripts/adaptive/engine_fix_phase.py`
- Modify: `skills/daemon/scripts/adaptive/loop_reporter.py`
- Modify: `skills/daemon/scripts/adaptive/run_inspection.py`
- Modify: `skills/daemon/scripts/adaptive/reporting.py`
- Test: `skills/daemon/augur/tests/test_adaptive_loop_executor.py`
- Test: `skills/daemon/augur/tests/test_run_inspection.py`

- [ ] **Step 1: Write failing tests for design-gated and context-insufficient reporting**

```python
def test_run_inspection_mentions_blocked_needs_design():
    report = CycleReport(loop_name="observability", categories=[
        CategoryReport(name="ownership-shift", issue_count=1, outcome="blocked-needs-design")
    ])

    analysis = generate_evolve_analysis([report])
    assert "blocked-needs-design" in analysis


def test_loop_reporter_treats_design_gated_fix_as_fixed():
    category = {"name": "ownership-shift", "outcome": "design-gated-fixed", "issue_count": 1}
    summary = summarize_report_categories([category])
    assert summary["fixed"] == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest skills/daemon/augur/tests/test_run_inspection.py skills/daemon/augur/tests/test_adaptive_loop_executor.py -q`

Expected: FAIL because the new outcomes are not yet fully surfaced.

- [ ] **Step 3: Update reporting, inspection, and verification behavior**

```python
# skills/daemon/scripts/adaptive/loop_reporter.py
if outcome in {"auto-fixed", "design-gated-fixed"}:
    kind = "fixed"
elif outcome == "blocked-needs-design":
    kind = "manual"
elif outcome == "context-insufficient":
    kind = "report-only"
```

```python
# skills/daemon/scripts/adaptive/run_inspection.py
if w["outcome"] == "blocked-needs-design":
    lines.append("    Structural issue blocked until a design gate is written.")
if w["outcome"] == "context-insufficient":
    lines.append("    Loop could not gather enough project context to act safely.")
```

```python
# skills/daemon/scripts/adaptive/engine_fix_phase.py
if finding_band == "structural" and not design_gate_written:
    return _report_only_result(..., outcome="blocked-needs-design")
```

- [ ] **Step 4: Run the focused tests and confirm they pass**

Run: `pytest skills/daemon/augur/tests/test_run_inspection.py skills/daemon/augur/tests/test_adaptive_loop_executor.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add \
  skills/daemon/scripts/adaptive/engine_fix_phase.py \
  skills/daemon/scripts/adaptive/loop_reporter.py \
  skills/daemon/scripts/adaptive/run_inspection.py \
  skills/daemon/scripts/adaptive/reporting.py \
  skills/daemon/augur/tests/test_run_inspection.py \
  skills/daemon/augur/tests/test_adaptive_loop_executor.py
git commit -m "feat(adaptive): surface design-gated loop outcomes"
```

---

### Task 5: Document The New Escalation Behavior And Run End-To-End Verification

**Files:**
- Modify: `skills/daemon/commands/dev-loops.md`
- Modify: `skills/daemon/references/dev-loops-implementation.md`
- Modify: `docs/superpowers/specs/2026-04-12-loop-quality-escalation-design.md`
- Test: `skills/daemon/augur/tests/test_engine_quality.py`
- Test: `skills/daemon/augur/tests/test_engine_context.py`
- Test: `skills/daemon/augur/tests/test_engine_design_gate.py`
- Test: `skills/daemon/augur/tests/test_adaptive_loop_executor.py`
- Test: `skills/daemon/augur/tests/test_run_inspection.py`

- [ ] **Step 1: Update the command and implementation docs**

```md
## Escalation

- Mechanical findings auto-fix directly.
- Local semantic findings escalate context only if intent is unclear.
- Structural findings must write a design gate before implementation.
- Wiki and ADR context are loaded only when the finding warrants it.
```

- [ ] **Step 2: Run the full focused verification bundle**

Run:

```bash
pytest \
  skills/daemon/augur/tests/test_engine_quality.py \
  skills/daemon/augur/tests/test_engine_context.py \
  skills/daemon/augur/tests/test_engine_design_gate.py \
  skills/daemon/augur/tests/test_adaptive_loop_executor.py \
  skills/daemon/augur/tests/test_run_inspection.py -q
```

Expected: PASS

- [ ] **Step 3: Run one real loop that should stay local/mechanical**

Run: `python skills/daemon/scripts/adaptive_loop_executor.py run code-quality`

Expected: completes without writing design-gate artifacts for purely mechanical issues.

- [ ] **Step 4: Run one structural simulation or seeded fixture path**

Run: `pytest skills/daemon/augur/tests/test_engine_design_gate.py -q`

Expected: PASS with evidence that structural findings write a design gate before implementation.

- [ ] **Step 5: Commit**

```bash
git add \
  skills/daemon/commands/dev-loops.md \
  skills/daemon/references/dev-loops-implementation.md \
  docs/superpowers/specs/2026-04-12-loop-quality-escalation-design.md \
  skills/daemon/augur/tests/test_engine_quality.py \
  skills/daemon/augur/tests/test_engine_context.py \
  skills/daemon/augur/tests/test_engine_design_gate.py \
  skills/daemon/augur/tests/test_adaptive_loop_executor.py \
  skills/daemon/augur/tests/test_run_inspection.py
git commit -m "docs(adaptive): document loop quality escalation"
```

---

## Self-Review

### Spec coverage

- finding bands and outcome taxonomy: Task 1
- adaptive wiki/ADR context only where needed: Task 2
- design-gated structural fixes: Task 3
- richer reporting and verification: Task 4
- docs and end-to-end verification: Task 5

No spec sections are uncovered.

### Placeholder scan

- no `TBD`, `TODO`, or “implement later” markers
- every task has exact files, commands, and expected outcomes

### Type consistency

- band names: `mechanical`, `local-semantic`, `structural`
- outcomes: `auto-fixed`, `report-only`, `blocked-needs-design`, `design-written`, `design-gated-fixed`, `verification-failed-reverted`, `context-insufficient`
- helper names are reused consistently across tasks:
  - `classify_finding_band`
  - `classify_fix_outcome`
  - `collect_context`
  - `write_design_gate`
