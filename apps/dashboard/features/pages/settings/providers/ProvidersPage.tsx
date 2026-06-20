'use client';

/**
 * Providers & Usage — Settings
 *
 * System LLM configuration, remote providers, budget limits, and activity log.
 * Moved from the AI hub into the Settings shell.
 */

import { useMemo, useCallback, useEffect, useReducer, useRef } from 'react';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { mcpCall } from '@/lib/mcp/client';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import ProviderCard from '@/components/remote/ProviderCard';
import ProviderConfigModal from '@/components/remote/ProviderConfigModal';
import UsageBudgetWidget from '@/components/remote/UsageBudgetWidget';
import { getProviderList } from '@/lib/remote/providers';
import type {
  ProviderDefinition,
  ProviderConfig,
  ProviderListResponse,
  UsageStats,
  BudgetSettings,
} from '@/lib/remote/types';
import {
  Terminal,
  Layers,
  AlertTriangle,
  RefreshCw,
  Cloud,
  Info,
  Monitor,
  Save,
  Activity,
} from 'lucide-react';

type ProviderType = 'openai_compatible' | 'command' | 'enterprise' | 'agentic_ide';
type ProviderWithConfig = ProviderDefinition & { config?: ProviderConfig };

interface LLMProfile {
  provider: ProviderType;
  model?: string;
  base_url?: string;
  timeout_s?: number;
}

interface LLMConfig {
  active_profile: string;
  profiles: Record<string, LLMProfile>;
}

interface LLMConfigResponse {
  config?: LLMConfig;
  configPath?: string;
  error?: string;
}

interface ProvidersPageState {
  activeProfile: string;
  selectedProvider: ProviderDefinition | null;
  selectedConfig: ProviderConfig | undefined;
  budgetDraft: BudgetSettings;
  budgetSaving: boolean;
}

type ProvidersPageAction =
  | { type: 'set-active-profile'; activeProfile: string }
  | { type: 'open-provider'; provider: ProviderDefinition; config?: ProviderConfig }
  | { type: 'close-provider' }
  | { type: 'sync-budget'; budget: BudgetSettings }
  | { type: 'patch-budget'; patch: Partial<BudgetSettings> }
  | { type: 'reset-budget'; budget: BudgetSettings }
  | { type: 'budget-save-start' }
  | { type: 'budget-save-finish' };

const DEFAULT_BUDGET: BudgetSettings = {
  dailyLimitUsd: 10.0,
  monthlyLimitUsd: 100.0,
  warnAtPercentage: 80,
};

const DEFAULT_USAGE: UsageStats = {
  dailyCost: 0,
  monthlyCost: 0,
  dailyTokens: 0,
  monthlyTokens: 0,
  byProvider: {},
};

const INITIAL_PROVIDERS_PAGE_STATE: ProvidersPageState = {
  activeProfile: 'default',
  selectedProvider: null,
  selectedConfig: undefined,
  budgetDraft: DEFAULT_BUDGET,
  budgetSaving: false,
};

function providersPageReducer(
  state: ProvidersPageState,
  action: ProvidersPageAction,
): ProvidersPageState {
  switch (action.type) {
    case 'set-active-profile':
      return { ...state, activeProfile: action.activeProfile };
    case 'open-provider':
      return {
        ...state,
        selectedProvider: action.provider,
        selectedConfig: action.config,
      };
    case 'close-provider':
      return { ...state, selectedProvider: null, selectedConfig: undefined };
    case 'sync-budget':
    case 'reset-budget':
      return { ...state, budgetDraft: action.budget };
    case 'patch-budget':
      return {
        ...state,
        budgetDraft: { ...state.budgetDraft, ...action.patch },
      };
    case 'budget-save-start':
      return { ...state, budgetSaving: true };
    case 'budget-save-finish':
      return { ...state, budgetSaving: false };
    default:
      return state;
  }
}

function ProfileHint({ activeProfile }: { activeProfile: string }) {
  if (activeProfile === 'local') {
    return (
      <div className="mt-4 bg-[var(--accent-warning)]/10 text-[var(--accent-warning)] text-sm p-4 rounded-lg flex gap-3 items-start border border-[var(--accent-warning)]/20">
        <Terminal className="size-5 shrink-0" aria-hidden="true" />
        <div>
          <p className="font-medium">Local LLM Mode</p>
          <p className="text-[var(--accent-warning)]/80 text-xs mt-1">
            Running with Ollama/LM Studio. Ensure your local server is running at localhost:11434
          </p>
        </div>
      </div>
    );
  }
  if (activeProfile === 'agentic_ide') {
    return (
      <div className="mt-4 bg-[var(--accent-secondary)]/10 text-[var(--accent-secondary)] text-sm p-4 rounded-lg flex gap-3 items-start border border-[var(--accent-secondary)]/20">
        <Monitor className="size-5 shrink-0" aria-hidden="true" />
        <div>
          <p className="font-medium">IDE Bridge Mode</p>
          <p className="text-[var(--accent-secondary)]/80 text-xs mt-1">
            Using your IDE&apos;s built-in AI (Cursor, Claude Code). No API costs.
          </p>
        </div>
      </div>
    );
  }
  return null;
}

function useProvidersPageController() {
  const [state, dispatch] = useReducer(
    providersPageReducer,
    INITIAL_PROVIDERS_PAGE_STATE,
  );
  const budgetSyncKeyRef = useRef('');
  const {
    data: llmData,
    loading: llmLoading,
    error: llmFetchError,
    refetch: refetchLLM,
  } = useMcpQuery<LLMConfigResponse>(
    ['config', 'llm'],
    'get-settings',
    'config',
    { args: { scope: 'llm-config' } },
  );
  const {
    data: providersData,
    loading: providersLoading,
    refetch: refetchProviders,
  } = useMcpQuery<ProviderListResponse>(
    ['remote', 'providers'],
    'get-settings',
    'config',
    { args: { scope: 'remote-providers' } },
  );
  const llmConfig = llmData?.config ?? null;
  const llmError = llmData?.error ?? llmFetchError;
  const configPath = llmData?.configPath ?? '';
  const resolvedActiveProfile = llmConfig?.active_profile ?? state.activeProfile;
  const providers = useMemo<ProviderWithConfig[]>(
    () => (providersData?.providers?.length ? providersData.providers : getProviderList()),
    [providersData],
  );
  const budget = useMemo<BudgetSettings>(
    () => ({ ...DEFAULT_BUDGET, ...providersData?.budget }),
    [providersData],
  );
  const usage = useMemo<UsageStats>(
    () => ({ ...DEFAULT_USAGE, ...providersData?.usage }),
    [providersData],
  );
  const incomingBudgetKey = providersData?.budget
    ? `${providersData.budget.dailyLimitUsd}-${providersData.budget.monthlyLimitUsd}-${providersData.budget.warnAtPercentage}`
    : '';

  useEffect(() => {
    if (!incomingBudgetKey || incomingBudgetKey === budgetSyncKeyRef.current || !providersData?.budget) {
      return;
    }
    const timer = window.setTimeout(() => {
      budgetSyncKeyRef.current = incomingBudgetKey;
      dispatch({ type: 'sync-budget', budget: { ...DEFAULT_BUDGET, ...providersData.budget } });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [incomingBudgetKey, providersData?.budget]);

  const profiles = Object.keys(llmConfig?.profiles ?? {});
  const hasBudgetChanges =
    budget.dailyLimitUsd !== state.budgetDraft.dailyLimitUsd ||
    budget.monthlyLimitUsd !== state.budgetDraft.monthlyLimitUsd ||
    budget.warnAtPercentage !== state.budgetDraft.warnAtPercentage;
  const activeProviders = providers.filter((provider) => provider.config?.enabled).length;

  const saveLLMConfig = useCallback(
    async (newConfig: LLMConfig) => {
      try {
        dispatch({
          type: 'set-active-profile',
          activeProfile: newConfig.active_profile,
        });
        const data = await mcpCall<{ error?: string }>('set-config', {
          scope: 'llm-config',
          config: newConfig,
        });
        if (data.error) throw new Error(data.error);
        refetchLLM();
      } catch (err: unknown) {
        console.error(err instanceof Error ? err.message : 'Failed to save LLM config');
        refetchLLM();
      }
    },
    [refetchLLM],
  );

  const handleGlobalProfileChange = useCallback(
    (profile: string) => {
      if (!llmConfig) return;
      void saveLLMConfig({ ...llmConfig, active_profile: profile });
    },
    [llmConfig, saveLLMConfig],
  );

  const handleOpenConfig = useCallback(async () => {
    if (!configPath) return;
    try {
      await mcpCall('system-open-file', { filePath: configPath });
    } catch (err) {
      console.error('Failed to open file', err);
    }
  }, [configPath]);

  const handleConfigureProvider = useCallback(
    (providerId: string) => {
      const provider = providers.find((item) => item.id === providerId);
      if (!provider) return;
      dispatch({
        type: 'open-provider',
        provider,
        config: provider.config,
      });
    },
    [providers],
  );

  const handleSaveProviderConfig = useCallback(
    async (config: Partial<ProviderConfig>) => {
      await mcpCall('set-config', {
        scope: 'remote-provider-update',
        providerId: config.id,
        updates: config,
      });
      refetchProviders();
    },
    [refetchProviders],
  );

  const handleTestProvider = useCallback(async (providerId: string) => {
    try {
      return await mcpCall<{ success: boolean; error?: string }>('set-config', {
        scope: 'remote-provider-test',
        providerId,
      });
    } catch {
      return { success: false, error: 'Test failed' };
    }
  }, []);

  const handleStartOAuth = useCallback(async (providerId: string) => {
    const response = await fetch(`/api/remote/auth/start/${providerId}`, {
      method: 'POST',
    });
    const payload = await response.json().catch(() => null) as { url?: string; error?: string } | null;
    if (!response.ok || typeof payload?.url !== 'string') {
      throw new Error(payload?.error ?? 'Failed to start OAuth');
    }
    window.location.href = payload.url;
  }, []);

  const handleBudgetDraftChange = useCallback((patch: Partial<BudgetSettings>) => {
    dispatch({ type: 'patch-budget', patch });
  }, []);

  const handleResetBudget = useCallback(() => {
    dispatch({ type: 'reset-budget', budget });
  }, [budget]);

  const handleSaveBudget = useCallback(async () => {
    dispatch({ type: 'budget-save-start' });
    try {
      await mcpCall('set-config', {
        scope: 'remote-providers-update',
        updates: { budget: state.budgetDraft },
      });
      refetchProviders();
    } catch (err) {
      console.error('Failed to save budget settings:', err);
    } finally {
      dispatch({ type: 'budget-save-finish' });
    }
  }, [state.budgetDraft, refetchProviders]);

  return {
    activeProviders,
    budget,
    budgetDraft: state.budgetDraft,
    budgetSaving: state.budgetSaving,
    configPath,
    handleBudgetDraftChange,
    handleConfigureProvider,
    handleGlobalProfileChange,
    handleOpenConfig,
    handleResetBudget,
    handleSaveBudget,
    handleSaveProviderConfig,
    handleStartOAuth,
    handleTestProvider,
    hasBudgetChanges,
    llmError,
    llmLoading,
    profiles,
    providers,
    providersLoading,
    refetchLLM,
    refetchProviders,
    resolvedActiveProfile,
    selectedConfig: state.selectedConfig,
    selectedProvider: state.selectedProvider,
    closeProvider: () => dispatch({ type: 'close-provider' }),
    usage,
  };
}

type ProvidersPageController = ReturnType<typeof useProvidersPageController>;

export default function ProvidersPage() {
  const controller = useProvidersPageController();

  return (
    <div className="space-y-6">
      <ProvidersHeader />
      <SystemLlmSection controller={controller} />
      <UsageBudgetSection controller={controller} />
      <QuickAccessProviders controller={controller} />
      <RemoteProvidersSection controller={controller} />
      {controller.selectedProvider ? (
        <ProviderConfigModal
          provider={controller.selectedProvider}
          config={controller.selectedConfig}
          isOpen={Boolean(controller.selectedProvider)}
          onClose={controller.closeProvider}
          onSave={controller.handleSaveProviderConfig}
          onStartOAuth={controller.handleStartOAuth}
        />
      ) : null}
    </div>
  );
}

function ProvidersHeader() {
  return (
    <div className="flex items-center gap-3">
      <div className="p-2 rounded-lg bg-[var(--accent-info)]/20 border border-[var(--accent-info)]/30">
        <Cloud className="size-5 text-[var(--accent-info)]" aria-hidden="true" />
      </div>
      <div>
        <h1 className="text-xl font-bold text-[var(--text-primary)]">
          System LLM & Providers
        </h1>
        <p className="text-sm text-[var(--text-muted)]">
          System LLM configuration, remote providers, and budget limits
        </p>
      </div>
    </div>
  );
}

function SystemLlmSection({
  controller,
}: {
  controller: ProvidersPageController;
}) {
  return (
    <GlassCard className="p-5 border-[var(--accent-info)]/20">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Layers className="size-5 text-[var(--accent-info)]" aria-hidden="true" />
          <h2 className="font-semibold text-[var(--text-primary)]">System LLM</h2>
        </div>
        {controller.configPath ? (
          <Button variant="ghost" size="sm" onClick={controller.handleOpenConfig}>
            <Activity className="size-4 mr-2" aria-hidden="true" />
            Open Config
          </Button>
        ) : null}
      </div>
      {controller.llmError ? (
        <div role="alert" className="flex items-center justify-between gap-3 text-[var(--accent-danger)]">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-4 flex-shrink-0" aria-hidden="true" />
            <p className="text-sm">{controller.llmError}</p>
          </div>
          <button
            type="button"
            onClick={() => controller.refetchLLM()}
            className="text-xs underline hover:opacity-70 cursor-pointer min-h-[44px] min-w-[44px] flex items-center justify-center transition-opacity duration-200"
          >
            Retry
          </button>
        </div>
      ) : null}
      {controller.llmLoading ? (
        <div className="flex items-center justify-center py-4">
          <RefreshCw className="size-5 animate-spin text-[var(--text-muted)]" aria-hidden="true" />
        </div>
      ) : null}
      {!controller.llmError && !controller.llmLoading ? (
        <>
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
            <div className="flex-1">
              <label htmlFor="active-llm-profile" className="text-sm font-medium text-[var(--text-secondary)] mb-2 block">
                Active Profile
              </label>
              <Select
                id="active-llm-profile"
                value={controller.resolvedActiveProfile}
                onChange={(event) => controller.handleGlobalProfileChange(event.target.value)}
                className="w-full max-w-xs"
                aria-label="Active LLM profile"
              >
                {controller.profiles.map((profile) => (
                  <option key={profile} value={profile}>{profile}</option>
                ))}
              </Select>
            </div>
            <div className="text-sm text-[var(--text-muted)] flex items-center gap-2">
              <Info className="size-4" aria-hidden="true" />
              Sets the default LLM for all system operations
            </div>
          </div>
          <ProfileHint activeProfile={controller.resolvedActiveProfile} />
        </>
      ) : null}
    </GlassCard>
  );
}

function UsageBudgetSection({
  controller,
}: {
  controller: ProvidersPageController;
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <UsageBudgetWidget usage={controller.usage} budget={controller.budgetDraft} />
      <BudgetLimitsCard controller={controller} />
    </div>
  );
}

function BudgetLimitsCard({
  controller,
}: {
  controller: ProvidersPageController;
}) {
  return (
    <GlassCard className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-medium text-[var(--text-secondary)]">API Budget Limits</h2>
        {controller.hasBudgetChanges ? (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--accent-warning)]/20 text-[var(--accent-warning)]">
            Unsaved
          </span>
        ) : null}
      </div>
      <div className="space-y-3">
        <BudgetInput
          id="daily-limit-usd"
          label="Daily limit (USD)"
          min={0}
          step={0.1}
          value={controller.budgetDraft.dailyLimitUsd}
          onChange={(next) => {
            controller.handleBudgetDraftChange({
              dailyLimitUsd: Number.isFinite(next) && next >= 0
                ? next
                : controller.budgetDraft.dailyLimitUsd,
            });
          }}
        />
        <BudgetInput
          id="monthly-limit-usd"
          label="Monthly limit (USD)"
          min={0}
          step={1}
          value={controller.budgetDraft.monthlyLimitUsd}
          onChange={(next) => {
            controller.handleBudgetDraftChange({
              monthlyLimitUsd: Number.isFinite(next) && next >= 0
                ? next
                : controller.budgetDraft.monthlyLimitUsd,
            });
          }}
        />
        <BudgetInput
          id="warning-threshold-percentage"
          label="Warning threshold (%)"
          min={1}
          max={100}
          step={1}
          value={controller.budgetDraft.warnAtPercentage}
          onChange={(raw) => {
            const next = Number.isFinite(raw)
              ? Math.max(1, Math.min(100, Math.round(raw)))
              : controller.budgetDraft.warnAtPercentage;
            controller.handleBudgetDraftChange({ warnAtPercentage: next });
          }}
        />
      </div>
      <div className="flex gap-2 mt-4">
        <Button
          variant="outline"
          size="sm"
          onClick={controller.handleResetBudget}
          disabled={!controller.hasBudgetChanges || controller.budgetSaving}
          className="cursor-pointer flex-1"
        >
          Reset
        </Button>
        <Button
          size="sm"
          onClick={controller.handleSaveBudget}
          disabled={!controller.hasBudgetChanges || controller.budgetSaving}
          className="cursor-pointer flex-1 gap-1.5"
        >
          <Save className="size-3.5" aria-hidden="true" />
          {controller.budgetSaving ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </GlassCard>
  );
}

function BudgetInput({
  id,
  label,
  min,
  max,
  step,
  value,
  onChange,
}: {
  id: string;
  label: string;
  min: number;
  max?: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-xs text-[var(--text-muted)] mb-1 block">
        {label}
      </label>
      <Input
        id={id}
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={label}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </div>
  );
}

function QuickAccessProviders({
  controller,
}: {
  controller: ProvidersPageController;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mr-1">
        Quick Access
      </span>
      <span className="text-xs text-[var(--text-muted)]">
        {controller.activeProviders}/{controller.providers.length}
      </span>
      <div className="w-px h-4 bg-[var(--border-color)] mx-1" />
      {controller.providers.slice(0, 8).map((provider) => (
        <ProviderQuickButton
          key={provider.id}
          provider={provider}
          onConfigure={controller.handleConfigureProvider}
        />
      ))}
    </div>
  );
}

function ProviderQuickButton({
  provider,
  onConfigure,
}: {
  provider: ProviderWithConfig;
  onConfigure: (providerId: string) => void;
}) {
  const enabled = provider.config?.enabled === true;

  return (
    <button
      type="button"
      onClick={() => onConfigure(provider.id)}
      aria-label={`Configure ${provider.name}`}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 min-h-[36px] rounded-lg border text-sm transition-all duration-200 hover:border-[var(--border-hover)] cursor-pointer ${
        enabled
          ? 'border-[var(--accent-success)]/30 bg-[var(--accent-success)]/5 text-[var(--accent-success)]'
          : 'border-[var(--border-color)] bg-[var(--bg-surface)] text-[var(--text-secondary)]'
      }`}
    >
      <div className={`w-1.5 h-1.5 rounded-full ${enabled ? 'bg-[var(--accent-success)]' : 'bg-[var(--text-muted)]'}`} />
      {provider.name}
    </button>
  );
}

function RemoteProvidersSection({
  controller,
}: {
  controller: ProvidersPageController;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-medium text-[var(--text-secondary)] flex items-center gap-2">
          <Cloud className="size-4 text-[var(--accent-info)]" aria-hidden="true" />
          Remote Execution Providers
        </h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => controller.refetchProviders()}
          disabled={controller.providersLoading}
        >
          <RefreshCw className={`size-4 mr-2 ${controller.providersLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
          Refresh
        </Button>
      </div>
      {!controller.providersLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {controller.providers.map((provider) => (
            <ProviderCard
              key={provider.id}
              provider={provider}
              config={provider.config}
              onConfigure={controller.handleConfigureProvider}
              onTest={controller.handleTestProvider}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
