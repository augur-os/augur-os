---
status: Accepted
date: 2026-06-09
deciders:
  - gsannikov
related:
  - ADR-806
  - ADR-805
hub: null
tags:
  - actions
  - browse
  - skills
  - scheduler
superseded_by: null
spec_file: 2026-06-09-augur-category-action-refactor-design.md
plan_file: 2026-06-09-actions-p2-unify-action-model.md
---

# ADR-807: Unified action model (one augur/actions.yaml per skill)

## Decision summary

After ADR-806 retired the dead FILE-actions pipeline, the live action surfaces were still
fragmented across `augur/browse-actions.yaml` (card buttons), `SKILL.md` `contributions.actions[]`
(page action bars), and per-skill `schedules/` + `actions/*.yaml` (daemon). This ADR unifies them
into ONE `{skill}/augur/actions.yaml` declaration with a `surfaces` field (`card` / `page` / `html`),
consumed by the existing Browse-card baker and the `useActionRunner` dispatch.

Resolved design decisions:
- **Fork 1 — card binding:** generic per-category buttons (Overview/Explain) are defined ONCE as
  baker defaults (genericized with `{title}`/`{path}` placeholders); `augur/actions.yaml` holds a
  skill's OWN runnable actions. `browse-actions.yaml` is removed.
- **Fork 2 — single fire contract:** every `dispatch: fire` action is `kind: mcp` + `mcp_tool`.
  `execute-fast-action` (which read a never-present `config/action_buttons.yaml`) and its
  `runFire`/scheduler fallbacks are removed.
- **Fork 3 — modals:** a modal action's entry moves to `augur/actions.yaml` (`dispatch: modal` +
  `modal: <id>`); its form schema stays in `contributions.modals`.
- **Fork 4 — self-describing schedule:** a scheduled action carries a `schedule:` block in its
  `augur/actions.yaml`; the daemon discovers schedules from there and keeps computed runtime state
  (`next_run`/`last_run`/`run_count`) in `~/Library/Application Support/Augur/state/schedules`,
  never written back into the version-controlled action file.

`list-skill-actions` now reads `augur/actions.yaml` (page surface) with full field passthrough;
`contributions.actions[]` is removed from SKILL.md files.

## Status notes

Implemented by `docs/superpowers/plans/2026-06-09-actions-p2-unify-action-model.md`.

## Related

- ADR-806 (retired the dead FILE-actions pipeline)
- ADR-805 (native-first skillify — skills as the unit)
