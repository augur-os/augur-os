---
title: Augur And Guriqo Positioning Design
date: 2026-04-21
status: draft-approved
branch: main
---

# Augur And Guriqo Positioning Design

## Summary

Augur and Guriqo need a deliberate brand split across three public surfaces:

1. GitHub repo: Augur OS technical proof.
2. Augur website: personal and SMB open-source product story.
3. Guriqo website: commercial enterprise company story.

The shared thesis is that AI needs a durable second brain underneath it. The surfaces should not repeat the same copy. Each surface should do a different job for a different audience.

## Approved Brand Architecture

### Augur

Augur is the open-source second-brain product for personal builders, technical operators, and SMB teams.

Augur should own:

- Open-source second-brain infrastructure.
- Local-first personal and team knowledge compounding.
- AI-client neutrality across Claude Code, Codex, Gemini, Cursor, Ollama, private models, and public models.
- SDK, MCP server, skill runtime, document pipeline, dashboard, wiki compiler, tests, ADRs, and auto-loops.
- The practical two-step target story: install Augur, add documents and notes, then let the brain compound.

Augur should not be positioned as:

- A per-project `.agent/` folder.
- A generic LLM wrapper.
- A cloud knowledge SaaS.
- A commercial enterprise services company.

### Guriqo

Guriqo is the commercial enterprise company that deploys second-brain infrastructure for organizations.

Guriqo should own:

- Enterprise AI adoption and rollout.
- Governance, integration, enablement, and transfer.
- Vendor lock-in avoidance.
- AI cost control.
- Commercial deployment of Augur-style second-brain architecture.
- Enterprise credibility and decision-maker language.

Guriqo should not lead with:

- Personal second-brain setup.
- Open-source installation details.
- Individual hobbyist workflows.
- Generic AI consulting without the second-brain infrastructure thesis.

## Surface Roles

### 1. GitHub Repo: Augur OS

Audience:

- Developers.
- Technical builders.
- Personal power users.
- SMB operators.
- Open-source evaluators.

Job:

- Prove Augur is real infrastructure.
- Explain architecture, installation, local-first control, tests, ADRs, and maintenance discipline.
- Show why Augur is not only a folder, prompt pack, or wrapper.

Primary message:

> Augur is open-source second-brain infrastructure for individuals and SMBs.

Supporting message:

> It connects documents, notes, skills, MCP commands, dashboards, and AI agents into one local system you own.

Tone:

- Technical.
- Concrete.
- Builder-trust focused.
- Honest about current install complexity.

### 2. Augur Website

Audience:

- Personal builders.
- Operators.
- Knowledge workers.
- SMB teams.
- AI power users who already feel tool and memory fragmentation.

Job:

- Explain the product story quickly.
- Make the pain emotional and concrete.
- Convert users to GitHub, waitlist, or install path.
- Preserve the open-source and vendor-neutral promise.

Primary message:

> Build the open-source second brain your AI agents can operate.

Supporting message:

> Install Augur, add your documents and notes, and let your knowledge compound across skills, dashboards, MCP commands, and the AI clients you already use.

Tone:

- Clear.
- Ambitious.
- Practical.
- Personal and SMB friendly.

### 3. Guriqo Website

Audience:

- Enterprise leaders.
- CIO, CTO, AI transformation, operations, and department owners.
- Buyers who need deployment help, governance, and cost control.

Job:

- Sell commercial enterprise deployment.
- Explain why enterprise AI needs infrastructure, not another isolated AI tool.
- Position Guriqo as the partner that can deploy, integrate, govern, and transfer the system.

Primary message:

> Guriqo helps enterprises unlock AI through second-brain infrastructure without vendor lock-in or runaway AI costs.

Alternative headline:

> Enterprise AI needs a brain, not another vendor dashboard.

Supporting message:

> Guriqo helps organizations deploy second-brain infrastructure that connects knowledge, workflows, agents, and tools while reducing vendor lock-in and uncontrolled AI costs.

Relationship line:

> Augur is the open-source second brain. Guriqo is the enterprise deployment company behind it.

Tone:

- Commercial.
- Credible.
- Enterprise-ready.
- Governance and cost aware.

## Narrative System

The narrative should use an open-core split with a builder-to-enterprise ladder.

Mental model:

> Augur is for builders and small teams. Guriqo is for enterprises.

Public relationship:

> Build your AI brain with Augur. Deploy it across the enterprise with Guriqo.

Reasoning:

- The open-core split is simple and credible.
- The builder-to-enterprise ladder preserves the founder story: Augur began as a serious personal second brain, then became the architecture Guriqo can deploy commercially.
- Enterprise buyers should not be forced through personal-install language.
- Personal and SMB users should not feel like they are only a lead funnel for consulting.

## Messaging Principles

- Keep Augur personal, practical, open-source, and builder-friendly.
- Keep Guriqo enterprise, commercial, deployment-oriented, and governance-aware.
- Use "second-brain infrastructure" as the category.
- Use "vendor lock-in" and "AI costs" more strongly on Guriqo than on Augur.
- Use "install Augur, add documents and notes, compound knowledge" more strongly on Augur than on Guriqo.
- Avoid saying Guriqo helps "personal people." That blurs the brand split.
- If Guriqo later serves SMBs commercially, frame it as paid onboarding or team enablement, not the core public story.

## Copy Blocks

### GitHub README

> Augur is open-source second-brain infrastructure for individuals and SMBs. It connects documents, notes, skills, MCP commands, dashboards, and AI agents into one local system you own.

### Augur Website Hero

> Build the open-source second brain your AI agents can operate.

Subhead:

> Install Augur, add your documents and notes, and let your knowledge compound across skills, dashboards, MCP commands, and the AI clients you already use.

### Guriqo Website Hero

> Enterprise AI needs a brain, not another vendor dashboard.

Subhead:

> Guriqo helps organizations deploy second-brain infrastructure that connects knowledge, workflows, agents, and tools while reducing vendor lock-in and uncontrolled AI costs.

### Cross-Link Copy

On Augur:

> Need enterprise deployment? Guriqo helps organizations deploy second-brain infrastructure commercially.

On Guriqo:

> Built around Augur, the open-source second-brain infrastructure for builders and small teams.

## Alternatives Considered

### Single Shared Message

Rejected. Using the same message across GitHub, Augur, and Guriqo makes the story feel vague. It also makes enterprise buyers read personal setup copy and makes personal builders feel like consulting leads.

### Guriqo As General AI Consulting

Rejected. It is too generic and loses the durable difference: Guriqo deploys second-brain infrastructure, not generic prompt training or slide-deck AI strategy.

### Augur As Enterprise Platform First

Rejected. It weakens the open-source and personal-builder advantage. Augur should remain the open-source product and technical proof; Guriqo should carry commercial enterprise deployment.

## Implementation Scope

This design should drive copy updates across:

- `README.md` and related GitHub-facing docs.
- `packages/create-augur/` install copy.
- `augur.run` homepage and support GEO surfaces.
- Guriqo standalone homepage generated from `website-working/enterprise.html`.
- Release packaging scripts if they rewrite Guriqo copy.
- Positioning tests that protect the surface split.

## Acceptance Criteria

- GitHub README names Augur as open-source second-brain infrastructure for individuals and SMBs.
- Augur website names the open-source personal and SMB story and the two-step install target.
- Guriqo website names enterprise deployment, second-brain infrastructure, vendor lock-in avoidance, and AI cost control.
- Guriqo is not framed as the personal product.
- Augur is not framed as the commercial enterprise services company.
- Cross-links explain the relationship without collapsing the two brands.
- Tests protect the repo, Augur website, and Guriqo website positioning separately.

