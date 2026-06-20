# Brain UI Federation And Memory Review Plan

## Goal

Expose multi-brain state in the dashboard and provide a clear memory review
workflow.

## Tasks

### Task 1: Brain Discovery Data API

- Add MCP/API surfaces for registered brains, discovered project brains,
  projection status, index status, and git arrangement.
- Add real-data tests against the local registry and a temp cloned project.

### Task 2: Brain Settings/Onboarding UI

- Add a brain discovery/settings surface.
- Show current project status and an `augur init` action.
- Show registered brain list with type, root, git arrangement, and projection
  status.

### Task 3: Federated Read Metadata

- Ensure search/Browse/wiki/list records include `brain_id`.
- Add brain badge metadata to existing card models.
- Keep Browse on the existing file-card mechanism.

### Task 4: Filters And Focus Mode

- Add brain filters for All, Personal, Current Project, and Team.
- Add focus mode that hides non-active brains without changing write
  destination.

### Task 5: Memory Review Product

- Add a review queue for candidate facts from client-native memory summaries,
  logs, `/ask retain`, and agent-curated observations.
- Add approve/reject actions.
- Write approved items into `<brain-root>/knowledge/memory/entries/`.

### Task 6: Browser Verification

- Verify the real dashboard shows real registered brains.
- Verify a real cloned-project scenario.
- Verify brain badges on real records.
- Verify one approved memory candidate lands in the selected brain.

## Acceptance Criteria

- Users can see every registered/detected brain.
- Users can tell whether AI-client projections are current.
- Federated views are visibly attributed by brain.
- Memory promotion is explicit, reviewed, and written to canonical brain memory.
