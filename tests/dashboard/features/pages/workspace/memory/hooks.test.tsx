/**
 * @jest-environment jsdom
 */
import { act, renderHook, waitFor } from '@testing-library/react';

const mockMcpCall = jest.fn();
const mockUseMcpQuery = jest.fn();

jest.mock('@/features/hooks/usePageActionsData', () => ({
  usePageActionsData: () => ({ buttons: [] }),
}));

jest.mock('@/lib/mcp/useMcpQuery', () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

jest.mock('@/lib/mcp/client', () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

describe('brain memory hooks', () => {
  beforeEach(() => {
    mockMcpCall.mockReset();
    mockUseMcpQuery.mockReset();
  });

  it('surfaces explicit MCP search failures as hook errors', async () => {
    mockMcpCall.mockResolvedValueOnce({
      success: false,
      error: 'Search backend is offline',
    });

    const { useMemorySearch } = await import('@/features/pages/workspace/memory/hooks');
    const { result } = renderHook(() => useMemorySearch());

    await act(async () => {
      await result.current.handleSearch('workflow');
    });

    expect(result.current.searchResults).toEqual([]);
    expect(result.current.searchError).toBe('Search memory failed: Search backend is offline');
    expect(result.current.hasSearched).toBe(true);
  });

  it('stores successful search results', async () => {
    mockMcpCall.mockResolvedValueOnce({
      results: [
        {
          content: 'We decided to keep the dashboard flat.',
          source: 'memory',
          category: 'architecture',
          date: '2026-04-22',
          relevance: 0.91,
        },
      ],
    });

    const { useMemorySearch } = await import('@/features/pages/workspace/memory/hooks');
    const { result } = renderHook(() => useMemorySearch());

    await act(async () => {
      await result.current.handleSearch('dashboard layout');
    });

    await waitFor(() => {
      expect(result.current.searchResults).toHaveLength(1);
      expect(result.current.searchResults[0]?.content).toContain('dashboard flat');
      expect(result.current.searchError).toBeNull();
      expect(result.current.hasSearched).toBe(true);
    });
  });

  it('keeps category counts returned by the memory bootstrap instead of zeroing them from theme counts', async () => {
    mockMcpCall.mockResolvedValueOnce({
      stats: {
        totalDecisions: 3,
        totalPatterns: 0,
        totalPreferences: 0,
        dailyLogs: 4,
        lastCurated: '2026-04-25T00:02:54.437Z',
        recentDecisions: [],
        categoryCounts: {
          career: 2,
          general: 1,
        },
      },
      categories: [
        {
          id: 'decision',
          name: 'Decisions',
          icon: 'CheckCircle',
          color: 'text-emerald-400',
          bundle: 'knowledge',
          count: 3,
        },
      ],
      workspace: { rootPath: '/tmp/memory', files: [] },
      report: { exists: true, path: '/tmp/vault/wiki/profile-human-api.md' },
      sources: {},
    });

    const { useMemoryDashboardData } = await import('@/features/pages/workspace/memory/hooks');
    const { result } = renderHook(() => useMemoryDashboardData());

    await waitFor(() => {
      expect(result.current.categories[0]?.id).toBe('decision');
      expect(result.current.categories[0]?.count).toBe(3);
    });
  });

  it('passes suggestion filters through to the memory search tool', async () => {
    mockMcpCall.mockResolvedValueOnce({
      results: [],
    });

    const { useMemorySearch } = await import('@/features/pages/workspace/memory/hooks');
    const { result } = renderHook(() => useMemorySearch());

    await act(async () => {
      await result.current.handleSearch('Augur Guriqo GTM positioning', {
        category: 'decision',
        source: 'curated',
        dateFrom: '2026-03-24',
        dateTo: '2026-04-23',
      });
    });

    expect(mockMcpCall).toHaveBeenCalledWith('memory-search', {
      query: 'Augur Guriqo GTM positioning',
      mode: 'hybrid',
      top_k: 10,
      category: 'decision',
      source: 'curated',
      date_from: '2026-03-24',
      date_to: '2026-04-23',
    });
  });

  it('preserves object-shaped daily log source metadata', async () => {
    mockUseMcpQuery.mockImplementation((key: unknown, tool: string) => {
      if (tool === 'knowledge-memory-daily-logs') {
        return {
          data: {
            logs: [
              { date: '2026-04-22', hasLog: true, entryCount: 3 },
            ],
            source: { label: 'Git commit history', exists: true, kind: 'git-log' },
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }

      if (tool === 'knowledge-memory-daily-logs-read') {
        return {
          data: {
            content: 'Daily log content',
            source: { label: 'Git commit history', exists: true, kind: 'git-log' },
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }

      return {
        data: null,
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useDailyLogs } = await import('@/features/pages/workspace/memory/hooks');
    const { result } = renderHook(() => useDailyLogs());

    await waitFor(() => {
      expect(result.current.dailyLogs).toHaveLength(1);
      expect(result.current.source).toMatchObject({
        exists: true,
        label: 'Git commit history',
        kind: 'git-log',
      });
    });

    act(() => {
      result.current.fetchLogContent('2026-04-22');
    });

    await waitFor(() => {
      expect(result.current.source?.label).toBe('Git commit history');
      expect(result.current.logContent).toBe('Daily log content');
    });
  });
});
