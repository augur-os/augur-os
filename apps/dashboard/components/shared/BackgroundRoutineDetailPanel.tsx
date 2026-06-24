'use client';

import { useEffect } from 'react';
import { Activity, MessageSquare, TriangleAlert, X } from 'lucide-react';
import { resolveIcon } from '@/lib/icon-map';
import {
  aiItemActionsFor,
  directItemActionsFor,
  type AiItemActionItem,
  type DirectItemAction,
} from '@/lib/browse/itemActions';
import type { Routine } from '@/lib/browse/types';
import { formatCadence, formatNextRun, formatRelativeTime, humanizeTokens } from '@/lib/browse/routine-format';

interface BackgroundRoutineDetailPanelProps {
  routine: Routine;
  onClose: () => void;
  onItemPrompt?: (prompt: string) => void;
  onItemDirect?: (action: DirectItemAction, item: AiItemActionItem) => void | Promise<void>;
}

function DetailBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4">
      <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
        {title}
      </h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function BackgroundRoutineDetailPanel({
  routine,
  onClose,
  onItemPrompt,
  onItemDirect,
}: BackgroundRoutineDetailPanelProps) {
  const isAiCliSpawn = routine.spawn_kind === 'ai-cli-spawn';
  const itemActionTarget: AiItemActionItem = {
    id: routine.id,
    title: routine.display_name,
    path: routine.source_path || routine.config_path || routine.id,
    hub: 'system',
    metadata: {
      sourceKind: routine.source_kind,
      status: routine.status,
      spawnKind: routine.spawn_kind,
    },
  };
  const aiActions = onItemPrompt ? aiItemActionsFor('loops', itemActionTarget) : [];
  const directActions = onItemDirect ? directItemActionsFor('loops', itemActionTarget) : [];

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <section
      className="flex h-full flex-col overflow-hidden"
      aria-label={`${routine.display_name} detail panel`}
    >
      <div className="flex items-start gap-3 border-b border-[var(--border-color)] p-4 shrink-0">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-primary)]/10">
          <Activity className="size-5 text-[var(--accent-primary)]" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="truncate text-lg font-semibold text-[var(--text-primary)]">
              {routine.display_name}
            </h2>
            <span className="rounded-md bg-[var(--bg-secondary)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)]">
              {routine.source_kind}
            </span>
            <span className={isAiCliSpawn
              ? 'rounded-md bg-[var(--accent-warning)]/15 px-2 py-0.5 text-[11px] font-medium text-[var(--accent-warning)]'
              : 'rounded-md bg-[var(--bg-secondary)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)]'}
            >
              {routine.spawn_kind}
            </span>
          </div>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            {routine.description || formatCadence(routine.cadence)}
          </p>
        </div>
        <button
          type="button"
          title="Close"
          aria-label="Close detail panel"
          onClick={onClose}
          className="rounded-lg bg-[var(--bg-secondary)] p-2.5 text-[var(--text-secondary)] transition-colors duration-200 hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] cursor-pointer"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {(aiActions.length > 0 || directActions.length > 0) ? (
          <DetailBlock title="Actions">
            <div className="flex flex-wrap items-center gap-2">
              {aiActions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => onItemPrompt?.(action.template(itemActionTarget))}
                  className="inline-flex min-h-[30px] cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-1 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
                  title={action.label}
                >
                  {(() => {
                    const Icon = resolveIcon(action.icon, MessageSquare);
                    return <Icon className="size-3.5" />;
                  })()}
                  {action.label}
                </button>
              ))}
              {directActions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => onItemDirect?.(action, itemActionTarget)}
                  className="inline-flex min-h-[30px] cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-1 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
                  title={action.label}
                >
                  {(() => {
                    const Icon = resolveIcon(action.icon, MessageSquare);
                    return <Icon className="size-3.5" />;
                  })()}
                  {action.label}
                </button>
              ))}
            </div>
          </DetailBlock>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          <DetailBlock title="Cadence">
            <div className="text-base font-medium text-[var(--text-primary)]">
              {formatCadence(routine.cadence)}
            </div>
            <div className="mt-1 text-sm text-[var(--text-secondary)]">
              next: {formatNextRun(routine.cadence?.next_run_estimated)}
            </div>
            {routine.cadence?.spec_raw ? (
              <pre className="mt-2 overflow-x-auto rounded-lg bg-[var(--bg-primary)] p-3 text-xs text-[var(--text-primary)]">
                {routine.cadence.spec_raw}
              </pre>
            ) : null}
          </DetailBlock>

          <DetailBlock title="Last Run">
            <div className="text-base font-medium text-[var(--text-primary)]">
              {formatRelativeTime(routine.last_run_at)}
              {routine.last_run_status ? ` (${routine.last_run_status})` : ''}
            </div>
            {routine.last_run_log ? (
              <div className="mt-1 truncate font-mono text-xs text-[var(--text-secondary)]">
                {routine.last_run_log}
              </div>
            ) : null}
            {routine.recent_runs_24h !== null && routine.recent_runs_24h !== undefined ? (
              <div className="mt-1 text-sm text-[var(--text-secondary)]">
                recent 24h: {routine.recent_runs_24h} run{routine.recent_runs_24h === 1 ? '' : 's'}
              </div>
            ) : null}
          </DetailBlock>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <DetailBlock title="Source">
            <div className="text-sm text-[var(--text-primary)]">{routine.source_kind}</div>
            <div className="mt-1 break-all font-mono text-xs text-[var(--text-secondary)]">
              {routine.source_path}
            </div>
          </DetailBlock>

          <DetailBlock title="Estimated Cost">
            {isAiCliSpawn && routine.ai_cost ? (
              <div className="space-y-1 text-sm text-[var(--text-primary)]">
                <div>~{humanizeTokens(routine.ai_cost.estimated_tokens_per_run)} tokens / run</div>
                <div>~{humanizeTokens(routine.ai_cost.estimated_tokens_per_day)} tokens / day</div>
                <div className="text-[var(--text-secondary)]">CLI: {routine.ai_cost.cli}</div>
              </div>
            ) : (
              <div className="text-sm text-[var(--text-secondary)]">: </div>
            )}
          </DetailBlock>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <DetailBlock title="Config">
            <div className="break-all font-mono text-xs text-[var(--text-secondary)]">
              {routine.config_path || '—'}
            </div>
          </DetailBlock>

          <DetailBlock title="Status">
            <span className="rounded-md bg-[var(--accent-success)]/10 px-2 py-0.5 text-xs text-[var(--accent-success)]">
              {routine.status}
            </span>
          </DetailBlock>
        </div>

        {routine.description ? (
          <DetailBlock title="Description">
            <p className="text-sm text-[var(--text-primary)]">{routine.description}</p>
          </DetailBlock>
        ) : null}

        {routine.warnings.length > 0 ? (
          <DetailBlock title="Warnings">
            <div className="mb-3 flex items-center gap-2">
              <TriangleAlert className="size-4 text-[var(--accent-warning)]" />
              <span className="text-sm text-[var(--text-primary)]">Routine warnings</span>
            </div>
            <ul className="space-y-2 text-sm text-[var(--text-primary)]">
              {routine.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </DetailBlock>
        ) : null}
      </div>
    </section>
  );
}
