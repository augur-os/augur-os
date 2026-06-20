import { act, renderHook } from '@testing-library/react';

let mockPathname = '/';

jest.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
}));

jest.mock('@/lib/chat/context-envelope', () => ({
  resolveContext: jest.fn(() => ({})),
}));

jest.mock('@/lib/stores/airplaneModeStore', () => ({
  useAirplaneModeStore: () => ({
    airplaneMode: false,
    airplaneModeReady: true,
    airplaneBackendReady: false,
    airplaneModeError: null,
  }),
}));

const setSelectedCli = jest.fn();
const setCliProcess = jest.fn();
const clearAttachedFiles = jest.fn();
let mockChatStoreState = {
  selectedCli: 'claude',
  cliProcess: null as { cliId: string; status: 'running' | 'waiting' | 'error' | 'exited'; pid?: number } | null,
  attachedFiles: [] as Array<{ stagedPath: string; originalName: string; size: number }>,
  sessionId: null as string | null,
};

jest.mock('@/lib/stores/chatStore', () => ({
  useChatStore: () => ({
    ...mockChatStoreState,
    setSelectedCli,
    setCliProcess,
    addAttachedFile: jest.fn(),
    removeAttachedFile: jest.fn(),
    clearAttachedFiles,
  }),
}));

import { useCliChat } from '@/features/hooks/useCliChat';

describe('useCliChat', () => {
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  beforeEach(() => {
    jest.clearAllMocks();
    mockPathname = '/';
    mockChatStoreState = {
      selectedCli: 'claude',
      cliProcess: null,
      attachedFiles: [],
      sessionId: null,
    };
    localStorage.clear();
    console.error = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  it('ignores aborted CLI config requests during cleanup', async () => {
    global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (input !== '/api/cli/configs') {
        return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
      }

      return new Promise((resolve, reject) => {
        const signal = init?.signal;
        if (signal) {
          signal.addEventListener(
            'abort',
            () => reject(new TypeError('Failed to fetch')),
            { once: true },
          );
        }

        setTimeout(() => {
          if (!signal?.aborted) {
            resolve({
              headers: new Headers({ 'content-type': 'application/json' }),
              json: async () => ({
                configs: [],
                default_cli: 'codex',
              }),
            } as Response);
          }
        }, 100);
      });
    }) as unknown as typeof fetch;

    const { unmount } = renderHook(() => useCliChat());

    await act(async () => {
      unmount();
      await Promise.resolve();
    });

    expect(console.error).not.toHaveBeenCalledWith(
      'Failed to fetch CLI configs:',
      expect.anything(),
    );
  });

  it('does not abort CLI config requests during cleanup', async () => {
    const observedSignals: AbortSignal[] = [];

    global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (input !== '/api/cli/configs') {
        return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
      }

      if (init?.signal) {
        observedSignals.push(init.signal);
      }

      return Promise.resolve({
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          configs: [],
          default_cli: 'codex',
        }),
      } as Response);
    }) as unknown as typeof fetch;

    const { unmount } = renderHook(() => useCliChat());

    await act(async () => {
      unmount();
      await Promise.resolve();
    });

    expect(observedSignals).toHaveLength(0);
  });

  it('does not send current_page for normal CLI starts without explicit autoContext', async () => {
    mockPathname = '/browse';
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      if (input === '/api/cli/configs') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ configs: [], default_cli: 'claude' }),
        } as Response);
      }
      if (input === '/api/cli') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ pid: 12345 }),
        } as Response);
      }
      if (input === '/api/chat/session') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({}),
        } as Response);
      }

      return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useCliChat());

    let started: boolean | undefined;
    await act(async () => {
      started = await result.current.startCli('claude');
    });

    expect(started).toBe(true);
    const cliStartCall = (global.fetch as jest.Mock).mock.calls.find(
      ([input]) => input === '/api/cli',
    );
    expect(JSON.parse(cliStartCall[1].body)).toEqual(
      expect.not.objectContaining({ current_page: '/browse' }),
    );

    const chatSessionCall = (global.fetch as jest.Mock).mock.calls.find(
      ([input]) => input === '/api/chat/session',
    );
    expect(JSON.parse(chatSessionCall[1].body).context).toEqual({
      cliId: 'claude',
      pid: 12345,
    });
  });

  it('sends current_page only when startup autoContext is explicitly enabled', async () => {
    mockPathname = '/browse';
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      if (input === '/api/cli/configs') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ configs: [], default_cli: 'claude' }),
        } as Response);
      }
      if (input === '/api/cli') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ pid: 12345 }),
        } as Response);
      }
      if (input === '/api/chat/session') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({}),
        } as Response);
      }

      return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useCliChat());

    let started: boolean | undefined;
    await act(async () => {
      started = await result.current.startCli('claude', { autoContext: true });
    });

    expect(started).toBe(true);
    const cliStartCall = (global.fetch as jest.Mock).mock.calls.find(
      ([input]) => input === '/api/cli',
    );
    expect(JSON.parse(cliStartCall[1].body)).toEqual(
      expect.objectContaining({
        current_page: '/browse',
        autoContext: true,
      }),
    );

    const chatSessionCall = (global.fetch as jest.Mock).mock.calls.find(
      ([input]) => input === '/api/chat/session',
    );
    expect(JSON.parse(chatSessionCall[1].body).context).toEqual({
      current_page: '/browse',
      cliId: 'claude',
      pid: 12345,
    });
  });

  it('exposes session ownership conflicts from CLI start failures', async () => {
    mockPathname = '/browse';
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      if (input === '/api/cli/configs') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ configs: [], default_cli: 'claude' }),
        } as Response);
      }
      if (input === '/api/cli') {
        return Promise.resolve({
          ok: false,
          status: 409,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            code: 'SESSION_OWNED_ELSEWHERE',
            error: 'Session is already open in native terminal.',
            sessionId: 'session-123',
            owner: {
              surface: 'native-terminal',
              pid: 9999,
              host: 'other-host',
              cli_id: 'claude',
            },
          }),
        } as Response);
      }

      return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useCliChat());

    let started: boolean | undefined;
    await act(async () => {
      started = await result.current.startCli('claude');
    });

    expect(started).toBe(false);
    expect(result.current.sessionConflict).toEqual({
      sessionId: 'session-123',
      owner: {
        surface: 'native-terminal',
        pid: 9999,
        host: 'other-host',
        cli_id: 'claude',
      },
    });
    expect(result.current.messages.at(-1)?.content).toContain(
      'Session is already open in native terminal.',
    );

    act(() => {
      result.current.clearSessionConflict();
    });

    expect(result.current.sessionConflict).toBeNull();
  });

  it('can take over a conflicting session by restarting with an explicit ownership transfer request', async () => {
    mockPathname = '/browse';
    let cliStartCount = 0;
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      if (input === '/api/cli/configs') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ configs: [], default_cli: 'claude' }),
        } as Response);
      }
      if (input === '/api/cli') {
        cliStartCount += 1;
        if (cliStartCount === 1) {
          return Promise.resolve({
            ok: false,
            status: 409,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({
              code: 'SESSION_OWNED_ELSEWHERE',
              error: 'Session is already open in native terminal.',
              sessionId: 'session-123',
              owner: {
                surface: 'native-terminal',
                pid: 9999,
                host: 'other-host',
                cli_id: 'claude',
              },
            }),
          } as Response);
        }
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ pid: 12345 }),
        } as Response);
      }
      if (input === '/api/chat/session') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({}),
        } as Response);
      }

      return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useCliChat());

    let firstStart: boolean | undefined;
    await act(async () => {
      firstStart = await result.current.startCli('claude');
    });
    await act(async () => {
      await result.current.takeOverSessionConflict();
    });

    expect(firstStart).toBe(false);
    const cliBodies = (global.fetch as jest.Mock).mock.calls
      .filter(([input]) => input === '/api/cli')
      .map(([, init]) => JSON.parse(init.body));
    expect(cliBodies).toHaveLength(2);
    expect(cliBodies[1]).toEqual(
      expect.objectContaining({
        action: 'start',
        cliId: 'claude',
        takeOverSessionOwner: true,
      }),
    );
    expect(result.current.sessionConflict).toBeNull();
  });

  it('returns false when CLI startup throws after preserving error state', async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      if (input === '/api/cli/configs') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ configs: [], default_cli: 'claude' }),
        } as Response);
      }
      if (input === '/api/cli') {
        return Promise.reject(new Error('network down'));
      }

      return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useCliChat());

    let started: boolean | undefined;
    await act(async () => {
      started = await result.current.startCli('claude');
    });

    expect(started).toBe(false);
    expect(setCliProcess).toHaveBeenLastCalledWith({
      cliId: 'claude',
      status: 'error',
    });
  });

  it('returns true when sendMessage sends to a running CLI', async () => {
    mockChatStoreState = {
      ...mockChatStoreState,
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
    };
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      if (input === '/api/cli/configs') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ configs: [], default_cli: 'claude' }),
        } as Response);
      }
      if (input === '/api/cli') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({}),
        } as Response);
      }

      return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useCliChat());

    let sent: boolean | undefined;
    await act(async () => {
      sent = await result.current.sendMessage('hello');
    });

    expect(sent).toBe(true);
    expect(clearAttachedFiles).toHaveBeenCalled();
  });

  it('returns false when sendMessage has no running CLI', async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      if (input === '/api/cli/configs') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ configs: [], default_cli: 'claude' }),
        } as Response);
      }

      return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useCliChat());

    let sent: boolean | undefined;
    await act(async () => {
      sent = await result.current.sendMessage('hello');
    });

    expect(sent).toBe(false);
    expect(result.current.messages.at(-1)?.content).toBe(
      'No CLI running. Select a CLI and start it first.',
    );
  });

  it('returns false when sendMessage receives a non-OK response', async () => {
    mockChatStoreState = {
      ...mockChatStoreState,
      cliProcess: { cliId: 'claude', status: 'running', pid: 12345 },
    };
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      if (input === '/api/cli/configs') {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ configs: [], default_cli: 'claude' }),
        } as Response);
      }
      if (input === '/api/cli') {
        return Promise.resolve({
          ok: false,
          status: 400,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ error: 'send failed' }),
        } as Response);
      }

      return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useCliChat());

    let sent: boolean | undefined;
    await act(async () => {
      sent = await result.current.sendMessage('hello');
    });

    expect(sent).toBe(false);
    expect(result.current.messages.at(-1)?.content).toBe('Send failed: send failed');
  });
});
