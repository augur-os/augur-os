# Vibe coding with Augur

> If you've never seen Augur before, read [what-is-augur.md](./what-is-augur.md) first — it explains what Augur is and isn't in five minutes.

## What "vibe coding" means here

Vibe coding is building primarily by directing an AI client — you describe intent, the agent writes and runs the code, and you steer rather than type every line. It is fast and fluid, and it works best when the agent has durable context to draw on and a human reviewing what comes back.

## How Augur helps

Augur is the local harness underneath your AI client, so the agent isn't starting cold each session:

- **Durable context** — your vault, compiled wiki, and memory persist across sessions and projects, so the agent already knows your setup, decisions, and prior work.
- **Reusable skills** — expertise you write once in `project-brain/capabilities/skills/` is available as named workflows the agent can invoke instead of improvising.
- **MCP tools** — atomic operations (search, ingest, extract, save) run through one local MCP server, so the agent acts on real local state rather than guessing.
- **One brain across clients** — the same effective context works in Claude Code, Codex, Gemini, Cursor, and Copilot. Switch clients for the job at hand without rebuilding your setup.

## A safe loop

1. **Ingest context** — bring the relevant documents, notes, and prior work into the brain so the agent retrieves from real material.
2. **Ask / build** — direct the agent to answer, draft, or implement.
3. **Review** — read and test what comes back before you depend on it. This step is not optional.
4. **Keep what's good** — persist the useful output (a prompt, a skill, a note, a decision) so the next session compounds on it.

## ⚠️ Warning

- **AI-generated code and output must be reviewed and tested.** The agent can be confidently wrong. Treat its output as a draft from a fast but fallible collaborator, not a finished answer.
- **Augur is pre-1.0 soft launch.** Expect rough edges and breaking changes. Pin versions and check the [Roadmap](../ROADMAP.md) before depending on anything.
- **Mind secrets and private data.** Be deliberate about what context you feed the agent and which client (and model) processes it.
- **No guarantees.** Augur makes no guarantee of correctness or security. You own the review.

## Links

- [Quick Start](../README.md#quick-start)
- [Getting Started](./getting-started.md)
- [What is Augur?](./what-is-augur.md)
- [Roadmap](../ROADMAP.md)
