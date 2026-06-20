'use client';

import { useState } from 'react';
import DashboardWidget from '@/features/components/DashboardWidget';
import { Calendar, ChevronLeft, ChevronRight, Clock, ExternalLink, X } from 'lucide-react';
import { mcpCall } from '@/lib/mcp/client';
import { assertMcpSuccess } from '../contracts';
import { formatDateKey, parseDateKey } from '@/features/pages/workspace/daily-logs/date-utils';

interface DailyLogsCalendarProps {
  calendarMonth: Date;
  setCalendarMonth: (d: Date) => void;
  selectedLog: string | null;
  logContent: string;
  lastCurated: string | null;
  sourceLabel?: string;
  generatedAt?: string | null;
  logError?: string | null;
  isLogLoading?: boolean;
  onSelectDate: (date: string) => void;
  onClearSelection: () => void;
  hasLogForDate: (date: Date) => boolean;
  getLogEntryCount: (date: Date) => number;
  getCalendarDays: () => (Date | null)[];
}

export function DailyLogsCalendar({
  calendarMonth, setCalendarMonth,
  selectedLog, logContent, lastCurated,
  sourceLabel, generatedAt, logError, isLogLoading = false,
  onSelectDate, onClearSelection,
  hasLogForDate, getLogEntryCount, getCalendarDays,
}: DailyLogsCalendarProps) {
  const [isOpening, setIsOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);
  const todayKey = formatDateKey(new Date());

  const handleOpenInEditor = async () => {
    if (!selectedLog) return;
    setIsOpening(true);
    setOpenError(null);
    try {
      const response = await mcpCall<unknown>('knowledge-memory-daily-logs-open', { date: selectedLog });
      assertMcpSuccess(response, 'Open daily log in editor');
    } catch (err) {
      setOpenError(err instanceof Error ? err.message : 'Could not reach server');
    } finally {
      setIsOpening(false);
    }
  };

  return (
    <DashboardWidget title="Daily Session Logs" icon={Calendar} fillHeight={false}>
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <button type="button"
              onClick={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1))}
              className="min-w-[44px] min-h-[44px] flex items-center justify-center hover:bg-[var(--bg-hover)] rounded transition-colors cursor-pointer"
              aria-label="Previous month"
            >
              <ChevronLeft className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
            </button>
            <span className="text-[var(--text-primary)] font-medium min-w-[140px] text-center">
              {calendarMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
            </span>
            <button type="button"
              onClick={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1))}
              className="min-w-[44px] min-h-[44px] flex items-center justify-center hover:bg-[var(--bg-hover)] rounded transition-colors cursor-pointer"
              aria-label="Next month"
            >
              <ChevronRight className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
            </button>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2 text-xs text-[var(--text-muted)]">
            {sourceLabel && (
              <span className="inline-flex items-center gap-1 rounded-full border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2 py-1 text-[var(--text-secondary)]">
                Source: {sourceLabel}
              </span>
            )}
            {generatedAt && (
              <span className="inline-flex items-center gap-1 rounded-full border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2 py-1 text-[var(--text-secondary)]">
                Generated: {generatedAt}
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <Clock className="size-3" aria-hidden="true" />
              <span>Last curated: {lastCurated || 'Never'}</span>
            </span>
          </div>
        </div>

        {/* Calendar Grid */}
        <div className="grid grid-cols-7 gap-1 mb-4">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
            <div key={day} className="text-xs text-[var(--text-muted)] text-center py-2">{day}</div>
          ))}
          {getCalendarDays().map((date, i) => {
            if (!date) {
              return <div key={`empty-${i}`} className="p-2" />;
            }
            const hasLog = hasLogForDate(date);
            const entryCount = getLogEntryCount(date);
            const dateStr = formatDateKey(date);
            const isToday = todayKey === dateStr;
            const isSelected = selectedLog === dateStr;

            return (
              <button type="button"
                key={dateStr}
                onClick={() => hasLog && onSelectDate(dateStr)}
                disabled={!hasLog}
                aria-label={`${date.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}${hasLog ? `, ${entryCount} entries` : ''}`}
                className={`p-2 rounded-lg text-center transition-colors duration-200 ${
                  isSelected
                    ? 'bg-purple-500/30 border border-purple-500/50'
                    : hasLog
                      ? 'bg-purple-500/20 border border-purple-500/30 hover:bg-purple-500/30 cursor-pointer'
                      : 'bg-[var(--bg-secondary)] border border-[var(--border-color)]/30 cursor-default'
                } ${isToday ? 'ring-2 ring-purple-400/50' : ''}`}
              >
                <div className={`text-sm ${hasLog ? 'text-[var(--accent-secondary)] font-medium' : 'text-[var(--text-muted)]'}`}>
                  {date.getDate()}
                </div>
                {hasLog && (
                  <div className="text-[10px] text-purple-400">{entryCount}</div>
                )}
              </button>
            );
          })}
        </div>

        {/* Selected Log Content */}
        {selectedLog && (
          <div className="mt-4 p-4 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-[var(--text-primary)]">
                Log: {parseDateKey(selectedLog).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
              </h4>
              <div className="flex items-center gap-1">
                <button type="button"
                  onClick={handleOpenInEditor}
                  disabled={isOpening}
                  title="Open in system editor"
                  className="flex items-center gap-1 px-2 min-h-[44px] text-xs text-[var(--accent-secondary)] hover:text-[var(--text-primary)] hover:bg-purple-500/20 rounded transition-colors disabled:opacity-50 cursor-pointer"
                >
                  <ExternalLink className="size-3" aria-hidden="true" />
                  {isOpening ? 'Opening...' : 'Open in Editor'}
                </button>
                <button type="button"
                  onClick={onClearSelection}
                  aria-label="Close log viewer"
                  className="min-w-[44px] min-h-[44px] flex items-center justify-center hover:bg-[var(--bg-hover)] rounded transition-colors cursor-pointer"
                >
                  <X className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
                </button>
              </div>
            </div>
            {(openError || logError) && (
              <div className="mb-3 space-y-2">
                {openError && (
                  <div className="rounded-lg border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 px-3 py-2 text-xs text-[var(--text-primary)]" role="alert">
                    {openError}
                  </div>
                )}
                {logError && (
                  <div className="rounded-lg border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 px-3 py-2 text-xs text-[var(--text-primary)]" role="alert">
                    {logError}
                  </div>
                )}
              </div>
            )}
            {isLogLoading ? (
              <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-card)] px-4 py-6 text-sm text-[var(--text-muted)]">
                Loading daily log content…
              </div>
            ) : logContent ? (
              <pre className="text-xs text-[var(--text-secondary)] whitespace-pre-wrap max-h-64 overflow-y-auto font-mono">
                {logContent}
              </pre>
            ) : (
              <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-card)] px-4 py-6 text-sm text-[var(--text-muted)]">
                No content returned for this date.
              </div>
            )}
          </div>
        )}

        <p className="text-xs text-[var(--text-muted)] mt-3">
          Click on highlighted dates to view session logs. Logs are automatically curated into MEMORY.md.
        </p>
      </div>
    </DashboardWidget>
  );
}
