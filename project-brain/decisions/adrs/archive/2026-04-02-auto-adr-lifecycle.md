# Auto ADR Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `auto-orphan-plans` with a difficulty-gated autoloop that detects orphan designs, creates missing ADRs, runs gap analysis, and implements found gaps.

**Architecture:** Single ops module (`adr_lifecycle_ops.py`) implementing `scan()` + `fix()` per `ops_protocol`. Scan collects three issue categories (orphan designs, stale Proposed, impl gaps). Fix gates behavior by difficulty: d1 creates ADRs + writes gap reports, d2 implements gaps in worktrees with auto-merge.

**Tech Stack:** Python 3.11+, `src.lib.ops_protocol`, `src.lib.adr_utils`, subprocess/git

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `skills/auto-adr-lifecycle/SKILL.md` | Skill frontmatter + description |
| Create | `skills/auto-adr-lifecycle/scripts/adr_lifecycle_ops.py` | Ops module: scan + fix |
| Create | `skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py` | Tests for scan + fix |
| Delete | `skills/auto-orphan-plans/` (entire directory) | Replaced by new skill |
| Delete | `skills/ai/scripts/ops/orphan_plans.py` | Replaced — ops module for old skill |

---

### Task 1: Create SKILL.md

**Files:**
- Create: `skills/auto-adr-lifecycle/SKILL.md`

- [ ] **Step 1: Create the skill directory and SKILL.md**

```bash
mkdir -p skills/auto-adr-lifecycle/scripts
mkdir -p skills/auto-adr-lifecycle/augur/dashboard
```

Write `skills/auto-adr-lifecycle/SKILL.md`:

```yaml
---
name: auto-adr-lifecycle
x-augur-type: autoloop
x-augur-tags: []
description: >
  Full ADR lifecycle automation — detect orphan designs, create missing ADRs,
  run gap analysis on recent Accepted ADRs, implement found gaps in worktrees.
  Replaces auto-orphan-plans.
x-augur-visibility: auto
x-augur-loop:
  name: hardening
  tier: 3
  trigger: nightly
x-augur-hub: adaptive
x-augur-tab: advisor
x-augur-callable: scripts/adr_lifecycle_ops.py
x-augur-dashboard-pages:
  - /adaptive/overview
x-augur-evolution:
  last_updated: 2026-04-02T00:00:00Z
  improvements_applied: 0
x-augur-config:
  contributions: {}
---

# auto-adr-lifecycle

Full ADR lifecycle automation in the hardening loop (tier 3). Replaces
`auto-orphan-plans`.

## Scan

Collects three issue categories:

1. **Orphan designs** — `docs/plans/*-design.md` not referenced by any ADR
2. **Stale Proposed ADRs** — Proposed status >60 days without progress
3. **Implementation gaps** — Accepted ADRs (last 30 days) with >50% of
   referenced paths missing from codebase

## Fix

Difficulty-gated:

- **d1 (Document)** — Create missing ADRs from orphan designs, run full gap
  analysis on newly created + recent Accepted ADRs, write reports
- **d2 (Implement)** — Implement all found gaps in git worktrees, auto-merge
  on completion gate pass

## Reports

- `docs/generated/orphan-plans-report.md` — orphan designs
- `docs/generated/adr-gaps-report.md` — implementation gaps by severity

## Dashboard

Contributes to `/adaptive/overview`.

## Usage

```
/dev-loops run hardening    # runs as part of the hardening loop
```
```

- [ ] **Step 2: Commit**

```bash
git add skills/auto-adr-lifecycle/SKILL.md
git commit -m "feat(auto-adr-lifecycle): add SKILL.md for ADR lifecycle autoloop"
```

---

### Task 2: Write scan() — orphan design detection

**Files:**
- Create: `skills/auto-adr-lifecycle/scripts/adr_lifecycle_ops.py`
- Test: `skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py`

- [ ] **Step 1: Write the failing test for orphan detection**

Write `skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py`:

```python
"""Tests for auto-adr-lifecycle ops module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.lib.ops_protocol import OpsContext, ScanResult


@pytest.fixture
def ctx(tmp_path: Path) -> OpsContext:
    return OpsContext(project_root=tmp_path)


@pytest.fixture
def vault_dirs(tmp_path: Path):
    """Create vault plans and adrs directories."""
    plans_dir = tmp_path / "vault" / "dev" / "plans"
    adr_dir = tmp_path / "vault" / "dev" / "adrs"
    plans_dir.mkdir(parents=True)
    adr_dir.mkdir(parents=True)
    return plans_dir, adr_dir


class TestScanOrphanDesigns:
    def test_no_plans_dir(self, ctx: OpsContext):
        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import scan

            result = scan(ctx)
            assert isinstance(result, ScanResult)
            assert result.issues == []
            assert result.severity == "info"

    def test_orphan_plan_detected(self, ctx: OpsContext, vault_dirs):
        plans_dir, adr_dir = vault_dirs
        # Create a design doc with no ADR reference
        (plans_dir / "2026-01-01-widget-design.md").write_text(
            "# Widget Feature Design\n\nSome design content.\n"
        )
        # Create an ADR that does NOT reference this plan
        (adr_dir / "ADR-100-unrelated.md").write_text(
            "---\nstatus: Accepted\n---\n# ADR-100: Unrelated\n"
        )

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import scan

            result = scan(ctx)
            assert len(result.issues) >= 1
            orphans = [i for i in result.issues if i.get("orphan_type") == "design-doc"]
            assert len(orphans) == 1
            assert "Widget Feature Design" in orphans[0]["detail"]

    def test_referenced_plan_not_flagged(self, ctx: OpsContext, vault_dirs):
        plans_dir, adr_dir = vault_dirs
        plan_name = "2026-01-01-widget-design.md"
        (plans_dir / plan_name).write_text("# Widget Design\n")
        # ADR references the plan filename
        (adr_dir / "ADR-100-widget.md").write_text(
            f"---\nstatus: Accepted\n---\n# ADR-100: Widget\n\nSee {plan_name}\n"
        )

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import scan

            result = scan(ctx)
            orphans = [i for i in result.issues if i.get("orphan_type") == "design-doc"]
            assert len(orphans) == 0
```

- [ ] **Step 2: Run tests — expect ImportError (module doesn't exist yet)**

```bash
cd ~/Projects/Augur
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Write the scan() function — orphan detection portion**

Write `skills/auto-adr-lifecycle/scripts/adr_lifecycle_ops.py`:

```python
"""auto-adr-lifecycle: Full ADR lifecycle automation.

Scan: detect orphan designs, stale Proposed ADRs, implementation gaps.
Fix: d1 creates missing ADRs + gap reports, d2 implements gaps in worktrees.

Replaces auto-orphan-plans.
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_project_root, get_vault_dir
from src.lib.adr_utils import (
    detect_stale_status,
    find_next_adr_number,
    get_adr_dir,
    scan_adrs,
)
from src.lib.ops_protocol import (
    FixClassification,
    FixResult,
    OpsContext,
    ScanResult,
    classify_fix,
    evolution_gap,
    make_issue,
    write_report,
)


name = "auto-adr-lifecycle"

DIFFICULTY_SPEC = {
    0: "Surface — detect orphan designs, stale Proposed, potential impl gaps (report only)",
    1: "Document — create missing ADRs from orphans, full gap analysis, write reports",
    2: "Implement — implement all found gaps in worktrees, auto-merge on gate pass",
}


# ---------------------------------------------------------------------------
# Helpers (carried over from orphan_plans.py)
# ---------------------------------------------------------------------------


def _extract_title(plan_file: Path) -> str:
    """Extract title from first H1 heading or filename."""
    try:
        content = plan_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except (OSError, UnicodeDecodeError):
        pass
    return plan_file.stem.replace("-", " ").replace("_", " ").title()


def _plan_declares_adr(plan_file: Path, adr_dir: Path) -> bool:
    """Check if plan has an explicit ADR-NNN reference to an existing ADR."""
    try:
        content = plan_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    for m in re.finditer(r"ADR-(\d+)", content):
        adr_num = m.group(1)
        if any(adr_dir.glob(f"ADR-{adr_num}-*.md")) or (adr_dir / f"ADR-{adr_num}.md").exists():
            return True
    return False


def _is_referenced_by_adr(plan_name: str, adr_dir: Path) -> bool:
    """Check if any ADR references this plan file."""
    for adr_file in adr_dir.glob("ADR-*.md"):
        try:
            content = adr_file.read_text(encoding="utf-8")
            if plan_name in content:
                return True
        except (OSError, UnicodeDecodeError):
            continue
    return False


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    """Stage specific paths and commit. Returns short hash or None."""
    for p in paths:
        subprocess.run(["git", "add", p], capture_output=True, cwd=str(project_root))
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return None
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        return rev.stdout.strip() if rev.returncode == 0 else None
    return None


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


def _scan_orphan_designs(plans_dir: Path, adr_dir: Path) -> list[dict]:
    """Category 1: Orphan design docs not referenced by any ADR."""
    orphans: list[dict] = []
    for plan_file in sorted(plans_dir.glob("*.md")):
        plan_name = plan_file.name
        if _is_referenced_by_adr(plan_name, adr_dir) or _plan_declares_adr(plan_file, adr_dir):
            continue
        title = _extract_title(plan_file)
        orphans.append(
            make_issue(
                category="adr-lifecycle",
                kind="actionable",
                detail=f"Orphan design: {title}",
                path=str(plan_file),
                root_cause_type="manual_debt",
                fixability="auto",
                orphan_type="design-doc",
                suggested_adr_title=title,
            )
        )
    return orphans


def scan(ctx: OpsContext) -> ScanResult:
    vault_dir = get_vault_dir()
    plans_dir = vault_dir / "dev" / "plans"
    adr_dir = vault_dir / "dev" / "adrs"

    issues: list[dict] = []
    items_scanned = 0

    # Category 1: Orphan designs
    if plans_dir.is_dir() and adr_dir.is_dir():
        orphans = _scan_orphan_designs(plans_dir, adr_dir)
        issues.extend(orphans)
        items_scanned += len(list(plans_dir.glob("*.md")))

    severity = "warning" if len(issues) > 5 else "info"
    health = "degraded" if severity == "warning" else "verified"

    if not issues:
        issues.append(
            evolution_gap(
                "No ADR lifecycle issues. Consider: scanning for skills without "
                "governing ADRs, detecting ADR/code drift beyond path existence.",
                category="adr-lifecycle",
            )
        )

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} ADR lifecycle issue(s)" if issues else "No ADR lifecycle issues",
        severity=severity,
        health=health,
        items_scanned=items_scanned,
    )
```

- [ ] **Step 4: Run tests — orphan detection tests should pass**

```bash
cd ~/Projects/Augur
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py::TestScanOrphanDesigns -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-adr-lifecycle/scripts/adr_lifecycle_ops.py skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py
git commit -m "feat(auto-adr-lifecycle): scan() with orphan design detection"
```

---

### Task 3: Add scan() — stale Proposed and implementation gap detection

**Files:**
- Modify: `skills/auto-adr-lifecycle/scripts/adr_lifecycle_ops.py`
- Modify: `skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py`

- [ ] **Step 1: Write failing tests for stale Proposed and impl gap detection**

Append to `test_adr_lifecycle_ops.py`:

```python
class TestScanStaleProposed:
    def test_stale_proposed_detected(self, ctx: OpsContext, vault_dirs):
        plans_dir, adr_dir = vault_dirs
        import time
        import os

        # Create an ADR file and backdate it >60 days
        adr_file = adr_dir / "ADR-200-old-thing.md"
        adr_file.write_text(
            "---\nstatus: Proposed\ndate: '2025-01-01'\n---\n# ADR-200: Old Thing\n"
        )
        old_time = time.time() - (61 * 86400)
        os.utime(adr_file, (old_time, old_time))

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import scan

            result = scan(ctx)
            stale = [i for i in result.issues if i.get("orphan_type") == "stale-proposed"]
            assert len(stale) == 1
            assert "Old Thing" in stale[0]["detail"]

    def test_recent_proposed_not_flagged(self, ctx: OpsContext, vault_dirs):
        plans_dir, adr_dir = vault_dirs
        (adr_dir / "ADR-201-new-thing.md").write_text(
            "---\nstatus: Proposed\ndate: '2026-03-30'\n---\n# ADR-201: New Thing\n"
        )

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import scan

            result = scan(ctx)
            stale = [i for i in result.issues if i.get("orphan_type") == "stale-proposed"]
            assert len(stale) == 0


class TestScanImplGaps:
    def test_impl_gap_detected(self, ctx: OpsContext, vault_dirs):
        plans_dir, adr_dir = vault_dirs
        # ADR references paths that don't exist
        (adr_dir / "ADR-300-feature.md").write_text(
            "---\nstatus: Accepted\ndate: '2026-03-20'\n---\n"
            "# ADR-300: Feature\n\n## Decision\n\n"
            "Create `src/lib/feature_engine.py` with the main logic.\n"
            "Create `src/lib/feature_utils.py` for helpers.\n"
            "Add API route at `/api/feature/status`.\n"
        )

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import scan

            result = scan(ctx)
            gaps = [i for i in result.issues if i.get("orphan_type") == "impl-gap"]
            assert len(gaps) == 1
            assert gaps[0]["gap_count"] > 0
```

- [ ] **Step 2: Run tests — expect failures**

```bash
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py -k "TestScanStale or TestScanImpl" -v
```

Expected: FAIL (stale/impl gap scanning not implemented yet)

- [ ] **Step 3: Add stale Proposed and impl gap scanning to scan()**

Add these functions to `adr_lifecycle_ops.py` before `scan()`:

```python
def _scan_stale_proposed(adr_dir: Path) -> list[dict]:
    """Category 2: Proposed ADRs older than 60 days."""
    adrs = scan_adrs(adr_dir)
    stale_issues = detect_stale_status(adrs, days=60, decisions_dir=adr_dir)
    results: list[dict] = []
    for issue in stale_issues:
        if issue["issue"] != "stale_proposed":
            continue
        # Find title from scanned ADRs
        title = ""
        for adr in adrs:
            if adr["number"] == issue["number"]:
                title = adr["title"]
                break
        results.append(
            make_issue(
                category="adr-lifecycle",
                kind="maintenance",
                detail=f"Stale Proposed ADR: {title} (ADR-{issue['number']}, {issue.get('age_days', '?')} days)",
                path=str(adr_dir / issue["filename"]),
                root_cause_type="manual_debt",
                fixability="manual",
                orphan_type="stale-proposed",
                adr_number=issue["number"],
                age_days=issue.get("age_days", 0),
            )
        )
    return results


def _extract_expected_artifacts(adr_content: str) -> list[str]:
    """Parse ADR Decision section for referenced file paths and artifacts."""
    artifacts: list[str] = []
    # Match file paths: src/, skills/, apps/, config/ prefixed paths
    for m in re.finditer(r'[`"\']?((?:src|skills|apps|config)/[\w/._-]+)', adr_content):
        artifacts.append(m.group(1))
    # Match API route paths
    for m in re.finditer(r'[`"\']?(/api/[\w/._-]+)', adr_content):
        artifacts.append(m.group(1))
    return list(dict.fromkeys(artifacts))  # dedupe preserving order


def _scan_impl_gaps(adr_dir: Path, project_root: Path) -> list[dict]:
    """Category 3: Accepted ADRs with >50% of referenced paths missing."""
    adrs = scan_adrs(adr_dir)
    now = datetime.now(timezone.utc)
    thirty_days_ago = now.timestamp() - (30 * 86400)

    results: list[dict] = []
    for adr in adrs:
        if adr["status"] != "Accepted":
            continue
        adr_path = adr_dir / adr["filename"]
        if not adr_path.exists():
            continue
        # Only recent ADRs (last 30 days by mtime)
        if adr_path.stat().st_mtime < thirty_days_ago:
            continue

        content = adr_path.read_text(encoding="utf-8")
        artifacts = _extract_expected_artifacts(content)
        if not artifacts:
            continue

        missing = 0
        for artifact in artifacts:
            if artifact.startswith("/api/"):
                # Check for API route file
                route_path = project_root / "apps" / "dashboard" / "app" / artifact.lstrip("/") / "route.ts"
                if not route_path.exists():
                    missing += 1
            else:
                full_path = project_root / artifact
                if not full_path.exists():
                    missing += 1

        if missing == 0 or len(artifacts) == 0:
            continue
        ratio = missing / len(artifacts)
        if ratio > 0.5:
            results.append(
                make_issue(
                    category="adr-lifecycle",
                    kind="actionable",
                    detail=f"Potential implementation gaps: {adr['title']} ({missing}/{len(artifacts)} artifacts missing)",
                    path=str(adr_path),
                    root_cause_type="manual_debt",
                    fixability="auto",
                    orphan_type="impl-gap",
                    adr_number=adr["number"],
                    gap_count=missing,
                    total_artifacts=len(artifacts),
                )
            )
    return results
```

Update `scan()` to call all three:

```python
def scan(ctx: OpsContext) -> ScanResult:
    vault_dir = get_vault_dir()
    plans_dir = vault_dir / "dev" / "plans"
    adr_dir = vault_dir / "dev" / "adrs"

    issues: list[dict] = []
    items_scanned = 0

    # Category 1: Orphan designs
    if plans_dir.is_dir() and adr_dir.is_dir():
        orphans = _scan_orphan_designs(plans_dir, adr_dir)
        issues.extend(orphans)
        items_scanned += len(list(plans_dir.glob("*.md")))

    # Category 2: Stale Proposed ADRs
    if adr_dir.is_dir():
        stale = _scan_stale_proposed(adr_dir)
        issues.extend(stale)

    # Category 3: Implementation gaps in recent Accepted ADRs
    if adr_dir.is_dir():
        gaps = _scan_impl_gaps(adr_dir, ctx.project_root)
        issues.extend(gaps)
        items_scanned += len(list(adr_dir.glob("ADR-*.md")))

    severity = "warning" if len(issues) > 5 else "info"
    health = "degraded" if severity == "warning" else "verified"

    if not issues:
        issues.append(
            evolution_gap(
                "No ADR lifecycle issues. Consider: scanning for skills without "
                "governing ADRs, detecting ADR/code drift beyond path existence.",
                category="adr-lifecycle",
            )
        )

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} ADR lifecycle issue(s)",
        severity=severity,
        health=health,
        items_scanned=items_scanned,
    )
```

- [ ] **Step 4: Run all scan tests**

```bash
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-adr-lifecycle/scripts/adr_lifecycle_ops.py skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py
git commit -m "feat(auto-adr-lifecycle): scan() with stale Proposed and impl gap detection"
```

---

### Task 4: Write fix() — d1 ADR creation from orphan designs

**Files:**
- Modify: `skills/auto-adr-lifecycle/scripts/adr_lifecycle_ops.py`
- Modify: `skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py`

- [ ] **Step 1: Write failing test for d1 ADR creation**

Append to `test_adr_lifecycle_ops.py`:

```python
class TestFixD1CreateAdrs:
    def test_creates_adr_from_orphan(self, ctx: OpsContext, vault_dirs):
        plans_dir, adr_dir = vault_dirs
        (plans_dir / "2026-01-01-widget-design.md").write_text(
            "# Widget Feature Design\n\n## Context\n\nWe need widgets.\n\n"
            "## Decision\n\nBuild a widget system.\n\n"
            "## Consequences\n\nMore widgets.\n"
        )
        ctx_d1 = OpsContext(project_root=ctx.project_root, difficulty=1)

        issues = [
            {
                "category": "adr-lifecycle",
                "kind": "actionable",
                "detail": "Orphan design: Widget Feature Design",
                "path": str(plans_dir / "2026-01-01-widget-design.md"),
                "orphan_type": "design-doc",
                "suggested_adr_title": "Widget Feature Design",
            }
        ]

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ), patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops._commit_files",
            return_value="abc1234",
        ), patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops._run_post_hooks",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import fix

            result = fix(ctx_d1, issues)
            assert result.success
            # Check an ADR file was created
            adr_files = list(adr_dir.glob("ADR-*.md"))
            assert len(adr_files) == 1
            content = adr_files[0].read_text()
            assert "Widget" in content
            assert "Proposed" in content

    def test_dry_run_creates_nothing(self, ctx: OpsContext, vault_dirs):
        plans_dir, adr_dir = vault_dirs
        ctx_dry = OpsContext(project_root=ctx.project_root, difficulty=1, dry_run=True)

        issues = [
            {
                "category": "adr-lifecycle",
                "orphan_type": "design-doc",
                "path": str(plans_dir / "fake.md"),
                "suggested_adr_title": "Fake",
            }
        ]

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import fix

            result = fix(ctx_dry, issues)
            assert result.success
            assert list(adr_dir.glob("ADR-*.md")) == []
```

- [ ] **Step 2: Run tests — expect failures**

```bash
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py::TestFixD1CreateAdrs -v
```

Expected: FAIL (fix not implemented yet)

- [ ] **Step 3: Implement fix() with d1 ADR creation**

Add to `adr_lifecycle_ops.py`:

```python
def _slugify(title: str) -> str:
    """Convert title to kebab-case slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:50]  # cap length


def _create_adr_from_design(plan_path: Path, adr_dir: Path) -> Path | None:
    """Read a design doc and generate an ADR file from it."""
    if not plan_path.exists():
        return None

    content = plan_path.read_text(encoding="utf-8")
    title = _extract_title(plan_path)
    next_num = find_next_adr_number(adr_dir)
    slug = _slugify(title)
    adr_filename = f"ADR-{next_num}-{slug}.md"
    adr_path = adr_dir / adr_filename

    # Extract sections from design doc
    sections = {"context": "", "decision": "", "consequences": ""}
    current_section = ""
    for line in content.splitlines():
        lower = line.lower().strip().lstrip("#").strip()
        if lower in ("context", "background", "motivation", "problem"):
            current_section = "context"
            continue
        elif lower in ("decision", "approach", "solution", "design"):
            current_section = "decision"
            continue
        elif lower in ("consequences", "trade-offs", "tradeoffs", "impact"):
            current_section = "consequences"
            continue
        elif line.startswith("## "):
            current_section = ""
            continue
        if current_section:
            sections[current_section] += line + "\n"

    # Write ADR with frontmatter
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    adr_content = f"""---
status: Proposed
date: '{today}'
tags: []
related: []
---

# ADR-{next_num}: {title}

## Context

{sections['context'].strip() or 'Generated from design doc. See references.'}

## Decision

{sections['decision'].strip() or 'See referenced design document for full decision details.'}

## Consequences

{sections['consequences'].strip() or 'See referenced design document.'}

## References

- Source design: `{plan_path.name}`
"""
    adr_path.write_text(adr_content, encoding="utf-8")
    return adr_path


def _run_post_hooks(project_root: Path) -> None:
    """Run ADR post-write hooks: regenerate index + sync agent instructions."""
    subprocess.run(
        ["python", ".github/scripts/generate_adr_index.py"],
        capture_output=True,
        cwd=str(project_root),
    )
    subprocess.run(
        ["python3", "-m", "skills.ai.scripts.sync_agents", "--rules"],
        capture_output=True,
        cwd=str(project_root),
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: {len(issues)} ADR lifecycle issue(s) detected",
        )
    if not issues:
        return FixResult(success=True, summary="No ADR lifecycle issues to fix")

    adr_dir = get_adr_dir()
    all_actions: list[dict] = []
    all_changes: list[str] = []
    created_adr_numbers: list[int] = []

    # -----------------------------------------------------------------------
    # d1: Create missing ADRs from orphan designs
    # -----------------------------------------------------------------------
    if ctx.difficulty >= 1:
        orphan_issues = [i for i in issues if i.get("orphan_type") == "design-doc"]
        for issue in orphan_issues:
            plan_path = Path(issue["path"])
            classification, _ = classify_fix("structural", str(plan_path), ctx.project_root)
            if classification == FixClassification.MODIFIED:
                continue  # Skip — user recently modified this design doc

            adr_path = _create_adr_from_design(plan_path, adr_dir)
            if adr_path:
                adr_num = parse_adr_number(adr_path.name)
                if adr_num:
                    created_adr_numbers.append(adr_num)
                all_changes.append(f"Created {adr_path.name} from {plan_path.name}")
                all_actions.append({"created_adr": str(adr_path)})

        # Commit new ADRs + run post-hooks
        if created_adr_numbers:
            adr_paths = [
                str(p.relative_to(ctx.project_root))
                for p in adr_dir.glob("ADR-*.md")
                if parse_adr_number(p.name) in created_adr_numbers
            ]
            _run_post_hooks(ctx.project_root)
            sha = _commit_files(
                ctx.project_root,
                f"feat(adaptive): create {len(created_adr_numbers)} ADR(s) from orphan designs",
                adr_paths + ["docs/generated/adr-index.md"],
            )
            if sha:
                all_actions.append({"commit": sha})

    # -----------------------------------------------------------------------
    # d1: Write reports (orphan plans + gap analysis placeholder)
    # -----------------------------------------------------------------------
    if ctx.difficulty >= 1:
        report_dir = ctx.project_root / "docs" / "generated"
        report_dir.mkdir(parents=True, exist_ok=True)

        # Orphan plans report
        orphan_issues = [i for i in issues if i.get("orphan_type") == "design-doc"]
        if orphan_issues:
            report_file = report_dir / "orphan-plans-report.md"
            lines = [
                "# Orphan Plans Report",
                "",
                "Design documents in the vault `dev/plans/` not referenced by any ADR.",
                "",
                "| Plan File | Suggested ADR Title |",
                "|-----------|-------------------|",
            ]
            for issue in orphan_issues:
                lines.append(f"| `{issue['path']}` | {issue.get('suggested_adr_title', 'Unknown')} |")
            lines.append("")
            report_file.write_text("\n".join(lines), encoding="utf-8")
            all_changes.append("Updated orphan-plans-report.md")

    fix_type = "sync" if created_adr_numbers else "report"
    summary_parts = []
    if created_adr_numbers:
        summary_parts.append(f"{len(created_adr_numbers)} ADR(s) created")
    summary_parts.append(f"{len(issues)} issue(s) processed")

    return FixResult(
        success=True,
        actions=all_actions,
        changes=all_changes,
        summary="; ".join(summary_parts),
        fix_type=fix_type,
    )
```

Add the missing import at the top:

```python
from src.lib.adr_utils import (
    detect_stale_status,
    find_next_adr_number,
    get_adr_dir,
    parse_adr_number,
    scan_adrs,
)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-adr-lifecycle/scripts/
git commit -m "feat(auto-adr-lifecycle): fix() d1 — create ADRs from orphan designs"
```

---

### Task 5: Write fix() — d1 gap analysis and reports

**Files:**
- Modify: `skills/auto-adr-lifecycle/scripts/adr_lifecycle_ops.py`
- Modify: `skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py`

- [ ] **Step 1: Write failing test for d1 gap analysis**

Append to `test_adr_lifecycle_ops.py`:

```python
class TestFixD1GapAnalysis:
    def test_gap_report_written(self, ctx: OpsContext, vault_dirs):
        plans_dir, adr_dir = vault_dirs
        # Create an ADR with references to nonexistent files
        (adr_dir / "ADR-300-feature.md").write_text(
            "---\nstatus: Accepted\ndate: '2026-03-20'\n---\n"
            "# ADR-300: Feature\n\n## Decision\n\n"
            "Create `src/lib/missing_module.py`.\n"
            "Create `src/lib/another_missing.py`.\n"
        )
        ctx_d1 = OpsContext(project_root=ctx.project_root, difficulty=1)

        # Issues include an impl-gap from scan
        issues = [
            {
                "category": "adr-lifecycle",
                "kind": "actionable",
                "orphan_type": "impl-gap",
                "adr_number": 300,
                "gap_count": 2,
                "total_artifacts": 2,
                "path": str(adr_dir / "ADR-300-feature.md"),
                "detail": "Potential implementation gaps: Feature",
            }
        ]

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ), patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops._commit_files",
            return_value="def5678",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import fix

            result = fix(ctx_d1, issues)
            assert result.success
            # Check gap report was written
            gap_report = ctx.project_root / "docs" / "generated" / "adr-gaps-report.md"
            assert gap_report.exists()
            content = gap_report.read_text()
            assert "ADR-300" in content
            assert "missing_module" in content or "Feature" in content
```

- [ ] **Step 2: Run test — expect failure**

```bash
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py::TestFixD1GapAnalysis -v
```

Expected: FAIL

- [ ] **Step 3: Add d1 full gap analysis to fix()**

Add this function to `adr_lifecycle_ops.py`:

```python
def _full_gap_analysis(adr_dir: Path, project_root: Path, adr_numbers: list[int] | None = None) -> list[dict]:
    """Run full gap analysis on target ADRs.

    Targets: specific adr_numbers (if given) + all Accepted ADRs from last 30 days.
    Returns list of gap detail dicts.
    """
    adrs = scan_adrs(adr_dir)
    now = datetime.now(timezone.utc).timestamp()
    thirty_days_ago = now - (30 * 86400)
    target_numbers = set(adr_numbers or [])

    gaps: list[dict] = []
    for adr in adrs:
        adr_path = adr_dir / adr["filename"]
        if not adr_path.exists():
            continue
        # Include if: in explicit target list, or Accepted + recent
        is_target = adr["number"] in target_numbers
        is_recent_accepted = (
            adr["status"] == "Accepted"
            and adr_path.stat().st_mtime >= thirty_days_ago
        )
        if not is_target and not is_recent_accepted:
            continue

        content = adr_path.read_text(encoding="utf-8")
        artifacts = _extract_expected_artifacts(content)
        if not artifacts:
            continue

        missing_artifacts: list[str] = []
        for artifact in artifacts:
            if artifact.startswith("/api/"):
                route_path = project_root / "apps" / "dashboard" / "app" / artifact.lstrip("/") / "route.ts"
                if not route_path.exists():
                    missing_artifacts.append(artifact)
            else:
                if not (project_root / artifact).exists():
                    missing_artifacts.append(artifact)

        if missing_artifacts:
            # Severity based on ratio
            ratio = len(missing_artifacts) / len(artifacts)
            if ratio > 0.75:
                severity = "Critical"
            elif ratio > 0.5:
                severity = "High"
            else:
                severity = "Medium"
            gaps.append({
                "adr_number": adr["number"],
                "adr_title": adr["title"],
                "adr_path": str(adr_path),
                "total_artifacts": len(artifacts),
                "missing_artifacts": missing_artifacts,
                "missing_count": len(missing_artifacts),
                "severity": severity,
            })

    # Sort by severity
    severity_order = {"Critical": 0, "High": 1, "Medium": 2}
    gaps.sort(key=lambda g: severity_order.get(g["severity"], 99))
    return gaps


def _write_gap_report(gaps: list[dict], report_dir: Path) -> Path:
    """Write adr-gaps-report.md from gap analysis results."""
    report_file = report_dir / "adr-gaps-report.md"
    lines = [
        "# ADR Gaps Report",
        "",
        f"**{len(gaps)} ADR(s) with implementation gaps**",
        "",
    ]
    if gaps:
        # Summary table
        by_severity = {}
        for g in gaps:
            by_severity[g["severity"]] = by_severity.get(g["severity"], 0) + 1
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for sev in ["Critical", "High", "Medium"]:
            if sev in by_severity:
                lines.append(f"| {sev} | {by_severity[sev]} |")
        lines.append("")

        # Per-ADR detail
        for gap in gaps:
            lines.append(f"### ADR-{gap['adr_number']}: {gap['adr_title']}")
            lines.append("")
            lines.append(f"**Severity:** {gap['severity']} ({gap['missing_count']}/{gap['total_artifacts']} missing)")
            lines.append("")
            lines.append("Missing artifacts:")
            for art in gap["missing_artifacts"]:
                lines.append(f"- `{art}`")
            lines.append("")
    else:
        lines.append("No implementation gaps found.")

    lines.append("")
    report_file.write_text("\n".join(lines), encoding="utf-8")
    return report_file
```

Update `fix()` — add gap analysis after ADR creation, before report writing. Insert this block inside fix() after the ADR creation block and before the report writing block:

```python
    # -----------------------------------------------------------------------
    # d1: Full gap analysis
    # -----------------------------------------------------------------------
    gap_details: list[dict] = []
    if ctx.difficulty >= 1:
        gap_details = _full_gap_analysis(adr_dir, ctx.project_root, created_adr_numbers or None)

    # -----------------------------------------------------------------------
    # d1: Write reports
    # -----------------------------------------------------------------------
    if ctx.difficulty >= 1:
        report_dir = ctx.project_root / "docs" / "generated"
        report_dir.mkdir(parents=True, exist_ok=True)

        # Orphan plans report
        orphan_issues = [i for i in issues if i.get("orphan_type") == "design-doc"]
        if orphan_issues:
            report_file = report_dir / "orphan-plans-report.md"
            lines = [
                "# Orphan Plans Report",
                "",
                "Design documents in the vault `dev/plans/` not referenced by any ADR.",
                "",
                "| Plan File | Suggested ADR Title |",
                "|-----------|-------------------|",
            ]
            for issue in orphan_issues:
                lines.append(f"| `{issue['path']}` | {issue.get('suggested_adr_title', 'Unknown')} |")
            lines.append("")
            report_file.write_text("\n".join(lines), encoding="utf-8")
            all_changes.append("Updated orphan-plans-report.md")

        # Gap analysis report
        gap_report_path = _write_gap_report(gap_details, report_dir)
        all_changes.append("Updated adr-gaps-report.md")
        all_actions.append({"gap_report": str(gap_report_path), "gap_count": len(gap_details)})

        # Commit reports
        report_paths = ["docs/generated/orphan-plans-report.md", "docs/generated/adr-gaps-report.md"]
        sha = _commit_files(
            ctx.project_root,
            "docs(adaptive): update ADR lifecycle reports",
            [p for p in report_paths if (ctx.project_root / p).exists()],
        )
        if sha:
            all_actions.append({"commit": sha})
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-adr-lifecycle/scripts/
git commit -m "feat(auto-adr-lifecycle): fix() d1 — gap analysis and report generation"
```

---

### Task 6: Write fix() — d2 implementation in worktrees

**Files:**
- Modify: `skills/auto-adr-lifecycle/scripts/adr_lifecycle_ops.py`
- Modify: `skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py`

- [ ] **Step 1: Write failing test for d2 worktree implementation**

Append to `test_adr_lifecycle_ops.py`:

```python
class TestFixD2Implement:
    def test_skips_without_llm(self, ctx: OpsContext, vault_dirs):
        """d2 without LLM session should skip implementation and report manual."""
        plans_dir, adr_dir = vault_dirs
        from src.lib.ops_protocol import SessionContext

        ctx_d2 = OpsContext(
            project_root=ctx.project_root,
            difficulty=2,
            session=SessionContext(has_llm=False),
        )

        issues = [
            {
                "category": "adr-lifecycle",
                "orphan_type": "impl-gap",
                "adr_number": 300,
                "gap_count": 2,
                "path": str(adr_dir / "ADR-300-feature.md"),
                "detail": "Potential implementation gaps: Feature",
            }
        ]

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ), patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops._commit_files",
            return_value=None,
        ), patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops._full_gap_analysis",
            return_value=[],
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import fix

            result = fix(ctx_d2, issues)
            assert result.success
            # Should not attempt implementation without LLM
            assert result.fix_type != "code-fix"

    def test_d2_with_llm_attempts_implementation(self, ctx: OpsContext, vault_dirs):
        """d2 with LLM session should attempt worktree implementation."""
        plans_dir, adr_dir = vault_dirs
        from src.lib.ops_protocol import SessionContext

        (adr_dir / "ADR-400-thing.md").write_text(
            "---\nstatus: Accepted\ndate: '2026-03-20'\n---\n"
            "# ADR-400: Thing\n\n## Decision\n\nCreate `src/lib/thing.py`.\n"
        )
        ctx_d2 = OpsContext(
            project_root=ctx.project_root,
            difficulty=2,
            session=SessionContext(has_llm=True, cli_path="/usr/bin/claude", cli_name="claude"),
        )

        # Simulate gap analysis returning gaps
        mock_gaps = [
            {
                "adr_number": 400,
                "adr_title": "Thing",
                "adr_path": str(adr_dir / "ADR-400-thing.md"),
                "total_artifacts": 1,
                "missing_artifacts": ["src/lib/thing.py"],
                "missing_count": 1,
                "severity": "Critical",
            }
        ]

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ), patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops._commit_files",
            return_value=None,
        ), patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops._full_gap_analysis",
            return_value=mock_gaps,
        ), patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops._implement_gap_in_worktree",
            return_value={"success": True, "branch": "adr-400-thing", "merged": True},
        ) as mock_impl:
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import fix

            result = fix(ctx_d2, [])
            assert result.fix_type == "code-fix"
            mock_impl.assert_called_once()
```

- [ ] **Step 2: Run tests — expect failures**

```bash
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py::TestFixD2Implement -v
```

- [ ] **Step 3: Implement d2 worktree implementation**

Add to `adr_lifecycle_ops.py`:

```python
def _implement_gap_in_worktree(
    gap: dict,
    project_root: Path,
    session: "SessionContext",
) -> dict:
    """Implement a single ADR gap in an isolated git worktree.

    Creates worktree, runs LLM CLI to implement missing artifacts,
    runs completion gates, merges on success.

    Returns dict with keys: success, branch, merged, error.
    """
    adr_num = gap["adr_number"]
    slug = _slugify(gap.get("adr_title", "unknown"))
    branch_name = f"adr-{adr_num}-{slug}"
    worktree_path = project_root / ".worktrees" / branch_name

    # Check if worktree already exists (idempotency)
    if worktree_path.exists():
        return {"success": False, "branch": branch_name, "merged": False, "error": "Worktree already exists"}

    try:
        # Create worktree
        subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            check=True,
        )

        # Build implementation prompt
        missing_list = "\n".join(f"- `{a}`" for a in gap["missing_artifacts"])
        prompt = (
            f"Implement the missing artifacts for ADR-{adr_num} ({gap['adr_title']}).\n\n"
            f"ADR file: {gap['adr_path']}\n\n"
            f"Missing artifacts:\n{missing_list}\n\n"
            f"Requirements:\n"
            f"1. Read the full ADR for context\n"
            f"2. Implement each missing artifact\n"
            f"3. Add tests for new code\n"
            f"4. Run `npm run build` if TypeScript files changed\n"
            f"5. Commit all changes\n"
        )

        # Run LLM CLI in worktree
        cli = session.cli_path or "claude"
        result = subprocess.run(
            [cli, "--print", "--dangerously-skip-permissions", "-m", prompt],
            capture_output=True,
            text=True,
            cwd=str(worktree_path),
            timeout=session.timeout,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "branch": branch_name,
                "merged": False,
                "error": f"CLI exited {result.returncode}: {result.stderr[:200]}",
            }

        # Check if there are actual commits in the worktree branch
        diff_result = subprocess.run(
            ["git", "log", "main.." + branch_name, "--oneline"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        if not diff_result.stdout.strip():
            return {"success": False, "branch": branch_name, "merged": False, "error": "No commits produced"}

        # Auto-merge to main
        merge_result = subprocess.run(
            ["git", "merge", branch_name, "--no-ff", "-m", f"feat(adaptive): implement ADR-{adr_num} gaps"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        merged = merge_result.returncode == 0

        # Cleanup worktree on successful merge
        if merged:
            subprocess.run(
                ["git", "worktree", "remove", str(worktree_path)],
                capture_output=True,
                cwd=str(project_root),
            )
            subprocess.run(
                ["git", "branch", "-d", branch_name],
                capture_output=True,
                cwd=str(project_root),
            )

        return {"success": merged, "branch": branch_name, "merged": merged, "error": None}

    except subprocess.TimeoutExpired:
        return {"success": False, "branch": branch_name, "merged": False, "error": "Timeout"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "branch": branch_name, "merged": False, "error": str(e)}
```

Update `fix()` — add d2 block after gap analysis and before the summary:

```python
    # -----------------------------------------------------------------------
    # d2: Implement gaps in worktrees
    # -----------------------------------------------------------------------
    implemented_count = 0
    manual_count = 0
    if ctx.difficulty >= 2 and gap_details:
        if not ctx.session.has_llm:
            # No LLM available — report all gaps as manual
            for gap in gap_details:
                all_actions.append({
                    "manual_gap": f"ADR-{gap['adr_number']}: {gap['missing_count']} missing artifacts (no LLM)",
                })
            manual_count = len(gap_details)
        else:
            for gap in gap_details:
                impl_result = _implement_gap_in_worktree(gap, ctx.project_root, ctx.session)
                if impl_result["success"] and impl_result["merged"]:
                    implemented_count += 1
                    all_actions.append({
                        "implemented": f"ADR-{gap['adr_number']}",
                        "branch": impl_result["branch"],
                    })
                    all_changes.append(f"Implemented ADR-{gap['adr_number']} gaps (merged)")
                else:
                    manual_count += 1
                    all_actions.append({
                        "manual_gap": f"ADR-{gap['adr_number']}: {impl_result.get('error', 'unknown')}",
                        "branch": impl_result["branch"],
                    })

            # Update gap report with implementation status
            if implemented_count > 0 and ctx.difficulty >= 1:
                report_dir = ctx.project_root / "docs" / "generated"
                _write_gap_report(
                    [g for g in gap_details if not any(
                        a.get("implemented") == f"ADR-{g['adr_number']}" for a in all_actions
                    )],
                    report_dir,
                )

            # Evolution gap
            if implemented_count == len(gap_details) and not gap_details:
                all_actions.append(
                    evolution_gap(
                        "All recent ADR gaps resolved. Consider: expanding scan window "
                        "beyond 30 days, adding code-drift detection for Implemented ADRs, "
                        "detecting undocumented architectural decisions from code patterns.",
                        category="adr-lifecycle",
                    )
                )
```

Update the summary at the end of `fix()`:

```python
    fix_type = "code-fix" if implemented_count > 0 else ("sync" if created_adr_numbers else "report")
    summary_parts = []
    if created_adr_numbers:
        summary_parts.append(f"{len(created_adr_numbers)} ADR(s) created")
    if gap_details:
        summary_parts.append(f"{len(gap_details)} gap(s) found")
    if implemented_count:
        summary_parts.append(f"{implemented_count} gap(s) implemented")
    if manual_count:
        summary_parts.append(f"{manual_count} gap(s) need manual attention")
    if not summary_parts:
        summary_parts.append(f"{len(issues)} issue(s) processed")

    return FixResult(
        success=True,
        actions=all_actions,
        changes=all_changes,
        summary="; ".join(summary_parts),
        fix_type=fix_type,
    )
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-adr-lifecycle/scripts/
git commit -m "feat(auto-adr-lifecycle): fix() d2 — implement gaps in worktrees with auto-merge"
```

---

### Task 7: Delete auto-orphan-plans and update references

**Files:**
- Delete: `skills/auto-orphan-plans/` (entire directory)
- Delete: `skills/ai/scripts/ops/orphan_plans.py`

- [ ] **Step 1: Check for references to auto-orphan-plans**

```bash
cd ~/Projects/Augur
grep -rn "auto-orphan-plans\|orphan_plans" --include='*.py' --include='*.ts' --include='*.yaml' --include='*.md' | grep -v "node_modules" | grep -v ".git/" | grep -v "auto-adr-lifecycle"
```

Record all files that reference the old skill for updating.

- [ ] **Step 2: Delete the old skill directory and ops module**

```bash
rm -rf skills/auto-orphan-plans/
rm -f skills/ai/scripts/ops/orphan_plans.py
```

- [ ] **Step 3: Update any references found in Step 1**

For each file that references `auto-orphan-plans` or `orphan_plans`:
- Replace references to `auto-orphan-plans` with `auto-adr-lifecycle`
- Replace references to `knowledge-enrichment` loop (for this module) with `hardening` loop
- Remove any import of `orphan_plans` from `__init__.py` or registry files

- [ ] **Step 4: Verify no stale references remain**

```bash
grep -rn "auto-orphan-plans\|orphan_plans" --include='*.py' --include='*.ts' --include='*.yaml' --include='*.md' | grep -v "node_modules" | grep -v ".git/" | grep -v "auto-adr-lifecycle" | grep -v "CHANGELOG\|adr-gaps-report\|orphan-plans-report"
```

Expected: No results (or only historical references in changelogs/ADRs)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(adaptive): delete auto-orphan-plans, replaced by auto-adr-lifecycle"
```

---

### Task 8: Integration test — run the full loop

**Files:**
- Modify: `skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py`

- [ ] **Step 1: Write integration test**

Append to `test_adr_lifecycle_ops.py`:

```python
class TestFullLoop:
    """Integration test: scan → fix at each difficulty level."""

    def test_d0_scan_only(self, ctx: OpsContext, vault_dirs):
        plans_dir, adr_dir = vault_dirs
        (plans_dir / "2026-01-01-alpha-design.md").write_text("# Alpha Design\n")
        ctx_d0 = OpsContext(project_root=ctx.project_root, difficulty=0)

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import fix, scan

            result = scan(ctx_d0)
            assert len(result.issues) >= 1

            # At d0, fix should just report
            fix_result = fix(ctx_d0, result.issues)
            assert fix_result.success
            # No ADRs should be created at d0
            assert list(adr_dir.glob("ADR-*.md")) == []

    def test_d1_creates_and_analyzes(self, ctx: OpsContext, vault_dirs):
        plans_dir, adr_dir = vault_dirs
        (plans_dir / "2026-01-01-beta-design.md").write_text(
            "# Beta Design\n\n## Context\n\nNeed beta.\n\n## Decision\n\nBuild beta.\n"
        )
        ctx_d1 = OpsContext(project_root=ctx.project_root, difficulty=1)

        with patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops.get_vault_dir",
            return_value=ctx.project_root / "vault",
        ), patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops._commit_files",
            return_value="abc1234",
        ), patch(
            "skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops._run_post_hooks",
        ):
            from skills.auto_adr_lifecycle.scripts.adr_lifecycle_ops import fix, scan

            result = scan(ctx_d1)
            orphans = [i for i in result.issues if i.get("orphan_type") == "design-doc"]
            assert len(orphans) == 1

            fix_result = fix(ctx_d1, result.issues)
            assert fix_result.success
            # ADR should be created
            adr_files = list(adr_dir.glob("ADR-*.md"))
            assert len(adr_files) == 1
            # Gap report should exist
            assert (ctx.project_root / "docs" / "generated" / "adr-gaps-report.md").exists()
```

- [ ] **Step 2: Run integration tests**

```bash
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py::TestFullLoop -v
```

Expected: All tests PASS

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add skills/auto-adr-lifecycle/scripts/test_adr_lifecycle_ops.py
git commit -m "test(auto-adr-lifecycle): integration tests for full scan → fix loop"
```

---

### Task 9: Final verification and cleanup

- [ ] **Step 1: Verify skill structure matches convention**

```bash
ls -la skills/auto-adr-lifecycle/
ls -la skills/auto-adr-lifecycle/scripts/
ls -la skills/auto-adr-lifecycle/augur/
```

Expected structure:
```
skills/auto-adr-lifecycle/
├── SKILL.md
├── scripts/
│   ├── adr_lifecycle_ops.py
│   └── test_adr_lifecycle_ops.py
└── augur/
    └── dashboard/
```

- [ ] **Step 2: Verify auto-orphan-plans is fully removed**

```bash
ls skills/auto-orphan-plans/ 2>&1
ls skills/ai/scripts/ops/orphan_plans.py 2>&1
```

Expected: Both should return "No such file or directory"

- [ ] **Step 3: Run all project tests to check for regressions**

```bash
python -m pytest skills/ -v --timeout=60 2>&1 | tail -20
```

Expected: No failures related to orphan_plans or auto-adr-lifecycle

- [ ] **Step 4: Verify SKILL.md frontmatter parses correctly**

```bash
python -c "
from src.lib.frontmatter_utils import parse_frontmatter
from pathlib import Path
meta, body = parse_frontmatter(Path('skills/auto-adr-lifecycle/SKILL.md'))
print('name:', meta.get('name'))
print('type:', meta.get('x-augur-type'))
print('loop:', meta.get('x-augur-loop'))
print('callable:', meta.get('x-augur-callable'))
"
```

Expected output:
```
name: auto-adr-lifecycle
type: autoloop
loop: {'name': 'hardening', 'tier': 3, 'trigger': 'nightly'}
callable: scripts/adr_lifecycle_ops.py
```

- [ ] **Step 5: Final commit if any cleanup was needed**

```bash
git add -A
git status
# Only commit if there are changes
git diff --cached --quiet || git commit -m "chore(auto-adr-lifecycle): final cleanup and verification"
```
