---
name: typed-link-extraction
description: Use when extracting typed relationships from Markdown links, frontmatter, citations, and local note structure into a deterministic file-first graph.
---

# Typed Link Extraction

## Operating Contract

- Work from user-provided local Markdown files, folders, frontmatter exports, citation lists, or graph reports.
- Use local CLIs and deterministic scripts for parsing links, frontmatter, citations, and note structure when available.
- Do not call hosted model providers from scripts.
- Leave relationship taxonomy choices, ambiguous edge review, and graph interpretation to the active AI client.
- Keep platform-specific MCP, dashboard, runtime, and generated-client behavior in an adapter.

## Workflow

1. Inspect the local Markdown inputs, link conventions, frontmatter shape, citation style, and dependency availability.
2. Produce deterministic local evidence, typed edge files, or structured graph reports.
3. Ask for approval before destructive edits, outbound graph export, or rewriting source notes.
4. Report missing dependencies directly instead of fabricating graph output.
