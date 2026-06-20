# Architecture Blueprint Template

## Overview

Standardized output format for architecture designs. Produces **decisive, actionable blueprints** rather than presenting multiple options.

## Blueprint Structure

Every architecture blueprint MUST include these seven sections:

---

### 1. Patterns & Conventions Found

Document existing codebase patterns with file:line references.

```markdown
### Patterns & Conventions

**State Management:**
- Uses React Context for global state (`src/context/AppContext.tsx:15`)
- Local state with useState for component-level (`src/components/Form.tsx:8`)

**Data Fetching:**
- Custom useFetch hook for API calls (`src/hooks/useFetch.ts:1`)
- SWR pattern for caching (`src/lib/api.ts:45`)

**Error Handling:**
- Centralized error boundary (`src/components/ErrorBoundary.tsx:1`)
- Toast notifications for user feedback (`src/utils/notify.ts:12`)

**File Organization:**
- Feature-based folder structure
- Collocated tests (*.test.ts alongside source)
- Index exports for public APIs

**Naming Conventions:**
- camelCase for functions and variables
- PascalCase for components and types
- kebab-case for file names
```

---

### 2. Architecture Decision

**Single decisive choice** with rationale. Do not present alternatives.

```markdown
### Architecture Decision

**Approach:** Server-side rendering with Next.js App Router + React Server Components

**Rationale:**
1. Aligns with existing Next.js 14 setup in codebase
2. Reduces client-side JavaScript bundle by 40%+
3. Built-in caching and revalidation matches our data update patterns
4. Team already familiar with React patterns

**Trade-offs Accepted:**
- Slightly more complex state management for interactive features
- Some components will need 'use client' directive
```

---

### 3. Component Design

Detailed specifications for each new component/module.

```markdown
### Component Design

#### UserDashboard (Server Component)
**Purpose:** Display user metrics and recent activity
**Location:** `src/app/dashboard/page.tsx`
**Props:** None (data fetched server-side)
**Data:** Fetches from `/api/users/[id]/metrics`

#### MetricsCard (Client Component)
**Purpose:** Interactive metrics display with drill-down
**Location:** `src/components/MetricsCard.tsx`
**Props:**
```typescript
interface MetricsCardProps {
  title: string;
  value: number;
  trend: 'up' | 'down' | 'stable';
  onClick: () => void;
}
```
**State:** Local hover state only
**Events:** onClick triggers modal with details
```

---

### 4. Implementation Map

Explicit list of files to create and modify.

```markdown
### Implementation Map

#### Files to Create
| File | Purpose | LOC Estimate |
|------|---------|--------------|
| `src/app/dashboard/page.tsx` | Dashboard server component | 80 |
| `src/components/MetricsCard.tsx` | Metrics display card | 60 |
| `src/hooks/useMetrics.ts` | Metrics data hook | 40 |
| `src/types/metrics.ts` | Type definitions | 20 |

#### Files to Modify
| File | Change | Risk |
|------|--------|------|
| `src/app/layout.tsx` | Add dashboard to nav | Low |
| `src/lib/api.ts` | Add metrics endpoint | Low |
| `src/types/index.ts` | Export new types | Low |

#### Files to Delete
| File | Reason |
|------|--------|
| `src/components/OldDashboard.tsx` | Replaced by new implementation |
```

---

### 5. Data Flow

Document how data moves through the system.

```markdown
### Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Database  │────▶│  API Route  │────▶│   Server    │
│  (Postgres) │     │ /api/metrics│     │  Component  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   Client    │
                                        │  Component  │
                                        └─────────────┘
```

**Request Flow:**
1. User navigates to `/dashboard`
2. Server component fetches `/api/metrics` (cached 60s)
3. API route queries Postgres via Prisma
4. Server component renders with data
5. Client components hydrate for interactivity

**Cache Strategy:**
- API responses: 60s stale-while-revalidate
- Static assets: Immutable, 1 year
- User data: No cache, always fresh
```

---

### 6. Build Sequence

Step-by-step implementation checklist.

```markdown
### Build Sequence

**Phase 1: Foundation (Day 1)**
- [ ] Create type definitions in `src/types/metrics.ts`
- [ ] Add API route `/api/metrics`
- [ ] Write API route tests
- [ ] Verify API returns expected shape

**Phase 2: Components (Day 2)**
- [ ] Create MetricsCard component
- [ ] Create UserDashboard page
- [ ] Add to navigation
- [ ] Component unit tests

**Phase 3: Integration (Day 3)**
- [ ] Connect components to API
- [ ] Add error boundary
- [ ] Loading states
- [ ] Integration tests

**Phase 4: Polish (Day 4)**
- [ ] Performance optimization
- [ ] Accessibility audit
- [ ] Documentation
- [ ] Code review
```

---

### 7. Critical Details

Error handling, state management, testing, performance, and security considerations.

```markdown
### Critical Details

#### Error Handling
- API errors surface via ErrorBoundary with retry option
- Network failures show offline indicator
- Validation errors display inline with form fields
- All errors logged to monitoring service

#### State Management
- Server state: React Server Components (no client state)
- Client interactivity: useState for local UI state
- No global client state needed for this feature

#### Testing Strategy
- Unit: Component rendering, hook behavior
- Integration: API route → Database
- E2E: Full user flow with Playwright
- Target: 80% coverage

#### Performance Targets
- LCP: < 2.5s
- FID: < 100ms
- CLS: < 0.1
- API response: < 200ms p95

#### Security Considerations
- API route requires authentication (middleware)
- User can only access own metrics (row-level security)
- No PII in logs
- Rate limiting: 100 req/min per user
```

---

## Usage

When designing architecture, produce a complete blueprint following this structure:

1. **Read existing code** to understand patterns
2. **Make decisive choices** - don't present alternatives
3. **Be specific** - include file paths, function names, line numbers
4. **Ensure testability** - every component should be testable
5. **Consider security** - authentication, authorization, data protection
6. **Plan for failure** - error states, fallbacks, monitoring
