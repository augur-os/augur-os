---
status: Implemented
date: 2026-03-28
deciders:
  - Gur Sannikov
related: []
hub: studio
tags:
  - widgets
  - blocks
  - mcp
  - generative-ui
  - dashboard
superseded_by: null
---

# ADR-574: Generative UI Widget System

## Context

Augur agents need to produce interactive HTML/SVG visualizations — charts, diagrams, calculators, comparison grids — that work both inside claude.ai (via the native `show_widget` capability) and inside the Augur dashboard. Today, the dashboard has no block type for arbitrary HTML, and no skill teaches agents how to author widgets compatible with both rendering surfaces.

Widgets must execute untrusted HTML/JS safely, follow a consistent design system that maps cleanly onto the dashboard's shadcn/ui theme, and persist as artifacts that users can pin to dashboard pages or revisit later.

## Decision

Add a `widget` block type to the dashboard and a cross-platform `generative-ui` skill, backed by four MCP tools that manage widget lifecycle.

### Widget block

- Extend the canonical `BlockType` union with `"widget"` (now 22 types) and register `WidgetBlock` in the block resolver.
- Render HTML in a sandboxed iframe with `sandbox="allow-scripts"` (no `allow-same-origin`) and a CSP meta tag allowlisting four CDN origins: `cdnjs.cloudflare.com`, `cdn.jsdelivr.net`, `unpkg.com`, `esm.sh`.
- Inject a `<style>` block that maps the claude.ai design-system CSS variables (`--color-background-primary`, `--font-sans`, `--border-radius-md`, etc.) onto the dashboard's shadcn/ui tokens, so a single widget body works on both platforms.
- Implement an action bridge and auto-resize via `postMessage`: the iframe posts `augur:resize` (handled by a `ResizeObserver` on `document.body`) and `augur:action` (validated against a registry).

### Widget MCP tools

Four tools registered under `tools/hubs/widgets.py`, persisting widgets as JSON files at `get_runtime_dir()/widgets/`:

- `render-widget(title, widget_code, source)` — create and persist a widget.
- `list-widgets(pinned_to?)` — list widgets, optionally filtered by pinned page.
- `pin-widget(widget_id, page_path)` — attach a widget to a dashboard page.
- `delete-widget(widget_id)` — remove a widget from runtime state.

### `generative-ui` skill

A new portable skill in the `studio` hub that teaches agents the Anthropic "Imagine" design system, adapted for Augur's dual rendering. Reference files cover: design system (CSS variables, typography, layout), Chart.js (script loading, canvas sizing), SVG diagrams (viewBox, pre-built color classes, node templates), and Augur theme (variable mapping, action bridge, dark mode). Routing rules pick `show_widget` first on claude.ai, `render-widget` on dashboard hosts, and raw HTML when neither is available.

## Consequences

### Positive
- Agents can produce rich, interactive visualizations without bespoke per-skill UI work.
- Widgets are sandboxed; the host page is protected from arbitrary script and same-origin access.
- A single widget body renders on both claude.ai and the Augur dashboard.
- Pinned widgets become first-class dashboard blocks, persisted in runtime state.

### Negative
- The CDN allowlist is closed; widgets requiring other CDNs cannot load them without changing the allowlist.
- The action bridge is a new surface area — actions must be validated to prevent privilege escalation.
- Widget persistence under runtime state grows over time and may require a cleanup policy.

### Neutral
- Canvas (Chart.js) cannot resolve CSS variables, so charts use hardcoded hex colors selected per light/dark mode.
- Widget HTML is fragment-only (no `<!DOCTYPE>`, `<html>`, `<head>`, `<body>`), enforced by the design-system reference.

## Alternatives Considered

### Alternative 1: Render widgets directly without a sandbox iframe
Rejected because untrusted HTML in the host DOM can read theme tokens, intercept clicks, and exfiltrate session state. Sandboxed iframes are the only safe substrate.

### Alternative 2: Build a dashboard-only widget format incompatible with claude.ai
Rejected because agents already produce widgets via `show_widget` on claude.ai; forcing two formats would double skill maintenance and split the design system.

### Alternative 3: Embed widgets as static images (server-side rendering)
Rejected because interactive controls — sliders, tabs, live calculations — are core use cases, and static images cannot deliver them.

## References
- Plan: docs/superpowers/plans/2026-03-28-generative-ui-widget-system.md
