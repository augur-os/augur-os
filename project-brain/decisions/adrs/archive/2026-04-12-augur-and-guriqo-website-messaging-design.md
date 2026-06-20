# Augur And Guriqo Website Messaging Design

**Date:** 2026-04-12  
**Status:** Approved for spec writing, pending final user review  
**Surfaces:** `augur.run`, `guriqo.com` / `enterprise.html`  
**Goal:** Refresh both website narratives to reflect Augur's latest product focus without making `augur.run` feel like a new site to returning visitors.

## Summary

The websites should stop trying to carry one blended message for every audience.

- `augur.run` remains the primary product surface for personal and prosumer users.
- `guriqo.com` becomes the enterprise translation layer for deployment, transformation, and organizational adoption.

The core product update behind both sites is that Augur is no longer best described as only a local second-brain shell or local AI control center. Its strongest new story is now:

1. it compounds knowledge into a maintained wiki layer
2. it maintains itself through autoloops
3. it stays understandable through browse and transparency
4. it can start from the files and folders users already have

The design constraint is equally important: existing visitors should feel that Augur has matured, not that it has been repositioned into an unfamiliar product.

## Positioning Split

### Augur

**Audience:** personal and prosumer users who want ownership, compounding, and calm maintenance without heavy operational overhead.

**Role:** product-led homepage and public product explanation.

**Primary framing:**

> Build your second brain on your machine.

This remains the best top-level anchor because it is already familiar, legible, and broad enough to hold the newer product story.

**What changes:** the sections directly under the hero should now explain why this second brain is materially more capable than before.

### Guriqo

**Audience:** enterprise leaders, internal champions, and teams evaluating how to deploy AI in real workflows without creating a new control dependency.

**Role:** deployment and transformation site.

**Primary framing:**

> Transform AI work from the laptop up, not from the cloud down.

This is the clearest articulation of the enterprise story:

- transformation starts where work actually happens
- adoption becomes real inside existing worker tools and laptops
- systems scale upward from working local practice
- the company avoids replacing one dependency with another vendor or aggregator layer

## Augur Homepage Strategy

### Core Decision

Do not rebrand the page around anti-vendor language or around the term "LLM wiki" alone.

Instead:

- keep the hero anchored in the familiar second-brain identity
- use the hero subhead and first sections to explain the new compounding model
- preserve the overall visual structure and page rhythm wherever possible

This approach preserves continuity for returning visitors while making the newest product truth much more legible.

### Hero

**Recommended headline direction:**

> Build your second brain on your machine

**Recommended subhead direction:**

Augur turns your notes, documents, skills, pages, and sessions into a maintained knowledge system that keeps getting better as you use it.

**Recommended support line / badge logic:**

- wiki compounding
- background autoloops
- full transparency

The hero should not try to teach architecture. It should establish three ideas fast:

- this is your second brain
- it compounds
- it stays understandable

### Augur Section Order

The top half of the page should be reordered to reflect the strongest new product narrative.

#### 1. Hero

Keep the current identity anchor and visual familiarity.

#### 2. Wiki Compounding Section

**Purpose:** explain the strongest new differentiator.

**Recommended headline direction:**

> Your second brain should compound, not just store

This section should explain that Augur does not merely accumulate files, notes, and tools. It continuously turns scattered inputs into a maintained knowledge layer.

The user-facing point is:

- not raw storage
- not passive RAG
- not disconnected notes
- but synthesized, maintained knowledge

The section should talk about:

- notes
- documents
- skills
- pages
- sessions
- decisions

without descending into implementation detail.

#### 3. Autoloops Section

**Purpose:** answer the fear that a compounding second brain becomes another thing the user must maintain.

**Recommended headline direction:**

> Automation that runs on your terms

**Required message emphasis:**

- autoloops do not require a mandatory Augur cloud
- autoloops do not require a mandatory API key
- autoloops do not require a third-party orchestration layer
- autoloops can run with the user's own tools, local or remote

This is not merely a convenience section. It is an ownership section.

The emotional promise is:

> the system can maintain itself without asking you to surrender the maintenance layer to another dependency.

The copy should emphasize:

- calm
- reduced babysitting
- local or remote execution flexibility
- no mandatory middle layer

Avoid overemphasizing internal loop counts or daemon mechanics.

#### 4. Transparency / Browse Section

**Purpose:** resolve the trust problem created by a system that compounds and automates.

**Recommended headline direction:**

> Understand it before you depend on it

This section should frame browse and transparency as a trust feature, not a developer feature.

The user-facing promise is:

- you can inspect the system
- you can understand what exists
- you can see how things connect
- the second brain does not become opaque as it grows

The message is not "debugability." The message is legibility.

#### 5. File And Folder Ingest Section

**Purpose:** lower the perceived effort to get started.

**Recommended headline direction:**

> Start with the files and folders you already have

This section should explain that users do not need a perfect migration or a brand-new app discipline before getting value. They can drop in raw material and let Augur consume, route, and enrich it.

This is an onboarding hook, not the lead differentiator, which is why it should appear after compounding, autoloops, and transparency.

#### 6. What You Can Do

Keep the concrete capabilities section, but reorder it so it echoes the new hierarchy:

1. bring in existing files and folders
2. compound knowledge over time
3. expose skills to connected AI clients
4. operate across local and external workflows
5. create workflows while keeping control
6. build local apps on top of the system

#### 7. Local-First / No Cloud

Keep this section, but shorten and sharpen it.

It should reinforce:

- no mandatory cloud
- no mandatory API key
- no mandatory middle layer

This section should support the story already established above, not restart the product explanation from a manifesto angle.

#### 8. CTA Layer

Keep the overall CTA structure familiar.

Recommended role split:

- primary: start using Augur / join waitlist / book session
- secondary: explore Augur OS on GitHub
- tertiary: enterprise rollout via Guriqo

This keeps `augur.run` personal/prosumer-first while still handing off enterprise intent cleanly.

## Why This Augur Direction Wins

### Pros

- strongest continuity with the existing site
- keeps the current second-brain identity intact
- surfaces the newest product truth without a visible rebrand
- better for personal/prosumer resonance than a vendor-lock-in-first homepage
- turns recent product work into a coherent narrative rather than additional feature clutter

### Cons

- the hero itself remains less differentiated than a more aggressive feature-led headline
- the wiki section must be worded carefully to stay legible to new visitors
- some existing sections may need trimming to avoid a long or repetitive page

### Rejected Alternatives

#### Compounding-First Hero

Rejected as the main Augur headline because it is highly differentiated but less instantly legible to cold traffic and more likely to make the site feel rewritten.

#### Vendor-Lock-In-First Hero

Rejected as the main Augur headline because it is sharp but too defensive for a primarily personal/prosumer product surface. It works better as a supporting theme and as a stronger enterprise bridge inside Guriqo.

## Guriqo Strategy

### Core Decision

Guriqo should not merely be framed as "enterprise deployment for Augur."

That wording is too generic and undersells the real insight:

- top-down cloud-first AI transformation often fails
- real adoption happens where work actually happens
- the enterprise needs a control layer it owns and understands
- that transformation should begin from workers' laptops and spread upward

### Guriqo Main Thesis

> Transform AI work from the laptop up, not from the cloud down

This is the recommended enterprise lead because it combines:

- deployment motion
- adoption logic
- architecture logic
- anti-dependency positioning

### Guriqo Section Order

#### 1. Hero

Lead with laptop-up transformation.

#### 2. Failure Pattern Section

Explain why cloud-down AI transformation fails:

- forced platform adoption
- workflow redesign before workflow proof
- workers asked to leave the tools they already use
- leadership buying systems that never become real daily practice

#### 3. Dependency Section

This section should explicitly cover both:

- single-vendor dependency
- third-party aggregator dependency

The message should be:

> the enterprise should not solve one lock-in problem by introducing a new external control point for models, pricing, workflows, memory, and orchestration.

This is a key differentiator for Guriqo.

#### 4. Bottom-Up Deployment Section

This should be the heart of the page.

The message should emphasize:

- transformation starts on workers' laptops
- it begins inside existing tools and real workflows
- working patterns are proven locally first
- the organization scales what works upward

Important nuance:

This is not "everyone improvises their own stack."
It is:

> working systems emerge where the work happens, then scale with structure.

#### 5. Augur As Control Layer Section

Explain Augur as the owned and inspectable control layer:

- local where it matters
- shareable where useful
- understandable by the organization
- not trapped in a provider or aggregator platform

#### 6. Why Guriqo Section

Position Guriqo as the deployment and transfer partner that:

- identifies where bottom-up deployment should start
- makes the first workflows real
- turns local working patterns into durable team systems
- leaves the organization with owned capability instead of permanent dependence

## Why This Guriqo Direction Wins

### Pros

- more differentiated than generic AI consulting language
- more concrete than a broad anti-vendor message alone
- aligns tightly with the existing "bottom-up, not top-down" thread already present on the enterprise page
- makes the anti-aggregator position legible without making it the entire brand
- creates a clean handoff from Augur personal/prosumer to Guriqo enterprise

### Cons

- requires careful wording to avoid sounding anti-IT or anti-cloud in a simplistic way
- needs operational examples so it stays grounded and not purely conceptual

### Rejected Alternatives

#### Vendor-Lock-In As Sole Lead

Rejected as the full Guriqo strategy because it is directionally right but too familiar and not specific enough.

#### Pure Control-Layer Architecture Lead

Rejected as the full Guriqo hero because it is strategically correct but too abstract on first contact. "Laptop up, not cloud down" is more concrete and human.

## Final Recommendation

### Augur

Keep the current identity anchor and redesign the message hierarchy around:

1. compounding
2. autoloops without mandatory dependency
3. transparency
4. easy ingest

This is a refinement, not a reinvention.

### Guriqo

Lead hard on bottom-up transformation:

1. laptop-up adoption
2. failure of cloud-down mandates
3. vendor and aggregator dependency risk
4. Augur as owned control layer
5. Guriqo as rollout and transfer partner

This is a sharper enterprise story than the current page and aligns directly with the latest product and consulting stance.
