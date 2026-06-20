---
title: Investor-prep — augur.run release-plan CTAs and augur-os architecture refresh
date: 2026-04-27
status: approved
owner: gsannikov
---

# Investor-prep — augur.run release-plan CTAs and augur-os architecture refresh

## Goal

Close two specific credibility gaps before the imminent investor review:

1. **Release-credibility gap** on augur.run — three homepage CTAs labeled "Explore on GitHub" point at the repo root and the surrounding copy uses vague phrases like *"the coming month."* An investor reading this sees no concrete release plan.
2. **Architecture-depth gap** in the public `augur-os` repo — `architecture-overview.md` was written at soft-launch and lags the last ~30 days of ADRs (wiki/ingest, browse redesign, IDE registry, Gemini extension, Windows hardening, MVP staged releases, security autoloop). An investor going one click deeper finds a story that's thinner than the actual product.

The fix is targeted and small: rewrite the three CTAs to point at a real roadmap; rewrite that roadmap so it's status-honest and verifiable; rewrite the public architecture overview around the current product with three Mermaid diagrams that include the security autoloop as a visible release gate; reconcile two adjacent docs so they don't contradict.

## In scope (6 artifacts)

1. `~/Projects/Au-docs/venture-augur/website-working/index.html` — three CTA placements rewritten and re-pointed at the roadmap; one section preamble line updated.
2. `~/Projects/augur-os/ROADMAP.md` — full rewrite to a phased structure with `[shipped]` / `[in-flight]` / `[planned]` markers grounded in real ADRs and PRs.
3. `~/Projects/augur-os/docs/architecture-overview.md` — full rewrite. 3-layer model stays as the spine. Six named subsystems become first-class. Three Mermaid diagrams embedded.
4. `~/Projects/augur-os/docs/architecture-mcp-gateway.md` — terminology polish only. Align subsystem names and three-type skills taxonomy with the new overview; reconcile against the overview's sequence diagram so they don't contradict. Not a full rewrite.
5. `~/Projects/augur-os/README.md` — ASCII architecture block conditionally refreshed. Read it; if it visibly contradicts the new overview (omits autoloops, miscounts skills, names subsystems that no longer exist), update to a simplified version using the same language. If already compatible at its level of abstraction, leave it. Default bias: light touch, hard 15-minute cap.
6. **Three Mermaid diagrams** embedded inside artifact #3, called out separately because they are the centerpiece of the architecture refresh.

## Out of scope (explicitly)

- New website pages (no `/release-plan.html`). Roadmap lives on GitHub.
- Other site pages: `more.html`, `enterprise.html`, `course.html`, `support.html`, `sessions.html`, `privacy.html`, `terms.html`.
- Hero headline, hero sub-headline, the architecture image, the waitlist form, the Guriqo card, the footer.
- Any code, config, or skill changes in the main `Augur` repo.
- Per-skill or per-hub deep dives.
- Security threat model. The security autoloop subsystem is referenced at architecture level only.
- Performance benchmarks or capacity planning.
- Marketing copy on guriqo.com.
- Revenue, pricing, or business-model commitments in the public ROADMAP.
- Personnel, team size, fundraising state.

## Approach per artifact

### 1. `index.html` — homepage CTA rewrite

Three placements rewritten in place. All point at the roadmap. No new pages, no new sections, no new CSS classes — reuse existing styling.

**Top nav button** (around line 1066–1070):
- Label: `Explore on GitHub` → `Roadmap`.
- Link: `https://github.com/augur-os/augur-os` → `https://github.com/augur-os/augur-os/blob/main/ROADMAP.md`.
- Keep GitHub icon SVG.

**Hero secondary CTA** (around line 1089–1093):
- Label: `Explore on GitHub` → `See the roadmap`.
- Link: same as nav.
- Keep GitHub icon, keep `cta-btn-secondary` styling, keep position next to the waitlist.

**"Get Started" card #2** (around line 1251–1262), currently titled *"Explore architecture"*:
- Title: `Explore architecture` → `Roadmap & architecture`.
- Body copy replaced with: *"The roadmap shows what's shipped, what's in flight, and what's next. The architecture overview shows how the layers fit together."*
- Replace the single "Explore on GitHub" button with two compact links inside the existing `cta-card-actions` container:
  - `Read the roadmap` → `ROADMAP.md`.
  - `Read the architecture` → `docs/architecture-overview.md`.
- Keep the `Available now` price label.

**Section preamble** (around line 1235):
- *"GitHub shows the open-source architecture today. The first community release lands in the coming month."*
- → *"The public roadmap shows what's shipped, what's in flight, and what's next. MVP release lands May 2026."*

### 2. `ROADMAP.md` — full rewrite

Structure:

```markdown
# Roadmap

One-paragraph framing. What Augur is, what soft launch means today,
how to read the page (status markers, dates as targets not commitments).

## Status legend
- [shipped]    — landed in main, behavior verified
- [in-flight]  — actively being built, ADR or PR open
- [planned]    — scoped, not started

## Phase 1 — Soft launch (April 2026, now)
Theme: prove the harness on macOS, finish the architecture for Windows.

- [shipped]   Native macOS: install path, dashboard, MCP gateway, 200+ skills
- [shipped]   MCP-native multi-client: Claude Code, Codex, Cursor, Gemini, Copilot, Ollama
- [shipped]   Local dashboard at localhost:3000
- [shipped]   Wiki compiler (concept-first) and ingest pipeline   <!-- ADR-559/560/561/564 -->
- [shipped]   Browse workbench redesign + skills tab               <!-- ADR-540/541/554 -->
- [shipped]   Security autoloop (S1–S5 + Tank CLI)                 <!-- loop-security -->
- [shipped]   Gemini extension support                             <!-- ADR-553 -->
- [shipped]   Runtime IDE registry                                 <!-- ADR-562 -->
- [in-flight] Vault user surfaces (phase 1)                        <!-- 2026-04-23 plan -->
- [in-flight] Windows native: architecture done, validation pending <!-- ADR-550 -->
- [in-flight] MVP staged release payloads                          <!-- ADR-557 -->

## Phase 2 — MVP release (May 2026)
Theme: tighten validation, ship a version a non-developer can install.

- [planned]  npx-based one-command install on macOS
- [planned]  Windows GA after validation passes
- [planned]  Open-source brain/inbox/wiki insights surface         <!-- ADR-564 -->
- [planned]  Sync managed-output purge for clean re-installs       <!-- ADR-558 -->
- [planned]  Documented upgrade and rollback paths

## Phase 3 — Monthly cadence (June 2026 onward)
Theme: predictable shipping, fold validated platforms into the public story.

- [planned]  Monthly release train
- [planned]  Public Windows support claim once validation is green
- [planned]  Skill group and release enablement                    <!-- ADR-551 -->
- [planned]  Continued autoloop expansion (security, ops, repo)

## How to verify
Each item links to its ADR or implementation plan. ADRs live in the
private architecture repo; PRs and CI runs are visible on GitHub.

## Enterprise and commercial
Commercial deployment, rollout support, and organization-wide infrastructure
go through Guriqo. See https://guriqo.com.
```

Rules for the rewrite:
- Every `[shipped]` claim verified against a real merged PR or ADR before commit. Reconcile each item against `git log` on the main `Augur` repo.
- HTML comments hold ADR/plan IDs so the file is grep-friendly without cluttering rendered output.
- No per-feature dates. Phase-level dates only.
- `[in-flight]` items must have an open plan or visible commit activity within the last 14 days, otherwise demote to `[planned]`.
- Tone: confident on shipped work, hedged only on Windows validation.

### 3. `architecture-overview.md` — full rewrite

Document structure:

```
# Augur Architecture

Lead paragraph: what Augur is, what the doc is for, who it's for.
Confident voice. One sentence on local-first / not-an-LLM-wrapper.

## At a glance
[Diagram 1 — Hero system diagram, Mermaid]
2–3 sentences naming each subsystem the diagram shows.

## The three layers
- Reasoning — model-agnostic clients
- Execution — skills + MCP gateway
- Ops — approvals, autoloops, audit
Tightened version of the existing 3-layer essay. This is the spine.

## How an action flows
[Diagram 2 — MCP gateway sequence, Mermaid]
2–3 sentences. Calls out: dashboard click and agent command share this path.

## Subsystems
Six named subsections, ~100–150 words each:
  1. Skills — three-type taxonomy (User / Project / Client)
  2. Wiki and ingest — concept-first compiler, source cards, ambient ingest
  3. Browse — skills tab, client inventory, freshness
  4. Multi-client surfaces — Claude/Codex/Gemini/Cursor/Copilot/Ollama,
     runtime IDE registry, Gemini extension support
  5. Autoloops — with the security autoloop called out as the lead example
     (S1 prompt-injection, S2 secrets, S3 static analysis, S4 integrity,
     S5 permissions/policy, Tank CLI)
  6. Release and lifecycle — staged payloads, managed-output purge,
     supported-client state

## Release and lifecycle
[Diagram 3 — Release pipeline, Mermaid]
Soft launch → MVP (May 2026) → monthly cadence (June 2026+).
Security autoloop and other autoloops shown as quality gates.

## Human-in-the-loop and safety
Tightened. Mentions the security autoloop as the automated half of safety,
complementing approval gates and allowlists.

## Repository mapping
Refreshed table for current paths and current subsystems.

## Where to go next
Links to ROADMAP.md, architecture-mcp-gateway.md, getting-started.md,
ADR index (private), session log on augur.run/sessions.html.
```

#### Skills subsystem — three-type taxonomy

Lead the Skills section with the three types, not the count:

- **User skills** live in the user's vault and are private to them (per ADR-563 vault-owned user skills, pages, and drafts).
- **Project skills** are the shared canonical set, versioned with the repo (`skills/` in `augur-os` / `Augur`).
- **Client skills** are managed exports tailored to each AI client surface (`.cursor/skills/`, `.gemini/skills/`, `.codex/skills/`, `~/.agents/skills/augur/`).

Total count ("200+") moves into a parenthetical in prose. Not a label on the diagram.

### Diagrams — three Mermaid blocks

All three Mermaid, embedded inline. No PNGs, no external tools. GitHub renders them natively. Each diagram answers exactly one investor question.

#### Diagram 1 — Hero system diagram

Top-down `flowchart`. Shows AI clients consuming the harness, MCP gateway as the single execution surface, ops cross-cutting.

- **Top tier (Reasoning):** Claude · Codex · Gemini · Cursor · Copilot · Ollama. All arrows down to MCP gateway.
- **Middle tier (Execution):** MCP gateway as a single named node. Below it, a row of named subsystem nodes:
  - `Skills` cluster of three: `User skills (vault)`, `Project skills (shared)`, `Client skills (exports)`.
  - `Wiki + Ingest`.
  - `Browse`.
  - `Vault (local files)`.
- **Right rail (Ops):** `Autoloops` (with `Security autoloop` as a sub-label), `Approvals`, `Audit log`. Dashed arrows from these into the gateway.
- **Bottom (Surfaces):** `Local dashboard` and `AI client UIs` both pointing into the gateway, signaling parity.

#### Diagram 2 — MCP gateway sequence

`sequenceDiagram` with five participants: `User`, `Client (Dashboard or AI)`, `MCP gateway`, `Skill`, `Vault + audit`.

Flow:
1. User → Client: intent (click or prompt).
2. Client → Gateway: tool call.
3. Gateway → Skill: dispatch (with policy check noted in a `Note over Gateway`).
4. Skill → Vault: read/write files.
5. Skill → Gateway: result.
6. Gateway → Vault: audit entry.
7. Gateway → Client → User: response.

A `Note over Client, Gateway` calls out: *"Same path whether the user clicked a dashboard button or asked an AI agent."* This is the single most investor-relevant claim — that GUI and agent share one execution surface. **This diagram is canonical for the cross-component sequence**; the gateway doc's own sequence diagram defers to it for the high-level flow.

#### Diagram 3 — Release / lifecycle pipeline

Left-to-right `flowchart`:

`Soft launch (now)` → `MVP (May 2026)` → `Monthly cadence (Jun 2026+)` → `Windows GA`

Below the main track, a parallel "quality gates" lane showing autoloops feeding each release cut:
- `Security autoloop` (S1–S5 + Tank CLI).
- `Test autoloop`.
- `Repo / dependency autoloop`.

Arrows from each gate into the release nodes. This pays off the security autoloop being a first-class subsystem — a concrete answer to *"how do you ship safely?"*

### 4. `architecture-mcp-gateway.md` — polish pass

Not a rewrite. Targeted alignment.

- Subsystem names match the new overview. Three-type skills taxonomy referenced where it matters.
- Security autoloop referenced at the right level of abstraction.
- The doc's existing sequence diagram, if any, is reconciled against Diagram 2 in the overview. The overview's diagram is canonical for the cross-component sequence; the gateway doc covers gateway-internal detail only and links out to Diagram 2 for the high-level flow.
- Trim or update only what's needed.

### 5. `README.md` — conditional ASCII refresh

- Read the existing ASCII architecture block.
- If it visibly contradicts the new overview (omits autoloops layer, miscounts skills, names subsystems that no longer exist, etc.), update to a simplified version using the same three-layer language and the same subsystem names.
- If already compatible at its level of abstraction, leave it untouched.
- Hard 15-minute cap. Default bias: light touch.

## Sequencing

Site path first (the investor's first-touch path), architecture second.

1. **ROADMAP.md rewrite.** Verify each `[shipped]` claim against `git log` and the ADR list before commit. Commit and push to `augur-os` remote.
2. **`index.html` CTAs.** Three placements rewritten, section preamble updated. Open locally in browser, confirm rendering, deploy via existing `release.sh` SCP pipeline only after step 1 has been pushed (otherwise links 404).
3. **`architecture-overview.md` rewrite + 3 Mermaid diagrams.** Largest piece of work. If time runs short, this is the artifact that ships "v1 tonight, polish tomorrow morning" — the site path is already airtight by then.
4. **`architecture-mcp-gateway.md` polish pass.** Terminology only. Reconcile against the new overview.
5. **`README.md` ASCII check.** Conditional refresh, hard 15-minute cap.
6. **Cross-link pass + Mermaid render verification on github.com.**

## Verification

- **ROADMAP:** every `[shipped]` item reconciled against a real merged PR or ADR. `[in-flight]` items have activity in the last 14 days, otherwise demoted to `[planned]`.
- **Site:** open `index.html` in a real browser, click each of the three rewritten CTAs, confirm they reach the new ROADMAP and architecture URLs (no 404, no broken anchor). Mobile view checked too — the get-started card now has two links instead of one button, layout must still hold.
- **Architecture doc:** all three Mermaid diagrams render on github.com after push. Mermaid silently fails on subtle syntax errors, so this check is non-optional.
- **Cross-doc consistency:** grep `architecture-overview.md` and `architecture-mcp-gateway.md` for subsystem names — must match. README ASCII (if changed) must use the same three-layer language and same subsystem names.
- **Tone:** every claim in all artifacts hedged only where genuinely uncertain (Windows validation). No "soft launch" or "coming month" phrasing survives in user-facing copy.
- **No drift between artifacts:** site, ROADMAP, and architecture doc all reference the same May 2026 MVP date and the same subsystem names. A reader bouncing between them sees one consistent story.

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| Investor reads ROADMAP, opens GitHub, finds a `[shipped]` claim that isn't actually shipped | Hard verification gate; reconcile each item against `git log` before commit |
| Mermaid diagram renders locally but breaks on github.com | Push, view raw rendered file on github.com, fix before claiming done |
| Site deploys before ROADMAP is pushed → CTAs 404 | Strict step order: ROADMAP push first, site deploy second |
| Time runs out, architecture doc only partially rewritten | Site path is already airtight by then; ship architecture v1, polish next pass |
| New labels or copy create CSS layout breakage on the site | Visual check in real browser before deploy; reuse only existing CSS classes |
| Public ROADMAP item the user later wants to retract | All items are phase-level dated only (no per-feature dates); status markers can be edited freely |
| Security autoloop referenced but not visible to a curious investor reading code | Loop-security work landed today (commits in main `Augur` repo); references in the architecture doc must match real files/skills, no fictional structure |
| `architecture-mcp-gateway.md` polish accidentally contradicts the overview because two diagrams cover overlapping ground | Overview's Diagram 2 designated canonical for cross-component sequence; gateway doc covers gateway-internal detail only and links out |
| README ASCII change scope-creeps into a full rewrite | Conditional rule ("only if visibly contradicts") and hard 15-minute cap |

## Decisions log

- Q1 — investor framing: **C** (split: site = release-credibility; repo = architecture-depth).
- Q2 — release plan location: **B** (rewrite homepage CTAs, beef up ROADMAP.md; no new website page).
- Q3 — ROADMAP concreteness: **B** (phases + scope + status markers, no per-feature dates).
- Q4 — homepage CTA scope: **A** (surgical; consistent "Roadmap" labeling across all three placements).
- Q5 — architecture refresh scope: **C** (full rewrite of architecture-overview.md with subsystems visible).
- Q6 — diagrams: **B** (three Mermaid diagrams), plus security autoloop as first-class subsystem and release gate.
- Q7 — tone: **B** (confident but factual; hedge only where genuinely uncertain).
- Q8 — sequencing: **A** (site path first, architecture second).
- Skills subsystem rendered as three-type taxonomy (User / Project / Client), not "200+".
- Architecture-mcp-gateway.md polish and README ASCII refresh added to scope (originally out of scope).

## Where the work lands

- Augur main repo (this repo): no changes. Only the spec lands here.
- `~/Projects/Au-docs/venture-augur/website-working/`: `index.html` edits.
- `~/Projects/augur-os/`: `ROADMAP.md`, `docs/architecture-overview.md`, `docs/architecture-mcp-gateway.md`, possibly `README.md`.
- Deployment: site via existing `release.sh` SCP path; augur-os via `git push` to `augur-os` remote.
