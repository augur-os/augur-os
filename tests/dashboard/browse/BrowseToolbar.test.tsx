/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

const browseToolbarProps = (overrides: any = {}) => ({
  activeCategory: { id: 'skills', label: 'Skills' } as any,
  effectiveViewMode: 'skills' as const,
  displayMode: 'card' as const,
  onDisplayModeChange: jest.fn(),
  search: '',
  onSearchChange: jest.fn(),
  onSemanticSearch: jest.fn(),
  semanticLoading: false,
  semanticResults: [],
  semanticSearched: false,
  semanticError: null,
  tagFilter: null,
  onTagFilterChange: jest.fn(),
  tagItems: [],
  hubFilter: null,
  onHubFilterChange: jest.fn(),
  hubItems: [],
  sourceFilter: null,
  onSourceFilterChange: jest.fn(),
  kindFilter: 'all' as const,
  onKindFilterChange: jest.fn(),
  archivedFilter: null,
  onArchivedFilterChange: jest.fn(),
  archivedItems: [],
  masterFilter: null,
  onMasterFilterChange: jest.fn(),
  masterClients: [],
  pluginFilter: null,
  onPluginFilterChange: jest.fn(),
  pluginNames: [],
  typeFilter: null,
  onTypeFilterChange: jest.fn(),
  typeItems: [],
  skillTagFilter: null,
  onSkillTagFilterChange: jest.fn(),
  skillTagItems: [],
  sortBy: 'default' as const,
  onSortChange: jest.fn(),
  ...overrides,
});

describe('BrowseToolbar', () => {
  it('keeps problem filter props optional for typed callers', () => {
    // Props interface lives in the BrowseToolbar.types.ts sibling after the WS5 split.
    const source = readFileSync(
      join(process.cwd(), 'app/(views)/browse/BrowseToolbar.types.ts'),
      'utf8',
    );

    expect(source).toContain('problemFilter?: string | null;');
    expect(source).toContain('onProblemFilterChange?: (problem: string | null) => void;');
    expect(source).toContain('problemItems?: { id: string; label: string }[];');
  });

  it('renders and clears the Problems filter', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const onProblemFilterChange = jest.fn();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'agent-profiles', label: 'Agent profiles' } as any}
        effectiveViewMode="agent-profiles"
        displayMode="grid"
        onDisplayModeChange={jest.fn()}
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        problemFilter="unknown_source"
        onProblemFilterChange={onProblemFilterChange}
        problemItems={[{ id: 'unknown_source', label: 'Unknown source (2)' }]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        archivedFilter={null}
        onArchivedFilterChange={jest.fn()}
        archivedItems={[]}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="default"
        onSortChange={jest.fn()}
        filtersOpen
      />,
    );

    expect(screen.getByRole('combobox', { name: /filter by problems/i })).toBeInTheDocument();
    expect(screen.getByText(/Problems: Unknown source/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /clear all/i }));
    expect(onProblemFilterChange).toHaveBeenCalledWith(null);
  });

  it('shows Ask AI next to the search control', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');

    render(
      <BrowseToolbar
        activeCategory={{ id: 'skills', label: 'Skills' } as any}
        effectiveViewMode="skills"
        search="pitch slide"
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="default"
        onSortChange={jest.fn()}
        onDeepSearch={jest.fn()}
        deepSearchDisabled={false}
        deepSearchBusy={false}
      />,
    );

    expect(screen.getByRole('textbox', { name: /search skills/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ask ai/i })).toBeInTheDocument();
  });

  it('disables Ask AI only when the query is empty or Ask AI is busy', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const baseProps = {
      activeCategory: { id: 'skills', label: 'Skills' } as any,
      effectiveViewMode: 'skills' as const,
      onSearchChange: jest.fn(),
      onSemanticSearch: jest.fn(),
      semanticResults: [],
      semanticSearched: false,
      semanticError: null,
      tagFilter: null,
      onTagFilterChange: jest.fn(),
      tagItems: [],
      hubFilter: null,
      onHubFilterChange: jest.fn(),
      hubItems: [],
      sourceFilter: null,
      onSourceFilterChange: jest.fn(),
      kindFilter: 'all' as const,
      onKindFilterChange: jest.fn(),
      masterFilter: null,
      onMasterFilterChange: jest.fn(),
      masterClients: [],
      pluginFilter: null,
      onPluginFilterChange: jest.fn(),
      pluginNames: [],
      typeFilter: null,
      onTypeFilterChange: jest.fn(),
      typeItems: [],
      skillTagFilter: null,
      onSkillTagFilterChange: jest.fn(),
      skillTagItems: [],
      sortBy: 'default' as const,
      onSortChange: jest.fn(),
      onDeepSearch: jest.fn(),
    };

    const { rerender } = render(
      <BrowseToolbar
        {...baseProps}
        search=""
        semanticLoading={false}
        deepSearchDisabled
        deepSearchBusy={false}
      />,
    );
    expect(screen.getByRole('button', { name: /ask ai/i })).toBeDisabled();

    rerender(
      <BrowseToolbar
        {...baseProps}
        search="pitch slide"
        semanticLoading
        deepSearchDisabled={false}
        deepSearchBusy={false}
      />,
    );
    expect(screen.getByRole('button', { name: /ask ai/i })).toBeEnabled();

    rerender(
      <BrowseToolbar
        {...baseProps}
        search="pitch slide"
        semanticLoading={false}
        deepSearchDisabled={false}
        deepSearchBusy
      />,
    );
    expect(screen.getByRole('button', { name: /ask ai/i })).toBeDisabled();
  });

  it('runs Ask AI for a non-empty query while fast search is loading', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const onDeepSearch = jest.fn();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'skills', label: 'Skills' } as any}
        effectiveViewMode="skills"
        search="pitch slide"
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="default"
        onSortChange={jest.fn()}
        onDeepSearch={onDeepSearch}
        deepSearchDisabled={false}
        deepSearchBusy={false}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /ask ai/i }));

    expect(onDeepSearch).toHaveBeenCalledTimes(1);
  });

  it('runs Ask AI when the query has text', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const onDeepSearch = jest.fn();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'skills', label: 'Skills' } as any}
        effectiveViewMode="skills"
        search="pitch slide"
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="default"
        onSortChange={jest.fn()}
        onDeepSearch={onDeepSearch}
        deepSearchDisabled={false}
        deepSearchBusy={false}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /ask ai/i }));

    expect(onDeepSearch).toHaveBeenCalledTimes(1);
  });

  it('uses class-based borders for toolbar controls to avoid hydration style drift', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'skills', label: 'Skills' } as any}
        effectiveViewMode="skills"
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[
          { id: 'all', label: 'Quality: All' },
          { id: 'production', label: 'Production' },
        ]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="default"
        onSortChange={jest.fn()}
      />,
    );

    expect(screen.getByRole('textbox', { name: /search skills/i })).not.toHaveAttribute('style');
    expect(screen.queryByRole('combobox', { name: /search mode/i })).not.toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /sort order/i })).not.toHaveAttribute('style');

    await user.click(screen.getByRole('button', { name: /show filters/i }));

    expect(screen.getByRole('combobox', { name: /filter by quality/i })).not.toHaveAttribute('style');
  });

  it('runs the default unified search when Enter is pressed', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const onSemanticSearch = jest.fn();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'skills', label: 'Skills' } as any}
        effectiveViewMode="skills"
        search="pitch slide"
        onSearchChange={jest.fn()}
        onSemanticSearch={onSemanticSearch}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="default"
        onSortChange={jest.fn()}
      />,
    );

    screen.getByRole('textbox', { name: /search skills/i }).focus();
    fireEvent.keyDown(screen.getByRole('textbox', { name: /search skills/i }), { key: 'Enter' });

    expect(onSemanticSearch).toHaveBeenCalledWith('pitch slide');
  });

  it('shows Default as the first sort option', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');

    render(
      <BrowseToolbar
        activeCategory={{ id: 'skills', label: 'Skills' } as any}
        effectiveViewMode="skills"
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="default"
        onSortChange={jest.fn()}
      />,
    );

    const sort = screen.getByRole('combobox', { name: /sort order/i });
    expect(sort).toHaveValue('default');
    expect(screen.getByRole('option', { name: 'Default' })).toBeInTheDocument();
  });

  it('shows ownership filter options inside the filter panel for skills', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'skills', label: 'Skills' } as any}
        effectiveViewMode="skills"
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="name-asc"
        onSortChange={jest.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: /show filters/i }));
    const select = screen.getByRole('combobox', { name: /filter by ownership/i });
    expect(select).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Augur' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'External' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Adopted' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Local' })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Global' })).not.toBeInTheDocument();
  });

  it('keeps Notes classification filters inside the existing filter panel', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'notes', label: 'Notes' } as any}
        effectiveViewMode="notes"
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[
          { id: 'all', label: 'All' },
          { id: 'url', label: 'URL (2)' },
        ]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        noteDomainItems={[{ id: 'projects', label: 'Project (1)' }]}
        noteSourceItems={[{ id: 'github', label: 'GitHub (1)' }]}
        noteStatusItems={[{ id: 'saved', label: 'Saved (1)' }]}
        sortBy="name-asc"
        onSortChange={jest.fn()}
      />,
    );

    expect(screen.getAllByRole('button', { name: /filters/i })).toHaveLength(1);

    await user.click(screen.getByRole('button', { name: /show filters/i }));

    expect(screen.getByRole('combobox', { name: /filter by domain/i })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /filter by source/i })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /filter by status/i })).toBeInTheDocument();
  });

  it('does not count hidden Notes classification filters outside Notes', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');

    render(
      <BrowseToolbar
        activeCategory={{ id: 'skills', label: 'Skills' } as any}
        effectiveViewMode="skills"
        displayMode="grid"
        onDisplayModeChange={jest.fn()}
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        noteDomainFilter="projects"
        noteDomainItems={[{ id: 'projects', label: 'Project (1)' }]}
        noteSourceFilter="github"
        noteSourceItems={[{ id: 'github', label: 'GitHub (1)' }]}
        noteStatusFilter="saved"
        noteStatusItems={[{ id: 'saved', label: 'Saved (1)' }]}
        sortBy="name-asc"
        onSortChange={jest.fn()}
      />,
    );

    const filtersButton = screen.getByRole('button', { name: /show filters/i });
    expect(filtersButton).toHaveTextContent(/Filters\s*0/);
    expect(screen.queryByText(/Domain:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Source:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Status: Saved/i)).not.toBeInTheDocument();
  });

  it('shows supported AI client filter options for skill inventory', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'skills', label: 'Skills' } as any}
        effectiveViewMode="skills"
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={['claude', 'codex', 'gemini']}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="name-asc"
        onSortChange={jest.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: /show filters/i }));
    const select = screen.getByRole('combobox', { name: /filter by client/i });
    expect(select).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Claude' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Codex' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Gemini' })).toBeInTheDocument();
  });

  it('labels the wiki primary filter as page tags', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'wiki', label: 'Wiki' } as any}
        effectiveViewMode="wiki"
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[
          { id: 'all', label: 'All' },
          { id: 'auto-wiki-maintenance-cycle', label: 'auto-wiki-maintenance-cycle (12)' },
        ]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[
          { id: 'all', label: 'All (222)' },
          { id: 'brain', label: 'Brain (222)' },
        ]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="name-asc"
        onSortChange={jest.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: /show filters/i }));

    expect(screen.getByRole('combobox', { name: /filter by tag/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Tag: All' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'auto-wiki-maintenance-cycle (12)' })).toBeInTheDocument();
  });

  it.each([
    ['tests', 'Filter'],
    ['notes', 'Format'],
    ['commands', 'Quality'],
  ] as const)('labels the %s primary filter as %s', async (effectiveViewMode, label) => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();

    render(
      <BrowseToolbar
        activeCategory={{ id: effectiveViewMode, label } as any}
        effectiveViewMode={effectiveViewMode}
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[
          { id: 'all', label: 'All' },
          { id: 'md', label: 'MD (2)' },
        ]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="name-asc"
        onSortChange={jest.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: /show filters/i }));

    expect(screen.getByRole('combobox', { name: new RegExp(`filter by ${label}`, 'i') })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: `${label}: All` })).toBeInTheDocument();
  });

  it('shows the pages kind segmented filter on Pages', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();
    const onKindFilterChange = jest.fn();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'pages', label: 'Pages' } as any}
        effectiveViewMode="pages"
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[
          { id: 'all', label: 'All' },
          { id: 'live', label: 'live (2)' },
        ]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={onKindFilterChange}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="name-asc"
        onSortChange={jest.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: /show filters/i }));
    await user.click(screen.getByRole('button', { name: 'Saved' }));

    expect(screen.getByRole('group', { name: /filter pages by kind/i })).toBeInTheDocument();
    expect(onKindFilterChange).toHaveBeenCalledWith('saved');
  });

  it('keeps Focus and Select out of the permanent toolbar row', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');

    render(
      <BrowseToolbar
        {...browseToolbarProps({
          activeCategory: { id: 'skills', label: 'Skills' } as any,
          effectiveViewMode: 'skills',
          brainItems: [
            { id: 'all', label: 'Brain: All' },
            { id: 'personal', label: 'Personal' },
          ],
          activeBrainId: 'personal',
          focusMode: false,
          onFocusModeChange: jest.fn(),
          selectionMode: false,
          onToggleSelectionMode: jest.fn(),
        })}
      />,
    );

    expect(screen.getByRole('textbox', { name: /search skills/i })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: /display mode/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /show filters/i })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /sort order/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /focus on active brain/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /enter select mode/i })).not.toBeInTheDocument();
  });

  it('shows Notes category chips as the visible Notes filter row', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();
    const onJourneyCategoryFilterChange = jest.fn();

    render(
      <BrowseToolbar
        {...browseToolbarProps({
          activeCategory: { id: 'notes', label: 'Notes' } as any,
          effectiveViewMode: 'notes',
          journeyCategoryFilter: null,
          onJourneyCategoryFilterChange,
          journeyCategoryItems: [
            { id: 'all', label: 'All' },
            { id: 'books', label: 'Books (17)' },
            { id: 'reading-list', label: 'Reading List (4)' },
          ],
        })}
      />,
    );

    const categoryRow = screen.getByRole('group', { name: /filter notes by category/i });
    const all = within(categoryRow).getByRole('button', { name: 'All' });
    const books = within(categoryRow).getByRole('button', { name: 'Books (17)' });
    expect(all).toHaveAttribute('aria-pressed', 'true');
    expect(books).toHaveAttribute('aria-pressed', 'false');

    await user.click(books);
    expect(onJourneyCategoryFilterChange).toHaveBeenCalledWith('books');
  });

  it('keeps Notes Type inside Filters and removes the old visible Type chip row', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();

    render(
      <BrowseToolbar
        {...browseToolbarProps({
          activeCategory: { id: 'notes', label: 'Notes' } as any,
          effectiveViewMode: 'notes',
          typeItems: [
            { id: 'all', label: 'Type: All' },
            { id: 'url', label: 'URL' },
          ],
          journeyCategoryFilter: 'books',
          onJourneyCategoryFilterChange: jest.fn(),
          journeyCategoryItems: [
            { id: 'all', label: 'All' },
            { id: 'books', label: 'Books' },
          ],
        })}
      />,
    );

    expect(screen.queryByText(/^Type$/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'URL' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /show filters/i }));

    expect(screen.getByRole('group', { name: /filter by type/i })).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: /filter by category/i })).not.toBeInTheDocument();
  });

  it('keeps Notes Type as a multi-select control inside Filters', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();
    const onTypeFilterChange = jest.fn();

    render(
      <BrowseToolbar
        {...browseToolbarProps({
          activeCategory: { id: 'notes', label: 'Notes' } as any,
          effectiveViewMode: 'notes',
          typeFilter: 'url',
          onTypeFilterChange,
          typeItems: [
            { id: 'all', label: 'Type: All' },
            { id: 'url', label: 'URL (2)' },
            { id: 'file', label: 'File (1)' },
          ],
          journeyCategoryFilter: null,
          onJourneyCategoryFilterChange: jest.fn(),
          journeyCategoryItems: [
            { id: 'all', label: 'All' },
            { id: 'books', label: 'Books' },
          ],
        })}
      />,
    );

    await user.click(screen.getByRole('button', { name: /show filters/i }));

    const typeGroup = screen.getByRole('group', { name: /filter by type/i });
    expect(within(typeGroup).getByRole('button', { name: 'URL (2)' })).toHaveAttribute('aria-pressed', 'true');
    expect(within(typeGroup).getByRole('button', { name: 'File (1)' })).toHaveAttribute('aria-pressed', 'false');

    await user.click(within(typeGroup).getByRole('button', { name: 'File (1)' }));
    expect(onTypeFilterChange).toHaveBeenCalledWith('url,file');

    await user.click(within(typeGroup).getByRole('button', { name: 'URL (2)' }));
    expect(onTypeFilterChange).toHaveBeenCalledWith(null);
  });

  it('clears visible Notes category and advanced Notes type together', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();
    const onTypeFilterChange = jest.fn();
    const onJourneyCategoryFilterChange = jest.fn();

    render(
      <BrowseToolbar
        {...browseToolbarProps({
          activeCategory: { id: 'notes', label: 'Notes' } as any,
          effectiveViewMode: 'notes',
          typeFilter: 'url',
          onTypeFilterChange,
          typeItems: [
            { id: 'all', label: 'Type: All' },
            { id: 'url', label: 'URL' },
          ],
          journeyCategoryFilter: 'books',
          onJourneyCategoryFilterChange,
          journeyCategoryItems: [
            { id: 'all', label: 'All' },
            { id: 'books', label: 'Books' },
          ],
        })}
      />,
    );

    expect(screen.getByRole('button', { name: /Category: Books/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Type: URL/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /clear all/i }));

    expect(onTypeFilterChange).toHaveBeenCalledWith(null);
    expect(onJourneyCategoryFilterChange).toHaveBeenCalledWith(null);
  });

  it('keeps expanded filter controls in a compact wrapping row', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const user = userEvent.setup();

    render(
      <BrowseToolbar
        activeCategory={{ id: 'skills', label: 'Skills' } as any}
        effectiveViewMode="skills"
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[
          { id: 'all', label: 'Quality: All' },
          { id: 'production', label: 'Production' },
        ]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[
          { id: 'all', label: 'Hub: All' },
          { id: 'brain', label: 'Brain' },
        ]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        kindFilter="all"
        onKindFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={['claude', 'codex', 'gemini']}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={['augur-local']}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[
          { id: 'all', label: 'Type: All' },
          { id: 'agent-skill', label: 'Agent Skill' },
        ]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[
          { id: 'all', label: 'Tag: All' },
          { id: 'knowledge', label: 'Knowledge' },
        ]}
        sortBy="name-asc"
        onSortChange={jest.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: /show filters/i }));

    const controls = screen.getByTestId('browse-filter-controls');
    expect(controls).toHaveClass('flex', 'flex-wrap', 'items-start', 'gap-2');
    expect(controls).not.toHaveClass('grid');
  });

  it('renders an Inbox chip row in notes view when inbox items exist', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');
    const onNoteStateFilterChange = jest.fn();

    render(
      <BrowseToolbar
        {...browseToolbarProps({
          activeCategory: { id: 'notes', label: 'Notes' } as any,
          effectiveViewMode: 'notes',
          noteStateFilter: null,
          onNoteStateFilterChange,
          noteStateItems: [
            { id: 'all', label: 'All' },
            { id: 'inbox', label: 'Inbox (3)' },
          ],
          journeyCategoryFilter: null,
          onJourneyCategoryFilterChange: jest.fn(),
          journeyCategoryItems: [],
        })}
      />,
    );

    const stateRow = screen.getByRole('group', { name: /filter notes by state/i });
    const all = within(stateRow).getByRole('button', { name: 'All' });
    const inbox = within(stateRow).getByRole('button', { name: 'Inbox (3)' });

    expect(all).toHaveAttribute('aria-pressed', 'true');
    expect(inbox).toHaveAttribute('aria-pressed', 'false');

    const user = userEvent.setup();
    await user.click(inbox);
    expect(onNoteStateFilterChange).toHaveBeenCalledWith('inbox');
  });

  it('renders no inbox chip row in notes view when noteStateItems is empty or not provided', async () => {
    const { BrowseToolbar } = await import('@/app/(views)/browse/BrowseToolbar');

    render(
      <BrowseToolbar
        {...browseToolbarProps({
          activeCategory: { id: 'notes', label: 'Notes' } as any,
          effectiveViewMode: 'notes',
          journeyCategoryFilter: null,
          onJourneyCategoryFilterChange: jest.fn(),
          journeyCategoryItems: [],
        })}
      />,
    );

    expect(screen.queryByRole('group', { name: /filter notes by state/i })).not.toBeInTheDocument();
  });
});
