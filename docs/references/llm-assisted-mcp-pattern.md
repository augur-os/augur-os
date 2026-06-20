---
title: "LLM-Assisted MCP Tools Pattern"
status: accepted
date: 2026-03-26
tags: [architecture, mcp, llm, pattern]
---

# LLM-Assisted MCP Tools Pattern

## Problem

Some MCP tools need LLM intelligence (vision, reasoning, summarization) to fully process their input. Augur is the harness layer, so the default source of that intelligence is the active native AI client, not a hidden model call inside the tool. The tool must also work identically from any calling context: AI client session, dashboard, daemon, or cron job.

## Solution

A two-mode execution pattern where the same MCP tool adapts its behavior based on whether an AI client is present in the calling context. This is the preferred shape whenever a tool needs LLM help: prepare a handoff, let the agent reason, then validate or merge the agent-provided result.

Direct model/API access remains possible only as a rare, named exception approved in the governing ADR, command, or config with a clear credential boundary.

### Execution Flow

```
Caller → tool(file, ...)
           │
           ├─ Can I process this without LLM?
           │   YES → return result (tier 0, always works)
           │   NO ↓
           │
           ├─ Am I being called by an AI client?
           │   YES → return {needs_llm: true, data: <payload>}
           │         Caller (the AI) processes it, calls companion tool with result
           │   NO ↓
           │
           └─ Spawn configured CLI agent session
               Agent calls same tool → now "inside AI client"
               Returns result to original caller
```

### Mode 1: Inside AI Client

When the tool is called by an AI agent (Claude Code, Codex, Cowork, Ollama CLI), the agent IS the LLM. The tool returns structured data that needs LLM processing, and the agent:

1. Receives `{needs_llm: true, data: <payload>}` response
2. Processes the data (e.g., describes an image, OCRs a page, summarizes content)
3. Calls a companion tool (e.g., `submit-llm-result`) with the LLM output
4. The skill merges the LLM output with parsed content and returns the final result

### Mode 2: Outside AI Client (Dashboard, Daemon, Cron)

When no AI client is in the calling context, the tool spawns a CLI agent session:

1. Reads CLI preference from skill config (`config.yaml`)
2. Spawns the configured CLI with a focused prompt
3. The CLI session calls the same MCP tool — now executing in Mode 1
4. Results returned synchronously to the original caller

### CLI Agent Configuration

```yaml
# In skill's vault config
llm_cli:
  preferred: claude          # First choice
  fallback: ollama           # Second choice
  ollama_model: glm-ocr      # OCR model for Ollama
  timeout: 120               # Max seconds per CLI session
```

Priority resolution: `claude` CLI → `ollama run <model>` → graceful degradation (return partial result without LLM processing)

### Callback Protocol

Tools that implement this pattern expose a pair:

| Tool | Purpose |
|------|---------|
| `<tool-name>` | Main tool — returns result or `{needs_llm: true, ...}` |
| `submit-<tool-name>-result` | Companion — accepts LLM output, returns merged final result |

The companion tool is only called by AI clients in Mode 1. Dashboard/daemon callers never see it — the spawned CLI handles the full round-trip internally.

### Context Detection

Tools detect their calling context via:

```python
def is_ai_client_context() -> bool:
    """Check if an AI client is in the calling context."""
    # Check for known AI client env vars or session markers
    return bool(
        os.environ.get("CLAUDE_CODE_ENTRY_POINT")
        or os.environ.get("CODEX_SESSION")
        or os.environ.get("GEMINI_SESSION")
        or os.environ.get("AUGUR_AGENT_SESSION")  # Set by spawned CLI sessions
    )
```

## Key Properties

- **Same tool, same interface** — callers don't need to know about modes
- **No direct LLM API calls by default** — native AI-client reasoning is the normal path; direct provider calls require an approved exception
- **CLI preference is user-configurable** — not hardcoded to any provider
- **Graceful degradation** — tier 0 (no LLM) always works; LLM processing is additive
- **Batch-compatible** — multiple files processed in a single CLI session

## When to Use This Pattern

Use when an MCP tool:
- Needs LLM intelligence for a subset of its inputs (not all)
- Must work from both AI client sessions and daemon/dashboard contexts
- Should not couple to a specific LLM provider

Do NOT use when:
- The tool always needs LLM processing (use `dispatch: 'fire'` action instead)
- The LLM processing is the primary purpose (that's an action, not a tool)

## Examples

- **`document-extractor`**: Text-based PDFs parse at tier 0. Scanned PDFs and images return image data for LLM OCR via this pattern.
- **Future**: Any tool that does content analysis, classification, or summarization on a subset of inputs.
