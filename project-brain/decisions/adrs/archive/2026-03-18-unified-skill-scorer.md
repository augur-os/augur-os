# Unified Skill Scorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace three divergent skill ranking systems with a single computed MCP tool that scores all 134 skills across 4 dimensions, surfaces results in browse badges and a dedicated deep-dive page with configurable weights.

**Architecture:** Python MCP tool (`skill-score`) computes scores by walking `.claude/skills/*/SKILL.md`, checking file presence, and cross-referencing wiring. Results flow via API route to: (1) browse page as `qualityTier`/`qualityScore` badges, and (2) a refactored `/professional/demo` page with score breakdown and weight sliders.

**Tech Stack:** Python (MCP tool), TypeScript/React (Next.js dashboard), YAML (vault weight config), shadcn/ui components.

**Spec:** `docs/superpowers/specs/2026-03-18-unified-skill-scorer-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/mcp/augur_mcp/infrastructure/skill_scorer.py` | Create | Scorer logic + MCP tool registration |
| `src/mcp/augur_mcp/infrastructure/__init__.py` | Modify (line 86-133) | Import + call `register_skill_score_tools` |
| `get_vault_dir()/config/skill-score-weights.yaml` | Create | Default weight config |
| `apps/dashboard/app/api/skill-score/route.ts` | Create | API route: GET scores, POST weights |
| `src/mcp/augur_mcp/infrastructure/browse.py` | Modify (lines 562-605) | Replace `grade` with `qualityTier`/`qualityScore` |
| `apps/dashboard/components/shared/BrowseCard.tsx` | Modify (lines 237-254) | Replace grade badge with quality tier badge |
| `apps/dashboard/app/(views)/browse/useBrowseState.ts` | Modify (line ~397) | Change tag key `"grade"` → `"qualityTier"` |
| `.claude/skills/venture-augur/augur/dashboard/demo/types.ts` | Rewrite | New types for scored data |
| `.claude/skills/venture-augur/augur/dashboard/demo/SkillGateVisualizer.tsx` | Rewrite | New visualization: TierDistribution, WeightConfig, SkillScoreTable, SkillDetail |
| `.claude/skills/venture-augur/augur/dashboard/demo/page.tsx` | Rewrite | Fetch from API, keep DemoCatalog/CodebaseStats, replace skill gate section |
| `.claude/skills/venture-augur/augur/dashboard/demo/data.ts` | Modify | Remove `SKILLS`, `SKILL_ENTRIES`, `buildSkillData`, `QUALITY_PRESETS`, `GATE_DEFS` exports. Keep `DEMOS`, `CATEGORY_LABELS`, `PRINCIPLE_LABELS`, `STEP_ICONS` (used by DemoCatalog.tsx) |

---

## Task 1: Python Scorer — Core Logic

**Files:**
- Create: `src/mcp/augur_mcp/infrastructure/skill_scorer.py`

- [ ] **Step 1: Create the scorer module with dimension functions**

```python
"""Unified skill scorer — computes quality scores across 4 dimensions."""

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from src.config.paths import get_project_root, get_vault_dir
from src.lib.frontmatter_utils import parse_frontmatter

# ── Cache ────────────────────────────────────────────────────────────────
_cache: dict[str, Any] = {}
_cache_ts: float = 0.0
_CACHE_TTL = 60.0  # seconds

DEFAULT_WEIGHTS = {
    "instruction": 0.30,
    "product": 0.40,
    "ui": 0.15,
    "wiring": 0.15,
}
DEFAULT_THRESHOLDS = {"A": 75, "B": 55, "C": 35, "D": 15}


def _load_weights() -> tuple[dict[str, float], dict[str, int]]:
    """Load weights from vault config, fall back to defaults."""
    config_path = get_vault_dir() / "config" / "skill-score-weights.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            weights = cfg.get("weights", DEFAULT_WEIGHTS)
            thresholds = cfg.get("tier_thresholds", DEFAULT_THRESHOLDS)
            # Validate weights sum to ~1.0
            total = sum(weights.values())
            if abs(total - 1.0) > 0.01:
                weights = DEFAULT_WEIGHTS
            return weights, thresholds
        except Exception:
            pass
    return DEFAULT_WEIGHTS.copy(), DEFAULT_THRESHOLDS.copy()


def _score_instruction(skill_path: Path, fm: dict, body: str) -> dict:
    """Score SKILL.md instruction quality (0-100)."""
    desc = fm.get("description", "") or ""
    desc_words = len(desc.split()) if desc.strip() else 0
    lines = body.strip().split("\n") if body.strip() else []
    body_lines = len(lines)
    sections = len(re.findall(r"^#{1,3}\s+", body, re.MULTILINE))

    # Description (0-25)
    if desc_words >= 20: desc_score = 25
    elif desc_words >= 10: desc_score = 15
    elif desc_words >= 5: desc_score = 8
    elif desc_words > 0: desc_score = 3
    else: desc_score = 0

    # Body depth (0-30)
    if body_lines >= 100: body_score = 30
    elif body_lines >= 50: body_score = 22
    elif body_lines >= 20: body_score = 15
    elif body_lines >= 5: body_score = 5
    else: body_score = 0

    # Sections (0-20)
    if sections >= 5: sect_score = 20
    elif sections >= 3: sect_score = 14
    elif sections >= 1: sect_score = 8
    else: sect_score = 0

    # Richness bonuses (0-25)
    has_examples = bool(re.search(r"(?i)(example|```)", body))
    has_references = bool(re.search(r"(?i)(references?/|scripts?/|assets?/)", body))
    has_workflow = bool(re.search(r"(?i)(workflow|step-by-step|procedure|process)", body))
    has_checklist = bool(re.search(r"(?i)(\[ \]|\[x\]|step \d|phase \d)", body))
    has_compat = "compatibility" in fm or "tools" in fm or "x-augur-tools" in str(fm)

    richness = 0
    if has_examples: richness += 8
    if has_references: richness += 5
    if has_workflow: richness += 5
    if has_checklist: richness += 4
    if has_compat: richness += 3

    score = min(100, desc_score + body_score + sect_score + richness)

    return {
        "score": score,
        "signals": {
            "desc_words": desc_words,
            "body_lines": body_lines,
            "sections": sections,
            "has_examples": has_examples,
            "has_references": has_references,
            "has_workflow": has_workflow,
            "has_checklist": has_checklist,
        },
    }


def _score_product(skill_dir: Path) -> dict:
    """Score product completeness (0-100). Binary signals."""
    has_data = (skill_dir / "data").is_dir()
    has_scripts = (skill_dir / "scripts").is_dir()
    has_references = (skill_dir / "references").is_dir()

    # Check for MCP tool registrations — grep for skill name in mcp tools
    has_mcp = False
    mcp_dir = get_project_root() / "src" / "mcp"
    skill_name = skill_dir.name
    if mcp_dir.exists():
        for py_file in mcp_dir.rglob("*.py"):
            try:
                content = py_file.read_text(errors="replace")
                if f'name="{skill_name}' in content or f"name='{skill_name}" in content:
                    has_mcp = True
                    break
            except Exception:
                pass

    # Check for API routes
    has_api = False
    api_dir = get_project_root() / "apps" / "dashboard" / "app" / "api"
    if api_dir.exists():
        for ts_file in api_dir.rglob("*.ts"):
            try:
                content = ts_file.read_text(errors="replace")
                if skill_name in content:
                    has_api = True
                    break
            except Exception:
                pass

    # Check for action files
    has_actions = False
    augur_dir = skill_dir / "augur"
    if augur_dir.exists():
        for f in augur_dir.rglob("*"):
            if f.suffix in (".yaml", ".yml", ".md") and "action" in f.name.lower():
                has_actions = True
                break

    score = 0
    if has_data: score += 20
    if has_mcp: score += 25
    if has_api: score += 20
    if has_actions: score += 15
    if has_scripts: score += 10
    if has_references: score += 10

    return {
        "score": min(100, score),
        "signals": {
            "has_data_dir": has_data,
            "has_mcp_tools": has_mcp,
            "has_api_routes": has_api,
            "has_actions": has_actions,
            "has_scripts": has_scripts,
            "has_references": has_references,
        },
    }


def _score_ui(fm: dict) -> dict:
    """Score UI maturity from SKILL.md frontmatter page states (0-100)."""
    config = fm.get("x-augur-config") or {}
    pages = (config.get("contributions") or {}).get("pages") or []
    page_list = [p for p in pages if isinstance(p, dict)]

    states = [p.get("state", "dev") for p in page_list]
    page_types = [p.get("page_type", "auto") for p in page_list]
    custom_count = sum(1 for pt in page_types if pt == "custom")
    mature_count = sum(1 for s in states if s == "mature")

    if not page_list:
        return {"score": 0, "signals": {"page_count": 0, "mature_pages": 0, "custom_pages": 0, "page_states": []}}

    score = 0
    # Page count (+5 per page, max 30)
    score += min(30, len(page_list) * 5)
    # Mature ratio
    if mature_count > 0: score += 40
    elif all(s != "mock" for s in states): score += 20
    # Custom pages
    if custom_count > 0: score += 15
    # Any non-mock
    if any(s != "mock" for s in states): score += 15

    return {
        "score": min(100, score),
        "signals": {
            "page_count": len(page_list),
            "mature_pages": mature_count,
            "custom_pages": custom_count,
            "page_states": states,
        },
    }


def _score_wiring(skill_dir: Path) -> dict:
    """Score wiring integrity via file-grep checks (0-100)."""
    skill_name = skill_dir.name
    root = get_project_root()
    api_dir = root / "apps" / "dashboard" / "app" / "api"
    mcp_dir = root / "src" / "mcp"

    has_api_route = False
    no_fs_bypasses = True
    has_mcp_tool = False
    no_fallback_masking = True

    # Check API routes reference this skill
    if api_dir.exists():
        for ts_file in api_dir.rglob("*.ts"):
            try:
                content = ts_file.read_text(errors="replace")
                if skill_name in content:
                    has_api_route = True
                    # Check for fs/spawn/exec bypasses
                    if re.search(r"import\s+.*\bfs\b|require\s*\(\s*['\"]fs['\"]|spawn|execSync|execFile", content):
                        no_fs_bypasses = False
                    # Check for gracefulFallback with empty/minimal data (masking failures)
                    if re.search(r"gracefulFallback\s*:\s*\{\s*data\s*:\s*\{\s*\}", content):
                        no_fallback_masking = False
            except Exception:
                pass

    # Check MCP tool registration
    if mcp_dir.exists():
        for py_file in mcp_dir.rglob("*.py"):
            try:
                content = py_file.read_text(errors="replace")
                if re.search(rf'@mcp\.tool\(\s*name\s*=\s*["\'].*{re.escape(skill_name)}', content):
                    has_mcp_tool = True
                    break
            except Exception:
                pass

    score = 0
    if has_api_route: score += 30
    if no_fs_bypasses: score += 25
    if has_mcp_tool: score += 25
    if no_fallback_masking: score += 20

    return {
        "score": min(100, score),
        "signals": {
            "has_api_route": has_api_route,
            "no_fs_bypasses": no_fs_bypasses,
            "has_mcp_tool": has_mcp_tool,
            "no_fallback_masking": no_fallback_masking,
        },
    }


def _get_tier(score: float, thresholds: dict[str, int]) -> str:
    """Map composite score to tier letter."""
    if score >= thresholds.get("A", 75): return "A"
    if score >= thresholds.get("B", 55): return "B"
    if score >= thresholds.get("C", 35): return "C"
    if score >= thresholds.get("D", 15): return "D"
    return "F"


def score_all_skills(
    skill_name: str | None = None,
    hub: str | None = None,
) -> dict:
    """Score all skills (or one). Returns dict with skills list + summary."""
    global _cache, _cache_ts

    # Cache check — invalidate if weight config was modified
    config_path = get_vault_dir() / "config" / "skill-score-weights.yaml"
    config_mtime = config_path.stat().st_mtime if config_path.exists() else 0
    cache_valid = (
        skill_name is None
        and time.time() - _cache_ts < _CACHE_TTL
        and _cache
        and _cache.get("_config_mtime") == config_mtime
    )
    if cache_valid:
        result = _cache
        if hub:
            result = {
                **result,
                "skills": [s for s in result["skills"] if s["hub"] == hub],
            }
        return result

    weights, thresholds = _load_weights()
    root = get_project_root()
    skills_dir = root / ".claude" / "skills"

    results = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill_dir = skill_md.parent
        sname = skill_dir.name

        if skill_name and sname != skill_name:
            continue

        try:
            fm, body = parse_frontmatter(skill_md)
        except Exception:
            fm, body = {}, ""

        instruction = _score_instruction(skill_md, fm, body)
        product = _score_product(skill_dir)
        ui = _score_ui(fm)
        wiring = _score_wiring(skill_dir)

        composite = (
            instruction["score"] * weights.get("instruction", 0.30)
            + product["score"] * weights.get("product", 0.40)
            + ui["score"] * weights.get("ui", 0.15)
            + wiring["score"] * weights.get("wiring", 0.15)
        )
        composite = round(composite, 1)
        tier = _get_tier(composite, thresholds)

        skill_hub = (fm.get("x-augur-config") or {}).get("hub", "system")
        if isinstance(skill_hub, list):
            skill_hub = skill_hub[0] if skill_hub else "system"

        results.append({
            "name": sname,
            "hub": skill_hub,
            "score": composite,
            "tier": tier,
            "dimensions": {
                "instruction": {**instruction, "weight": weights.get("instruction", 0.30), "weighted": round(instruction["score"] * weights.get("instruction", 0.30), 1)},
                "product": {**product, "weight": weights.get("product", 0.40), "weighted": round(product["score"] * weights.get("product", 0.40), 1)},
                "ui": {**ui, "weight": weights.get("ui", 0.15), "weighted": round(ui["score"] * weights.get("ui", 0.15), 1)},
                "wiring": {**wiring, "weight": weights.get("wiring", 0.15), "weighted": round(wiring["score"] * weights.get("wiring", 0.15), 1)},
            },
        })

    results.sort(key=lambda x: -x["score"])

    # Tier distribution
    tier_dist = {}
    for r in results:
        tier_dist[r["tier"]] = tier_dist.get(r["tier"], 0) + 1

    avg = round(sum(r["score"] for r in results) / max(len(results), 1), 1)

    config_mtime_val = config_path.stat().st_mtime if config_path.exists() else 0
    output = {
        "skills": results,
        "summary": {
            "total": len(results),
            "tier_distribution": tier_dist,
            "average_score": avg,
        },
        "weights": weights,
        "thresholds": thresholds,
        "_config_mtime": config_mtime_val,
    }

    # Cache full results
    if skill_name is None:
        _cache = output
        _cache_ts = time.time()

    if hub:
        output = {**output, "skills": [s for s in output["skills"] if s["hub"] == hub]}

    return output


def register_skill_score_tools(mcp, mcp_tool_interceptor=None, metrics=None):
    """Register skill-score MCP tool."""
    from augur_mcp.annotations import tool_annotations

    @mcp.tool(
        name="skill-score",
        annotations=tool_annotations({
            "title": "Skill Quality Score",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    async def skill_score(skill_name: str = "", hub: str = "") -> str:
        """Compute quality scores for skills across 4 dimensions: instruction quality, product completeness, UI maturity, and wiring integrity. Returns scored list with tier rankings."""
        result = score_all_skills(
            skill_name=skill_name or None,
            hub=hub or None,
        )
        return json.dumps(result)
```

- [ ] **Step 2: Verify the file exists and has no syntax errors**

Run: `cd ~/Projects/Augur && python -c "import ast; ast.parse(open('src/mcp/augur_mcp/infrastructure/skill_scorer.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/skill_scorer.py
git commit -m "feat(scorer): add unified skill scorer MCP tool"
```

---

## Task 2: Register Tool + Create Weight Config

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/__init__.py` (lines 86-133)
- Create: `get_vault_dir()/config/skill-score-weights.yaml`

- [ ] **Step 1: Add scorer import and registration to infrastructure __init__.py**

In `src/mcp/augur_mcp/infrastructure/__init__.py`, add after line 99 (`from .workflow import register_workflow_tools`):

```python
    from .skill_scorer import register_skill_score_tools
```

Then add after line 133 (`register_browse_tools(mcp, mcp_tool_interceptor, metrics)`):

```python
    # Register skill quality score tools
    register_skill_score_tools(mcp, mcp_tool_interceptor, metrics)
```

- [ ] **Step 2: Create default weight config in vault**

Create `get_vault_dir()/config/skill-score-weights.yaml`:

```yaml
# Skill Quality Score — weight configuration
# Weights must sum to 1.0. Edit via dashboard at /professional/demo.
weights:
  instruction: 0.30
  product: 0.40
  ui: 0.15
  wiring: 0.15
tier_thresholds:
  A: 75
  B: 55
  C: 35
  D: 15
```

- [ ] **Step 3: Test MCP tool loads without errors**

Run: `cd ~/Projects/Augur && python -c "from src.mcp.augur_mcp.infrastructure.skill_scorer import score_all_skills; r = score_all_skills(); print(f'Scored {r[\"summary\"][\"total\"]} skills, avg={r[\"summary\"][\"average_score\"]}'); print('Tiers:', r['summary']['tier_distribution'])"`
Expected: Scored ~134 skills with tier distribution output.

- [ ] **Step 4: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/__init__.py get_vault_dir()/config/skill-score-weights.yaml
git commit -m "feat(scorer): register skill-score MCP tool and create default weight config"
```

---

## Task 3: Dashboard API Route

**Files:**
- Create: `apps/dashboard/app/api/skill-score/route.ts`

- [ ] **Step 1: Create the API route**

```typescript
import { NextResponse } from "next/server";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const skill = searchParams.get("skill") || "";
  const hub = searchParams.get("hub") || "";

  try {
    const result = await callMCPTool("skill-score", { skill_name: skill, hub });

    if (result.isError) {
      const errorText = MCPBridge.extractText(result);
      return NextResponse.json({ error: errorText }, { status: 502 });
    }

    const data = MCPBridge.parseJSON(result);
    return NextResponse.json({ success: true, data });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "skill-score MCP tool failed" },
      { status: 500 },
    );
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { weights, tier_thresholds } = body;

    // Validate weights sum to 1.0
    if (weights) {
      const total = Object.values(weights).reduce(
        (sum: number, w) => sum + (w as number),
        0,
      );
      if (Math.abs(total - 1.0) > 0.01) {
        return NextResponse.json(
          { error: `Weights must sum to 1.0, got ${total.toFixed(3)}` },
          { status: 400 },
        );
      }
    }

    // Build YAML content
    const yamlLines = [
      "# Skill Quality Score — weight configuration",
      "weights:",
      `  instruction: ${weights?.instruction ?? 0.3}`,
      `  product: ${weights?.product ?? 0.4}`,
      `  ui: ${weights?.ui ?? 0.15}`,
      `  wiring: ${weights?.wiring ?? 0.15}`,
      "tier_thresholds:",
      `  A: ${tier_thresholds?.A ?? 75}`,
      `  B: ${tier_thresholds?.B ?? 55}`,
      `  C: ${tier_thresholds?.C ?? 35}`,
      `  D: ${tier_thresholds?.D ?? 15}`,
    ].join("\n");

    const writeResult = await callMCPTool("file-write", {
      path: "get_vault_dir()/config/skill-score-weights.yaml",
      content: yamlLines,
    });

    if (writeResult.isError) {
      const errorText = MCPBridge.extractText(writeResult);
      return NextResponse.json({ error: errorText }, { status: 502 });
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to save weights" },
      { status: 500 },
    );
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/dashboard/app/api/skill-score/route.ts
git commit -m "feat(scorer): add /api/skill-score API route for GET scores and POST weights"
```

---

## Task 4: Browse Integration — Replace Grade with Quality Tier

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/browse.py` (lines 562-605)
- Modify: `apps/dashboard/components/shared/BrowseCard.tsx` (lines 237-254)
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts` (line ~397)

- [ ] **Step 1: Update browse.py — add qualityTier/qualityScore to metadata**

In `src/mcp/augur_mcp/infrastructure/browse.py`, replace the grade_map block (lines 562-605). Keep `pages`/`customPages` computation. Replace `grade` with `qualityTier`/`qualityScore`.

Replace this block (lines 562-588 — the `grade_map` builder):
```python
    # Build skill grade map from SKILL.md frontmatter page states
    grade_map: dict[str, str] = {}
    if category == "skills":
        ...entire grade_map block...
```

With:
```python
    # Build skill quality score map + page counts from SKILL.md
    quality_map: dict[str, str] = {}
    page_map: dict[str, str] = {}
    if category == "skills":
        try:
            from augur_mcp.infrastructure.skill_scorer import score_all_skills
            scored = score_all_skills()
            for s in scored.get("skills", []):
                quality_map[s["name"]] = f'{s["tier"]}'
                quality_map[f'{s["name"]}:score'] = str(s["score"])
            # Page counts still come from frontmatter
            root = get_project_root()
            for _sd in get_all_client_skill_dirs(root):
                for skill_md_path in _sd.glob("*/SKILL.md"):
                    try:
                        fm, _ = parse_frontmatter(skill_md_path)
                        skill_name = fm.get("name", "")
                        config = fm.get("x-augur-config") or {}
                        pages = (config.get("contributions") or {}).get("pages") or []
                        page_types = [p.get("page_type", "auto") for p in pages if isinstance(p, dict)]
                        custom_count = sum(1 for pt in page_types if pt == "custom")
                        page_map[f"{skill_name}:pages"] = str(len(pages))
                        page_map[f"{skill_name}:custom"] = str(custom_count)
                    except Exception:
                        pass
        except Exception:
            pass
```

Then replace the metadata injection (lines 602-605):
```python
        if grade_map:
            metadata["grade"] = grade_map.get(name, "")
            metadata["pages"] = grade_map.get(f"{name}:pages", "0")
            metadata["customPages"] = grade_map.get(f"{name}:custom", "0")
```

With:
```python
        if quality_map:
            metadata["qualityTier"] = quality_map.get(name, "")
            metadata["qualityScore"] = quality_map.get(f"{name}:score", "0")
        if page_map:
            metadata["pages"] = page_map.get(f"{name}:pages", "0")
            metadata["customPages"] = page_map.get(f"{name}:custom", "0")
```

- [ ] **Step 2: Update BrowseCard.tsx — replace grade badge with qualityTier badge**

In `apps/dashboard/components/shared/BrowseCard.tsx`, replace the grade badge block (lines ~237-248):

```tsx
{/* Skill grade badge */}
{item.metadata?.grade && (
  ...existing grade badge...
)}
```

With:
```tsx
{/* Skill quality tier badge */}
{item.metadata?.qualityTier && (
  <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
    item.metadata.qualityTier === 'A'
      ? 'bg-[var(--accent-success)]/15 text-[var(--accent-success)]'
      : item.metadata.qualityTier === 'B'
        ? 'bg-[var(--accent-info)]/15 text-[var(--accent-info)]'
        : item.metadata.qualityTier === 'C'
          ? 'bg-[var(--accent-warning)]/15 text-[var(--accent-warning)]'
          : item.metadata.qualityTier === 'D' || item.metadata.qualityTier === 'F'
            ? 'bg-red-500/15 text-red-500'
            : 'bg-[var(--text-muted)]/15 text-[var(--text-muted)]'
  }`}>
    {item.metadata.qualityTier} ({item.metadata.qualityScore})
  </span>
)}
```

Keep the existing pages/customPages badge as-is.

- [ ] **Step 3: Update useBrowseState.ts — change tag key for skills**

In `apps/dashboard/app/(views)/browse/useBrowseState.ts`, change line ~397:

```typescript
    case "skills": return "grade";
```
To:
```typescript
    case "skills": return "qualityTier";
```

Also check `default: return "grade"` (~line 402). This is the fallback for non-skills views — leave it as `"grade"` since other views don't have quality scoring. Only the `"skills"` case needs to change.

- [ ] **Step 4: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/browse.py apps/dashboard/components/shared/BrowseCard.tsx apps/dashboard/app/(views)/browse/useBrowseState.ts
git commit -m "feat(scorer): replace browse grade with computed qualityTier/qualityScore badges"
```

---

## Task 5: Deep-Dive Page — Types and Data Fetching

**Files:**
- Rewrite: `.claude/skills/venture-augur/augur/dashboard/demo/types.ts`

- [ ] **Step 1: Rewrite types.ts with new scored types**

Keep the Demo-related types (`DemoCategory`, `DemoStep`, `Demo`, `Readiness`, `Principle`) and the codebase stats types (`HubStats`, `CoreBreakdown`, `PatternUsage`, `AugurStats`). Also keep `GateStatus`, `FactoryStage`, `QualityDimension`, `ImplementationGate`, `SkillProfile`, `LifecycleState`, `SkillData`, `QualityLevel`, `SkillEntry` — these are still imported by the remaining demo-related code in `data.ts` and `DemoCatalog.tsx`. Add the new scorer types at the bottom.

```typescript
// ── Demo types (keep existing) ──────────────────────────────────
export type Readiness = 'green' | 'yellow' | 'red';
export type Principle = 'trust' | 'freedom' | 'pace' | 'complexity' | 'future_proof';
export type DemoCategory = 'ecosystem' | 'cross-tool' | 'orchestration' | 'knowledge' | 'domain' | 'integration' | 'automation';
export type DemoStep = { action: string; type: 'cli' | 'dashboard' | 'browser'; narration: string };
export type Demo = { id: string; number: number; title: string; category: DemoCategory; rank: number; principles: Principle[]; readiness: Readiness; durationSeconds: number; steps: DemoStep[] };

// ── Codebase stats types (keep existing) ────────────────────────
export type HubStats = { hub: string; files: number; lines: number };
export type CoreBreakdown = { area: string; files: number; lines: number };
export type PatternUsage = { pattern: string; usage_count: number };
export type AugurStats = {
  code_distribution: { core: { files: number; lines: number; breakdown: CoreBreakdown[] }; plugins: { files: number; lines: number; by_hub: HubStats[] }; auto_generated: { files: number; lines: number } };
  scale_kpis: { shared_components: number; shared_hooks: number; shared_utilities: number; total_plugin_dashboard_files: number; plugins_using_shared: number; total_shared_imports: number; average_reuse_per_component: number; top_reused_patterns: PatternUsage[] };
  metadata: { collected_at: string; commit_hash: string; commit_message: string; commit_date: string };
};

// ── Legacy skill gate types (kept for DemoCatalog/data.ts compatibility) ──
export type GateStatus = 'pass' | 'fail' | 'na' | 'untested';
export type FactoryStage = { id: number; name: string; description: string; icon: React.ComponentType<{ className?: string }>; complete: boolean };
export type QualityDimension = { name: string; weight: number; score: number; maxScore: number };
export type ImplementationGate = { id: number; name: string; focus: string; status: GateStatus };
export type SkillProfile = 'minimal' | 'standard' | 'full';
export type LifecycleState = 'new' | 'configured' | 'enabled' | 'disabled' | 'archived';
export type SkillData = { name: string; bundle: string; profile: SkillProfile; lifecycle: LifecycleState; dependencies: { name: string; resolved: boolean }[]; factoryStages: FactoryStage[]; qualityDimensions: QualityDimension[]; qualityTier: string; overallScore: number; gates: ImplementationGate[] };
export type QualityLevel = 'functional' | 'partial' | 'scaffold' | 'stub';
export type SkillEntry = { name: string; bundle: string; quality: QualityLevel; hasData: boolean; hasMcp: boolean; hasUi: boolean; notes?: string };

// ── Skill scorer types (new) ────────────────────────────────────
export type DimensionSignals = Record<string, string | number | boolean | string[]>;

export type ScoredDimension = {
  score: number;
  weight: number;
  weighted: number;
  signals: DimensionSignals;
};

export type ScoredSkill = {
  name: string;
  hub: string;
  score: number;
  tier: string;
  dimensions: {
    instruction: ScoredDimension;
    product: ScoredDimension;
    ui: ScoredDimension;
    wiring: ScoredDimension;
  };
};

export type ScoreSummary = {
  total: number;
  tier_distribution: Record<string, number>;
  average_score: number;
};

export type ScoreWeights = {
  instruction: number;
  product: number;
  ui: number;
  wiring: number;
};

export type TierThresholds = {
  A: number;
  B: number;
  C: number;
  D: number;
};

export type SkillScoreResponse = {
  skills: ScoredSkill[];
  summary: ScoreSummary;
  weights: ScoreWeights;
  thresholds: TierThresholds;
};
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/venture-augur/augur/dashboard/demo/types.ts
git commit -m "feat(scorer): rewrite demo types for computed scoring model"
```

---

## Task 6: Deep-Dive Page — Visualization Components

**Files:**
- Rewrite: `.claude/skills/venture-augur/augur/dashboard/demo/SkillGateVisualizer.tsx`

- [ ] **Step 1: Write new visualization components**

Rewrite `SkillGateVisualizer.tsx` with 4 components: `TierDistribution`, `WeightConfig`, `SkillScoreTable`, `SkillDetail`.

The component should:
- `TierDistribution`: horizontal stacked bar (A green, B blue, C orange, D red, F gray) + total count + average score
- `WeightConfig`: 4 range sliders (0-100, displayed as 0.0-1.0) + 4 tier threshold number inputs + Apply/Reset buttons. Calls `onSave(weights, thresholds)` on Apply. Validates sum = 1.0.
- `SkillScoreTable`: searchable, sortable table with columns: Name, Hub, Tier, Score, 4 mini dimension bars. Click row to expand `SkillDetail`.
- `SkillDetail`: expanded row showing 4 dimension bars at full width with signal-level breakdown (checkmarks/crosses for boolean signals, numbers for counts)

Use shadcn/ui `Input`, `Button`, `Badge` where available. Use CSS variables (`--accent-success`, `--accent-info`, `--accent-warning`, `--bg-primary`, `--text-primary`, `--border-color`) for theming.

See the spec wireframe in `docs/superpowers/specs/2026-03-18-unified-skill-scorer-design.md` for layout reference.

Export: `{ TierDistribution, WeightConfig, SkillScoreTable }`

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/venture-augur/augur/dashboard/demo/SkillGateVisualizer.tsx
git commit -m "feat(scorer): rewrite visualizer with TierDistribution, WeightConfig, SkillScoreTable"
```

---

## Task 7: Deep-Dive Page — Page Component + Clean data.ts

**Files:**
- Rewrite: `.claude/skills/venture-augur/augur/dashboard/demo/page.tsx`
- Modify: `.claude/skills/venture-augur/augur/dashboard/demo/data.ts` — remove skill-related exports, keep demo exports

- [ ] **Step 1: Clean data.ts — remove skill scoring exports, keep demo data**

`DemoCatalog.tsx` imports `{ DEMOS, CATEGORY_LABELS, PRINCIPLE_LABELS, STEP_ICONS }` from `'./data'`. These must stay.

Remove from `data.ts`: `SKILL_ENTRIES`, `QUALITY_PRESETS`, `GATE_DEFS`, `buildSkillData`, `SKILLS` and all their associated code. Keep: `DEMOS`, `CATEGORY_LABELS`, `PRINCIPLE_LABELS`, `STEP_ICONS` and their types.

- [ ] **Step 2: Rewrite page.tsx**

Keep `DemoCatalog` and `CodebaseStats` imports. Replace the `SkillGateVisualizer` section with the new scoring UI. Fetch data from `/api/skill-score`.

```typescript
'use client';

import { useState, useCallback } from 'react';
import { BarChart3 } from 'lucide-react';
import { useCachedFetch } from '@/lib/hooks/useCachedFetch';
import DemoCatalog from './DemoCatalog';
import { TierDistribution, WeightConfig, SkillScoreTable } from './SkillGateVisualizer';
import CodebaseStats from './CodebaseStats';
import type { SkillScoreResponse } from './types';

export default function DemoPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const { data, loading, error } = useCachedFetch<{ success: boolean; data: SkillScoreResponse }>(
    `/api/skill-score?_=${refreshKey}`,
    ["skill-score", String(refreshKey)],
    { scope: "config" },
  );

  const scoreData = data?.data;

  const handleSaveWeights = useCallback(async (weights: Record<string, number>, thresholds: Record<string, number>) => {
    const res = await fetch("/api/skill-score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weights, tier_thresholds: thresholds }),
    });
    if (res.ok) {
      setRefreshKey((k) => k + 1);
    }
    return res.ok;
  }, []);

  return (
    <div className="space-y-8">
      <header className="page-header">
        <div className="flex-1">
          <h1 className="page-title">Demo</h1>
          <p className="page-subtitle">19 demos across 7 categories — pick one to present</p>
        </div>
      </header>

      {/* Demo Catalog — primary section */}
      <DemoCatalog />

      {/* Skill Quality Scores — secondary section */}
      <div className="pt-4 border-t border-[var(--border-color)]">
        <h2 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-4">
          <BarChart3 className="w-5 h-5 text-[var(--accent-info)]" />
          Skill Quality Scores
        </h2>

        {loading && <p className="text-sm text-[var(--text-muted)]">Loading scores...</p>}
        {error && <p className="text-sm text-red-500">Failed to load scores: {String(error)}</p>}

        {scoreData && (
          <div className="space-y-4">
            <TierDistribution summary={scoreData.summary} />
            <WeightConfig
              weights={scoreData.weights}
              thresholds={scoreData.thresholds}
              onSave={handleSaveWeights}
            />
            <SkillScoreTable skills={scoreData.skills} />
          </div>
        )}
      </div>

      {/* Codebase Statistics — tertiary section */}
      <div className="pt-4 border-t border-[var(--border-color)]">
        <CodebaseStats />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify DemoCatalog still imports from data.ts successfully**

Run: `grep "from.*./data" .claude/skills/venture-augur/augur/dashboard/demo/DemoCatalog.tsx`
Expected: `import { DEMOS, CATEGORY_LABELS, PRINCIPLE_LABELS, STEP_ICONS } from './data';` — still present and valid.

Run: `grep "SKILLS\|SKILL_ENTRIES\|QUALITY_PRESETS\|buildSkillData\|GATE_DEFS" .claude/skills/venture-augur/augur/dashboard/demo/data.ts`
Expected: No matches — all skill-related exports removed.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/venture-augur/augur/dashboard/demo/page.tsx .claude/skills/venture-augur/augur/dashboard/demo/data.ts
git commit -m "feat(scorer): rewrite demo page with live scoring, strip skill data from data.ts"
```

---

## Task 8: Build Verification

- [ ] **Step 1: Run Python scorer standalone**

Run: `cd ~/Projects/Augur && python -c "from src.mcp.augur_mcp.infrastructure.skill_scorer import score_all_skills; import json; r = score_all_skills(); print(json.dumps(r['summary'], indent=2))"`
Expected: Summary with total ~134, tier distribution, average score.

- [ ] **Step 2: Check TypeScript compiles**

Run: `cd ~/Projects/Augur/apps/dashboard && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors in scorer-related files. Pre-existing errors in other files are acceptable.

- [ ] **Step 3: Test dashboard builds**

Run: `cd ~/Projects/Augur/apps/dashboard && npm run build 2>&1 | tail -20`
Expected: Build succeeds.

- [ ] **Step 4: Verify browse page loads with new badges**

Start dev server and check `/browse` page renders skill cards with `qualityTier` badges instead of `grade`.

- [ ] **Step 5: Verify demo page loads with live scores**

Check `/professional/demo` page shows tier distribution, weight sliders, and sortable skill score table.

- [ ] **Step 6: Final commit if any fixups needed**

```bash
git add -A
git commit -m "fix(scorer): build verification fixups"
```
