---
title: browse-rule-32-every-tab-is-the-same-card-grid-no-bespoke-panels
name: browse-rule-32-every-tab-is-the-same-card-grid-no-bespoke-panels
description: A new Browse tab is a FILTER over BrowseItem cards, never a bespoke multi-section
  panel. Signals (audits, profile state, interview progress, memory entries) ride
  existing cards as metadata badges + detail-panel sections; the only sanctioned exception
  is a genuine interactive manager surface like extensions-bundles install/configure
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_browse_rule_32_cards_only.md
source_hash: d4d43772e336461c
_mentions:
- '[[feedback_client_side_verification]]'
- '[[feedback_long_session_drift]]'
---



CLAUDE.md rule 32 + `docs/architecture-dashboard.md` "Discovery contract — every tab is the shared file-card mechanism" are the canonical statement. Re-read both before any Browse change.

**Why this memory exists:** During the 2026-05-17 Profile-tab merge I built `ProfileTabPanel.tsx` with `VoiceProfile + InterviewSection + MemoriesSection + ActivitySection` and added an early-return `if (viewMode === "profile") return <ProfileTabPanel />` in `BrowseDisplayRenderer.tsx`. That is exactly the bespoke-panel pattern rule 32 forbids and the architecture doc names as an "architecture violation: it splits the discovery mechanism and needs out-of-band toggles to even render."

**The user's words when they caught it:** "you also broke complately the pattern of brose page that all tabs are same infrasctrure of card and list."

**The correct mental model:**
- Every Browse tab is a filter over a category of `BrowseItem` records.
- A new signal (voice profile state, interview progress, ADR-741 audit, drift finding) joins onto the relevant item's `BrowseItem.metadata` and becomes a card tag/badge + a section in the detail panel that opens on click.
- A signal with no owning item rides the nearest related card (per the architecture-dashboard.md `mcp-tools` / `stale_capability_entries` example).
- An aggregate (e.g. "73 memories total") belongs on a hub dashboard card or stays in CLI/MCP — never as a tab.
- The ONLY sanctioned exception is an interactive manager surface (install/configure/rebuild console). `extensions-bundles` is the only current one.

**How to apply:** before any Browse change, run this checklist:
1. Open `docs/architecture-dashboard.md` "Browse page taxonomy" section AND CLAUDE.md rule 32. Read both, not from memory.
2. Ask: "Which existing BrowseItem card does this signal belong on?" If the answer is "none," the answer is probably "this is a hub dashboard card or a CLI/MCP report — not a new tab."
3. If extending: enrich `transformMemory` / `transformIndexEntry` / matching transformer in `lib/browse/transforms.ts` so cards carry the new metadata. Extend the bootstrap MCP response with structured per-item data, not aggregate counts.
4. If adding a `viewMode === "..."` early-return in `BrowseDisplayRenderer.tsx`, STOP. Rule 32 violation. The sanctioned exception is a manager surface, not a discovery panel.
5. Mention `architecture-dashboard.md` in the implementation plan explicitly — don't write a Browse plan that only cites types.ts and useBrowseState.ts.

**Related:** [[feedback_long_session_drift]] (mechanical gates beat behavioral rules — rule 32 alone wasn't enough), [[feedback_client_side_verification]] (typecheck-clean + snapshot-clean is not design-correct).

**Future hook to write:** a lint script (probably `.githooks/pre-commit` or `pre-commit-config.yaml`) that fails when `BrowseDisplayRenderer.tsx` contains `viewMode === ` early-return branches outside the manager-surface allowlist (currently just `extensions-bundles`). Would have caught this commit.
