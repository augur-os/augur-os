/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import type { ReactNode } from 'react';
import { DailyLogsWorkbench } from '@/features/pages/workspace/daily-logs/components/DailyLogsWorkbench';

jest.mock('@/features/components/DashboardWidget', () => ({
  __esModule: true,
  default: ({ children, title }: { children: ReactNode; title: string }) => (
    <section aria-label={title}>{children}</section>
  ),
}));

jest.mock('@/features/pages/workspace/memory/components/DailyLogsCalendar', () => ({
  DailyLogsCalendar: () => <div>Daily logs calendar</div>,
}));

describe('DailyLogsWorkbench', () => {
  const baseProps = {
    dailyLogs: [
      {
        date: '2026-04-21',
        hasLog: true,
        entryCount: 3,
        preview: 'Keep Brain pages flat. Follow up on task extraction.',
        kindCounts: { decision: 2, task: 1 },
      },
      {
        date: '2026-04-13',
        hasLog: true,
        entryCount: 2,
        preview: 'Keep responses concise.',
        kindCounts: { preference: 1, decision: 1 },
      },
    ],
    selectedLog: '2026-04-21',
    logContent: '# Session Log: 2026-04-21',
    lastCurated: '2026-04-23T10:00:00.000Z',
    sourceLabel: 'Daily memory logs',
    generatedAt: '2026-04-23T14:28:42.015245+00:00',
    logError: null,
    isLogLoading: false,
    openingSelectedLog: false,
    openLogError: null,
    calendarMonth: new Date('2026-04-01T12:00:00.000Z'),
    setCalendarMonth: jest.fn(),
    onSelectDate: jest.fn(),
    onClearSelection: jest.fn(),
    hasLogForDate: jest.fn(() => true),
    getLogEntryCount: jest.fn(() => 2),
    getCalendarDays: jest.fn(() => []),
    onOpenSelectedLog: jest.fn(),
  };

  beforeEach(() => {
    jest.useFakeTimers().setSystemTime(Date.parse('2026-04-21T15:00:00Z'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('shows recent log shortcuts and source actions around the calendar', () => {
    render(<DailyLogsWorkbench {...baseProps} />);

    expect(screen.getByLabelText('Recent Logs')).toBeInTheDocument();
    expect(screen.getByLabelText('Log Summary')).toBeInTheDocument();
    expect(screen.getByLabelText('Log Viewer')).toBeInTheDocument();
    expect(screen.getAllByText(/Keep Brain pages flat/).length).toBeGreaterThan(0);
    expect(screen.getByText('Daily logs calendar')).toBeInTheDocument();
  });

  it('lets users jump to a recent log and open the selected source file', () => {
    render(<DailyLogsWorkbench {...baseProps} />);

    fireEvent.click(screen.getByRole('button', { name: /View April 13, 2026 log/i }));
    fireEvent.click(screen.getByRole('button', { name: /Open selected log/i }));

    expect(baseProps.onSelectDate).toHaveBeenCalledWith('2026-04-13');
    expect(baseProps.onOpenSelectedLog).toHaveBeenCalled();
  });

  it('shows extracted decision and task visibility for the selected log', () => {
    render(<DailyLogsWorkbench {...baseProps} />);

    expect(screen.getByLabelText('Review Signals')).toHaveTextContent('2 decisions');
    expect(screen.getByLabelText('Review Signals')).toHaveTextContent('1 task');
  });

  it('compares the latest log against the previous review day', () => {
    render(<DailyLogsWorkbench {...baseProps} />);

    expect(screen.getByLabelText('Today vs previous')).toBeInTheDocument();
    expect(screen.getByText('+1 signals')).toBeInTheDocument();
    expect(screen.getByText(/April 21, 2026 vs April 13, 2026/i)).toBeInTheDocument();
  });

  it('provides a current-day jump when a log exists for today', () => {
    render(<DailyLogsWorkbench {...baseProps} selectedLog={null} />);

    fireEvent.click(screen.getByRole('button', { name: /View today's log/i }));

    expect(baseProps.onSelectDate).toHaveBeenCalledWith('2026-04-21');
  });
});
