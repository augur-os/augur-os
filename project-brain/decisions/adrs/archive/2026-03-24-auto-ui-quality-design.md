# Auto UI Quality — Nightly Design Audit Autoloop

**Date:** 2026-03-24
**Status:** Approved
**Skill:** `auto-ui-quality`
**Loop:** `ui-quality` (new, #11)

---

## Summary

Nightly autoloop that scans all 60 dashboard pages for UI/UX quality issues, scores them across 4 dimensions, and progressively fixes problems from safe code-level patches (d0-d2) to full LLM-assisted page redesigns (d3-d4). Uses ui-ux-pro-max design intelligence and Playwright screenshots for visual analysis. Auto-reverts on build failure or score regression.

## Identity & Loop Assignment

| Field | Value |
|-------|-------|
| Skill name | `auto-ui-quality` |
| Skill directory | `skills/auto-ui-quality/` |
| Hub | `adaptive` |
| Type | `autoloop` |
| Loop | `ui-quality` (new) |
| Tier | 2 |
| Trigger | `nightly` |
| Budget | 10 |
| Budget growth rate | 2 |

New `ui-quality` loop added to `config/system/adaptive_loops.yaml` alongside the existing 10 loops.

### Required SKILL.md Frontmatter

```yaml
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
```

### Required Module-Level DIFFICULTY_SPEC

```python
DIFFICULTY_SPEC = {
    0: "Inventory — discover pages, count accessibility/interaction/design-system issues",
    1: "Pattern check — validate transitions, icons, responsive classes, focus states",
    2: "Safe auto-fix — add cursor-pointer, fix transitions, replace hardcoded colors",
    3: "Visual analysis — Playwright screenshots, LLM audit against ui-ux-pro-max guidelines",
    4: "Full redesign — structural rewrites, layout grouping, search/filter addition",
}
```

## Difficulty Progression

| Level | Name | What it does | Auto-fix? | Trust gate |
|-------|------|-------------|-----------|------------|
| **d0** | Inventory | Discover all pages via `find_page_routes()`. Count high-confidence issues: missing `aria-label` on icon-only buttons, missing `cursor-pointer` on `onClick` elements, hardcoded hex/rgb colors (not `var(--*)`), emoji characters in JSX | No | Always |
| **d1** | Pattern check | Validate medium-confidence patterns: transition duration values outside 150-300ms, non-Lucide icon imports, missing responsive breakpoint classes (`md:`, `lg:`), `animate-*` without `motion-reduce:` variant | No | Always |
| **d2** | Safe auto-fix | Fix d0-d1 high-confidence issues: add `cursor-pointer`, fix transition durations, replace hardcoded colors with CSS vars, add `aria-label` on icon-only buttons | Yes | trust > 0.3 |
| **d3** | Visual analysis | Playwright screenshots of bottom-N pages. LLM analysis against ui-ux-pro-max guidelines. Apply targeted fixes. Engine verify_command + score check — revert on regression. | Yes (LLM) | trust > 0.5 |
| **d4** | Full redesign | Structural page rewrites: replace flat grids with grouped layouts, improve information hierarchy, add search/filter. Same git safety. | Yes (LLM) | trust > 0.5 |

**Budget per night:** d0-d1 scan all pages (~2 min). d2 fixes top 10 worst (`ctx.config["d2_fix_limit"]`). d3-d4 deep analysis on bottom 3 (`ctx.config["d3_analysis_limit"]`) + recently changed pages.

### Check Confidence Levels

Each check in `check_registry.yaml` declares a confidence level. Low-confidence checks are weighted 0.5x in scoring to prevent false positives from dominating.

| Confidence | Checks | Weight |
|------------|--------|--------|
| **High** | `cursor-pointer` on `onClick`, hardcoded hex colors, missing `aria-label` on icon-only buttons, emoji in JSX | 1.0x |
| **Medium** | Transition durations, non-Lucide imports, missing responsive classes, `animate-*` without `motion-reduce:` | 0.75x |
| **Low** | Touch target sizing (needs layout context), `prefers-reduced-motion` presence, focus state completeness (shadcn provides built-in) | 0.5x |

## Hybrid Priority System

### Page Score Registry

Stored at `get_runtime_dir() / "adaptive" / "ui-quality" / "page-scores.json"`:

```json
{
  "life/home-automation/scenes": {
    "score": 72,
    "last_audit": "2026-03-24",
    "issues": { "d0": 3, "d1": 1, "d2": 0 },
    "last_changed": "2026-03-24",
    "check_counts": { "applicable": 18, "passing": 13 }
  }
}
```

### Nightly Priority Algorithm

1. **d0-d1**: Scan ALL pages every night (cheap static regex/import analysis)
2. **d2**: Fix top N lowest-scoring pages (N = `ctx.config["d2_fix_limit"]`, default 10)
3. **d3-d4**: Pick bottom M pages by score (M = `ctx.config["d3_analysis_limit"]`, default 3), PLUS any pages with `git diff` changes since last audit
4. **Tie-breaking**: Never audited > oldest `last_audit` > most d0 issues
5. **Score formula**: Weighted sum of applicable checks passing, normalized to 0-100. Pages with fewer applicable checks (simple pages) are not penalized — only checks relevant to elements present in the page are counted.

### Score Dimensions

| Dimension | Weight | Checks |
|-----------|--------|--------|
| Accessibility | 30% | aria-labels on icon-only buttons, alt text on `<img>`, keyboard-navigable interactive elements |
| Interaction | 25% | cursor-pointer on onClick handlers, touch targets (44px min), transition durations (150-300ms), hover states |
| Design system | 25% | CSS vars (not hardcoded hex/rgb), Lucide icon imports (not emoji), consistent icon sizing |
| Responsiveness | 20% | breakpoint classes on grid/flex containers, no fixed-width containers without max-w |

Pages start at score 0 (unaudited). Score = (weighted passing checks / weighted applicable checks) * 100. Pages with 0 applicable checks for a dimension score N/A (dimension excluded from that page's calculation).

### Intentional Skip Support

Pages or components with `INTENTIONAL_SKIP: auto-ui-quality` comments are excluded from scoring. Checked via `check_intentional_skip()` from ops_protocol. Use for pages that intentionally deviate from design system (e.g., terminal emulator, code editor).

## Git Safety Net (d2-d4)

```
1. Snapshot current score for page
2. Apply fix (code edit)
3. Run engine verify_command (from adaptive_loops.yaml — currently tsc --noEmit)
4. If build fails → git revert, log failure, return FixResult(success=False)
5. If build passes → re-score page
6. If score regressed → git revert, log regression, return FixResult(success=False)
7. If score improved → commit, return FixResult(success=True)
```

Trust adjustments are handled by the engine based on FixResult — the module does not manipulate trust directly.

**Commit convention:** `fix(auto-ui-quality): improve {page-path} — {what changed}`

### d3-d4 Additional Safety

- Screenshots taken before AND after fix (stored in `get_runtime_dir() / "adaptive" / "ui-quality" / "screenshots"`)
- Before/after comparison included in nightly report
- Max page rewrites per night configurable via `ctx.config["max_page_rewrites"]` (default 3)
- Each page fix is a separate commit (granular revert)

### Dashboard Dev Server for Screenshots (d3-d4)

At d3-d4, screenshots require a running dashboard. The module:
1. Checks if `localhost:3000` responds (quick HTTP probe)
2. If available → proceed with Playwright screenshots
3. If unavailable → gracefully degrade to d2-only for this cycle, log `kind: "maintenance"` issue noting screenshots were skipped
4. Does NOT start the dev server itself (nightly runs at 03:00, server may be intentionally down)

## ui-ux-pro-max Integration

The autoloop calls ui-ux-pro-max at d3+ for design intelligence. Search results are injected into the LLM escalation prompt as context (same pattern as `llm_escalation.py`):

| Step | Command | Usage |
|------|---------|-------|
| Score against UX rules | `search.py "accessibility interaction" --domain ux` | Injected as LLM context |
| Check design patterns | `search.py "{page-context}" --design-system` | Injected as LLM context |
| Get stack guidelines | `search.py "{issue-keywords}" --stack shadcn` | Injected as LLM context |

The LLM agent at d3-d4 receives in its prompt:
- Page source code (TSX)
- Playwright screenshot (if available)
- Current score breakdown with per-check results
- ui-ux-pro-max search results as design recommendations
- GlassCard / design system component API summary

Generates targeted fixes within the existing component library.

## Nightly Report

**Primary report** (JSON, consumed by engine): written via `ops_protocol.write_report()` to `get_runtime_dir() / "adaptive" / "ui-quality" / "reports" / "YYYY-MM-DD.json"`.

**Secondary report** (Markdown, human-readable): written alongside as `YYYY-MM-DD.md`:

```markdown
# UI Quality Report — YYYY-MM-DD

## Summary
- Pages scanned: 60
- Average score: 68/100
- Issues found: 142 (d0: 89, d1: 53)
- Auto-fixed: 23 issues across 8 pages
- Deep analysis: 3 pages (d3-d4)

## Bottom 5 Pages
| Page | Score | Issues | Action |
|------|-------|--------|--------|
| life/finance | 34 | 12 | d4 rewrite applied |
| career/gtm/content | 41 | 9 | d3 fixes applied |
| brain/knowledge/index | 45 | 8 | d3 fixes applied |
| command/workflows | 52 | 7 | d2 fixes only |
| studio/workbench | 55 | 6 | d2 fixes only |

## Fixes Applied
- [commit abc123] life/finance: grouped cards by category, added search
- [commit def456] career/gtm/content: added cursor-pointer, fixed transitions

## Score Changes
- life/finance: 34 → 71 (+37)
- career/gtm/content: 41 → 63 (+22)

## Evolution Gaps
- No responsive breakpoint testing yet (needs viewport resize in Playwright)
- Dark mode contrast checking not implemented
```

## File Structure

```
skills/auto-ui-quality/
├── SKILL.md                          # Frontmatter + overview
├── scripts/
│   └── ui_quality.py                 # Main scan()/fix() module with DIFFICULTY_SPEC
├── augur/
│   ├── tests/
│   │   └── test_ui_quality.py        # Unit tests
│   └── data/
│       └── check_registry.yaml       # All d0-d1 check definitions with confidence levels
├── assets/
│   └── seeds/
│       └── _seed.yaml
└── references/
    └── .gitkeep
```

## Config Change

Add to `config/system/adaptive_loops.yaml`:

```yaml
ui-quality:
  budget: 10
  budget_growth_rate: 2
```

## Dependencies

- `src/lib/ops_protocol.py` — OpsCommand protocol (scan/fix), `find_page_routes()`, `check_intentional_skip()`
- `skills/ui-ux-pro-max/scripts/search.py` — Design intelligence
- Playwright (for d3-d4 screenshots, graceful degradation if unavailable)
- `apps/dashboard/components/ui/GlassCard.tsx` — Component API reference
- `ctx.shared_snapshot` — Reuse page route inventory from engine shared snapshot when available

## Evolution Gaps (Known)

- No dark mode contrast checking (d1 candidate)
- No viewport resize testing for responsive (d1 candidate)
- No animation performance profiling (future d2)
- No cross-page consistency scoring (future d3)
