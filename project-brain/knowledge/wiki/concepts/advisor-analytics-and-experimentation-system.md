---
title: Advisor Analytics And Experimentation System
summary: Advisor analytics and experimentation turns telemetry, cost, session, skill,
  GitHub, marketing, and experiment data into evidence for optimizing Augur workflows.
tags:
- advisor-analytics-and-experimentation-system
- advisor-architecture-and-product-review-system
- brain
- advisor
- analytics
- experimentation
- system
aliases:
- advisor analytics
related:
- '[[advisor-architecture-and-product-review-system]]'
created: '2026-05-03T13:36:28Z'
_page_type: concept
_hub: brain
_sources:
- vault:notes/augur/advisor/README.md
- vault:notes/venture/content/linkedin/posts/2026-02-19-token-cost-adr-workflow.md
- vault:skills/advisor/SKILL.md
- vault:skills/advisor/augur/actions/advisor-overview.md
- vault:skills/advisor/augur/modules/cost-analytics.md
- vault:skills/advisor/augur/modules/github-search.md
- vault:skills/advisor/augur/modules/marketing-analytics.md
- vault:skills/advisor/augur/modules/session-analytics.md
- vault:skills/advisor/augur/modules/skill-usage-analytics.md
- vault:skills/advisor/commands/add-prompt-helper.md
- vault:skills/advisor/commands/analyze-usage-patterns.md
- vault:skills/advisor/commands/improve-prompt.md
- vault:skills/advisor/commands/triage-backlog.md
- vault:skills/advisor/references/ab-testing-framework.md
_source_fingerprint: a7294975b3294484de4bb5b3f9b9cc43cc75562b4f5ae3f88a0030cdccdcab2e
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:41:02Z'
_cites:
- '[[vault:notes/augur/advisor/README.md]]'
- '[[vault:notes/venture/content/linkedin/posts/2026-02-19-token-cost-adr-workflow.md]]'
- '[[vault:skills/advisor/SKILL.md]]'
- '[[vault:skills/advisor/augur/actions/advisor-overview.md]]'
- '[[vault:skills/advisor/augur/modules/cost-analytics.md]]'
- '[[vault:skills/advisor/augur/modules/github-search.md]]'
- '[[vault:skills/advisor/augur/modules/marketing-analytics.md]]'
- '[[vault:skills/advisor/augur/modules/session-analytics.md]]'
- '[[vault:skills/advisor/augur/modules/skill-usage-analytics.md]]'
- '[[vault:skills/advisor/commands/add-prompt-helper.md]]'
- '[[vault:skills/advisor/commands/analyze-usage-patterns.md]]'
- '[[vault:skills/advisor/commands/improve-prompt.md]]'
- '[[vault:skills/advisor/commands/triage-backlog.md]]'
- '[[vault:skills/advisor/references/ab-testing-framework.md]]'
_mentions:
- '[[concepts/advisor-architecture-and-product-review-system]]'
_relates_to:
- '[[advisor-architecture-and-product-review-system]]'
- '[[advisor]]'
- '[[analytics]]'
- '[[brain]]'
- '[[experimentation]]'
- '[[system]]'
_entity_tier: 2
---

# Advisor Analytics And Experimentation System

## Compiled truth

### Current Thesis

Advisor analytics uses telemetry, token costs, sessions, skill usage, GitHub search, marketing funnels, and experiments to optimize Augur from evidence.

### What This Page Knows

Advisor data and skill metadata describe telemetry, eval harnesses, backlog snapshots, and health actions. Cost, session, and skill-usage modules define operational metrics around tier routing, tool calls, context, chain completion, and per-skill value. GitHub search, marketing analytics, and A/B testing extend that measurement habit to external discovery, campaign performance, funnel analysis, and experiment decisions. The existing advisor page already covers telemetry, cost, session, skill, GitHub, marketing, and A/B evidence. The command sources add the operator-facing actions: add dashboard buttons end to end, analyze usage patterns, improve prompts from real logs, and triage backlog items by priority, owner, blockers, and sprint. The token-cost post adds a public lesson about model routing and agent-team spend. Together the page describes an evidence loop that finds waste, revises prompts, prioritizes work, and verifies whether the change improved quality.

### Key Dimensions

- Backlog triage separates blockers from deferrable work and assigns owners, dependencies, and sprint timing.
- Cost analytics finds spend by tier, workflow, chain, escalation, and failed sessions.
- Dashboard action wiring must be verified through the action run path, not only by adding a button.
- GitHub search adds structured external-option discovery and adaptation estimates.
- Marketing and experiments add funnel, cohort, KPI, ROI, guardrail, and significance discipline.
- Prompt improvement should compare current weaknesses, revised wording, expected quality gains, and an A/B evaluation plan.
- Session analytics shows duration, tools, context use, handoffs, abandonment, and compression.
- Skill usage analytics connects invocations, completion, token spend, coverage, and value.
- Token-cost analysis belongs beside quality analysis because model routing can change the economics of agent teams.
- Usage analysis starts from telemetry and produces patterns, anomalies, evaluation observations, prompt opportunities, and weekly actions.

### Recent Shifts

- Advisor analytics now includes concrete command actions, not only background modules.
- Advisor is becoming a Studio workbench for evidence-backed optimization.
- Public token-cost evidence strengthens the model-routing and cost-control dimension.

### Open Tensions

- Backlog triage can become performative unless blockers and owners are explicit.
- Cheaper routing helps only when it preserves enough reasoning quality for the task.
- Telemetry shows signals, but judgment is still needed to separate waste from necessary reasoning cost.

### How to Use This

Use this when deciding which skills, chains, prompts, models, campaigns, experiments, or external repositories deserve optimization attention.

### Open Questions

- Which advisor metrics should become always-visible dashboard health signals?
- Which dashboard actions need run-path proof before being trusted?
- Which prompt changes should get formal A/B tests?

### Source Basis

- `vault:notes/augur/advisor/README.md`: analytics, design artifacts, and evaluation outputs
- `vault:notes/venture/content/linkedin/posts/2026-02-19-token-cost-adr-workflow.md`: Claude Code Agent Teams default behavior will quietly drain your budget.
- `vault:skills/advisor/SKILL.md`: Score every skill on completeness
- `vault:skills/advisor/augur/actions/advisor-overview.md`: Advisor Overview
- `vault:skills/advisor/augur/modules/cost-analytics.md`: Track and analyze token spend across tiers, agents, and workflows.
- `vault:skills/advisor/augur/modules/github-search.md`: Compare user requirements vs found repos
- `vault:skills/advisor/augur/modules/marketing-analytics.md`: Provides structured patterns for marketing metrics tracking, funnel analysis, and campaign performance reporting.
- `vault:skills/advisor/augur/modules/session-analytics.md`: Analyze session behavior patterns: length, tool call distribution, context window utilization, and agent switching frequency.
- `vault:skills/advisor/augur/modules/skill-usage-analytics.md`: Analyze which Augur skills and chains are used most, measure cost per skill, and track token efficiency across the system.
- `vault:skills/advisor/commands/add-prompt-helper.md`: Add a new dashboard action button and wire it end-to-end.
- `vault:skills/advisor/commands/analyze-usage-patterns.md`: Analyze advisor telemetry and usage evidence
- `vault:skills/advisor/commands/improve-prompt.md`: Improve the selected action prompt using real advisor telemetry and backlog evidence.

### Related Concepts

- [[concepts/advisor-architecture-and-product-review-system]]

## Timeline

- _at: 2026-05-03T13:41:02Z  _source: vault:notes/augur/advisor/README.md
  analytics, design artifacts, and evaluation outputs.

- _at: 2026-05-03T13:41:02Z  _source: vault:notes/venture/content/linkedin/posts/2026-02-19-token-cost-adr-workflow.md
  Claude Code Agent Teams default behavior will quietly drain your budget.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/advisor/SKILL.md
  Score every skill on completeness.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/advisor/augur/actions/advisor-overview.md
  Advisor Overview.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/advisor/augur/modules/cost-analytics.md
  Track and analyze token spend across tiers, agents, and workflows.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/advisor/augur/modules/github-search.md
  Compare user requirements vs found repos.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/advisor/augur/modules/marketing-analytics.md
  Provides structured patterns for marketing metrics tracking, funnel analysis, and campaign performance reporting.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/advisor/augur/modules/session-analytics.md
  Analyze session behavior patterns: length, tool call distribution, context window utilization, and agent switching frequency.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/advisor/augur/modules/skill-usage-analytics.md
  Analyze which Augur skills and chains are used most, measure cost per skill, and track token efficiency across the system.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/advisor/commands/add-prompt-helper.md
  Add a new dashboard action button and wire it end-to-end.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/advisor/commands/analyze-usage-patterns.md
  Analyze advisor telemetry and usage evidence.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/advisor/commands/improve-prompt.md
  Improve the selected action prompt using real advisor telemetry and backlog evidence.
