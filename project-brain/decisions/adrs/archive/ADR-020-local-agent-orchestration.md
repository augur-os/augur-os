---
status: Implemented
date: '2026-01-25'
deciders:
- Gur
related: []
hub: null
tags:
- unified
- agent
- execution
- protocol
superseded_by: null
---

# ADR-020: Unified Agent Execution Protocol

**Supersedes**: Extends ADR-remote-providers.md

## Context

Augur has three execution pathways that are currently siloed:

| Pathway | Current Implementation | Gap |
|---------|----------------------|-----|
| **Local GUI** | ActionButtonModal → paste to Cursor/Claude Code | Manual, no observation |
| **Remote API** | Partially implemented (ADR-remote-providers) | Not integrated with action buttons |
| **Auto mode** | Not implemented | Users want "just run it" option |

The ActionButtonModal already has:
- Agent selector (Claude Code, Cursor, Antigravity, VS Code, Clipboard)
- Health status indicators (green/red dots)
- Recommended agent highlighting
- Context switching via MCP

But users can't toggle between "paste to local GUI" vs "call API directly" vs "let system decide".

## Decision

### 1. Unified Execution Protocol

Every action button execution follows the same protocol regardless of pathway:

```typescript
interface ExecutionRequest {
  prompt: string;
  agent: AgentTarget;
  mode: ExecutionMode;
  observation: ObservationConfig;
}

type ExecutionMode = 
  | 'local'    // Paste to local agent GUI (Cursor, Claude Code, etc.)
  | 'api'      // Direct API call via configured provider
  | 'auto';    // System selects best available

interface AgentTarget {
  id: string;              // 'claude-code', 'cursor', 'anthropic', 'openrouter'
  type: 'ide' | 'cli' | 'browser' | 'api' | 'utility';
  capabilities: string[];
  health: 'healthy' | 'degraded' | 'unhealthy';
}
```

### 2. Enhanced Agent Registry

Merge local agents and remote providers into unified registry:

```yaml
# config-data/agents/registry.yaml
agents:
  # Local Agents (GUI-based)
  claude-code:
    type: cli
    execution_mode: local
    invocation: send-ide-prompt
    capabilities: [code, terminal, mcp]
    health_check: ide-bridge
    
  cursor:
    type: ide
    execution_mode: local
    invocation: send-ide-prompt
    capabilities: [code, terminal, mcp]
    health_check: ide-bridge
    
  antigravity:
    type: browser
    execution_mode: local
    invocation: send-browser-prompt  # TBD
    capabilities: [browser, web-scraping, screenshot]
    health_check: process-check
    
  # Remote Providers (API-based)
  anthropic:
    type: api
    execution_mode: api
    invocation: llm-router
    capabilities: [code, reasoning, analysis]
    health_check: api-ping
    config_ref: providers.anthropic  # From /settings/providers
    
  openrouter:
    type: api
    execution_mode: api
    invocation: llm-router
    capabilities: [code, reasoning, analysis]
    health_check: api-ping
    config_ref: providers.openrouter
    
  # Utility
  clipboard:
    type: utility
    execution_mode: local
    invocation: clipboard-copy
    capabilities: []
    health_check: always-healthy
```

### 3. Execution Mode Toggle in UI

Enhance ActionButtonModal with mode selector:

```
┌─────────────────────────────────────────────────────────────┐
│  Send Prompt                                            ✕   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Your Message (Optional)                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Add your own context or instructions here...        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ═══════════════════════════════════════════════════════   │
│                                                             │
│  Execution Mode                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                       │
│  │ 🖥 Local │ │ ☁ API   │ │ ⚡ Auto │  ← NEW: Mode toggle   │
│  └─────────┘ └─────────┘ └─────────┘                       │
│                                                             │
│  Send to Agent                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ◇ Cursor  [Recommended]  ●                     ▼    │   │
│  └─────────────────────────────────────────────────────┘   │
│     ├─ Claude Code      CLI     ●                          │
│     ├─ Cursor           IDE     ● ✓  ← filtered by mode    │
│     ├─ Antigravity      IDE     ○                          │
│     ├─ Anthropic API    API     ●  ← shown when mode=api   │
│     ├─ OpenRouter       API     ●                          │
│     └─ Copy to Clipboard        ●                          │
│                                                             │
│  [Cancel]                    [▷ Send to Cursor]            │
└─────────────────────────────────────────────────────────────┘
```

**Mode behavior:**

| Mode | Agent dropdown shows | Execution |
|------|---------------------|--------|
| **Local** | Only `execution_mode: local` agents | Paste to GUI, observe via MCP |
| **API** | Only `execution_mode: api` providers | Direct API call, response in modal |
| **Auto** | All agents | System picks healthiest with required capabilities |

### 4. Provider Integration

API providers are sourced from `/settings/providers`:

```typescript
// In ActionButtonModal.tsx
const [executionMode, setExecutionMode] = useState<ExecutionMode>('local');

// Fetch agents filtered by mode
const { data: agents } = useQuery(['agents', executionMode], () =>
  fetch(`/api/agents/available?mode=${executionMode}`).then(r => r.json())
);

// For API mode, merge with configured providers
useEffect(() => {
  if (executionMode === 'api') {
    fetch('/api/settings/providers')
      .then(r => r.json())
      .then(providers => {
        // Convert enabled providers to AgentInfo format
        const apiAgents = providers
          .filter(p => p.enabled && p.api_key_configured)
          .map(p => ({
            id: p.id,
            name: p.name,
            type: 'api',
            health: p.health_status,
            capabilities: p.capabilities,
          }));
        setAgents([...apiAgents, clipboardAgent]);
      });
  }
}, [executionMode]);
```

### 5. Unified Execution Handler

```typescript
async function executeAction(
  request: ExecutionRequest
): Promise<ExecutionResult> {
  const { prompt, agent, mode, observation } = request;
  
  // Route based on agent type
  switch (agent.type) {
    case 'ide':
    case 'cli':
      // Local: paste to GUI, start observation
      const ideResult = await sendIdePrompt(prompt, agent.id);
      if (observation.enabled) {
        return await observeCompletion(observation);
      }
      return { status: 'sent', message: `Sent to ${agent.id}` };
      
    case 'api':
      // Remote: direct API call
      const provider = await getProviderConfig(agent.id);
      const response = await callLLM(provider, prompt);
      return { status: 'completed', response };
      
    case 'browser':
      // Browser agent (Antigravity)
      return await sendBrowserPrompt(prompt, agent.id);
      
    case 'utility':
      // Clipboard
      await navigator.clipboard.writeText(prompt);
      return { status: 'copied' };
  }
}
```

### 6. Observation Protocol

For local agents, observe completion via MCP:

```typescript
interface ObservationConfig {
  enabled: boolean;
  type: 'mcp-state' | 'file-watch' | 'git-commit' | 'none';
  watch_paths?: string[];
  completion_signal?: string;
  timeout_ms: number;
  poll_interval_ms: number;
}

class AgentObserver {
  async observeCompletion(config: ObservationConfig): Promise<ObservationResult> {
    const startTime = Date.now();
    
    while (Date.now() - startTime < config.timeout_ms) {
      // Check MCP state for completion signal
      if (config.type === 'mcp-state') {
        const state = await this.checkMcpState(config.completion_signal);
        if (state.completed) {
          return { status: 'completed', result: state.result };
        }
      }
      
      // Check watched files for changes
      if (config.type === 'file-watch') {
        const changed = await this.checkFileChanges(config.watch_paths);
        if (changed) {
          return { status: 'completed', files: changed };
        }
      }
      
      await sleep(config.poll_interval_ms);
    }
    
    return { status: 'timeout' };
  }
}
```

### 7. Auto Mode Selection Logic

```typescript
function selectBestAgent(
  taskType: string,
  requiredCapabilities: string[],
  registry: AgentRegistry
): AgentTarget {
  // 1. Filter agents with required capabilities
  const capable = registry.agents.filter(a =>
    requiredCapabilities.every(cap => a.capabilities.includes(cap))
  );
  
  // 2. Prefer healthy agents
  const healthy = capable.filter(a => a.health === 'healthy');
  const candidates = healthy.length > 0 ? healthy : capable;
  
  // 3. Prefer local over API (privacy, no cost)
  const local = candidates.filter(a => a.execution_mode === 'local');
  if (local.length > 0) {
    // Prefer agents with MCP observation
    const mcpCapable = local.filter(a => a.capabilities.includes('mcp'));
    return mcpCapable[0] || local[0];
  }
  
  // 4. Fall back to API
  return candidates[0];
}
```

## Implementation Plan

### Phase 1: Mode Toggle UI ✅
- [x] Add `ExecutionMode` state to ActionButtonModal
- [x] Create mode toggle component (Local/API/Auto tabs) → `ExecutionModeToggle.tsx`
- [x] Filter agent dropdown based on mode
- [x] Update `/api/agents/available` to accept `?mode=` param

### Phase 2: Provider Integration ✅
- [x] Create `/api/settings/providers` endpoint (existing)
- [x] Convert providers to AgentInfo format
- [x] Add API providers to agent dropdown when mode=api
- [x] Implement `callLLM()` for API execution → `/api/llm/route.ts`

### Phase 3: Unified Execution ✅
- [x] Implement `executeAction()` router (in `handleSend`)
- [x] Handle local vs API vs utility execution paths
- [x] Add response display for API mode in modal (with cost/tokens)

### Phase 4: Observation Hardening (Future Enhancement)
- [ ] Implement `AgentObserver` class
- [x] Add timeout/retry to observation (existing polling)
- [ ] Create completion signal convention for local agents
- [ ] Test MCP state observation end-to-end

### Phase 5: Auto Mode ✅
- [x] Implement `selectBestAgent()` logic (agents sorted by health)
- [x] Add capability tagging to agents in registry
- [x] Wire auto mode to execution flow

## Consequences

### Positive

- **Unified UX**: Same modal, same flow, different execution backends
- **Flexibility**: User chooses: manual control (local) vs fire-and-forget (API) vs smart routing (auto)
- **Provider reuse**: Configured providers work for action buttons AND direct API calls
- **Extensible**: Add new agents/providers by updating registry

### Negative

- **Complexity**: Three execution paths to maintain
- **API costs**: Users may accidentally run expensive API calls
- **Observation gaps**: Not all local agents support MCP observation

### Mitigations

- Default to `mode: local` to prevent accidental API costs
- Show cost estimate before API execution (from ADR-remote-providers)
- Clearly indicate observation support per agent

## References

- ADR-remote-providers.md - Provider registry and security model
- [ADR-007: Chain-Based Agent Orchestration](./ADR-007-chain-orchestration.md)

### New/Modified Files

| File | Description |
|------|-------------|
| `config-data/agents/registry.yaml` | Unified agent registry (local + API) |
| `src/dashboard/components/ExecutionModeToggle.tsx` | Mode toggle UI component |
| `src/dashboard/components/ActionButtonModal.tsx` | Updated with mode selection and API execution |
| `src/dashboard/components/AgentSelector.tsx` | Updated for mode filtering and API agents |
| `src/dashboard/lib/stores/actionModalStore.ts` | Added execution mode state |
| `src/dashboard/lib/remote/types.ts` | Added execution types (ExecutionMode, AgentTarget, etc.) |
| `src/dashboard/app/api/agents/available/route.ts` | Updated to support mode parameter |
| `src/dashboard/app/api/llm/route.ts` | LLM router for API provider calls |
| `/settings/providers` | Provider configuration page |
