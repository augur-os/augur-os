/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import type { ReactNode } from 'react';
import { DailyLogsCalendar } from '@/features/pages/workspace/memory/components/DailyLogsCalendar';

const mockMcpCall = jest.fn();

jest.mock('@/lib/mcp/client', () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

jest.mock('@/features/components/DashboardWidget', () => ({
  __esModule: true,
  default: ({ children, title }: { children: ReactNode; title: string }) => (
    <section aria-label={title}>{children}</section>
  ),
}));

describe('DailyLogsCalendar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const baseProps = {
    calendarMonth: new Date('2026-04-01T00:00:00.000Z'),
    setCalendarMonth: jest.fn(),
    selectedLog: '2026-04-22',
    logContent: '',
    lastCurated: '2026-04-21',
    onSelectDate: jest.fn(),
    onClearSelection: jest.fn(),
    hasLogForDate: jest.fn(() => false),
    getLogEntryCount: jest.fn(() => 0),
    getCalendarDays: jest.fn(() => [null]),
  };

  it('shows source and generated metadata in the selected log header', () => {
    render(
      <DailyLogsCalendar
        {...baseProps}
        sourceLabel="Daily memory source"
        generatedAt="2026-04-22T10:30:00.000Z"
      />,
    );

    expect(screen.getByText(/Source: Daily memory source/)).toBeInTheDocument();
    expect(screen.getByText(/Generated: 2026-04-22T10:30:00.000Z/)).toBeInTheDocument();
  });

  it('shows a visible alert when opening in the editor fails', async () => {
    mockMcpCall.mockResolvedValueOnce({ success: false, error: 'No editor configured' });

    render(
      <DailyLogsCalendar
        {...baseProps}
        sourceLabel="Daily memory source"
        generatedAt="2026-04-22T10:30:00.000Z"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /open in editor/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('No editor configured');
    });
  });

  it('shows an empty content state when the selected log has no content', () => {
    render(
      <DailyLogsCalendar
        {...baseProps}
        sourceLabel="Daily memory source"
        generatedAt="2026-04-22T10:30:00.000Z"
        isLogLoading={false}
      />,
    );

    expect(screen.getByText('No content returned for this date.')).toBeInTheDocument();
  });

  it('renders selected log dates without shifting them to the previous local day', () => {
    render(
      <DailyLogsCalendar
        {...baseProps}
        selectedLog="2026-04-21"
        logContent="# Session Log: 2026-04-21"
      />,
    );

    expect(
      screen.getByText('Log: Tuesday, April 21, 2026'),
    ).toBeInTheDocument();
  });
});
