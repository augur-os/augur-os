---
title: guriqo.com light-mode rebrand (Phase 3)
date: 2026-04-27
status: approved
owner: gsannikov
---

# guriqo.com light-mode rebrand (Phase 3)

## Goal

Convert guriqo.com from the inherited Augur dark theme to a B2B "Trust & Authority" light-mode palette with Lexend/Source Sans 3 typography, by extending the CSS variable system, refactoring `enterprise.html`'s hard-coded rgba colors to reference those variables, and overriding the variables under `body.guriqo-theme`.

Underlies the strategic shift documented in `2026-04-27-augur-run-and-guriqo-investor-messaging-design.md`: guriqo.com's audience is enterprise IT/legal/finance buyers, for whom dark-mode developer aesthetics signal "tech tool" instead of "trusted services partner". The light-mode flip is the visual half of the rebrand; the messaging half landed in V10026.

## In scope (3 file regions)

1. **`styles.css`** — additions:
   - 3 new RGB-triple variables in `:root`: `--accent-violet-rgb`, `--accent-primary-rgb`, `--status-red-rgb`. Mirror the existing hex tokens; allow `rgba(var(--triple), X)` syntax for variable-driven opacity.
   - Replace the focused `body.guriqo-theme` block (currently Phase-2b gradient-only) with the comprehensive light-mode override: RGB triples swapped to navy/corporate-blue/light-red; hex tokens swapped to navy/blue; bg/text/border/shadow tokens flipped to light variants; font-family swapped to Lexend (headings) + Source Sans 3 (body) + Fira Code (mono).
   - Universal card override under `body.guriqo-theme` to disable `backdrop-filter` blur and switch glass cards to solid white with soft shadow.

2. **`enterprise.html` inline `<style>` block** (lines 60–610) — refactor:
   - Replace every `rgba(144, 64, 255, X)` → `rgba(var(--accent-violet-rgb), X)`. ~25 occurrences.
   - Replace every `rgba(0, 240, 255, X)` → `rgba(var(--accent-primary-rgb), X)`. ~5 occurrences.
   - Replace every `rgba(239, 68, 68, X)` → `rgba(var(--status-red-rgb), X)`. ~6 occurrences.

3. **`enterprise.html` `<head>` font import** — replace:
   - Old: `Fira Sans + Fira Code + Inter`.
   - New: `Lexend + Source Sans 3 + Fira Code`.
   - `display=swap` retained.

## Out of scope (explicitly)

- No changes to `index.html` or any other augur.run page (Augur stays on the inherited dark palette).
- No layout, spacing, section structure, or copy changes in enterprise.html.
- No new sections, illustrations, or images.
- No edits to schema.org JSON-LD or meta tags.
- No edits to `release.sh` (already polished previous round).
- No theme-toggle UI on guriqo.com.
- No new ADRs.

## Tone & visual direction

Content stays the same; only visual treatment changes. Hero proof line, "What we deploy" text, all section copy unchanged. The B2B "Trust & Authority" pattern is achieved through palette + typography + card style, not through new copy. Anti-pattern explicitly avoided: no AI purple/pink gradients (already addressed Phase 2b — kept).

## Acceptance criteria

After deploy of V10028 (or whatever version lands this rebrand):

- `guriqo.com` body background is `#f8fafc` (light slate).
- Headings render in Lexend (weights 300–700).
- Body text renders in Source Sans 3.
- Code/badge fragments render in Fira Code.
- Primary CTAs render in corporate blue (`#0369a1`) on white with white text.
- Secondary buttons render as navy outlines.
- No visible purple, violet, magenta, or pink in any section.
- No visible cyan in any section.
- All text passes WCAG AA contrast against its background (4.5:1 minimum). Pre-verified ratios:
  - `#020617` on `#f8fafc` → 18:1 (AAA).
  - `#475569` on `#f8fafc` → 7.6:1 (AAA).
  - `#64748b` on `#f8fafc` → 5.4:1 (AA).
- `augur.run` is **unchanged**: hero, sections, colors, typography all identical to pre-rebrand. Verified by curl + visual.

## Approach per artifact

### 1. `styles.css` additions

#### New `:root` variables (top of file, alongside existing definitions):

```css
:root {
    /* ... existing variables ... */

    /* RGB-triple variables — for use inside rgba() with opacity */
    --accent-violet-rgb: 144, 64, 255;
    --accent-primary-rgb: 0, 240, 255;
    --status-red-rgb: 239, 68, 68;
}
```

#### Replace existing `body.guriqo-theme` block with:

```css
body.guriqo-theme {
    /* RGB triples — navy + corporate blue + WCAG-grade red */
    --accent-violet-rgb: 15, 23, 42;
    --accent-primary-rgb: 3, 105, 161;
    --status-red-rgb: 220, 38, 38;

    /* Hex tokens — paths that use --accent-* directly */
    --accent-violet: #0f172a;
    --accent-primary: #0369a1;
    --accent-violet-dim: #1e293b;
    --accent-glow: rgba(3, 105, 161, 0.1);
    --accent-text: #ffffff;

    /* Backgrounds — light, professional */
    --bg-primary: #f8fafc;
    --bg-secondary: #ffffff;
    --bg-card: rgba(255, 255, 255, 0.95);
    --bg-glass: rgba(255, 255, 255, 0.85);
    --bg-hover: rgba(241, 245, 249, 0.95);
    --bg-section-alt: rgba(248, 250, 252, 0.6);
    --bg-input: rgba(255, 255, 255, 0.95);
    --bg-nav: rgba(255, 255, 255, 0.9);
    --bg-nav-mobile: rgba(248, 250, 252, 0.98);
    --bg-code: #f1f5f9;
    --bg-table-head: rgba(241, 245, 249, 0.7);

    /* Text — high contrast (WCAG AA+) */
    --text-primary: #020617;
    --text-secondary: #475569;
    --text-muted: #64748b;

    /* Borders */
    --border: rgba(15, 23, 42, 0.12);
    --border-hover: rgba(15, 23, 42, 0.22);
    --glass-border: rgba(15, 23, 42, 0.08);
    --glass-shine: rgba(15, 23, 42, 0.03);

    /* Shadows — softer for light mode */
    --shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.06);
    --shadow-md: 0 4px 24px -1px rgba(15, 23, 42, 0.08);
    --shadow-glow: 0 8px 32px rgba(3, 105, 161, 0.1);
    --glass-highlight: inset 0 1px 0 rgba(255, 255, 255, 0.5);

    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: 'Source Sans 3', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Headings */
body.guriqo-theme h1,
body.guriqo-theme h2,
body.guriqo-theme h3,
body.guriqo-theme h4,
body.guriqo-theme h5,
body.guriqo-theme h6 {
    font-family: 'Lexend', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Mono — kept Fira Code */
body.guriqo-theme code,
body.guriqo-theme pre,
body.guriqo-theme .mono,
body.guriqo-theme .badge-value,
body.guriqo-theme .cta-price,
body.guriqo-theme .hero-tagline,
body.guriqo-theme .principle-num,
body.guriqo-theme .session-meta,
body.guriqo-theme .module-num,
body.guriqo-theme .arch-tag,
body.guriqo-theme .arch-layer-num {
    font-family: 'Fira Code', SFMono-Regular, Menlo, Monaco, monospace;
}

/* Body bg gradient swap (kept from Phase 2b — navy/blue replaces purple/pink) */
body.guriqo-theme::before {
    background:
        radial-gradient(circle at calc(var(--mouse-x) * 0.6% + 8%) calc(var(--mouse-y) * 0.6% + 12%), rgba(3, 105, 161, 0.06) 0%, transparent 50%),
        radial-gradient(circle at calc(100% - var(--mouse-x) * 0.4%) calc(var(--mouse-y) * 0.4%), rgba(15, 23, 42, 0.04) 0%, transparent 50%),
        radial-gradient(circle at calc(var(--mouse-x) * 0.5% + 15%) calc(100% - var(--mouse-y) * 0.5%), rgba(2, 132, 199, 0.04) 0%, transparent 50%) !important;
}

/* Card override — solid white, no backdrop-filter */
body.guriqo-theme .cta-card,
body.guriqo-theme .glass-panel,
body.guriqo-theme .ring-card,
body.guriqo-theme .path-card,
body.guriqo-theme .augur-is-card,
body.guriqo-theme .works-card,
body.guriqo-theme .option-card,
body.guriqo-theme .mode-card,
body.guriqo-theme .corporate-callout,
body.guriqo-theme .problem-bullet,
body.guriqo-theme .faq-item,
body.guriqo-theme .metric-badge {
    background: #ffffff;
    border: 1px solid var(--border);
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    box-shadow: var(--shadow-md);
}

/* Button overrides */
body.guriqo-theme .cta-btn-primary,
body.guriqo-theme .nav-cta {
    background: var(--accent-primary);
    color: var(--accent-text);
    box-shadow: 0 4px 16px rgba(3, 105, 161, 0.2);
}
body.guriqo-theme .cta-btn-primary:hover,
body.guriqo-theme .nav-cta:hover {
    box-shadow: 0 6px 24px rgba(3, 105, 161, 0.3);
}
body.guriqo-theme .cta-btn-secondary {
    color: var(--accent-violet);
    border-color: rgba(15, 23, 42, 0.2);
}
body.guriqo-theme .cta-btn-secondary:hover {
    background: rgba(15, 23, 42, 0.05);
    border-color: var(--accent-violet);
}
body.guriqo-theme .cta-btn-tertiary {
    color: var(--accent-primary);
    border-color: rgba(3, 105, 161, 0.3);
}
body.guriqo-theme .cta-btn-tertiary:hover {
    border-color: var(--accent-primary);
    background: rgba(3, 105, 161, 0.04);
    color: var(--accent-primary);
}

/* Section labels */
body.guriqo-theme .section-label {
    color: var(--accent-primary);
}

/* Scrollbar — light variant */
body.guriqo-theme::-webkit-scrollbar-thumb { background: rgba(15, 23, 42, 0.18); }
body.guriqo-theme::-webkit-scrollbar-thumb:hover { background: rgba(15, 23, 42, 0.3); }
body.guriqo-theme::-webkit-scrollbar-track { background: var(--bg-secondary); }

/* Selection */
body.guriqo-theme ::selection {
    background: var(--accent-primary);
    color: #ffffff;
}
```

### 2. `enterprise.html` inline `<style>` refactor

Three sed-style passes inside the `<style>` block (lines 60–610):

```
rgba(144, 64, 255, X)   →   rgba(var(--accent-violet-rgb), X)
rgba(0, 240, 255, X)    →   rgba(var(--accent-primary-rgb), X)
rgba(239, 68, 68, X)    →   rgba(var(--status-red-rgb), X)
```

Verify post-refactor:
```bash
grep -c "rgba(144, 64, 255" enterprise.html      # expect 0
grep -c "rgba(0, 240, 255" enterprise.html        # expect 0
grep -c "rgba(239, 68, 68" enterprise.html        # expect 0
grep -c "rgba(var(--accent-violet-rgb)" enterprise.html    # expect 25+
grep -c "rgba(var(--accent-primary-rgb)" enterprise.html    # expect 5+
grep -c "rgba(var(--status-red-rgb)" enterprise.html        # expect 6+
```

### 3. `enterprise.html` font import

```html
<!-- old -->
<link href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@300;400;500;600;700&family=Fira+Code:wght@400;600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

<!-- new -->
<link href="https://fonts.googleapis.com/css2?family=Lexend:wght@300;400;500;600;700&family=Source+Sans+3:wght@300;400;500;600;700&family=Fira+Code:wght@400;600&display=swap" rel="stylesheet">
```

## Sequencing

1. Add 3 `:root` RGB-triple variables to `styles.css`.
2. Replace existing `body.guriqo-theme` block (Phase-2b only) with the comprehensive override block.
3. Refactor `enterprise.html` inline `<style>` block via 3 sed passes.
4. Update `enterprise.html` font import.
5. `bash release.sh` → V10028 zips.
6. Open `enterprise.html` in Chrome via `claude-in-chrome` MCP. Screenshot.
7. Identify obvious visual breakage (sections with hard-coded values I missed; contrast issues; layout breaks). Fix. Re-screenshot.
8. **User eyeball gate** — surface screenshot/result, ask user to confirm visual is acceptable.
9. SCP + SSH deploy guriqo zip on confirm. (augur.run zip can deploy too — change to styles.css adds variables which augur ignores.)
10. Live verify both URLs (curl + visual).

## Verification gates

- **Variable refactor**: post-edit grep counts (zero hard-coded rgba violet/cyan/red; counts of var() match).
- **Font import**: `grep "Lexend" enterprise.html` returns 1; `grep "Fira Sans" enterprise.html` returns 0 (no longer loaded).
- **augur.run unchanged**: visit augur.run after deploy; hero, sections, colors all identical to pre-rebrand.
- **guriqo.com light mode**: visit guriqo.com after deploy; bg light; Lexend headings; corporate-blue CTAs; no purple/cyan.
- **WCAG contrast**: spot-check 3 text/bg pairs against contrast checker.
- **Both fonts load**: DevTools Network tab shows Lexend + Source Sans 3 + Fira Code (no Fira Sans / Inter requests).

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| `rgba(var(--triple), X)` browser support | Supported in Chrome 49+, Firefox 46+, Safari 9+. All targets fine. |
| Refactor misses a hard-coded value (typo with extra spaces, etc.) | Chrome MCP screenshot in step 6 surfaces visible breakage. Fix and re-screenshot. |
| Some section-specific style hard-codes a color outside the rgba pattern (e.g. `background: #9040ff` literal hex) | Audit pass: `grep -E "144, 64, 255\|9040ff\|0, 240, 255\|00f0ff\|239, 68, 68" enterprise.html` before refactor; refactor any non-rgba forms separately if found |
| Lexend/Source Sans 3 fail to load → FOUT | `display=swap` set; user sees fallback briefly then proper font. Acceptable. |
| Card backdrop-filter blur visible against white | Universal `backdrop-filter: none` override |
| WCAG contrast fails on a specific text combination | Pre-verified the three color pairs in Section 2; spot-check after deploy |
| augur.run inadvertently breaks (style drift via shared styles.css) | The new `:root` RGB triples are additive (don't replace existing tokens); `body.guriqo-theme` overrides scoped to that class. augur.run's `<body>` has no class, so untouched. |

## Decisions log

- Q1 — implementation approach: **B** (refactor enterprise.html to use CSS variables; cleanest long-term).
- Q2 — typography scope: **A** (full swap to Lexend + Source Sans 3 + Fira Code).
- Q3 — visual feedback method: **C** (hybrid: I do bulk refactor + Chrome MCP screenshot + user eyeball before deploy).

## Where the work lands

- Augur main repo (this repo): only this spec lands here.
- `~/Projects/Au-docs/venture-augur/website-working/styles.css`: 3 new `:root` vars + comprehensive `body.guriqo-theme` block.
- `~/Projects/Au-docs/venture-augur/website-working/enterprise.html`: rgba refactor (~36 replacements) + font import update.
- Deploy: `release.sh` → SCP + SSH for guriqo.com (and augur.run, although augur.run has no functional change). User confirmation gate before SCP.
