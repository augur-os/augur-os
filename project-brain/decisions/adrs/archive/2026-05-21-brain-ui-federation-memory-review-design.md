# Brain UI Federation And Memory Review Design

Date: 2026-05-21

## Context

Once brain roots and client projections are canonical, users need visibility.
They should see which brains are registered, which project brains are discoverable
from cloned repos, whether projections are current, and which brain a record
belongs to.

Memory also needs a clear product split. AI clients may keep their own native
memory. Augur should not copy raw client memory into runtime folders or make
multiple memory layers visible to users. Instead, Augur should expose a review
surface where useful cross-client facts can be promoted into canonical brain
memory entries.

## Goals

- Add UI discovery for registered and detected brains.
- Show projection/index status per brain.
- Add brain badges to records that can appear in federated views.
- Add filters/focus mode for personal/team/project read sets.
- Add a memory review product that treats client-native memory as input, not
  canonical state.
- Keep canonical memory under `<brain-root>/knowledge/memory/`.

## Brain Discovery UI

The UI should show:

- registered brains from `brains.yaml`
- detected project brains from cwd/project scanning
- missing/unregistered project brains in cloned repos
- projection status per supported AI client
- index/search status per brain
- git arrangement and sync status per brain

The primary onboarding action is `augur init` for the current project.

## Federation UI

Federated records must carry immutable `brain_id`. UI surfaces should render a
brain badge wherever records from multiple brains can appear together.

Read controls:

- All brains
- Personal
- Current project
- Team
- Focus mode: hide all non-active brains for screen sharing

Write controls remain separate from read filters and must use the destination
selector from ADR-771.

## Memory Review

Memory types:

- **Client-native memory:** owned and stored by the AI client.
- **Brain memory:** canonical reviewed memory under
  `<brain-root>/knowledge/memory/`.
- **Profile:** canonical profile facts under `<brain-root>/profile/`.
- **Logs/activity:** chronological activity under `<brain-root>/activity/` or
  OS logs, depending on durability.
- **Notes/sources:** captured content under `<brain-root>/knowledge/notes` and
  `<brain-root>/knowledge/sources`.

The memory review UI imports summaries or candidate facts from client-native
memory, never raw uncontrolled client stores. The user or agent must approve
promotion into canonical brain memory.

## Verification

- Browser verification must show real registered brains and real projection
  status, not placeholder cards.
- A cloned repo with existing `project-brain/BRAIN.yaml` appears as a detected
  project brain and can be registered.
- Federated views show brain badges on real records.
- Memory review shows candidate facts and writes an approved canonical memory
  entry into the selected brain.
