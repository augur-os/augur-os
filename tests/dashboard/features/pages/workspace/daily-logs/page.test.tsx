/**
 * @jest-environment jsdom
 */
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import MemoryDailyLogsPage from '@/features/pages/workspace/daily-logs/page';

let lastWorkbenchProps: Record<string, unknown> | null = null;

jest.mock('@/features/pages/workspace/memory/hooks', () => ({
  useMemoryDashboardData: () => ({
    stats: {
      totalDecisions: 3,
      totalPatterns: 1,
      totalPreferences: 1,
      dailyLogs: 4,
      lastCurated: '2026-04-23T10:00:00.000Z',
      recentDecisions: [],
      categoryCounts: {},
    },
  }),
  useDailyLogs: () => ({
    calendarMonth: new Date('2026-04-01T12:00:00.000Z'),
    setCalendarMonth: jest.fn(),
    dailyLogs: [
      {
        date: '2026-04-21',
        hasLog: true,
        entryCount: 2,
        preview: 'Keep Brain pages flat.',
        kindCounts: { decision: 2 },
      },
    ],
    selectedLog: '2026-04-21',
    logContent: '# Session Log: 2026-04-21',
    source: {
      exists: true,
      label: 'Daily memory logs',
      kind: 'markdown-directory',
      modifiedAt: '2026-04-21T16:28:42.015245+00:00',
    },
    generatedAt: '2026-04-23T14:28:42.015245+00:00',
    logError: null,
    isLogLoading: false,
    fetchLogContent: jest.fn(),
    clearSelection: jest.fn(),
    hasLogForDate: jest.fn(() => true),
    getLogEntryCount: jest.fn(() => 2),
    getCalendarDays: jest.fn(() => []),
    openSelectedLog: jest.fn(),
    openingSelectedLog: false,
    openLogError: null,
  }),
}));

jest.mock('@/features/pages/workspace/daily-logs/components/DailyLogsWorkbench', () => ({
  DailyLogsWorkbench: (props: Record<string, unknown>) => {
    lastWorkbenchProps = props;
    return <div>Daily logs workbench</div>;
  },
}));

describe('MemoryDailyLogsPage', () => {
  beforeEach(() => {
    lastWorkbenchProps = null;
  });

  it('renders a dedicated daily logs workbench instead of only the raw calendar', () => {
    render(<MemoryDailyLogsPage />);

    expect(screen.getByText('Daily Logs')).toBeInTheDocument();
    expect(screen.getByText(/Review real session logs, jump into the latest entries/)).toBeInTheDocument();
    expect(screen.getByText('Daily logs workbench')).toBeInTheDocument();
    expect(lastWorkbenchProps?.dailyLogs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          date: '2026-04-21',
          preview: 'Keep Brain pages flat.',
        }),
      ]),
    );
  });
});
