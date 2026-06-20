---
title: Workflow Example 02 - Discover GUI And Web Capture
type: demo-runbook
demo_id: demo_02_discover_gui_web_capture
order: 2
pinned: true
x-augur-note-type: file
_source_type: demo-runbook
tags:
  - example
  - workflow-example
  - discover
  - keep
  - browse
  - web-capture
---

# Workflow Example 02 - Discover GUI And Web Capture

## Agent Prompt

Run the bounded command below so the workflow example executes the real command registry,
captures or reuses the fixed webpage, verifies Browse search, and prints one
judge-facing result block.

```text
uv run aug demo-run-discover-capture
```

Return only the final workflow example output block from the command. Do not run ad hoc
Python, do not discover tool implementations, and do not repeat the Expected
Visible Output preview.

Underlying command sequence shown by the wrapper:

```text
/discover --commands
/keep https://www.iana.org/domains/reserved
```

Use the fixed IANA reserved-domains page for every practice run. After `/keep` returns the saved source card, open Browse and search for `IANA-managed Reserved Domains` or `www.iana.org`.

## Expected Visible Output

```text
Workflow Example 02 is running: we are showing the command surface and turning a webpage into searchable brain material.
Command surface: <real command count> are exposed from the real Augur command registry.
Saved webpage: IANA-managed Reserved Domains is searchable in Browse.
Human artifact: Workflow Example 02 proof card.
Open in Browse: search "Workflow Example 02 Command Surface Web Capture".
What to show: Discover command list, then the saved page from Browse search "IANA-managed Reserved Domains".
Judge takeaway: GUI commands, slash commands, and file-backed evidence are one shared surface.
Reset proof: workflow example reset completed before the run.
Example status: pass.
```

## Automatic Reset / Idempotency

Before running live, call `demo-run-reset` with reason `before-demo_02_discover_gui_web_capture`.
Use `https://www.iana.org/domains/reserved` as the fixed judge-safe URL for practice runs. Before writing a new capture, search Browse for `IANA-managed Reserved Domains` or `www.iana.org` and dedupe or refresh the existing source card when it already exists. Only create a new card when there is no matching existing source card.

## Bounded Live Command

```text
uv run aug demo-run-discover-capture
```

Return only the final workflow example output block. Do not replace this command with manual
tool discovery or a custom script.

## Live Flow

1. Click Run and let `demo-run-discover-capture` execute.
2. Point at the command-group count.
3. Search Browse for `Workflow Example 02 Command Surface Web Capture` and open the proof card.
4. Search Browse for `IANA-managed Reserved Domains` or `www.iana.org`.
5. Open the saved webpage card and show extracted content.
6. End on the `Human artifact` block: proof card, Browse search phrase, and readable page title.

## Success Criteria

- `demo-run-discover-capture` displays real command registry group count.
- The fixed webpage is saved or deduped as a real source card.
- Browse search finds the captured webpage.
- The result is a normal Browse card.
- The output names the proof-card search phrase the presenter can open.

## Stop Conditions

- Stop if the webpage cannot be captured.
- Stop if Browse search cannot find the saved title or domain.
- Stop if the card has no useful extracted content.
- Stop if the final output does not include a Browse-searchable proof card.

## Judge Talking Points

- Augur exposes the supported command surface instead of relying on hidden prompts.
- Web capture becomes local searchable brain material.
- Browse is the shared GUI over files, commands, and evidence.
