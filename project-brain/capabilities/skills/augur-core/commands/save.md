---
description: Save files and generated assets into the correct skill-owned location.
visibility: core
x-augur-export-command: false
---

> **Retired primary surface:** `/save` is no longer exported to primary AI
> clients. Use `/keep --save <file>` or `/keep artifact <path>` instead.

# /save

Save files, images, PDFs, or generated output into the correct skill-owned location.

## What It Does

1. Identifies the content to save from the current conversation.
2. Detects or confirms the target skill.
3. Resolves the correct destination under that skill.
4. Writes the file through the normal file tools.
5. Triggers follow-up indexing when needed.
6. Emits typed knowledge-graph edges for any Markdown (`.md`) save (ADR-738).

## Usage

```bash
/save
/save --to project-augur report.md
/save banner.png to venture
/save report.pdf
```

## Rules

- Prefer explicit skill targeting when the destination is ambiguous.
- Accept `--to <brain-id>` for explicit brain write routing. When omitted, use
  active project brain from cwd, then personal fallback.
- Save assets inside the owning skill, not the repo root.
- Use the correct asset subfolder for file type.
- Trigger reindexing only after the write succeeds.
- After a successful Markdown (`.md`) save, you MUST call the `graph-extract` MCP
  tool with the saved path and `source_type=note` so the typed knowledge graph
  (ADR-738) picks up the new edges. Binary assets (images, PDFs) emit no edges —
  skip the call for them.

## Common Cases

- images -> skill assets image folder
- reports -> skill assets reports folder
- text drafts -> the owning skill's content or post data path
- generated output -> the owning skill's assets or managed data path

## Artifact Mode

`/save artifact <source-path> [--hub <name>] [--slug <slug>] [--title "..."] [--tags a,b,c]`

Promotes a single HTML file into Au-docs/<hub>/artifacts/<slug>.html with a sidecar.
Use this for Claude-generated brainstorm HTMLs you want to keep, or for static HTMLs
you want surfaced in Browse.

The implementation calls the `save-artifact` MCP tool on the augur-framework server:

- `source_path`: absolute or repo-relative path to the HTML.
- `hub`: one of the 9 hubs (adaptive, brain, business, career, command, dev, life, studio, websites). Required.
- `slug`: optional; auto-derived from title or filename when omitted.
- `title`: optional; auto-derived from the `<title>` tag, then `<h1>`, then filename.
- `tags`: optional comma-separated list.

After the tool returns, surface the new artifact at `/artifact/<slug>` and confirm
in the response that the sidecar is at `<target>.meta.yaml`.
