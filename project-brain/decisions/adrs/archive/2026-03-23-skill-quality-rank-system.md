# Skill Quality & Rank System Implementation Plan

**ADR:** ADR-492

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add type-aware scoring rubrics, behavioral tier gates, seed eval generation, user feedback hooks, and imported skill metadata to the Augur skill quality system.

**Architecture:** Extends the existing `skill_scorer.py` with per-type rubrics and a two-phase tier computation (structural + behavioral gate). Auto-skill-quality loop gains seed eval generation at d2+ and rank.json sidecar writes. New feedback hook collects post-execution user signals. Import metadata stamped via shared utility in frontmatter_utils.py.

**Tech Stack:** Python 3.11+, YAML frontmatter, JSON sidecar files, Claude Code PostToolUse hooks

**Spec:** `docs/superpowers/specs/2026-03-23-skill-quality-rank-system-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/mcp/augur_mcp/infrastructure/skill_scorer.py` | Type-aware rubrics, two-phase tier computation, behavioral reader |
| `skills/auto-skill-quality/scripts/skill_quality_ops.py` | Seed eval generation, rank.json writer in scan(), feedback-informed evals |
| `skills/auto-skill-quality/scripts/feedback_hook.py` | **New.** PostToolUse CLI for lightweight feedback collection |
| `src/lib/frontmatter_utils.py` | Shared `stamp_import_metadata()` utility |
| `skills/skillstore/scripts/mcp/__init__.py` | Call stamp on skill install from skills.sh/GitHub |
| `skills/import/scripts/mcp/__init__.py` | Call stamp on skill install from URL/repo |
| `CLAUDE.md` | Add `evals/` to allowed skill root dirs (rule 19) |
| `tests/mcp/test_skill_scorer.py` | **New.** Tests for rubric resolution, tier computation, behavioral reading |
| `tests/scripts/test_feedback_hook.py` | **New.** Tests for feedback hook logic |
| `tests/scripts/test_seed_evals.py` | **New.** Tests for seed eval generation per type |

---

### Task 1: Prerequisites — Fix Scorer Path and CLAUDE.md

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/skill_scorer.py:279`
- Modify: `skills/auto-skill-quality/scripts/skill_quality_ops.py:749,904`
- Modify: `CLAUDE.md` (rule 19)
- Modify: `.github/scripts/validate_skill_structure.py:78`

- [ ] **Step 1: Fix the legacy skills_dir path in skill_scorer.py**

In `skill_scorer.py` line 279, change the skills directory from the legacy `.claude/skills` to the canonical `skills/` path:

```python
# Before (line 279):
skills_dir = root / ".claude" / "skills"

# After:
skills_dir = root / "skills"
```

- [ ] **Step 2: Fix the legacy skills_dir path in skill_quality_ops.py**

Fix two occurrences in `skill_quality_ops.py`:

```python
# Line 749 in fix():
# Before:
skill_dir = root / ".claude" / "skills" / skill_name
# After:
skill_dir = root / "skills" / skill_name

# Line 904 in llm_fix():
# Before:
skill_dir = ctx.project_root / ".claude" / "skills" / worst_skill
# After:
skill_dir = ctx.project_root / "skills" / worst_skill
```

- [ ] **Step 3: Add `evals/` to CLAUDE.md rule 19**

In CLAUDE.md, find rule 19 and add `evals/` to the list of standard dirs at skill root:

```markdown
# Before:
Standard dirs at skill root (`commands/`, `references/`, `scripts/`, `assets/`, `examples/`, `modules/`) are portable across AI clients.

# After:
Standard dirs at skill root (`commands/`, `references/`, `scripts/`, `assets/`, `examples/`, `evals/`, `modules/`) are portable across AI clients.
```

- [ ] **Step 4: Add `evals` to validate_skill_structure.py ALLOWED_ROOT_DIRS**

In `.github/scripts/validate_skill_structure.py` line 78, add `"evals"` to the set:

```python
# Before:
ALLOWED_ROOT_DIRS = {
    "commands", "references", "scripts", "assets",
    "examples", "modules", "augur",
}

# After:
ALLOWED_ROOT_DIRS = {
    "commands", "references", "scripts", "assets",
    "examples", "evals", "modules", "augur",
}
```

- [ ] **Step 5: Verify scorer still works with new path**

Run: `cd ~/Projects/Augur && python3 -c "from src.mcp.augur_mcp.infrastructure.skill_scorer import score_all_skills; r = score_all_skills(); print(f'{r[\"summary\"][\"total\"]} skills scored')"`

Expected: `186 skills scored` (or close — should match the skill count)

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/skill_scorer.py skills/auto-skill-quality/scripts/skill_quality_ops.py CLAUDE.md .github/scripts/validate_skill_structure.py
git commit -m "fix: use canonical skills/ path everywhere, add evals/ to allowed dirs"
```

---

### Task 2: Type-Aware Rubrics in skill_scorer.py

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/skill_scorer.py`
- Create: `tests/mcp/test_skill_scorer.py`

- [ ] **Step 1: Write failing tests for rubric resolution**

Create `tests/mcp/test_skill_scorer.py`:

```python
"""Tests for type-aware skill scoring rubrics."""
import pytest


def test_resolve_rubric_command_type():
    """Command skills should get 50% instruction, 0% UI weight."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _resolve_rubric

    fm = {"x-augur-type": "command"}
    rubric = _resolve_rubric(fm)
    assert rubric["weights"]["instruction"] == 0.50
    assert rubric["weights"]["ui"] == 0.0
    assert rubric["weights"]["wiring"] == 0.25


def test_resolve_rubric_autoloop_type():
    """Autoloop skills should get 45% wiring weight."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _resolve_rubric

    fm = {"x-augur-type": "autoloop"}
    rubric = _resolve_rubric(fm)
    assert rubric["weights"]["wiring"] == 0.45
    assert rubric["weights"]["instruction"] == 0.20


def test_resolve_rubric_domain_high_scope():
    """Domain skills with 8+ tools should use high-scope rubric."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _resolve_rubric

    fm = {
        "x-augur-type": "domain",
        "x-augur-mcp-tools": [f"tool-{i}" for i in range(10)],
        "x-augur-dashboard-pages": ["/a", "/b"],
    }
    rubric = _resolve_rubric(fm)
    assert rubric["weights"]["ui"] == 0.20
    assert rubric["weights"]["instruction"] == 0.25


def test_resolve_rubric_domain_low_scope():
    """Domain skills with few tools should use low-scope rubric."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _resolve_rubric

    fm = {
        "x-augur-type": "domain",
        "x-augur-mcp-tools": ["tool-1", "tool-2"],
    }
    rubric = _resolve_rubric(fm)
    assert rubric["weights"]["ui"] == 0.05
    assert rubric["weights"]["instruction"] == 0.35


def test_resolve_rubric_domain_high_by_pages():
    """Domain skills with 3+ pages should use high-scope rubric."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _resolve_rubric

    fm = {
        "x-augur-type": "domain",
        "x-augur-mcp-tools": ["tool-1"],
        "x-augur-dashboard-pages": ["/a", "/b", "/c"],
    }
    rubric = _resolve_rubric(fm)
    assert rubric["weights"]["ui"] == 0.20


def test_resolve_rubric_unknown_type_falls_back():
    """Unknown types should fall back to domain-low rubric."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _resolve_rubric

    fm = {"x-augur-type": "exotic-new-type"}
    rubric = _resolve_rubric(fm)
    assert rubric["weights"]["instruction"] == 0.35  # domain-low default


def test_resolve_rubric_missing_type():
    """Missing x-augur-type should default to domain-low."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _resolve_rubric

    fm = {}
    rubric = _resolve_rubric(fm)
    assert rubric["weights"]["instruction"] == 0.35


def test_rubric_weights_sum_to_one():
    """All rubric weight sets must sum to 1.0."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import RUBRICS

    for name, rubric in RUBRICS.items():
        total = sum(rubric["weights"].values())
        assert abs(total - 1.0) < 0.01, f"Rubric {name} weights sum to {total}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/mcp/test_skill_scorer.py -v`

Expected: FAIL — `_resolve_rubric` and `RUBRICS` don't exist yet.

- [ ] **Step 3: Implement RUBRICS dict and _resolve_rubric()**

Add to `skill_scorer.py` after the `DEFAULT_THRESHOLDS` line (line 24):

```python
RUBRICS = {
    "domain-high": {
        "weights": {"instruction": 0.25, "product": 0.35, "ui": 0.20, "wiring": 0.20},
    },
    "domain-low": {
        "weights": {"instruction": 0.35, "product": 0.40, "ui": 0.05, "wiring": 0.20},
    },
    "command": {
        "weights": {"instruction": 0.50, "product": 0.25, "ui": 0.0, "wiring": 0.25},
    },
    "autoloop": {
        "weights": {"instruction": 0.20, "product": 0.30, "ui": 0.05, "wiring": 0.45},
    },
    "library-reference": {
        "weights": {"instruction": 0.60, "product": 0.20, "ui": 0.0, "wiring": 0.20},
    },
    "runbook": {
        "weights": {"instruction": 0.55, "product": 0.25, "ui": 0.0, "wiring": 0.20},
    },
    "template": {
        "weights": {"instruction": 0.40, "product": 0.35, "ui": 0.10, "wiring": 0.15},
    },
    "meta": {
        "weights": {"instruction": 0.50, "product": 0.30, "ui": 0.0, "wiring": 0.20},
    },
    "integration": {
        "weights": {"instruction": 0.35, "product": 0.35, "ui": 0.10, "wiring": 0.20},
    },
}


def _resolve_rubric(fm: dict) -> dict:
    """Resolve the scoring rubric for a skill based on its type and scope."""
    skill_type = fm.get("x-augur-type", "domain")
    if skill_type == "domain":
        tools = len(fm.get("x-augur-mcp-tools", []))
        pages = len(fm.get("x-augur-dashboard-pages", []))
        scope = "domain-high" if (tools >= 8 or pages >= 3) else "domain-low"
        return RUBRICS[scope]
    return RUBRICS.get(skill_type, RUBRICS["domain-low"])
```

- [ ] **Step 4: Modify score_all_skills() to use type-aware weights**

In `score_all_skills()`, replace the hardcoded `weights` usage with per-skill rubric resolution. Change lines 299-304:

```python
# Before:
composite = (
    instruction["score"] * weights.get("instruction", 0.30)
    + product["score"] * weights.get("product", 0.40)
    + ui["score"] * weights.get("ui", 0.15)
    + wiring["score"] * weights.get("wiring", 0.15)
)

# After:
rubric = _resolve_rubric(fm)
skill_weights = rubric["weights"]
composite = (
    instruction["score"] * skill_weights["instruction"]
    + product["score"] * skill_weights["product"]
    + ui["score"] * skill_weights["ui"]
    + wiring["score"] * skill_weights["wiring"]
)
```

Also update the dimension output dict (lines 317-322) to use `skill_weights` instead of `weights`:

```python
"dimensions": {
    "instruction": {**instruction, "weight": skill_weights["instruction"], "weighted": round(instruction["score"] * skill_weights["instruction"], 1)},
    "product": {**product, "weight": skill_weights["product"], "weighted": round(product["score"] * skill_weights["product"], 1)},
    "ui": {**ui, "weight": skill_weights["ui"], "weighted": round(ui["score"] * skill_weights["ui"], 1)},
    "wiring": {**wiring, "weight": skill_weights["wiring"], "weighted": round(wiring["score"] * skill_weights["wiring"], 1)},
},
```

Add `rubric_name` to each skill result so rank.json can record which rubric was used. Determine the name:

```python
rubric = _resolve_rubric(fm)
rubric_name = next((k for k, v in RUBRICS.items() if v is rubric), "domain-low")
```

Add to the results.append dict: `"rubric": rubric_name,`

Note: Line numbers referenced above are approximate — they will shift after Task 1's edits. Use the string patterns (e.g., `DEFAULT_WEIGHTS`, `composite =`) to locate the correct lines.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/mcp/test_skill_scorer.py -v`

Expected: All 8 tests PASS.

- [ ] **Step 6: Validate rubric distribution against real skills**

Run: `cd ~/Projects/Augur && python3 -c "
from src.mcp.augur_mcp.infrastructure.skill_scorer import score_all_skills
r = score_all_skills()
from collections import Counter
rubrics = Counter(s.get('rubric', 'unknown') for s in r['skills'])
for k, v in sorted(rubrics.items()):
    print(f'{k}: {v}')
"`

Expected: Distribution across rubric types. Verify domain-high has ~15 skills, domain-low ~31, command ~52, autoloop ~75.

- [ ] **Step 7: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/skill_scorer.py tests/mcp/test_skill_scorer.py
git commit -m "feat: type-aware scoring rubrics with per-type dimension weights"
```

---

### Task 3: Two-Phase Tier Computation with Behavioral Gate

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/skill_scorer.py`
- Modify: `tests/mcp/test_skill_scorer.py`

- [ ] **Step 1: Write failing tests for tier computation**

Append to `tests/mcp/test_skill_scorer.py`:

```python
import json
import tempfile
from pathlib import Path


def test_compute_tier_no_evals_caps_at_B():
    """Structural score >= 55 without evals should cap at tier B."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _compute_tier

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        result = _compute_tier(80.0, evals_dir)
        assert result["tier"] == "B"
        assert result["behavioral"] is None


def test_compute_tier_structural_below_55():
    """Structural score < 55 should be C/D/F regardless of evals."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _compute_tier

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        result = _compute_tier(40.0, evals_dir)
        assert result["tier"] == "C"


def _make_benchmark(pass_rate_mean: float, runs_count: int = 3, timestamp: str = "2026-03-23T00:00:00Z") -> dict:
    """Helper to create a minimal benchmark.json structure."""
    return {
        "metadata": {"timestamp": timestamp},
        "runs": [{"eval_id": i} for i in range(runs_count)],
        "run_summary": {
            "with_skill": {"pass_rate": {"mean": pass_rate_mean}},
        },
    }


def _make_evals(confidence: str = "seed") -> dict:
    """Helper to create a minimal evals.json structure."""
    return {
        "skill_name": "test",
        "evals": [{"id": 1, "prompt": "test", "confidence": confidence}],
    }


def test_compute_tier_seed_evals_promote_to_A():
    """Structural >= 65 with seed evals passing >= 60% should be tier A."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _compute_tier

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        (evals_dir / "benchmark.json").write_text(json.dumps(_make_benchmark(0.72)))
        (evals_dir / "evals.json").write_text(json.dumps(_make_evals("seed")))
        result = _compute_tier(70.0, evals_dir)
        assert result["tier"] == "A"


def test_compute_tier_verified_evals_promote_to_S():
    """Structural >= 75 with verified evals >= 80% should be tier S."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _compute_tier

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        (evals_dir / "benchmark.json").write_text(json.dumps(_make_benchmark(0.85)))
        (evals_dir / "evals.json").write_text(json.dumps(_make_evals("verified")))
        result = _compute_tier(80.0, evals_dir)
        assert result["tier"] == "S"


def test_compute_tier_verified_but_low_structural_not_S():
    """Verified evals >= 80% but structural < 75 should be A, not S."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _compute_tier

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        (evals_dir / "benchmark.json").write_text(json.dumps(_make_benchmark(0.85)))
        (evals_dir / "evals.json").write_text(json.dumps(_make_evals("verified")))
        result = _compute_tier(68.0, evals_dir)
        assert result["tier"] == "A"


def test_compute_tier_low_pass_rate_gets_B_plus():
    """Evals exist but pass_rate < 60% should give B+."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _compute_tier

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        (evals_dir / "benchmark.json").write_text(json.dumps(_make_benchmark(0.40)))
        (evals_dir / "evals.json").write_text(json.dumps(_make_evals("seed")))
        result = _compute_tier(60.0, evals_dir)
        assert result["tier"] == "B+"


def test_read_behavioral_missing_benchmark():
    """Missing benchmark.json should return None."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _read_behavioral

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        assert _read_behavioral(evals_dir) is None


def test_read_behavioral_valid_benchmark():
    """Valid benchmark.json should return behavioral dict with confidence from evals.json."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _read_behavioral

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        (evals_dir / "benchmark.json").write_text(json.dumps(_make_benchmark(0.65)))
        (evals_dir / "evals.json").write_text(json.dumps(_make_evals("seed")))
        result = _read_behavioral(evals_dir)
        assert result["confidence"] == "seed"
        assert result["pass_rate"] == 0.65


def test_read_behavioral_malformed_json():
    """Malformed benchmark.json should return None."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _read_behavioral

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        (evals_dir / "benchmark.json").write_text("not valid json {{{")
        assert _read_behavioral(evals_dir) is None


def test_read_behavioral_mixed_confidence_is_seed():
    """If any eval is seed, aggregate confidence should be seed."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import _read_behavioral

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        (evals_dir / "benchmark.json").write_text(json.dumps(_make_benchmark(0.80)))
        mixed_evals = {
            "skill_name": "test",
            "evals": [
                {"id": 1, "prompt": "a", "confidence": "verified"},
                {"id": 2, "prompt": "b", "confidence": "seed"},
            ],
        }
        (evals_dir / "evals.json").write_text(json.dumps(mixed_evals))
        result = _read_behavioral(evals_dir)
        assert result["confidence"] == "seed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/mcp/test_skill_scorer.py -v -k "compute_tier or read_behavioral"`

Expected: FAIL — `_compute_tier` and `_read_behavioral` don't exist yet.

- [ ] **Step 3: Implement _read_behavioral() and _compute_tier()**

Add to `skill_scorer.py` after `_resolve_rubric()`:

```python
def _read_behavioral(evals_dir: Path) -> dict | None:
    """Read behavioral eval results from evals/benchmark.json.

    Reads actual eval run results (benchmark.json), NOT the computed
    rank snapshot (rank.json) — avoids circular read/write bootstrap.
    Falls back to checking evals.json for confidence metadata.
    """
    benchmark_file = evals_dir / "benchmark.json"
    evals_file = evals_dir / "evals.json"

    if not benchmark_file.exists():
        return None

    try:
        bm = json.loads(benchmark_file.read_text())
        summary = bm.get("run_summary", {}).get("with_skill", {})
        pass_rate = summary.get("pass_rate", {})
        mean_pass = pass_rate.get("mean", 0.0) if isinstance(pass_rate, dict) else pass_rate

        # Determine confidence from evals.json
        confidence = "seed"
        if evals_file.exists():
            try:
                evals_data = json.loads(evals_file.read_text())
                evals_list = evals_data.get("evals", [])
                if evals_list and all(e.get("confidence") == "verified" for e in evals_list):
                    confidence = "verified"
            except (json.JSONDecodeError, KeyError):
                pass

        eval_count = len(bm.get("runs", []))
        return {
            "confidence": confidence,
            "pass_rate": mean_pass,
            "eval_count": eval_count,
            "last_run": bm.get("metadata", {}).get("timestamp"),
        }
    except (json.JSONDecodeError, KeyError):
        return None


def _compute_tier(structural_score: float, evals_dir: Path) -> dict:
    """Two-phase tier: structural base (caps at B) + behavioral gate (promotes above B)."""
    if structural_score >= 55:
        base_tier = "B"
    elif structural_score >= 35:
        base_tier = "C"
    elif structural_score >= 15:
        base_tier = "D"
    else:
        base_tier = "F"

    behavioral = _read_behavioral(evals_dir)
    if behavioral is None:
        return {"tier": base_tier, "behavioral": None}

    if base_tier != "B":
        return {"tier": base_tier, "behavioral": behavioral}

    if behavioral["confidence"] == "verified" and behavioral["pass_rate"] >= 0.80 and structural_score >= 75:
        return {"tier": "S", "behavioral": behavioral}
    elif behavioral["pass_rate"] >= 0.60 and structural_score >= 65:
        return {"tier": "A", "behavioral": behavioral}
    elif behavioral["eval_count"] > 0:
        return {"tier": "B+", "behavioral": behavioral}
    else:
        return {"tier": "B", "behavioral": behavioral}
```

- [ ] **Step 4: Wire _compute_tier() into score_all_skills()**

Replace the old `tier = _get_tier(composite, thresholds)` (line 306) and update the result dict:

```python
# After computing composite score:
evals_dir = skill_dir / "evals"
tier_result = _compute_tier(composite, evals_dir)

results.append({
    "name": sname,
    "hub": skill_hub,
    "score": composite,
    "tier": tier_result["tier"],
    "rubric": rubric_name,
    "behavioral": tier_result["behavioral"],
    "dimensions": {
        # ... (same as before with skill_weights)
    },
})
```

Remove the old `_get_tier()` function — per CLAUDE.md rule 14, no backward-compatibility stubs. Search the codebase for any callers first (`grep -r "_get_tier" src/ skills/`). If none, delete it.

- [ ] **Step 5: Run all scorer tests**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/mcp/test_skill_scorer.py -v`

Expected: All tests PASS (rubric tests + tier tests).

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/skill_scorer.py tests/mcp/test_skill_scorer.py
git commit -m "feat: two-phase tier computation with behavioral gate (S/A/B+/B/C/D/F)"
```

---

### Task 4: stamp_import_metadata() in frontmatter_utils.py

**Files:**
- Modify: `src/lib/frontmatter_utils.py`
- Create: `tests/src/test_stamp_import_metadata.py`

- [ ] **Step 1: Write failing test**

Create `tests/src/test_stamp_import_metadata.py`:

```python
"""Tests for stamp_import_metadata in frontmatter_utils."""
import tempfile
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter


def test_stamp_import_metadata_adds_fields():
    """stamp_import_metadata should add source, url, version, date to frontmatter."""
    from src.lib.frontmatter_utils import stamp_import_metadata

    with tempfile.TemporaryDirectory() as td:
        skill_path = Path(td)
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("---\nname: test-skill\ndescription: A test\n---\n\nBody content.\n")

        stamp_import_metadata(skill_path, "github", "https://github.com/user/repo", "1.2.0")

        fm, body = parse_frontmatter(skill_md)
        assert fm["x-augur-source"] == "github"
        assert fm["x-augur-source-url"] == "https://github.com/user/repo"
        assert fm["x-augur-source-version"] == "1.2.0"
        assert "x-augur-imported-at" in fm
        assert "Body content." in body


def test_stamp_import_metadata_preserves_existing():
    """Existing frontmatter fields should be preserved."""
    from src.lib.frontmatter_utils import stamp_import_metadata

    with tempfile.TemporaryDirectory() as td:
        skill_path = Path(td)
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("---\nname: test-skill\nx-augur-type: command\n---\n\nBody.\n")

        stamp_import_metadata(skill_path, "skills-sh", "https://skills.sh/test", "0.1.0")

        fm, _ = parse_frontmatter(skill_md)
        assert fm["name"] == "test-skill"
        assert fm["x-augur-type"] == "command"
        assert fm["x-augur-source"] == "skills-sh"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/src/test_stamp_import_metadata.py -v`

Expected: FAIL — `stamp_import_metadata` doesn't exist.

- [ ] **Step 3: Implement stamp_import_metadata()**

Add to the end of `src/lib/frontmatter_utils.py`:

```python
def stamp_import_metadata(skill_path: Path, source: str, url: str, version: str) -> None:
    """Stamp import origin metadata into a skill's SKILL.md frontmatter.

    Args:
        skill_path: Path to the skill directory (containing SKILL.md).
        source: Origin type — "github", "skills-sh", or "local".
        url: Source URL (repo URL or skills.sh URL).
        version: Version tag or commit SHA at time of import.
    """
    from datetime import date

    skill_md = skill_path / "SKILL.md"
    fm, body = parse_frontmatter(skill_md)
    fm["x-augur-source"] = source
    fm["x-augur-source-url"] = url
    fm["x-augur-source-version"] = version
    fm["x-augur-imported-at"] = date.today().isoformat()
    write_frontmatter(skill_md, fm, body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/src/test_stamp_import_metadata.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/frontmatter_utils.py tests/src/test_stamp_import_metadata.py
git commit -m "feat: stamp_import_metadata() shared utility for import origin tracking"
```

---

### Task 5: Wire Import Metadata into Skillstore and Import Skills

**Files:**
- Modify: `skills/skillstore/scripts/mcp/__init__.py`
- Modify: `skills/import/scripts/mcp/__init__.py`

- [ ] **Step 1: Read the skillstore MCP file to find install functions**

Read `skills/skillstore/scripts/mcp/__init__.py` and locate the `skills_sh_add()` and `skillstore_gh_add()` functions. Identify where skill files are written to disk (the point after which SKILL.md exists in the skill dir).

- [ ] **Step 2: Add import stamp to skillstore**

At the top of `skills/skillstore/scripts/mcp/__init__.py`, add the import:

```python
from src.lib.frontmatter_utils import stamp_import_metadata
```

**Important:** The actual function names in this file are `skillstore_sh_add()` (line 266, tool name `skills-sh-add`) and `skillstore_gh_add()` (line 419, tool name `skillstore-gh-add`). NOT `skills_sh_add()`.

**Note:** These functions install to client-specific directories (e.g., `~/.claude/skills/`), not to the project `skills/` directory. The stamp should still work — it writes to whichever SKILL.md path the skill was installed to. Read the file to find where `skill_ref` resolves to a path and add the stamp call after the skill files are in place.

In `skillstore_sh_add()`, after the `_skills_action()` call, resolve the installed skill path and stamp:

```python
# After successful install, stamp import metadata
# The install path depends on the client — read the function to find it
stamp_import_metadata(installed_skill_path, "skills-sh", skill_ref, "latest")
```

In `skillstore_gh_add()`, after the skill is installed, add:

```python
stamp_import_metadata(installed_skill_path, "github", repo_url, version_or_sha)
```

Use the actual variable names from the function — read the file to get the correct path, URL, and version variables.

- [ ] **Step 3: Read the import MCP file and add stamp**

Read `skills/import/scripts/mcp/__init__.py` and locate `install_skill()`. Add the import at top:

```python
from src.lib.frontmatter_utils import stamp_import_metadata
```

After the skill is installed, add the stamp call with the appropriate source type (detect from URL — "github" if contains "github.com", "local" if local path, "skills-sh" if skills.sh).

- [ ] **Step 4: Commit**

```bash
git add skills/skillstore/scripts/mcp/__init__.py skills/import/scripts/mcp/__init__.py
git commit -m "feat: stamp import origin metadata on skill install from skillstore/import"
```

---

### Task 6: Seed Eval Generation in Auto-Skill-Quality

**Files:**
- Modify: `skills/auto-skill-quality/scripts/skill_quality_ops.py`
- Create: `tests/scripts/test_seed_evals.py`

- [ ] **Step 1: Write failing tests for seed eval generation**

Create `tests/scripts/test_seed_evals.py`:

```python
"""Tests for seed eval generation per skill type."""
import json
import tempfile
from pathlib import Path


def test_generate_seed_evals_command():
    """Command skills should get usage + help evals."""
    from skills.auto_skill_quality.scripts.skill_quality_ops import _generate_seed_evals

    with tempfile.TemporaryDirectory() as td:
        skill_path = Path(td)
        fm = {
            "name": "test-cmd",
            "x-augur-type": "command",
            "description": "Run test command for checking things",
        }
        result = _generate_seed_evals(skill_path, fm)
        assert result["skill_name"] == "test-cmd"
        assert len(result["evals"]) >= 2
        assert all(e["confidence"] == "seed" for e in result["evals"])
        assert any("--help" in e["prompt"] for e in result["evals"])


def test_generate_seed_evals_domain_with_tools():
    """Domain skills with tools should get tool-exercise evals."""
    from skills.auto_skill_quality.scripts.skill_quality_ops import _generate_seed_evals

    with tempfile.TemporaryDirectory() as td:
        skill_path = Path(td)
        fm = {
            "name": "test-domain",
            "x-augur-type": "domain",
            "description": "Manage test items",
            "x-augur-mcp-tools": ["add-test-item", "list-test-items", "delete-test-item"],
        }
        result = _generate_seed_evals(skill_path, fm)
        assert len(result["evals"]) >= 2
        assert any("add-test-item" in str(e) for e in result["evals"])


def test_generate_seed_evals_autoloop():
    """Autoloop skills should get a d0 scan eval."""
    from skills.auto_skill_quality.scripts.skill_quality_ops import _generate_seed_evals

    with tempfile.TemporaryDirectory() as td:
        skill_path = Path(td)
        fm = {
            "name": "auto-test-loop",
            "x-augur-type": "autoloop",
            "description": "Test loop for checking things",
        }
        result = _generate_seed_evals(skill_path, fm)
        assert len(result["evals"]) >= 1
        assert any("scan" in e["prompt"].lower() or "d0" in e["prompt"].lower() or "difficulty 0" in e["prompt"].lower() for e in result["evals"])


def test_generate_seed_evals_unknown_type_gets_generic():
    """Unknown types should get a generic eval based on description."""
    from skills.auto_skill_quality.scripts.skill_quality_ops import _generate_seed_evals

    with tempfile.TemporaryDirectory() as td:
        skill_path = Path(td)
        fm = {
            "name": "test-meta",
            "x-augur-type": "meta",
            "description": "Cross-reference skill for linking things",
        }
        result = _generate_seed_evals(skill_path, fm)
        assert len(result["evals"]) >= 1
        assert all(e["confidence"] == "seed" for e in result["evals"])


def test_generate_seed_evals_no_description_returns_empty():
    """Skills with no description should return empty evals."""
    from skills.auto_skill_quality.scripts.skill_quality_ops import _generate_seed_evals

    with tempfile.TemporaryDirectory() as td:
        skill_path = Path(td)
        fm = {"name": "empty-skill", "x-augur-type": "domain"}
        result = _generate_seed_evals(skill_path, fm)
        assert result["evals"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/scripts/test_seed_evals.py -v`

Expected: FAIL — `_generate_seed_evals` doesn't exist.

- [ ] **Step 3: Implement _generate_seed_evals() and _tool_to_action()**

Add to `skill_quality_ops.py` after the existing `_scaffold_action()` function (around line 586):

```python
def _tool_to_action(tool_name: str) -> str:
    """Convert a hyphenated MCP tool name to a natural-language action phrase."""
    parts = tool_name.split("-")
    if len(parts) >= 2:
        verb = parts[0]
        noun = " ".join(parts[1:])
        return f"{verb} a {noun}"
    return f"use the {tool_name} feature"


def _generate_seed_evals(skill_path: Path, fm: dict) -> dict:
    """Generate seed evals.json from skill metadata, following skill-creator schema."""
    skill_type = fm.get("x-augur-type", "domain")
    name = fm.get("name", skill_path.name)
    description = fm.get("description", "")
    tools = fm.get("x-augur-mcp-tools", [])

    if not description:
        return {"skill_name": name, "evals": []}

    evals: list[dict] = []

    if skill_type == "command":
        evals.append({
            "id": 1,
            "prompt": f"Run /{name} with default arguments",
            "expected_output": f"The /{name} command executes and returns a useful result",
            "files": [],
            "expectations": [
                f"The skill /{name} is triggered",
                "Output is non-empty and relevant to the command's purpose",
                "No errors or stack traces in output",
            ],
            "confidence": "seed",
        })
        evals.append({
            "id": 2,
            "prompt": f"Run /{name} --help",
            "expected_output": "Usage information with flags and examples",
            "files": [],
            "expectations": [
                "Output contains usage or syntax information",
                "Available flags or options are listed",
            ],
            "confidence": "seed",
        })

    elif skill_type == "domain" and tools:
        for i, tool in enumerate(tools[:3]):
            evals.append({
                "id": i + 1,
                "prompt": f"Use the {name} skill to {_tool_to_action(tool)}",
                "expected_output": f"The {tool} MCP tool executes successfully",
                "files": [],
                "expectations": [
                    f"The {tool} tool is called",
                    "Tool returns structured data without errors",
                ],
                "confidence": "seed",
            })

    elif skill_type == "autoloop":
        evals.append({
            "id": 1,
            "prompt": f"Run /{name} at difficulty 0 (scan only)",
            "expected_output": "Scan report with issues list",
            "files": [],
            "expectations": [
                "Returns a scan result with issues array",
                "No unhandled exceptions",
                "Follows ops_protocol format",
            ],
            "confidence": "seed",
        })

    elif skill_type == "library-reference":
        evals.append({
            "id": 1,
            "prompt": f"I'm working with code that uses patterns from {name}. What gotchas should I know about?",
            "expected_output": "References the skill's gotchas documentation",
            "files": [],
            "expectations": [
                f"The {name} skill is triggered",
                "Response references specific gotchas or patterns",
            ],
            "confidence": "seed",
        })

    elif skill_type == "runbook":
        evals.append({
            "id": 1,
            "prompt": f"Something related to {name.replace('-', ' ')} is broken. Help me troubleshoot.",
            "expected_output": "Step-by-step troubleshooting procedure",
            "files": [],
            "expectations": [
                f"The {name} skill is triggered",
                "Response contains numbered or ordered steps",
            ],
            "confidence": "seed",
        })

    elif skill_type == "template":
        evals.append({
            "id": 1,
            "prompt": f"Create a new project using the {name.replace('-', ' ')} template",
            "expected_output": "Files scaffolded from template",
            "files": [],
            "expectations": [
                f"The {name} skill is triggered",
                "Output files are created based on the template",
            ],
            "confidence": "seed",
        })

    else:
        # Generic fallback for meta, integration, and unknown types
        evals.append({
            "id": 1,
            "prompt": f"Use the {name} skill: {description[:100]}",
            "expected_output": "The skill executes and produces relevant output",
            "files": [],
            "expectations": [
                f"The {name} skill is triggered",
                "Output is non-empty and relevant",
                "No errors or stack traces",
            ],
            "confidence": "seed",
        })

    return {"skill_name": name, "evals": evals}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/scripts/test_seed_evals.py -v`

Expected: All 5 tests PASS.

- [ ] **Step 5: Wire seed generation into fix() at d2+**

In the `fix()` function in `skill_quality_ops.py` (line 726), inside the `for sname, skill_issues in by_skill.items():` loop, add seed eval generation after the existing product fix block:

```python
# After product fixes, generate seed evals if missing (d2+)
if ctx.difficulty >= 2:
    evals_dir = skill_dir / "evals"
    if not (evals_dir / "evals.json").exists():
        fm_current = ctx_info.get("fm", {})
        seed = _generate_seed_evals(skill_dir, fm_current)
        if seed["evals"]:
            evals_dir.mkdir(exist_ok=True)
            (evals_dir / "evals.json").write_text(json.dumps(seed, indent=2))
            all_changes.append(f"{sname}: generated {len(seed['evals'])} seed evals")
```

Add `import json` at the top of the file if not already present.

- [ ] **Step 6: Commit**

```bash
git add skills/auto-skill-quality/scripts/skill_quality_ops.py tests/scripts/test_seed_evals.py
git commit -m "feat: seed eval generation per skill type at d2+ difficulty"
```

---

### Task 7: rank.json Writer in scan()

**Files:**
- Modify: `skills/auto-skill-quality/scripts/skill_quality_ops.py`

- [ ] **Step 1: Add rank.json writing to scan()**

In the `scan()` function, after the `scored = score_all()` call succeeds (around line 63), add rank.json writing for each skill:

```python
import json
from datetime import datetime

# Write rank.json sidecar for each scored skill
skills_dir = get_project_root() / "skills"
for skill_result in scored["skills"]:
    skill_evals_dir = skills_dir / skill_result["name"] / "evals"
    skill_evals_dir.mkdir(exist_ok=True)
    rank_data = {
        "tier": skill_result["tier"],
        "score": skill_result["score"],
        "rubric": skill_result.get("rubric", "domain-low"),
        "structural": {
            "score": skill_result["score"],
            "dimensions": skill_result["dimensions"],
        },
        "behavioral": skill_result.get("behavioral"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    (skill_evals_dir / "rank.json").write_text(json.dumps(rank_data, indent=2))
```

Note: `rank.json` is a computed snapshot for dashboard consumption. `_read_behavioral()` reads from `benchmark.json` (actual eval results), not `rank.json`, to avoid circular bootstrap. The `behavioral` field in `rank.json` is informational — it records what the scorer found, but the scorer always reads from `benchmark.json` as the source of truth.

- [ ] **Step 2: Verify scan still works**

Run: `cd ~/Projects/Augur && python3 -c "
from src.lib.ops_protocol import OpsContext
from skills.auto_skill_quality.scripts.skill_quality_ops import scan
ctx = OpsContext(difficulty=0, project_root=__import__('src.config.paths', fromlist=['get_project_root']).get_project_root(), config={})
result = scan(ctx)
print(result.summary)
"`

Expected: Summary line like "X/186 skills below tier A, targeting Y this cycle". Also verify that `skills/career/evals/rank.json` was created.

- [ ] **Step 3: Commit**

```bash
git add skills/auto-skill-quality/scripts/skill_quality_ops.py
git commit -m "feat: scan() writes rank.json sidecar per skill"
```

---

### Task 8: Post-Execution Feedback Hook

**Files:**
- Create: `skills/auto-skill-quality/scripts/feedback_hook.py`
- Create: `tests/scripts/test_feedback_hook.py`

- [ ] **Step 1: Write failing tests**

Create `tests/scripts/test_feedback_hook.py`:

```python
"""Tests for the post-execution feedback hook."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


def test_should_prompt_no_evals():
    """Should always prompt when no evals exist."""
    from skills.auto_skill_quality.scripts.feedback_hook import should_prompt_feedback

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        assert should_prompt_feedback("test-skill", evals_dir) is True


def test_should_prompt_recent_feedback_skips():
    """Should not prompt if feedback was given in last 7 days."""
    from skills.auto_skill_quality.scripts.feedback_hook import should_prompt_feedback
    from datetime import datetime, timedelta, timezone

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        (evals_dir / "evals.json").write_text('{"skill_name": "x", "evals": []}')
        feedback = {
            "skill_name": "test-skill",
            "entries": [{
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "result": "positive",
                "note": "",
                "prompt_summary": "test",
            }],
        }
        (evals_dir / "feedback.json").write_text(json.dumps(feedback))
        assert should_prompt_feedback("test-skill", evals_dir) is False


def test_append_feedback_creates_file():
    """append_feedback should create feedback.json if missing."""
    from skills.auto_skill_quality.scripts.feedback_hook import append_feedback

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        append_feedback(evals_dir, "test-skill", "positive", "", "test prompt")

        feedback = json.loads((evals_dir / "feedback.json").read_text())
        assert feedback["skill_name"] == "test-skill"
        assert len(feedback["entries"]) == 1
        assert feedback["entries"][0]["result"] == "positive"


def test_append_feedback_caps_at_50():
    """feedback.json should keep only the last 50 entries."""
    from skills.auto_skill_quality.scripts.feedback_hook import append_feedback

    with tempfile.TemporaryDirectory() as td:
        evals_dir = Path(td) / "evals"
        evals_dir.mkdir()
        existing = {
            "skill_name": "test-skill",
            "entries": [{"timestamp": f"2026-01-{i:02d}", "result": "positive", "note": "", "prompt_summary": f"prompt {i}"} for i in range(50)],
        }
        (evals_dir / "feedback.json").write_text(json.dumps(existing))

        append_feedback(evals_dir, "test-skill", "negative", "broke", "prompt 51")

        feedback = json.loads((evals_dir / "feedback.json").read_text())
        assert len(feedback["entries"]) == 50
        assert feedback["entries"][-1]["prompt_summary"] == "prompt 51"
        assert feedback["entries"][0]["prompt_summary"] == "prompt 2"  # oldest dropped
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/scripts/test_feedback_hook.py -v`

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement feedback_hook.py**

Create `skills/auto-skill-quality/scripts/feedback_hook.py`:

```python
"""Post-execution feedback hook for skill quality.

Called as a PostToolUse hook after skill execution. Collects lightweight
thumbs up/down feedback and suggests full eval runs.

Usage:
    python3 -m skills.auto_skill_quality.scripts.feedback_hook --skill SKILL_NAME
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config.paths import get_project_root

MAX_ENTRIES = 50
FEEDBACK_COOLDOWN_DAYS = 7


def should_prompt_feedback(skill_name: str, evals_dir: Path) -> bool:
    """Decide whether to prompt user for feedback.

    Prompts when:
    - Skill has no evals (always prompt)
    - No feedback in last 7 days
    - 20% random sampling otherwise
    """
    # Always prompt if no evals exist
    if not (evals_dir / "evals.json").exists():
        return True

    # Check feedback recency
    feedback_file = evals_dir / "feedback.json"
    if feedback_file.exists():
        try:
            data = json.loads(feedback_file.read_text())
            entries = data.get("entries", [])
            if entries:
                last_ts = entries[-1].get("timestamp", "")
                if last_ts:
                    last_dt = datetime.fromisoformat(last_ts.rstrip("Z"))
                    if datetime.now(timezone.utc) - last_dt < timedelta(days=FEEDBACK_COOLDOWN_DAYS):
                        return False
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    # Random sampling: 20% of executions
    return random.random() < 0.20


def append_feedback(
    evals_dir: Path,
    skill_name: str,
    result: str,
    note: str,
    prompt_summary: str,
) -> None:
    """Append a feedback entry to evals/feedback.json, capping at MAX_ENTRIES."""
    feedback_file = evals_dir / "feedback.json"

    if feedback_file.exists():
        try:
            data = json.loads(feedback_file.read_text())
        except json.JSONDecodeError:
            data = {"skill_name": skill_name, "entries": []}
    else:
        data = {"skill_name": skill_name, "entries": []}

    data["entries"].append({
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "result": result,
        "note": note,
        "prompt_summary": prompt_summary,
    })

    # Cap at MAX_ENTRIES
    if len(data["entries"]) > MAX_ENTRIES:
        data["entries"] = data["entries"][-MAX_ENTRIES:]

    evals_dir.mkdir(exist_ok=True)
    feedback_file.write_text(json.dumps(data, indent=2))


def main():
    """CLI entrypoint for PostToolUse hook."""
    import argparse

    parser = argparse.ArgumentParser(description="Skill feedback hook")
    parser.add_argument("--skill", required=True, help="Skill name")
    args = parser.parse_args()

    skill_name = args.skill
    root = get_project_root()
    evals_dir = root / "skills" / skill_name / "evals"

    if not should_prompt_feedback(skill_name, evals_dir):
        return

    # Output prompt to stdout — the hook runner displays this to the user
    print(f"\nDid {skill_name} do what you expected? (y/n)", flush=True)
    # Note: actual user input handling depends on the hook runner implementation.
    # This script outputs the prompt; the hook runner collects the response.
    # For now, just log that feedback was requested.
    print(f"Run /skill-creator eval {skill_name} to benchmark this skill and improve its rank.", flush=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/scripts/test_feedback_hook.py -v`

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/auto-skill-quality/scripts/feedback_hook.py tests/scripts/test_feedback_hook.py
git commit -m "feat: post-execution feedback hook with 50-entry cap"
```

---

### Task 9: Integration Test — Full Scoring Pipeline

**Files:**
- Modify: `tests/mcp/test_skill_scorer.py`

- [ ] **Step 1: Add integration test for the full pipeline**

Append to `tests/mcp/test_skill_scorer.py`:

```python
def test_score_all_skills_returns_rubric_field():
    """score_all_skills should include rubric name in each skill result."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import score_all_skills

    result = score_all_skills(skill_name="career")
    assert len(result["skills"]) == 1
    skill = result["skills"][0]
    assert "rubric" in skill
    assert skill["rubric"] in ("domain-high", "domain-low")


def test_score_all_skills_command_has_zero_ui_weight():
    """Command skills should have 0% UI weight in results."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import score_all_skills

    result = score_all_skills(skill_name="ask")
    if result["skills"]:
        skill = result["skills"][0]
        assert skill["dimensions"]["ui"]["weight"] == 0.0


def test_score_all_skills_includes_behavioral():
    """Results should include behavioral field (None if no evals)."""
    from src.mcp.augur_mcp.infrastructure.skill_scorer import score_all_skills

    result = score_all_skills(skill_name="career")
    if result["skills"]:
        skill = result["skills"][0]
        assert "behavioral" in skill
```

- [ ] **Step 2: Run integration tests**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/mcp/test_skill_scorer.py -v`

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/mcp/test_skill_scorer.py
git commit -m "test: integration tests for full type-aware scoring pipeline"
```

---

### Task 10: Final Validation and Tier Distribution Report

**Files:** None created — validation only.

- [ ] **Step 1: Run full test suite**

Run: `cd ~/Projects/Augur && python3 -m pytest tests/mcp/test_skill_scorer.py tests/src/test_stamp_import_metadata.py tests/scripts/test_seed_evals.py tests/scripts/test_feedback_hook.py -v`

Expected: All tests PASS.

- [ ] **Step 2: Generate tier distribution report**

Run: `cd ~/Projects/Augur && python3 -c "
from src.mcp.augur_mcp.infrastructure.skill_scorer import score_all_skills
r = score_all_skills()
print(f'Total skills: {r[\"summary\"][\"total\"]}')
print(f'Average score: {r[\"summary\"][\"average_score\"]}')
print(f'Tier distribution: {r[\"summary\"][\"tier_distribution\"]}')
print()
from collections import Counter
rubrics = Counter(s.get('rubric', 'unknown') for s in r['skills'])
print('Rubric distribution:')
for k, v in sorted(rubrics.items()):
    print(f'  {k}: {v}')
print()
behavioral_count = sum(1 for s in r['skills'] if s.get('behavioral'))
print(f'Skills with behavioral data: {behavioral_count}')
"`

Expected: Report showing tier/rubric distribution. Verify domain-high/domain-low split is reasonable.

- [ ] **Step 3: Spot-check a few skills**

Run: `cd ~/Projects/Augur && python3 -c "
from src.mcp.augur_mcp.infrastructure.skill_scorer import score_all_skills
for name in ['career', 'ask', 'auto-lint', 'nextjs-patterns']:
    r = score_all_skills(skill_name=name)
    if r['skills']:
        s = r['skills'][0]
        print(f'{s[\"name\"]}: tier={s[\"tier\"]} score={s[\"score\"]} rubric={s[\"rubric\"]} ui_weight={s[\"dimensions\"][\"ui\"][\"weight\"]}')
"`

Expected:
- `career`: rubric=domain-high, ui_weight=0.20
- `ask`: rubric=command, ui_weight=0.0
- `auto-lint`: rubric=autoloop, ui_weight=0.05
- `nextjs-patterns`: rubric=library-reference, ui_weight=0.0

- [ ] **Step 4: Commit validation results as a note**

No commit needed — this is a validation step only.
