---
title: Setup Completeness Widget — Design
type: spec
status: draft
created: 2026-05-10
authors:
  - gsannikov
related:
  - shared-vault/skills/onboard/SKILL.md
  - apps/dashboard/components/SidebarNav.tsx
  - apps/dashboard/app/settings/page.tsx
  - config/system/capability_exposure.yaml
governance:
  next_step: ADR (via /adr write) → implementation plan (writing-plans)
tags:
  - dashboard
  - onboarding
  - sidebar
  - mcp
  - vault
---

# Setup Completeness Widget — Design

A persistent, progressive-disclosure widget that lives at the bottom of the dashboard sidebar (above Settings) and on the Settings page header. It tracks 11 setup milestones across three phases — Foundation, Knowledge, Personalization — auto-detecting completion via existing MCP tools and small additions to the onboard skill.

The widget is *not* a one-time onboarding wizard. It is an ongoing **setup-completeness signal**. As the user progresses, the widget quiets itself: full card → compact bar → tiny chip. If a previously-completed probe regresses (vault disconnects, sources go empty), the chip flips amber and re-asserts itself.

## Goals

1. **Drive momentum** for new users by showing a clear, ordered path from empty system to fully personalized second brain.
2. **Surface regressions** for long-time users without nagging them at 100%.
3. **Stay honest** — auto-detect every item against a real source of truth. No manual checkboxes, no phantom items.
4. **Stay quiet at 100%** — no permanent 8-item checklist eating sidebar space forever.

## Non-goals

- A full onboarding wizard or guided tour.
- A celebration animation on completion.
- Per-item history ("vault verified 17 times this month").
- A `manage saved prompts` dashboard surface (convention-only for now; future ADR).
- Daemon-driven push notifications on regression (nice-to-have v2).

## User-facing behavior

### Three states, derived from `% complete`

| State | Range | Behavior |
|---|---|---|
| **Full card** | 0–60% | Phase headers + 11 checklist items. Click an incomplete item to inline-expand → 1-line description, "do it now" button, "Skip" button. |
| **Compact bar** | 60–99% | One-line `⚡ ▓▓▓░ 8/11 →`. Click expands the same full-card body in a popover. |
| **Chip** | 100% | Tiny pill `● Setup complete`. Click expands the card. |
| **Alert chip** | Regression at 100% | Same chip flips amber: `● Sources empty · review`. |

Transitions are automatic. No user toggles. Probe results recompute on dashboard load and on a 5-minute server-side cache window.

### Skip semantics

"Skip" marks an item as `dismissed` for that user. Skipped items don't count toward the denominator. The user can un-skip from the Settings page deep-dive. This is honest — it doesn't claim the user did the thing, just acknowledges they chose not to.

### Click action

Clicking an incomplete item inline-expands it inside the widget body, showing:
- 1–2 line description.
- A "do it now" action button (behavior depends on `action.type`).
- A "Skip" link.

No modals. No multi-page wizard. No toasts.

**Action-button mechanics by type (v1):**

| `action.type` | What the button does in v1 |
|---|---|
| `route` | `next/link` navigation to the dashboard route. Preserves history. |
| `mcp` | Calls `POST /api/mcp/tool` with the named tool. Shows inline result/error in the expanded item. |
| `command` | **Copy slash command to clipboard + show toast "Paste in your AI client"**. v1 does *not* attempt to dispatch into an active client session — that's a separate ADR (cross-client command dispatch is non-trivial). |

The `command` mechanic is intentionally low-effort for v1 — the user is already in their AI client when working with Augur, paste-from-clipboard is one keystroke, and we avoid the rabbit hole of session routing. Future ADR can upgrade `command` to one-click dispatch.

## The 11 items

| # | Phase | Item | Detection |
|---|---|---|---|
| 1 | Foundation | Index your machine | `agent-registry` MCP returns ≥1 client AND ≥1 skill |
| 2 | Foundation | Create or clone vault | `vault-status` + `Path(vault_dir).exists()` |
| 3 | Foundation | Build human profile | Profile file exists AND size > 256 bytes |
| 4 | Knowledge | Configure inbox folders | `inbox-folders` returns ≥1 |
| 5 | Knowledge | Add document source folders | `knowledge-sources` + `knowledge-linked-folders` ≥1 |
| 6 | Knowledge | Set wiki compounding queries | `wiki-status.compounding.queries` ≥1 |
| 7 | Knowledge | Wiki has ≥5 compounded pages | `wiki-list --count` ≥5 |
| 8 | Personalization | Create a private skill | `count(<vault>/skills/*/SKILL.md)` ≥1 |
| 9 | Personalization | Save first prompt | `count(<vault>/prompts/*.md)` ≥1 |
| 10 | Personalization | First /ask answered | `wc -l <state>/ask-history.jsonl` ≥1 |
| 11 | Personalization | Connect first integration | `list-integrations` returns ≥1 active |

## Architecture

```
┌──────────── shared-vault/skills/onboard/ ─────────────┐
│  config/setup-items.yaml         (11 items registry)   │
│  probes/{foundation,knowledge,personalization}.py      │
│  mcp/setup_status.py             (aggregator)          │
└───────────────────────────┬───────────────────────────┘
                            │
                  MCP tool: get-setup-status
                            │
┌───────────────────────────┴───────────────────────────┐
│  apps/dashboard/                                        │
│    components/SidebarNav.tsx → mounts <SetupWidget>     │
│    app/settings/page.tsx → mounts <SetupWidget …>       │
│    features/setup/SetupWidget/                          │
│      ├ index.tsx (state machine: card|bar|chip|alert)   │
│      ├ FullCard, CompactBar, Chip, ItemRow              │
│      └ useSetupStatus.ts (calls MCP via dashboard)      │
└─────────────────────────────────────────────────────────┘
```

### Ownership (rule 2 — plugin decentralization)

- The **onboard skill** owns: items registry, probes, persisted state, aggregator MCP. Extend `shared-vault/skills/onboard/` — do **not** create a new skill.
- The **dashboard** owns the widget UI under `apps/dashboard/features/setup/` (per ADR-490 — feature-volatile code under `@/features/`).
- They never bypass MCP. The widget calls `POST /api/mcp/tool` → `get-setup-status` per rule 11. Never reads files or shells out from the dashboard.

### MCP exposure

`get-setup-status` is added to `config/system/capability_exposure.yaml` with surface `mcp via dashboard` and `export_to: [mcp]`. The widget consumes it via the existing dashboard MCP client.

### State persistence

Two new keys under `preferences.yaml` (managed via existing `update-preference` MCP):

```yaml
setup:
  skipped: []           # list of item ids the user explicitly skipped
  ever_completed: false # flips to true on first 100%, never flips back
```

That is the only thing written. Probe results are recomputed every load (cached 5 min server-side, 60 s client-side).

## Data model

### Items registry — `shared-vault/skills/onboard/config/setup-items.yaml`

Declarative; adding/removing an item is a YAML edit, not code:

```yaml
version: 1
phases:
  - id: foundation
    label: Foundation
    items:
      - id: index-machine
        label: Index your machine
        description: Discover skills and AI clients across your harness.
        probe: foundation.index_machine
        action: { type: command, command: "/discover", label: "Run /discover" }
      - id: vault
        label: Create or clone vault
        probe: foundation.vault
        action: { type: command, command: "/onboard --migrate", label: "Set up vault" }
      - id: human-profile
        label: Build human profile
        probe: foundation.human_profile
        action: { type: mcp, mcp_tool: "memory-profile-regenerate", label: "Generate profile" }

  - id: knowledge
    label: Knowledge
    items: [ inbox-folders, source-folders, wiki-queries, wiki-pages-5 ]

  - id: personalization
    label: Personalization
    items: [ private-skill, saved-prompt, first-ask, integration ]
```

`action.type` ∈ `command | route | mcp`.

### MCP response — `get-setup-status`

```typescript
interface SetupStatus {
  version: 1
  computed_at: string         // ISO
  total: number               // non-skipped items
  completed: number
  pct: number                 // 0–100
  state: 'card' | 'bar' | 'chip' | 'alert'
  ever_completed: boolean
  phases: PhaseStatus[]
}

interface PhaseStatus {
  id: 'foundation' | 'knowledge' | 'personalization'
  label: string
  total: number
  completed: number
  pct: number
  items: ItemStatus[]
}

interface ItemStatus {
  id: string
  label: string
  description: string
  status: 'done' | 'pending' | 'skipped' | 'regressed'
  action: { type: 'command' | 'route' | 'mcp', command?: string, route?: string, mcp_tool?: string, label: string }
  details?: string             // e.g. "Vault at ~/Augur — verified 2m ago"
  last_checked: string         // ISO
}
```

### Regression rule

`state === 'alert'` iff `ever_completed && any non-skipped item.status === 'pending'`. Each regressed item is tagged `status: 'regressed'` (not just `pending`) so the widget renders them in amber and surfaces them at the top of the card.

## Probes

Each probe is a thin Python function in the onboard skill. None mutate state. Failure modes return `pending` with a `details` warning, never crash the aggregator.

### The shared `vault_has` helper

Two items follow the same shape (vault has artifact X). One helper, two one-line probes:

```python
def vault_has(subdir: str, glob: str = "*", min_count: int = 1) -> ProbeResult:
    paths = list((vault_dir / subdir).glob(glob))
    return ProbeResult(
        status="done" if len(paths) >= min_count else "pending",
        details=f"{len(paths)} in {subdir}/" if paths else None,
    )

# private-skill:
vault_has("skills", "*/SKILL.md")
# saved-prompt:
vault_has("prompts", "*.md")
```

The `first-ask` probe is similar in spirit (vault state has artifact X) but reads a line count from a JSONL log rather than a directory glob — distinct mechanic, kept as its own one-liner.

### Resolved gaps

Each "gap" identified during brainstorm is closed inside the design — no deferred phantom items:

| Gap | Resolution | Owner | Effort |
|---|---|---|---|
| Non-mutating profile check | Drop the MCP call. Probe stats the profile file (path exists + size > 256 b). | onboard probe | ~5 lines |
| Ask history | `/ask` appends one JSONL line to `<state>/ask-history.jsonl` on successful completion: `{ts, query_hash, model, latency_ms}`. Probe reads `wc -l`. | ask skill (1 hook) + onboard probe | ~15 lines total |
| Saved-prompt surface | Convention only: `<vault>/prompts/*.md` with a README. The richer "manage saved prompts" feature is a separate future ADR — not coupled to onboarding. | new vault dir + README | ~10 lines |
| Private-skill detection | `<vault>/skills/` *is* the private location by definition (per ADR-601 / CLAUDE.md). No frontmatter filter — count directories. | onboard probe | ~3 lines |
| `wiki-queries` shape | Extend `wiki-status` to expose `compounding.queries` (passthrough from existing config). | rag/wiki skill | ~5 lines |

### Failure handling

A probe that errors (tool unreachable, permission denied) returns `status='pending'` with `details='Could not verify — click to retry'` rather than crashing. The widget renders these distinctively (small warning icon).

## Caching

- **Server-side**: probes run on first request, cached for **5 min** keyed by tool name. Manual refresh button bypasses cache.
- **Client-side**: dashboard hook caches MCP response for **60 s** to avoid re-hitting on every render.

## Rollout

One PR, four verified checkpoints (rule 10):

| Checkpoint | What | Verifiable by |
|---|---|---|
| **C1** Prerequisites | `<vault>/prompts/README.md` · `/ask` appends history JSONL · `wiki-status` exposes `compounding.queries` · `capability_exposure.yaml` entry | unit tests on each touch |
| **C2** Backend | `setup-items.yaml` registry · 11 probes · aggregator MCP `get-setup-status` | `python -m augur.onboard.setup_status --json` returns valid `SetupStatus` against fixture vault |
| **C3** UI (sidebar) | `SetupWidget/` components · SidebarNav mount above Settings · `useSetupStatus` hook | Real-browser load (rule 28) — verify card/bar/chip/alert transitions |
| **C4** Settings deep-dive | Same widget body mounted at top of `/settings` with `variant="settings"` | Real-browser load + screenshot diff. Cleanup of older `/api/agents/onboarding/validate/[step]` route iff grep confirms no callers (rule 22) |

## Testing

- **pytest** — each probe has fixture-vault test cases (done, pending, regressed, timeout, permission-denied). Aggregator state-machine tests cover the four threshold transitions and the alert rule.
- **Component tests** — React Testing Library on `FullCard`, `CompactBar`, `Chip` with mocked `useSetupStatus`. Snapshot the four states and the inline-expanded item.
- **Browser verification (rule 28)** — `/auto-test-dashboard` for Sidebar + Settings pages. Manual screenshot pass on the four states before C3 / C4 are declared done. **HTTP 200 from curl is not sufficient.**
- **Auto-loop integration** — register `auto-test-onboarding-probes` to run the aggregator against a fixture vault and verify expected output. Honest reporting per rule 8.

## Edge cases handled in design

- **Vault unavailable** — all items pending, widget renders amber alert with copy "Vault unreachable — verify config".
- **Probe times out** — 2 s per-probe cap, 10 s aggregate; timeouts surface as `pending: 'timed out, click retry'`, never silently dropped.
- **All items skipped** — denominator floor of 1; widget shows "All items skipped — un-skip from Settings."
- **First load with no preferences** — `ever_completed: false` default, `skipped: []`, full-card state.
- **Multi-machine** — preferences.yaml is per-machine; setup is per-machine. Honest with Augur's local-first model.

## Coexistence with existing `/onboard` skill

The existing `onboard` skill ships `/onboard --full | --migrate | --templates` plus an older step-validation API at `apps/dashboard/app/api/agents/onboarding/validate/[step]/route.ts` (steps: organization, ide, mcp, workspace, testing). That is a *technical bootstrap* surface — separate concern from this *user-adoption journey* surface.

Decision:
- Keep `/onboard --migrate` (used by the vault item action).
- The older step-validation route is checked for callers in C4. If unused → delete (rule 14, canonical cleanup). If used → leave intact, no compatibility shims.

## Visual design

The widget matches existing sidebar tokens: `text-sm font-medium`, `w-5 h-5` Lucide icons, CSS variables (`--text-primary`, `--text-secondary`, `--border-color`, `--bg-sidebar`). Custom CSS classes nav-link / nav-link-active for hover. Phase mini-bars use the project's `--accent-success` for completion, neutral surface for incomplete. Alert state uses `--accent-warning` (amber).

## Governance

This brainstorming spec is the design record. After approval:

1. `/adr write` adopts this design as a numbered ADR under `get_adr_dir()` (rule 12).
2. `writing-plans` skill produces an implementation plan against the ADR.
3. Implementation executes against the plan in one PR with the four checkpoints above.

The brainstorming spec is not the architectural commitment — the ADR is.
