'use client';

import { Calendar } from 'lucide-react';
import { useDailyLogs, useMemoryDashboardData } from '../memory/hooks';
import { DailyLogsWorkbench } from './components/DailyLogsWorkbench';

export default function MemoryDailyLogsPage() {
  const { stats } = useMemoryDashboardData();
  const {
    calendarMonth,
    setCalendarMonth,
    dailyLogs,
    selectedLog,
    logContent,
    source,
    generatedAt,
    logError,
    isLogLoading,
    openSelectedLog,
    openingSelectedLog,
    openLogError,
    fetchLogContent,
    clearSelection,
    hasLogForDate,
    getLogEntryCount,
    getCalendarDays,
  } = useDailyLogs();

  return (
    <div className="space-y-6">
      <header className="flex items-start gap-3">
        <div className="rounded-xl border border-purple-500/25 bg-purple-500/10 p-3">
          <Calendar className="size-5 text-purple-400" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Daily Logs</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Review real session logs, jump into the latest entries, and open the original markdown files.
          </p>
        </div>
      </header>

      <DailyLogsWorkbench
        calendarMonth={calendarMonth}
        setCalendarMonth={setCalendarMonth}
        dailyLogs={dailyLogs}
        selectedLog={selectedLog}
        logContent={logContent}
        lastCurated={stats?.lastCurated ?? null}
        sourceLabel={source?.label ?? undefined}
        generatedAt={generatedAt}
        logError={logError}
        isLogLoading={isLogLoading}
        onOpenSelectedLog={openSelectedLog}
        openingSelectedLog={openingSelectedLog}
        openLogError={openLogError}
        onSelectDate={fetchLogContent}
        onClearSelection={clearSelection}
        hasLogForDate={hasLogForDate}
        getLogEntryCount={getLogEntryCount}
        getCalendarDays={getCalendarDays}
      />
    </div>
  );
}
