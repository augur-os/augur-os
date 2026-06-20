# Generative UI Widget System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `widget` block type to the Augur dashboard that renders sandboxed HTML/SVG widgets from MCP tools, plus a `generative-ui` skill that teaches agents to produce widgets compatible with both claude.ai and Augur.

**Architecture:** New `WidgetBlock` component renders HTML in sandboxed iframe with CDN allowlist and action bridge. Four MCP tools manage widget lifecycle (render, list, pin, delete). The `generative-ui` skill provides the design system with CSS variable mapping for cross-platform widget compatibility.

**Tech Stack:** TypeScript (Next.js dashboard), Python (MCP tools), Markdown (skill references)

---

### Task 1: Add `widget` to the BlockType union and block resolver

**Files:**
- Modify: `apps/dashboard/lib/blocks/types.ts:1-23`
- Modify: `apps/dashboard/lib/blocks/block-resolver.ts:9-37`

- [ ] **Step 1: Add `widget` to the BlockType union**

In `apps/dashboard/lib/blocks/types.ts`, add `"widget"` to the BlockType union. Change line 1 comment and add after `"data-preview"`:

```typescript
/** The 22 canonical block types */
export type BlockType =
  | "stat-card"
  | "stat-grid"
  | "data-list"
  | "data-table"
  | "action-bar"
  | "card-grid"
  | "chart"
  | "markdown"
  | "calendar"
  | "activity-feed"
  | "notes"
  | "embed"
  | "ops-board"
  | "progress"
  | "kanban"
  | "tabbed"
  | "health"
  | "vault-notes"
  | "custom-sources"
  | "file-list"
  | "data-preview"
  | "widget";
```

- [ ] **Step 2: Add widget to block resolver**

In `apps/dashboard/lib/blocks/block-resolver.ts`, add the widget entry to `BLOCK_COMPONENTS` after line 36 (`"data-preview"`):

```typescript
  "data-preview": dynamic(() => import("@/components/blocks/types/DataPreviewBlock")),
  widget: dynamic(() => import("@/components/blocks/types/WidgetBlock")),
};
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard && npx tsc --noEmit --pretty 2>&1 | head -20
```

Expected: May show errors for missing `WidgetBlock` component — that's correct, we create it in Task 2.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/lib/blocks/types.ts apps/dashboard/lib/blocks/block-resolver.ts
git commit -m "feat(blocks): add widget to BlockType union and resolver"
```

---

### Task 2: Create `WidgetBlock.tsx` component

**Files:**
- Create: `apps/dashboard/components/blocks/types/WidgetBlock.tsx`

The component renders HTML/SVG in a sandboxed iframe with:
- `sandbox="allow-scripts"` (no `allow-same-origin`)
- CSP meta tag allowing 4 CDN origins
- `postMessage` listener for action bridge and auto-resize
- Injected CSS variables mapping claude.ai tokens to Augur's shadcn/ui theme

- [ ] **Step 1: Create the WidgetBlock component**

Create `apps/dashboard/components/blocks/types/WidgetBlock.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Code2 } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";

interface WidgetConfig {
  title?: string;
  html?: string;
  height?: number;
}

interface WidgetData {
  title?: string;
  html: string;
  height?: number;
}

const CDN_ALLOWLIST = [
  "https://cdnjs.cloudflare.com",
  "https://cdn.jsdelivr.net",
  "https://unpkg.com",
  "https://esm.sh",
];

const THEME_CSS = `
:root {
  --color-background-primary: hsl(var(--background, 0 0% 100%));
  --color-background-secondary: hsl(var(--muted, 210 40% 96%));
  --color-background-tertiary: hsl(var(--card, 0 0% 100%));
  --color-text-primary: hsl(var(--foreground, 222 84% 5%));
  --color-text-secondary: hsl(var(--muted-foreground, 215 16% 47%));
  --color-text-tertiary: hsl(var(--muted-foreground, 215 16% 47%) / 0.7);
  --color-border-tertiary: hsl(var(--border, 214 32% 91%));
  --color-border-secondary: hsl(var(--border, 214 32% 91%));
  --color-border-primary: hsl(var(--ring, 222 84% 5%));
  --color-background-info: hsl(217 91% 60% / 0.1);
  --color-background-danger: hsl(var(--destructive, 0 84% 60%) / 0.1);
  --color-background-success: hsl(142 76% 36% / 0.1);
  --color-background-warning: hsl(38 92% 50% / 0.1);
  --color-text-info: hsl(217 91% 60%);
  --color-text-danger: hsl(var(--destructive, 0 84% 60%));
  --color-text-success: hsl(142 76% 36%);
  --color-text-warning: hsl(38 92% 50%);
  --font-sans: system-ui, -apple-system, sans-serif;
  --font-serif: Georgia, serif;
  --font-mono: ui-monospace, monospace;
  --border-radius-md: 8px;
  --border-radius-lg: 12px;
  --border-radius-xl: 16px;
}
body {
  margin: 0;
  padding: 0;
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.7;
  color: var(--color-text-primary);
  background: transparent;
}
`;

function buildSrcdoc(html: string): string {
  const csp = [
    "default-src 'none'",
    `script-src 'unsafe-inline' ${CDN_ALLOWLIST.join(" ")}`,
    "'unsafe-inline'",
    `style-src 'unsafe-inline' ${CDN_ALLOWLIST.join(" ")}`,
    `connect-src ${CDN_ALLOWLIST.join(" ")}`,
    `font-src ${CDN_ALLOWLIST.join(" ")}`,
  ].join("; ");

  const resizeScript = `
    <script>
      function notifyResize() {
        window.parent.postMessage(
          { type: "augur:resize", height: document.body.scrollHeight },
          "*"
        );
      }
      new ResizeObserver(notifyResize).observe(document.body);
      window.addEventListener("load", notifyResize);
    </script>
  `;

  return `<meta http-equiv="Content-Security-Policy" content="${csp}">
<style>${THEME_CSS}</style>
${html}
${resizeScript}`;
}

export default function WidgetBlock(props: BlockProps<WidgetConfig>) {
  const { config, dataSource, onExpand } = props;
  const { title = "Widget" } = config;
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [iframeHeight, setIframeHeight] = useState(config.height ?? 300);

  const selfFetched = useBlockData<WidgetData>(dataSource, config, "widget");
  const data = (props.data as WidgetData | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;
  const html = data?.html ?? config.html;

  const handleMessage = useCallback((event: MessageEvent) => {
    if (!event.data || typeof event.data !== "object") return;

    if (event.data.type === "augur:resize" && typeof event.data.height === "number") {
      setIframeHeight(Math.min(event.data.height + 16, 2000));
    }

    if (event.data.type === "augur:action" && typeof event.data.action === "string") {
      // Action bridge: validated dispatch would go here
      // For now, log the action request
      console.log("[WidgetBlock] Action request:", event.data.action, event.data.args);
    }
  }, []);

  useEffect(() => {
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [handleMessage]);

  return (
    <BlockShell
      title={data?.title ?? title}
      icon={Code2}
      color="violet"
      onExpand={onExpand}
      staleError={error}
    >
      {loading ? (
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="h-24 w-full rounded bg-[var(--bg-hover)] animate-pulse" />
        </div>
      ) : !html && error ? (
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center">
            <p className="text-xs text-red-400/80">Failed to load widget</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        </div>
      ) : html ? (
        <iframe
          ref={iframeRef}
          srcDoc={buildSrcdoc(html)}
          className="w-full border-0"
          sandbox="allow-scripts"
          title={data?.title ?? title}
          style={{ height: `${iframeHeight}px` }}
        />
      ) : (
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-xs text-[var(--text-muted)] italic">
            No widget content
          </p>
        </div>
      )}
    </BlockShell>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd apps/dashboard && npx tsc --noEmit --pretty 2>&1 | head -20
```

Expected: PASS (no type errors).

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/components/blocks/types/WidgetBlock.tsx
git commit -m "feat(blocks): add WidgetBlock with sandboxed iframe rendering

Renders HTML/SVG in iframe with sandbox='allow-scripts', CDN allowlist
via CSP, auto-resize via postMessage, and claude.ai CSS variable mapping."
```

---

### Task 3: Create MCP tools for widget lifecycle

**Files:**
- Create: `src/mcp/augur_mcp/tools/hubs/widgets.py`
- Modify: `src/mcp/augur_mcp/tools/hubs/__init__.py:10-18`

Four MCP tools: `render-widget`, `list-widgets`, `pin-widget`, `delete-widget`. Storage at `get_runtime_dir()/widgets/`.

- [ ] **Step 1: Create the widget tools module**

Create `src/mcp/augur_mcp/tools/hubs/widgets.py`:

```python
"""MCP tools for widget lifecycle — render, list, pin, delete."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from augur_mcp.config import get_runtime_dir

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _widgets_dir() -> Path:
    d = get_runtime_dir() / "widgets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_widget(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_widget(widget: dict[str, Any]) -> Path:
    path = _widgets_dir() / f"{widget['id']}.json"
    path.write_text(json.dumps(widget, indent=2), encoding="utf-8")
    return path


def register_tools(mcp: "FastMCP", interceptor=None, metrics: Any = None) -> None:
    """Register widget lifecycle tools."""

    @mcp.tool(name="render-widget")
    def render_widget(title: str, widget_code: str, source: str = "chat") -> dict:
        """Render an interactive HTML/SVG widget. Persists to runtime state.

        Args:
            title: Snake_case identifier for the widget
            widget_code: Raw HTML or SVG code to render
            source: Origin context — "chat", "skill", or "block"
        """
        widget_id = str(uuid.uuid4())[:8]
        widget = {
            "id": widget_id,
            "type": "widget",
            "title": title,
            "html": widget_code,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pinned_to": None,
        }
        _write_widget(widget)
        return widget

    @mcp.tool(name="list-widgets")
    def list_widgets(pinned_to: str | None = None) -> dict:
        """List all widgets, optionally filtered by pinned page.

        Args:
            pinned_to: Optional page path to filter by. If None, returns all widgets.
        """
        widgets = []
        for path in sorted(_widgets_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            w = _read_widget(path)
            if w is None:
                continue
            if pinned_to is not None and w.get("pinned_to") != pinned_to:
                continue
            widgets.append(w)
        return {"items": widgets, "count": len(widgets)}

    @mcp.tool(name="pin-widget")
    def pin_widget(widget_id: str, page_path: str) -> dict:
        """Pin a widget to a dashboard page so it appears as a widget block.

        Args:
            widget_id: The widget ID returned by render-widget
            page_path: Dashboard page path to pin to (e.g., "/studio/visualization")
        """
        path = _widgets_dir() / f"{widget_id}.json"
        if not path.exists():
            return {"error": f"Widget {widget_id} not found"}
        widget = _read_widget(path)
        if widget is None:
            return {"error": f"Widget {widget_id} is corrupted"}
        widget["pinned_to"] = page_path
        _write_widget(widget)
        return widget

    @mcp.tool(name="delete-widget")
    def delete_widget(widget_id: str) -> dict:
        """Remove a widget from runtime state.

        Args:
            widget_id: The widget ID to delete
        """
        path = _widgets_dir() / f"{widget_id}.json"
        if not path.exists():
            return {"error": f"Widget {widget_id} not found"}
        path.unlink()
        return {"deleted": widget_id}
```

- [ ] **Step 2: Register widget tools in hub __init__.py**

In `src/mcp/augur_mcp/tools/hubs/__init__.py`, add the import and registration call:

```python
"""Hub Tools - Domain-specific vertical functionality"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_hub_tools(mcp: "FastMCP", interceptor=None, metrics: Any = None) -> None:
    """Register all hub tools with the MCP server."""
    from .capabilities import register_tools as register_capabilities
    from .agent_registry import register_tools as register_agent_registry
    from .scrape_and_save_idea import register_tools as register_scrape_and_save_idea
    from .widgets import register_tools as register_widgets

    register_capabilities(mcp, interceptor=interceptor, metrics=metrics)
    register_agent_registry(mcp, interceptor=interceptor, metrics=metrics)
    register_scrape_and_save_idea(mcp, interceptor=interceptor, metrics=metrics)
    register_widgets(mcp, interceptor=interceptor, metrics=metrics)


__all__ = ["register_hub_tools"]
```

- [ ] **Step 3: Verify the MCP tools load**

```bash
cd ~/Projects/Augur && python3 -c "
from src.mcp.augur_mcp.tools.hubs.widgets import register_tools
print('Widget tools module loads OK')
"
```

Expected: `Widget tools module loads OK`

- [ ] **Step 4: Commit**

```bash
git add src/mcp/augur_mcp/tools/hubs/widgets.py src/mcp/augur_mcp/tools/hubs/__init__.py
git commit -m "feat(mcp): add widget lifecycle tools — render, list, pin, delete

Four MCP tools for managing interactive widgets:
- render-widget: Create and persist widget HTML to runtime state
- list-widgets: Query widgets with optional page filter
- pin-widget: Attach widget to a dashboard page
- delete-widget: Remove widget from runtime state"
```

---

### Task 4: Create the `generative-ui` skill

**Files:**
- Create: `skills/generative-ui/SKILL.md`
- Create: `skills/generative-ui/README.md`
- Create: `skills/generative-ui/references/design-system.md`
- Create: `skills/generative-ui/references/chart-js.md`
- Create: `skills/generative-ui/references/svg-diagrams.md`
- Create: `skills/generative-ui/references/augur-theme.md`

Port the finance-skills generative-ui design system, adapted for Augur's dual rendering (show_widget on claude.ai, render-widget MCP tool for dashboard).

- [ ] **Step 1: Create the SKILL.md**

Create `skills/generative-ui/SKILL.md`:

```markdown
---
name: generative-ui
x-augur-hub: studio
x-augur-portable: true
x-augur-type: skill
x-augur-tags: [visualization, charts, diagrams, widgets]
description: >
  Design system for interactive HTML/SVG widgets. Triggers on: visualize, chart,
  diagram, dashboard, widget, interactive, mockup, draw, flowchart, explain visually,
  show me, illustrate, comparison grid, live calculation, payoff curve. Provides
  the complete Anthropic "Imagine" design system for generating high-quality widgets
  that work on both claude.ai (via show_widget) and the Augur dashboard (via render-widget MCP tool).
---

# Generative UI Skill

Create interactive HTML/SVG widgets for data visualization, diagrams, dashboards, and explainers.

## Platform Detection

` ``
!`echo "${CLAUDE_PLATFORM:-unknown}" 2>/dev/null`
` ``

**Rendering strategy based on platform:**

| Platform | Primary render | Also do |
|----------|---------------|---------|
| claude.ai | `show_widget` (native inline) | Call `render-widget` MCP tool for dashboard persistence |
| Claude Code / Cowork / other | `render-widget` MCP tool only | Tell user: "Widget rendered — view at localhost:3000" |
| Skills-pack (no dashboard) | `show_widget` if on claude.ai | Otherwise return raw HTML in response |

## Step 1: Pick the Visual Type

Route on the **verb**, not the noun:

| User says | Type | Format |
|---|---|---|
| "how does X work" | Illustrative diagram | SVG |
| "X architecture" | Structural diagram | SVG |
| "what are the steps" | Flowchart | SVG |
| "explain compound interest" | Interactive explainer | HTML |
| "compare these options" | Comparison grid | HTML |
| "show revenue chart" | Chart.js chart | HTML |
| "create a contact card" | Data record | HTML |
| "draw a sunset" | Art/illustration | SVG |

## Step 2: Build the Widget

Read the appropriate reference file for detailed patterns:

- `references/design-system.md` — Core rules, CSS variables, typography, layout
- `references/chart-js.md` — Chart.js patterns, canvas sizing, CDN loading
- `references/svg-diagrams.md` — SVG viewBox, pre-built classes, flowcharts
- `references/augur-theme.md` — Augur CSS variable mapping, action bridge API

### Core Rules (always apply)

- **Structure**: `<style>` → HTML content → `<script>` (streams token-by-token)
- **No comments** in widget code (waste tokens, break streaming)
- **No font-size below 11px**
- **No emoji** — use CSS shapes or SVG paths
- **No gradients, drop shadows, blur, glow** — flat design only
- **No `position: fixed`** — normal-flow layouts only
- **Typography**: two weights only: 400 regular, 500 medium
- **Round every displayed number** — `Math.round()`, `.toFixed(n)`, `Intl.NumberFormat`
- **Dark mode mandatory** — use CSS variables, never hardcode colors

### CDN Allowlist

External resources may ONLY load from:
- `cdnjs.cloudflare.com`
- `cdn.jsdelivr.net`
- `unpkg.com`
- `esm.sh`

## Step 3: Render the Widget

**On claude.ai** (show_widget available):
```json
{
  "title": "snake_case_widget_name",
  "widget_code": "<style>...</style>\n<div>...</div>\n<script>...</script>"
}
```

**On Augur dashboard** (render-widget MCP tool):
Call the `render-widget` MCP tool:
- `title`: Snake_case identifier
- `widget_code`: HTML/SVG code (same as show_widget format)
- `source`: "chat" (from conversation) or "skill" (from skill invocation)

**On both** (when both are available):
Call `show_widget` first for inline display, then `render-widget` for persistence.

## Step 4: After Rendering

Briefly explain:
1. What the widget shows
2. How to interact with it (which controls do what)
3. One key insight from the data

## Reference Files

- `references/design-system.md` — Color palette, CSS variables, UI patterns, layout rules
- `references/chart-js.md` — Chart.js configuration, script loading, canvas sizing
- `references/svg-diagrams.md` — SVG viewBox, font calibration, pre-built classes, diagram patterns
- `references/augur-theme.md` — Augur-specific CSS variable mapping, dark mode tokens, action bridge API
```

- [ ] **Step 2: Create `references/design-system.md`**

Create `skills/generative-ui/references/design-system.md`. Port from the finance-skills version with Augur adaptations:

```markdown
# Design System Reference

## CSS Variables

All widgets MUST use CSS variables for colors. Never hardcode hex values in HTML (Canvas/Chart.js is the exception — canvas cannot resolve CSS variables).

### Backgrounds
- `--color-background-primary` — main content bg (white in light, dark in dark)
- `--color-background-secondary` — surface/card bg
- `--color-background-tertiary` — page bg
- `--color-background-info` / `-danger` / `-success` / `-warning` — semantic light fills

### Text
- `--color-text-primary` — main text (black in light, white in dark)
- `--color-text-secondary` — muted text
- `--color-text-tertiary` — hints
- `--color-text-info` / `-danger` / `-success` / `-warning` — semantic text

### Borders
- `--color-border-tertiary` — default border (0.15 alpha)
- `--color-border-secondary` — hover border (0.3 alpha)
- `--color-border-primary` — focus border (0.4 alpha)

### Typography
- `--font-sans` — system sans-serif
- `--font-serif` — Georgia, serif
- `--font-mono` — system monospace

### Layout
- `--border-radius-md` — 8px (elements)
- `--border-radius-lg` — 12px (cards)
- `--border-radius-xl` — 16px (containers)

## Typography Rules

- Headings: h1=22px, h2=18px, h3=16px — all font-weight 500
- Body: 16px, weight 400, line-height 1.7
- Two weights only: 400 (regular), 500 (medium). Never 600 or 700.
- Sentence case always. Never Title Case, never ALL CAPS.
- No mid-sentence bolding — entity names go in `code style`

## Layout Patterns

### Stat Cards
```html
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px;">
  <div style="background: var(--color-background-secondary); border-radius: var(--border-radius-md); padding: 1rem;">
    <div style="font-size: 13px; color: var(--color-text-secondary);">Label</div>
    <div style="font-size: 24px; font-weight: 500;">Value</div>
  </div>
</div>
```

### Slider Controls
```html
<div style="display: flex; align-items: center; gap: 12px; margin: 0 0 1.5rem;">
  <label style="font-size: 14px; color: var(--color-text-secondary);">Param</label>
  <input type="range" min="0" max="100" value="50" id="param" style="flex: 1;" />
  <span style="font-size: 14px; font-weight: 500; min-width: 32px;" id="param-out">50</span>
</div>
```

## Constraints

- No `<!DOCTYPE>`, `<html>`, `<head>`, `<body>` — content fragments only
- No `position: fixed`
- No tabs, carousels, or `display: none` during streaming
- No nested scrolling — auto-fit height
- No rounded corners on single-sided borders
- Outer container background must be `transparent` (host provides bg)
```

- [ ] **Step 3: Create `references/chart-js.md`**

Create `skills/generative-ui/references/chart-js.md`:

```markdown
# Chart.js Reference

## Script Loading Pattern

Use `onload` callback to handle async CDN loading:

```html
<div style="position: relative; width: 100%; height: 300px;">
  <canvas id="myChart"></canvas>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js" onload="initChart()"></script>
<script>
function initChart() {
  // Chart setup here
}
if (window.Chart) initChart();
</script>
```

## Canvas Rules

- Canvas CANNOT resolve CSS variables — use hardcoded hex colors
- Set height ONLY on the wrapper div, never on canvas
- Always: `responsive: true, maintainAspectRatio: false`
- Always disable default legend, build custom HTML legends
- Number formatting: `-$5M` not `$-5M`

## Recommended Colors (hex for canvas)

| Use | Light mode | Dark mode |
|-----|-----------|-----------|
| Primary line | `#7F77DD` | `#9B94E8` |
| Secondary line | `#3B82F6` | `#60A5FA` |
| Success fill | `rgba(34, 197, 94, 0.15)` | `rgba(34, 197, 94, 0.25)` |
| Danger fill | `rgba(239, 68, 68, 0.15)` | `rgba(239, 68, 68, 0.25)` |
| Grid lines | `rgba(0,0,0,0.06)` | `rgba(255,255,255,0.06)` |
| Tick text | `#6B7280` | `#9CA3AF` |

## Chart Template

```html
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px;">
  <div style="background: var(--color-background-secondary); border-radius: var(--border-radius-md); padding: 1rem;">
    <div style="font-size: 13px; color: var(--color-text-secondary);">Label</div>
    <div style="font-size: 24px; font-weight: 500;" id="stat1">—</div>
  </div>
</div>

<div style="position: relative; width: 100%; height: 300px; margin-top: 1rem;">
  <canvas id="myChart"></canvas>
</div>

<div style="display: flex; align-items: center; gap: 12px; margin-top: 1rem;">
  <label style="font-size: 14px; color: var(--color-text-secondary);">Parameter</label>
  <input type="range" min="0" max="100" value="50" id="param" step="1" style="flex: 1;" />
  <span style="font-size: 14px; font-weight: 500; min-width: 32px;" id="param-out">50</span>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js" onload="initChart()"></script>
<script>
function initChart() {
  const slider = document.getElementById('param');
  const out = document.getElementById('param-out');
  let chart = null;

  function update() {
    const val = parseFloat(slider.value);
    out.textContent = val;
    document.getElementById('stat1').textContent = val.toFixed(1);

    const labels = [], data = [];
    for (let x = 0; x <= 100; x++) {
      labels.push(x);
      data.push(x * val / 100);
    }

    if (chart) chart.destroy();
    chart = new Chart(document.getElementById('myChart'), {
      type: 'line',
      data: { labels, datasets: [{ data, borderColor: '#7F77DD', borderWidth: 2, pointRadius: 0, fill: false }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { grid: { display: false } } }
      }
    });
  }

  slider.addEventListener('input', update);
  update();
}
if (window.Chart) initChart();
</script>
```
```

- [ ] **Step 4: Create `references/svg-diagrams.md`**

Create `skills/generative-ui/references/svg-diagrams.md`:

```markdown
# SVG Diagram Reference

## ViewBox Setup

- Always 680px wide: `viewBox="0 0 680 H"` where H = content height + 40px padding
- Safe area: x=40 to x=640, y=40 to y=(H-40)
- Use `width="100%"` for responsive scaling

## Pre-Built CSS Classes

Include these in `<style>` for every SVG widget:

```css
.t { font-size: 14px; fill: var(--color-text-primary); font-family: var(--font-sans); }
.ts { font-size: 12px; fill: var(--color-text-secondary); font-family: var(--font-sans); }
.th { font-size: 14px; fill: var(--color-text-primary); font-weight: 500; font-family: var(--font-sans); }
.box { fill: var(--color-background-secondary); stroke: var(--color-border-tertiary); }
.node rect { fill: var(--color-background-secondary); stroke: var(--color-border-tertiary); }
.arr { stroke: var(--color-border-secondary); stroke-width: 1; }

/* Color ramps */
.c-blue rect { fill: hsl(217 91% 60% / 0.1); stroke: hsl(217 91% 60% / 0.4); }
.c-blue text { fill: hsl(217 91% 60%); }
.c-teal rect { fill: hsl(172 66% 50% / 0.1); stroke: hsl(172 66% 50% / 0.4); }
.c-teal text { fill: hsl(172 66% 50%); }
.c-violet rect { fill: hsl(263 70% 60% / 0.1); stroke: hsl(263 70% 60% / 0.4); }
.c-violet text { fill: hsl(263 70% 60%); }
.c-amber rect { fill: hsl(38 92% 50% / 0.1); stroke: hsl(38 92% 50% / 0.4); }
.c-amber text { fill: hsl(38 92% 50%); }
.c-red rect { fill: hsl(0 84% 60% / 0.1); stroke: hsl(0 84% 60% / 0.4); }
.c-red text { fill: hsl(0 84% 60%); }
.c-green rect { fill: hsl(142 76% 36% / 0.1); stroke: hsl(142 76% 36% / 0.4); }
.c-green text { fill: hsl(142 76% 36%); }
```

## Arrow Marker

```svg
<defs>
  <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>
```

## Node Templates

### Single-line node (44px tall)
```svg
<g class="node c-blue">
  <rect x="250" y="40" width="180" height="44" rx="8" stroke-width="0.5"/>
  <text class="th" x="340" y="62" text-anchor="middle" dominant-baseline="central">Label</text>
</g>
```

### Two-line node (56px tall)
```svg
<g class="node c-teal">
  <rect x="230" y="120" width="220" height="56" rx="8" stroke-width="0.5"/>
  <text class="th" x="340" y="140" text-anchor="middle" dominant-baseline="central">Title</text>
  <text class="ts" x="340" y="158" text-anchor="middle" dominant-baseline="central">Subtitle</text>
</g>
```

### Connector arrow
```svg
<line x1="340" y1="84" x2="340" y2="120" class="arr" marker-end="url(#arrow)"/>
```

## Rules

- Every `<text>` must carry a class (`t`, `ts`, or `th`)
- Use `dominant-baseline="central"` for vertical centering in boxes
- Connector paths need `fill="none"` (SVG defaults to `fill: black`)
- Stroke width: 0.5px for borders and edges
```

- [ ] **Step 5: Create `references/augur-theme.md`**

Create `skills/generative-ui/references/augur-theme.md`:

```markdown
# Augur Theme Reference

## CSS Variable Mapping

Widgets use claude.ai variable names. The Augur dashboard injects a style block that maps them to shadcn/ui tokens. **Write widgets using the claude.ai names — they work on both platforms.**

| Widget variable | Maps to (Augur) |
|----------------|-----------------|
| `--color-background-primary` | `hsl(var(--background))` |
| `--color-background-secondary` | `hsl(var(--muted))` |
| `--color-background-tertiary` | `hsl(var(--card))` |
| `--color-text-primary` | `hsl(var(--foreground))` |
| `--color-text-secondary` | `hsl(var(--muted-foreground))` |
| `--color-border-tertiary` | `hsl(var(--border))` |
| `--font-sans` | `var(--font-sans)` |
| `--border-radius-md` | `var(--radius)` |
| `--border-radius-lg` | `calc(var(--radius) + 4px)` |

## Action Bridge API

Widgets can dispatch Augur dashboard actions via `postMessage`:

```javascript
// Send an action to the dashboard
window.parent.postMessage({
  type: "augur:action",
  action: "action-name",
  args: { key: "value" }
}, "*");
```

The dashboard validates the action name against its registry before dispatching. Invalid actions are logged and ignored.

## Auto-Resize

Widgets automatically communicate their height to the parent:

```javascript
// Injected automatically by WidgetBlock — you don't need to add this
window.parent.postMessage({
  type: "augur:resize",
  height: document.body.scrollHeight
}, "*");
```

A `ResizeObserver` on `document.body` handles dynamic height changes (e.g., when a user expands a section or loads more data).

## Dark Mode

Both platforms inject CSS variables that auto-adapt to light/dark mode. Test every widget by asking: "If the background were near-black, would every text element still be readable?"

Rules:
- In HTML: always use CSS variables for text. Never `color: #333`
- In SVG: use pre-built color classes (`.c-blue`, `.c-teal`, etc.)
- In Canvas (Chart.js): use hardcoded hex — pick from the chart color table in `references/chart-js.md`
```

- [ ] **Step 6: Create README.md**

Create `skills/generative-ui/README.md`:

```markdown
# generative-ui

Design system for interactive HTML/SVG widgets. Works on claude.ai (via `show_widget`) and the Augur dashboard (via `render-widget` MCP tool).

## Install

```bash
npx skills add AugurOS/augur --skill generative-ui
```

## Platform

All platforms. Rendering adapts automatically:
- **claude.ai**: Uses `show_widget` for inline display
- **Claude Code / Cursor / Cowork**: Uses `render-widget` MCP tool for dashboard display
- **Skills-pack (no dashboard)**: Returns raw HTML

## Triggers

visualize, chart, diagram, dashboard, widget, interactive, mockup, draw, flowchart, explain visually, show me, illustrate, comparison grid, live calculation

## Reference Files

- `references/design-system.md` — CSS variables, typography, layout patterns
- `references/chart-js.md` — Chart.js configuration and templates
- `references/svg-diagrams.md` — SVG viewBox, pre-built classes, node templates
- `references/augur-theme.md` — Augur CSS variable mapping, action bridge, dark mode
```

- [ ] **Step 7: Commit**

```bash
git add skills/generative-ui/
git commit -m "feat: add generative-ui skill with cross-platform widget design system

Ports the Anthropic 'Imagine' design system from finance-skills, adapted for
Augur's dual rendering: show_widget on claude.ai, render-widget MCP tool for
dashboard. CSS variable mapping ensures widgets work on both platforms."
```

---

### Task 5: End-to-end verification

**Files:** None (verification only)

- [ ] **Step 1: Verify TypeScript builds**

```bash
cd ~/Projects/Augur/apps/dashboard && npx tsc --noEmit --pretty 2>&1 | tail -5
```

Expected: No errors.

- [ ] **Step 2: Verify MCP tools register**

```bash
cd ~/Projects/Augur && python3 -c "
from src.mcp.augur_mcp.tools.hubs.widgets import register_tools
print('render-widget, list-widgets, pin-widget, delete-widget — OK')
"
```

Expected: Tools load without errors.

- [ ] **Step 3: Verify generative-ui skill frontmatter**

```bash
head -12 skills/generative-ui/SKILL.md
```

Expected: Valid YAML frontmatter with `name: generative-ui`, `x-augur-hub: studio`, `x-augur-portable: true`.

- [ ] **Step 4: Verify widget block resolves**

Check that the block resolver can find the widget component:

```bash
grep -n "widget" apps/dashboard/lib/blocks/block-resolver.ts
```

Expected: Line showing `widget: dynamic(() => import("@/components/blocks/types/WidgetBlock"))`.

- [ ] **Step 5: Verify all reference files exist**

```bash
ls -la skills/generative-ui/references/
```

Expected: `design-system.md`, `chart-js.md`, `svg-diagrams.md`, `augur-theme.md`

- [ ] **Step 6: Commit verification pass**

```bash
git add -A && git status
```

Expected: No uncommitted changes (all tasks already committed).
