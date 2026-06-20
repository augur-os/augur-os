import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ActionButtons from '@/scripts/skill-scripts/blocks/ActionButtons';
import { renderWithQuery } from '../../helpers/component-test-utils';
import { useChatStore } from '@/lib/stores/chatStore';
import { toast } from 'sonner';

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

jest.mock('@/lib/mcp/useMcpQuery', () => ({
  useMcpQuery: () => ({ data: undefined, loading: false, error: null }),
}));

jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    info: jest.fn(),
  },
}));

const mockFetch = jest.fn();
global.fetch = mockFetch as unknown as typeof fetch;

describe('page-builder ActionButtons', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });
    useChatStore.setState({
      isOpen: false,
      mode: 'ide',
      context: {},
      agent: 'default',
      initialPrompt: '',
      isWaiting: false,
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      isEnlarged: false,
      chatView: 'terminal',
      embeddedAction: null,
      preparedActionDraft: null,
      terminalFocused: false,
      terminalFallbackActive: false,
      sessionId: null,
      oneshotResult: null,
      focusPayload: null,
      focusInjectedForPath: null,
    });

    (toast.success as jest.Mock).mockClear();
    (toast.error as jest.Mock).mockClear();
    (toast.info as jest.Mock).mockClear();
  });

  it('opens a prepared action draft for oneshot dispatch', async () => {
    renderWithQuery(
      <ActionButtons
        actions={[
          {
            id: 'quick-analysis',
            label: 'Quick Analysis',
            dispatch: 'oneshot',
            prompt: 'Analyze this',
          },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /quick analysis/i }));

    await waitFor(() => {
      const state = useChatStore.getState();
      expect(state.preparedActionDraft?.id).toBe('quick-analysis');
      expect(state.preparedActionDraft?.dispatch).toBe('oneshot');
      expect(state.preparedActionDraft?.prompt).toContain('Analyze this');
      expect(state.chatView).toBe('terminal');
      expect(state.embeddedAction).toBeNull();
      expect(state.oneshotResult).toBeNull();
    });
  });

  it('opens a prepared action draft for chat dispatch', async () => {
    renderWithQuery(
      <ActionButtons
        actions={[
          {
            id: 'chat-action',
            label: 'Chat Action',
            dispatch: 'chat',
            prompt: 'Discuss next steps',
          },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /chat action/i }));

    await waitFor(() => {
      const state = useChatStore.getState();
      expect(state.isOpen).toBe(true);
      expect(state.preparedActionDraft?.id).toBe('chat-action');
      expect(state.preparedActionDraft?.dispatch).toBe('chat');
      expect(state.preparedActionDraft?.prompt).toContain('Discuss next steps');
      expect(state.chatView).toBe('terminal');
      expect(state.initialPrompt).toBe('');
    });
  });

  it('opens a prepared action draft for ide dispatch', async () => {
    renderWithQuery(
      <ActionButtons
        actions={[
          {
            id: 'ide-action',
            label: 'IDE Action',
            dispatch: 'ide',
            prompt: 'Implement feature X',
          },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /ide action/i }));

    await waitFor(() => {
      const state = useChatStore.getState();
      expect(state.isOpen).toBe(true);
      expect(state.preparedActionDraft?.id).toBe('ide-action');
      expect(state.preparedActionDraft?.dispatch).toBe('ide');
      expect(state.preparedActionDraft?.prompt).toContain('Implement feature X');
      expect(state.chatView).toBe('terminal');
      expect(state.embeddedAction).toBeNull();
    });
  });

  it('errors a fire dispatch that declares no mcp_tool (ADR-807)', async () => {
    renderWithQuery(
      <ActionButtons
        actions={[
          {
            id: 'run-action',
            label: 'Run Action',
            dispatch: 'fire',
          },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /run action/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('fire action requires an mcp_tool');
    });
    // No MCP call: the retired execute-fast-action fallback is gone.
    expect(mockFetch).not.toHaveBeenCalledWith(
      '/api/mcp/tool',
      expect.anything(),
    );
    expect(toast.success).not.toHaveBeenCalled();
  });

  it('runs fire dispatch with declared MCP tool directly', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, message: 'tool done' }),
    });

    renderWithQuery(
      <ActionButtons
        actions={[
          {
            id: 'tool-action',
            label: 'Tool Action',
            dispatch: 'fire',
            args: { category: 'skills' },
            mcp_tools: ['reindex-browse-category'],
          },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /tool action/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/mcp/tool',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            tool: 'reindex-browse-category',
            args: {
              category: 'skills',
              context: {
                page: '/',
                hub: 'dashboard',
                tier: 'standard',
              },
            },
          }),
        })
      );
    });
    expect(toast.success).toHaveBeenCalledWith('tool done');
  });
});
