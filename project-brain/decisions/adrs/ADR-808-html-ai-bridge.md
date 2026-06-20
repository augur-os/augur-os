---
status: Accepted
date: 2026-06-09
deciders:
  - gsannikov
related:
  - ADR-807
  - ADR-806
hub: null
tags:
  - actions
  - pages
  - bridge
  - security
superseded_by: null
spec_file: 2026-06-09-augur-category-action-refactor-design.md
plan_file: 2026-06-09-actions-p3-html-ai-bridge.md
---

# ADR-808: Constrained HTML→AI bridge for Pages mini-apps

## Decision summary

A button inside a user-authored HTML mini-app (the Browse "Pages" artifact iframe) can reach an
AI agent through a constrained `window.augur` bridge exposing exactly two verbs: `augur.ask(prompt)`
(opens the chat dock as a human-confirmed draft) and `augur.runAction(actionId)` (dispatches a
DECLARED action of the artifact's owning skill only). Nothing else is exposed.

The artifact iframe is sandboxed at an opaque origin (`sandbox="...allow-scripts"`, no
`allow-same-origin`), so `postMessage` is the only cross-boundary channel. The `window.augur` shim
is injected server-side into the raw artifact HTML response (`/api/artifact/[slug]/raw`); a parent
listener in `ArtifactChrome` validates the sender (`event.source === iframe.contentWindow`, opaque
`event.origin === "null"`) and routes `augur:ask` → `openChat` and `augur:runAction` → an
owning-skill-scoped `list-skill-actions` lookup + dispatch. HTML cannot reach arbitrary MCP tools,
another skill's actions, or the parent React tree. Artifacts with no owning `skill` cannot use
`runAction` (only `ask`).

This completes the Actions workstream (ADR-806 retired the dead pipeline; ADR-807 unified the
action model; this ADR lets Pages mini-apps drive AI agents safely — "pages = fast actions").

## Status notes

Implemented by `docs/superpowers/plans/2026-06-09-actions-p3-html-ai-bridge.md`. Verified end-to-end:
a real mini-app button calling `augur.ask(...)` opened the chat dock pre-filled with the prompt as a
human-confirmed draft (browser, real served artifact); handler/injector unit-tested (9 jest tests).

## Related

- ADR-807 (unified action model — augur/actions.yaml; the source runAction looks up)
- ADR-806 (retired the dead FILE-actions pipeline)
