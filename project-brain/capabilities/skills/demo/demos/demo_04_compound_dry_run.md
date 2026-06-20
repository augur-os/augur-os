---
title: Workflow Example 04 - Compound Dry Run
type: demo-runbook
demo_id: demo_04_compound_dry_run
order: 4
pinned: true
x-augur-note-type: file
_source_type: demo-runbook
tags:
  - example
  - workflow-example
  - ask
  - wiki
  - compounding
  - dry-run
---

# Workflow Example 04 - Compound Dry Run

## Agent Prompt

Run the bounded command below so the workflow example resets, reads retained `/ask`
clusters, formats the compounding preview, and prints one judge-facing result
block without applying any wiki mutation.

```text
uv run aug demo-run-compound-preview --days-back 90 --limit 5
```

Return only the final workflow example output block from the command. Do not run ad hoc
Python, do not inspect implementation source, and do not repeat the Expected
Visible Output preview.

Create a small retained signal only if the session needs fresh context:

Use this retained seed if the session needs fresh context:

```text
/ask --retain "For workflow example preparation, what insight should Augur preserve about offline offload and cross-agent compounding?"
```

Then inspect retained compounding candidates with the bounded Augur CLI command above. If using `/wiki update`, stop at the returned batch or agent-action prompt and do not apply the concept batch.

For the live judge run, use `uv run aug demo-run-compound-preview --days-back 90 --limit 5`. It previews retained `/ask` outcomes, cluster summaries, and candidate wiki page targets without mutating wiki pages. Do not use the generic `wiki-update` backlog as the primary workflow example unless the backlog is already filtered to the workflow example topic.

Do not write ad hoc Python, inspect implementation source, or run a wiki backlog scan unless the bounded CLI command fails. The workflow example should finish from the CLI JSON by reading the first relevant cluster's `label`, `summary`, `item_count`, `priority_score`, and first `page_targets[].page`.

## Expected Visible Output

```text
Workflow Example 04 is running: we are previewing what would compound before any wiki mutation is applied.
Retained signal: existing /ask syntheses provide the workflow example signal; fresh retention is skipped for repeatability.
Compound preview: 4 retained /ask outcomes would strengthen concepts/wiki-ingest-and-compilation-commands without writing wiki pages.
Current cluster: "What pattern is emerging..." has 4 retained items, priority_score 0.843, and targets concepts/wiki-ingest-and-compilation-commands.
Safety proof: no wiki apply command was run; this is a dry run.
Human artifact: Workflow Example 04 proof card.
Open in Browse: search "Workflow Example 04 Governed Compounding Preview".
What to show: 4 retained outcomes would strengthen Wiki Ingest And Compilation Commands.
Judge takeaway: compounding is governed promotion with previewable evidence, not blind autosave.
Reset proof: workflow example reset completed before the run.
Example status: pass.
```

## Automatic Reset / Idempotency

Before running live, call `demo-run-reset` with reason `before-demo_04_compound_dry_run`.
Default to dry-run inspection only by running `uv run aug demo-run-compound-preview --days-back 90 --limit 5`. The wrapper uses `uv run aug ask-sync-clusters --days-back 90 --limit 5` internally. Skip the retained seed unless the cluster list is empty or stale for the workflow example topic. Never run `wiki-apply-concept-batch` during repeated practice unless the user explicitly changes the workflow example.

## Bounded Live Command

```bash
uv run aug demo-run-compound-preview --days-back 90 --limit 5
```

Return only the final workflow example output block. Do not replace it with a custom script when preparing the judge-facing answer.

## Live Flow

1. Click Run and let `demo-run-compound-preview` execute.
2. Search Browse for `Workflow Example 04 Governed Compounding Preview` and open the proof card.
3. Show the first relevant cluster label, summary, item count, priority score, and suggested page target from the card.
4. If `/wiki update` is used, show only the dry-run batch or agent-action prompt and call out when the backlog is unrelated to the workflow example topic.
5. Stop before `wiki-apply-concept-batch`.

## Success Criteria

- The dry run names concrete retained outcomes.
- The output says which concept or wiki page would be strengthened.
- The user can clearly say this is a preview, not a live mutation.
- The output ends with a human artifact block naming the proof-card search phrase.

## Stop Conditions

- Stop if there are no retained outcomes.
- Stop if the cluster summary is generic or unsupported.
- Stop before any apply command unless the user explicitly changes the workflow example.
- Stop if no proof card or candidate wiki target is shown.

## Judge Talking Points

- Compounding is not blind autosave.
- The system can show what would be promoted before writing durable wiki pages.
- Agents remain responsible for judgment; MCP tools expose the source clusters.
