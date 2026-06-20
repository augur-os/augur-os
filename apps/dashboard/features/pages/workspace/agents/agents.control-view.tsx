'use client';

import { type RefObject } from 'react';
import {
  Activity,
  Bot,
  ChevronRight,
  Loader2,
  Play,
  RefreshCw,
  Terminal,
} from 'lucide-react';
import {
  type ControlAttentionItem,
  type ControlCta,
  type ExecutionPathStatus,
  type RegistryAgent,
} from './control-state';
import { type AgentControlState, type RegistryCoverage } from './agents.types';
import { STATUS_ICON_MAP, statusTone } from './agents.helpers';
import { AttentionCard, OutcomeCard, PathCard } from './agents.cards';
import { ConfigureAgentModal } from './agents.configure-modal';

export function AgentsControlView({
  apiPath,
  clientsSectionRef,
  controlState,
  firstFix,
  isConfigureOpen,
  isLoading,
  isRunningTests,
  lastUpdated,
  localPath,
  onConfigureClose,
  onConfigureSaved,
  onPrimaryAction,
  onRefresh,
  onRunCheck,
  primaryRunsCheck,
  registryAgents,
  registryCoverage,
  runCheckLabel,
}: {
  apiPath?: ExecutionPathStatus;
  clientsSectionRef: RefObject<HTMLDivElement | null>;
  controlState: AgentControlState;
  firstFix: ControlAttentionItem | null;
  isConfigureOpen: boolean;
  isLoading: boolean;
  isRunningTests: boolean;
  lastUpdated: Date | null;
  localPath?: ExecutionPathStatus;
  onConfigureClose: () => void;
  onConfigureSaved: () => void;
  onPrimaryAction: () => void;
  onRefresh: () => void;
  onRunCheck: (cta?: ControlCta) => Promise<void>;
  primaryRunsCheck: boolean;
  registryAgents: RegistryAgent[];
  registryCoverage: RegistryCoverage;
  runCheckLabel: string;
}) {
  const ExecutionStatusIcon = STATUS_ICON_MAP[controlState.execution.status] ?? Activity;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="rounded-xl border border-[var(--accent-primary)]/25 bg-[var(--accent-primary)]/10 p-3">
            <Bot className="size-5 text-[var(--accent-primary)]" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-2xl font-semibold text-[var(--text-primary)]">Agent Control Center</h2>
            <p className="mt-1 max-w-2xl text-sm text-[var(--text-secondary)]">
              See which execution paths Augur can use right now, what setup is blocking them,
              and which action restores useful agent work fastest.
            </p>
            {lastUpdated ? (
              <p className="mt-2 text-xs text-[var(--text-muted)]">
                Updated {lastUpdated.toLocaleTimeString()}
              </p>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={primaryRunsCheck && isRunningTests}
            onClick={onPrimaryAction}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-sm font-medium text-[var(--accent-foreground)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {primaryRunsCheck && isRunningTests ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <ChevronRight className="size-4" aria-hidden="true" />
            )}
            {primaryRunsCheck && isRunningTests ? 'Checking...' : controlState.primaryCta.label}
          </button>
          <button
            type="button"
            onClick={() => void onRunCheck()}
            disabled={isRunningTests}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className={`size-4 ${isRunningTests ? 'animate-pulse' : ''}`} aria-hidden="true" />
            {runCheckLabel}
          </button>
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            aria-label="Refresh agent control center"
            title="Refresh"
            className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className={`size-4 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
          </button>
        </div>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <OutcomeCard
          label="Client readiness"
          value={`${localPath?.ready ?? 0}/${localPath?.total ?? 0} local routes ready`}
          detail={
            (localPath?.ready ?? 0) > 0
              ? 'Local agent work can run through at least one synced client or backend.'
              : 'Local agent work is blocked until a client or backend is ready.'
          }
        />
        <OutcomeCard
          label="Provider readiness"
          value={`${apiPath?.ready ?? 0}/${apiPath?.total ?? 0} providers ready`}
          detail={
            (apiPath?.ready ?? 0) > 0
              ? 'Remote execution is available through a configured API provider.'
              : 'Remote execution needs enabled providers with valid keys.'
          }
        />
        <OutcomeCard
          label="Test now"
          value={controlState.primaryCta.label}
          detail={controlState.primaryCta.detail}
        />
        <OutcomeCard
          label="Fix this"
          value={firstFix?.title ?? 'No blockers detected'}
          detail={firstFix?.detail ?? 'The current execution path has no reported setup blockers.'}
        />
      </section>

      <section className="liquid-glass-card p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${statusTone(controlState.execution.status)}`}>
              <ExecutionStatusIcon className="size-3.5" aria-hidden="true" />
              {controlState.execution.status}
            </div>
            <h2 className="mt-3 text-xl font-semibold text-[var(--text-primary)]">
              {controlState.execution.summary}
            </h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">{controlState.execution.detail}</p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
              <div className="text-2xl font-semibold text-[var(--text-primary)]">{controlState.stats.registeredAgents}</div>
              <div className="mt-1 text-xs uppercase tracking-wide text-[var(--text-muted)]">Registered</div>
            </div>
            <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
              <div className="text-2xl font-semibold text-[var(--text-primary)]">{controlState.stats.projectAgents + controlState.stats.pluginAgents}</div>
              <div className="mt-1 text-xs uppercase tracking-wide text-[var(--text-muted)]">Browse inventory</div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {controlState.paths.map((path) => (
              <PathCard key={path.id} path={path} />
            ))}
          </div>

          <div className="space-y-3">
            {controlState.attention.length > 0 ? (
              controlState.attention.map((item) => <AttentionCard key={item.id} item={item} />)
            ) : (
              <div className="rounded-xl border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 text-sm text-[var(--text-secondary)]">
                No attention items detected.
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            <div className="flex items-center gap-2">
              <Terminal className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">Dispatch</h3>
            </div>
            <div className="mt-3 space-y-2">
              <div className="text-sm font-medium text-[var(--text-primary)]">{controlState.dispatch.summary}</div>
              <p className="text-sm text-[var(--text-secondary)]">{controlState.dispatch.detail}</p>
            </div>
          </div>

          <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            <div className="flex items-center gap-2">
              <Bot className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">Providers</h3>
            </div>
            <div className="mt-3 space-y-3">
              {controlState.providers.length > 0 ? (
                controlState.providers.map((provider) => (
                  <div key={provider.id} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-[var(--text-primary)]">{provider.name}</div>
                        <div className="mt-1 text-xs text-[var(--text-muted)]">{provider.defaultModel || 'No default model set'}</div>
                      </div>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${statusTone(provider.status)}`}>
                        {provider.status}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-card)] p-3 text-sm text-[var(--text-secondary)]">
                  No remote providers are registered yet. Provider configuration will appear here after setup.
                </div>
              )}
            </div>
          </div>

          <div ref={clientsSectionRef} className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            <div className="flex items-center gap-2">
              <Activity className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">Registry coverage</h3>
            </div>
            {registryAgents.length ? (
              <div className="mt-3 space-y-3">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
                    <div className="text-lg font-semibold text-[var(--text-primary)]">{registryCoverage.mcpCapable}</div>
                    <div className="mt-1 text-xs uppercase tracking-wide text-[var(--text-muted)]">MCP-Capable</div>
                  </div>
                  <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
                    <div className="text-lg font-semibold text-[var(--text-primary)]">{registryCoverage.isolated}</div>
                    <div className="mt-1 text-xs uppercase tracking-wide text-[var(--text-muted)]">Isolated</div>
                  </div>
                </div>
                <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
                  <div className="text-[11px] uppercase tracking-wide text-[var(--text-muted)]">Registry Roles</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {registryCoverage.roles.length > 0 ? (
                      registryCoverage.roles.map((role) => (
                        <span
                          key={role}
                          className="rounded-full border border-[var(--border-color)] px-2 py-1 text-[11px] text-[var(--text-secondary)]"
                        >
                          {role}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-[var(--text-secondary)]">No role metadata reported.</span>
                    )}
                  </div>
                  <p className="mt-3 text-sm text-[var(--text-secondary)]">
                    Browse owns the full agent inventory. This view stays focused on execution coverage and control-path readiness.
                  </p>
                </div>
              </div>
            ) : (
              <div className="mt-4">
                <div className="rounded-xl border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 text-sm text-[var(--text-secondary)]">
                  No registered agents were returned by the registry. Check the AI skill registry if this stays empty.
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      <ConfigureAgentModal
        isOpen={isConfigureOpen}
        onClose={onConfigureClose}
        onSaved={onConfigureSaved}
      />
    </div>
  );
}
