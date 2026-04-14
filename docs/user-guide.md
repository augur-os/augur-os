# User Guide

Augur is in soft launch. Native macOS support is implemented. Native Windows architecture is implemented, but Windows validation is still pending before a firmer public support claim.

This guide is the short public tour of Augur: what it is, how to use it, and what to expect from the current release surface.

## What Augur Is

Augur is a local-first AI workspace. It gives your AI clients a shared skill layer, a persistent knowledge base, and a local dashboard.

Use it when you want to:

- capture information in plain text files or connected apps
- process that information through skills and MCP tools
- keep the resulting state local and reviewable
- search, organize, and reuse the same knowledge over time

## Typical Workflow

1. Add something to a skill inbox or another supported capture source.
2. Run the relevant skill or workflow.
3. Review the processed result in the local dashboard, files, or connected client.
4. Repeat the same pattern for jobs, notes, reading, research, or automation.

The important idea is consistency: capture first, process second, store locally, then query later.

## Platform Status

Augur is currently best described as a soft-launch project.

- macOS is the fully implemented native path today.
- Windows has a native architecture in place.
- Windows validation is still pending before the public support story becomes firmer.

If you are evaluating Augur on Windows, follow the current validation docs rather than assuming every macOS workflow is already equally validated there.

## What To Use First

Start with the repo-first workflow and the dashboard.

- Clone the repo and install dependencies from the project root.
- Launch the dashboard locally.
- Use the command and skill docs to discover the workflow you need.
- Keep your own notes, documents, and generated outputs in the repo-managed locations described by the setup docs.

## Good Starting Points

- [Getting Started](getting-started.md)
- [Developer Guide](developer-guide.md)
- [Creating Skills](creating-skills.md)
- [Architecture Overview](architecture-overview.md)
- [Windows Installation Guide](guides/installation-windows.md)

## When A Skill Feels Close But Not Quite Right

Augur is designed around small, composable skills. If a skill does most of what you need, use it as the starting point and adjust the workflow rather than looking for a single monolithic app.

If you are unsure where to begin, use the dashboard or the repo search tools to find the closest skill, then follow its docs.
