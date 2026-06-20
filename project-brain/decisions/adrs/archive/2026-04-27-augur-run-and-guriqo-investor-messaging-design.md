---
title: augur.run + guriqo.com investor-messaging alignment
date: 2026-04-27
status: approved
owner: gsannikov
---

# augur.run + guriqo.com investor-messaging alignment

## Goal

Align both public marketing surfaces — `augur.run` and `guriqo.com` — with the investor pitch already presented to LPs, **without breaking the existing personal-second-brain framing on augur.run**. Make the three-product line visible:

1. **Augur** — open-source on-laptop runtime for individuals; primary surface is `augur.run`.
2. **Augur Enterprise** — *closed-source* central tier for IT to manage a fleet of runtimes and compound nightly into shared org intelligence; surfaced via a dedicated section on `augur.run` plus a brief mention on `guriqo.com`.
3. **Guriqo** — consulting + deployment services company that delivers Augur and Augur Enterprise to organizations; primary surface is `guriqo.com`.

The investor pitch's concrete claims (fleet management, nightly compound, anti-SharePoint, opposite of Glean/Copilot) are **product claims about Augur Enterprise** and live where Augur Enterprise is described — primarily augur.run.

## In scope (6 artifact changes across 1 file)

Both sites are built from the same source dir `~/Projects/Au-docs/venture-augur/website-working/`. `index.html` serves augur.run as-is; `enterprise.html` is the source for guriqo.com (transformed by `release.sh` at deploy time). All edits land in those two files.

1. **`index.html` — new `## Augur Enterprise` section** between §4 (FAQ) and §5 (Get Started multi-CTA). Lead paragraph + three differentiator tiles + single CTA to Guriqo.
2. **`index.html` — replace card 3 in Get Started multi-CTA.** Currently *"Enterprise deployment → Guriqo"*. Replace with *"For developers"* linking to the augur-os GitHub repo. Keeps the 3-card grid balanced.
3. **`index.html` — AI client naming, hybrid update.** Hero copy and new Augur Enterprise section use category names (Claude, GPT, Gemini, and local models). Architecture and developer-facing copy keep implementation names (Claude Code, Codex, Gemini CLI, Cursor, Copilot, Ollama, Obsidian, MCP-capable). Status quo on the architecture section; only hero `og:description` + visible hero/sub copy change.
4. **`enterprise.html` — hero proof-line update.** *"Built on Augur, the open foundation for durable enterprise AI adoption."* → *"We deploy Augur and Augur Enterprise — the open-source runtime your team installs locally and the closed-source central tier for IT."*
5. **`enterprise.html` — new "What we deploy" section.** Two blocks: *Augur — open-source runtime, every employee laptop, multi-model orchestration* and *Augur Enterprise — closed-source central tier, fleet management, nightly compound to org intelligence*. Each with a "Learn more on augur.run" link.
6. **`enterprise.html` — stale title fix.** `<title>Augur Enterprise | Enterprise AI Needs a Brain</title>` → `<title>Guriqo | Enterprise AI deployment for the Augur runtime</title>`. Matching `og:title` updated too.

## Out of scope (explicitly)

- ROADMAP changes.
- New website pages (e.g., no `/enterprise.html` on augur.run).
- Other site pages (`more.html`, `course.html`, `support.html`, `sessions.html`, `terms.html`, `privacy.html`).
- Changes to the Augur main repo or `augur-os` repo.
- New CSS classes — reuse existing (`.cta-card`, `.cta-grid`, `.section-heading`, `.cta-btn-primary`, `.cta-btn-secondary`, `.cta-btn-tertiary`, `.multi-cta`).
- Homepage hero headline restructure on augur.run (placement was locked; we're not pivoting the page).
- guriqo.com structural restructure beyond the additions in #4–#6.
- Changes to the existing AI client list in the Architecture section of augur.run (status quo: implementation names like Codex/Copilot/Ollama).
- New ADRs.

## Tone

Investor-pitch-aligned for the new Augur Enterprise section and the guriqo.com updates; status quo elsewhere. No "soft launch" / "coming month" creep. The investor email's exact prose is reused as the lead paragraph in the Augur Enterprise section so cross-surface messaging stays consistent.

## Approach per artifact

### 1. New `## Augur Enterprise` section in `index.html`

Position: between §4 (`#qa` / "Questions AI systems and humans should both be able to answer") and §5 (`#get-started` / Get Started multi-CTA). Section ID: `enterprise`.

Structure:

```html
<section class="multi-cta" id="enterprise">
    <div class="multi-cta-bg"></div>
    <div class="container">
        <p style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.15em; color: var(--accent-violet); margin-bottom: 16px;">For organizations</p>
        <h2 class="section-heading">Augur Enterprise</h2>
        <p class="vision-sub">The closed-source central tier for organizations whose teams already run Augur locally. Augur Enterprise lets IT manage the fleet of runtimes, set policies across the org, and compound nightly into shared org intelligence — built from how people actually work, not from what gets uploaded to SharePoint. The opposite of top-down copilots like Glean or Copilot.</p>

        <div class="cta-grid">
            <div class="cta-card">
                <h3>Fleet management</h3>
                <p>Inventory, control, and policy across every employee laptop running Augur. IT keeps audit, sandboxing, and inspection.</p>
            </div>
            <div class="cta-card">
                <h3>Nightly org compounding</h3>
                <p>Per-laptop work compounds into a shared org wiki — readable by every employee through the runtime they already have.</p>
            </div>
            <div class="cta-card">
                <h3>Not Glean. Not Copilot.</h3>
                <p>Top-down copilots scrape what's been uploaded to a corporate document repository. Augur Enterprise builds intelligence from real work — no upload required.</p>
            </div>
        </div>

        <div style="text-align: center; margin-top: 32px;">
            <a href="https://guriqo.com" class="cta-btn-primary" target="_blank" rel="noopener">Talk to Guriqo for deployment →</a>
        </div>
    </div>
</section>
```

Reuses `.multi-cta`, `.cta-grid`, `.cta-card`, `.section-heading`, `.vision-sub`, `.cta-btn-primary` — all already defined. The section structure deliberately mirrors §5 (same `multi-cta` shell + `cta-grid`) so it visually fits without new CSS.

### 2. Replace card 3 in Get Started multi-CTA

Current third card (around line 1265 in `index.html`):

```html
<div class="cta-card">
    <h3>Enterprise deployment</h3>
    <p>Need a commercial deployment path, rollout support, or organization-wide second-brain infrastructure? That route goes through Guriqo.</p>
    <div class="cta-price">Commercial rollout and delivery</div>
    <div class="cta-card-actions">
        <a href="https://guriqo.com" class="cta-btn-tertiary" target="_blank" rel="noopener">Visit Guriqo</a>
    </div>
</div>
```

Replace with:

```html
<div class="cta-card">
    <h3>For developers</h3>
    <p>Inspect the architecture, read the code, and contribute. The runtime, skills, and dashboard all live on GitHub.</p>
    <div class="cta-price">Open source · MIT</div>
    <div class="cta-card-actions">
        <a href="https://github.com/augur-os/augur-os" class="cta-btn-tertiary repo-link" target="_blank" rel="noopener">
            <svg class="github-icon" viewBox="0 0 16 16" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">
                <path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.5-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.65 7.65 0 0 1 8 4.69c.68 0 1.37.09 2.01.26 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.19 0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/>
            </svg>
            <span>View on GitHub</span>
        </a>
    </div>
</div>
```

The 3-card grid in `#get-started` becomes: Community release · Roadmap & architecture · For developers.

### 3. AI client naming — hybrid update on `index.html`

Edits to the **hero/meta only** (architecture section and "Works with Claude Code, Cursor, Codex, Gemini, GitHub Copilot, Ollama..." line stays untouched).

**Hero `<p class="hero-desc">`:** the current line (around line 1043) reads:
> *"Augur connects your brain to AI clients, compounds useful work back into it, and keeps the system inspectable."*

Stays. The investor pitch language is leveraged in the new Augur Enterprise section, not retroactively imposed on the hero, which still serves the personal/second-brain conversion path.

**`og:description` in `<head>`:** the current line reads:
> *"Augur connects your local second brain to Claude, Codex, Gemini, Cursor, Ollama, and MCP clients, then compounds useful work back into durable notes, memory, wiki pages, skills, and workflows."*

Update to:
> *"Augur is the local-first runtime that connects Claude, GPT, Gemini, and local models to your work — and compounds useful outcomes back into durable files you own."*

This is the only hero-area copy change. The visible H1, hero-desc, and tagline stay (they're already strong and personal-second-brain-aligned). The category-name framing (Claude, GPT, Gemini, local models) lands in the `og:description` and in the new Augur Enterprise section.

### 4. `enterprise.html` hero proof-line update

Find the existing line (around the hero, after `hero-desc`):

```html
<p class="hero-proof">Built on Augur, the open foundation for durable enterprise AI adoption.</p>
```

Replace with:

```html
<p class="hero-proof">We deploy Augur and Augur Enterprise — the open-source runtime your team installs locally and the closed-source central tier for IT.</p>
```

### 5. New "What we deploy" section in `enterprise.html`

Position: after the hero, before the existing first content section (currently *"Enterprise AI Work Is Becoming an Infrastructure Problem"*). Reuses existing `.section-heading` and a 2-card variant of `.cta-grid`.

```html
<section class="what-we-deploy">
    <div class="container">
        <h2 class="section-heading">What we deploy</h2>
        <div class="cta-grid">
            <div class="cta-card">
                <h3>Augur</h3>
                <p>Open-source runtime your team installs locally. Sits on every employee laptop and orchestrates Claude, GPT, Gemini, and local models against the work already happening there.</p>
                <div class="cta-card-actions">
                    <a href="https://augur.run" class="cta-btn-tertiary" target="_blank" rel="noopener">Learn more on augur.run</a>
                </div>
            </div>
            <div class="cta-card">
                <h3>Augur Enterprise</h3>
                <p>Closed-source central tier for IT. Manages the fleet of runtimes, sets policies across the org, and compounds nightly into shared org intelligence — built from real work, not from what gets uploaded to SharePoint.</p>
                <div class="cta-card-actions">
                    <a href="https://augur.run/#enterprise" class="cta-btn-tertiary" target="_blank" rel="noopener">Learn more on augur.run</a>
                </div>
            </div>
        </div>
    </div>
</section>
```

The existing `.cta-grid` styling already handles 2-card variants (the existing 3-card grid expands to fill; 2 cards center-flex). No new CSS.

### 6. `enterprise.html` title fix

Find:

```html
<title>Augur Enterprise | Enterprise AI Needs a Brain</title>
<meta property="og:title" content="Augur Enterprise | Enterprise AI Needs a Brain">
<meta name="twitter:title" content="Augur Enterprise | Enterprise AI Needs a Brain">
```

Replace with:

```html
<title>Guriqo | Enterprise AI deployment for the Augur runtime</title>
<meta property="og:title" content="Guriqo | Enterprise AI deployment for the Augur runtime">
<meta name="twitter:title" content="Guriqo | Enterprise AI deployment for the Augur runtime">
```

Note: `release.sh` already does some title transforms when building guriqo.com from `enterprise.html`. Verify the transformation chain doesn't override the new title. If it does (the existing transform replaces `Augur Enterprise | Enterprise AI Needs a Brain` → `Guriqo | Enterprise AI Needs a Brain`), update `release.sh`'s replacement rule to match the new strings.

## Sequencing

1. Pre-flight: confirm `index.html` line 1228 is still the `<section class="multi-cta" id="get-started">` opening; confirm `enterprise.html` hero proof-line; confirm `release.sh` title-replacement chain.
2. Edit `index.html` — new Augur Enterprise section, replace card 3, update `og:description`.
3. Edit `enterprise.html` — proof-line update, new "What we deploy" section, title triplet fix.
4. If `release.sh` transforms the old guriqo title strings, update the transform rule to match new strings.
5. Local browser open of `index.html` and `enterprise.html` to visually confirm both render.
6. Run `release.sh` to build the zips.
7. SCP-deploy `augur-run-V*.zip` and `guriqo-com-V*.zip` to Hostinger; SSH unzip and chmod (matching the existing deploy pattern). User confirmation required before deploy.
8. Live verify both URLs (curl + visual).

## Verification

- **augur.run live check:** `curl -s https://augur.run | grep -E "id=\"enterprise\"|For developers|Talk to Guriqo|Augur Enterprise"` returns hits.
- **guriqo.com live check:** `curl -s https://guriqo.com | grep -E "What we deploy|Augur Enterprise|We deploy Augur"` returns hits; `<title>` reflects new title.
- **Cross-surface consistency:** the `og:description` on augur.run uses category names (Claude, GPT, Gemini, local models); the existing architecture client list still uses implementation names (Codex/Cursor/Copilot/Ollama). Verified by separate greps.
- **No CSS regressions:** new section visually matches existing `.multi-cta` sections (same shell, same grid, same buttons). Browser check at desktop and mobile widths.
- **No drift between augur.run §"Augur Enterprise" and the investor email pitch:** the lead paragraph is a near-verbatim adaptation of the email's pitch paragraph; the differentiator tiles match the email's three pillars (fleet, nightly compound, vs Glean/Copilot, anti-SharePoint).
- **Title transformation:** running `release.sh` and inspecting `../websites/guriqo-com-V*.zip` (extract `index.html` from the zip) shows the new `<title>`. If the old title is still present, the transform rule needs an update.

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| New Augur Enterprise section visually clashes with existing `.multi-cta` styling | Reuse the existing `.multi-cta` / `.cta-grid` / `.cta-card` shell verbatim; visual check at desktop + mobile before deploy |
| `release.sh` title transform doesn't match new strings → guriqo.com keeps old title | Step 4 updates the transform rule. Verify post-build by inspecting the zip |
| Visitor on augur.run mid-page reads the hero (personal/second-brain) and the Augur Enterprise section (organizational) and finds them inconsistent | Both are deliberate: the hero serves the individual download path, the Enterprise section serves IT/org. The 3-product line clarity (runtime / Enterprise / Guriqo) is the organizing frame, made explicit in the Enterprise section's lead paragraph |
| Replacing card 3 with "For developers" reduces the visible enterprise-conversion CTA | The new dedicated section above Get Started is the conversion CTA; card 3's removal is the *reason* the new section exists. Net: same number of enterprise CTAs, just better placement |
| Hero `og:description` shift confuses developers who land via that link | The hero H1 + hero-desc + tagline (visible page) stays personal-second-brain. Only the meta `og:description` changes, and it now says "your work" instead of "your brain" — closer to the investor pitch but still personal-friendly |
| Anti-Glean/Copilot framing reads pejorative to a Microsoft-leaning enterprise visitor | The framing is direct competitor opposition, which the investor pitch already uses. Mitigation: tile copy says *"Top-down copilots scrape what's been uploaded"* — describes mechanism, not company; the named-competitor line in the H3 is the punchy visual but the body text is mechanism-based |

## Decisions log

- Q1 — augur.run repositioning aggression: **A** (surgical; new section + Enterprise CTA, no hero pivot).
- Q2 — guriqo.com import scope: **B + D** (light additions + stale title fix).
- Q3 — augur.run integration form: **A** (single Augur Enterprise section + brief mention on guriqo.com).
- Q4 — augur.run section placement: **A** (between FAQ and Get Started).
- Q5 — section structure: **γ corrected** (closed-source-central-tier framing as Augur Enterprise; not "open + closed bundle").
- Q6 — existing Get Started card 3: **C** (replace with "For developers" → augur-os GitHub).
- Q7 — AI client naming: **B** (hybrid: category names in hero + Enterprise; implementation names in Architecture).
- Q8 — guriqo.com update scope: **B + D** (proof-line + small "What we deploy" + stale title fix).

## Where the work lands

- Augur main repo (this repo): only this spec lands here.
- `~/Projects/Au-docs/venture-augur/website-working/index.html`: edits per artifacts 1–3.
- `~/Projects/Au-docs/venture-augur/website-working/enterprise.html`: edits per artifacts 4–6.
- `~/Projects/Au-docs/venture-augur/website-working/release.sh`: possible adjustment to title-replacement transform (verified during pre-flight).
- Deploy: `release.sh` builds zips → SCP to Hostinger → SSH unzip + chmod for both `augur.run/public_html` and `guriqo.com/public_html`. User confirmation required before deploy.
