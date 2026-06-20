'use client';

import DashboardWidget from '@/features/components/DashboardWidget';
import { DailyLogsCalendar } from '@/features/pages/workspace/memory/components/DailyLogsCalendar';
import { formatFreshness } from '@/features/pages/workspace/memory/contracts';
import type { DailyLogInfo } from '@/features/pages/workspace/memory/types';
import { formatDateKey, parseDateKey } from '../date-utils';
import { CalendarDays, Clock3, ExternalLink, FileText, ListTree } from 'lucide-react';

interface DailyLogsWorkbenchProps {
  dailyLogs: DailyLogInfo[];
  selectedLog: string | null;
  logContent: string;
  lastCurated: string | null;
  sourceLabel?: string;
  generatedAt?: string | null;
  logError?: string | null;
  isLogLoading?: boolean;
  openingSelectedLog: boolean;
  openLogError?: string | null;
  calendarMonth: Date;
  setCalendarMonth: (date: Date) => void;
  onSelectDate: (date: string) => void;
  onClearSelection: () => void;
  hasLogForDate: (date: Date) => boolean;
  getLogEntryCount: (date: Date) => number;
  getCalendarDays: () => (Date | null)[];
  onOpenSelectedLog: () => void;
}

function formatLogDate(dateKey: string) {
  return parseDateKey(dateKey).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function signalSummary(kindCounts?: Record<string, number> | null) {
  if (!kindCounts) return 'No signal breakdown';
  const summary = Object.entries(kindCounts).flatMap(([kind, count]) =>
    count > 0 ? [`${count} ${kind}${count === 1 ? '' : 's'}`] : [],
  );
  return summary.length > 0 ? summary.join(' • ') : 'No signal breakdown';
}

function signalEntries(kindCounts?: Record<string, number> | null) {
  return Object.entries(kindCounts ?? {})
    .filter(([, count]) => count > 0)
    .sort((left, right) => right[1] - left[1]);
}

function signalLabel(kind: string, count: number) {
  return `${count} ${kind}${count === 1 ? '' : 's'}`;
}

function formatSignalDelta(delta: number) {
  if (delta > 0) return `+${delta} signals`;
  if (delta < 0) return `${delta} signals`;
  return 'No signal change';
}

export function DailyLogsWorkbench({
  dailyLogs,
  selectedLog,
  logContent,
  lastCurated,
  sourceLabel,
  generatedAt,
  logError,
  isLogLoading = false,
  openingSelectedLog,
  openLogError,
  calendarMonth,
  setCalendarMonth,
  onSelectDate,
  onClearSelection,
  hasLogForDate,
  getLogEntryCount,
  getCalendarDays,
  onOpenSelectedLog,
}: DailyLogsWorkbenchProps) {
  const latestLog = dailyLogs[0] ?? null;
  const previousLog = dailyLogs[1] ?? null;
  const totalSignals = dailyLogs.reduce((sum, log) => sum + (log.entryCount || 0), 0);
  const selectedMeta = selectedLog ? dailyLogs.find((log) => log.date === selectedLog) ?? null : null;
  const selectedSignalEntries = signalEntries(selectedMeta?.kindCounts);
  const todayKey = formatDateKey(new Date());
  const todayLog = dailyLogs.find((log) => log.date === todayKey && log.hasLog) ?? null;
  const latestDelta = latestLog && previousLog ? (latestLog.entryCount || 0) - (previousLog.entryCount || 0) : null;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <div className="space-y-6">
          <DashboardWidget title="Recent Logs" icon={CalendarDays} fillHeight={false} maxHeight={null} scrollable={false}>
            <div className="space-y-3 p-4">
              {dailyLogs.length > 0 ? (
                dailyLogs.slice(0, 4).map((log) => (
                  <div key={log.date} className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-[var(--text-primary)]">{formatLogDate(log.date)}</p>
                        <p className="mt-1 text-xs text-[var(--text-muted)]">{signalSummary(log.kindCounts)}</p>
                        {log.preview && (
                          <p className="mt-2 text-sm text-[var(--text-secondary)] line-clamp-3">{log.preview}</p>
                        )}
                      </div>
                      <button
                        type="button"
                        aria-label={`View ${formatLogDate(log.date)} log`}
                        onClick={() => onSelectDate(log.date)}
                        className="min-h-[44px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
                      >
                        View
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-6 text-sm text-[var(--text-muted)]">
                  No daily logs yet. Session logs will appear here after the next retained memory event.
                </div>
              )}
            </div>
          </DashboardWidget>

          <DailyLogsCalendar
            calendarMonth={calendarMonth}
            setCalendarMonth={setCalendarMonth}
            selectedLog={selectedLog}
            logContent={logContent}
            lastCurated={lastCurated}
            sourceLabel={sourceLabel}
            generatedAt={generatedAt}
            logError={logError}
            isLogLoading={isLogLoading}
            onSelectDate={onSelectDate}
            onClearSelection={onClearSelection}
            hasLogForDate={hasLogForDate}
            getLogEntryCount={getLogEntryCount}
            getCalendarDays={getCalendarDays}
          />
        </div>

        <div className="space-y-6">
          <DashboardWidget title="Log Summary" icon={ListTree} fillHeight={false} maxHeight={null} scrollable={false}>
            <div className="space-y-3 p-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-[var(--text-muted)]">Log days</p>
                  <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{dailyLogs.length}</p>
                </div>
                <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-[var(--text-muted)]">Signals</p>
                  <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{totalSignals}</p>
                </div>
                <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-[var(--text-muted)]">Latest log</p>
                  <p className="mt-2 text-sm font-medium text-[var(--text-primary)]">
                    {latestLog ? formatLogDate(latestLog.date) : 'No logs yet'}
                  </p>
                </div>
                <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-[var(--text-muted)]">Last curated</p>
                  <p className="mt-2 text-sm font-medium text-[var(--text-primary)]">
                    {lastCurated ? formatFreshness(lastCurated) : 'Never curated'}
                  </p>
                </div>
              </div>

              {todayLog && (
                <button
                  type="button"
                  aria-label="View today's log"
                  onClick={() => onSelectDate(todayLog.date)}
                  className="inline-flex min-h-[44px] w-full items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
                >
                  View today&apos;s log
                </button>
              )}
            </div>
          </DashboardWidget>

          {latestLog && previousLog && (
            <DashboardWidget title="Today vs previous" icon={CalendarDays} fillHeight={false} maxHeight={null} scrollable={false}>
              <div className="space-y-2 p-4">
                <p className="text-2xl font-semibold text-[var(--text-primary)]">
                  {latestDelta !== null ? formatSignalDelta(latestDelta) : 'No comparison'}
                </p>
                <p className="text-sm text-[var(--text-secondary)]">
                  {formatLogDate(latestLog.date)} vs {formatLogDate(previousLog.date)}
                </p>
                <div className="grid gap-2 text-xs text-[var(--text-muted)] sm:grid-cols-2">
                  <span>{signalSummary(latestLog.kindCounts)}</span>
                  <span>{signalSummary(previousLog.kindCounts)}</span>
                </div>
              </div>
            </DashboardWidget>
          )}

          {selectedMeta && (
            <DashboardWidget title="Review Signals" icon={ListTree} fillHeight={false} maxHeight={null} scrollable={false}>
              <div className="space-y-2 p-4">
                {selectedSignalEntries.length > 0 ? (
                  selectedSignalEntries.map(([kind, count]) => (
                    <div key={kind} className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2">
                      <span className="text-sm capitalize text-[var(--text-secondary)]">{kind}</span>
                      <span className="text-sm font-medium text-[var(--text-primary)]">{signalLabel(kind, count)}</span>
                    </div>
                  ))
                ) : (
                  <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] p-3 text-sm text-[var(--text-muted)]">
                    No extracted signal counts for this log.
                  </div>
                )}
              </div>
            </DashboardWidget>
          )}

          <DashboardWidget title="Log Viewer" icon={FileText} fillHeight={false} maxHeight={null} scrollable={false}>
            <div className="space-y-3 p-4">
              {selectedMeta ? (
                <>
                  <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                    <p className="text-sm font-medium text-[var(--text-primary)]">{formatLogDate(selectedMeta.date)}</p>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">{signalSummary(selectedMeta.kindCounts)}</p>
                    {selectedMeta.preview && (
                      <p className="mt-2 text-sm text-[var(--text-secondary)] line-clamp-4">{selectedMeta.preview}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={onOpenSelectedLog}
                    disabled={openingSelectedLog}
                    className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <ExternalLink className="size-4" aria-hidden="true" />
                    {openingSelectedLog ? 'Opening...' : 'Open selected log'}
                  </button>
                  {openLogError && (
                    <div role="alert" className="rounded-lg border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 px-3 py-2 text-xs text-[var(--text-primary)]">
                      {openLogError}
                    </div>
                  )}
                </>
              ) : (
                <div className="rounded-xl border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-6 text-sm text-[var(--text-muted)]">
                  Choose a recent log or click a highlighted calendar date to inspect it here.
                </div>
              )}

              {sourceLabel && (
                <div className="inline-flex items-center gap-2 text-xs text-[var(--text-muted)]">
                  <Clock3 className="size-3.5" aria-hidden="true" />
                  <span>{sourceLabel}</span>
                </div>
              )}
            </div>
          </DashboardWidget>
        </div>
      </div>
    </div>
  );
}
