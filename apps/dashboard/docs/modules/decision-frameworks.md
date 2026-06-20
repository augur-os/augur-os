# Decision Frameworks

When building Augur plugins, use these frameworks to determine what components to create.

## When to Create an MCP Tool

MCP tools are for **AI agent consumption** - they let Claude/agents interact with your plugin.

| Question | If Yes |
|----------|--------|
| Does an **AI agent** need to perform this action? | Create MCP tool |
| Is it a **read/write operation** on plugin data? | Create MCP tool |
| Does it need **structured input/output** for agents? | Create MCP tool |
| Is it **only for dashboard UI**? | Skip MCP, use service or API |
| Is it **only for human CLI usage**? | Skip MCP, use Python script |

### MCP vs API Route

| Layer | Consumer | Example |
|-------|----------|---------|
| **MCP Tool** | AI agents (Claude, chains), API routes | `search_jobs` - agent finds jobs |
| **API Route** | Browser (fetch from React) | `/api/jobs` - UI fetches via `createAPIRoute` |

### MCP Tool Location
```
plugins/{bundle}/skills/{skill}/
├── mcp/
│   ├── __init__.py      # Tool registration
│   └── tools.py         # Tool implementations
```

## When to Create an API Route

API routes are for **browser/client consumption** - they bridge React client components to server-side data.

| Question | If Yes |
|----------|--------|
| Does a **Client Component** need this data? | Create API route |
| Does it involve **user interaction** (forms, mutations)? | Create API route |
| Do you need **authentication/authorization**? | Create API route |
| Is it a **Server Component** only? | Use API route with `createAPIRoute` (ADR-287) |
| Is it **agent-only** functionality? | Skip API, use MCP tool |

### MCP-First API Pattern (ADR-287)

```tsx
// API route — proxies to MCP tool via createAPIRoute
// apps/dashboard/app/api/jobs/route.ts
import { createAPIRoute } from '@/lib/mcp/createAPIRoute';

export const GET = createAPIRoute({
  toolName: 'jobs-get-all',
  extractParams: async () => ({}),
});

// Client Component — fetches data via API route
'use client';
export default function JobsFilter() {
  const { data } = useSWR('/api/jobs'); // Fetch via API
}
```

### API Route Location
```
plugins/{bundle}/skills/{skill}/
├── api/
│   ├── route.ts         # Main endpoint
│   └── [id]/route.ts    # Dynamic routes
```

## When to Create an Action

Actions are **button clicks** in the dashboard - they trigger operations.

| Question | If Yes |
|----------|--------|
| Should user **trigger this from UI**? | Create action |
| Is it a **common operation** for this plugin? | Create action |
| Does it need **user input** before running? | Create action with modal |

### Action Dispatch Types

| Dispatch | When to Use | Example |
|------|-------------|---------|
| `fire` | No AI needed, instant result | "Refresh data", "Export CSV" |
| `oneshot` | Needs one-shot AI reasoning/generation | "Analyze code", "Summarize thread" |
| `modal` | Needs user input first | "Create new..." with form |

### Decision Framework

```
User clicks button
    |
    +-> Needs one-shot AI? --> Yes --> dispatch: oneshot
    |                                  (runs via CLI/agent)
    |
    +-> Needs input? --> Yes --> dispatch: modal
    |                                (shows form first)
    |
    +-> Simple operation? --> dispatch: fire
                                  (runs immediately)
```

### Action Location
Actions are defined in `dashboard.yaml`:
```yaml
actions:
  - id: my-action
    label: "Do Something"
    icon: Zap
    dispatch: fire      # or: oneshot, modal, ide
    endpoint: /api/...  # for fire
    prompt: "..."       # for oneshot / ide
```

## When to Create UI Components

| Question | If Yes |
|----------|--------|
| Is it a **new domain/vertical**? | Create new hub (page) |
| Is it a **view within existing domain**? | Create new tab |
| Is it **reusable across pages**? | Create component |
| Is it **home page summary**? | Create widget |

### UI Hierarchy

```
Hub (Page)           /career
├── Tab              /career/jobs
├── Tab              /career/interviews
└── Tab              /career/networking

Widget               CalendarWidget (on home page)
Component            JobCard (reusable)
```

### Page vs Tab Decision

| Choose | When |
|--------|------|
| **New Hub** | New life domain (career, health, finance) |
| **New Tab** | New view in existing domain |
| **Widget** | Summary/preview on home page |

### UI Location
```
plugins/{bundle}/skills/{skill}/
├── dashboard/
│   ├── page.tsx           # Main page
│   ├── layout.tsx         # Layout wrapper
│   ├── loading.tsx        # Loading skeleton
│   └── tabs/
│       └── OverviewTab.tsx
```

## When to Create a Schema

Schemas define **data structure** for validation and documentation.

| Question | If Yes |
|----------|--------|
| Does plugin have **structured data** (YAML/JSON)? | Create schema |
| Do you need **validation** on input? | Create schema |
| Is data **src/lib between tools/UI**? | Create schema |
| Is it **ad-hoc/temporary data**? | Skip schema |

### Schema Location
```
plugins/{bundle}/skills/{skill}/
├── schemas/
│   └── my-data.yaml      # JSON Schema format
```
