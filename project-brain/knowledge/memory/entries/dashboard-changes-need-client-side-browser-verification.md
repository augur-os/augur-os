---
title: dashboard changes need client-side browser verification
name: dashboard-changes-need-client-side-browser-verification
description: HTTP 200 from curl + SSR markup checks + accessibility-tree YAML do NOT
  prove a dashboard page works; visual screenshot at the rendered viewport size is
  the only honest UI verification
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_client_side_verification.md
source_hash: 4009cebb20797bb2
---

For any change touching dashboard UI, dashboard config (`config.yaml`, `manifest.yaml`, `SKILL.md` pages), generated tab/hub registries, or anything that triggers a Next.js rebuild — verify the affected pages load to interactive state in a real browser AND take a screenshot at a tall-enough viewport that you can see the actual rendered output. If the browser is unavailable, say so explicitly. Never claim "all good" from curl smoke alone.

**Four failure modes I've personally hit:**
1. **Chunk drift** (the original lesson, 2026-04): server returns 200 SSR doc that references chunks the client cannot load → page mounts a `Failed to load chunk` error boundary while every server-side check reports green.
2. **Accessibility-tree snapshot lies by omission** (2026-05-17 Profile-tab merge): Playwright's YAML snapshot showed "4 headings present, 4 sections rendered, console clean". I called it verified. The user opened the page and it was visually broken — VoiceProfile content overflowed its `DashboardWidget` (maxHeight + `scrollable={false}` = `overflow:visible`) and painted ON TOP of the three sections below it. The DOM said sections existed at the right y-coordinates; the actual paint bleed was invisible to the snapshot. Always pair the snapshot with a real screenshot.
3. **Viewport too short** (same incident): a 1200×600 fullPage screenshot captured the viewport, not the full scroll-height of a 2400px-tall tab — looked fine because the broken sections were below the fold. Use `browser_resize` to a tall viewport (1440×2400+) before screenshotting, OR scroll the inner `<main>` (not just `window`) and screenshot multiple segments.
4. **Pipeline late-stage silent filter** (2026-05-17 Profile-tab card grid): MCP probe confirmed bootstrap returned 78 server-built BrowseItems with the right shape. Bundle inspection confirmed my new transformMemory code was loaded. Yet React props.items showed ZERO of my server cards in the visible top-30. Root cause: I extended the entry point (transformMemory) but the downstream pipeline had a *default recency sort* (`getBrowseItemTimestampMs`) that ranked items missing `metadata.modified` to last place — past the page-size pagination cap. Plus the bare-allFiles enumeration produced 3-5 duplicate cards per file (each client-projection dir contributes one), drowning even the few semantic cards that did surface. Fix needed both: add `metadata.modified` on server cards AND skip allFiles when serverBuiltItems is populated.

**Lesson: when extending a pipeline, walk the whole pipeline against real data.** The pipeline order in Browse is: transform → dedup-by-id → filter-by-tag/hub/etc → sort-by-recency → paginate-visibleCount. Each step has its own contract. Tracking only step 1 (transform output) led me to "MCP probe shows 78 items, code is in the bundle" → false confidence. Instead trace each step's output against real production data: log/inspect rawItems.length, items.length (post-dedup), filtered.length, sorted[0..5] (head after sort), displayItems.length (post-pagination). The point where my cards disappeared was sort → pagination, two layers downstream of my edit.

**Why:** SSR HTML + accessibility tree both describe DOM structure. They do not describe paint order, overflow bleed, z-index conflicts, or CSS variable cascades. A page can have a perfect accessibility tree and look completely broken because of one `overflow: visible` inside a constrained wrapper.

**How to apply:** Before reporting completion on a UI/dashboard task:
1. Resize browser to viewport tall enough to fit the entire scroll-height (`mcp__plugin_playwright_playwright__browser_resize` width=1440 height=2400 or larger).
2. Take a real screenshot (`browser_take_screenshot`) and actually LOOK at it. If the file size is <100 KB it's probably empty or viewport-only; >300 KB usually means real content.
3. For long pages, also use `browser_evaluate` to query each kid container's `getBoundingClientRect()` and verify `kid[i+1].y >= kid[i].bottom + gap` (no overlap).
4. Add a `Verified-Browser:` trailer to the commit (CLAUDE.md rule 28, .githooks/commit-msg enforces it). Dispatched sub-agents working on UI/dashboard changes inherit the same rule and must report client-load status, not just SSR.
