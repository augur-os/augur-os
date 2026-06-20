---
status: Implemented
date: '2025-01-01'
deciders:
- Core team
related: []
hub: null
tags:
- three
- layer
- architecture
- reasoning
- execution
superseded_by: null
---

# ADR-001: Three-Layer Architecture (Reasoning, Execution, Ops)

## Context

Augur aims to be a personal AI operating system that connects multiple LLM providers and IDE agents to real workflows. Early development showed a common pattern in AI-assisted systems: conflating the "thinking" (reasoning about what to do) with the "doing" (actually executing actions) and the "controlling" (routing, permissions, auditing).

This conflation leads to:
- Expensive LLM calls being used for simple deterministic operations
- Safety concerns when the same component reasons about and executes destructive actions
- Difficulty swapping LLM providers or execution surfaces (IDE vs CLI vs web)
- Lack of auditability when reasoning and execution are interleaved

## Decision

Adopt a **three-layer architecture** with clear boundaries:

### 1. Reasoning Layer
- **Role**: Turn ambiguous user requests into concrete plans and checks
- **Responsibilities**: Intent understanding, plan generation, validation criteria, human clarification
- **Non-responsibilities**: Direct file mutation, network calls, tool execution
- **Key property**: Model-agnostic (works with any LLM)

### 2. Execution Layer
- **Role**: Perform work deterministically based on the plan
- **Responsibilities**: File edits, command execution, artifact production, running validations
- **Non-responsibilities**: Policy decisions, approval logic, goal redefinition
- **Key property**: Surface-agnostic (IDE, CLI, MCP client can all execute)

### 3. Ops Layer
- **Role**: Make the system safe and reliable through control infrastructure
- **Responsibilities**: Intent routing, approval gates, audit trails, safety policies, maintenance
- **Non-responsibilities**: Business logic for individual skills
- **Key property**: Shared infrastructure across all skills

## Consequences

### Positive

- **Cost optimization**: Expensive reasoning is used where it matters (planning, reviewing), cheap execution handles the rest
- **Safety by design**: Destructive actions pass through explicit approval gates in Ops layer
- **Flexibility**: Can swap LLM providers in Reasoning layer without touching Execution
- **Auditability**: Clear boundaries make it easy to log what was reasoned vs what was executed
- **Testability**: Execution layer can be unit tested without LLM dependencies

### Negative

- **Coordination overhead**: Three layers need clear interfaces between them
- **Potential for over-engineering**: Simple operations might feel heavyweight
- **Learning curve**: Contributors need to understand where code belongs

### Neutral

- Skills span all three layers (reasoning prompts, execution scripts, ops config)
- The dashboard lives in Ops layer as src/lib infrastructure

## Alternatives Considered

### Alternative 1: Two-Layer (Reasoning + Execution)

Simpler model without explicit Ops layer. Rejected because:
- Safety and routing logic would be scattered across components
- No clear owner for cross-cutting concerns (audit, permissions)
- Maintenance automation had no natural home

### Alternative 2: Single Monolithic Agent

One LLM agent handles everything end-to-end. Rejected because:
- Expensive (every operation requires LLM reasoning)
- Safety concerns (agent decides its own permissions)
- Vendor lock-in to specific LLM capabilities
- Poor auditability

### Alternative 3: Microservices Per Capability

Each skill as an independent service. Rejected because:
- Excessive infrastructure complexity for a personal tool
- Coordination overhead between services
- Lost benefits of src/lib context and state

## References

- Architecture Overview - Detailed description of each layer
- Interaction Flows - How requests flow through layers
- This pattern is influenced by the Unix philosophy: "Do one thing well"
