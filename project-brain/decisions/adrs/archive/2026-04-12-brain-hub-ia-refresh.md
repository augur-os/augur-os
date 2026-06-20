# Brain Hub IA Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move provider configuration into Settings, turn Brain Agents into a distinct control center, and split Memory into dedicated routes that surface high-value content immediately.

**Architecture:** Keep Settings as the shell-owned configuration hub and Brain as the skill-owned content hub. Reuse the existing providers and memory components by moving them behind new canonical routes, update skill metadata so generated Brain navigation matches the new IA, and refactor Brain Agents around derived control-state rather than raw inventory so it no longer overlaps Browse.

**Tech Stack:** Next.js App Router, TypeScript, React, TanStack Query, MCP hooks, generated tab registry, Jest/RTL

---

### Task 1: Move Providers Into Settings

**Files:**
- Create: `apps/dashboard/features/pages/settings/providers/ProvidersPage.tsx`
- Create: `apps/dashboard/app/settings/providers/page.tsx`
- Create: `apps/dashboard/app/settings/providers/page.test.tsx`
- Modify: `apps/dashboard/app/settings/page.tsx`
- Modify: `apps/dashboard/app/settings/page.test.tsx`
- Modify: `apps/dashboard/lib/tabs/registry.ts`
- Modify: `apps/dashboard/app/api/remote/auth/start/[provider]/route.ts`
- Modify: `skills/ai/SKILL.md`
- Delete: `apps/dashboard/features/pages/brain/ai/providers/page.tsx`

- [ ] **Step 1: Write the failing Settings route tests**

```tsx
// apps/dashboard/app/settings/page.test.tsx
it("redirects legacy providers tab to the canonical settings providers route", async () => {
  await Page({ searchParams: Promise.resolve({ tab: "providers" }) });
  expect(redirect).toHaveBeenCalledWith("/settings/providers");
});

it("does not keep a legacy integrations redirect in settings", async () => {
  await Page({ searchParams: Promise.resolve({ tab: "integrations" }) });
  expect(redirect).not.toHaveBeenCalledWith("/browse?category=integrations");
});
```

```tsx
// apps/dashboard/app/settings/providers/page.test.tsx
jest.mock("@/features/pages/settings/providers/ProvidersPage", () => ({
  ProvidersPage: () => <div>Providers Settings Surface</div>,
}));

import ProvidersRoute from "./page";

describe("Settings providers route", () => {
  it("renders the canonical providers settings page", () => {
    const element = ProvidersRoute();
    expect(element).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run the Settings route tests to verify they fail**

Run:

```bash
pnpm --filter dashboard test -- apps/dashboard/app/settings/page.test.tsx apps/dashboard/app/settings/providers/page.test.tsx
```

Expected:

```text
FAIL apps/dashboard/app/settings/page.test.tsx
  redirects legacy providers tab to the canonical settings providers route

FAIL apps/dashboard/app/settings/providers/page.test.tsx
  Cannot find module './page'
```

- [ ] **Step 3: Move the providers UI into a Settings-owned feature component**

```tsx
// apps/dashboard/features/pages/settings/providers/ProvidersPage.tsx
'use client';

import { useCallback, useEffect, useState } from 'react';
import { Cloud } from 'lucide-react';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { mcpCall } from '@/lib/mcp/client';
import ProviderCard from '@/components/remote/ProviderCard';
import ProviderConfigModal from '@/components/remote/ProviderConfigModal';
import UsageBudgetWidget from '@/components/remote/UsageBudgetWidget';

useEffect(() => {
  if (!providersData?.budget) return;
  setBudgetDraft({ ...DEFAULT_BUDGET, ...providersData.budget });
}, [
  providersData?.budget?.dailyLimitUsd,
  providersData?.budget?.monthlyLimitUsd,
  providersData?.budget?.warnAtPercentage,
]);

return (
  <div className="space-y-6">
    <div className="flex items-center gap-3">
      <div className="rounded-lg border border-[var(--accent-info)]/30 bg-[var(--accent-info)]/20 p-2">
        <Cloud className="h-5 w-5 text-[var(--accent-info)]" />
      </div>
      <div>
        <h2 className="text-2xl font-semibold text-[var(--text-primary)]">Providers</h2>
        <p className="text-sm text-[var(--text-secondary)]">
          Configure local and remote model providers, budgets, and active profiles.
        </p>
      </div>
    </div>
    <UsageBudgetWidget
      budget={budgetDraft}
      usage={usage}
      hasChanges={hasBudgetChanges}
      saving={budgetSaving}
      onChange={handleBudgetDraftChange}
      onReset={handleResetBudget}
      onSave={handleSaveBudget}
    />
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      {providers.map((provider) => (
        <ProviderCard
          key={provider.id}
          provider={provider}
          onConfigure={() => handleConfigureProvider(provider.id)}
          onTest={() => handleTestProvider(provider.id)}
          onOAuth={() => handleStartOAuth(provider.id)}
        />
      ))}
    </div>
    <ProviderConfigModal
      provider={selectedProvider}
      config={selectedConfig}
      isOpen={!!selectedProvider}
      onClose={() => setSelectedProvider(null)}
      onSave={handleSaveProviderConfig}
      onRefresh={fetchProviders}
    />
  </div>
);
```

- [ ] **Step 4: Add the canonical Settings route and update the shell navigation**

```tsx
// apps/dashboard/app/settings/providers/page.tsx
import { ProvidersPage } from "@/features/pages/settings/providers/ProvidersPage";

export default function SettingsProvidersPage() {
  return <ProvidersPage />;
}
```

```ts
// apps/dashboard/lib/tabs/registry.ts
tabs: [
  { id: "general", label: "General", icon: "Settings", href: "/settings" },
  { id: "layout", label: "Layout", icon: "Layout", href: "/settings/layout" },
  { id: "plugins", label: "Plugins", icon: "Package", href: "/settings/skills" },
  { id: "providers", label: "Providers", icon: "Cloud", href: "/settings/providers" },
  { id: "security", label: "Security", icon: "Shield", href: "/settings/security" },
  { id: "permissions", label: "Permissions", icon: "Key", href: "/settings/permissions" },
  { id: "dispatch", label: "Dispatch", icon: "Send", href: "/settings/dispatch" },
]
```

```ts
// apps/dashboard/app/settings/page.tsx
const LEGACY_TAB_ROUTES: Record<string, string> = {
  general: "/settings",
  skills: "/settings/skills",
  plugins: "/settings/skills",
  layout: "/settings/layout",
  providers: "/settings/providers",
  security: "/settings/security",
  permissions: "/settings/permissions",
  dispatch: "/settings/dispatch",
};
```

- [ ] **Step 5: Update route ownership and OAuth return paths**

```ts
// apps/dashboard/app/api/remote/auth/start/[provider]/route.ts
const OAUTH_DEFAULT_RETURN_URL = "/settings/providers";
```

```yaml
# skills/ai/SKILL.md
x-augur-dashboard-pages:
- /brain/ai
- /brain/ai/agents
```

```bash
git rm apps/dashboard/features/pages/brain/ai/providers/page.tsx
```

- [ ] **Step 6: Run the Settings route tests again**

Run:

```bash
pnpm --filter dashboard test -- apps/dashboard/app/settings/page.test.tsx apps/dashboard/app/settings/providers/page.test.tsx
```

Expected:

```text
PASS apps/dashboard/app/settings/page.test.tsx
PASS apps/dashboard/app/settings/providers/page.test.tsx
```

- [ ] **Step 7: Commit the provider move**

```bash
git add apps/dashboard/features/pages/settings/providers/ProvidersPage.tsx apps/dashboard/app/settings/providers/page.tsx apps/dashboard/app/settings/providers/page.test.tsx apps/dashboard/app/settings/page.tsx apps/dashboard/app/settings/page.test.tsx apps/dashboard/lib/tabs/registry.ts apps/dashboard/app/api/remote/auth/start/[provider]/route.ts skills/ai/SKILL.md
git rm apps/dashboard/features/pages/brain/ai/providers/page.tsx
git commit -m "refactor: move provider configuration into settings"
```

### Task 2: Turn Brain Agents Into a Control Center

**Files:**
- Create: `apps/dashboard/features/pages/brain/ai/agents/control-state.ts`
- Create: `apps/dashboard/features/pages/brain/ai/agents/control-state.test.ts`
- Modify: `apps/dashboard/features/pages/brain/ai/agents/page.tsx`
- Modify: `apps/dashboard/lib/mcp/useMcpPoll.ts`

- [ ] **Step 1: Write failing control-state tests**

```ts
// apps/dashboard/features/pages/brain/ai/agents/control-state.test.ts
import { deriveAgentControlState } from "./control-state";

describe("deriveAgentControlState", () => {
  it("flags API providers without keys as setup-required attention items", () => {
    const state = deriveAgentControlState([
      {
        id: "openai",
        name: "OpenAI",
        icon: "sparkles",
        health: "offline",
        type: "api",
        execution_mode: "api",
        provider: { hasApiKey: false, defaultModel: "gpt-5.4" },
      },
    ]);

    expect(state.attention.setupRequired).toHaveLength(1);
    expect(state.summary.primaryCallToAction.label).toBe("Configure providers");
  });

  it("prefers healthy local execution paths for the current execution summary", () => {
    const state = deriveAgentControlState([
      {
        id: "codex",
        name: "Codex",
        icon: "terminal",
        health: "healthy",
        type: "cli",
        execution_mode: "local",
        capabilities: ["code", "terminal"],
      },
    ]);

    expect(state.summary.currentPathLabel).toContain("local");
    expect(state.summary.availablePathCount).toBe(1);
  });
});
```

- [ ] **Step 2: Run the control-state tests to verify they fail**

Run:

```bash
pnpm --filter dashboard test -- apps/dashboard/features/pages/brain/ai/agents/control-state.test.ts
```

Expected:

```text
FAIL apps/dashboard/features/pages/brain/ai/agents/control-state.test.ts
  Cannot find module './control-state'
```

- [ ] **Step 3: Add a pure derived-state helper for routing, attention, and CTA selection**

```ts
// apps/dashboard/features/pages/brain/ai/agents/control-state.ts
export function deriveAgentControlState(agents: AgentInfo[]) {
  const healthyLocal = agents.filter((agent) => agent.execution_mode === "local" && agent.health === "healthy");
  const setupRequired = agents.filter((agent) =>
    agent.execution_mode === "api" &&
    agent.provider &&
    !agent.provider.hasApiKey
  );
  const degraded = agents.filter((agent) => agent.health === "degraded");
  const offline = agents.filter((agent) =>
    (agent.health === "offline" || agent.health === "unhealthy") &&
    !(agent.execution_mode === "api" && agent.provider && !agent.provider.hasApiKey)
  );

  return {
    summary: {
      currentPathLabel: healthyLocal.length > 0 ? "Healthy local execution path available" : "No healthy local execution path",
      availablePathCount: healthyLocal.length + agents.filter((agent) => agent.execution_mode === "api" && agent.provider?.hasApiKey).length,
      primaryCallToAction: setupRequired.length > 0
        ? { label: "Configure providers", href: "/settings/providers" }
        : { label: "Test all paths", action: "test-all" },
    },
    attention: {
      setupRequired,
      degraded,
      offline,
    },
  };
}
```

- [ ] **Step 4: Make the polling hook support manual refresh and refactor the page around control-state**

```ts
// apps/dashboard/lib/mcp/useMcpPoll.ts
export interface McpPollResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<unknown>;
}

const { data, isLoading, error, refetch } = useQuery<unknown, Error, T>({
  queryKey,
  queryFn: () => mcpCall<T>(tool, opts?.args ?? {}),
  staleTime: presetConfig.staleTime,
  refetchOnWindowFocus: presetConfig.refetchOnWindowFocus,
  refetchInterval: canPoll ? intervalMs : false,
  enabled,
  placeholderData: keepPreviousData,
  select: opts?.select,
});

return {
  data: data ?? null,
  loading: isLoading,
  error: error ? error.message : null,
  refetch,
};
```

```tsx
// apps/dashboard/features/pages/brain/ai/agents/page.tsx
const { data: agents, loading: isLoading, error, refetch } = useMcpPoll<AgentInfo[]>(
  ["ai", "agents"],
  "agent-registry",
  REFRESH_INTERVAL_MS,
  { preset: "device", args: { mode: "auto" }, select: (raw: any) => raw.agents ?? [] },
);

useEffect(() => {
  if (agents) setLastUpdated(new Date());
}, [agents]);

const control = deriveAgentControlState(agentsList);

const handleRefresh = () => {
  void refetch();
};

return (
  <div className="space-y-6">
    <section className="liquid-glass-card p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
        Current Execution
      </h2>
      <p className="mt-2 text-lg font-semibold text-[var(--text-primary)]">
        {control.summary.currentPathLabel}
      </p>
      <p className="mt-1 text-sm text-[var(--text-secondary)]">
        {control.summary.availablePathCount} path(s) available to Augur right now.
      </p>
    </section>

    <section className="grid gap-4 lg:grid-cols-3">
      <div className="liquid-glass-card p-4">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">Setup Required</h3>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          {control.attention.setupRequired.length} provider path(s) need credentials or connection setup.
        </p>
      </div>
      <div className="liquid-glass-card p-4">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">Degraded</h3>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          {control.attention.degraded.length} path(s) are reachable but unstable.
        </p>
      </div>
      <div className="liquid-glass-card p-4">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">Offline</h3>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          {control.attention.offline.length} path(s) are currently unavailable.
        </p>
      </div>
    </section>
  </div>
);
```

- [ ] **Step 5: Run the control-state tests**

Run:

```bash
pnpm --filter dashboard test -- apps/dashboard/features/pages/brain/ai/agents/control-state.test.ts
```

Expected:

```text
PASS apps/dashboard/features/pages/brain/ai/agents/control-state.test.ts
```

- [ ] **Step 6: Commit the agents control-center refactor**

```bash
git add apps/dashboard/features/pages/brain/ai/agents/control-state.ts apps/dashboard/features/pages/brain/ai/agents/control-state.test.ts apps/dashboard/features/pages/brain/ai/agents/page.tsx apps/dashboard/lib/mcp/useMcpPoll.ts
git commit -m "refactor: turn brain agents into a control center"
```

### Task 3: Split Memory Into Overview, Workspace, Profile, and Daily Logs

**Files:**
- Create: `apps/dashboard/features/pages/brain/knowledge/memory/MemorySectionNav.tsx`
- Create: `apps/dashboard/features/pages/brain/knowledge/memory/workspace/page.tsx`
- Create: `apps/dashboard/features/pages/brain/knowledge/memory/profile/page.tsx`
- Create: `apps/dashboard/features/pages/brain/knowledge/memory/daily-logs/page.tsx`
- Create: `apps/dashboard/features/pages/brain/knowledge/memory/page.test.tsx`
- Modify: `apps/dashboard/features/pages/brain/knowledge/memory/page.tsx`
- Modify: `skills/knowledge/SKILL.md`
- Modify: `tests/dashboard/scripts/generate-registry.test.ts`

- [ ] **Step 1: Write failing registry and overview tests**

```ts
// tests/dashboard/scripts/generate-registry.test.ts
it("builds nested brain memory imports for workspace, profile, and daily logs", () => {
  const registries = buildHubRegistries(
    [
      { hubId: "brain", slug: "knowledge/memory", sourceDir: "/repo/apps/dashboard/features/pages/brain/knowledge/memory" },
      { hubId: "brain", slug: "knowledge/memory/workspace", sourceDir: "/repo/apps/dashboard/features/pages/brain/knowledge/memory/workspace" },
      { hubId: "brain", slug: "knowledge/memory/profile", sourceDir: "/repo/apps/dashboard/features/pages/brain/knowledge/memory/profile" },
      { hubId: "brain", slug: "knowledge/memory/daily-logs", sourceDir: "/repo/apps/dashboard/features/pages/brain/knowledge/memory/daily-logs" },
    ],
    { brain: "/brain/knowledge/memory" },
    "/repo/apps/dashboard/app",
    "/repo",
  );

  expect(registries[0].entries).toEqual([
    { slug: "knowledge/memory", importPath: "@/features/pages/brain/knowledge/memory/page" },
    { slug: "knowledge/memory/daily-logs", importPath: "@/features/pages/brain/knowledge/memory/daily-logs/page" },
    { slug: "knowledge/memory/profile", importPath: "@/features/pages/brain/knowledge/memory/profile/page" },
    { slug: "knowledge/memory/workspace", importPath: "@/features/pages/brain/knowledge/memory/workspace/page" },
  ]);
});
```

```tsx
// apps/dashboard/features/pages/brain/knowledge/memory/page.test.tsx
it("shows memory section navigation instead of collapsed workspace/profile/log toggles", () => {
  render(<MemoryPage />);

  expect(screen.getByRole("link", { name: /workspace/i })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /profile/i })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /daily logs/i })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /toggle workspace/i })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the registry and overview tests to verify they fail**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/scripts/generate-registry.test.ts apps/dashboard/features/pages/brain/knowledge/memory/page.test.tsx
```

Expected:

```text
FAIL tests/dashboard/scripts/generate-registry.test.ts
  builds nested brain memory imports for workspace, profile, and daily logs

FAIL apps/dashboard/features/pages/brain/knowledge/memory/page.test.tsx
  Unable to find role="link" name=/workspace/i
```

- [ ] **Step 3: Add a shared Memory section nav and simplify the overview page**

```tsx
// apps/dashboard/features/pages/brain/knowledge/memory/MemorySectionNav.tsx
'use client';

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/brain/knowledge/memory", label: "Overview" },
  { href: "/brain/knowledge/memory/workspace", label: "Workspace" },
  { href: "/brain/knowledge/memory/profile", label: "Profile" },
  { href: "/brain/knowledge/memory/daily-logs", label: "Daily Logs" },
];

export function MemorySectionNav() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap gap-2" aria-label="Memory sections">
        {ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
          <Link
            key={item.href}
            href={item.href}
            className={active
              ? "rounded-lg border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 px-3 py-2 text-sm text-[var(--text-primary)]"
              : "rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
```

```tsx
// apps/dashboard/features/pages/brain/knowledge/memory/page.tsx
return (
  <div className="space-y-6">
    <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Session Memory</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Decisions, patterns, and preferences from your sessions
        </p>
      </div>
      <button onClick={handleCurate} disabled={isCurating} className="flex min-h-[44px] items-center gap-2 rounded-lg border border-purple-500/30 px-4 text-purple-500">
        <RefreshCw className={`h-4 w-4 ${isCurating ? "animate-spin" : ""}`} />
        {isCurating ? "Curating..." : "Curate Memory"}
      </button>
    </header>

    <MemorySectionNav />
    <MemorySearchWidget
      searchQuery={searchHook.searchQuery}
      setSearchQuery={searchHook.setSearchQuery}
      isSearching={searchHook.isSearching}
      searchResults={searchHook.searchResults}
      hasSearched={searchHook.hasSearched}
      searchError={searchHook.searchError}
      onSearch={searchHook.handleSearch}
      categories={categories}
    />
    <MemoryStatsGrid stats={stats} isLoading={isStatsLoading} />
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <RecentDecisions stats={stats} categories={categories} />
      </div>
      <DecisionCategories stats={stats} />
    </div>
    <MemoryInsights stats={stats} categories={categories} />
    <WikiMaintenancePanel
      summary={wikiMaintenance.summary}
      candidates={wikiMaintenance.candidates}
      totalCandidates={wikiMaintenance.totalCandidates}
      isLoading={wikiMaintenance.isLoading}
      error={wikiMaintenance.error}
      onRefresh={wikiMaintenance.refetch}
    />
  </div>
);
```

- [ ] **Step 4: Add dedicated Workspace, Profile, and Daily Logs route pages**

```tsx
// apps/dashboard/features/pages/brain/knowledge/memory/workspace/page.tsx
'use client';

import { useState } from 'react';
import { MemorySectionNav } from '../MemorySectionNav';
import { useMemoryDashboardData, useMemoryReportAction } from '../hooks';
import { MemoryWorkspacePanel } from '../components/MemoryWorkspacePanel';
import { HumanReportPreview } from '../components/HumanReportPreview';

export default function MemoryWorkspacePage() {
  const { workspace, report, isWorkspaceLoading, refreshWorkspace, openWorkspaceFile } = useMemoryDashboardData();
  const regenerateAction = useMemoryReportAction("/brain/knowledge/memory/workspace");
  const [openingFileId, setOpeningFileId] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <MemorySectionNav />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.05fr_1.35fr]">
        <MemoryWorkspacePanel
          workspace={workspace}
          isLoading={isWorkspaceLoading}
          openingFileId={openingFileId}
          onOpenFile={async (fileId) => {
            setOpeningFileId(fileId);
            try {
              await openWorkspaceFile(fileId);
            } finally {
              setOpeningFileId(null);
            }
          }}
          onRefresh={refreshWorkspace}
        />
        <HumanReportPreview
          report={report}
          isLoading={isWorkspaceLoading}
          onOpenReport={() => openWorkspaceFile("report")}
          onRefresh={refreshWorkspace}
          regenerateAction={regenerateAction}
        />
      </div>
    </div>
  );
}
```

```tsx
// apps/dashboard/features/pages/brain/knowledge/memory/profile/page.tsx
'use client';

import { MemorySectionNav } from '../MemorySectionNav';
import { HumanApiProfileSection } from '../components/HumanApiProfileSection';
import { useMemoryDashboardData } from '../hooks';

export default function MemoryProfilePage() {
  const { refreshWorkspace } = useMemoryDashboardData();

  return (
    <div className="space-y-6">
      <MemorySectionNav />
      <HumanApiProfileSection onWorkspaceChange={refreshWorkspace} />
    </div>
  );
}
```

```tsx
// apps/dashboard/features/pages/brain/knowledge/memory/daily-logs/page.tsx
'use client';

import { MemorySectionNav } from '../MemorySectionNav';
import { DailyLogsSection } from '../components/DailyLogsSection';
import { useMemoryDashboardData } from '../hooks';

export default function MemoryDailyLogsPage() {
  const { stats } = useMemoryDashboardData();

  return (
    <div className="space-y-6">
      <MemorySectionNav />
      <DailyLogsSection lastCurated={stats?.lastCurated ?? null} />
    </div>
  );
}
```

- [ ] **Step 5: Update knowledge metadata so generated Brain navigation can discover the new pages cleanly**

```yaml
# skills/knowledge/SKILL.md
x-augur-dashboard-pages:
- /brain/knowledge
- /brain/knowledge/memory
- /brain/knowledge/memory/workspace
- /brain/knowledge/memory/profile
- /brain/knowledge/memory/daily-logs
```

- [ ] **Step 6: Run the Memory tests again**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/scripts/generate-registry.test.ts apps/dashboard/features/pages/brain/knowledge/memory/page.test.tsx
```

Expected:

```text
PASS tests/dashboard/scripts/generate-registry.test.ts
PASS apps/dashboard/features/pages/brain/knowledge/memory/page.test.tsx
```

- [ ] **Step 7: Commit the Memory split**

```bash
git add apps/dashboard/features/pages/brain/knowledge/memory/MemorySectionNav.tsx apps/dashboard/features/pages/brain/knowledge/memory/workspace/page.tsx apps/dashboard/features/pages/brain/knowledge/memory/profile/page.tsx apps/dashboard/features/pages/brain/knowledge/memory/daily-logs/page.tsx apps/dashboard/features/pages/brain/knowledge/memory/page.tsx apps/dashboard/features/pages/brain/knowledge/memory/page.test.tsx skills/knowledge/SKILL.md tests/dashboard/scripts/generate-registry.test.ts
git commit -m "feat: split memory into dedicated routes"
```

### Task 4: Regenerate Navigation, Validate, and Verify in Browser

**Files:**
- Modify: `apps/dashboard/lib/tabs/generated-registry.ts`
- Modify: `apps/dashboard/app/brain/[[...slug]]/registry.ts`

- [ ] **Step 1: Regenerate tab and catch-all registry outputs**

Run:

```bash
pnpm --filter dashboard run generate-tabs
pnpm --filter dashboard run mount-plugins
pnpm --filter dashboard run validate-tabs
```

Expected:

```text
Generated lib/tabs/generated-registry.ts
Mounted plugin pages with 0 orphan routes
Navigation validation passed
```

- [ ] **Step 2: Run focused dashboard tests after regeneration**

Run:

```bash
pnpm --filter dashboard test -- apps/dashboard/app/settings/page.test.tsx apps/dashboard/app/settings/providers/page.test.tsx apps/dashboard/features/pages/brain/ai/agents/control-state.test.ts apps/dashboard/features/pages/brain/knowledge/memory/page.test.tsx tests/dashboard/scripts/generate-registry.test.ts
```

Expected:

```text
PASS apps/dashboard/app/settings/page.test.tsx
PASS apps/dashboard/app/settings/providers/page.test.tsx
PASS apps/dashboard/features/pages/brain/ai/agents/control-state.test.ts
PASS apps/dashboard/features/pages/brain/knowledge/memory/page.test.tsx
PASS tests/dashboard/scripts/generate-registry.test.ts
```

- [ ] **Step 3: Run full dashboard build validation through the lifecycle gate**

Run:

```bash
/dev-build
```

Expected:

```text
Dashboard lifecycle requested build
Build completed successfully
```

- [ ] **Step 4: Verify the new IA in the browser**

Check these routes manually in Chrome after the build completes:

```text
/settings/providers
/brain/ai/agents
/brain/knowledge/memory
/brain/knowledge/memory/workspace
/brain/knowledge/memory/profile
/brain/knowledge/memory/daily-logs
```

Expected:

```text
- Settings shows Providers as a first-class tab and no Integrations detour
- Brain no longer shows Providers
- Brain Agents opens with a visible execution summary and actionable setup state
- Memory overview shows summary content immediately
- Workspace/Profile/Daily Logs each render real content, not collapsed placeholders
```

- [ ] **Step 5: Commit generated registry files and verification-safe changes**

```bash
git add apps/dashboard/lib/tabs/generated-registry.ts apps/dashboard/app/brain/[[...slug]]/registry.ts
git commit -m "refactor: regenerate dashboard navigation for brain IA refresh"
```
