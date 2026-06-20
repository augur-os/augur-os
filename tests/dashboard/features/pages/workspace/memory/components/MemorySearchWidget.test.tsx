/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import type { ReactNode } from 'react';
import { MemorySearchWidget } from '@/features/pages/workspace/memory/components/MemorySearchWidget';

jest.mock('@/features/components/DashboardWidget', () => ({
  __esModule: true,
  default: ({ children, title }: { children: ReactNode; title: string }) => (
    <section aria-label={title}>{children}</section>
  ),
}));

describe('MemorySearchWidget', () => {
  it('shows source and freshness chips near the description', () => {
    render(
      <MemorySearchWidget
        searchQuery=""
        setSearchQuery={jest.fn()}
        isSearching={false}
        searchResults={[]}
        hasSearched={false}
        searchError={null}
        onSearch={jest.fn()}
        categories={[]}
        sourceLabel="Primary memory source"
        freshnessLabel="Updated 2h ago"
      />,
    );

    expect(screen.getByText('Primary memory source')).toBeInTheDocument();
    expect(screen.getByText('Updated 2h ago')).toBeInTheDocument();
  });

  it('suggests curating memory when no results are found', () => {
    render(
      <MemorySearchWidget
        searchQuery="stale topic"
        setSearchQuery={jest.fn()}
        isSearching={false}
        searchResults={[]}
        hasSearched
        searchError={null}
        onSearch={jest.fn()}
        categories={[]}
      />,
    );

    expect(screen.getByText(/Curate memory if the source looks stale\./)).toBeInTheDocument();
  });

  it('renders results without category metadata', () => {
    expect(() =>
      render(
        <MemorySearchWidget
          searchQuery="workflow"
          setSearchQuery={jest.fn()}
          isSearching={false}
          searchResults={[
            {
              source: 'daily',
              content: 'Workflow review captured in a daily log.',
              relevance: 0.9,
            } as any,
          ]}
          hasSearched
          searchError={null}
          onSearch={jest.fn()}
          categories={[]}
        />,
      ),
    ).not.toThrow();

    expect(screen.getByText('Workflow review captured in a daily log.')).toBeInTheDocument();
  });

  it('renders memory-specific suggestions and lets users open a result source', () => {
    const onOpenResult = jest.fn();

    render(
      <MemorySearchWidget
        searchQuery="workflow"
        setSearchQuery={jest.fn()}
        isSearching={false}
        searchResults={[
          {
            source: 'daily',
            content: 'Workflow review captured in a daily log.',
            relevance: 0.9,
            file_path: '/tmp/2026-04-21.md',
            line_number: 8,
          } as any,
        ]}
        hasSearched
        searchError={null}
        onSearch={jest.fn()}
        onOpenResult={onOpenResult}
        suggestedQueries={['workflow decisions', 'wiki compounding']}
        categories={[]}
      />,
    );

    expect(screen.getByRole('button', { name: /workflow decisions/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /open source/i })).toBeInTheDocument();

    screen.getByRole('button', { name: /open source/i }).click();

    expect(onOpenResult).toHaveBeenCalledWith(
      expect.objectContaining({
        file_path: '/tmp/2026-04-21.md',
        line_number: 8,
      }),
    );
  });

  it('passes structured suggestion filters through to search actions', () => {
    const onSearch = jest.fn();

    render(
      <MemorySearchWidget
        searchQuery=""
        setSearchQuery={jest.fn()}
        isSearching={false}
        searchResults={[]}
        hasSearched={false}
        searchError={null}
        onSearch={onSearch}
        categories={[]}
        suggestedQueries={[
          {
            label: 'last month decisions',
            query: 'career decisions',
            category: 'decision',
            source: 'curated',
            dateFrom: '2026-03-24',
            dateTo: '2026-04-23',
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /last month decisions/i }));

    expect(onSearch).toHaveBeenCalledWith('career decisions', {
      category: 'decision',
      source: 'curated',
      dateFrom: '2026-03-24',
      dateTo: '2026-04-23',
    });
  });

  it('keeps the search field before suggestion chips for mobile scanning', () => {
    render(
      <MemorySearchWidget
        searchQuery=""
        setSearchQuery={jest.fn()}
        isSearching={false}
        searchResults={[]}
        hasSearched={false}
        searchError={null}
        onSearch={jest.fn()}
        categories={[]}
        suggestedQueries={['workflow decisions']}
      />,
    );

    const input = screen.getByLabelText('Search memory');
    const suggestion = screen.getByRole('button', { name: /workflow decisions/i });

    expect(input.compareDocumentPosition(suggestion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
