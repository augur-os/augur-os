# Plugin Distribution Polish + Generative UI Widget System

**Date:** 2026-03-28
**Status:** Approved
**Approach:** Parallel workstreams with zero file overlap

## Context

Review of [himself65/finance-skills](https://github.com/himself65/finance-skills) revealed patterns Augur should adopt:

1. **Plugin distribution** — finance-skills supports `claude install`, `npx skills add`, per-skill zip releases, and `!command` dynamic detection. Augur has the infrastructure (`.claude-plugin/`, workflows) but gaps in UX, cherry-picking, and onboarding complexity.
2. **Generative UI** — finance-skills ships a design system for claude.ai's `show_widget`. Augur has no dynamic widget rendering. The design system is platform-agnostic and valuable, but needs an Augur-native rendering path.

## Workstream A: Plugin Distribution Polish

### A1. Fix `claude install` UX

**Current state:** `.claude-plugin/plugin.json` and `marketplace.json` exist.

**Work:**
- Audit `plugin.json` — ensure `skills` field correctly references `skills/` with auto-discovery
- Audit `marketplace.json` — match current Anthropic plugin marketplace schema
- Test `claude install gh:<user>/augur-os` end-to-end, fix failures
- Document the install command in root README

**Files:** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`

### A2. Individual skill cherry-picking

**Current state:** `export-plugins.yml` exports tarballs. No `npx skills add` support for individual skills.

**Work:**
- Ensure each portable skill directory is independently installable via `npx skills add`
- Each skill already has self-contained `SKILL.md` with frontmatter — verify compliance
- Add install instructions per-skill in their `README.md`
- Test: `npx skills add <repo> --skill <name>` for each portable skill

**Files:** Portable skill `README.md` files, skill directory structure validation

### A3. `!command` dynamic detection in onboarding

**Rationale:** Selective approach — use `!command` for deterministic env/deps checks (fast, reliable). Keep `platform-detection.md` as reference doc because IDE detection involves heuristics better expressed as agent instructions than shell one-liners.

**Add to `skills/onboard/SKILL.md`:**
```markdown
!`(python3 --version && node --version && pnpm --version && uv --version) 2>&1 || echo "DEPS_MISSING"`
!`cat ~/Library/Application\ Support/Augur/state/onboard-complete.json 2>/dev/null || echo "NOT_ONBOARDED"`
```

**Behavior:**
- Agent sees live versions → skips install steps
- Agent sees `NOT_ONBOARDED` → runs fresh setup flow
- Agent sees state JSON → knows connected platforms, skips "are you new?" decision tree

**Files:** `skills/onboard/SKILL.md`

### A4. Onboarding SKILL.md refactor (mode-per-file)

**Rationale:** Current 367-line SKILL.md loads all 6 modes on every invocation. Mode-per-file means `/onboard --status` only loads ~30 lines of routing + the status reference.

**From:**
```
skills/onboard/
  SKILL.md (367 lines, 6 modes inline)
  references/platform-detection.md
```

**To:**
```
skills/onboard/
  SKILL.md (~100 lines: frontmatter, !command checks, routing table, common steps)
  references/
    platform-detection.md        # (exists, keep)
    mode-default.md              # Interactive setup steps 1-6
    mode-migrate.md              # Legacy detection, vault migration, plugin verify
    mode-connect.md              # Per-platform connection instructions
    mode-full.md                 # Combined fresh + migrate + verify
    mode-status.md               # Read-only state display
    mode-templates.md            # Template catalog, auto-derivation, persistence
```

**SKILL.md routing table:**

| Flag | Reference | When |
|------|-----------|------|
| (none) | `references/mode-default.md` | Fresh interactive setup |
| `--migrate` | `references/mode-migrate.md` | Upgrade existing install |
| `--connect <platform>` | `references/mode-connect.md` | Add IDE platform |
| `--full` | `references/mode-full.md` | Complete setup + migration |
| `--status` | `references/mode-status.md` | Show install state |
| `--templates` | `references/mode-templates.md` | Template-based onboarding |

**Files:** `skills/onboard/SKILL.md`, `skills/onboard/references/mode-*.md` (6 new files)

### A5. GitHub Actions release improvements

**Current state:** `build-skills-pack.yml` and `export-plugins.yml` exist.

**Work:**
- Add per-skill zip release workflow (like finance-skills' `release-skills.yml`) — each skill gets its own `.zip` in GitHub Releases for claude.ai web upload
- Ensure `export-plugins.yml` produces artifacts compatible with `npx skills add` consumption
- Add `CHANGELOG.md` entry per skill in releases

**Files:** `.github/workflows/release-skills.yml` (new), `.github/workflows/export-plugins.yml` (modify)

---

## Workstream B: Generative UI Widget System

### B1. New `widget` block type

**Add a 22nd block type** to the dashboard block system.

**Type definition (in `types.ts`):**
```typescript
widget: {
  title: string;
  html: string;         // Raw HTML/SVG from MCP tool
  height?: number;      // Optional fixed height, defaults to auto-fit
  cdnAllowlist?: string[]; // Override default CDN list
}
```

**Rendering (`WidgetBlock.tsx`):**
- Renders `<iframe srcdoc="...">` with `sandbox="allow-scripts"` (no `allow-same-origin`)
- CSP meta tag injected into srcdoc: `<meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline'; script-src 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com https://esm.sh; style-src 'unsafe-inline';">`
- `postMessage` listener in parent accepts `{type: "augur:action", action: string, args: object}` — validates action name against registry before dispatching
- Auto-height: widget posts `{type: "augur:resize", height: document.body.scrollHeight}`, parent resizes iframe
- Dark mode: parent injects CSS variable mapping (see B6) into srcdoc `<style>` block

**Security model (B+ semi-trusted with action bridge):**
- `sandbox="allow-scripts"` — JS runs, but no parent DOM access, no cookies, no localStorage
- CDN allowlist enforced via CSP — only 4 approved origins for external scripts
- Action bridge is the only parent communication channel — validated against action registry
- Fits Augur's local-first trust model: MCP output is trusted, but widget rendering is contained

**Files:** `apps/dashboard/lib/blocks/types.ts` (add type), `apps/dashboard/lib/blocks/block-resolver.ts` (add import), `apps/dashboard/components/blocks/types/WidgetBlock.tsx` (new)

### B2. MCP tools for widget lifecycle

**Three new MCP tools:**

```python
@mcp.tool(name="render-widget")
def render_widget(title: str, widget_code: str, source: str = "chat") -> dict:
    """Render an interactive HTML/SVG widget. Persists to runtime state."""
    widget_id = generate_id()
    widget = {
        "id": widget_id,
        "type": "widget",
        "title": title,
        "html": widget_code,
        "source": source,       # "chat" | "skill" | "block"
        "timestamp": now_iso(),
        "pinned_to": None
    }
    write_json(get_runtime_dir() / "widgets" / f"{widget_id}.json", widget)
    return widget

@mcp.tool(name="list-widgets")
def list_widgets(pinned_to: str = None) -> dict:
    """List all widgets, optionally filtered by pinned page."""
    # Reads from get_runtime_dir()/widgets/*.json
    # Returns sorted by recency

@mcp.tool(name="pin-widget")
def pin_widget(widget_id: str, page_path: str) -> dict:
    """Pin a widget to a dashboard page. Appears as a widget block."""
    # Updates pinned_to field in widget JSON

@mcp.tool(name="delete-widget")
def delete_widget(widget_id: str) -> dict:
    """Remove a widget from runtime state."""
    # Deletes widget JSON file
```

**Storage:** `get_runtime_dir()/widgets/{id}.json` — runtime state, not vault (widgets are ephemeral unless pinned).

**Files:** MCP tool registration in Python MCP server

### B3. Chatbot → Dashboard bridge

**Flow:**
1. Agent calls `render-widget` MCP tool with HTML
2. MCP tool writes to `get_runtime_dir()/widgets/{id}.json`
3. Dashboard picks up via `useMcpPoll("list-widgets", {}, { preset: "realtime" })`
4. Widget appears on pinned page (if pinned) or is accessible via `list-widgets` MCP tool for any page that queries it

**Platform-adaptive rendering:**

| Platform | Primary render | Persistence |
|----------|---------------|-------------|
| claude.ai | `show_widget` (native, inline) | Also calls `render-widget` for dashboard |
| Claude Code | `render-widget` only | Agent tells user "Widget at localhost:3000" |
| Cowork | `render-widget` only | Same as Claude Code |
| Skills-pack (no dashboard) | `show_widget` if on claude.ai, otherwise raw HTML in response | No persistence |

**Platform detection in SKILL.md:**
```markdown
!`echo $CLAUDE_PLATFORM 2>/dev/null || echo "unknown"`
```

### B4. Widget persistence and pinning

- **Ephemeral by default** — stored in runtime state, cleared on system cleanup
- **Pin to persist** — `pin-widget` attaches widget to a page path; pinned widgets survive cleanup
- **Pinned widgets render as blocks** — page scanner finds pinned widgets and injects `widget` blocks into page layout
- **CRUD via MCP** — `list-widgets`, `pin-widget`, `delete-widget`

### B5. The `generative-ui` skill

**Location:** `skills/generative-ui/`

**Structure:**
```
skills/generative-ui/
  SKILL.md                    # Platform detection, routing, when to use show_widget vs render-widget
  README.md                   # Skill documentation
  references/
    design-system.md          # Ported from finance-skills, CSS vars mapped to Augur theme
    chart-js.md               # Chart.js patterns, CDN allowlist, canvas sizing
    svg-diagrams.md           # SVG viewBox, pre-built classes, flowchart patterns
    augur-theme.md            # Augur-specific: CSS variable mapping, dark mode, action bridge API
```

**Frontmatter:**
```yaml
name: generative-ui
x-augur-hub: studio
x-augur-portable: true
description: >
  Design system for interactive HTML/SVG widgets. Triggers on: visualize, chart,
  diagram, dashboard, widget, interactive, mockup, draw, flowchart, explain visually,
  show me, illustrate, comparison grid, live calculation, payoff curve.
```

**Portable behavior:** When installed without the full dashboard (skills-pack), the skill only uses `show_widget` (claude.ai) or returns raw HTML in conversation. No `render-widget` calls since there's no dashboard.

### B6. CSS variable mapping (augur-theme.md)

The `WidgetBlock.tsx` injects this style block into every srcdoc, mapping claude.ai variable names to Augur's shadcn/ui tokens:

```css
:root {
  --color-background-primary: hsl(var(--background));
  --color-background-secondary: hsl(var(--muted));
  --color-background-tertiary: hsl(var(--card));
  --color-text-primary: hsl(var(--foreground));
  --color-text-secondary: hsl(var(--muted-foreground));
  --color-text-tertiary: hsl(var(--muted-foreground) / 0.7);
  --color-border-tertiary: hsl(var(--border));
  --color-border-secondary: hsl(var(--border));
  --color-border-primary: hsl(var(--ring));
  --color-background-info: hsl(var(--info, 217 91% 60%) / 0.1);
  --color-background-danger: hsl(var(--destructive) / 0.1);
  --color-background-success: hsl(142 76% 36% / 0.1);
  --color-background-warning: hsl(38 92% 50% / 0.1);
  --color-text-info: hsl(var(--info, 217 91% 60%));
  --color-text-danger: hsl(var(--destructive));
  --color-text-success: hsl(142 76% 36%);
  --color-text-warning: hsl(38 92% 50%);
  --font-sans: var(--font-sans, system-ui, sans-serif);
  --font-serif: Georgia, serif;
  --font-mono: var(--font-mono, ui-monospace, monospace);
  --border-radius-md: var(--radius, 8px);
  --border-radius-lg: calc(var(--radius, 8px) + 4px);
  --border-radius-xl: calc(var(--radius, 8px) + 8px);
}
```

**Result:** Widget code written for claude.ai's generative-ui skill works unmodified in Augur's dashboard. Same variable names, mapped to Augur's theme at render time.

---

## Coordination

### File ownership (zero overlap)

| Workstream | Owns | Does NOT touch |
|-----------|------|---------------|
| **A: Distribution** | `skills/onboard/`, `.claude-plugin/`, `.github/workflows/`, `scripts/build_skills_pack.py`, root `README.md` | `apps/dashboard/`, MCP Python tools |
| **B: Widgets** | `skills/generative-ui/`, `apps/dashboard/components/blocks/types/WidgetBlock.tsx`, `apps/dashboard/lib/blocks/types.ts` (+1 type), `apps/dashboard/lib/blocks/block-resolver.ts` (+1 import), MCP tool registration, `get_runtime_dir()/widgets/` | `skills/onboard/`, `.claude-plugin/`, workflows |

### Dependency

None blocking. Widget workstream sets `x-augur-portable: true` on `generative-ui`. Distribution workstream's `build_skills_pack.py` already scans for this flag — it will include the skill in the next skills-pack build automatically.

### Testing boundaries

| Workstream | Verification |
|-----------|-------------|
| **A: Distribution** | `claude install gh:...` works; `npx skills add` works per-skill; `/onboard --status` reads `!command` output; each `mode-*.md` loads for its flag; per-skill zips uploadable to claude.ai |
| **B: Widgets** | `WidgetBlock` renders HTML in sandboxed iframe; `render-widget` MCP tool returns correct shape; `postMessage` action bridge dispatches correctly; CSS vars map correctly in dark/light; `list-widgets`/`pin-widget`/`delete-widget` CRUD works; portable mode (no dashboard) degrades to `show_widget` or raw HTML |

### Out of scope

- No changes to existing 21 block types
- No changes to MCP bridge or transport layer
- No new dashboard navigation pages (widgets appear on existing pages via pinning or block builder)
- No `show_widget` polyfill for Claude Code
- No external user authentication
- No trade execution (finance-skills constraint carries over)
