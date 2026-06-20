/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockRunCliExecPrompt = jest.fn();
jest.mock('@/lib/browse/cliExecClient', () => ({
  runCliExecPrompt: (...args: unknown[]) => mockRunCliExecPrompt(...args),
}));
jest.mock('sonner', () => ({
  toast: {
    loading: jest.fn(() => 'toast-1'),
    success: jest.fn(),
    error: jest.fn(),
    info: jest.fn(),
  },
}));

describe('BrowseDetailActions', () => {
  beforeEach(() => {
    mockRunCliExecPrompt.mockReset();
    mockRunCliExecPrompt.mockResolvedValue({ answer: 'ok' });
  });

  it('renders action buttons from skill actions', async () => {
    const { BrowseDetailActions } = await import(
      '@/components/shared/BrowseDetailActions'
    );
    const actions = [
      { id: 'analyze', label: 'Analyze', dispatch: 'ide', icon: 'Search' },
      { id: 'refresh', label: 'Refresh', dispatch: 'fire', icon: 'RefreshCw' },
    ];
    render(<BrowseDetailActions actions={actions} skillId="career" />);
    expect(screen.getByText('Analyze')).toBeInTheDocument();
    expect(screen.getByText('Refresh')).toBeInTheDocument();
  });

  it('runs non-modal action prompts through raw CLI exec on click', async () => {
    const { BrowseDetailActions } = await import(
      '@/components/shared/BrowseDetailActions'
    );
    const actions = [{ id: 'run', label: 'Run', description: 'Run this action', dispatch: 'fire' }];
    render(<BrowseDetailActions actions={actions} skillId="test" />);
    fireEvent.click(screen.getByText('Run'));
    expect(mockRunCliExecPrompt).toHaveBeenCalledWith('Run this action');
  });
});
