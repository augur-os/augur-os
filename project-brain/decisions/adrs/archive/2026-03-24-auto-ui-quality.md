# Auto UI Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a nightly autoloop that scores all dashboard pages for UI/UX quality and progressively auto-fixes issues from safe code patches (d2) to LLM-assisted page redesigns (d3-d4).

**Architecture:** New `auto-ui-quality` skill with `scan()`/`fix()` protocol. Checks defined in YAML registry, scored across 4 weighted dimensions. Page score registry persisted to runtime dir. Git safety net reverts on build failure or score regression. LLM escalation at d3+ uses Playwright screenshots + ui-ux-pro-max design intelligence.

**Tech Stack:** Python 3.11+, ops_protocol (ScanResult/FixResult/OpsContext), YAML check registry, Playwright (d3-d4), subprocess for build verification

**Spec:** `docs/superpowers/specs/2026-03-24-auto-ui-quality-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `skills/auto-ui-quality/SKILL.md` | Frontmatter + overview |
| `skills/auto-ui-quality/scripts/ui_quality.py` | Entrypoint: `scan()`, `fix()`, `DIFFICULTY_SPEC` |
| `skills/auto-ui-quality/scripts/checks.py` | d0-d1 check functions (static TSX analysis) |
| `skills/auto-ui-quality/scripts/scorer.py` | Page scoring: weighted dimension scores, registry persistence |
| `skills/auto-ui-quality/scripts/fixers.py` | d2 safe auto-fixes + d3-d4 git safety net |
| `skills/auto-ui-quality/scripts/visual.py` | d3-d4 Playwright screenshots + LLM prompt assembly |
| `skills/auto-ui-quality/augur/data/check_registry.yaml` | All check definitions with confidence/dimension/weight |
| `skills/auto-ui-quality/augur/tests/test_checks.py` | Unit tests for d0-d1 checks |
| `skills/auto-ui-quality/augur/tests/test_scorer.py` | Unit tests for scoring logic |
| `skills/auto-ui-quality/augur/tests/test_fixers.py` | Unit tests for d2 fixers |
| `skills/auto-ui-quality/assets/seeds/_seed.yaml` | Seed data manifest |
| `config/system/adaptive_loops.yaml` | Add `ui-quality` loop entry |

---

### Task 1: Scaffold Skill Directory + Config

**Files:**
- Create: `skills/auto-ui-quality/SKILL.md`
- Create: `skills/auto-ui-quality/assets/seeds/_seed.yaml`
- Create: `skills/auto-ui-quality/references/.gitkeep`
- Modify: `config/system/adaptive_loops.yaml`

- [ ] **Step 1: Create skill directory structure**

```bash
mkdir -p skills/auto-ui-quality/{scripts,augur/{tests,data},assets/seeds,references}
```

- [ ] **Step 2: Write SKILL.md with frontmatter**

Create `skills/auto-ui-quality/SKILL.md`:

```markdown
---
name: auto-ui-quality
x-augur-type: autoloop
x-augur-tags: [ui, ux, accessibility, design-system]
description: 'Nightly UI/UX quality audit — scores pages across accessibility, interaction, design system, and responsiveness; auto-fixes at d2+ with git safety'
x-augur-visibility: auto
x-augur-loop:
  name: ui-quality
  tier: 2
  trigger: nightly
  config:
    scan_timeout: 120
    fix_timeout: 300
    max_turns: 20
    max_page_rewrites: 3
    d2_fix_limit: 10
    d3_analysis_limit: 3
x-augur-hub: adaptive
x-augur-tab: code-quality
x-augur-evolution:
  last_updated: 2026-03-24
  improvements_applied: 0
---

# auto-ui-quality

Nightly UI/UX quality audit autoloop. Scans all dashboard pages for accessibility,
interaction, design system, and responsiveness issues. Auto-fixes safe issues at d2,
uses Playwright screenshots + LLM analysis at d3-d4 for visual redesigns.

## Difficulty Levels

| Level | Name | Scope |
|-------|------|-------|
| d0 | Inventory | Count issues: aria-labels, cursor-pointer, hardcoded colors, emoji |
| d1 | Pattern check | Transitions, icon imports, responsive classes, motion-reduce |
| d2 | Safe auto-fix | Apply high-confidence fixes with build verification |
| d3 | Visual analysis | Playwright screenshots + LLM audit + targeted fixes |
| d4 | Full redesign | Structural page rewrites with git safety net |

## Priority Algorithm

1. d0-d1: Scan ALL pages every night
2. d2: Fix top 10 lowest-scoring pages
3. d3-d4: Bottom 3 by score + recently changed pages
```

- [ ] **Step 3: Create seed manifest**

Create `skills/auto-ui-quality/assets/seeds/_seed.yaml`:

```yaml
seed_version: 1
files: []
```

- [ ] **Step 4: Create references placeholder**

```bash
touch skills/auto-ui-quality/references/.gitkeep
```

- [ ] **Step 5: Add ui-quality loop to adaptive_loops.yaml**

In `config/system/adaptive_loops.yaml`, add after the `skill-quality` entry:

```yaml
  ui-quality:
    budget: 10
    budget_growth_rate: 2
```

- [ ] **Step 6: Commit scaffold**

```bash
git add skills/auto-ui-quality/ config/system/adaptive_loops.yaml
git commit -m "feat(auto-ui-quality): scaffold skill directory and register ui-quality loop"
```

---

### Task 2: Check Registry

**Files:**
- Create: `skills/auto-ui-quality/augur/data/check_registry.yaml`

- [ ] **Step 1: Write check registry with all d0-d1 checks**

Create `skills/auto-ui-quality/augur/data/check_registry.yaml`:

```yaml
# UI Quality Check Registry
# Each check defines: id, dimension, difficulty, confidence, weight, pattern, description
# Confidence: high (1.0x), medium (0.75x), low (0.5x)

checks:
  # ── d0: High-confidence inventory checks ────────────────────────

  - id: cursor-pointer-on-click
    dimension: interaction
    difficulty: 0
    confidence: high
    description: "onClick handlers must have cursor-pointer class"
    pattern: 'onClick\s*='
    negative_pattern: 'cursor-pointer'
    scope: element  # check that the element or its className contains the negative pattern

  - id: hardcoded-hex-color
    dimension: design_system
    difficulty: 0
    confidence: high
    description: "Use CSS vars instead of hardcoded hex/rgb colors in className"
    pattern: '(?:className|style).*?(?:#[0-9a-fA-F]{3,8}|rgb\(|rgba\()'
    exclude_pattern: '(?:bg-gradient|from-|to-|via-)'  # tailwind gradient classes use color names

  - id: aria-label-icon-button
    dimension: accessibility
    difficulty: 0
    confidence: high
    description: "Icon-only buttons must have aria-label"
    pattern: '<button[^>]*>[\s]*<(?:[\w]+Icon|Lucide|svg)[^>]*/>[\s]*</button>'
    negative_pattern: 'aria-label'
    scope: element

  - id: emoji-in-jsx
    dimension: design_system
    difficulty: 0
    confidence: high
    description: "No emoji characters in JSX — use SVG icons from Lucide"
    pattern: '[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]'

  # ── d1: Medium-confidence pattern checks ────────────────────────

  - id: transition-duration-range
    dimension: interaction
    difficulty: 1
    confidence: medium
    description: "Transition durations should be 150-300ms"
    pattern: 'duration-(\d+)'
    valid_range: [150, 300]
    exclude_values: [0]  # duration-0 is intentional (disable)

  - id: non-lucide-icon-import
    dimension: design_system
    difficulty: 1
    confidence: medium
    description: "Icon imports should come from lucide-react"
    pattern: "import.*(?:Icon|Icons).*from\\s+'\""

  - id: missing-responsive-breakpoint
    dimension: responsiveness
    difficulty: 1
    confidence: medium
    description: "Grid/flex containers should have responsive breakpoint classes"
    pattern: 'className=.*(?:grid-cols-|flex\s)(?!.*(?:md:|lg:|sm:))'

  - id: animate-without-motion-reduce
    dimension: interaction
    difficulty: 1
    confidence: medium
    description: "animate-* classes should have motion-reduce variant nearby"
    pattern: 'animate-(?!none)'
    negative_pattern: 'motion-reduce'
    scope: file  # check entire file for the negative pattern

  # ── d0-d1: Low-confidence checks (weighted 0.5x) ───────────────

  - id: touch-target-size
    dimension: interaction
    difficulty: 0
    confidence: low
    description: "Interactive elements should have min-h-[44px] or equivalent"
    pattern: '<button[^>]*(?:onClick)'
    negative_pattern: 'min-h-\[4[4-9]px\]|min-h-\[[5-9]\d+px\]|h-1[0-2]|p-[3-9]'
    scope: element

  - id: prefers-reduced-motion
    dimension: responsiveness
    difficulty: 1
    confidence: low
    description: "Files with animations should respect prefers-reduced-motion"
    pattern: 'animate-(?!none)|transition-'
    negative_pattern: 'motion-reduce|prefers-reduced-motion'
    scope: file

# Dimension weights for scoring
dimensions:
  accessibility:
    weight: 0.30
  interaction:
    weight: 0.25
  design_system:
    weight: 0.25
  responsiveness:
    weight: 0.20

# Confidence multipliers
confidence_weights:
  high: 1.0
  medium: 0.75
  low: 0.5
```

- [ ] **Step 2: Commit check registry**

```bash
git add skills/auto-ui-quality/augur/data/check_registry.yaml
git commit -m "feat(auto-ui-quality): add check registry with d0-d1 checks across 4 dimensions"
```

---

### Task 3: Check Functions (d0-d1 Static Analysis)

**Files:**
- Create: `skills/auto-ui-quality/augur/tests/test_checks.py`
- Create: `skills/auto-ui-quality/scripts/checks.py`

- [ ] **Step 1: Write failing tests for d0 checks**

Create `skills/auto-ui-quality/augur/tests/test_checks.py`:

```python
"""Tests for d0-d1 UI quality checks."""
from __future__ import annotations

import pytest
from pathlib import Path

# Inline TSX snippets for testing
GOOD_BUTTON = '<button onClick={() => doThing()} className="cursor-pointer px-4 py-2 min-h-[44px]" aria-label="Do thing"><Play className="w-4 h-4" /></button>'
BAD_BUTTON_NO_CURSOR = '<button onClick={() => doThing()} className="px-4 py-2"><Play className="w-4 h-4" /></button>'
BAD_BUTTON_NO_ARIA = '<button onClick={() => doThing()} className="cursor-pointer"><Play className="w-4 h-4" /></button>'
HARDCODED_COLOR = 'className="bg-[#ff0000] text-white"'
CSS_VAR_COLOR = 'className="bg-[var(--accent-danger)] text-[var(--text-primary)]"'
EMOJI_JSX = '<span>Settings ⚙️</span>'
NO_EMOJI_JSX = '<span><Settings className="w-4 h-4" /> Settings</span>'
GOOD_TRANSITION = 'className="transition-colors duration-200"'
BAD_TRANSITION = 'className="transition-colors duration-500"'
LUCIDE_IMPORT = "import { Play, Settings } from 'lucide-react';"
NON_LUCIDE_IMPORT = "import { FaPlay } from 'react-icons/fa';"
RESPONSIVE_GRID = 'className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3"'
NON_RESPONSIVE_GRID = 'className="grid grid-cols-3"'


def test_check_cursor_pointer_on_click():
    from scripts.checks import check_cursor_pointer_on_click
    assert check_cursor_pointer_on_click(GOOD_BUTTON) == []
    issues = check_cursor_pointer_on_click(BAD_BUTTON_NO_CURSOR)
    assert len(issues) == 1
    assert issues[0]["check_id"] == "cursor-pointer-on-click"


def test_check_hardcoded_colors():
    from scripts.checks import check_hardcoded_colors
    assert check_hardcoded_colors(CSS_VAR_COLOR) == []
    issues = check_hardcoded_colors(HARDCODED_COLOR)
    assert len(issues) == 1
    assert issues[0]["check_id"] == "hardcoded-hex-color"


def test_check_emoji_in_jsx():
    from scripts.checks import check_emoji_in_jsx
    assert check_emoji_in_jsx(NO_EMOJI_JSX) == []
    issues = check_emoji_in_jsx(EMOJI_JSX)
    assert len(issues) == 1
    assert issues[0]["check_id"] == "emoji-in-jsx"


def test_check_aria_label_icon_button():
    from scripts.checks import check_aria_label_icon_button
    assert check_aria_label_icon_button(GOOD_BUTTON) == []
    issues = check_aria_label_icon_button(BAD_BUTTON_NO_ARIA)
    assert len(issues) == 1


def test_check_transition_duration():
    from scripts.checks import check_transition_duration
    assert check_transition_duration(GOOD_TRANSITION) == []
    issues = check_transition_duration(BAD_TRANSITION)
    assert len(issues) == 1
    assert issues[0]["check_id"] == "transition-duration-range"


def test_check_non_lucide_import():
    from scripts.checks import check_non_lucide_import
    assert check_non_lucide_import(LUCIDE_IMPORT) == []
    issues = check_non_lucide_import(NON_LUCIDE_IMPORT)
    assert len(issues) == 1


def test_check_responsive_breakpoints():
    from scripts.checks import check_responsive_breakpoints
    assert check_responsive_breakpoints(RESPONSIVE_GRID) == []
    issues = check_responsive_breakpoints(NON_RESPONSIVE_GRID)
    assert len(issues) == 1


def test_run_all_checks_returns_scored_result():
    from scripts.checks import run_all_checks
    content = f"""
    {LUCIDE_IMPORT}
    export default function Page() {{
      return (
        <div>
          {BAD_BUTTON_NO_CURSOR}
          {HARDCODED_COLOR}
        </div>
      );
    }}
    """
    result = run_all_checks(content, "test/page.tsx", difficulty=0)
    assert "issues" in result
    assert "applicable" in result
    assert "passing" in result
    assert len(result["issues"]) >= 2  # cursor-pointer + hardcoded color
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest skills/auto-ui-quality/augur/tests/test_checks.py -v 2>&1 | head -30
```

Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.checks'`

- [ ] **Step 3: Implement check functions**

Create `skills/auto-ui-quality/scripts/checks.py`:

```python
"""d0-d1 UI quality check functions — static TSX analysis."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_REGISTRY: list[dict] | None = None
_CONFIDENCE_WEIGHTS: dict[str, float] = {"high": 1.0, "medium": 0.75, "low": 0.5}
_DIMENSION_WEIGHTS: dict[str, float] = {
    "accessibility": 0.30,
    "interaction": 0.25,
    "design_system": 0.25,
    "responsiveness": 0.20,
}


def _load_registry() -> list[dict]:
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    registry_path = Path(__file__).parent.parent / "augur" / "data" / "check_registry.yaml"
    with open(registry_path) as f:
        data = yaml.safe_load(f)
    _REGISTRY = data.get("checks", [])
    if "dimensions" in data:
        _DIMENSION_WEIGHTS.update({k: v["weight"] for k, v in data["dimensions"].items()})
    if "confidence_weights" in data:
        _CONFIDENCE_WEIGHTS.update(data["confidence_weights"])
    return _REGISTRY


# ── d0 checks (high confidence) ─────────────────────────────────


def check_cursor_pointer_on_click(content: str) -> list[dict]:
    """onClick handlers must have cursor-pointer."""
    issues = []
    for i, line in enumerate(content.splitlines(), 1):
        if re.search(r"onClick\s*=", line) and "cursor-pointer" not in line:
            # Check if it's a disabled element (acceptable)
            if "disabled" in line and "cursor-not-allowed" in line:
                continue
            issues.append({
                "check_id": "cursor-pointer-on-click",
                "line": i,
                "detail": "onClick handler without cursor-pointer",
                "confidence": "high",
                "dimension": "interaction",
            })
    return issues


def check_hardcoded_colors(content: str) -> list[dict]:
    """Detect hardcoded hex/rgb colors in className strings."""
    issues = []
    hex_pattern = re.compile(r'(?:className|style)[^"]*"[^"]*(?:#[0-9a-fA-F]{3,8}|rgb\(|rgba\()')
    gradient_pattern = re.compile(r"(?:bg-gradient|from-|to-|via-)")
    for i, line in enumerate(content.splitlines(), 1):
        if hex_pattern.search(line) and not gradient_pattern.search(line):
            issues.append({
                "check_id": "hardcoded-hex-color",
                "line": i,
                "detail": "Hardcoded color — use CSS var(--*) instead",
                "confidence": "high",
                "dimension": "design_system",
            })
    return issues


def check_emoji_in_jsx(content: str) -> list[dict]:
    """Detect emoji characters in JSX."""
    issues = []
    emoji_pattern = re.compile(
        "[\U0001F300-\U0001F9FF\U00002600-\U000027BF"
        "\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
        "\U0000FE00-\U0000FE0F\U0000200D]"
    )
    for i, line in enumerate(content.splitlines(), 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        if emoji_pattern.search(line):
            issues.append({
                "check_id": "emoji-in-jsx",
                "line": i,
                "detail": "Emoji character in JSX — use Lucide SVG icon",
                "confidence": "high",
                "dimension": "design_system",
            })
    return issues


def check_aria_label_icon_button(content: str) -> list[dict]:
    """Icon-only buttons need aria-label."""
    issues = []
    # Match button tags that contain only an icon component (no text children)
    button_pattern = re.compile(
        r"<button([^>]*)>[\s]*<[\w]+\s[^/]*/>[\s]*</button>", re.DOTALL
    )
    for m in button_pattern.finditer(content):
        attrs = m.group(1)
        if "aria-label" not in attrs:
            line = content[: m.start()].count("\n") + 1
            issues.append({
                "check_id": "aria-label-icon-button",
                "line": line,
                "detail": "Icon-only button missing aria-label",
                "confidence": "high",
                "dimension": "accessibility",
            })
    return issues


# ── d1 checks (medium confidence) ───────────────────────────────


def check_transition_duration(content: str) -> list[dict]:
    """Transition durations should be 150-300ms."""
    issues = []
    dur_pattern = re.compile(r"duration-(\d+)")
    for i, line in enumerate(content.splitlines(), 1):
        for m in dur_pattern.finditer(line):
            ms = int(m.group(1))
            if ms == 0:
                continue  # intentional disable
            if ms < 150 or ms > 300:
                issues.append({
                    "check_id": "transition-duration-range",
                    "line": i,
                    "detail": f"duration-{ms} outside 150-300ms range",
                    "confidence": "medium",
                    "dimension": "interaction",
                })
    return issues


def check_non_lucide_import(content: str) -> list[dict]:
    """Icon imports should come from lucide-react."""
    issues = []
    pattern = re.compile(r"import\s+.*(?:Icon|Icons).*from\s+'\"")
    for i, line in enumerate(content.splitlines(), 1):
        if pattern.search(line):
            issues.append({
                "check_id": "non-lucide-icon-import",
                "line": i,
                "detail": "Icon import not from lucide-react",
                "confidence": "medium",
                "dimension": "design_system",
            })
    return issues


def check_responsive_breakpoints(content: str) -> list[dict]:
    """Grid/flex containers should have responsive classes."""
    issues = []
    grid_pattern = re.compile(r"grid[\s-]cols-\d+")
    responsive_pattern = re.compile(r"(?:sm:|md:|lg:|xl:)")
    for i, line in enumerate(content.splitlines(), 1):
        if grid_pattern.search(line) and not responsive_pattern.search(line):
            issues.append({
                "check_id": "missing-responsive-breakpoint",
                "line": i,
                "detail": "Grid without responsive breakpoint classes",
                "confidence": "medium",
                "dimension": "responsiveness",
            })
    return issues


def check_animate_without_motion_reduce(content: str) -> list[dict]:
    """animate-* should have motion-reduce variant."""
    issues = []
    has_animation = bool(re.search(r"animate-(?!none)", content))
    has_motion_reduce = "motion-reduce" in content or "prefers-reduced-motion" in content
    if has_animation and not has_motion_reduce:
        issues.append({
            "check_id": "animate-without-motion-reduce",
            "line": 0,
            "detail": "File uses animate-* but lacks motion-reduce variant",
            "confidence": "medium",
            "dimension": "interaction",
        })
    return issues


# ── Aggregator ───────────────────────────────────────────────────

# Check functions by difficulty level
_D0_CHECKS = [
    check_cursor_pointer_on_click,
    check_hardcoded_colors,
    check_emoji_in_jsx,
    check_aria_label_icon_button,
]

_D1_CHECKS = [
    check_transition_duration,
    check_non_lucide_import,
    check_responsive_breakpoints,
    check_animate_without_motion_reduce,
]


def run_all_checks(
    content: str,
    page_path: str,
    difficulty: int = 1,
) -> dict[str, Any]:
    """Run all checks up to the given difficulty level.

    Returns dict with: issues, applicable, passing, dimension_scores.
    """
    all_issues: list[dict] = []
    checks_run = 0

    # d0 checks
    for check_fn in _D0_CHECKS:
        checks_run += 1
        issues = check_fn(content)
        for issue in issues:
            issue["page"] = page_path
        all_issues.extend(issues)

    # d1 checks
    if difficulty >= 1:
        for check_fn in _D1_CHECKS:
            checks_run += 1
            issues = check_fn(content)
            for issue in issues:
                issue["page"] = page_path
            all_issues.extend(issues)

    # Calculate dimension scores
    dimension_scores = _calculate_dimension_scores(all_issues, checks_run)

    return {
        "issues": all_issues,
        "applicable": checks_run,
        "passing": checks_run - len(set(i["check_id"] for i in all_issues)),
        "dimension_scores": dimension_scores,
    }


def _calculate_dimension_scores(
    issues: list[dict], checks_run: int
) -> dict[str, float]:
    """Calculate weighted scores per dimension."""
    # Count failing checks per dimension
    failing_by_dim: dict[str, set[str]] = {}
    for issue in issues:
        dim = issue.get("dimension", "")
        check_id = issue.get("check_id", "")
        if dim:
            failing_by_dim.setdefault(dim, set()).add(check_id)

    # Checks per dimension (from registry or inferred)
    checks_per_dim: dict[str, int] = {}
    for fn in _D0_CHECKS + _D1_CHECKS:
        # Infer dimension from first issue or function name
        dim = _infer_dimension(fn)
        checks_per_dim[dim] = checks_per_dim.get(dim, 0) + 1

    scores: dict[str, float] = {}
    for dim, total in checks_per_dim.items():
        failing = len(failing_by_dim.get(dim, set()))
        scores[dim] = max(0, (total - failing) / total * 100) if total > 0 else 100.0

    return scores


def _infer_dimension(fn) -> str:
    """Infer dimension from function name convention."""
    name = fn.__name__
    if "aria" in name or "alt" in name:
        return "accessibility"
    if "cursor" in name or "transition" in name or "animate" in name or "touch" in name:
        return "interaction"
    if "color" in name or "emoji" in name or "lucide" in name or "icon" in name:
        return "design_system"
    if "responsive" in name or "breakpoint" in name or "motion" in name:
        return "responsiveness"
    return "design_system"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && PYTHONPATH=skills/auto-ui-quality:$PYTHONPATH python -m pytest skills/auto-ui-quality/augur/tests/test_checks.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-ui-quality/scripts/checks.py skills/auto-ui-quality/augur/tests/test_checks.py
git commit -m "feat(auto-ui-quality): implement d0-d1 check functions with tests"
```

---

### Task 4: Page Scorer + Registry Persistence

**Files:**
- Create: `skills/auto-ui-quality/augur/tests/test_scorer.py`
- Create: `skills/auto-ui-quality/scripts/scorer.py`

- [ ] **Step 1: Write failing tests for scorer**

Create `skills/auto-ui-quality/augur/tests/test_scorer.py`:

```python
"""Tests for page scoring and registry persistence."""
from __future__ import annotations

import json
import pytest
from pathlib import Path


def test_compute_page_score_weighted():
    from scripts.scorer import compute_page_score
    dimension_scores = {
        "accessibility": 80.0,      # weight 0.30 → 24.0
        "interaction": 60.0,        # weight 0.25 → 15.0
        "design_system": 100.0,     # weight 0.25 → 25.0
        "responsiveness": 50.0,     # weight 0.20 → 10.0
    }
    score = compute_page_score(dimension_scores)
    assert score == pytest.approx(74.0, abs=0.1)


def test_compute_page_score_missing_dimension():
    """Pages missing a dimension should not be penalized."""
    from scripts.scorer import compute_page_score
    dimension_scores = {
        "accessibility": 80.0,
        "interaction": 60.0,
        # design_system and responsiveness absent (no applicable checks)
    }
    score = compute_page_score(dimension_scores)
    # Only accessibility (0.30) and interaction (0.25) apply
    # Renormalized: acc=0.30/0.55=0.545, int=0.25/0.55=0.454
    # Score: 80*0.545 + 60*0.454 = 43.6 + 27.3 = 70.9
    assert score == pytest.approx(70.9, abs=0.5)


def test_load_and_save_registry(tmp_path):
    from scripts.scorer import load_registry, save_registry
    registry_path = tmp_path / "page-scores.json"

    # Empty on first load
    reg = load_registry(registry_path)
    assert reg == {}

    # Save and reload
    reg["life/home-automation/scenes"] = {
        "score": 72,
        "last_audit": "2026-03-24",
        "issues": {"d0": 3, "d1": 1},
        "check_counts": {"applicable": 18, "passing": 13},
    }
    save_registry(reg, registry_path)
    reg2 = load_registry(registry_path)
    assert reg2["life/home-automation/scenes"]["score"] == 72


def test_priority_sort():
    from scripts.scorer import priority_sort
    pages = {
        "a": {"score": 50, "last_audit": "2026-03-20"},
        "b": {"score": 30, "last_audit": "2026-03-22"},
        "c": {"score": 0, "last_audit": None},  # never audited
        "d": {"score": 80, "last_audit": "2026-03-24"},
    }
    sorted_pages = priority_sort(pages)
    # Never audited first, then lowest score
    assert sorted_pages[0] == "c"
    assert sorted_pages[1] == "b"
    assert sorted_pages[2] == "a"
    assert sorted_pages[3] == "d"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && PYTHONPATH=skills/auto-ui-quality:$PYTHONPATH python -m pytest skills/auto-ui-quality/augur/tests/test_scorer.py -v 2>&1 | head -20
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement scorer**

Create `skills/auto-ui-quality/scripts/scorer.py`:

```python
"""Page scoring and registry persistence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DIMENSION_WEIGHTS: dict[str, float] = {
    "accessibility": 0.30,
    "interaction": 0.25,
    "design_system": 0.25,
    "responsiveness": 0.20,
}


def compute_page_score(dimension_scores: dict[str, float]) -> float:
    """Compute weighted page score from dimension scores.

    Only dimensions present in dimension_scores contribute.
    Missing dimensions are excluded and weights renormalized.
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for dim, score in dimension_scores.items():
        weight = _DIMENSION_WEIGHTS.get(dim, 0.0)
        if weight > 0:
            total_weight += weight
            weighted_sum += score * weight
    if total_weight == 0:
        return 0.0
    return weighted_sum / total_weight


def load_registry(registry_path: Path) -> dict[str, Any]:
    """Load page score registry from JSON file."""
    if not registry_path.exists():
        return {}
    try:
        return json.loads(registry_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_registry(registry: dict[str, Any], registry_path: Path) -> None:
    """Save page score registry to JSON file."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2))


def priority_sort(pages: dict[str, dict]) -> list[str]:
    """Sort page keys by priority: never audited first, then lowest score.

    Tie-breaking: oldest last_audit > most issues.
    """
    def sort_key(page_key: str) -> tuple:
        entry = pages[page_key]
        never_audited = entry.get("last_audit") is None
        score = entry.get("score", 0)
        last_audit = entry.get("last_audit") or "0000-00-00"
        return (
            0 if never_audited else 1,  # never audited first
            score,                       # lowest score next
            last_audit,                  # oldest audit next
        )
    return sorted(pages.keys(), key=sort_key)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && PYTHONPATH=skills/auto-ui-quality:$PYTHONPATH python -m pytest skills/auto-ui-quality/augur/tests/test_scorer.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-ui-quality/scripts/scorer.py skills/auto-ui-quality/augur/tests/test_scorer.py
git commit -m "feat(auto-ui-quality): implement page scorer with weighted dimensions and registry persistence"
```

---

### Task 5: d2 Fixers + Git Safety

**Files:**
- Create: `skills/auto-ui-quality/augur/tests/test_fixers.py`
- Create: `skills/auto-ui-quality/scripts/fixers.py`

- [ ] **Step 1: Write failing tests for d2 fixers**

Create `skills/auto-ui-quality/augur/tests/test_fixers.py`:

```python
"""Tests for d2 safe auto-fixes."""
from __future__ import annotations

import pytest


def test_fix_missing_cursor_pointer():
    from scripts.fixers import fix_cursor_pointer
    content = '<button onClick={() => doThing()} className="px-4 py-2">'
    fixed = fix_cursor_pointer(content)
    assert "cursor-pointer" in fixed
    assert 'className="cursor-pointer px-4 py-2"' in fixed


def test_fix_cursor_pointer_already_present():
    from scripts.fixers import fix_cursor_pointer
    content = '<button onClick={() => doThing()} className="cursor-pointer px-4">'
    fixed = fix_cursor_pointer(content)
    assert fixed == content  # no change


def test_fix_transition_duration():
    from scripts.fixers import fix_transition_duration
    content = 'className="transition-colors duration-500"'
    fixed = fix_transition_duration(content)
    assert "duration-200" in fixed


def test_fix_transition_duration_valid():
    from scripts.fixers import fix_transition_duration
    content = 'className="transition-colors duration-200"'
    fixed = fix_transition_duration(content)
    assert fixed == content  # no change


def test_apply_safe_fixes_returns_changes():
    from scripts.fixers import apply_safe_fixes
    content = """
    <button onClick={() => doThing()} className="px-4 py-2 transition-all duration-500">
      <Play className="w-4 h-4" />
    </button>
    """
    fixed, changes = apply_safe_fixes(content, "test/page.tsx")
    assert len(changes) >= 1
    assert "cursor-pointer" in fixed
    assert "duration-200" in fixed
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && PYTHONPATH=skills/auto-ui-quality:$PYTHONPATH python -m pytest skills/auto-ui-quality/augur/tests/test_fixers.py -v 2>&1 | head -20
```

Expected: FAIL

- [ ] **Step 3: Implement fixers**

Create `skills/auto-ui-quality/scripts/fixers.py`:

```python
"""d2 safe auto-fixes and git safety net."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


# ── d2 safe fixes ────────────────────────────────────────────────


def fix_cursor_pointer(content: str) -> str:
    """Add cursor-pointer to onClick elements missing it."""
    lines = content.splitlines()
    result = []
    for line in lines:
        if (
            re.search(r"onClick\s*=", line)
            and "cursor-pointer" not in line
            and "cursor-not-allowed" not in line
        ):
            # Insert cursor-pointer at start of className value
            line = re.sub(
                r'className="',
                'className="cursor-pointer ',
                line,
            )
            # Handle template literal classNames
            line = re.sub(
                r"className=\{`",
                "className={`cursor-pointer ",
                line,
            )
        result.append(line)
    return "\n".join(result)


def fix_transition_duration(content: str) -> str:
    """Fix transition durations outside 150-300ms to 200ms."""
    def replace_duration(m: re.Match) -> str:
        ms = int(m.group(1))
        if ms == 0:
            return m.group(0)  # duration-0 is intentional
        if ms < 150 or ms > 300:
            return "duration-200"
        return m.group(0)

    return re.sub(r"duration-(\d+)", replace_duration, content)


def apply_safe_fixes(
    content: str, page_path: str
) -> tuple[str, list[str]]:
    """Apply all safe d2 fixes. Returns (fixed_content, list_of_change_descriptions)."""
    changes: list[str] = []
    original = content

    # Fix cursor-pointer
    fixed = fix_cursor_pointer(content)
    if fixed != content:
        changes.append("added cursor-pointer to onClick elements")
        content = fixed

    # Fix transition durations
    fixed = fix_transition_duration(content)
    if fixed != content:
        changes.append("fixed transition durations to 150-300ms range")
        content = fixed

    return content, changes


# ── Git safety net ───────────────────────────────────────────────


def verify_build(project_root: Path, verify_command: str | None = None) -> bool:
    """Run the engine verify_command. Returns True if build passes."""
    cmd = verify_command or "cd apps/dashboard && npx tsc --noEmit"
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def git_commit(project_root: Path, message: str, files: list[str]) -> bool:
    """Stage files and commit. Returns True on success."""
    try:
        subprocess.run(
            ["git", "add"] + files,
            cwd=str(project_root),
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(project_root),
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def git_revert(project_root: Path) -> bool:
    """Revert the last commit. Returns True on success."""
    try:
        subprocess.run(
            ["git", "revert", "--no-edit", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def safe_fix_page(
    project_root: Path,
    page_path: str,
    page_file: Path,
    score_before: float,
    score_fn,
    verify_command: str | None = None,
) -> dict:
    """Apply safe fixes to a page with git safety net.

    1. Read and fix content
    2. Write fixed file
    3. Commit
    4. Verify build
    5. Re-score — revert on regression

    Returns action dict with results.
    """
    content = page_file.read_text()
    fixed_content, changes = apply_safe_fixes(content, page_path)

    if not changes:
        return {"page": page_path, "action": "skip", "reason": "no fixable issues"}

    # Write fix
    page_file.write_text(fixed_content)

    # Commit
    commit_msg = f"fix(auto-ui-quality): improve {page_path} — {', '.join(changes[:3])}"
    if not git_commit(project_root, commit_msg, [str(page_file)]):
        # Restore original
        page_file.write_text(content)
        return {"page": page_path, "action": "skip", "reason": "git commit failed"}

    # Verify build
    if not verify_build(project_root, verify_command):
        git_revert(project_root)
        return {"page": page_path, "action": "reverted", "reason": "build failure"}

    # Re-score
    score_after = score_fn(page_path)
    if score_after < score_before:
        git_revert(project_root)
        return {
            "page": page_path,
            "action": "reverted",
            "reason": f"score regression {score_before:.0f} → {score_after:.0f}",
        }

    return {
        "page": page_path,
        "action": "fixed",
        "changes": changes,
        "score_before": score_before,
        "score_after": score_after,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && PYTHONPATH=skills/auto-ui-quality:$PYTHONPATH python -m pytest skills/auto-ui-quality/augur/tests/test_fixers.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-ui-quality/scripts/fixers.py skills/auto-ui-quality/augur/tests/test_fixers.py
git commit -m "feat(auto-ui-quality): implement d2 safe fixers with git safety net"
```

---

### Task 6: Visual Analysis Module (d3-d4)

**Files:**
- Create: `skills/auto-ui-quality/scripts/visual.py`

- [ ] **Step 1: Implement visual analysis module**

Create `skills/auto-ui-quality/scripts/visual.py`:

```python
"""d3-d4 visual analysis — Playwright screenshots + LLM prompt assembly."""
from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime, timezone


def check_dashboard_available(url: str = "http://localhost:3000") -> bool:
    """Quick HTTP probe to check if dashboard dev server is running."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=3)
        return True
    except Exception:
        return False


def take_screenshot(
    page_url: str,
    output_path: Path,
    viewport_width: int = 1440,
    viewport_height: int = 900,
) -> bool:
    """Take a Playwright screenshot of a dashboard page.

    Returns True on success, False if Playwright unavailable or page fails.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
    const browser = await chromium.launch({{ headless: true }});
    const page = await browser.newPage({{
        viewport: {{ width: {viewport_width}, height: {viewport_height} }}
    }});
    await page.goto('{page_url}', {{ waitUntil: 'networkidle', timeout: 15000 }});
    await page.screenshot({{ path: '{output_path}', fullPage: true }});
    await browser.close();
}})();
"""
    try:
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0 and output_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def build_llm_prompt(
    page_path: str,
    page_source: str,
    score_breakdown: dict,
    issues: list[dict],
    design_recommendations: str,
    screenshot_path: Path | None = None,
) -> str:
    """Assemble the LLM escalation prompt for d3-d4 visual analysis."""
    prompt_parts = [
        f"# UI Quality Improvement: {page_path}\n",
        "## Current Score Breakdown",
        f"Overall: {score_breakdown.get('score', 0):.0f}/100\n",
    ]

    for dim, score in score_breakdown.get("dimension_scores", {}).items():
        prompt_parts.append(f"- {dim}: {score:.0f}/100")

    prompt_parts.append(f"\n## Issues Found ({len(issues)})")
    for issue in issues[:20]:  # cap to avoid prompt bloat
        prompt_parts.append(
            f"- [{issue.get('check_id', '?')}] line {issue.get('line', '?')}: "
            f"{issue.get('detail', '')}"
        )

    prompt_parts.append("\n## Design Recommendations (from ui-ux-pro-max)")
    prompt_parts.append(design_recommendations or "No specific recommendations available.")

    prompt_parts.append("\n## Page Source Code")
    prompt_parts.append(f"```tsx\n{page_source}\n```")

    if screenshot_path and screenshot_path.exists():
        prompt_parts.append(f"\n## Screenshot available at: {screenshot_path}")

    prompt_parts.append(
        "\n## Task"
        "\nImprove this page's UI quality. Focus on:"
        "\n1. Fix all identified issues"
        "\n2. Improve information hierarchy and grouping"
        "\n3. Use existing design system components (GlassCard, CSS vars, Lucide icons)"
        "\n4. Ensure accessibility (aria-labels, focus states, touch targets)"
        "\n5. Add responsive breakpoints where missing"
        "\n\nOutput the complete fixed page.tsx file."
    )

    return "\n".join(prompt_parts)


def get_design_recommendations(
    page_context: str,
    search_script: Path,
) -> str:
    """Call ui-ux-pro-max search.py for design recommendations."""
    try:
        result = subprocess.run(
            ["python3", str(search_script), page_context, "--domain", "ux"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def get_screenshot_dir(runtime_dir: Path) -> Path:
    """Get the screenshots directory path."""
    return runtime_dir / "adaptive" / "ui-quality" / "screenshots"


def screenshot_page(
    page_path: str,
    runtime_dir: Path,
    base_url: str = "http://localhost:3000",
    label: str = "current",
) -> Path | None:
    """Take a screenshot of a page and save to the screenshots dir.

    Returns the screenshot path, or None if failed.
    """
    screenshot_dir = get_screenshot_dir(runtime_dir)
    safe_name = page_path.replace("/", "__")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"{safe_name}_{label}_{timestamp}.png"
    output = screenshot_dir / filename

    url = f"{base_url}/{page_path}"
    if take_screenshot(url, output):
        return output
    return None
```

- [ ] **Step 2: Commit**

```bash
git add skills/auto-ui-quality/scripts/visual.py
git commit -m "feat(auto-ui-quality): implement d3-d4 visual analysis with Playwright + LLM prompt assembly"
```

---

### Task 7: Main Entrypoint (scan + fix)

**Files:**
- Create: `skills/auto-ui-quality/scripts/ui_quality.py`

- [ ] **Step 1: Implement main scan()/fix() entrypoint**

Create `skills/auto-ui-quality/scripts/ui_quality.py`:

```python
"""auto-ui-quality: Nightly UI/UX quality audit autoloop.

Scans all dashboard pages for accessibility, interaction, design system,
and responsiveness issues. Auto-fixes at d2+ with git safety net.
LLM-assisted visual analysis at d3-d4.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_project_root, get_runtime_dir
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    check_intentional_skip,
    evolution_gap,
    find_page_routes,
    issue_fingerprint,
    make_issue,
)

name = "auto-ui-quality"

DIFFICULTY_SPEC = {
    0: "Inventory — discover pages, count accessibility/interaction/design-system issues",
    1: "Pattern check — validate transitions, icons, responsive classes, focus states",
    2: "Safe auto-fix — add cursor-pointer, fix transitions, replace hardcoded colors",
    3: "Visual analysis — Playwright screenshots, LLM audit against ui-ux-pro-max guidelines",
    4: "Full redesign — structural rewrites, layout grouping, search/filter addition",
}


def _get_state_dir() -> Path:
    return get_runtime_dir() / "adaptive" / "ui-quality"


def _get_registry_path() -> Path:
    return _get_state_dir() / "page-scores.json"


def _find_page_files(project_root: Path) -> dict[str, Path]:
    """Find all page.tsx files and map route → file path."""
    pages: dict[str, Path] = {}
    # Primary: skills/dashboard/pages/{hub}/**/page.tsx
    skills_pages = project_root / "skills" / "dashboard" / "pages"
    if skills_pages.exists():
        for page_file in skills_pages.rglob("page.tsx"):
            rel = page_file.relative_to(skills_pages)
            route = str(rel.parent).replace("\\", "/")
            if route != ".":
                pages[route] = page_file
    return pages


def scan(ctx: OpsContext) -> ScanResult:
    """Scan dashboard pages for UI quality issues."""
    from scripts.checks import run_all_checks
    from scripts.scorer import (
        compute_page_score,
        load_registry,
        priority_sort,
        save_registry,
    )

    project_root = ctx.project_root or get_project_root()
    page_files = _find_page_files(project_root)

    if not page_files:
        return ScanResult(
            issues=[evolution_gap(
                "No dashboard pages found. Check skills/dashboard/pages/ exists.",
                category="ui-quality",
            )],
            summary="No pages found",
            severity="warning",
            health="degraded",
        )

    registry = load_registry(_get_registry_path())
    all_issues: list[dict] = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for page_path, page_file in page_files.items():
        # Check intentional skip
        if check_intentional_skip(page_file):
            continue

        try:
            content = page_file.read_text()
        except (OSError, UnicodeDecodeError):
            continue

        result = run_all_checks(content, page_path, difficulty=min(ctx.difficulty, 1))
        page_score = compute_page_score(result["dimension_scores"])

        # Update registry
        registry[page_path] = {
            "score": round(page_score, 1),
            "last_audit": today,
            "issues": {
                "d0": len([i for i in result["issues"] if i.get("confidence") == "high"]),
                "d1": len([i for i in result["issues"] if i.get("confidence") in ("medium", "low")]),
            },
            "check_counts": {
                "applicable": result["applicable"],
                "passing": result["passing"],
            },
        }

        # Convert check issues to ops_protocol issues
        for issue in result["issues"]:
            all_issues.append(make_issue(
                category="ui-quality",
                detail=f"{page_path}: {issue['detail']}",
                path=str(page_file),
                kind="actionable" if ctx.difficulty >= 2 else "maintenance",
                root_cause_type="repo_bug",
                fixability="auto" if issue.get("confidence") == "high" else "manual",
                fingerprint=issue_fingerprint(
                    category="ui-quality",
                    path=page_path,
                    detail=issue["check_id"],
                ),
                check_id=issue["check_id"],
                page_route=page_path,
                dimension=issue.get("dimension", ""),
                confidence=issue.get("confidence", "medium"),
                line=issue.get("line", 0),
            ))

    # Save updated registry
    save_registry(registry, _get_registry_path())

    # Evolution gaps at max difficulty with no issues
    if ctx.difficulty >= 2 and not all_issues:
        all_issues.append(evolution_gap(
            "All pages pass d0-d1 checks. Next: add dark mode contrast checking, "
            "viewport resize testing for responsive breakpoints.",
            category="ui-quality",
        ))

    # Compute summary stats
    scores = [r["score"] for r in registry.values()]
    avg_score = sum(scores) / len(scores) if scores else 0

    return ScanResult(
        issues=all_issues,
        summary=(
            f"Scanned {len(page_files)} pages, avg score {avg_score:.0f}/100, "
            f"{len(all_issues)} issues found"
        ),
        severity="warning" if all_issues else "info",
        health="degraded" if avg_score < 60 else "verified",
        items_scanned=len(page_files),
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix UI quality issues at d2+ with git safety net."""
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issues")

    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    from scripts.checks import run_all_checks
    from scripts.fixers import safe_fix_page
    from scripts.scorer import (
        compute_page_score,
        load_registry,
        priority_sort,
        save_registry,
    )

    project_root = ctx.project_root or get_project_root()
    page_files = _find_page_files(project_root)
    registry = load_registry(_get_registry_path())

    # Get verify command from engine config
    verify_command = ctx.loop_config.get("verify_command")

    all_actions: list[dict] = []
    all_changes: list[str] = []

    # ── d2: Safe auto-fixes on worst pages ───────────────────────
    if ctx.difficulty >= 2:
        fix_limit = ctx.config.get("d2_fix_limit", 10)
        worst_pages = priority_sort(registry)[:fix_limit]

        def score_fn(page_path: str) -> float:
            """Re-score a page after fix."""
            pf = page_files.get(page_path)
            if not pf or not pf.exists():
                return 0
            content = pf.read_text()
            result = run_all_checks(content, page_path, difficulty=1)
            return compute_page_score(result["dimension_scores"])

        for page_path in worst_pages:
            page_file = page_files.get(page_path)
            if not page_file or not page_file.exists():
                continue

            score_before = registry.get(page_path, {}).get("score", 0)
            action = safe_fix_page(
                project_root=project_root,
                page_path=page_path,
                page_file=page_file,
                score_before=score_before,
                score_fn=score_fn,
                verify_command=verify_command,
            )
            all_actions.append(action)
            if action.get("action") == "fixed":
                all_changes.append(
                    f"{page_path}: {', '.join(action.get('changes', []))}"
                )
                # Update registry with new score
                registry[page_path]["score"] = action.get("score_after", score_before)

    # ── d3-d4: LLM-assisted visual analysis ──────────────────────
    if ctx.difficulty >= 3:
        from scripts.visual import (
            build_llm_prompt,
            check_dashboard_available,
            get_design_recommendations,
            screenshot_page,
        )

        dashboard_up = check_dashboard_available()
        if not dashboard_up:
            all_actions.append({
                "action": "skip_visual",
                "reason": "Dashboard not running at localhost:3000",
            })
        else:
            analysis_limit = ctx.config.get("d3_analysis_limit", 3)
            rewrite_limit = ctx.config.get("max_page_rewrites", 3)
            worst_pages = priority_sort(registry)[:analysis_limit]
            rewrites_done = 0

            search_script = project_root / "skills" / "ui-ux-pro-max" / "scripts" / "search.py"
            runtime_dir = get_runtime_dir()

            for page_path in worst_pages:
                if rewrites_done >= rewrite_limit:
                    break

                page_file = page_files.get(page_path)
                if not page_file or not page_file.exists():
                    continue

                # Screenshot before
                screenshot_before = screenshot_page(
                    page_path, runtime_dir, label="before"
                )

                # Get design recommendations
                design_recs = get_design_recommendations(
                    f"dashboard {page_path}", search_script
                )

                # Build LLM prompt
                score_data = registry.get(page_path, {})
                page_source = page_file.read_text()
                page_issues = [
                    i for i in issues if i.get("page_route") == page_path
                ]

                llm_prompt = build_llm_prompt(
                    page_path=page_path,
                    page_source=page_source,
                    score_breakdown=score_data,
                    issues=page_issues,
                    design_recommendations=design_recs,
                    screenshot_path=screenshot_before,
                )

                all_actions.append({
                    "kind": "llm_escalation",
                    "page": page_path,
                    "prompt": llm_prompt,
                    "reason": f"score {score_data.get('score', 0):.0f}/100, {len(page_issues)} issues",
                })
                rewrites_done += 1

    # Save updated registry
    save_registry(registry, _get_registry_path())

    # ── Write reports ────────────────────────────────────────────
    _write_reports(registry, all_actions, all_changes)

    fixed_count = sum(1 for a in all_actions if a.get("action") == "fixed")
    llm_count = sum(1 for a in all_actions if a.get("kind") == "llm_escalation")

    summary_parts = []
    if fixed_count:
        summary_parts.append(f"Fixed {fixed_count} pages")
    if llm_count:
        summary_parts.append(f"{llm_count} LLM escalation(s) queued")
    if not summary_parts:
        summary_parts.append("No fixes applied")

    return FixResult(
        success=fixed_count > 0 or not issues,
        actions=all_actions,
        changes=all_changes,
        summary=", ".join(summary_parts),
        fix_type="code-fix" if all_changes else "report",
    )


def _write_reports(
    registry: dict,
    actions: list[dict],
    changes: list[str],
) -> None:
    """Write JSON + markdown reports."""
    state_dir = _get_state_dir()
    reports_dir = state_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    scores = [r["score"] for r in registry.values()]
    avg_score = sum(scores) / len(scores) if scores else 0

    # JSON report
    json_report = {
        "date": today,
        "pages_scanned": len(registry),
        "average_score": round(avg_score, 1),
        "total_issues": sum(
            r.get("issues", {}).get("d0", 0) + r.get("issues", {}).get("d1", 0)
            for r in registry.values()
        ),
        "fixes_applied": len(changes),
        "actions": actions,
    }
    (reports_dir / f"{today}.json").write_text(json.dumps(json_report, indent=2))

    # Markdown report
    sorted_pages = sorted(registry.items(), key=lambda x: x[1].get("score", 0))
    bottom_5 = sorted_pages[:5]

    md_lines = [
        f"# UI Quality Report — {today}\n",
        "## Summary",
        f"- Pages scanned: {len(registry)}",
        f"- Average score: {avg_score:.0f}/100",
        f"- Fixes applied: {len(changes)}",
        "",
        "## Bottom 5 Pages",
        "| Page | Score | d0 Issues | d1 Issues |",
        "|------|-------|-----------|-----------|",
    ]
    for page, data in bottom_5:
        d0 = data.get("issues", {}).get("d0", 0)
        d1 = data.get("issues", {}).get("d1", 0)
        md_lines.append(f"| {page} | {data.get('score', 0):.0f} | {d0} | {d1} |")

    if changes:
        md_lines.extend(["", "## Fixes Applied"])
        for change in changes:
            md_lines.append(f"- {change}")

    (reports_dir / f"{today}.md").write_text("\n".join(md_lines))
```

- [ ] **Step 2: Commit**

```bash
git add skills/auto-ui-quality/scripts/ui_quality.py
git commit -m "feat(auto-ui-quality): implement main scan()/fix() entrypoint with d0-d4 support"
```

---

### Task 8: Integration Validation

**Files:**
- None created — validation only

- [ ] **Step 1: Verify module loads and scan runs at d0**

```bash
cd ~/Projects/Augur && python -c "
import sys
sys.path.insert(0, 'skills/auto-ui-quality')
from scripts.ui_quality import scan, fix, name, DIFFICULTY_SPEC
from src.lib.ops_protocol import OpsContext
print(f'Module: {name}')
print(f'Difficulty levels: {len(DIFFICULTY_SPEC)}')
ctx = OpsContext(difficulty=0)
result = scan(ctx)
print(f'Scan result: {result.summary}')
print(f'Issues: {len(result.issues)}')
print(f'Health: {result.health}')
"
```

Expected: Module loads, scan discovers pages and reports issues.

- [ ] **Step 2: Verify check registry loads**

```bash
cd ~/Projects/Augur && python -c "
import sys
sys.path.insert(0, 'skills/auto-ui-quality')
from scripts.checks import _load_registry
checks = _load_registry()
print(f'Loaded {len(checks)} checks')
for c in checks:
    print(f'  [{c[\"difficulty\"]}] {c[\"id\"]} ({c[\"confidence\"]})')
"
```

Expected: 10 checks loaded with correct difficulty/confidence.

- [ ] **Step 3: Verify page score registry persisted**

```bash
python -c "
from src.config.paths import get_runtime_dir
import json
p = get_runtime_dir() / 'adaptive' / 'ui-quality' / 'page-scores.json'
if p.exists():
    data = json.loads(p.read_text())
    for page, info in sorted(data.items(), key=lambda x: x[1]['score'])[:5]:
        print(f'{info[\"score\"]:5.1f}  {page}')
else:
    print('Registry not yet created (run scan first)')
"
```

- [ ] **Step 4: Run all unit tests**

```bash
cd ~/Projects/Augur && PYTHONPATH=skills/auto-ui-quality:$PYTHONPATH python -m pytest skills/auto-ui-quality/augur/tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 5: Verify discovery finds the new autoloop**

```bash
cd ~/Projects/Augur && python -c "
from src.plugins.skill_discovery import discover_all_skills
skills = discover_all_skills()
ui = [s for s in skills if s.name == 'auto-ui-quality']
if ui:
    s = ui[0]
    print(f'Found: {s.name}')
    print(f'Loop: {s.loop_config}')
    print(f'Hub: {s.hub}')
else:
    print('NOT FOUND in skill discovery')
"
```

Expected: `auto-ui-quality` discovered with loop config `ui-quality`.

- [ ] **Step 6: Final commit**

```bash
git add -A skills/auto-ui-quality/
git commit -m "feat(auto-ui-quality): complete nightly UI/UX quality audit autoloop

New autoloop skill that scans all dashboard pages for UI/UX issues across
4 dimensions (accessibility, interaction, design system, responsiveness).

- d0-d1: Static analysis with confidence-weighted scoring
- d2: Safe auto-fixes (cursor-pointer, transitions) with git safety net
- d3-d4: Playwright screenshots + LLM escalation for visual redesigns
- Hybrid priority: scan all, fix worst, deep-analyze bottom N
- Reports: JSON (engine) + Markdown (human) to runtime state dir"
```

---

## Execution Notes

- **PYTHONPATH**: Tests need `PYTHONPATH=skills/auto-ui-quality:$PYTHONPATH` to resolve `scripts.*` imports
- **d3-d4 testing**: Requires dashboard running at localhost:3000 + Playwright installed. Skip in CI.
- **Registry location**: `get_runtime_dir() / "adaptive" / "ui-quality" / "page-scores.json"` — created automatically on first scan.
- **Nightly integration**: After committing, the nightly engine will auto-discover via `x-augur-loop` frontmatter in SKILL.md. No manual registration needed.
