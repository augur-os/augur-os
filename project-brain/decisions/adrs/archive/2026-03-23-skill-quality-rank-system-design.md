# Skill Quality & Rank System Design

**Date:** 2026-03-23
**Status:** Draft
**Scope:** Type-aware scoring, behavioral tier gates, seed evals, feedback hooks, imported skill metadata

## Problem

The current skill quality system has three gaps:

1. **One-size-fits-all scoring** — All 186 skills are scored with the same dimension weights (instruction 30%, product 40%, UI 15%, wiring 15%). A command skill like `/ask` gets penalized for zero UI score when it doesn't need UI. An autoloop gets penalized for low instruction score when its value is in wiring/ops compliance.

2. **No behavioral validation** — Quality is measured by structural completeness (does it have files, tools, pages?) but never by whether the skill actually works when triggered. A structurally perfect skill that crashes on every invocation still scores tier A.

3. **No origin tracking** — Skills imported from GitHub or skills.sh are indistinguishable from native skills. No URL, version, or import date is recorded in the skill itself.

## Prerequisites

### Fix scorer path (CRITICAL)

The current `score_all_skills()` in `skill_scorer.py` iterates `root / ".claude" / "skills"` — a legacy path forbidden by ADR-479. This must be fixed to `root / "skills"` before any eval-related changes, otherwise the scorer will never find `evals/` directories.

### Add `evals/` to allowed skill root directories (CRITICAL)

CLAUDE.md rule 19 lists standard skill root dirs (`commands/`, `references/`, `scripts/`, `assets/`, `examples/`, `modules/`). The `evals/` directory must be added to this list. It is a standard directory in the Agent Skills specification — eval test cases are portable across clients, not Augur-specific. Update CLAUDE.md rule 19 and any pre-commit hook allowlists.

## Design

### 1. Type-Aware Scoring Rubrics

Each `x-augur-type` gets its own dimension weights and scoring signals. The 8 existing types remain unchanged. `domain` is split into high-scope and low-scope based on frontmatter declarations (tool count, page count) — not a new type, just a rubric selector.

**Type population note:** The three dominant types in the codebase today are `autoloop` (75 skills), `command` (52), and `domain` (46). The remaining types (`template`, `library-reference`, `runbook`, `meta`, `integration`) have 1-4 skills each. Rubrics for sparse types are future-proofing — they work today but won't be heavily exercised until more skills of those types exist.

**Rubric table:**

| Type | Instruction | Product | UI | Wiring | Key scoring signals |
|------|------------|---------|-----|--------|---------------------|
| `domain` (high-scope) | 25% | 35% | 20% | 20% | Pages, tools, actions, data completeness |
| `domain` (low-scope) | 35% | 40% | 5% | 20% | Tools, scripts, references |
| `command` | 50% | 25% | 0% | 25% | Usage docs, flags, examples, --help |
| `autoloop` | 20% | 30% | 5% | 45% | ops_protocol, difficulty levels, evolution |
| `library-reference` | 60% | 20% | 0% | 20% | Gotchas depth, doc quality |
| `runbook` | 55% | 25% | 0% | 20% | Steps, prerequisites, troubleshooting |
| `template` | 40% | 35% | 10% | 15% | Example output, customization points |
| `meta` | 50% | 30% | 0% | 20% | Cross-references, scope description |
| `integration` | 35% | 35% | 10% | 20% | Connection docs, auth patterns |

**Domain scope detection** — automatic from frontmatter. Threshold: `tools >= 8 or pages >= 3` classifies as high-scope. Based on current distribution: ~15 domain skills are high-scope (career, apple, wealth, etc.), ~31 are low-scope. This should be validated during implementation by running the rubric selector against all domain skills and reviewing the split.

```python
def _resolve_rubric(fm: dict) -> dict:
    skill_type = fm.get("x-augur-type", "domain")
    if skill_type == "domain":
        tools = len(fm.get("x-augur-mcp-tools", []))
        pages = len(fm.get("x-augur-dashboard-pages", []))
        scope = "domain-high" if (tools >= 8 or pages >= 3) else "domain-low"
        return RUBRICS[scope]
    return RUBRICS.get(skill_type, RUBRICS["domain-low"])
```

The existing `score_skill()` function changes from using `DEFAULT_WEIGHTS` to calling `_resolve_rubric(fm)`. All dimension scoring functions (`_score_instruction`, `_score_product`, `_score_ui`, `_score_wiring`) remain the same — only the weights that combine them change.

### 2. Tier Gate System

Tier computation changes from a single threshold lookup to two phases: structural score determines the base tier (caps at B), behavioral eval results gate promotion above B.

**Expanded tier scale (5 → 7 levels):**

| Tier | Structural Requirement | Behavioral Requirement |
|------|----------------------|----------------------|
| S | >= 75 | verified evals, pass_rate >= 80% |
| A | >= 65 | seed evals, pass_rate >= 60% |
| B+ | >= 55 | evals exist, pass_rate < 60% |
| B | >= 55 | none (structural ceiling without evals) |
| C | >= 35 | none |
| D | >= 15 | none |
| F | < 15 | none |

**Implementation:**

```python
def _compute_tier(structural_score: float, evals_dir: Path) -> dict:
    # Phase 1: structural base tier (caps at B)
    if structural_score >= 55:
        base_tier = "B"
    elif structural_score >= 35:
        base_tier = "C"
    elif structural_score >= 15:
        base_tier = "D"
    else:
        base_tier = "F"

    # Phase 2: behavioral gate (promotes above B)
    behavioral = _read_behavioral(evals_dir)
    if behavioral is None:
        return {"tier": base_tier, "behavioral": None}

    if base_tier != "B":
        return {"tier": base_tier, "behavioral": behavioral}

    # Structural floor for top tiers
    if behavioral["confidence"] == "verified" and behavioral["pass_rate"] >= 0.80 and structural_score >= 75:
        return {"tier": "S", "behavioral": behavioral}
    elif behavioral["pass_rate"] >= 0.60 and structural_score >= 65:
        return {"tier": "A", "behavioral": behavioral}
    elif behavioral["eval_count"] > 0:
        return {"tier": "B+", "behavioral": behavioral}
    else:
        return {"tier": "B", "behavioral": behavioral}


def _read_behavioral(evals_dir: Path) -> dict | None:
    """Read behavioral eval results from evals/rank.json.

    Returns None if no eval data exists. The confidence field
    is aggregated conservatively: 'verified' only if ALL evals
    in evals.json are marked confidence: verified, otherwise 'seed'.
    """
    rank_file = evals_dir / "rank.json"
    if not rank_file.exists():
        return None
    try:
        data = json.loads(rank_file.read_text())
        return {
            "confidence": data.get("confidence", "seed"),
            "pass_rate": data.get("pass_rate", 0.0),
            "eval_count": data.get("eval_count", 0),
            "last_run": data.get("last_run"),
        }
    except (json.JSONDecodeError, KeyError):
        return None
```

**Confidence aggregation rule:** Aggregate confidence is `verified` only if ALL evals in `evals.json` have `confidence: verified`. If any eval is `seed`, the aggregate is `seed`. This prevents gaming by adding one verified eval to a set of seeds.

### 3. Eval Location & Schema

Evals live at the skill root in `evals/`, following the skill-creator convention. They are portable across Claude Code, Codex, Gemini — any client that understands the schema can run them.

**Directory structure:**

```
skills/{skill}/
├── SKILL.md
├── evals/
│   ├── evals.json       # test cases (skill-creator schema)
│   ├── benchmark.json   # full eval run results
│   ├── feedback.json    # lightweight user feedback
│   └── rank.json        # computed rank snapshot
├── scripts/
├── references/
└── augur/
```

**evals.json** — skill-creator compatible:

```json
{
  "skill_name": "career",
  "evals": [
    {
      "id": 1,
      "prompt": "Add a job application for Google SRE role",
      "expected_output": "Job entry created with company, role, and status",
      "files": [],
      "expectations": [
        "The add-career-job tool is called",
        "Tool returns structured data without errors"
      ],
      "confidence": "seed"
    }
  ]
}
```

The `confidence` field (`seed` or `verified`) is an Augur extension to the skill-creator schema. It determines the tier ceiling: seed evals cap at A, verified evals unlock S.

**rank.json** — computed rank snapshot:

```json
{
  "tier": "A",
  "score": 78.5,
  "structural": {
    "score": 82,
    "rubric": "domain-high",
    "dimensions": {
      "instruction": {"score": 75, "weight": 0.25, "weighted": 18.75},
      "product": {"score": 90, "weight": 0.35, "weighted": 31.5},
      "ui": {"score": 70, "weight": 0.20, "weighted": 14.0},
      "wiring": {"score": 85, "weight": 0.20, "weighted": 17.0}
    }
  },
  "behavioral": {
    "confidence": "seed",
    "pass_rate": 0.72,
    "eval_count": 3,
    "last_run": "2026-03-23T02:00:00Z"
  },
  "computed_at": "2026-03-23T02:00:00Z"
}
```

### 4. Seed Eval Generation

Auto-skill-quality at d2+ generates seed evals for skills that reach structural tier B and have no `evals/evals.json`.

**Generation strategy per type:**

| Type | Seed eval strategy |
|------|-------------------|
| `command` | 2-3 prompts invoking the command with different args + --help. Assert: triggers, non-empty output, no errors |
| `domain` (high) | Prompts exercising top 3 MCP tools by name. Assert: tool executes, returns structured data |
| `domain` (low) | 1-2 prompts for primary workflow. Assert: triggers, expected output type |
| `autoloop` | d0 scan prompt. Assert: returns issues list, no crashes, ops_protocol format |
| `library-reference` | "How do I X" prompts from gotchas section. Assert: triggers, references correct docs |
| `runbook` | "X is broken" prompt from prerequisites. Assert: triggers, step-by-step output |
| `template` | "Create X from template" prompt. Assert: triggers, scaffolds expected files |

**Integration with fix cycle:**

```python
def fix(ctx, issues):
    for issue in issues:
        skill_path = Path(issue["path"])
        evals_dir = skill_path / "evals"

        if ctx.difficulty >= 2 and not (evals_dir / "evals.json").exists():
            fm = parse_frontmatter(skill_path / "SKILL.md")
            seed = _generate_seed_evals(skill_path, fm)
            if seed["evals"]:
                evals_dir.mkdir(exist_ok=True)
                (evals_dir / "evals.json").write_text(json.dumps(seed, indent=2))
                _git_commit(f"seed evals for {fm['name']}")
```

All generated evals are tagged `confidence: seed`. To reach tier S, a human must write new evals or review and mark existing ones as `confidence: verified` via `/skill-creator`.

**Sparse types (`meta`, `integration`):** Seed generation falls back to a generic strategy — 1-2 prompts derived from the skill description. Assert: skill triggers, output is non-empty, no errors. These won't be high-quality evals, but they provide basic "doesn't crash" coverage.

**rank.json writer:** The `skill_quality_ops.py` `scan()` function writes `rank.json` for each scored skill as part of its nightly loop. The scan already iterates all skills and computes scores — writing the sidecar is a natural side effect. `score_all_skills()` in `skill_scorer.py` remains read-only (returns JSON over MCP, no disk writes).

```python
# In skill_quality_ops.py scan()
for skill_result in score_results["skills"]:
    skill_dir = skills_dir / skill_result["name"]
    evals_dir = skill_dir / "evals"
    evals_dir.mkdir(exist_ok=True)
    rank_data = {
        "tier": skill_result["tier"],
        "score": skill_result["score"],
        "structural": skill_result["dimensions"],
        "behavioral": _read_behavioral(evals_dir),
        "computed_at": datetime.utcnow().isoformat() + "Z",
    }
    (evals_dir / "rank.json").write_text(json.dumps(rank_data, indent=2))
```

### 5. Post-Execution Feedback Hook

A PostToolUse hook that fires after skill execution, collects lightweight thumbs up/down feedback, and suggests full eval runs.

**Trigger conditions** — not every execution:

- Skill has no evals → always prompt
- Evals exist but no feedback in 7 days → prompt
- Otherwise → 20% random sampling

**Flow:**

```
1. Skill finishes executing
2. should_prompt_feedback() → True
3. "Did {skill_name} do what you expected? (y/n)"
4. User responds
5. Append to evals/feedback.json
6. "Run /skill-creator eval {skill_name} to benchmark and improve rank"
```

**feedback.json:**

```json
{
  "skill_name": "career",
  "entries": [
    {
      "timestamp": "2026-03-23T14:30:00Z",
      "result": "positive",
      "note": "",
      "prompt_summary": "Add a job application for Google SRE role"
    },
    {
      "timestamp": "2026-03-20T09:15:00Z",
      "result": "negative",
      "note": "Didn't parse the salary range correctly",
      "prompt_summary": "Import job listing from LinkedIn URL"
    }
  ]
}
```

**Feedback retention:** feedback.json keeps only the last 50 entries per skill. On append, if entries exceed 50, the oldest are dropped. This bounds git repo growth — at ~200 bytes per entry, 50 entries is ~10KB per skill.

**Feedback → Eval improvement loop:** At d3+, auto-skill-quality reads `feedback.json` to identify failure patterns and generates better-targeted seed evals. Negative note "didn't parse salary range" becomes a test case for salary parsing.

**Hook registration:** The feedback hook runs as a direct CLI script (not an MCP tool) because PostToolUse hooks need sub-second latency for the prompt to feel natural in the conversation flow. MCP round-trip adds overhead that would break the UX. The hook only writes to the local `evals/feedback.json` — no metrics or interceptors needed.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "mcp__augur__skill-action|mcp__augur__cross-skill",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -m skills.auto_skill_quality.scripts.feedback_hook --skill $SKILL_NAME"
          }
        ]
      }
    ]
  }
}
```

### 6. Imported Skill Metadata

Skills installed via `/skillstore` or `/import` get origin metadata stamped into SKILL.md frontmatter.

**New frontmatter fields:**

```yaml
x-augur-source: github              # enum: github, skills-sh, local
x-augur-source-url: https://github.com/user/repo-name
x-augur-source-version: 1.2.0       # version tag or commit SHA
x-augur-imported-at: 2026-03-15     # date of import
```

Absence of `x-augur-source` means native (no stamp needed).

**Write location:** `stamp_import_metadata()` lives in `src/lib/frontmatter_utils.py` (shared utility, already imported by both skills). Both `skillstore` and `import` MCP scripts import and call it — no duplication.

```python
# In src/lib/frontmatter_utils.py
def stamp_import_metadata(skill_path: Path, source: str, url: str, version: str):
    fm, body = parse_frontmatter(skill_path / "SKILL.md")
    fm["x-augur-source"] = source
    fm["x-augur-source-url"] = url
    fm["x-augur-source-version"] = version
    fm["x-augur-imported-at"] = date.today().isoformat()
    write_frontmatter(skill_path / "SKILL.md", fm, body)
```

Called from `skills_sh_add()`, `skillstore_gh_add()`, and `install_skill()` after skill files are in place.

**Scoring impact:** None. Imported skills graded identically to native. Metadata is informational — enables dashboard views ("12 native, 5 GitHub, 3 skills.sh") and future upgrade detection.

## File Change Map

| File | Change | Lines delta |
|------|--------|-------------|
| `src/mcp/augur_mcp/infrastructure/skill_scorer.py` | Fix `skills_dir` path from `.claude/skills` to `skills/` (prerequisite). Add `RUBRICS`, `_resolve_rubric()`, `_compute_tier()`, `_read_behavioral()`. Modify `score_skill()` for type-aware weights and two-phase tier | +180 |
| `skills/auto-skill-quality/scripts/skill_quality_ops.py` | Add `_generate_seed_evals()`, `_tool_to_action()`. Modify `scan()` to write `rank.json` per skill. Modify `fix()` for seed gen at d2+, feedback-informed evals at d3+ | +140 |
| `skills/auto-skill-quality/scripts/feedback_hook.py` | **New.** PostToolUse CLI — trigger check, feedback prompt, writes feedback.json (50-entry cap), suggests full eval | +80 |
| `src/lib/frontmatter_utils.py` | Add `stamp_import_metadata()` — shared utility for import origin stamping | +15 |
| `skills/skillstore/scripts/mcp/__init__.py` | Import and call `stamp_import_metadata()` in `skills_sh_add()` and `skillstore_gh_add()` | +10 |
| `skills/import/scripts/mcp/__init__.py` | Import and call `stamp_import_metadata()` in `install_skill()` | +10 |
| `CLAUDE.md` | Add `evals/` to allowed skill root directories in rule 19 | +1 |
| `skills/*/evals/evals.json` | **New per skill.** Generated by seed eval creation or manually via /skill-creator | per skill |
| `skills/*/evals/rank.json` | **New per skill.** Written by nightly scoring loop via `scan()` | per skill |
| `skills/*/evals/feedback.json` | **New per skill.** Written by feedback hook on user response | per skill |

## Migration

No migration needed. All changes are additive:

- Skills without `evals/` dir continue working — cap at tier B
- Skills without `x-augur-type` fall back to `domain-low` rubric
- Skills without `x-augur-source` are native (default)
- The scorer falls back to current behavior when type-aware data is missing
- **Prerequisite:** `skill_scorer.py` path fix from `.claude/skills` to `skills/` must land first

## Dependencies

- `src.lib.frontmatter_utils` — `parse_frontmatter()`, `write_frontmatter()`, `stamp_import_metadata()` (new)
- `src.lib.ops_protocol` — `OpsContext`, `ScanResult`, `FixResult`, `make_issue()`, `evolution_gap()`
- `src.config.paths` — `get_project_root()`
- skill-creator eval schema — `evals.json`, `benchmark.json` formats used as-is
