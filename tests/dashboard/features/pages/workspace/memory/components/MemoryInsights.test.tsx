/**
 * @jest-environment jsdom
 */
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryInsights } from '@/features/pages/workspace/memory/components/MemoryInsights';

describe('MemoryInsights', () => {
  it('uses honest copy after curation when no signals were extracted', () => {
    render(
      <MemoryInsights
        stats={{
          totalDecisions: 0,
          totalPatterns: 0,
          totalPreferences: 0,
          dailyLogs: 4,
          lastCurated: '2026-04-23',
          recentDecisions: [],
          categoryCounts: {},
        }}
        categories={[]}
      />,
    );

    expect(screen.getByText(/did not extract durable memory signals/i)).toBeInTheDocument();
    expect(screen.queryByText(/first curation/i)).not.toBeInTheDocument();
  });
});
