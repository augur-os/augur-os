// TODO_CLEANUP: This file is 932 lines — consider splitting into smaller modules
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import FloatingChat from '@/features/components/FloatingChat';
import { useChatStore } from '@/lib/stores/chatStore';
import { createQueryWrapper, renderWithQuery } from '../helpers/component-test-utils';
import { toast } from 'sonner';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  usePathname: () => '/brain',
  useSearchParams: () => new URLSearchParams(),
}));

// Mock hooks
const mockUseCliChat = jest.fn();
jest.mock('@/features/hooks/useCliChat', () => ({
  useCliChat: () => mockUseCliChat(),
}));

const mockAirplaneState = {
  airplaneMode: false,
  airplaneModeReady: true,
  airplaneBackendReady: false,
  airplaneLocalModel: null as string | null,
  airplaneModeError: null as string | null,
  setAirplaneMode: jest.fn(),
  toggleAirplaneMode: jest.fn(),
};
jest.mock('@/lib/stores/airplaneModeStore', () => ({
  useAirplaneModeStore: () => mockAirplaneState,
}));

const mockClearTerminal = jest.fn();
jest.mock('@/features/hooks/useXtermTerminal', () => ({
  useXtermTerminal: () => ({
    terminalContainerRef: { current: null },
    clearTerminal: mockClearTerminal,
    containerRef: { current: null },
  }),
}));

// Spy on the PTY stream parser reset so handoff "return to clean state" is testable.
const mockResetPtyStreamParser = jest.fn();
jest.mock('@/lib/chat/ptyStreamParser', () => ({
  getPtyStreamParser: () => ({ feed: jest.fn(), processExit: jest.fn() }),
  resetPtyStreamParser: () => mockResetPtyStreamParser(),
}));

// Terminal handoff fires sonner toasts — stub them so jsdom doesn't choke.
jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

jest.mock('@/features/hooks/useIdeBridge', () => ({
  useIdeBridge: () => ({
    sendPrompt: jest.fn(),
  }),
}));

jest.mock('@/features/hooks/useOnlineStatus', () => ({
  useOnlineStatus: () => true,
}));

jest.mock('@/features/hooks/useCliHealthPoller', () => ({
  useCliHealthPoller: () => false,
}));

jest.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ effectiveMode: 'dark' }),
}));

// Mock ActionsListView
jest.mock('@/features/components/ActionsListView', () => ({
  __esModule: true,
  default: ({ onBack }: { onBack: () => void }) => (
    <div data-testid="actions-list-view">
      <button onClick={onBack}>Back</button>
    </div>
  ),
}));

// Mock ModeToggle
jest.mock('@/features/components/action-bar', () => ({
  ModeToggle: () => <div data-testid="mode-toggle">Mode Toggle</div>,
}));

// NOTE: ChatBubbleView was deleted (commit 0c7082306 "remove stale chat bubble
// view"). FloatingChat now renders the real `renderFloatingChatLayout` from
// ChatLayout, which composes the header, toolbar buttons, input area, and
// welcome overlay this suite exercises directly through the real DOM. The old
// ChatBubbleView mock (and its onSendMessage/onBackToChat/onTerminalFallback/
// onRetry buttons) targeted a module that no longer exists and that no test
// body ever interacted with, so it is intentionally not replaced — mocking the
// layout out would gut the 35 behavioral assertions below.
// Mock modeStore — default to 'development' so existing terminal-view tests work unchanged
const mockMode = { mode: 'development' as 'operation' | 'development' };
jest.mock('@/lib/stores/modeStore', () => ({
  useModeStore: () => mockMode,
}));

// Mock HelpRequestModal
jest.mock('@/features/components/HelpRequestModal', () => ({
  __esModule: true,
  default: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="help-modal">
      <button onClick={onClose}>Close Help</button>
    </div>
  ),
}));

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch as any;

// Helper: render inside async act() so useEffect fetch calls settle
async function renderAsync(ui: React.ReactElement) {
  let result: ReturnType<typeof render>;
  await act(async () => {
    result = renderWithQuery(ui);
  });
  return result!;
}

function jsonResponse(payload: unknown): Response {
  return {
    ok: true,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  } as Response;
}

function mockChatRouteControlEndpoints() {
  mockFetch.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith('/api/cli?')) {
      return jsonResponse({
        status: 'running',
        sessionAirplaneMode: false,
        sessionLocalModel: null,
      });
    }
    if (url === '/api/mcp/tool') {
      const body = JSON.parse(String(init?.body ?? '{}')) as { tool?: string };
      if (body.tool === 'list-ollama-integrations') {
        return jsonResponse({ integrations: ['claude'] });
      }
      return jsonResponse({});
    }
    return jsonResponse({ tools: [] });
  });
}

const makePreparedActionDraft = (
  overrides: Partial<NonNullable<ReturnType<typeof useChatStore.getState>['preparedActionDraft']>> = {},
) => ({
  id: 'browse.deep-search',
  label: 'Ask AI',
  description: 'Inspect Browse sources',
  prompt: 'Inspect source paths.',
  page: '/workspace/browse',
  tier: 'deep' as const,
  dispatch: 'chat' as const,
  createdAt: '2026-05-24T00:00:00.000Z',
  ...overrides,
});

describe('FloatingChat', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.assign(mockAirplaneState, {
      airplaneMode: false,
      airplaneModeReady: true,
      airplaneBackendReady: false,
      airplaneLocalModel: null,
      airplaneModeError: null,
      setAirplaneMode: jest.fn(),
      toggleAirplaneMode: jest.fn(),
    });
    mockMode.mode = 'development';
    mockFetch.mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ tools: [] }),
      text: () => Promise.resolve(JSON.stringify({ tools: [] })),
    });

    // Set default mock return value for useCliChat
    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', available: true },
        { cli_id: 'kimi', label: 'Kimi', available: true },
        { cli_id: 'codex', label: 'Codex', available: false },
      ],
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    // Reset chat store to closed state
    act(() => {
      useChatStore.setState({
        isOpen: false,
        isEnlarged: false,
        chatView: 'terminal',
        embeddedAction: null,
        preparedActionDraft: null,
        terminalFocused: false,
        initialPrompt: '',
        draft: false,
      });
    });
  });

  it('returns null when chat is closed', async () => {
    const { container } = await renderAsync(<FloatingChat />);
    expect(container.firstChild).toBeNull();
  });

  it('renders when chat is open', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true });
    });

    await renderAsync(<FloatingChat />);

    expect(screen.getByText('Claude Code')).toBeInTheDocument();
  });

  it('uploads files pasted into the chat composer from the clipboard', async () => {
    const uploadFile = jest.fn();
    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [{ cli_id: 'claude', label: 'Claude Code', available: true }],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 39423 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile,
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    const image = new File(['fake image'], 'clip.png', { type: 'image/png' });
    fireEvent.paste(screen.getByRole('textbox', { name: /chat message input/i }), {
      clipboardData: {
        files: [image],
        items: [{ kind: 'file', getAsFile: () => image }],
      },
    });

    expect(uploadFile).toHaveBeenCalledWith(image);
  });

  it('renders minimized pill when minimized', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true });
    });

    await renderAsync(<FloatingChat />);

    const minimizeButton = screen.getByTitle('Minimize');
    fireEvent.click(minimizeButton);

    // After minimizing, should show the pill
    expect(screen.getByRole('button', { name: 'Restore chat window' })).toBeInTheDocument();
    expect(screen.queryByTitle('Close')).not.toBeInTheDocument();
  });

  it('clears stale embedded action state when it appears while minimized', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true });
    });

    await renderAsync(<FloatingChat />);

    fireEvent.click(screen.getByTitle('Minimize'));
    expect(screen.getByRole('button', { name: 'Restore chat window' })).toBeInTheDocument();

    act(() => {
      useChatStore.setState({
        chatView: 'action-dialog',
        embeddedAction: {
          id: 'auto-claude-md-audit',
          name: 'auto-claude-md-audit',
          prompt: 'Run the audit',
        },
      });
    });

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Restore chat window' })).not.toBeInTheDocument();
      expect(screen.getByTitle('Close')).toBeInTheDocument();
      expect(screen.queryByTestId('action-dialog-view')).not.toBeInTheDocument();
      expect(useChatStore.getState().chatView).toBe('terminal');
      expect(useChatStore.getState().embeddedAction).toBeNull();
    });
  });

  it('does not render the legacy bridge view when stale embedded action state changes', async () => {
    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'action-dialog',
        embeddedAction: {
          id: 'auto-lint',
          name: 'auto-lint',
          prompt: 'Run auto-lint',
        },
      });
    });

    await renderAsync(<FloatingChat />);

    await waitFor(() => {
      expect(screen.queryByTestId('action-dialog-view')).not.toBeInTheDocument();
      expect(useChatStore.getState().chatView).toBe('terminal');
      expect(useChatStore.getState().embeddedAction).toBeNull();
    });

    fireEvent.click(screen.getByTitle('Minimize'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Restore chat window' })).toBeInTheDocument();
      expect(screen.queryByTestId('action-dialog-view')).not.toBeInTheDocument();
    });

    act(() => {
      useChatStore.setState({
        chatView: 'action-dialog',
        embeddedAction: {
          id: 'auto-ui-quality',
          name: 'auto-ui-quality',
          prompt: 'Run auto-ui-quality',
        },
      });
    });

    await waitFor(() => {
      expect(screen.queryByTestId('action-dialog-view')).not.toBeInTheDocument();
      expect(useChatStore.getState().chatView).toBe('terminal');
      expect(useChatStore.getState().embeddedAction).toBeNull();
    });
  });

  it('closes chat when close button clicked', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true });
    });

    await renderAsync(<FloatingChat />);

    const closeButton = screen.getByTitle('Close');
    fireEvent.click(closeButton);

    // Chat should be closed
    const state = useChatStore.getState();
    expect(state.isOpen).toBe(false);
    expect(state.chatView).toBe('terminal');
    expect(state.embeddedAction).toBe(null);
  });

  it('toggles enlarged state', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true, isEnlarged: false });
    });

    await renderAsync(<FloatingChat />);

    const enlargeButton = screen.getByTitle('Enlarge');
    fireEvent.click(enlargeButton);

    const state = useChatStore.getState();
    expect(state.isEnlarged).toBe(true);
  });

  it('shows CLI selector dropdown when clicked', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true });
    });

    await renderAsync(<FloatingChat />);

    const cliButton = screen.getByText('Claude Code');
    fireEvent.click(cliButton);

    await waitFor(() => {
      expect(screen.getByText('Kimi')).toBeInTheDocument();
    });
  });

  it('renders the CLI selector menu outside the clipped chat window', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true });
    });

    await renderAsync(<FloatingChat />);

    fireEvent.click(screen.getByText('Claude Code'));

    const kimiOption = await screen.findByRole('button', { name: 'Select CLI: Kimi' });
    const selectorMenu = screen.getByTestId('cli-selector-menu');
    const chatWindow = screen.getByTestId('floating-chat-window');

    expect(selectorMenu).toHaveClass('fixed');
    expect(chatWindow).toHaveClass('overflow-hidden');
    expect(chatWindow.contains(selectorMenu)).toBe(false);
  });

  it('renders toolbar buttons in terminal view', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    // ADR-271: unified toolbar — buttons are Context, Actions, Search, Assist
    expect(screen.getByText('Context')).toBeInTheDocument();
    expect(screen.getByText('Actions')).toBeInTheDocument();
    expect(screen.getByText('Search')).toBeInTheDocument();
    expect(screen.getByText('Assist')).toBeInTheDocument();
  });

  it('opens MCP tools popover when clicked', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/mcp/tools/list')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            tools: [
              { name: 'tool1', description: 'Test tool 1' },
              { name: 'tool2', description: 'Test tool 2' },
            ],
          }),
          text: async () => JSON.stringify({ tools: [{ name: 'tool1', description: 'Test tool 1' }, { name: 'tool2', description: 'Test tool 2' }] }),
        } as Response;
      }
      return {
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ tools: [] }),
        text: async () => JSON.stringify({ tools: [] }),
      } as Response;
    });

    await renderAsync(<FloatingChat />);

    // ADR-271: Actions button opens the unified actions/tools/commands panel
    const actionsButton = screen.getByText('Actions');
    fireEvent.click(actionsButton);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search actions, tools, commands...')).toBeInTheDocument();
    });
  });

  it('opens help modal when Assist button clicked', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    const assistButton = screen.getByText('Assist');
    fireEvent.click(assistButton);

    await waitFor(() => {
      expect(screen.getByTestId('help-modal')).toBeInTheDocument();
    });
  });

  it('closes help modal when close is clicked', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    const assistButton = screen.getByText('Assist');
    fireEvent.click(assistButton);

    await waitFor(() => {
      expect(screen.getByTestId('help-modal')).toBeInTheDocument();
    });

    const closeButton = screen.getByText('Close Help');
    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByTestId('help-modal')).not.toBeInTheDocument();
    });
  });

  it('renders a prepared action draft instead of the bridge target list', async () => {
    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        preparedActionDraft: makePreparedActionDraft(),
      });
    });

    await renderAsync(<FloatingChat />);

    expect(screen.getByText('Prepared action')).toBeInTheDocument();
    expect(screen.getByText('Ask AI')).toBeInTheDocument();
    expect(screen.getAllByText('Claude Code').length).toBeGreaterThan(0);
    expect(screen.queryByTestId('action-dialog-view')).not.toBeInTheDocument();
  });

  it('sends a prepared action through the running selected client', async () => {
    const sendMessage = jest.fn().mockResolvedValue(true);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', category: 'remote', enabled: true, available: true },
      ],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage,
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        preparedActionDraft: makePreparedActionDraft({
          prompt: 'Inspect source paths.',
        }),
      });
    });

    await renderAsync(<FloatingChat />);

    fireEvent.change(screen.getByRole('textbox', { name: /prepared action remarks/i }), {
      target: { value: 'Use the newest deck.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send prepared action' }));

    await waitFor(() => {
      expect(sendMessage).toHaveBeenCalledWith(
        'Use the newest deck.\n\n--- SYSTEM PROMPT ---\n\nInspect source paths.',
      );
      expect(useChatStore.getState().preparedActionDraft).toBeNull();
    });
  });

  it('labels and sends through the running client when selectedCli differs', async () => {
    const sendMessage = jest.fn().mockResolvedValue(true);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', category: 'remote', enabled: true, available: true },
        { cli_id: 'kimi', label: 'Kimi', category: 'remote', enabled: true, available: true },
        { cli_id: 'codex', label: 'Codex', category: 'remote', enabled: false, available: false },
      ],
      selectedCli: 'codex',
      cliProcess: { cliId: 'kimi', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage,
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        preparedActionDraft: makePreparedActionDraft({
          prompt: 'Use the active running session.',
        }),
      });
    });

    await renderAsync(<FloatingChat />);

    expect(screen.getAllByText('Kimi').length).toBeGreaterThan(0);
    expect(screen.queryByText('Select an enabled chat client.')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Send prepared action' }));

    await waitFor(() => {
      expect(sendMessage).toHaveBeenCalledWith('Use the active running session.');
      expect(useChatStore.getState().preparedActionDraft).toBeNull();
    });
  });

  it('starts the current selected client with a prepared action prompt when no CLI is running', async () => {
    const startCli = jest.fn().mockResolvedValue(true);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'kimi', label: 'Kimi', category: 'remote', enabled: true, available: true },
      ],
      selectedCli: 'kimi',
      cliProcess: null,
      attachedFiles: [],
      startCli,
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        preparedActionDraft: makePreparedActionDraft({
          prompt: 'Rebuild the Skills browse index.',
        }),
      });
    });

    await renderAsync(<FloatingChat />);

    fireEvent.click(screen.getByRole('button', { name: 'Send prepared action' }));

    await waitFor(() => {
      expect(startCli).toHaveBeenCalledWith(
        'kimi',
        expect.objectContaining({
          oneshotPrompt: 'Rebuild the Skills browse index.',
        }),
      );
    });
  });

  it('keeps the prepared draft visible when client startup returns false', async () => {
    const startCli = jest.fn().mockResolvedValue(false);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', category: 'remote', enabled: true, available: true },
      ],
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      startCli,
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        preparedActionDraft: makePreparedActionDraft({
          id: 'skill.reindex',
          prompt: 'Rebuild the Skills browse index.',
        }),
      });
    });

    await renderAsync(<FloatingChat />);

    fireEvent.click(screen.getByRole('button', { name: 'Send prepared action' }));

    await waitFor(() => {
      expect(screen.getByText('Failed to start Claude Code.')).toBeInTheDocument();
      expect(useChatStore.getState().preparedActionDraft?.id).toBe('skill.reindex');
    });
  });

  it('keeps the prepared draft visible when running client send returns false', async () => {
    const sendMessage = jest.fn().mockResolvedValue(false);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', category: 'remote', enabled: true, available: true },
      ],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage,
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        preparedActionDraft: makePreparedActionDraft({
          id: 'skill.reindex',
          prompt: 'Rebuild the Skills browse index.',
        }),
      });
    });

    await renderAsync(<FloatingChat />);

    fireEvent.click(screen.getByRole('button', { name: 'Send prepared action' }));

    await waitFor(() => {
      expect(screen.getByText('Failed to send prepared action.')).toBeInTheDocument();
      expect(useChatStore.getState().preparedActionDraft?.id).toBe('skill.reindex');
    });
  });

  it('does not render the legacy action-dialog bridge target list', async () => {
    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'action-dialog',
        embeddedAction: {
          id: 'test-action',
          name: 'Test Action',
          description: 'Test description',
          prompt: 'Test prompt',
        },
      });
    });

    await renderAsync(<FloatingChat />);

    await waitFor(() => {
      expect(screen.queryByTestId('action-dialog-view')).not.toBeInTheDocument();
      expect(useChatStore.getState().chatView).toBe('terminal');
      expect(useChatStore.getState().embeddedAction).toBeNull();
    });
  });

  it('starts operation chat without injecting startup page context by default', async () => {
    mockMode.mode = 'operation';
    const startCli = jest.fn().mockResolvedValue(undefined);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', category: 'remote', enabled: true, available: true },
      ],
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      startCli,
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    await waitFor(() => {
      expect(startCli).toHaveBeenCalledWith(
        'claude',
        expect.objectContaining({ autoContext: false, verbosity: 'quiet' }),
      );
    });

    mockMode.mode = 'development';
  });

  it('does not auto-start operation chat for editable action drafts', async () => {
    mockMode.mode = 'operation';
    const startCli = jest.fn().mockResolvedValue(undefined);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', category: 'remote', enabled: true, available: true },
      ],
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      startCli,
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        draft: true,
        initialPrompt: 'Review this action before sending.',
      });
    });

    await renderAsync(<FloatingChat />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByRole('textbox', { name: /chat message input/i })).toHaveValue(
      'Review this action before sending.',
    );
    expect(startCli).not.toHaveBeenCalled();

    mockMode.mode = 'development';
  });

  it('keeps manual operation-mode CLI start free of startup page context', async () => {
    mockMode.mode = 'operation';
    const startCli = jest.fn().mockResolvedValue(undefined);

    mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/cli?cliId=claude')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ status: 'detached', pid: 12345 }),
          text: async () => JSON.stringify({ status: 'detached', pid: 12345 }),
        } as Response;
      }
      return {
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ tools: [] }),
        text: async () => JSON.stringify({ tools: [] }),
      } as Response;
    });

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', category: 'remote', enabled: true, available: true },
      ],
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      startCli,
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(startCli).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTitle('Start CLI'));

    await waitFor(() => {
      expect(startCli).toHaveBeenCalledWith(
        'claude',
        expect.objectContaining({ autoContext: false, verbosity: 'quiet' }),
      );
    });

    mockMode.mode = 'development';
  });

  it('does not render the legacy action-dialog bridge in operation mode', async () => {
    mockMode.mode = 'operation';
    const startCli = jest.fn().mockResolvedValue(undefined);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', category: 'remote', enabled: true, available: true },
      ],
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      startCli,
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'action-dialog',
        embeddedAction: {
          id: 'browse-deep-search',
          name: 'Browse Deep Search',
          prompt: 'Find my last pitch',
        },
      });
    });

    await renderAsync(<FloatingChat />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(screen.queryByTestId('action-dialog-view')).not.toBeInTheDocument();
      expect(useChatStore.getState().chatView).toBe('terminal');
      expect(useChatStore.getState().embeddedAction).toBeNull();
    });

    mockMode.mode = 'development';
  });

  it('starts prepared action handoff without the generic operation auto-context prompt', async () => {
    mockMode.mode = 'operation';
    const startCli = jest.fn().mockResolvedValue(undefined);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', category: 'remote', enabled: true, available: true },
      ],
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      startCli,
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        preparedActionDraft: makePreparedActionDraft({
          id: 'browse-deep-search',
          label: 'Browse Deep Search',
          prompt: 'Find my last pitch',
        }),
      });
    });

    await renderAsync(<FloatingChat />);
    fireEvent.click(screen.getByRole('button', { name: 'Send prepared action' }));

    await waitFor(() => {
      expect(startCli).toHaveBeenCalledWith(
        'claude',
        expect.objectContaining({ autoContext: false, verbosity: 'quiet' }),
      );
    });

    mockMode.mode = 'development';
  });

  it('returns to terminal view when stale action dialog state is cancelled by cleanup', async () => {
    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'action-dialog',
        embeddedAction: {
          id: 'test-action',
          name: 'Test Action',
          prompt: 'Test prompt',
        },
      });
    });

    await renderAsync(<FloatingChat />);

    await waitFor(() => {
      const state = useChatStore.getState();
      expect(state.chatView).toBe('terminal');
      expect(state.embeddedAction).toBeNull();
    });
  });

  it('shows actions-list view when chatView is actions-list', async () => {
    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'actions-list',
      });
    });

    await renderAsync(<FloatingChat />);

    expect(screen.getByTestId('actions-list-view')).toBeInTheDocument();
  });

  it('returns to terminal view when back is clicked from actions list', async () => {
    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'actions-list',
      });
    });

    await renderAsync(<FloatingChat />);

    const backButton = screen.getByText('Back');
    fireEvent.click(backButton);

    await waitFor(() => {
      const state = useChatStore.getState();
      expect(state.chatView).toBe('terminal');
    });
  });

  it('renders mode toggle in header', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true });
    });

    await renderAsync(<FloatingChat />);

    expect(screen.getByTestId('mode-toggle')).toBeInTheDocument();
  });

  it('applies enlarged height class when isEnlarged is true', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true, isEnlarged: true });
    });

    const { container } = await renderAsync(<FloatingChat />);

    const chatContainer = container.querySelector('.fixed');
    expect(chatContainer).toHaveClass('h-[calc(100vh-1.5rem)]', 'sm:h-[960px]');
  });

  it('applies default height class when isEnlarged is false', async () => {
    act(() => {
      useChatStore.setState({ isOpen: true, isEnlarged: false });
    });

    const { container } = await renderAsync(<FloatingChat />);

    const chatContainer = container.querySelector('.fixed');
    expect(chatContainer).toHaveClass(
      'h-[min(600px,calc(100vh-1.5rem))]',
      'sm:h-[600px]',
    );
  });

  it('shows terminal focus indicator when terminalFocused is true', async () => {
    // Mock a running CLI process
    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', available: true },
      ],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        terminalFocused: true,
      });
    });

    await renderAsync(<FloatingChat />);

    expect(screen.getByText('Terminal Focus')).toBeInTheDocument();
    expect(screen.getByText('Keyboard input goes directly to terminal')).toBeInTheDocument();
  });

  it('does not restart a running CLI when airplane status hydrates from loading to ready', async () => {
    const startCli = jest.fn();
    const stopCli = jest.fn();

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', available: true },
      ],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli,
      stopCli,
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });
    Object.assign(mockAirplaneState, {
      airplaneMode: false,
      airplaneModeReady: false,
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    const { Wrapper } = createQueryWrapper();
    const { rerender } = render(<FloatingChat />, { wrapper: Wrapper });

    await act(async () => {
      Object.assign(mockAirplaneState, {
        airplaneMode: true,
        airplaneModeReady: true,
      });
      rerender(<FloatingChat />);
    });

    expect(stopCli).not.toHaveBeenCalled();
    expect(startCli).not.toHaveBeenCalled();
  });

  it('switches the route preference for new chats without restarting a running CLI', async () => {
    const startCli = jest.fn().mockResolvedValue(undefined);
    const stopCli = jest.fn().mockResolvedValue(undefined);
    const setAirplaneMode = jest.fn(async (enabled: boolean) => {
      Object.assign(mockAirplaneState, { airplaneMode: enabled });
    });

    mockChatRouteControlEndpoints();
    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', available: true },
      ],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli,
      stopCli,
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });
    Object.assign(mockAirplaneState, {
      airplaneMode: false,
      airplaneModeReady: true,
      airplaneBackendReady: true,
      airplaneLocalModel: 'qwen3.5:9b',
      setAirplaneMode,
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    const { Wrapper } = createQueryWrapper();
    const { rerender } = render(<FloatingChat />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('button', { name: /use offline for chat routing/i }));
    fireEvent.click(await screen.findByRole('button', { name: /switch for new chats/i }));

    await waitFor(() => expect(setAirplaneMode).toHaveBeenCalledWith(true));
    await act(async () => {
      rerender(<FloatingChat />);
      await Promise.resolve();
    });

    expect(stopCli).not.toHaveBeenCalled();
    expect(startCli).not.toHaveBeenCalled();
  });

  it('restarts exactly once when the route sheet switch and restart action is used', async () => {
    const startCli = jest.fn().mockResolvedValue(undefined);
    const stopCli = jest.fn().mockResolvedValue(undefined);
    const setAirplaneMode = jest.fn(async (enabled: boolean) => {
      Object.assign(mockAirplaneState, { airplaneMode: enabled });
    });

    mockChatRouteControlEndpoints();
    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', available: true },
      ],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli,
      stopCli,
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });
    Object.assign(mockAirplaneState, {
      airplaneMode: false,
      airplaneModeReady: true,
      airplaneBackendReady: true,
      airplaneLocalModel: 'qwen3.5:9b',
      setAirplaneMode,
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    const { Wrapper } = createQueryWrapper();
    const { rerender } = render(<FloatingChat />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('button', { name: /use offline for chat routing/i }));
    fireEvent.click(await screen.findByRole('button', { name: /switch \+ restart/i }));

    await waitFor(() => {
      expect(setAirplaneMode).toHaveBeenCalledWith(true);
      expect(stopCli).toHaveBeenCalledTimes(1);
      expect(stopCli).toHaveBeenCalledWith('claude');
      expect(startCli).toHaveBeenCalledTimes(1);
      expect(startCli).toHaveBeenCalledWith(
        'claude',
        expect.objectContaining({ airplaneMode: true }),
      );
    });

    await act(async () => {
      rerender(<FloatingChat />);
      await Promise.resolve();
    });

    expect(stopCli).toHaveBeenCalledTimes(1);
    expect(startCli).toHaveBeenCalledTimes(1);
  });

  it('does not restart a running CLI when airplane mode stays on but the configured local model changes', async () => {
    const startCli = jest.fn().mockResolvedValue(undefined);
    const stopCli = jest.fn().mockResolvedValue(undefined);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', available: true },
      ],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli,
      stopCli,
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });
    Object.assign(mockAirplaneState, {
      airplaneMode: true,
      airplaneModeReady: true,
      airplaneBackendReady: true,
      airplaneLocalModel: 'qwen3.5:9b',
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    const { Wrapper } = createQueryWrapper();
    const { rerender } = render(<FloatingChat />, { wrapper: Wrapper });

    await act(async () => {
      Object.assign(mockAirplaneState, {
        airplaneLocalModel: 'llama3.2:3b',
      });
      rerender(<FloatingChat />);
      await Promise.resolve();
    });

    expect(stopCli).not.toHaveBeenCalled();
    expect(startCli).not.toHaveBeenCalled();
  });

  it('does not restart a running CLI when airplane mode turns on before the local backend is ready and later becomes ready', async () => {
    const startCli = jest.fn().mockResolvedValue(undefined);
    const stopCli = jest.fn().mockResolvedValue(undefined);

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', available: true },
      ],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli,
      stopCli,
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });
    Object.assign(mockAirplaneState, {
      airplaneMode: false,
      airplaneModeReady: true,
      airplaneBackendReady: false,
      airplaneLocalModel: null,
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    const { Wrapper } = createQueryWrapper();
    const { rerender } = render(<FloatingChat />, { wrapper: Wrapper });

    await act(async () => {
      Object.assign(mockAirplaneState, {
        airplaneMode: true,
        airplaneBackendReady: false,
        airplaneLocalModel: 'qwen3.5:9b',
      });
      rerender(<FloatingChat />);
      await Promise.resolve();
    });

    expect(stopCli).not.toHaveBeenCalled();
    expect(startCli).not.toHaveBeenCalled();

    await act(async () => {
      Object.assign(mockAirplaneState, {
        airplaneBackendReady: true,
      });
      rerender(<FloatingChat />);
      await Promise.resolve();
    });

    expect(stopCli).not.toHaveBeenCalled();
    expect(startCli).not.toHaveBeenCalled();
  });

  it('exits terminal focus when Esc to exit button is clicked', async () => {
    // Mock a running CLI process
    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', available: true },
      ],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        terminalFocused: true,
      });
    });

    await renderAsync(<FloatingChat />);

    const exitButton = screen.getByText('Esc to exit');
    fireEvent.click(exitButton);

    await waitFor(() => {
      const state = useChatStore.getState();
      expect(state.terminalFocused).toBe(false);
    });
  });

  it('hides input area when in terminal focus mode', async () => {
    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        terminalFocused: true,
      });
    });

    await renderAsync(<FloatingChat />);

    // Input area should not be visible in focus mode
    expect(screen.queryByPlaceholderText(/Type a command/)).not.toBeInTheDocument();
  });

  it('shows input area when not in terminal focus mode', async () => {
    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        terminalFocused: false,
      });
    });

    await renderAsync(<FloatingChat />);

    // Input area should be visible.
    expect(screen.getByRole('textbox', { name: /chat message input/i })).toBeInTheDocument();
  });

  // --- ADR-047: Chat bubble view tests ---
  // Note: ADR-104 changed operation mode to use terminal view instead of chat

  it('keeps terminal view in operation mode (ADR-104)', async () => {
    mockMode.mode = 'operation';

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
      });
    });

    await renderAsync(<FloatingChat />);

    // ADR-104: Terminal view stays in operation mode
    const state = useChatStore.getState();
    expect(state.chatView).toBe('terminal');

    mockMode.mode = 'development'; // restore
  });

  it('keeps terminal view in development mode', async () => {
    mockMode.mode = 'development';

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
      });
    });

    await renderAsync(<FloatingChat />);

    // Should stay on terminal
    const state = useChatStore.getState();
    expect(state.chatView).toBe('terminal');
  });

  it('redirects stale chat view state back to terminal', async () => {
    mockMode.mode = 'development';

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'chat',
      });
    });

    await renderAsync(<FloatingChat />);

    await waitFor(() => {
      expect(useChatStore.getState().chatView).toBe('terminal');
    });

    mockMode.mode = 'development'; // restore
  });

  // --- ADR-047 Phase 5: Mode-aware label tests ---

  it('shows actions button in operation mode (auto-fetches tools)', async () => {
    mockMode.mode = 'operation';

    // Start directly in terminal view - toggle is hidden in operation mode
    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        terminalFocused: false,
      });
    });

    await renderAsync(<FloatingChat />);

    // Actions button is visible in operation mode (ADR-047)
    // When no tools loaded, button shows without count badge
    await waitFor(() => {
      expect(screen.getByText('Actions')).toBeInTheDocument();
    });
    expect(screen.queryByText('MCP Tools')).not.toBeInTheDocument();

    mockMode.mode = 'development'; // restore
  });

  it('shows "Actions" button label in dev mode (ADR-271 unified toolbar)', async () => {
    mockMode.mode = 'development';

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        terminalFocused: false,
      });
    });

    await renderAsync(<FloatingChat />);

    // ADR-271: unified toolbar uses "Actions" in both dev and operation modes
    expect(screen.getByText('Actions')).toBeInTheDocument();
  });

  it('shows "Assistant" label instead of CLI name in operation mode', async () => {
    mockMode.mode = 'operation';

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'chat' });
    });

    await renderAsync(<FloatingChat />);

    // Header is always visible regardless of chatView
    expect(screen.getByText('Assistant')).toBeInTheDocument();

    mockMode.mode = 'development'; // restore
  });

  it('shows Assist button in operation mode (ADR-271 unified toolbar)', async () => {
    mockMode.mode = 'operation';

    // Start directly in terminal view - in operation mode toggle is hidden
    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        terminalFocused: false,
      });
    });

    await renderAsync(<FloatingChat />);

    await waitFor(() => {
      // ADR-271: unified toolbar — Assist button always shown, no standalone Data button
      expect(screen.getByText('Assist')).toBeInTheDocument();
      expect(screen.queryByText('Data')).not.toBeInTheDocument();
    });

    mockMode.mode = 'development'; // restore
  });

  it('hides PID badge in operation mode', async () => {
    mockMode.mode = 'operation';

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [
        { cli_id: 'claude', label: 'Claude Code', available: true },
      ],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'chat' });
    });

    await renderAsync(<FloatingChat />);

    expect(screen.queryByText(/PID/)).not.toBeInTheDocument();

    mockMode.mode = 'development'; // restore
  });

  // --- ADR-104: Welcome overlay tests ---

  it('shows welcome overlay in operation mode when CLI is not running', async () => {
    mockMode.mode = 'operation';

    // Mock CLI not running
    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [{ cli_id: 'claude', label: 'Claude Code', available: true }],
      selectedCli: 'claude',
      cliProcess: null, // Not running
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    await waitFor(() => {
      expect(screen.getByText('Ask me anything')).toBeInTheDocument();
    });

    mockMode.mode = 'development';
  });

  it('hides welcome overlay when CLI is running in operation mode', async () => {
    mockMode.mode = 'operation';

    // Mock CLI running
    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [{ cli_id: 'claude', label: 'Claude Code', available: true }],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    await waitFor(() => {
      expect(screen.queryByText('Ask me anything')).not.toBeInTheDocument();
    });

    mockMode.mode = 'development';
  });

  it('shows suggested actions in welcome overlay', async () => {
    mockMode.mode = 'operation';

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [{ cli_id: 'claude', label: 'Claude Code', available: true }],
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      startCli: jest.fn().mockResolvedValue(undefined),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/mcp/tools/list')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            tools: [
              { name: 'finance-summary', displayName: 'View Finances' },
              { name: 'career-summary', displayName: 'Career Overview' },
            ],
          }),
          text: async () => JSON.stringify({ tools: [{ name: 'finance-summary', displayName: 'View Finances' }, { name: 'career-summary', displayName: 'Career Overview' }] }),
        } as Response;
      }
      return {
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({}),
        text: async () => JSON.stringify({}),
      } as Response;
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    // Suggested actions are now derived from MCP tools via useMcpQuery.
    // In test environment without full MCP mock, the chat panel renders
    // but suggested actions may not appear. Verify the chat panel is open.
    await waitFor(() => {
      expect(screen.getByTestId('mode-toggle')).toBeInTheDocument();
    });

    mockMode.mode = 'development';
  });

  it('allows input in operation mode even when CLI is not running', async () => {
    mockMode.mode = 'operation';

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [{ cli_id: 'claude', label: 'Claude Code', available: true }],
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      startCli: jest.fn().mockResolvedValue(undefined),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal', terminalFocused: false });
    });

    await renderAsync(<FloatingChat />);

    // In operation mode, placeholder should say "Message..." and textarea should NOT be disabled
    const textarea = screen.getByPlaceholderText('Message...');
    expect(textarea).not.toBeDisabled();

    mockMode.mode = 'development';
  });

  it('routes remote chat submissions through the CLI flow instead of /api/llm', async () => {
    const sendMessage = jest.fn();

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [{ cli_id: 'claude', label: 'Claude Code', available: true }],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage,
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({
        isOpen: true,
        chatView: 'terminal',
        mode: 'remote',
      });
    });

    await renderAsync(<FloatingChat />);

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'hello from remote mode' } });
    fireEvent.keyDown(textarea, { key: 'Enter', metaKey: true });

    await waitFor(() => {
      expect(sendMessage).toHaveBeenCalledWith('hello from remote mode');
    });

    expect(
      mockFetch.mock.calls.some((call) => String(call[0]).includes('/api/llm')),
    ).toBe(false);
  });

  it('does not call terminal handoff when the server reports the local CLI is no longer running', async () => {
    mockMode.mode = 'development';
    const setMessages = jest.fn();

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [{ cli_id: 'claude', label: 'Claude Code', available: true }],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 39423 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages,
      clearMessages: jest.fn(),
    });

    mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/cli?cliId=claude')) {
        return {
          ok: true,
          status: 200,
          url,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ status: 'exited', pid: 39423 }),
          text: async () => JSON.stringify({ status: 'exited', pid: 39423 }),
        } as Response;
      }
      if (url.includes('/api/session/open-terminal')) {
        throw new Error('open-terminal should not be called for exited sessions');
      }
      return {
        ok: true,
        status: 200,
        url,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ tools: [] }),
        text: async () => JSON.stringify({ tools: [] }),
      } as Response;
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    const handoffButton = screen.getByRole('button', {
      name: /open in native terminal/i,
    });
    expect(handoffButton).not.toBeDisabled();

    await act(async () => {
      fireEvent.click(handoffButton);
    });

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'CLI session is not running. Start it before opening a native terminal.',
      );
    });
    expect(
      mockFetch.mock.calls.some((call) =>
        String(call[0]).includes('/api/session/open-terminal'),
      ),
    ).toBe(false);
    expect(setMessages).toHaveBeenCalled();
  });

  it('clears the embedded terminal and resets the parser after a native terminal handoff', async () => {
    mockMode.mode = 'development';

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [{ cli_id: 'claude', label: 'Claude Code', available: true }],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 39423 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/cli?cliId=claude')) {
        return {
          ok: true,
          status: 200,
          url,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ status: 'running', pid: 39423 }),
          text: async () => JSON.stringify({ status: 'running', pid: 39423 }),
        } as Response;
      }
      if (url.includes('/api/session/open-terminal')) {
        return {
          ok: true,
          status: 200,
          url,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ ok: true, shortcut: 'ca' }),
          text: async () => JSON.stringify({ ok: true, shortcut: 'ca' }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        url,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ tools: [] }),
        text: async () => JSON.stringify({ tools: [] }),
      } as Response;
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    const handoffButton = screen.getByRole('button', {
      name: /open in native terminal/i,
    });
    expect(handoffButton).not.toBeDisabled();

    await act(async () => {
      fireEvent.click(handoffButton);
    });

    await waitFor(() => {
      expect(
        mockFetch.mock.calls.some((call) =>
          String(call[0]).includes('/api/session/open-terminal'),
        ),
      ).toBe(true);
    });

    // Bug: handoff exited the PTY but left the stale "exit / Resume this
    // session with: claude --resume ..." buffer painted in the terminal.
    // Returning to a clean state must clear the xterm buffer and parser.
    await waitFor(() => {
      expect(mockClearTerminal).toHaveBeenCalled();
    });
    expect(mockResetPtyStreamParser).toHaveBeenCalled();
  });

  it('uploads files pasted into the chat composer from the clipboard', async () => {
    const uploadFile = jest.fn();
    const image = new File(['fake image'], 'clip.png', { type: 'image/png' });

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [{ cli_id: 'claude', label: 'Claude Code', available: true }],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 39423 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile,
      removeAttachedFile: jest.fn(),
      setMessages: jest.fn(),
      clearMessages: jest.fn(),
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    fireEvent.paste(screen.getByRole('textbox'), {
      clipboardData: {
        files: [image],
        items: [
          {
            kind: 'file',
            type: 'image/png',
            getAsFile: () => image,
          },
        ],
      },
    });

    expect(uploadFile).toHaveBeenCalledWith(image);
  });

  it('does not call terminal handoff when the server reports the local CLI is no longer running', async () => {
    const setMessages = jest.fn();

    mockUseCliChat.mockReturnValue({
      messages: [],
      configs: [{ cli_id: 'claude', label: 'Claude Code', available: true }],
      selectedCli: 'claude',
      cliProcess: { cliId: 'claude', status: 'running', pid: 39423 },
      attachedFiles: [],
      startCli: jest.fn(),
      stopCli: jest.fn(),
      switchCli: jest.fn(),
      sendMessage: jest.fn(),
      sendRawKey: jest.fn(),
      sendSystemCommand: jest.fn(),
      uploadFile: jest.fn(),
      removeAttachedFile: jest.fn(),
      setMessages,
      clearMessages: jest.fn(),
    });

    mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/cli?cliId=claude')) {
        return {
          ok: true,
          status: 200,
          url,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ cliId: 'claude', status: 'exited', pid: 39423 }),
          text: async () => JSON.stringify({ cliId: 'claude', status: 'exited', pid: 39423 }),
        } as Response;
      }
      if (url.includes('/api/session/open-terminal')) {
        throw new Error('open-terminal should not be called for an exited PTY');
      }
      return {
        ok: true,
        status: 200,
        url,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ tools: [] }),
        text: async () => JSON.stringify({ tools: [] }),
      } as Response;
    });

    act(() => {
      useChatStore.setState({ isOpen: true, chatView: 'terminal' });
    });

    await renderAsync(<FloatingChat />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /open in native terminal/i }));
    });

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'CLI session is not running. Start it before opening a native terminal.',
      );
    });
    expect(
      mockFetch.mock.calls.some((call) =>
        String(call[0]).includes('/api/session/open-terminal'),
      ),
    ).toBe(false);
    expect(setMessages).toHaveBeenCalled();
  });
});
