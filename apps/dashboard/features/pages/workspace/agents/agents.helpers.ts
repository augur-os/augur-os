import { useRouter } from 'next/navigation';
import { AlertTriangle, CheckCircle2, KeyRound, XCircle } from 'lucide-react';
import { type ControlCta } from './control-state';

export function parseAgentCommand(value: string) {
  return value
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

export function statusTone(status: string) {
  switch (status) {
    case 'healthy':
    case 'ready':
      return 'border-[var(--accent-success)]/25 bg-[var(--accent-success)]/10 text-[var(--accent-success)]';
    case 'setup-required':
      return 'border-[var(--accent-warning)]/25 bg-[var(--accent-warning)]/10 text-[var(--accent-warning)]';
    case 'degraded':
    case 'issues':
      return 'border-[var(--accent-warning)]/25 bg-[var(--accent-warning)]/10 text-[var(--accent-warning)]';
    case 'offline':
    case 'not_installed':
    case 'disabled':
      return 'border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 text-[var(--accent-danger)]';
    default:
      return 'border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)]';
  }
}

export const STATUS_ICON_MAP = {
  healthy: CheckCircle2,
  ready: CheckCircle2,
  'setup-required': KeyRound,
  degraded: AlertTriangle,
  issues: AlertTriangle,
  offline: XCircle,
  not_installed: XCircle,
  disabled: XCircle,
} as const;

export function runPrimaryAction(
  cta: ControlCta,
  options: {
    router: ReturnType<typeof useRouter>;
    onOpenConfigure: () => void;
    onRunCheck: (cta: ControlCta) => Promise<void>;
    clientsSection: HTMLDivElement | null;
  },
) {
  if (cta.action === 'open-provider-settings') {
    options.router.push('/settings/providers');
    return;
  }
  if (cta.action === 'configure-agent') {
    options.onOpenConfigure();
    return;
  }
  if (cta.action === 'open-sync-status') {
    options.clientsSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  void options.onRunCheck(cta);
}
