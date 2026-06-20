---
status: Implemented
date: 2026-03-28
deciders:
  - Gur Sannikov
related: [ADR-489, ADR-491, ADR-479]
hub: studio
tags: [distribution, generative-ui, widget, onboarding, skills-pack]
superseded_by: null
---

# ADR-520: Plugin Distribution Polish and Generative UI Widget System

## Context

Review of the [finance-skills](https://github.com/himself65/finance-skills) repository revealed two patterns Augur should adopt:

1. **Plugin distribution** — finance-skills supports `claude install`, `npx skills add`, per-skill zip releases, and `!command` dynamic detection at skill load time. Augur has the infrastructure (`.claude-plugin/`, workflows) but gaps in install UX, individual skill cherry-picking, onboarding SKILL.md complexity (368 lines for 6 modes), and no per-skill release artifacts for claude.ai.

2. **Generative UI** — finance-skills ships a design system for claude.ai's `show_widget` tool that produces interactive HTML/SVG widgets. Augur has no dynamic widget rendering. The design system is platform-agnostic but needs an Augur-native rendering path via the dashboard.

## Decision

Two parallel workstreams with zero file overlap:

### Workstream A: Plugin Distribution Polish

1. **Plugin manifests** — Enriched `.claude-plugin/plugin.json` and `marketplace.json` with `repository`, `keywords`, and `metadata` fields for `claude install` discoverability.

2. **Individual skill cherry-picking** — All 9 portable skills (`x-augur-portable: true`) verified for independent installability via `npx skills add`. READMEs with install instructions added to each.

3. **`!command` dynamic detection** — Added inline shell commands to onboarding SKILL.md that execute at load time, detecting installed dependencies and onboard state so the agent skips unnecessary steps.

4. **Mode-per-file refactor** — Split the 368-line onboarding SKILL.md into a ~131-line lean router + 6 reference files (`mode-default.md`, `mode-migrate.md`, `mode-connect.md`, `mode-full.md`, `mode-status.md`, `mode-templates.md`). Each mode loads only its reference file.

5. **Per-skill zip release workflow** — GitHub Actions workflow that zips each `skills/*/` directory and publishes as individual `.zip` release artifacts for claude.ai upload.

### Workstream B: Generative UI Widget System

1. **Widget block type** — Added `widget` as the 22nd canonical block type to the dashboard block system.

2. **WidgetBlock component** — Sandboxed iframe renderer (`sandbox="allow-scripts"`, no `allow-same-origin`) with CSP meta tag allowing 4 CDN origins (cdnjs, jsdelivr, unpkg, esm.sh), `postMessage` action bridge, auto-resize, and CSS variable mapping from claude.ai token names to Augur's shadcn/ui theme.

3. **MCP widget lifecycle tools** — Four Python MCP tools: `render-widget` (create and persist), `list-widgets` (query with page filter), `pin-widget` (attach to dashboard page), `delete-widget` (remove from runtime state). Storage at `get_runtime_dir()/widgets/`.

4. **generative-ui skill** — Portable skill (`x-augur-portable: true`) with platform detection, visual type routing, core design rules, and 4 reference files covering the design system, Chart.js patterns, SVG diagrams, and Augur theme mapping.

5. **Cross-platform widget compatibility** — CSS variable mapping ensures widget code written for claude.ai's `show_widget` works unmodified in Augur's dashboard. Platform detection routes to `show_widget` on claude.ai or `render-widget` MCP tool elsewhere.

## Consequences

### Positive

- External users can install Augur skills via `claude install gh:AugurOS/augur`
- Individual skills installable without pulling the full system
- Onboarding loads 3x fewer tokens per invocation
- Dashboard can render interactive widgets from chatbot sessions
- Widgets are cross-platform compatible (claude.ai and Augur dashboard)
- Widget design system teaches agents to produce high-quality visualizations

### Negative

- Widget HTML rendering in iframe has inherent limitations (no parent DOM access, limited to CDN allowlist)
- `!command` syntax only works in CLI-based agents (Claude Code, Codex) — ignored on claude.ai

### Neutral

- Existing 21 block types unchanged
- MCP bridge and transport layer unchanged
- Widget storage is ephemeral (runtime state) unless explicitly pinned

## Alternatives Considered

### Alternative 1: Sequential implementation (distribution first, then widgets)

Would unblock external users faster but delay widget rendering. Rejected because both workstreams have zero file overlap and can safely run in parallel.

### Alternative 2: Integrated approach (widget as flagship for distribution)

Build widget system first, use it as test case for distribution improvements. Rejected because it over-constrains the widget design to be portable-first and couples unrelated concerns.

### Alternative 3: Strict iframe sandbox (no CDN access)

Would break Chart.js, D3, and most useful widget libraries. Rejected in favor of semi-trusted model with CDN allowlist, consistent with Augur's local-first trust model where MCP output is trusted.

## References

- Design spec: `docs/superpowers/specs/2026-03-28-plugin-distribution-and-generative-ui-design.md`
- Distribution plan: `docs/superpowers/plans/2026-03-28-plugin-distribution-polish.md`
- Widget plan: `docs/superpowers/plans/2026-03-28-generative-ui-widget-system.md`
- Finance-skills repo: https://github.com/himself65/finance-skills
- ADR-489: One-Click Onboarding with Portable Skills Pack
- ADR-491: Unified Config-Driven Pages
- ADR-479: Multi-Client Skill Structure
