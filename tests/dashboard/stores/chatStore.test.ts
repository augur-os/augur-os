import { act, renderHook } from '@testing-library/react';
import { useChatStore } from '@/lib/stores/chatStore';

describe('chatStore - CLI state (ADR-034)', () => {
  beforeEach(() => {
    act(() => {
      const state = useChatStore.getState();
      // Reset CLI state
      state.setSelectedCli('claude');
      state.setCliProcess(null);
      state.clearAttachedFiles();
      state.closeChat();
    });
  });

  describe('initial state', () => {
    it('should have correct CLI initial values', () => {
      const { result } = renderHook(() => useChatStore());

      expect(result.current.selectedCli).toBe('claude');
      expect(result.current.cliProcess).toBeNull();
      expect(result.current.attachedFiles).toEqual([]);
    });
  });

  describe('setSelectedCli', () => {
    it('test_cli_store_select_cli - should update selectedCli', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.setSelectedCli('claude');
      });
      expect(result.current.selectedCli).toBe('claude');

      act(() => {
        result.current.setSelectedCli('kimi');
      });
      expect(result.current.selectedCli).toBe('kimi');

      act(() => {
        result.current.setSelectedCli('codex');
      });
      expect(result.current.selectedCli).toBe('codex');
    });
  });

  describe('setCliProcess', () => {
    it('should set CLI process state', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.setCliProcess({
          cliId: 'claude',
          status: 'running',
          pid: 12345,
        });
      });

      expect(result.current.cliProcess).toEqual({
        cliId: 'claude',
        status: 'running',
        pid: 12345,
      });
    });

    it('should clear CLI process state', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.setCliProcess({
          cliId: 'claude',
          status: 'running',
          pid: 12345,
        });
      });

      act(() => {
        result.current.setCliProcess(null);
      });

      expect(result.current.cliProcess).toBeNull();
    });
  });

  describe('attachedFiles', () => {
    const mockFile = {
      originalName: 'test.jpg',
      stagedPath: '/tmp/uploads/123_test.jpg',
      size: 2048,
      mimeType: 'image/jpeg',
      timestamp: 1700000000,
    };

    const mockFile2 = {
      originalName: 'data.csv',
      stagedPath: '/tmp/uploads/456_data.csv',
      size: 4096,
      mimeType: 'text/csv',
      timestamp: 1700000001,
    };

    it('test_cli_store_add_attached_file - should add file to attachedFiles', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.addAttachedFile(mockFile);
      });

      expect(result.current.attachedFiles).toHaveLength(1);
      expect(result.current.attachedFiles[0]).toEqual(mockFile);
    });

    it('should add multiple files', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.addAttachedFile(mockFile);
        result.current.addAttachedFile(mockFile2);
      });

      expect(result.current.attachedFiles).toHaveLength(2);
    });

    it('test_cli_store_remove_attached_file - should remove file by stagedPath', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.addAttachedFile(mockFile);
        result.current.addAttachedFile(mockFile2);
      });

      act(() => {
        result.current.removeAttachedFile(mockFile.stagedPath);
      });

      expect(result.current.attachedFiles).toHaveLength(1);
      expect(result.current.attachedFiles[0].originalName).toBe('data.csv');
    });

    it('test_cli_store_clear_attached_files - should clear all files', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.addAttachedFile(mockFile);
        result.current.addAttachedFile(mockFile2);
      });

      expect(result.current.attachedFiles).toHaveLength(2);

      act(() => {
        result.current.clearAttachedFiles();
      });

      expect(result.current.attachedFiles).toEqual([]);
    });
  });

  describe('existing state preservation', () => {
    it('should preserve existing openChat/closeChat behavior', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChat({ mode: 'ide', agent: 'test' });
      });

      expect(result.current.isOpen).toBe(true);
      expect(result.current.mode).toBe('ide');
      expect(result.current.agent).toBe('test');

      act(() => {
        result.current.closeChat();
      });

      expect(result.current.isOpen).toBe(false);
    });

    it('should preserve setWaiting behavior', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.setWaiting(true);
      });

      expect(result.current.isWaiting).toBe(true);

      act(() => {
        result.current.setWaiting(false);
      });

      expect(result.current.isWaiting).toBe(false);
    });
  });

  describe('openChat - session persistence and context', () => {
    const mockFetch = jest.fn();

    beforeEach(() => {
      global.fetch = mockFetch as any;
      mockFetch.mockClear();
      mockFetch.mockResolvedValue({
        json: () => Promise.resolve({ success: true }),
      });
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    it('should persist session via fetch when opening chat', async () => {
      const { result } = renderHook(() => useChatStore());

      await act(async () => {
        result.current.openChat({
          mode: 'ide',
          context: { page: '/brain' },
          agent: 'test-agent',
          initialPrompt: 'hello',
        });
      });

      // openChat now uses mcpCall("update-chat-session", ...) which routes to /api/mcp/tool
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/mcp/tool',
        expect.objectContaining({
          method: 'POST',
        })
      );

      // Check that the fetch body contains expected data via the MCP tool wrapper
      const fetchCall = mockFetch.mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);
      expect(body.tool).toBe('update-chat-session');
      expect(body.args.isActive).toBe(true);
      expect(body.args.mode).toBe('ide');
      expect(body.args.context).toEqual({ page: '/brain' });
      expect(body.args.status).toBe('idle');
      expect(body.args.startTime).toBeDefined();
    });

    it('should propagate context parameter to state', () => {
      const { result } = renderHook(() => useChatStore());

      const testContext = {
        page: '/career',
        skillId: 'career',
        metadata: { foo: 'bar' },
      };

      act(() => {
        result.current.openChat({
          mode: 'ide',
          context: testContext,
        });
      });

      expect(result.current.context).toEqual(testContext);
    });

    it('should handle empty context parameter', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChat({
          mode: 'ide',
        });
      });

      expect(result.current.context).toEqual({});
    });

    it('should handle fetch errors gracefully', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useChatStore());

      await act(async () => {
        result.current.openChat({
          mode: 'ide',
          context: { page: '/brain' },
        });
        // Wait for promise to settle
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      // Chat should still open even if persistence fails
      expect(result.current.isOpen).toBe(true);
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to persist session',
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe('closeChat - state reset', () => {
    it('should reset chatView when closing chat', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChat({ mode: 'ide' });
        result.current.setChatView('action-dialog');
      });

      expect(result.current.chatView).toBe('action-dialog');

      act(() => {
        result.current.closeChat();
      });

      expect(result.current.chatView).toBe('terminal');
    });

    it('should reset embeddedAction when closing chat', () => {
      const { result } = renderHook(() => useChatStore());

      const testAction = {
        id: 'test-action',
        name: 'Test',
        prompt: 'test prompt',
      };

      act(() => {
        result.current.openChat({ mode: 'ide' });
        result.current.setEmbeddedAction(testAction);
      });

      expect(result.current.embeddedAction).toEqual(testAction);

      act(() => {
        result.current.closeChat();
      });

      expect(result.current.embeddedAction).toBeNull();
    });

    it('should reset terminalFocused when closing chat', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChat({ mode: 'ide' });
        result.current.setTerminalFocused(true);
      });

      expect(result.current.terminalFocused).toBe(true);

      act(() => {
        result.current.closeChat();
      });

      expect(result.current.terminalFocused).toBe(false);
    });

    it('should reset terminalFallbackActive when closing chat', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChat({ mode: 'ide' });
        result.current.setTerminalFallbackActive(true);
      });

      expect(result.current.terminalFallbackActive).toBe(true);

      act(() => {
        result.current.closeChat();
      });

      expect(result.current.terminalFallbackActive).toBe(false);
    });
  });

  describe('preparedActionDraft', () => {
    const preparedDraft = {
      id: 'browse.deep-search',
      label: 'Ask AI',
      description: 'Investigate Browse results',
      prompt: 'Inspect source paths.',
      page: 'browse',
      tier: 'deep' as const,
      dispatch: 'ide' as const,
      createdAt: '2026-05-24T00:00:00.000Z',
    };

    it('opens chat with a prepared action draft in terminal view', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChatWithPreparedActionDraft(preparedDraft, {
          page: '/browse',
          actionId: preparedDraft.id,
          actionName: preparedDraft.label,
        });
      });

      expect(result.current.isOpen).toBe(true);
      expect(result.current.chatView).toBe('terminal');
      expect(result.current.embeddedAction).toBeNull();
      expect(result.current.initialPrompt).toBe('');
      expect(result.current.draft).toBe(false);
      expect(result.current.preparedActionDraft).toEqual(preparedDraft);
      expect(result.current.context).toEqual({
        page: '/browse',
        actionId: preparedDraft.id,
        actionName: preparedDraft.label,
      });
    });

    it('clears a prepared action draft without closing chat', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChatWithPreparedActionDraft(preparedDraft);
        result.current.clearPreparedActionDraft();
      });

      expect(result.current.isOpen).toBe(true);
      expect(result.current.preparedActionDraft).toBeNull();
    });

    it('resets prepared action drafts when closing chat', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChatWithPreparedActionDraft(preparedDraft);
      });
      expect(result.current.preparedActionDraft).toEqual(preparedDraft);

      act(() => {
        result.current.closeChat();
      });

      expect(result.current.isOpen).toBe(false);
      expect(result.current.preparedActionDraft).toBeNull();
    });

    it('clears a prepared action draft when opening a normal chat', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChatWithPreparedActionDraft(preparedDraft);
      });
      expect(result.current.preparedActionDraft).toEqual(preparedDraft);

      act(() => {
        result.current.openChat({ mode: 'ide' });
      });

      expect(result.current.isOpen).toBe(true);
      expect(result.current.preparedActionDraft).toBeNull();
    });

    it('clears a prepared action draft when opening a oneshot result', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChatWithPreparedActionDraft(preparedDraft);
      });
      expect(result.current.preparedActionDraft).toEqual(preparedDraft);

      act(() => {
        result.current.openChatWithOneshotResult({
          actionId: 'browse.summary',
          actionLabel: 'Summarize',
          resultText: 'Summary text',
          timestamp: new Date('2026-05-24T00:01:00.000Z'),
          prompt: 'Summarize Browse.',
        });
      });

      expect(result.current.isOpen).toBe(true);
      expect(result.current.preparedActionDraft).toBeNull();
    });
  });

  describe('clearInitialPrompt - ADR-144', () => {
    it('should clear initialPrompt after first send', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.openChat({
          mode: 'auto',
          context: { actionId: 'test', actionName: 'Test Action' },
          initialPrompt: 'Help me brainstorm content ideas',
        });
      });

      expect(result.current.initialPrompt).toBe('Help me brainstorm content ideas');
      expect(result.current.context.actionName).toBe('Test Action');

      act(() => {
        result.current.clearInitialPrompt();
      });

      expect(result.current.initialPrompt).toBe('');
    });
  });

  describe('setChatView - view mode changes', () => {
    it('should change view mode to terminal', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.setChatView('action-dialog');
      });

      expect(result.current.chatView).toBe('action-dialog');

      act(() => {
        result.current.setChatView('terminal');
      });

      expect(result.current.chatView).toBe('terminal');
    });

    it('should change view mode to chat', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.setChatView('chat');
      });

      expect(result.current.chatView).toBe('chat');
    });

    it('should change view mode to action-dialog', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.setChatView('action-dialog');
      });

      expect(result.current.chatView).toBe('action-dialog');
    });

    it('should change view mode to actions-list', () => {
      const { result } = renderHook(() => useChatStore());

      act(() => {
        result.current.setChatView('actions-list');
      });

      expect(result.current.chatView).toBe('actions-list');
    });
  });
});
