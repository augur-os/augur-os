---
status: Implemented
date: '2025-01-01'
deciders:
- Core team
related: []
hub: null
tags:
- mcp
- execution
- gateway
superseded_by: null
---

# ADR-005: MCP as Execution Gateway

## Context

Augur needs to expose skill capabilities to multiple AI agents and IDEs:
- Claude Desktop
- Cursor IDE
- VS Code with extensions
- Antigravity
- CLI tools
- Future agents (Codex, Jules)

Each agent has different integration requirements. Building custom integrations for each would be:
- Time-consuming and error-prone
- Hard to maintain as agents evolve
- Inconsistent across surfaces

The Model Context Protocol (MCP) emerged as a standard way for LLMs to interact with external tools and data sources.

## Decision

Use **MCP as the primary execution gateway**:

### Architecture
```
┌─────────────────────────────────────────────────┐
│  MCP Server (src/mcp/augur_mcp/)             │
├─────────────────────────────────────────────────┤
│  - Dynamic tool registry from skills            │
│  - Self-updating capabilities                   │
│  - Background job management                    │
│  - Smart intent matching                        │
│  - Rate limiting and safety                     │
└─────────────────────────────────────────────────┘
          ↑               ↑              ↑
     Claude Desktop    Cursor       Antigravity
```

### Tool Exposure
Each skill's `SKILL.md` frontmatter defines MCP tools:
```yaml
mcp_tools:
  - name: careers_search_jobs
    description: Search job listings
    handler: scripts/job_search.py
```

The MCP server dynamically registers these tools at startup.

### Execution Flow
1. Agent sends tool call via MCP protocol
2. MCP server validates and routes to skill
3. Skill executes, returns result
4. MCP server formats response for agent

## Consequences

### Positive

- **Universal compatibility**: Any MCP client can use Augur skills
- **Single integration point**: Maintain one MCP server, not N integrations
- **Dynamic capabilities**: Skills self-register, no central coordination
- **Protocol standard**: Benefits from MCP ecosystem improvements
- **IDE agnostic**: Works with current and future MCP-compatible agents

### Negative

- **MCP dependency**: Tied to MCP protocol evolution
- **Protocol overhead**: Simple operations go through MCP abstraction
- **Limited to MCP semantics**: Some interactions don't fit tool-call model
- **Discovery complexity**: Agents need to understand available tools

### Neutral

- Dashboard uses direct skill imports (not MCP) for performance
- CLI can bypass MCP for direct script execution when needed
- MCP server runs as subprocess, not separate service

## Alternatives Considered

### Alternative 1: Custom REST APIs per Skill

Each skill exposes its own HTTP endpoints. Rejected because:
- N skills × M agents = N×M integrations
- No standard protocol for tool discovery
- Authentication complexity per endpoint
- Different conventions across skills

### Alternative 2: LangChain/LlamaIndex Integration

Use framework-specific tool interfaces. Rejected because:
- Framework lock-in
- Different interface per framework
- Rapid framework evolution causes breakage
- Not compatible with native IDE agents

### Alternative 3: Direct Python Imports

Agents import and call Python functions directly. Rejected because:
- Only works for Python-based agents
- No sandboxing or safety layer
- Tight coupling between agent and skill code
- Version compatibility issues

### Alternative 4: gRPC Services

Use gRPC for high-performance tool calls. Rejected because:
- Overkill for personal tool volumes
- Complex client setup per agent
- No ecosystem support in AI agents
- Binary protocol harder to debug

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- Registry Flow Diagram
- `src/mcp/augur_mcp/` - MCP server implementation
- Agent Hub Architecture
