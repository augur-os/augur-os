---
title: Workflow Example 01 - Wiki LLM Cross-Agent Ask
type: demo-runbook
demo_id: demo_01_wiki_llm_cross_agent_ask
order: 1
pinned: true
x-augur-note-type: file
_source_type: demo-runbook
tags:
  - example
  - workflow-example
  - ask
  - wiki
  - compounding
  - cross-agent
---

# Workflow Example 01 - Wiki LLM Cross-Agent Ask

## Agent Prompt

For the Run button, do not execute the free-form `/ask` workflow directly. Use the bounded command below so the workflow example starts cleanly, avoids tool discovery noise, and prints one judge-facing bottom line.

Run this exact bounded command:

```text
uv run aug demo-run-wiki-ask --days-back 90 --limit 5
```

Return only the final workflow example output block from the command. Do not run ad hoc Python, do not grep for tool implementations, do not import internal modules, and do not call `reflect-context` directly.

The cross-agent live variant, when explicitly shown outside the Run button, is:

```text
/ask --retain "What pattern is emerging in how I want Augur's wiki to compound and learn from me over time?"
```

Answer from real reflected context. Do not invent wiki state. If context is weak, say what source is missing. After the answer, retain the outcome only when `--retain` is explicitly used in the native agent chat.

Then inspect retained outcomes with:

```text
uv run aug ask-sync-clusters --days-back 90 --limit 5
```

Return the visible result in this shape:

```text
Answer: <one sentence>
Evidence: <real retained cluster and candidate wiki page>
Confidence: <high|medium|low with reason>
Retained: <yes/no and target brain or failure>
Compounding preview: <cluster and candidate wiki page>
Reset proof: <reset reason and state>
Example status: <pass|partial-pass|fail>
```

Use `partial-pass`, not `pass`, when reflected context reports stale-primary-source, stale-source-present, missing source basis, or an unrelated identity such as `adaptive-engine-daemon`.

## Expected Visible Output

```text
Workflow Example 01 is running: we are proving cross-agent wiki compounding from the shared Augur brain.
Answer: Augur turns repeated /ask answers into source-backed wiki concepts that other agents can reuse.
Evidence: ask-sync-clusters returned 4 retained items for the wiki-compounding cluster.
Human artifact: Workflow Example 01 proof card.
Open in Browse: search "Workflow Example 01 Cross-Agent Wiki Compounding".
What to show: Wiki Ingest And Compilation Commands, backed by 4 retained /ask outcomes.
Judge takeaway: Codex and Claude can compound into the same governed brain instead of isolated chat memory.
Reset proof: workflow example reset completed before the run.
Example status: pass.
```

## Automatic Reset / Idempotency

Before running live, call `demo-run-reset` with reason `before-demo_01_wiki_llm_cross_agent_ask`.
After reset, inspect existing retained clusters first. To keep repeated practice runs clean, skip the retained seed unless fresh retention is explicitly needed for this run. If fresh retention is used, call it out in the final output and verify the new retained item appears in `ask-sync-clusters`.

## Bounded Live Command

```text
uv run aug demo-run-wiki-ask --days-back 90 --limit 5
```

Do not run ad hoc Python. Do not search for implementations. Do not import internal modules. Return only the final workflow example output block.

## Live Flow

1. Click Run and let the bounded command print the clean workflow example result.
2. Search Browse for "Workflow Example 01 Cross-Agent Wiki Compounding" and open the proof card.
3. Show the retained cluster evidence and candidate wiki page from the card.
4. If the judges ask for the cross-agent proof, run the `/ask --retain ...` command once in Codex and once in Claude.
5. Inspect retained outcomes with `uv run aug ask-sync-clusters --days-back 90 --limit 5`.
6. Point at the candidate compounding signal for the wiki.

## Success Criteria

- The Run button executes `uv run aug demo-run-wiki-ask --days-back 90 --limit 5`.
- The command resets the rehearsal note before reading retained clusters.
- The output names the retained cluster count and candidate wiki target.
- The output ends with a human artifact block naming one proof card to search in Browse.
- The final line is `Example status: pass.` when the cluster exists.
- No search, ad hoc Python imports, or obsolete internal API calls are visible to the user.

## Stop Conditions

- Stop if `demo-run-reset` fails.
- Stop if `ask-sync-clusters` returns no wiki-compounding cluster.
- Stop if the command cannot distinguish Augur wiki compounding from generic note search.
- Stop if the output does not name a Browse-searchable proof card.

## Judge Talking Points

- The LLM is not just answering; the answer becomes future brain material.
- The same brain contract is available across Codex and Claude.
- Compounding is explicit and inspectable instead of hidden in one chat vendor.
