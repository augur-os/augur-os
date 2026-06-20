---
status: Implemented
date: 2026-04-27
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-604: Guriqo Light Mode Rebrand (Phase 3)

## Context

guriqo.com inherited the Augur dark theme, but its audience is enterprise IT/legal/finance buyers — for whom dark-mode developer aesthetics signal "tech tool" rather than "trusted services partner." The visual half of the strategic positioning shift (the messaging half landed in V10026) needed to align with the B2B "Trust & Authority" pattern: light backgrounds, high contrast, professional typography (Lexend headings, Source Sans 3 body, Fira Code mono), corporate-blue CTAs, no purple/cyan AI gradients.

The rebrand is scoped to three file regions: additions to `styles.css` (RGB-triple variables and a comprehensive `body.guriqo-theme` override block); refactoring `enterprise.html`'s inline `<style>` block to replace hard-coded `rgba(144, 64, 255, X)`, `rgba(0, 240, 255, X)`, and `rgba(239, 68, 68, X)` literals with `rgba(var(--accent-violet-rgb), X)` and equivalents so opacity-driven colors flow through the token system; and swapping the `enterprise.html` `<head>` font import from Fira Sans + Inter + Fira Code to Lexend + Source Sans 3 + Fira Code.

`augur.run` must remain visually unchanged — the `:root` RGB-triple additions are additive and don't replace existing tokens, and the `body.guriqo-theme` overrides are scoped to that class only (augur.run's body has no class).

## Decision

Convert guriqo.com from dark mode to a B2B light-mode palette by:

1. **Adding 3 RGB-triple variables to `:root`** in `styles.css` (`--accent-violet-rgb`, `--accent-primary-rgb`, `--status-red-rgb`) mirroring existing hex tokens, enabling `rgba(var(--triple), X)` syntax for variable-driven opacity.
2. **Replacing the focused Phase-2b `body.guriqo-theme` block** with a comprehensive light-mode override: navy/corporate-blue/light-red RGB triples; navy/blue hex tokens; light bg/text/border/shadow tokens; Lexend (headings), Source Sans 3 (body), Fira Code (mono); universal card override that disables `backdrop-filter` blur and switches glass cards to solid white with soft shadow; light-variant scrollbar and selection.
3. **Refactoring `enterprise.html` inline `<style>`** via three replacement passes: violet rgba → `var(--accent-violet-rgb)` (~25), cyan rgba → `var(--accent-primary-rgb)` (~5), red rgba → `var(--status-red-rgb)` (~6).
4. **Updating the font import** to Lexend + Source Sans 3 + Fira Code with `display=swap` retained.

Approach choices: (Q1) refactor enterprise.html to use CSS variables — cleanest long-term over an override-only path; (Q2) full typography swap; (Q3) hybrid visual feedback — bulk refactor + Chrome MCP screenshot + user eyeball gate before deploy.

Out of scope: `index.html` or any other augur.run page; layout/spacing/copy changes; new sections, illustrations, or images; schema.org JSON-LD or meta tags; `release.sh`; theme-toggle UI on guriqo.com.

Acceptance criteria include: body bg `#f8fafc`; Lexend headings; corporate-blue (`#0369a1`) primary CTAs on white; navy-outline secondary buttons; no visible purple/violet/magenta/pink or cyan; WCAG AA contrast (pre-verified pairs at 18:1, 7.6:1, 5.4:1); `augur.run` visually unchanged.

## Consequences

### Positive
- Visual treatment matches the enterprise audience (Trust & Authority B2B pattern).
- WCAG AA+ contrast on all text/background pairs (pre-verified ratios).
- CSS variable refactor is structurally cleaner than per-rule overrides; future palette tweaks are central.
- `augur.run` untouched — same `styles.css`, additive variables, scoped class overrides.
- Variable-driven opacity (`rgba(var(--triple), X)`) supported in Chrome 49+ / Firefox 46+ / Safari 9+ — universal coverage.

### Negative
- Ongoing maintenance: any new section in `enterprise.html` must use `var(--triple)` form, not raw `rgba(144, 64, 255, X)`. Discipline required.
- Lexend / Source Sans 3 fonts add network requests; FOUT possible on slow connections (mitigated by `display=swap`).
- Refactor surface is wide (~36 replacements); a missed hard-coded value would visibly break.

### Neutral
- No new ADRs created elsewhere by this change.
- No layout / structure / copy changes; visual-only.
- Card backdrop-filter explicitly disabled under `body.guriqo-theme` — different visual treatment from augur.run.

## Alternatives Considered

### Alternative 1: Override-only approach (don't refactor enterprise.html)
Rejected. Would require duplicating every rgba opacity rule under `body.guriqo-theme`, creating massive selector duplication and ongoing drift risk. Refactoring to CSS variables is cleanest long-term.

### Alternative 2: Keep existing typography (no Lexend/Source Sans 3 swap)
Rejected. Typography is a load-bearing part of the Trust & Authority pattern; the dark theme's Fira Sans / Inter pairing reads as "tech" rather than "professional services."

### Alternative 3: Add a theme-toggle UI to guriqo.com
Rejected. The audience flip is permanent for guriqo (not user-preference); a toggle would imply both palettes are valid options for this audience.

### Alternative 4: Move guriqo to its own stylesheet
Rejected for now. Shared `styles.css` with class-scoped overrides keeps deploy simple (one stylesheet, two classed bodies) and minimizes drift.

## References
- Spec: docs/superpowers/specs/2026-04-27-guriqo-light-mode-rebrand-design.md
- Related strategic spec: docs/superpowers/specs/2026-04-27-augur-run-and-guriqo-investor-messaging-design.md
