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

# ADR-594: Augur Run and Guriqo Investor Messaging

## Context

The two public marketing surfaces — `augur.run` (personal/second-brain) and `guriqo.com` (consulting + deployment) — were not aligned with the three-product line presented to LPs:

1. **Augur** — open-source on-laptop runtime for individuals (primary surface: augur.run).
2. **Augur Enterprise** — closed-source central tier for IT to manage a fleet of runtimes and compound nightly into shared org intelligence.
3. **Guriqo** — consulting/deployment company that delivers Augur and Augur Enterprise (primary surface: guriqo.com).

Concrete investor claims (fleet management, nightly compound, anti-SharePoint, opposite of Glean/Copilot) are product claims about Augur Enterprise and need a visible home. The `enterprise.html` source (which is transformed by `release.sh` into guriqo.com) had a stale title, an outdated proof line, and no "what we deploy" framing.

The personal-second-brain framing on augur.run must remain intact — no hero pivot. Both surfaces are built from the same source dir (`~/Projects/Au-docs/venture-augur/website-working/`), which is not a git repo; deploy is `release.sh` → SCP + SSH unzip to Hostinger.

## Decision

Make six changes across two HTML files and one deploy script:

`index.html` (augur.run):
1. Insert a new `## Augur Enterprise` section between FAQ and Get Started, with three differentiator tiles (fleet management; nightly org compounding; not Glean/not Copilot) and a single CTA to Guriqo. Reuses existing `.multi-cta`, `.cta-grid`, `.cta-card` classes — no new CSS.
2. Replace the third Get Started card ("Enterprise deployment → Guriqo") with "For developers → GitHub". The new dedicated Enterprise section is the conversion CTA.
3. Update `og:description` to category-name framing ("Claude, GPT, Gemini, and local models"). Hero H1/desc/tagline stay personal-second-brain.

`enterprise.html` (guriqo.com source):
4. Update hero proof line to "We deploy Augur and Augur Enterprise…".
5. Insert a "What we deploy" section after the hero with two product cards (Augur · Augur Enterprise) linking to augur.run.
6. Fix the stale `<title>` triplet: `Guriqo | Enterprise AI deployment for the Augur runtime`.

`release.sh`:
7. Remove the three obsolete title-transform tuples that targeted the old `Augur Enterprise | Enterprise AI Needs a Brain` strings — they would silently fail to match after the source title fix.

Deploy is gated on explicit user confirmation before SCP+SSH.

## Consequences

### Positive
- Three-product line is visible on both surfaces.
- Investor pitch claims (fleet, nightly compound, anti-SharePoint, anti-Glean/Copilot) live where Augur Enterprise is described.
- guriqo.com browser tab title and hero proof line stop misrepresenting the company.
- `release.sh` no longer carries dead transform rules.

### Negative
- Anti-Glean/Copilot framing reads pejorative to a Microsoft-leaning enterprise visitor; mitigated by mechanism-based body copy ("Top-down copilots scrape what's been uploaded").
- A visitor on augur.run who reads both hero (personal) and Enterprise section (organizational) sees two different audiences — by design.

### Neutral
- No CSS changes; `.multi-cta`/`.cta-grid` already handle 2- and 3-card variants.
- ROADMAP, other site pages (more.html, course.html, support.html, sessions.html, terms.html, privacy.html), Augur main repo, and augur-os repo are untouched.

## Alternatives Considered

### Alternative 1: Aggressive augur.run repositioning (hero pivot)
Rejected: hero serves the personal/second-brain conversion path and is already strong; surgical addition is sufficient.

### Alternative 2: Keep card 3 as "Enterprise deployment → Guriqo"
Rejected: the new dedicated Enterprise section above Get Started is the better conversion CTA; net same number of enterprise CTAs but better placement.

### Alternative 3: Open + closed bundle framing for Augur Enterprise
Rejected: closed-source-central-tier framing matches the investor pitch and is honest about what Augur Enterprise actually is.

## References
- Plan: docs/superpowers/plans/2026-04-27-augur-run-and-guriqo-investor-messaging.md
- Spec: docs/superpowers/specs/2026-04-27-augur-run-and-guriqo-investor-messaging-design.md
