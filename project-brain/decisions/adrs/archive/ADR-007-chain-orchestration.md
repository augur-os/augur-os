---
status: Implemented
date: '2025-01-05'
deciders:
- Core team
related: []
hub: null
tags:
- chain
- based
- agent
- orchestration
superseded_by: null
---

# ADR-007: Chain-Based Agent Orchestration

## Context

Complex workflows in Augur require multiple skills working together:
- Feature development: architect → developer → validator → testing
- Bug investigation: data-scientist → developer → validator
- Content creation: knowledge-manager → marketing → librarian

Early implementation had skills calling each other directly, leading to:
- Tight coupling between skills
- Hard to understand execution flow
- Difficult to add new workflows
- No visibility into multi-step progress
- Error handling scattered across skills

## Decision

Adopt **chain-based orchestration** for multi-skill workflows:

### Chain Definition (YAML)
```yaml
chain_id: new_feature
name: "New Feature Development"
description: "Full feature development lifecycle"
steps:
  - agent: architect
    action: design
    output: design_doc
  - agent: developer
    action: implement_feature
    input: $design_doc
    output: code_changes
  - agent: security
    action: security_audit
    input: $code_changes
  - agent: validator
    action: verify_changes
    output: validation_report
  - agent: webapp-testing
    action: ui_qa
```

### Execution Model
```
Chain Orchestrator
├── Load chain definition from YAML
├── Execute steps sequentially
├── Pass outputs between steps ($variable syntax)
├── Handle errors with retry/skip policy
├── Report progress via callback
└── Store execution trace for audit
```

### Invocation
```bash
# Via CLI
python agent_orchestrator.py --execute new_feature --input "Add dark mode"

# Via dashboard
POST /api/chains/execute { chain: "new_feature", input: "..." }

# Via IDE (/ command)
/new_feature Add dark mode toggle
```

## Consequences

### Positive

- **Declarative workflows**: YAML defines what, orchestrator handles how
- **Loose coupling**: Skills don't know about each other, only chain does
- **Visibility**: Can see exactly what steps will run
- **Extensibility**: Add new chains without modifying skills
- **Error handling**: Centralized retry/skip logic
- **Auditability**: Execution traces capture full workflow history

### Negative

- **YAML complexity**: Long chains can be hard to read
- **Debug indirection**: Errors may be far from root cause
- **Sequential bottleneck**: Steps run one at a time (no parallelism yet)
- **Variable passing**: Need to understand $variable syntax

### Neutral

- Chains are versioned in code repo
- CLAUDE.md auto-generates available chains from YAML
- Dashboard shows chain execution status

## Alternatives Considered

### Alternative 1: Direct Skill Composition

Skills call each other via imports. Rejected because:
- Creates dependency web between skills
- Hard to trace execution flow
- No centralized error handling
- Changing one skill may break others

### Alternative 2: Event-Driven (Pub/Sub)

Skills publish events, others subscribe. Rejected because:
- Hard to guarantee ordering
- Complex debugging ("who consumed this event?")
- Eventually consistent is wrong model for workflows
- Overkill for synchronous operations

### Alternative 3: DAG Orchestration (Airflow-style)

Define workflows as directed acyclic graphs. Rejected because:
- Heavy infrastructure for personal tool
- Most workflows are linear sequences
- DAG complexity not needed yet
- Can evolve to DAG later if needed

### Alternative 4: LLM-Driven Orchestration

Let LLM decide which skills to call. Rejected because:
- Non-deterministic execution
- Hard to audit and reproduce
- Expensive (LLM call per routing decision)
- User loses control over workflow

## References

- Chain Integration Architecture
- Chains Architecture Analysis
- `plugins/orchestration/executor/scripts/agent_orchestrator.py`
- `augur-data/factory/chains/` - Chain definitions
