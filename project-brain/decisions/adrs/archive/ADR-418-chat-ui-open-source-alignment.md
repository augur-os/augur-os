---
status: Cancelled
date: 2026-03-17
deciders:
  - Gur Sannikov
related: []
hub: core
tags: [chat, assistant-ui, copilotkit, open-source]
superseded_by: null
---

# ADR-418: Chat UI Open-Source Alignment

## Context

Augur's dashboard chat has ~3,500 lines of custom rendering code (ChatBubbleView, ChatMessageBubble, MarkdownMessage, VirtualizedMessageList, ChatInput, PromptCard, ToolApprovalCard, ErrorCard, ProgressCard). The goal was to reduce proprietary maintenance surface by adopting an open-source chat UI library.

CopilotKit was evaluated as the primary candidate but rejected — its runtime model (browser owns the LLM connection) conflicts with Augur's CLI-first architecture where the dashboard is a presentation layer and all AI execution routes through PTY/IDE agents.

assistant-ui was identified as a better fit due to its transport-agnostic, headless design. A prototype was built with ExternalStoreAdapter bridging the Zustand chatStore to assistant-ui primitives, custom ContentPart renderers for Augur's interactive cards, and a feature flag for rollback.

## Decision

**Cancelled.** The prototype revealed that the integration between assistant-ui's rendering model and Augur's PTY stream parser is more complex than estimated. The critical gap is the parser event subscription flow — ChatBubbleView internally manages its own message state from PTY events, and lifting that to feed assistant-ui's ExternalStoreAdapter requires non-trivial refactoring of the chat data flow. The feature flag wiring did not produce a working renderer in the real dashboard.

The spec and plan are preserved for future reference when the chat architecture evolves or when a post-launch revisit is warranted.

## Evaluation Summary

| System | CopilotKit Fit | assistant-ui Fit | Verdict |
|---|---|---|---|
| Chat UI rendering | Runtime conflict | Transport-agnostic | assistant-ui viable but PTY adapter complex |
| Generative UI | Requires CK runtime | N/A | Deferred — needs structured agent protocol |
| Context (Readables) | Browser-only | N/A | Skip — Augur envelopes are better |
| Action registration | React-only hooks | N/A | Skip — YAML+CLI model is more capable |
| CopilotTextarea | Requires CK runtime | N/A | Possible narrow use for vault notes |

## Consequences

### What was learned

- CopilotKit's value proposition conflicts with PTY/CLI-first architectures at the transport level
- assistant-ui's ExternalStoreAdapter is the right integration point for external state management
- The real complexity is not in the rendering layer but in the parser event → message state pipeline
- Chat architecture would need a `useParserMessages()` hook extracted from ChatBubbleView before any renderer swap is feasible

### Artifacts preserved

- Spec: `docs/superpowers/specs/2026-03-16-chat-ui-open-source-alignment-design.md`
- Plan: `docs/superpowers/plans/2026-03-17-chat-ui-open-source-alignment.md`
- Prototype branch deleted (was `feature/chat-assistant-ui`, 5 commits, ~1,050 lines)
