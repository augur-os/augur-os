/**
 * @jest-environment jsdom
 */
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { RecentDecisions } from '@/features/pages/workspace/memory/components/RecentDecisions';

describe('RecentDecisions', () => {
  it('does not claim decisions are missing because curation never ran when memory was already curated', () => {
    render(
      <RecentDecisions
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

    expect(screen.getByText(/last curation/i)).toBeInTheDocument();
    expect(screen.queryByText(/click "Curate Memory" to extract insights/i)).not.toBeInTheDocument();
  });
});
