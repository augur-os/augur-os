# Agent vs MCP Examples

Concrete examples of good and bad implementations using Augur's intended execution model.

Use this alongside:

- [Agent vs MCP Checklist](./agent-vs-mcp-checklist.md)
- [AI Client Execution Model](./ai-client-execution-model.md)

## Example 1: `/ask` Retention

### Good

- `/ask` command defines the retention workflow
- agent answers the question
- agent classifies the outcome as `decision`, `preference`, `insight`, or `inferred-pattern`
- agent calls:
  - `memory-log-decision`
  - `memory-log-preference`
  - `save-synthesis`
- session-end compounding later decides whether to rewrite wiki pages

Why this is correct:

- the agent does the reasoning
- tools do the atomic writes
- wiki updates remain compiled, not chat-shaped

### Bad

- `save-synthesis` decides which wiki page to update
- `save-synthesis` appends directly into wiki pages
- `/ask` writes wiki pages in the same step as the answer

Why this is wrong:

- tool owns orchestration
- wiki becomes too reactive
- the workflow bypasses the agent’s judgment layer

## Example 2: Ingesting A New PDF

### Good

- user drops PDF into the dashboard
- dashboard dispatches to IDE agent
- agent decides:
  - extract content
  - classify destination
  - route file
  - decide if wiki should be updated
- agent calls:
  - `ingest-extract`
  - `ingest-rename`
  - `ingest-route`
  - later `wiki-tags` / `wiki-read` / `wiki-write` if warranted

### Bad

- dashboard uploads PDF
- server action directly spawns a Python script
- script classifies content, moves files, rewrites wiki pages, and updates indexes in one internal workflow

Why this is wrong:

- bypasses agent orchestration
- creates a hidden second execution model
- makes behavior inconsistent across dashboard vs CLI

## Example 3: Nightly Wiki Maintenance

### Good

- daemon or scheduler triggers an AI client session
- the agent runs `/auto-wiki-maintenance`
- agent decides what needs refresh
- agent calls:
  - `wiki-tags`
  - `wiki-scan-sources`
  - `wiki-read`
  - `wiki-write`
  - `wiki-log`

### Bad

- daemon directly scans vault
- daemon diffs pages vs sources
- daemon rewrites wiki markdown itself without an AI session

Why this is wrong:

- daemon became a second orchestrator
- intelligence moved out of the AI session
- workflow is now split between two architectures

## Example 4: Dashboard Action Button

### Good

- button uses `dispatch: 'ide'`
- action opens or routes to an AI client session
- agent uses MCP tools to do the work
- dashboard shows results from MCP-backed state

### Bad

- button calls `/api/run-script`
- API route runs `execSync("python ...")`
- script mutates files directly

Why this is wrong:

- bypasses MCP
- bypasses the AI agent
- breaks the shared execution path the repo is designed around

## Example 5: Search And Synthesis

### Good

- user runs `/search`
- agent retrieves context
- agent synthesizes the answer
- if the result is valuable, agent offers or triggers `save-synthesis`
- later compounding may promote it into wiki updates

### Bad

- search tool automatically saves every answer
- search tool decides that a result is important
- search tool writes both a note and wiki changes without the agent deciding

Why this is wrong:

- tool is making retention decisions
- persistence becomes noisy
- every answer becomes sticky whether or not it deserves to be

## Example 6: New Feature Design

Question:

“Should this live in the agent or in an MCP tool?”

### Good reasoning

- “This needs judgment about whether the output is durable, so the agent should decide.”
- “The write itself is just a single markdown mutation, so that part should be an MCP tool.”

### Bad reasoning

- “We can put everything in one tool so it’s easier.”
- “The daemon can decide this when the user is offline.”

Why this is wrong:

- convenience is creating architecture drift
- it hides orchestration in the wrong layer

## Example 7: Contradiction Handling

### Good

- agent detects that a new `/ask` inference conflicts with older memory
- agent retains both sides as a tension
- future compounding decides whether one becomes canonical

### Bad

- tool sees a new value and overwrites the old one immediately

Why this is wrong:

- atomic tool is making semantic decisions
- memory becomes brittle and loses history

## Quick Smell Test

If you can describe the feature as:

- “the agent decides, the tools execute”

it is probably aligned.

If you find yourself describing it as:

- “the script/tool/daemon figures it out and then does everything”

it is probably violating the architecture.
