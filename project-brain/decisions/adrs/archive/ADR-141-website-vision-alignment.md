---
status: Implemented
date: '2026-02-23'
deciders:
- Gur Sannikov
related:
- ADR-045 (website hardening V17)
hub: null
tags:
- website
- vision
- alignment
superseded_by: null
---

# ADR-141: Website Vision Alignment

## Context

The Augur website (augur.run) had diverged from the canonical messaging defined in two updated pitch decks:

- **Augur-Vision.pdf** (10 slides) — product vision and positioning for individuals/investors
- **Guriqo-Services.pdf** (10 slides) — consulting narrative with Two Rings Framework

The website used generic SaaS messaging (market stats, feature grids, 3-step how-it-works) that didn't reflect the refined pitch deck narrative arc.

## Decision

Rewrite the website to mirror the pitch decks slide-by-slide, establishing a single source of truth for all Augur/Guriqo messaging.

### index.html — Augur Vision Alignment

Map the 10-slide Augur-Vision deck to website sections 1:1:

| # | Deck Slide | Website Section | Action |
|---|---|---|---|
| 1 | AUGUR — "Your files become outcomes" | Hero — add subtitle | UPDATE |
| 2 | THE QUESTION — "Why am I not 10x yet?" | New section with 3 dependency bullets | NEW |
| 3 | THE INVERSION — Opportunity vs Augur Way | 2-column card replacing 4-persona problem/solution | REPLACE |
| 4 | WHAT AUGUR IS — Infrastructure for Self-Augmentation | 4-card grid replacing features grid | REPLACE |
| 5 | THE JOURNEY — 5-stage path | 5-step flow replacing 3-step How It Works | REPLACE |
| 6 | THE PRINCIPLES — 5 core values | Numbered list (Trust, Freedom, Pace, Sovereignty, Future-Proof) | NEW |
| 7 | TWO MODES — Operation vs Dev | 2-column card | NEW |
| 8 | HONEST TRADEOFFS — 3 honest costs | 3-item list | NEW |
| 9 | FOR WHO — Individuals vs Organizations | 2-column card | NEW |
| 10 | THE FUTURE — closing vision | Reworked multi-CTA with vision closing | UPDATE |

**Sections removed**: Market stats (73%/$240B/0%), 4-persona problem/solution, features grid, 3-step How It Works.

**Sections kept**: Video placeholder, Cost Comparison table, Social Proof badges, FAQ, Code Install, Footer.

### enterprise.html — Guriqo Services Alignment

Add consulting narrative sections above existing contact form:

1. **The Pattern We Keep Seeing** — AI transformations that fail
2. **Why AI Transformations Fail** — 3 cards (Change Everything, Replace vs Augment, Vendor Lock-in)
3. **The Two Rings Framework** — Fast Ring (commodity) vs Slow Ring (Guriqo's focus)
4. **The Guriqo Difference** — comparison table (Most Consultants vs Guriqo)
5. Update footer tagline with founder context

### Deferred Items

- **Video**: New video file to be provided by user (current `ai-neutrality-web.mp4` placeholder retained)
- **Stripe payment link**: User will provide at next stage
- **Comparison page**: `comparison-table.html` linking decision deferred

## Consequences

- Website messaging now mirrors pitch decks exactly — single source of truth
- 7 new sections added to index.html, 3 sections replaced, hero updated
- enterprise.html gains Guriqo consulting narrative with Two Rings Framework
- Cal.com links updated to Cal.eu (`https://cal.eu/guriqo`)
- All changes are static HTML/CSS — no build system dependency
