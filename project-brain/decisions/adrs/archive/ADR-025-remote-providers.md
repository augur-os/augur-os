---
status: Implemented
date: '2026-01-23'
deciders: []
related: []
hub: null
tags:
- remote
- llm
- providers
- feature
superseded_by: null
---

# ADR-025: Remote LLM Providers Feature

**Author**: Gur

---

## Context

Augur currently supports three execution modes for action buttons:
- **IDE** - Routes through connected IDE (Cursor, Claude Desktop, etc.)
- **Local** - Uses Ollama or local models
- **Remote** - Placeholder for cloud LLM providers (not fully implemented)

Users need a way to configure and use cloud LLM providers (OpenRouter, Anthropic, OpenAI, etc.) with:
1. Easy one-click OAuth setup (like Goose)
2. Transparent pricing visibility
3. Security controls to prevent unauthorized API usage
4. Cost tracking and limits

## Decision

### 1. Feature Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     REMOTE PROVIDERS SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────────┐     ┌───────────────────┐   │
│  │   Provider   │     │   Security Gate  │     │   LLM Router      │   │
│  │   Registry   │────►│                  │────►│                   │   │
│  │              │     │ • Action whitelist│     │ • Provider select │   │
│  │ • OAuth URLs │     │ • Data validation │     │ • Fallback logic  │   │
│  │ • Pricing    │     │ • Usage limits   │     │ • Cost tracking   │   │
│  │ • Models     │     │ • Audit logging  │     │                   │   │
│  └──────────────┘     └──────────────────┘     └───────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2. Provider Registry

Supported providers with pricing display:

| Provider | Auth Method | Pricing Model | Example Costs (per 1M tokens) |
|----------|-------------|---------------|-------------------------------|
| **OpenRouter** | OAuth (PKCE) | Pass-through + 5.5% fee | Varies by model |
| **Anthropic** | Manual API Key | Direct pricing | Claude Sonnet: $3/$15 |
| **OpenAI** | Manual API Key | Direct pricing | GPT-4o: $2.50/$10 |
| **Google Gemini** | Manual API Key | Direct pricing | Gemini Pro: $1.25/$5 |
| **Groq** | Manual API Key | Direct pricing | Llama 3 70B: $0.59/$0.79 |
| **Together.ai** | Manual API Key | Direct pricing | Various |
| **Custom** | Manual API Key | User-defined | N/A |

### 3. Security Model (CRITICAL)

#### 3.1 Action Button Whitelist
Remote providers are **ONLY accessible for action buttons explicitly configured as `mode: remote`**.

```yaml
# action_buttons.yaml
buttons:
  - id: "summarize-document"
    name: "Summarize Document"
    mode: "remote"              # ← Explicitly allows remote
    allowed_providers: ["openrouter", "anthropic"]  # ← Provider whitelist
    max_tokens: 4000            # ← Token limit per execution
    max_cost_usd: 0.50          # ← Cost limit per execution
```

#### 3.2 Data Protection Gates

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY GATES                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  GATE 1: Action Validation                                       │
│  ─────────────────────────                                       │
│  • Is this action button configured for remote? NO → BLOCK      │
│  • Is the provider in allowed_providers list? NO → BLOCK        │
│                                                                  │
│  GATE 2: Data Classification                                     │
│  ─────────────────────────                                       │
│  • Check for PII patterns (SSN, credit cards, etc.)             │
│  • Check for secrets (API keys, passwords)                       │
│  • Check against user-defined sensitive folders                  │
│  • If sensitive data detected → WARN or BLOCK (configurable)    │
│                                                                  │
│  GATE 3: User Consent                                            │
│  ─────────────────────────                                       │
│  • First-time provider use → Explicit consent modal              │
│  • Show estimated cost before execution                          │
│  • Log user approval with timestamp                              │
│                                                                  │
│  GATE 4: Rate Limiting                                           │
│  ─────────────────────────                                       │
│  • Per-action token limit                                        │
│  • Per-action cost limit                                         │
│  • Daily/monthly budget caps                                     │
│  • Cooldown between executions (configurable)                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.3 LLM Prompt Injection Protection

```typescript
// Prevent LLMs from accessing remote providers through prompt manipulation
const FORBIDDEN_PATTERNS = [
  /use.*remote.*provider/i,
  /call.*api.*key/i,
  /send.*to.*(openrouter|anthropic|openai)/i,
  /bypass.*security/i,
];

function validatePrompt(prompt: string, context: ExecutionContext): boolean {
  // 1. Check if execution originated from approved action button
  if (!context.actionButton || context.actionButton.mode !== 'remote') {
    return false;
  }

  // 2. Scan for injection attempts
  for (const pattern of FORBIDDEN_PATTERNS) {
    if (pattern.test(prompt)) {
      logSecurityEvent('prompt_injection_attempt', { prompt, pattern });
      return false;
    }
  }

  return true;
}
```

### 4. Configuration Schema

#### 4.1 Provider Configuration (`config-data/remote_providers.yaml`)

```yaml
# Remote LLM Providers Configuration
# WARNING: API keys should use environment variables, not plain text

providers:
  openrouter:
    enabled: true
    auth_method: oauth
    api_key_env: OPENROUTER_API_KEY  # Reference to env var
    default_model: anthropic/claude-sonnet-4

  anthropic:
    enabled: true
    auth_method: manual
    api_key_env: ANTHROPIC_API_KEY
    default_model: claude-sonnet-4-20250514

  openai:
    enabled: false
    auth_method: manual
    api_key_env: OPENAI_API_KEY
    default_model: gpt-4o

# Security Settings
security:
  require_explicit_consent: true
  warn_on_pii: true
  block_on_secrets: true
  sensitive_folders:
    - "~/Documents/Private"
    - "~/Work/Confidential"

# Budget Controls
budget:
  daily_limit_usd: 10.00
  monthly_limit_usd: 100.00
  warn_at_percentage: 80

# Audit Settings
audit:
  log_all_requests: true
  log_prompts: false           # Privacy: don't log actual prompts by default
  log_responses: false         # Privacy: don't log responses by default
  retention_days: 30
```

#### 4.2 Extended LLM Config (`config-data/llm.yaml`)

```yaml
active_profile: agentic_ide

profiles:
  agentic_ide:
    provider: agentic_ide
    model: ide-model

  local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    api_key: ollama
    model: llama3.2:3b-instruct-q8_0

  # NEW: Remote profiles reference remote_providers.yaml
  remote_openrouter:
    provider: remote
    remote_provider: openrouter
    model: anthropic/claude-sonnet-4

  remote_anthropic:
    provider: remote
    remote_provider: anthropic
    model: claude-sonnet-4-20250514
```

### 5. UI Components

#### 5.1 Provider Setup Modal

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚡ Configure Remote Providers                              [X] │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Select a provider to configure:                                │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ OpenRouter  │  │  Anthropic  │  │   OpenAI    │             │
│  │             │  │             │  │             │             │
│  │  ⚡ OAuth   │  │  🔑 API Key │  │  🔑 API Key │             │
│  │             │  │             │  │             │             │
│  │ ~$3/M in    │  │ $3/M in     │  │ $2.50/M in  │             │
│  │ ~$15/M out  │  │ $15/M out   │  │ $10/M out   │             │
│  │ (Sonnet)    │  │ (Sonnet)    │  │ (GPT-4o)    │             │
│  │             │  │             │  │             │             │
│  │ [Configure] │  │ [Configure] │  │ [Configure] │             │
│  │  ✓ Active   │  │  ○ Not Set  │  │  ○ Not Set  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Gemini    │  │    Groq     │  │   Custom    │             │
│  │             │  │             │  │             │             │
│  │  🔑 API Key │  │  🔑 API Key │  │  🔑 API Key │             │
│  │             │  │             │  │             │             │
│  │ $1.25/M in  │  │ $0.59/M in  │  │  Your URL   │             │
│  │ $5/M out    │  │ $0.79/M out │  │  Your price │             │
│  │ (Pro)       │  │ (Llama 70B) │  │             │             │
│  │             │  │             │  │             │             │
│  │ [Configure] │  │ [Configure] │  │ [Add New]   │             │
│  │  ○ Not Set  │  │  ○ Not Set  │  │             │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  ────────────────────────────────────────────────────────────── │
│  Budget: $2.45 / $10.00 daily │ $15.30 / $100.00 monthly       │
│  ████████░░░░░░░░░░░░░ 24%    │ ███░░░░░░░░░░░░░░░░░░ 15%      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 5.2 Execution Consent Modal

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️  Confirm Remote Execution                               [X] │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Action: "Summarize Document"                                   │
│  Provider: OpenRouter (Claude Sonnet)                           │
│                                                                  │
│  Estimated Cost: ~$0.05                                         │
│  Token Estimate: ~2,500 input / ~500 output                     │
│                                                                  │
│  ⚠️  Data will be sent to: api.openrouter.ai                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ □ Don't ask again for this action                          │ │
│  │ □ Don't ask again for this provider                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│                              [Cancel]  [Execute - $0.05]        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6. API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/remote/providers` | GET | List configured providers |
| `/api/remote/providers/[id]` | PUT | Update provider config |
| `/api/remote/providers/[id]/test` | POST | Test provider connection |
| `/api/remote/auth/callback/[provider]` | GET | OAuth callback handler |
| `/api/remote/execute` | POST | Execute with remote provider |
| `/api/remote/usage` | GET | Get usage/cost statistics |
| `/api/remote/audit` | GET | Get audit log |

### 7. OAuth Flow (OpenRouter)

```
User clicks "Configure OpenRouter"
         │
         ▼
┌─────────────────────────────────┐
│ 1. Generate PKCE verifier       │
│ 2. Generate code challenge      │
│ 3. Store verifier in session    │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 4. Redirect to OpenRouter:      │
│    https://openrouter.ai/auth   │
│    ?callback_url=...            │
│    &code_challenge=...          │
└─────────────────────────────────┘
         │
         ▼
   [User authorizes in browser]
         │
         ▼
┌─────────────────────────────────┐
│ 5. OpenRouter redirects to:     │
│    /api/remote/auth/callback/   │
│    openrouter?code=...          │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 6. Exchange code for API key:   │
│    POST openrouter.ai/api/v1/   │
│    auth/keys                    │
│    {code, code_verifier}        │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 7. Store API key securely:      │
│    - Set env var, OR            │
│    - Encrypt in config          │
└─────────────────────────────────┘
         │
         ▼
   [Provider ready to use]
```

### 8. File Structure

```
src/dashboard/
├── app/
│   ├── api/
│   │   └── remote/
│   │       ├── providers/
│   │       │   └── route.ts              # Provider CRUD
│   │       ├── auth/
│   │       │   └── callback/
│   │       │       └── [provider]/
│   │       │           └── route.ts      # OAuth callback
│   │       ├── execute/
│   │       │   └── route.ts              # Execute with security gates
│   │       └── usage/
│   │           └── route.ts              # Usage stats
│   └── settings/
│       └── tabs/
│           └── ProvidersTab.tsx          # Settings UI
├── components/
│   └── remote/
│       ├── RemoteProvidersModal.tsx      # Main modal
│       ├── ProviderCard.tsx              # Provider card with pricing
│       ├── ProviderConfigForm.tsx        # Config form
│       ├── ExecutionConsentModal.tsx     # Consent before execution
│       └── UsageBudgetWidget.tsx         # Budget display
└── lib/
    └── remote/
        ├── providers.ts                   # Provider registry
        ├── oauth.ts                       # PKCE utilities
        ├── security.ts                    # Security gates
        └── pricing.ts                     # Pricing data

config-data/
├── remote_providers.yaml                  # Provider configuration
└── llm.yaml                              # Extended with remote profiles
```

## Consequences

### Positive
- Users can easily configure cloud providers with one-click OAuth
- Transparent pricing prevents surprise bills
- Security gates protect against unauthorized API usage
- Audit logging provides accountability
- Budget controls prevent runaway costs

### Negative
- Additional complexity in configuration
- OAuth flow requires careful security implementation
- Pricing data needs regular updates
- Users may still make mistakes despite warnings

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| API key leakage | Use env vars, encrypt at rest, never log keys |
| Prompt injection triggering remote | Whitelist-only approach, origin validation |
| Cost overruns | Hard budget limits, per-action caps |
| Sensitive data sent to cloud | PII detection, folder blacklists, user consent |
| OAuth CSRF attacks | PKCE flow, state parameter validation |

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create provider registry with pricing data
- [ ] Implement configuration schema
- [ ] Build basic ProviderCard UI component
- [ ] Add ProvidersTab to settings

### Phase 2: Manual Key Entry (Week 1-2)
- [ ] Provider configuration forms
- [ ] API key secure storage
- [ ] Connection test endpoint
- [ ] Basic execution flow

### Phase 3: Security Gates (Week 2)
- [ ] Action whitelist validation
- [ ] Data classification scanner
- [ ] Consent modal
- [ ] Rate limiting & budget controls

### Phase 4: OAuth Flows (Week 2-3)
- [ ] PKCE utilities
- [ ] OpenRouter OAuth flow
- [ ] Callback handler
- [ ] Session management

### Phase 5: Polish & Monitoring (Week 3)
- [ ] Usage dashboard
- [ ] Audit log viewer
- [ ] Cost tracking
- [ ] Documentation

## References

- [OpenRouter Auth Docs](https://openrouter.ai/docs/authentication)
- [OpenRouter Pricing](https://openrouter.ai/pricing)
- [PKCE RFC 7636](https://tools.ietf.org/html/rfc7636)
- [Goose Provider Implementation](https://github.com/block/goose) (Apache 2.0 - for reference only, not copying)
