---
title: Workflow Example 06 - Brain Manifest Architecture
type: demo-runbook
demo_id: demo_06_brain_manifest_architecture
order: 6
pinned: true
x-augur-note-type: file
_source_type: demo-runbook
tags:
  - example
  - workflow-example
  - brain
  - manifest
  - architecture
  - governance
---

# Workflow Example 06 - Brain Manifest Architecture

## Agent Prompt

Run the bounded command below so the workflow example resets, reads the real project brain
manifest and folder contract, and prints one judge-facing result block. Do not
describe the brain as hidden prompt state.

```text
uv run aug demo-run-brain-manifest
```

Return only the final workflow example output block from the command. Do not run ad hoc
Python, do not discover tool implementations, and do not repeat the Expected
Visible Output preview.

The output starts with:

```text
Workflow Example 06 is running: we are showing that an Augur brain is a portable, inspectable architecture surface, not a hidden prompt folder.
```

Inspect these real files and folders:

```text
project-brain/BRAIN.yaml
project-brain/README.md
project-brain/capabilities/skills/
project-brain/knowledge/
project-brain/instructions/
project-brain/decisions/adrs/
project-brain/workflows/
```

Return the visible result in this shape:

```text
Brain manifest: <id, type, root, attached_project>
Architecture proof: <one sentence explaining what the manifest controls>
Folder contract: <skills, knowledge, instructions, decisions, workflows>
Separation proof: <personal brain and project brain are distinct>
Investor answer: <one crisp answer to "what is a brain?">
Example status: <pass|partial-pass|fail>
```

Use `partial-pass` if any expected folder is missing or if the active brain
cannot be tied back to `project-brain/BRAIN.yaml`.

## Expected Visible Output

```text
Workflow Example 06 is running: we are showing that an Augur brain is a portable, inspectable architecture surface, not a hidden prompt folder.
Brain manifest: project-augur, type project, root '.', attached_project '..'.
Architecture proof: the manifest binds this portable brain folder to the Augur repository instead of relying on hidden agent state.
Folder contract: capabilities/skills holds executable skills, knowledge holds memory/wiki/source material, instructions holds agent behavior, decisions/adrs holds architecture history, and workflows holds repeatable procedures.
Separation proof: the project brain is project-augur under project-brain, while the personal brain remains a separate personal vault.
Investor answer: a brain is a governed workspace that agents can read, update, project into native clients, and audit as files.
Human artifact: Workflow Example 06 proof card.
Open in Browse: search "Workflow Example 06 Brain Manifest Architecture".
What to show: BRAIN.yaml, capabilities/skills, knowledge, instructions, decisions/adrs, and the personal brain separation.
Reset proof: workflow example reset completed before the run.
Example status: pass.
```

## Automatic Reset / Idempotency

Before running live, call `demo-run-reset` with reason `before-demo_06_brain_manifest_architecture`.
After that preflight, this workflow example is read-only after preflight: inspect the manifest and folders without writing files, pins, settings, or retained memory.

## Bounded Live Command

```text
uv run aug demo-run-brain-manifest
```

Return only the final workflow example output block. Do not replace this command with manual
tool discovery or a custom script.

## Live Flow

1. Click Run and let `demo-run-brain-manifest` execute.
2. Open `project-brain/BRAIN.yaml`.
3. Explain each manifest field: `schema_version`, `id`, `type`, `root`,
   `attached_project`, and `description`.
4. Open `project-brain/README.md`.
5. Show the standard root files and the folder contract.
6. Show the core folders: `capabilities/skills`, `knowledge`, `instructions`,
   `decisions/adrs`, and `workflows`.
7. End on the `Human artifact` block: proof card and folder contract.
8. Search Browse for `Workflow Example 06 Brain Manifest Architecture` to show
   the workflow example is itself a normal brain card.

## Success Criteria

- The workflow example uses the real `project-brain/BRAIN.yaml`.
- The answer explains why the brain is more than a prompt folder.
- The folder contract names concrete folders and their roles.
- The project brain and personal brain separation is explicit.
- The workflow example stays under two minutes and does not mutate files.
- The final output names the proof-card search phrase and concrete relative files/folders to show.

## Stop Conditions

- Stop if `project-brain/BRAIN.yaml` is missing.
- Stop if the folder contract cannot be shown from real files.
- Stop if the explanation drifts into generic "AI memory" language without
  naming the manifest and folders.
- Stop if the final output does not include a Browse-searchable proof card and at least one real folder to show.

## Judge Talking Points

- A brain is a file-backed control surface for agents.
- `BRAIN.yaml` gives the brain identity, type, root, and project attachment.
- Skills, memory, instructions, decisions, and workflows live in inspectable
  folders.
- Personal and project brains stay separated, which is the governance story.
