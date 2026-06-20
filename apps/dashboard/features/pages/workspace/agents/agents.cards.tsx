'use client';

import { Activity, Cpu, Globe } from 'lucide-react';
import { type ControlAttentionItem, type ExecutionPathStatus } from './control-state';
import { STATUS_ICON_MAP, statusTone } from './agents.helpers';

export function PathCard({ path }: { path: ExecutionPathStatus }) {
  const Icon = path.id === 'local' ? Cpu : Globe;

  return (
    <div className="liquid-glass-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-2">
            <Icon className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{path.label}</h3>
            <p className="mt-1 text-xs text-[var(--text-muted)]">{path.summary}</p>
          </div>
        </div>
        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${statusTone(path.status)}`}>
          {path.status}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2">
          <div className="text-lg font-semibold text-[var(--text-primary)]">{path.ready}</div>
          <div className="text-[11px] uppercase tracking-wide text-[var(--text-muted)]">Ready</div>
        </div>
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2">
          <div className="text-lg font-semibold text-[var(--text-primary)]">{path.total}</div>
          <div className="text-[11px] uppercase tracking-wide text-[var(--text-muted)]">Total</div>
        </div>
      </div>
    </div>
  );
}

export function AttentionCard({ item }: { item: ControlAttentionItem }) {
  const Icon = STATUS_ICON_MAP[item.level] ?? Activity;

  return (
    <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex items-start gap-3">
        <div className={`rounded-lg border p-2 ${statusTone(item.level)}`}>
          <Icon className="size-4" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{item.title}</h3>
            <span className="rounded-full border border-[var(--border-color)] px-2 py-0.5 text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
              {item.source}
            </span>
          </div>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{item.detail}</p>
        </div>
      </div>
    </div>
  );
}

export function OutcomeCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <p className="text-xs uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{value}</p>
      <p className="mt-1 text-xs text-[var(--text-secondary)]">{detail}</p>
    </div>
  );
}
