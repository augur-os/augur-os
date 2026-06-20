---
name: document-extractor
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
x-augur-license: MIT
description: Universal document-to-Markdown extraction service. Converts PDF, Office
  docs, images, audio, and HTML to structured Markdown. Supports offline extraction
  (tier 0) and LLM-assisted OCR via the LLM-Assisted MCP pattern.
x-augur-tab: home
x-augur-requires-platform: true
x-augur-mcp-tools:
- extract-audio
x-augur-dashboard-pages: []
x-augur-dependencies:
  python:
  - markitdown[all]
  - openvino-genai
  - imageio-ffmpeg
x-augur-config-file: config.yaml
---














# Document Extractor

Universal document-to-Markdown extraction powered by MarkItDown.

## Standard core

Portable workflow guidance for this capability lives in:

- `local-document-extraction/document-to-markdown`

This skill remains the Augur adapter. It owns MCP tools, dashboard/Browse/routine
projection, path-helper access, runtime state, and real-data verification for
Augur.

## Tiers

- **Tier 0** — Pure parsing, always available offline. Handles text-based PDF, DOCX, PPTX, XLSX, HTML, CSV, JSON, plain text, and local OCR where that is enough.
- **Tier 1** — LLM-assisted OCR for scanned PDFs and images when local extraction is too weak for a structurally complex source. The gate is driven by need and extraction quality, not raw file size. Uses the LLM-Assisted MCP pattern: when called by an AI client, the agent processes the OCR requests directly; when called from daemon/dashboard, spawns a CLI agent session.

## Browse Document Actions

Browse document cards may dispatch these actions:

- `Summary` extracts readable content, summarizes it, and writes derived metadata or a sidecar without changing the original file.
- `Transcript` uses `extract-audio`; when offline mode is enabled it must use the configured local transcription backend only.
- `Describe Image` and `Extract Text` use the OCR/vision path; when offline mode is enabled they must use local OCR only.
- `Sweep` may move or rename the original file only through the sweep/hygiene MCP flow and only after high-confidence classification or user confirmation.

When the required local OCR or transcription engine is missing in offline mode, report the exact setup step, write no partial transcript/summary as success, and leave the source file unchanged.

## Architecture Pattern

See `docs/references/llm-assisted-mcp-pattern.md`.

## Additional resources

- [assets/seeds/.gitkeep](assets/seeds/.gitkeep)
- [evals/.gitkeep](evals/.gitkeep)
- [assets/seeds/_seed.yaml](assets/seeds/_seed.yaml)

## Dashboard

This skill contributes pages to the command hub.
- [augur/data/.gitkeep](augur/data/.gitkeep)
- [evals/evals.json](evals/evals.json)
- [evals/rank.json](evals/rank.json)
- [references/.gitkeep](references/.gitkeep)
- [assets/seeds/example-document-extractor.yaml](assets/seeds/example-document-extractor.yaml)
