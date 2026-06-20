---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- llm
- assisted
- retry
superseded_by: null
---

# ADR-106: LLM-Assisted Retry

**Date:** 2026-02-16
**Implementation Date:** 2026-02-16
**Related:** ADR-076 (AI self-healer), ADR-084 (fail-fast self-heal), ADR-063 (MCP hardening)

## Context

Several Augur components have retry loops that fail blindly — they repeat the same action hoping for a different result without understanding *why* the failure occurred:

| Component | File | Retry Pattern | Problem |
|-----------|------|---------------|---------|
| Workflow engine | `stage_runner.py` | Retry from PLAN phase up to `max_retries` | Replans blind — no knowledge of why previous execution failed |
| Parallel executor | `parallel_executor.py` | Retry step up to `step.retries` | Retries identical action on timeout/exception |
| MCP bridge | `MCPBridge.ts` | Reconnect up to 3 times with 2s delay | Reconnects without diagnosing server crash cause |

Meanwhile, `ai_self_healer.py` already has a working pattern: it invokes a headless CLI to classify errors and produce fix strategies. This capability is not available to the retry loops above.

## Decision

### Shared LLM-retry utility in `src/lib/llm_retry.py` (Python) and `src/dashboard/lib/llm-retry.ts` (TypeScript)

Extract `resolve_cli()` from `ai_self_healer.py` into a src/lib module. Add a `diagnose_with_llm()` function that:

1. Takes the component name, list of previous attempt errors, and optional context
2. Builds a diagnosis prompt asking the LLM to return structured JSON with `root_cause`, `suggestion`, and `should_retry` fields
3. Invokes the CLI via subprocess (`--print --max-turns 1`)
4. Parses the JSON response
5. Logs the event to `runtime/llm_retry_events.jsonl`

### Configuration in `config/system/llm.yaml`

New `llm_retry` section controls behavior:

```yaml
llm_retry:
  enabled: true           # Kill switch — false = zero overhead
  trigger_attempt: 3      # Only invoke LLM after N failed attempts
  timeout_s: 90           # Max time for LLM diagnosis call
  cli: auto               # CLI binary — auto-detected or explicit
  mode: diagnose          # diagnose = advise only, fix = attempt repair
  components:             # Per-component opt-in
    workflow_engine: true
    parallel_executor: true
    mcp_bridge: true
```

### Integration points

- **`stage_runner.py`**: After incrementing `retry_count`, if count >= `trigger_attempt`, call `diagnose_with_llm()`. Feed the diagnosis `suggestion` into the retry context so the PLAN phase can incorporate it.
- **`parallel_executor.py`**: Track attempt logs in the while-loop. When `retries == trigger_attempt`, call `diagnose_with_llm()` and enrich the context dict for the next retry.
- **`MCPBridge.ts`**: Track reconnect attempt logs. When `reconnectAttempts === triggerAttempt`, call `diagnoseWithLLM()` async (non-blocking, does not delay reconnect).

### Event logging

All LLM retry events are appended as JSONL to `runtime/llm_retry_events.jsonl`, following the same atomic-append pattern as `self_heal_event.py` (ADR-084). Each event includes timestamp, component, attempt number, error context, and LLM diagnosis.

## Consequences

### Positive

- Retry loops gain diagnostic intelligence — instead of blind repetition, the system understands failure root causes
- Shared utility eliminates duplication of CLI resolution logic across modules
- `trigger_attempt` threshold means LLM is only invoked after initial cheap retries fail — no overhead for transient errors
- Per-component and global kill switches allow gradual rollout
- JSONL event log enables post-hoc analysis of retry patterns

### Negative

- Adds subprocess dependency to retry paths (mitigated by timeout and non-blocking mode)
- LLM diagnosis adds latency on the Nth attempt (acceptable since earlier attempts already failed)
- Requires CLI binary available on PATH (same constraint as self-healer)

### Risks

- LLM diagnosis could be wrong — `mode: diagnose` means it only advises, never auto-fixes
- CLI binary might not be installed — graceful fallback to standard retry behavior
