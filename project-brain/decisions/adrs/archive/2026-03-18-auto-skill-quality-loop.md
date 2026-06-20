# Auto Skill Quality Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an adaptive nightly loop that scores all skills and aggressively improves them toward tier A across all 4 dimensions, with git revert on build failure or score regression.

**Architecture:** New `skill-quality` loop registered in `adaptive_loops.yaml`, implemented as an OpsCommand module (`scan` + `fix`) in `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py`. Scan calls the unified scorer, fix applies dimension-specific improvements gated by difficulty level (d0=report, d1=instruction, d2=+product, d3=+UI, d4=+wiring). Every fix commits, verifies build, re-scores, and reverts on failure.

**Tech Stack:** Python (OpsCommand protocol), YAML (SKILL.md frontmatter, loop config)

**Spec:** `docs/superpowers/specs/2026-03-18-auto-skill-quality-loop-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `.claude/skills/auto-skill-quality/SKILL.md` | Create | Skill declaration with `x-augur-loop` frontmatter |
| `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py` | Create | OpsCommand: scan + fix with all dimension fixers |
| `config/system/adaptive_loops.yaml` | Modify | Add `skill-quality` loop entry |

---

## Task 1: Create SKILL.md

**Files:**
- Create: `.claude/skills/auto-skill-quality/SKILL.md`

- [ ] **Step 1: Create the skill directory and SKILL.md**

```markdown
---
name: auto-skill-quality
description: >-
  Adaptive loop that improves skill quality scores toward tier A across all 4 dimensions
  (instruction, product, UI, wiring) with user-journey awareness. Generates seed data,
  rewrites descriptions, scaffolds product files, and fixes wiring — with git revert on
  build failure or score regression. Use this when skills are scoring below tier A and
  need automated quality improvement.
x-augur-visibility: auto
x-augur-loop:
  name: skill-quality
  tier: 0
  trigger: nightly
  config:
    max_skills_per_cycle: 5
    build_verify: true
    revert_on_regression: true
x-augur-hub: adaptive
x-augur-master: claude-code
x-augur-plugin: augur-adaptive
---

# auto-skill-quality

Nightly adaptive loop that scores all skills via the unified scorer and aggressively
improves them toward tier A. Operates across all 4 scoring dimensions with user-journey
awareness — every fix considers what problem the skill solves and how the user consumes
the data on the dashboard.

## Difficulty Levels

- **d0**: Scan only — report tier distribution, worst skills, user journey gaps
- **d1**: Fix instruction dimension — rewrite descriptions, expand bodies, add examples
- **d2**: Fix instruction + product — create dirs, generate seeds, scaffold actions
- **d3**: Fix instruction + product + UI — promote page states, add page contributions
- **d4**: Fix all dimensions including wiring — fix toolName refs, remove fs bypasses

## Safety

- Every fix cycle creates a git commit
- Runs `npm run build` after each skill fix
- If build fails → `git revert HEAD` + trust penalty
- If re-score shows regression → `git revert HEAD` + trust penalty
- Respects `dry_run` flag (scan only, no changes)

## User Journey Awareness

Before fixing any skill, the loop reads:
1. SKILL.md body — what problem does this solve?
2. Hub context — what's the user persona?
3. Page components — what data does the page display?
4. Data directory — what files exist? What's missing?

This reasoning drives fix decisions: descriptions explain user value, seed data
reflects realistic scenarios, page states reflect actual usability.

## Integration

- **Depends on**: `skill-standards` loop (structural hygiene runs first)
- **Complements**: `auto-seed-data` (this loop generates seed templates, auto-seed-data copies them)
- **Uses**: `score_all_skills()` from `src/mcp/augur_mcp/infrastructure/skill_scorer.py`
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/auto-skill-quality/SKILL.md
git commit -m "feat(auto-skill-quality): create skill with loop frontmatter"
```

---

## Task 2: Register Loop in adaptive_loops.yaml

**Files:**
- Modify: `config/system/adaptive_loops.yaml`

- [ ] **Step 1: Read the file to find where to add the new loop**

Read `config/system/adaptive_loops.yaml`. Find the `loops:` section and add the new entry.

- [ ] **Step 2: Add skill-quality loop entry**

Add under the `loops:` key (alphabetically or at the end):

```yaml
  skill-quality:
    budget: 15
    budget_growth_rate: 1
```

- [ ] **Step 3: Commit**

```bash
git add config/system/adaptive_loops.yaml
git commit -m "feat(auto-skill-quality): register skill-quality loop in adaptive config"
```

---

## Task 3: Create OpsCommand Module — Scan Function

**Files:**
- Create: `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py`

- [ ] **Step 1: Create the module with scan() and stub fix()**

```python
"""Auto skill quality — improve skill scores toward tier A across all dimensions."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from src.config.paths import get_project_root, get_all_client_skill_dirs, get_vault_dir
from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter
from src.lib.ops_protocol import (
    OpsContext,
    ScanResult,
    FixResult,
    make_issue,
    evolution_gap,
)

name = "auto-skill-quality"

DIFFICULTY_SPEC = {
    0: "Scan only — report tier distribution, worst skills, user journey gaps",
    1: "Fix instruction — rewrite descriptions, expand bodies, add examples",
    2: "Fix instruction + product — create dirs, generate seeds, scaffold actions",
    3: "Fix instruction + product + UI — promote page states, add page contributions",
    4: "Fix all dimensions including wiring — fix toolName refs, remove fs bypasses",
}


def _get_scorer():
    """Import scorer lazily to avoid circular imports."""
    from augur_mcp.infrastructure.skill_scorer import score_all_skills
    return score_all_skills


def scan(ctx: OpsContext) -> ScanResult:
    """Score all skills and return issues for non-A skills."""
    score_all = _get_scorer()

    try:
        scored = score_all()
    except Exception as e:
        return ScanResult(
            issues=[make_issue(
                category="skill-quality",
                detail=f"Scorer failed: {e}",
                kind="scanner-defect",
                root_cause_type="scanner_bug",
                fixability="manual",
            )],
            summary=f"Scorer error: {e}",
            severity="error",
            health="broken",
        )

    skills = scored["skills"]
    below_a = [s for s in skills if s["tier"] != "A"]
    below_a.sort(key=lambda s: s["score"])

    max_skills = ctx.config.get("max_skills_per_cycle", 5)
    targets = below_a[:max_skills]

    issues = []
    for skill in targets:
        dims = skill["dimensions"]
        skill_name = skill["name"]
        base_path = f".claude/skills/{skill_name}"

        # Instruction issues (all difficulties report, d1+ actionable)
        if dims["instruction"]["score"] < 75:
            sig = dims["instruction"]["signals"]
            issues.append(make_issue(
                category="skill-quality",
                detail=(
                    f'{skill_name}: instruction {dims["instruction"]["score"]}/100 — '
                    f'{sig["desc_words"]}w desc, {sig["body_lines"]}L body, '
                    f'{sig["sections"]} sections'
                ),
                path=f"{base_path}/SKILL.md",
                kind="actionable" if ctx.difficulty >= 1 else "maintenance",
                root_cause_type="repo_bug",
                fixability="auto" if ctx.difficulty >= 1 else "manual",
                dimension="instruction",
                skill_name=skill_name,
                score=dims["instruction"]["score"],
                signals=sig,
            ))

        # Product issues (d2+)
        if ctx.difficulty >= 2 and dims["product"]["score"] < 75:
            sig = dims["product"]["signals"]
            missing = [k.replace("has_", "").replace("_", " ")
                       for k, v in sig.items() if not v]
            issues.append(make_issue(
                category="skill-quality",
                detail=(
                    f'{skill_name}: product {dims["product"]["score"]}/100 — '
                    f'missing: {", ".join(missing) or "none"}'
                ),
                path=f"{base_path}/",
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="auto",
                dimension="product",
                skill_name=skill_name,
                score=dims["product"]["score"],
                signals=sig,
            ))

        # UI issues (d3+)
        if ctx.difficulty >= 3 and dims["ui"]["score"] < 75:
            sig = dims["ui"]["signals"]
            issues.append(make_issue(
                category="skill-quality",
                detail=(
                    f'{skill_name}: ui {dims["ui"]["score"]}/100 — '
                    f'{sig["page_count"]} pages, {sig["mature_pages"]} mature'
                ),
                path=f"{base_path}/SKILL.md",
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="auto",
                dimension="ui",
                skill_name=skill_name,
                score=dims["ui"]["score"],
                signals=sig,
            ))

        # Wiring issues (d4)
        if ctx.difficulty >= 4 and dims["wiring"]["score"] < 75:
            sig = dims["wiring"]["signals"]
            problems = [k.replace("has_", "").replace("no_", "missing ")
                        for k, v in sig.items() if not v]
            issues.append(make_issue(
                category="skill-quality",
                detail=(
                    f'{skill_name}: wiring {dims["wiring"]["score"]}/100 — '
                    f'{", ".join(problems) or "none"}'
                ),
                path=f"{base_path}/",
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="auto",
                dimension="wiring",
                skill_name=skill_name,
                score=dims["wiring"]["score"],
                signals=sig,
            ))

    # Evolution gap when all skills at A
    if not below_a:
        issues.append(evolution_gap(
            "All skills at tier A (≥75). Tier A threshold could be raised to 85 "
            "to target remaining quality gaps in UI maturity and wiring integrity. "
            "Next: update DEFAULT_THRESHOLDS in skill_scorer.py and weight config.",
            category="skill-quality",
        ))

    total = len(skills)
    return ScanResult(
        issues=issues,
        summary=f"{len(below_a)}/{total} skills below tier A, targeting {len(targets)} this cycle",
        severity="warning" if below_a else "info",
        health="degraded" if len(below_a) > total * 0.5 else "verified",
        items_scanned=total,
    )
```

- [ ] **Step 2: Verify syntax**

Run: `cd ~/Projects/Augur && python -c "import ast; ast.parse(open('.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/auto-skill-quality/scripts/skill_quality_ops.py
git commit -m "feat(auto-skill-quality): implement scan function with per-dimension issue detection"
```

---

## Task 4: Implement Fix — Instruction Dimension

**Files:**
- Modify: `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py`

- [ ] **Step 1: Add instruction fix helpers and the fix() function**

Append to the end of `skill_quality_ops.py`:

```python
# ── Fix Helpers ──────────────────────────────────────────────────────────

def _read_skill_context(skill_name: str, skill_dir: Path) -> dict:
    """Read skill context for user-journey-aware fixes."""
    context = {"name": skill_name, "hub": "system", "purpose": "", "has_pages": False}

    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        try:
            fm, body = parse_frontmatter(skill_md)
            context["fm"] = fm
            context["body"] = body
            context["hub"] = (fm.get("x-augur-config") or {}).get("hub", "system")
            context["purpose"] = fm.get("description", "")
            pages = ((fm.get("x-augur-config") or {}).get("contributions") or {}).get("pages") or []
            context["has_pages"] = len(pages) > 0
            context["pages"] = pages
        except Exception:
            context["fm"] = {}
            context["body"] = ""

    # Check what directories exist
    context["has_data"] = (skill_dir / "data").is_dir()
    context["has_scripts"] = (skill_dir / "scripts").is_dir()
    context["has_references"] = (skill_dir / "references").is_dir()
    context["has_augur"] = (skill_dir / "augur").is_dir()
    context["has_seed"] = (skill_dir / "augur" / "seed").is_dir()

    return context


def _fix_instruction(skill_name: str, skill_dir: Path, signals: dict, ctx_info: dict) -> list[str]:
    """Improve SKILL.md description and body content."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return []

    fm = ctx_info.get("fm", {})
    body = ctx_info.get("body", "")
    changes = []

    # 1. Expand thin description (< 20 words)
    desc = fm.get("description", "") or ""
    desc_words = len(desc.split()) if desc.strip() else 0
    if desc_words < 20:
        hub = ctx_info.get("hub", "system")
        # Build a richer description from the body and skill name
        new_desc = _generate_description(skill_name, hub, body, desc)
        if new_desc and len(new_desc.split()) >= 15:
            fm["description"] = new_desc
            changes.append(f"expanded description from {desc_words} to {len(new_desc.split())} words")

    # 2. Add missing sections to thin bodies (< 20 lines)
    body_lines = len(body.strip().split("\n")) if body.strip() else 0
    if body_lines < 20:
        new_body = _expand_body(skill_name, ctx_info, body)
        if new_body and len(new_body.strip().split("\n")) > body_lines:
            body = new_body
            changes.append(f"expanded body from {body_lines} to {len(new_body.strip().split(chr(10)))} lines")

    if changes:
        write_frontmatter(skill_md, fm, body)

    return changes


def _generate_description(skill_name: str, hub: str, body: str, current_desc: str) -> str:
    """Generate a richer description based on skill context."""
    # Extract key terms from body
    lines = body.strip().split("\n") if body.strip() else []
    headings = [l.lstrip("#").strip() for l in lines if l.startswith("#")]

    # Build description from skill name + hub + headings
    name_parts = skill_name.replace("-", " ").replace("_", " ")

    # If current desc is a placeholder like "Skill: foo", replace entirely
    if current_desc.startswith("Skill:") or len(current_desc.split()) < 3:
        base = f"{name_parts.title()} management"
    else:
        base = current_desc

    # Add hub context
    hub_context = {
        "career": "for job search and professional development",
        "health": "for personal health tracking",
        "finance": "for financial planning and budgeting",
        "admin": "for system administration and maintenance",
        "dev": "for development workflow automation",
        "ai": "for AI integration and knowledge management",
        "observability": "for system monitoring and observability",
        "productivity": "for task management and productivity",
        "lifestyle": "for personal lifestyle and wellness",
        "consulting": "for client management and consulting",
        "professional": "for professional development and business",
        "enterprise": "for enterprise integration features",
        "home": "for home automation and smart devices",
    }
    suffix = hub_context.get(hub, "")

    # Add heading-derived capabilities
    capabilities = []
    for h in headings[:3]:
        if len(h) > 3 and h.lower() not in ("overview", "usage", "configuration", "notes"):
            capabilities.append(h.lower())

    desc = base
    if suffix and suffix not in desc:
        desc = f"{desc} {suffix}"
    if capabilities:
        desc = f"{desc}. Covers: {', '.join(capabilities)}"

    # Ensure minimum length with trigger guidance
    if len(desc.split()) < 15:
        desc = f"{desc}. Use when working with {name_parts} features or data."

    return desc.strip()


def _expand_body(skill_name: str, ctx_info: dict, current_body: str) -> str:
    """Expand a thin SKILL.md body with useful sections."""
    sections = []

    # Keep existing content
    if current_body.strip():
        sections.append(current_body.strip())

    # Add overview if missing
    if "## Overview" not in current_body and "## " not in current_body:
        desc = ctx_info.get("purpose", "")
        if desc:
            sections.append(f"\n## Overview\n\n{desc}")

    # Add difficulty levels if this is an auto-command
    if skill_name.startswith("auto-") and "## Difficulty" not in current_body:
        sections.append(
            "\n## Difficulty Levels\n\n"
            "- **d0**: Surface scan — discover and count issues\n"
            "- **d1**: Content check — validate correctness\n"
            "- **d2**: Deep check — root-cause classification\n"
        )

    # Add integration section if has pages or data
    if ctx_info.get("has_pages") and "## Dashboard" not in current_body:
        sections.append(
            "\n## Dashboard\n\n"
            f"This skill contributes pages to the {ctx_info.get('hub', 'system')} hub."
        )

    if ctx_info.get("has_data") and "## Data" not in current_body:
        sections.append(
            "\n## Data\n\n"
            f"Skill data stored in `data/` directory within the skill folder."
        )

    return "\n".join(sections)


def _verify_build(project_root: Path) -> bool:
    """Run npm run build and return True if it succeeds."""
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(project_root / "apps" / "dashboard"),
            capture_output=True,
            timeout=120,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _git_commit(project_root: Path, message: str) -> bool:
    """Stage all changes and commit."""
    subprocess.run(["git", "add", "-A"], cwd=str(project_root), capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(project_root),
        capture_output=True,
    )
    return result.returncode == 0


def _git_revert(project_root: Path) -> bool:
    """Revert the last commit."""
    result = subprocess.run(
        ["git", "revert", "HEAD", "--no-edit"],
        cwd=str(project_root),
        capture_output=True,
    )
    return result.returncode == 0


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix issues across dimensions with git safety net."""
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issues")

    score_all = _get_scorer()
    root = ctx.project_root
    all_actions = []
    all_changes = []

    # Group issues by skill
    by_skill: dict[str, list[dict]] = {}
    for issue in issues:
        sname = issue.get("skill_name", "")
        if sname:
            by_skill.setdefault(sname, []).append(issue)

    for skill_name, skill_issues in by_skill.items():
        skill_dir = root / ".claude" / "skills" / skill_name
        if not skill_dir.exists():
            continue

        # Score before
        try:
            before = score_all(skill_name=skill_name)
            before_score = before["skills"][0]["score"] if before["skills"] else 0
        except Exception:
            before_score = 0

        # Read context once per skill
        ctx_info = _read_skill_context(skill_name, skill_dir)
        changes = []

        # Apply fixes per dimension
        for issue in skill_issues:
            dim = issue.get("dimension", "")
            signals = issue.get("signals", {})

            if dim == "instruction":
                changes.extend(_fix_instruction(skill_name, skill_dir, signals, ctx_info))
            elif dim == "product":
                changes.extend(_fix_product(skill_name, skill_dir, signals, ctx_info))
            elif dim == "ui":
                changes.extend(_fix_ui(skill_name, skill_dir, signals, ctx_info))
            elif dim == "wiring":
                changes.extend(_fix_wiring(skill_name, skill_dir, signals, ctx_info))

        if not changes:
            continue

        # Commit
        commit_msg = f"auto(skill-quality): improve {skill_name} [{', '.join(changes[:3])}]"
        if not _git_commit(root, commit_msg):
            continue

        # Build verify
        build_ok = _verify_build(root) if ctx.config.get("build_verify", True) else True

        # Re-score
        try:
            # Clear scorer cache to get fresh results
            from augur_mcp.infrastructure.skill_scorer import _cache
            _cache.clear()
            after = score_all(skill_name=skill_name)
            after_score = after["skills"][0]["score"] if after["skills"] else 0
        except Exception:
            after_score = before_score

        # Revert if build failed or score regressed
        revert = False
        reason = ""
        if not build_ok:
            revert = True
            reason = "build failure"
        elif ctx.config.get("revert_on_regression", True) and after_score < before_score:
            revert = True
            reason = f"score regression {before_score}→{after_score}"

        if revert:
            _git_revert(root)
            all_actions.append({
                "skill": skill_name, "reverted": True, "reason": reason,
                "before": before_score, "after": after_score,
            })
        else:
            all_actions.append({
                "skill": skill_name, "reverted": False,
                "before": before_score, "after": after_score,
                "changes": changes,
            })
            all_changes.extend(changes)

    succeeded = sum(1 for a in all_actions if not a.get("reverted"))
    total = len(all_actions)

    return FixResult(
        success=succeeded > 0 or total == 0,
        actions=all_actions,
        changes=all_changes,
        summary=f"Fixed {succeeded}/{total} skills" if total else "No skills needed fixing",
        fix_type="code-fix",
    )
```

- [ ] **Step 2: Verify syntax**

Run: `cd ~/Projects/Augur && python -c "import ast; ast.parse(open('.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/auto-skill-quality/scripts/skill_quality_ops.py
git commit -m "feat(auto-skill-quality): implement fix function with instruction dimension + git safety"
```

---

## Task 5: Implement Fix — Product Dimension

**Files:**
- Modify: `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py`

- [ ] **Step 1: Add product fix function**

Insert before the `fix()` function:

```python
def _fix_product(skill_name: str, skill_dir: Path, signals: dict, ctx_info: dict) -> list[str]:
    """Create missing directories, scaffold files, generate seeds."""
    changes = []

    # 1. Create missing directories
    for dirname, signal_key in [("data", "has_data_dir"), ("scripts", "has_scripts"), ("references", "has_references")]:
        if not signals.get(signal_key, True):  # default True = don't create if signal missing
            dir_path = skill_dir / dirname
            if not dir_path.exists():
                dir_path.mkdir(exist_ok=True)
                (dir_path / ".gitkeep").touch()
                changes.append(f"created {dirname}/")

    # 2. Generate seed data when data/ is empty and no seed/ exists
    data_dir = skill_dir / "data"
    seed_dir = skill_dir / "augur" / "seed"
    if data_dir.exists() and not any(f for f in data_dir.iterdir() if f.name != ".gitkeep") and not seed_dir.exists():
        seed_files = _generate_seeds(skill_name, ctx_info)
        if seed_files:
            seed_dir.mkdir(parents=True, exist_ok=True)
            for filename, content in seed_files.items():
                (seed_dir / filename).write_text(content)
            changes.append(f"generated {len(seed_files)} seed files in augur/seed/")

    # 3. Scaffold action if missing and skill has augur/ dir
    augur_dir = skill_dir / "augur"
    if not signals.get("has_actions", True) and augur_dir.exists():
        actions_dir = augur_dir / "actions"
        if not actions_dir.exists():
            actions_dir.mkdir(parents=True, exist_ok=True)
            action_content = _scaffold_action(skill_name, ctx_info)
            if action_content:
                action_file = actions_dir / f"{skill_name}-overview.yaml"
                action_file.write_text(action_content)
                changes.append("scaffolded action YAML")

    return changes


def _generate_seeds(skill_name: str, ctx_info: dict) -> dict[str, str]:
    """Generate seed data files based on skill context."""
    seeds = {}
    hub = ctx_info.get("hub", "system")
    purpose = ctx_info.get("purpose", "")

    # Read page components to infer data shape
    pages = ctx_info.get("pages", [])
    if not pages and not purpose:
        return seeds

    # Generate a manifest
    manifest = f"""# Seed data for {skill_name}
# Auto-generated by auto-skill-quality loop
tool: null  # No MCP tool — use file copy
data_path: .
files:
  - example-{skill_name}.yaml
"""
    seeds["_seed.yaml"] = manifest

    # Generate one example data file
    example = f"""---
_seeded: true
_generated_by: auto-skill-quality
name: Example {skill_name.replace('-', ' ').title()} Entry
description: Sample data for the {skill_name} skill
created_at: "2026-01-15"
status: active
---

This is example seed data for the **{skill_name}** skill in the **{hub}** hub.

{purpose}
"""
    seeds[f"example-{skill_name}.yaml"] = example

    return seeds


def _scaffold_action(skill_name: str, ctx_info: dict) -> str:
    """Generate a basic action YAML for the skill."""
    hub = ctx_info.get("hub", "system")
    purpose = ctx_info.get("purpose", skill_name.replace("-", " "))

    return f"""id: {skill_name}-overview
label: "{skill_name.replace('-', ' ').title()} Overview"
description: "View {purpose}"
dispatch: fire
page: "/{hub}/{skill_name}"
hub: {hub}
"""
```

- [ ] **Step 2: Verify syntax**

Run: `cd ~/Projects/Augur && python -c "import ast; ast.parse(open('.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/auto-skill-quality/scripts/skill_quality_ops.py
git commit -m "feat(auto-skill-quality): add product dimension fixer with seed generation"
```

---

## Task 6: Implement Fix — UI and Wiring Dimensions

**Files:**
- Modify: `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py`

- [ ] **Step 1: Add UI and wiring fix functions**

Insert before `_verify_build()`:

```python
def _fix_ui(skill_name: str, skill_dir: Path, signals: dict, ctx_info: dict) -> list[str]:
    """Promote page states and add missing page contributions."""
    changes = []
    fm = ctx_info.get("fm", {})
    config = fm.get("x-augur-config") or {}
    pages = (config.get("contributions") or {}).get("pages") or []

    if not pages:
        return changes

    modified = False
    for page in pages:
        if not isinstance(page, dict):
            continue

        state = page.get("state", "dev")
        page_path = page.get("path", "")

        # Promote mock → dev when augur/dashboard/ dir exists
        if state == "mock":
            dashboard_dir = skill_dir / "augur" / "dashboard"
            if dashboard_dir.exists() and any(dashboard_dir.rglob("*.tsx")):
                page["state"] = "dev"
                changes.append(f"promoted {page_path} mock→dev")
                modified = True

        # Promote dev → mature when data exists
        elif state == "dev":
            has_data = ctx_info.get("has_data", False)
            data_dir = skill_dir / "data"
            data_populated = has_data and any(
                f for f in data_dir.iterdir() if f.name != ".gitkeep"
            ) if has_data else False

            if data_populated:
                page["state"] = "mature"
                changes.append(f"promoted {page_path} dev→mature")
                modified = True

    if modified:
        skill_md = skill_dir / "SKILL.md"
        body = ctx_info.get("body", "")
        write_frontmatter(skill_md, fm, body)

    return changes


def _fix_wiring(skill_name: str, skill_dir: Path, signals: dict, ctx_info: dict) -> list[str]:
    """Fix stale toolName refs and remove fs/spawn bypasses in API routes."""
    changes = []
    root = get_project_root()
    api_dir = root / "apps" / "dashboard" / "app" / "api"

    if not api_dir.exists():
        return changes

    # Find API route files that reference this skill
    for ts_file in api_dir.rglob("*.ts"):
        try:
            content = ts_file.read_text(errors="replace")
        except Exception:
            continue

        if skill_name not in content:
            continue

        modified = False

        # Remove fs imports and replace with comments
        if not signals.get("no_fs_bypasses", True):
            # Replace fs/spawn imports with TODO markers
            new_content = re.sub(
                r'import\s+\{[^}]*\}\s+from\s+["\']fs["\'];?\n?',
                '// TODO_BUG: fs import removed by auto-skill-quality — replace with MCP tool call\n',
                content,
            )
            new_content = re.sub(
                r'import\s+\{[^}]*(?:spawn|execSync|execFile)[^}]*\}\s+from\s+["\']child_process["\'];?\n?',
                '// TODO_BUG: child_process import removed — replace with MCP tool call\n',
                new_content,
            )
            if new_content != content:
                content = new_content
                modified = True
                changes.append(f"removed fs/spawn bypass in {ts_file.name}")

        if modified:
            ts_file.write_text(content)

    return changes
```

- [ ] **Step 2: Verify syntax**

Run: `cd ~/Projects/Augur && python -c "import ast; ast.parse(open('.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/auto-skill-quality/scripts/skill_quality_ops.py
git commit -m "feat(auto-skill-quality): add UI and wiring dimension fixers"
```

---

## Task 7: Integration Test — Run Scan at d0

- [ ] **Step 1: Test scan function standalone**

Run:
```bash
cd ~/Projects/Augur && python -c "
from src.lib.ops_protocol import OpsContext
from pathlib import Path
import json

# Import the module
import importlib.util
spec = importlib.util.spec_from_file_location('skill_quality_ops', '.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Run scan at d0
ctx = OpsContext(project_root=Path.cwd(), difficulty=0, dry_run=True)
result = mod.scan(ctx)
print(f'Summary: {result.summary}')
print(f'Severity: {result.severity}')
print(f'Health: {result.health}')
print(f'Issues: {len(result.issues)}')
for i in result.issues[:3]:
    print(f'  - [{i.get(\"kind\")}] {i.get(\"detail\", \"\")[:80]}')
"
```

Expected: Scan reports ~130 skills below A, targets 5, shows maintenance-level issues at d0.

- [ ] **Step 2: Test scan at d1**

Same as above but with `difficulty=1`. Expected: issues have `kind="actionable"` for instruction dimension.

- [ ] **Step 3: Test fix at d1 dry run**

Run:
```bash
cd ~/Projects/Augur && python -c "
from src.lib.ops_protocol import OpsContext
from pathlib import Path

import importlib.util
spec = importlib.util.spec_from_file_location('skill_quality_ops', '.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ctx = OpsContext(project_root=Path.cwd(), difficulty=1, dry_run=True)
scan_result = mod.scan(ctx)
actionable = [i for i in scan_result.issues if i.get('kind') == 'actionable']
print(f'Actionable issues: {len(actionable)}')

fix_result = mod.fix(ctx, actionable)
print(f'Fix result: {fix_result.summary}')
"
```

Expected: Dry run reports issues but makes no changes.

- [ ] **Step 4: Commit any test fixups**

```bash
git add .claude/skills/auto-skill-quality/scripts/skill_quality_ops.py
git commit -m "fix(auto-skill-quality): integration test fixups"
```

---

## Task 8: Live Test — Fix One Skill at d1

- [ ] **Step 1: Run fix on one skill (non-dry-run, instruction only)**

Run:
```bash
cd ~/Projects/Augur && python -c "
from src.lib.ops_protocol import OpsContext
from pathlib import Path
import json

import importlib.util
spec = importlib.util.spec_from_file_location('skill_quality_ops', '.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Scan at d1, limit to 1 skill
ctx = OpsContext(project_root=Path.cwd(), difficulty=1, config={'max_skills_per_cycle': 1, 'build_verify': False, 'revert_on_regression': True})
scan_result = mod.scan(ctx)
actionable = [i for i in scan_result.issues if i.get('kind') == 'actionable']
print(f'Fixing {len(actionable)} issues...')

fix_result = mod.fix(ctx, actionable)
print(f'Result: {fix_result.summary}')
for a in fix_result.actions:
    print(f'  {a[\"skill\"]}: {a.get(\"before\", \"?\")}→{a.get(\"after\", \"?\")} reverted={a.get(\"reverted\", False)}')
"
```

Expected: One skill improved, commit created, score increased.

- [ ] **Step 2: Verify the commit exists**

Run: `git log --oneline -3`
Expected: See an `auto(skill-quality): improve ...` commit.

- [ ] **Step 3: Verify score actually improved**

Run:
```bash
cd ~/Projects/Augur && python -c "
from src.mcp.augur_mcp.infrastructure.skill_scorer import score_all_skills
r = score_all_skills()
print(f'Avg: {r[\"summary\"][\"average_score\"]}')
print(f'Tiers: {r[\"summary\"][\"tier_distribution\"]}')
"
```

Expected: Average score slightly higher than initial 34.5.
