# Augur Homepage Messaging Refresh

**Date:** 2026-04-10  
**Status:** Proposed  
**Surface:** `augur.run` homepage  
**Goal:** Clarify the persona, reduce ambiguity about who Augur is for, and explain what Augur actually lets users do without making the homepage feel overly technical.

## Problem

User interviews surfaced a messaging gap on the current homepage:

- It is not clear who Augur is for.
- The copy gestures toward power and architecture, but the persona is still blurry.
- The page does not clearly explain what users can practically do with Augur.
- The copy risks sounding like a tool for infra-heavy power users only, even though Augur already ships with apps and roughly 80 autoloops that reduce maintenance burden.

The right users are not generic consumers. They are people who already feel the pain of fragmented AI tooling, vendor dependency, quotas, pricing changes, policy shifts, missing features, and painful import/export experiences. But the homepage should not imply that only highly technical users can benefit.

## Positioning Decision

**Primary homepage positioning:**

> **Own your AI setup without vendor lock-in**

This will be the anchor message because it captures the strongest interview signal:

- dependency risk
- fragmented AI workflows
- instability from vendor-controlled limits and policies

This is sharper than a generic “second brain” promise and more differentiated than a convenience-first message.

## Messaging Principles

### 1. Website and GitHub should do different jobs

The homepage should be:

- product-led
- persona-clear
- low-jargon
- capability-oriented

The GitHub repo can carry:

- MCP depth
- Obsidian terminology
- architectural language
- autoloop and infra details
- more explicit power-user phrasing

The website should not try to compete with the repo in technical density.

The public GitHub destination must be named correctly:

- **Repo name:** Augur OS
- **Canonical URL:** `https://github.com/augur-os/augur-os`

The homepage should not refer to this generically as “GitHub” when the product surface is specifically the public **Augur OS** repository.

### 2. The homepage should not say Augur is only for power users

That would undersell one of Augur’s strongest product truths:

- it ships with apps
- it ships with autoloops
- it reduces maintenance load

The framing should be:

- Augur is built for people who care about ownership, portability, and vendor risk
- but it does not require them to personally babysit every layer of the system

### 3. Lead with pain and relief, not architecture

The first message should make users feel seen:

- multi-AI fragmentation
- vendor lock-in
- quota changes
- reasoning model price increases
- one vendor missing a feature they need
- painful import/export and migration friction

Only after that should the homepage explain the local system and integration model.

## Persona Definition

The homepage should implicitly and explicitly speak to:

- people using multiple AI tools, not just one
- users who know the pain of context fragmentation across tools
- users who care about owning their knowledge and workflows
- users who have already felt vendor dependency risk
- users who may know tools like Obsidian, but do not need the homepage to front-load that technical language

The homepage should **not** frame the persona as:

- casual AI beginners
- generic productivity users
- people looking for a simple hosted chatbot

It should also **not** say:

- “only for power users”
- “only for developers”

Instead it should say, in effect:

Augur is for people who want ownership and control, without spending all their time maintaining the system.

## Core Messaging Stack

### Hero

**Headline direction**

> Own your AI setup without vendor lock-in

**Hero subhead direction**

Augur gives users one local system for knowledge, tools, and workflows. It already comes with apps and roughly 80 autoloops, so users get ownership and portability without manually maintaining every moving part.

### Persona / Pain Section

This section should directly name the real pains:

- multiple AI tools that do not share context
- vendor limits and quotas
- pricing changes
- policy changes
- feature gaps from single-vendor dependence
- painful import/export and migration

This is where the homepage should tell the user:

If you already felt these problems, Augur is built for you.

### Capability Section

The homepage should include a simple, plain-English “what you can do with Augur” section.

Required examples:

1. Add a document and have it automatically indexed into your second brain.
2. Add a skill and expose it to all connected AI clients.
3. Connect local apps through CLI, such as home control systems.
4. Talk to your second brain while it is connected to Google and Apple ecosystems.
5. Add your Obsidian vault and work with it from any markdown editor.
6. Create MCP workflows and action items while retaining control over how each workflow executes.
7. Compound your knowledge base every day as you use it.
8. Build local apps you own on top of MCP and all the connected parts.

This section must stay concrete and user-readable. It should answer “what can I actually do?” in under a minute.

### Calm / Maintenance Relief Section

This section should explain a subtle but important promise:

- AI ecosystems keep changing quickly
- Augur keeps integrating with that change
- users can stay focused on their own knowledge and workflows instead of constantly rebuilding their system

This is the right place to introduce the role of shipped apps and autoloops:

- the system evolves
- maintenance burden is reduced
- the user remains in control without having to manage everything manually

### GitHub / Augur OS CTA

The homepage should include a clear CTA to the public **Augur OS** repository.

Recommended direction:

- **Button:** `Explore Augur OS on GitHub`
- **Support text:** `Read the philosophy, architecture, and technical direction in the public Augur OS repository. Augur is currently in soft launch.`

Important constraints:

- `soft launch` should appear only as a light status note near the GitHub CTA
- `soft launch` should not appear in the hero
- the CTA should make it clear that GitHub already contains substantive value today

## Documentation and Architecture Sync Requirement

The repo-facing philosophy and architecture documents must be updated to reflect the latest public product story.

This matters because the website and GitHub now play different roles:

- the website explains the product, persona, pains, and practical capabilities
- the Augur OS repository carries the deeper philosophy, architecture, and technical framing

The GitHub-facing documentation should be refreshed so it reflects:

- the current local-first ownership story
- the current explanation of apps and autoloops
- the current “what you can do with Augur” model
- the current soft-launch state
- the latest architecture language and public positioning

The website should not promise a repo experience that still reflects stale architecture or outdated launch framing.

## Content Constraints

- Avoid overloading the homepage with MCP-heavy or repo-style technical language.
- Avoid making Augur sound like a generic convenience app.
- Avoid making Augur sound like a tool only infra-minded hackers can use.
- Keep the homepage emotionally sharp and operationally concrete.
- Save deeper technical explanations for the repo and secondary pages.

## Proposed Homepage Flow

1. **Hero**
   Ownership and anti-lock-in, with reduced maintenance burden.

2. **Pain recognition**
   Explicitly name the fragmented multi-AI and vendor-dependency pain.

3. **What you can do with Augur**
   Concrete user actions in plain language.

4. **Why Augur feels calmer**
   AI evolves fast; Augur absorbs that churn so users can focus on knowledge.

5. **Augur OS CTA**
   Link deeper technical users to the public Augur OS repository with a light soft-launch note.

## Success Criteria

The revised homepage should make these things clear within the first screen and first scroll:

- who Augur is for
- why the user should care now
- how Augur is different from a vendor-controlled AI stack
- what the user can concretely do with it
- why local ownership does not mean manual maintenance burden

## Out of Scope

- Full visual redesign
- Deep GitHub README rewrite
- Secondary page rewrite for all site pages
- Detailed architecture explanation on the homepage

## Recommended Next Step

Implement a homepage copy pass that:

- rewrites the hero around anti-lock-in ownership
- sharpens the persona/pain section
- adds a concrete capabilities section
- adds a calm-maintenance framing section
- adds an Augur OS GitHub CTA with a light soft-launch note
- keeps deep technical language primarily in GitHub and secondary pages
- refreshes the GitHub-facing philosophy and architecture docs so they match the latest public story
