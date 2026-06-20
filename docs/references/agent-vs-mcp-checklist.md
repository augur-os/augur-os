# Agent vs MCP Checklist

Use this checklist when designing a new Augur feature, command, loop, or integration.

The architecture rule is:

```text
trigger -> AI agent session -> MCP tools
```

Not:

```text
trigger -> background service -> internal workflow executor
```

## Core Split

- The **AI agent** is the orchestrator.
- The **MCP tools** are the hands.
- **Skill docs and commands** define workflow and policy.
- **Daemon / scheduler** only triggers sessions; it does not own the intelligence.
- The **native AI client LLM** is the default reasoning engine. Augur harnesses it; Augur code does not normally call model APIs itself.

Direct model/API access from Augur code is a rare, named exception. It must be explicitly approved by the user in the governing ADR, command, or config, state the credential boundary, and explain why a native-agent handoff is not sufficient.

## Put It In Agent Logic If It Requires Judgment

Use the agent when the work involves:

- classification
- summarization
- prioritization
- deciding what to save
- choosing which page/note/tool to update
- interpreting ambiguity
- sequencing multiple steps
- deciding what should run in parallel

Examples:

- deciding whether an `/ask` answer is a `decision` or `preference`
- deciding whether new knowledge belongs in memory, synthesis, or wiki
- deciding which wiki page should be rewritten after ingest
- deciding whether a contradiction is strong enough to promote

## Put It In An MCP Tool If It Is Atomic

Use an MCP tool when the operation is bounded and stateless:

- read one thing
- write one thing
- search one scope
- extract one file
- return one structured dataset
- perform one narrow mutation

Examples:

- `wiki-read`
- `wiki-write`
- `wiki-tags`
- `wiki-search`
- `ingest-extract`
- `vault-file-read`
- `save-synthesis`

An MCP tool should not decide the whole workflow. It should do one unit of work and return.

## Put It In Skill Docs / Commands If It Defines Policy

Use command docs and skill docs for:

- operator guidance
- command UX
- workflow steps
- retention rules
- trigger semantics
- “when to use which tool” guidance

Examples:

- `/ask` behavior and retention contract
- `/wiki update` workflow
- `/ask sync` workflow
- session-end compounding rules

This layer explains how the agent should behave. It does not replace tools or the agent.

## Put It In Daemon / Scheduler Only If It Starts Work

Use daemon/scheduler only to:

- start an AI session
- request a run
- set a flag
- schedule work

Do not put intelligence here.
Do not make the daemon the second executor.

Correct:

- nightly loop triggers an AI session
- the agent uses MCP tools

Wrong:

- daemon directly classifies content
- daemon directly rewrites wiki pages
- daemon owns business logic that the agent should own

## Put It In Dashboard Only If It Is UI Or Transport

Dashboard code should:

- dispatch to the AI session
- call MCP tools for data
- render results

Dashboard code should not:

- call LLM APIs directly
- spawn scripts directly
- implement hidden workflow logic outside the agent/tool model

## Quick Decision Test

Ask these questions in order:

1. Does this require judgment?
   - yes -> agent
2. Is this one bounded operation?
   - yes -> MCP tool
3. Is this describing how the agent should behave?
   - yes -> command doc / skill doc / rules
4. Is this only about when work starts?
   - yes -> daemon / scheduler trigger

## Red Flags

You are probably violating the architecture if:

- an MCP tool decides which other tools to call
- an MCP tool runs a whole workflow internally
- a daemon is doing intelligent work instead of triggering a session
- the dashboard bypasses agent dispatch
- MCP, dashboard, or daemon code calls a model API without an approved exception
- you add script spawning instead of exposing an MCP tool
- you need background threads in the MCP server
- you create a second orchestration layer

## Good Feature Shape

The preferred shape for new work is:

1. command or trigger defines intent
2. AI agent interprets that intent
3. AI agent calls MCP tools
4. MCP tools perform atomic work
5. AI agent decides what happens next
6. optional session-end or scheduled trigger starts another AI session later

## Reference

See also:

- [AI Client Execution Model](./ai-client-execution-model.md)
- [LLM-Assisted MCP Pattern](./llm-assisted-mcp-pattern.md)
- [Dispatch Escalation Pattern](./dispatch-escalation-pattern.md)
