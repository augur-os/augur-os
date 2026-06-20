---
name: document-to-markdown
description: Use when converting local documents, PDFs, Office files, images, HTML, or audio into Markdown or agent-readable text using local tools and explicit user-provided files.
---

# Document to Markdown

## Operating Contract

- Work from user-provided local files, folders, or extraction reports.
- Use local CLIs and deterministic scripts for PDF, Office, image, HTML, and audio inspection when available.
- Do not call hosted model providers from scripts.
- Leave OCR judgment, cleanup choices, and ambiguous interpretation to the active AI client.
- Keep platform-specific MCP, dashboard, runtime, and generated-client behavior in an adapter.

## Workflow

1. Inspect the local input type, file readability, and dependency availability.
2. Produce deterministic local evidence, extracted Markdown, or structured text output.
3. Ask for approval before destructive file changes, outbound network actions, or irreversible conversions.
4. Report missing dependencies directly instead of fabricating extraction output.
