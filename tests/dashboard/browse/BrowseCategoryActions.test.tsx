/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowseCategoryActions, ApiRoutesStats } from '@/components/shared/BrowseCategoryActions';
import type { BrowseCategory } from '@/lib/browse/types';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';

const mockRunCliExecPrompt = jest.fn();
const mockPush = jest.fn();

jest.mock('@/lib/browse/cliExecClient', () => ({
  runCliExecPrompt: (...args: unknown[]) => mockRunCliExecPrompt(...args),
}));
jest.mock('@/features/browse/AddSkillModal', () => ({
  AddSkillModal: ({ open }: { open: boolean }) => (open ? <div>Add Skill Modal</div> : null),
}));
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));
jest.mock('sonner', () => ({
  toast: {
    loading: jest.fn(() => 'toast-1'),
    success: jest.fn(),
    error: jest.fn(),
  },
}));
jest.mock('@/lib/mcp/useMcpQuery', () => ({
  useMcpQuery: jest.fn(() => ({
    data: { stats: { total: 42, byStatus: { migrated: 30, legacy: 12 } } },
    isLoading: false,
    error: null,
  })),
}));
jest.mock('@/lib/mcp/client', () => ({
  mcpCall: jest.fn().mockResolvedValue({}),
}));

const CATEGORIES: Record<string, BrowseCategory> = {
  integrations: { id: 'integrations', label: 'Integrations', singularLabel: 'Integration', icon: 'Plug', devOnly: false, group: 'system', journey_group: 'loop', journey_order: 1 },
  skills: { id: 'skills', label: 'Skills', singularLabel: 'Skill', icon: 'Puzzle', devOnly: false, group: 'content', journey_group: 'prompt', journey_order: 1 },
  wiki: { id: 'wiki', label: 'Wiki', singularLabel: 'Wiki Page', icon: 'NotebookTabs', devOnly: true, group: 'content', journey_group: 'context', journey_order: 2 },
  documents: { id: 'documents', label: 'Documents', singularLabel: 'Document', icon: 'FolderOpen', devOnly: false, group: 'content', journey_group: 'context', journey_order: 2 },
  'api-routes': { id: 'api-routes', label: 'API Routes', singularLabel: 'Route', icon: 'Route', devOnly: true, group: 'dev', journey_group: 'capabilities', journey_order: 4, defaultDisplayMode: 'list' },
  notes: { id: 'notes', label: 'Notes', singularLabel: 'Note', icon: 'BookOpen', devOnly: false, group: 'content', journey_group: 'context', journey_order: 1 },
  pages: { id: 'pages', label: 'Pages', singularLabel: 'Page', icon: 'PanelsTopLeft', devOnly: false, group: 'content', journey_group: 'context', journey_order: 3 },
};

describe('BrowseCategoryActions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRunCliExecPrompt.mockResolvedValue({ answer: 'ok' });
  });

  it('renders an actions trigger for integrations category', () => {
    render(<BrowseCategoryActions category="integrations" activeCategory={CATEGORIES.integrations} itemCount={5} onRefetch={jest.fn()} />);
    expect(screen.getByRole('button', { name: 'Manage' })).toBeInTheDocument();
  });

  it('shows the default generic actions for an integrations category', () => {
    render(<BrowseCategoryActions category="integrations" activeCategory={CATEGORIES.integrations} itemCount={5} onRefetch={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));

    expect(screen.getByRole('menuitem', { name: 'New Integration' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Add skill' })).not.toBeInTheDocument();
  });

  it('shows only global skill actions for the skills category', () => {
    render(<BrowseCategoryActions category="skills" activeCategory={CATEGORIES.skills} itemCount={12} onRefetch={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));

    const expectedLabels = [
      'Add skill',
      'Discover client skills',
      'Sync managed skills to clients',
      'Review external skills',
      'Reindex skills',
      'Open skills settings',
    ];

    const menuItems = screen.getAllByRole('menuitem');
    expect(menuItems).toHaveLength(expectedLabels.length);
    expectedLabels.forEach((label) => {
      expect(screen.getByRole('menuitem', { name: label })).toBeInTheDocument();
    });
    expect(screen.queryByRole('menuitem', { name: 'New Skill' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Improve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Adopt' })).not.toBeInTheDocument();
  });

  it('opens AddSkillModal and does not dispatch a CLI prompt for Add skill', () => {
    render(<BrowseCategoryActions category="skills" activeCategory={CATEGORIES.skills} itemCount={12} onRefetch={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Add skill' }));
    expect(screen.getByText('Add Skill Modal')).toBeInTheDocument();
    expect(mockRunCliExecPrompt).not.toHaveBeenCalled();
  });

  it('runs discover/sync/review skill actions through raw CLI exec prompts', () => {
    render(<BrowseCategoryActions category="skills" activeCategory={CATEGORIES.skills} itemCount={12} onRefetch={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));

    fireEvent.click(screen.getByRole('menuitem', { name: 'Discover client skills' }));
    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Sync managed skills to clients' }));
    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Review external skills' }));

    expect(mockRunCliExecPrompt).toHaveBeenCalledTimes(3);
    expect(mockRunCliExecPrompt).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('Discover all skills installed'),
    );
    expect(mockRunCliExecPrompt).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('Synchronize all managed'),
    );
    expect(mockRunCliExecPrompt).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining('Review all external'),
    );
  });

  it('navigates to skills settings in-app', () => {
    render(<BrowseCategoryActions category="skills" activeCategory={CATEGORIES.skills} itemCount={12} onRefetch={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Open skills settings' }));
    expect(mockPush).toHaveBeenCalledWith('/settings/skills');
    expect(mockRunCliExecPrompt).not.toHaveBeenCalled();
  });

  it('calls onReindex for skills and disables when callback missing or reindexing', () => {
    const onReindex = jest.fn();
    const { rerender } = render(
      <BrowseCategoryActions
        category="skills"
        activeCategory={CATEGORIES.skills}
        itemCount={12}
        onRefetch={jest.fn()}
        onReindex={onReindex}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    const reindexMenuItem = screen.getByRole('menuitem', { name: 'Reindex skills' });
    expect(reindexMenuItem).toBeInTheDocument();
    expect(reindexMenuItem).not.toBeDisabled();

    fireEvent.click(reindexMenuItem);
    expect(onReindex).toHaveBeenCalledTimes(1);

    rerender(
      <BrowseCategoryActions
        category="skills"
        activeCategory={CATEGORIES.skills}
        itemCount={12}
        onRefetch={jest.fn()}
        onReindex={onReindex}
        reindexing
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    expect(screen.getByRole('menuitem', { name: 'Reindexing...' })).toBeDisabled();
    expect(onReindex).toHaveBeenCalledTimes(1);
  });

  it('shows reindex menu item disabled when onReindex is missing for skills', () => {
    render(<BrowseCategoryActions category="skills" activeCategory={CATEGORIES.skills} itemCount={12} onRefetch={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    expect(screen.getByRole('menuitem', { name: 'Reindex skills' })).toBeDisabled();
  });

  it('runs the wiki bootstrap-or-repair action through raw CLI exec', () => {
    render(<BrowseCategoryActions category="wiki" activeCategory={CATEGORIES.wiki} itemCount={0} onRefetch={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    expect(screen.getByRole('menuitem', { name: 'New Wiki' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'New Wiki Page' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('menuitem', { name: 'New Wiki' }));
    expect(mockRunCliExecPrompt).toHaveBeenCalledWith(
      expect.stringContaining('repair and harden'),
    );
  });

  it('renders optional page-level actions for non-skill categories', () => {
    const onAddContent = jest.fn();
    const onReindex = jest.fn();
    render(
      <BrowseCategoryActions
        category="notes"
        activeCategory={CATEGORIES.notes}
        itemCount={10}
        onRefetch={jest.fn()}
        onAddContent={onAddContent}
        onReindex={onReindex}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Add Note' }));
    expect(onAddContent).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Reindex' }));
    expect(onReindex).toHaveBeenCalled();
  });

  it('keeps the project question inside Manage for non-skill categories', () => {
    const onSelect = jest.fn();
    render(
      <BrowseCategoryActions
        category="documents"
        activeCategory={CATEGORIES.documents}
        itemCount={7}
        onRefetch={jest.fn()}
        projectQuestionAction={{
          label: 'Ask Augur about this project',
          onSelect,
        }}
      />,
    );

    expect(screen.queryByRole('button', { name: 'Ask Augur about this project' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Ask Augur about this project' }));

    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it('shows the project question inside Manage for skills when provided', () => {
    const onSelect = jest.fn();
    render(
      <BrowseCategoryActions
        category="skills"
        activeCategory={CATEGORIES.skills}
        itemCount={7}
        onRefetch={jest.fn()}
        projectQuestionAction={{
          label: 'Ask Augur about this project',
          onSelect,
        }}
      />,
    );

    expect(screen.queryByRole('button', { name: 'Ask Augur about this project' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Ask Augur about this project' }));

    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it.each(['notes', 'documents', 'pages'] as const)(
    'shows Sweep visible for %s when a sweep callback exists',
    (category) => {
      const onSweepVisible = jest.fn();
      render(
        <BrowseCategoryActions
          category={category}
          activeCategory={CATEGORIES[category]}
          itemCount={10}
          onRefetch={jest.fn()}
          onAddContent={jest.fn()}
          onSweepVisible={onSweepVisible}
          onReindex={jest.fn()}
        />,
      );

      fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
      fireEvent.click(screen.getByRole('menuitem', { name: 'Sweep visible' }));

      expect(onSweepVisible).toHaveBeenCalledTimes(1);
    },
  );

  it('does not show Sweep visible for unsupported categories', () => {
    render(
      <BrowseCategoryActions
        category="wiki"
        activeCategory={CATEGORIES.wiki}
        itemCount={10}
        onRefetch={jest.fn()}
        onSweepVisible={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));

    expect(screen.queryByRole('menuitem', { name: 'Sweep visible' })).not.toBeInTheDocument();
  });

  it('disables Sweep visible and shows progress text while sweeping', () => {
    const onSweepVisible = jest.fn();
    render(
      <BrowseCategoryActions
        category="notes"
        activeCategory={CATEGORIES.notes}
        itemCount={10}
        onRefetch={jest.fn()}
        onAddContent={jest.fn()}
        onSweepVisible={onSweepVisible}
        sweeping
        onReindex={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    const sweepItem = screen.getByRole('menuitem', { name: 'Sweeping...' });

    expect(sweepItem).toBeDisabled();
    fireEvent.click(sweepItem);
    expect(onSweepVisible).not.toHaveBeenCalled();
  });

  it('disables Sweep visible when there are no filtered items', () => {
    const onSweepVisible = jest.fn();
    render(
      <BrowseCategoryActions
        category="notes"
        activeCategory={CATEGORIES.notes}
        itemCount={0}
        onRefetch={jest.fn()}
        onAddContent={jest.fn()}
        onSweepVisible={onSweepVisible}
        onReindex={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Manage' }));
    const sweepItem = screen.getByRole('menuitem', { name: 'Sweep visible' });

    expect(sweepItem).toBeDisabled();
    fireEvent.click(sweepItem);
    expect(onSweepVisible).not.toHaveBeenCalled();
  });
});

describe('ApiRoutesStats', () => {
  it('renders stats summary and Architecture Audit button', () => {
    render(<ApiRoutesStats itemCount={42} />);
    expect(screen.getByText(/42/)).toBeInTheDocument();
    expect(screen.getByText(/migrated/i)).toBeInTheDocument();
    expect(screen.getByText('Architecture Audit')).toBeInTheDocument();
    expect(useMcpQuery).toHaveBeenCalledWith(
      'browse-api-routes-stats',
      'get-api-route-stats',
      'config',
      expect.objectContaining({
        fallback: expect.any(Object),
      }),
    );
  });

  it('runs architecture audit through raw CLI exec', async () => {
    render(<ApiRoutesStats itemCount={42} />);
    fireEvent.click(screen.getByRole('button', { name: 'Architecture Audit' }));

    await waitFor(() => {
      expect(mockRunCliExecPrompt).toHaveBeenCalledWith(
        expect.stringContaining('Audit all API routes'),
      );
    });
  });
});
