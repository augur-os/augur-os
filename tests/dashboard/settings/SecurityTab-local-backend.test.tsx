import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import LocalBackendSection from '@/app/settings/components/LocalBackendSection';

jest.mock('next/navigation', () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => '/settings/security',
  useSearchParams: () => ({ get: jest.fn() }),
}));

const mockStatusRefetch = jest.fn();
const mockUseMcpQuery = jest.fn();
const mockMcpCall = jest.fn();
const mockToggleAirplaneMode = jest.fn();

jest.mock('@/lib/mcp/useMcpQuery', () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

jest.mock('@/lib/mcp/client', () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

jest.mock('@/lib/stores/airplaneModeStore', () => ({
  useAirplaneModeStore: () => ({
    airplaneMode: false,
    airplaneModeReady: true,
    airplaneModeError: null,
    toggleAirplaneMode: mockToggleAirplaneMode,
  }),
}));

jest.mock('@/hooks/useActionRunner', () => ({
  useActionRunner: () => ({
    runAction: jest.fn(),
    isExecuting: false,
  }),
}));

const readyStatus = {
  ollama: {
    installed: true,
    version: '0.6.2',
    binary: '/opt/homebrew/bin/ollama',
    server_running: true,
    ready: true,
    models: [
      { name: 'qwen3.5:9b', size: '5.5 GB' },
      { name: 'llama3.2:3b', size: '2.0 GB' },
    ],
    configured_model: 'qwen3.5:9b',
    has_configured_model: true,
  },
};

function renderLocalBackendSection({
  status = readyStatus,
  integrations = ['claude', 'codex', 'copilot'],
}: {
  status?: Record<string, unknown>;
  integrations?: string[];
} = {}) {
  mockUseMcpQuery.mockImplementation((key: string | string[]) => {
    const queryKey = Array.isArray(key) ? key[0] : key;
    if (queryKey === 'airplane-status') {
      return { data: status, loading: false, error: null, refetch: mockStatusRefetch };
    }
    if (queryKey === 'ollama-integrations') {
      return {
        data: { integrations },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    }
    return {
      data: {
        security: {
          requireExplicitConsent: true,
          warnOnPii: true,
          blockOnSecrets: true,
          sensitiveFolders: [],
        },
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    };
  });

  return render(<LocalBackendSection />);
}

describe('SecurityTab Local Backend section', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockMcpCall.mockImplementation((tool: string) => {
      if (tool === 'query-audit-log') return Promise.resolve({ ok: true, logs: [] });
      if (tool === 'get-security-report') return Promise.resolve({ status: 'no_report' });
      return Promise.resolve({});
    });
  });

  it('shows detected Ollama binary and populates the local model dropdown', async () => {
    renderLocalBackendSection();

    expect(await screen.findByText('Local Backend')).toBeInTheDocument();
    expect(await screen.findByText('/opt/homebrew/bin/ollama')).toBeInTheDocument();

    const modelSelect = screen.getByLabelText('Local model') as HTMLSelectElement;
    await waitFor(() => {
      expect(modelSelect.value).toBe('qwen3.5:9b');
    });
    expect(screen.getByRole('option', { name: 'qwen3.5:9b' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'llama3.2:3b' })).toBeInTheDocument();
  });

  it('keeps a configured model visible when it is not installed locally', async () => {
    renderLocalBackendSection({
      status: {
        ollama: {
          installed: true,
          version: '0.6.2',
          binary: '/opt/homebrew/bin/ollama',
          server_running: true,
          ready: true,
          models: [{ name: 'qwen3.5:latest', size: '5.5 GB' }],
          configured_model: 'qwen3.5:9b',
          has_configured_model: false,
        },
      },
    });

    const modelSelect = await screen.findByLabelText('Local model') as HTMLSelectElement;
    await waitFor(() => {
      expect(modelSelect.value).toBe('qwen3.5:9b');
    });
    expect(
      screen.getByRole('option', {
        name: 'qwen3.5:9b (configured, missing)',
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'qwen3.5:latest' })).toBeInTheDocument();
  });

  it('changing the local model dispatches update-preference and refetches status', async () => {
    renderLocalBackendSection();

    const modelSelect = await screen.findByLabelText('Local model');
    await screen.findByRole('option', { name: 'llama3.2:3b' });

    fireEvent.change(modelSelect, {
      target: { value: 'llama3.2:3b' },
    });

    await waitFor(() => {
      expect(mockMcpCall).toHaveBeenCalledWith('update-preference', {
        key: 'local_backends.ollama.model',
        value: 'llama3.2:3b',
      });
    });
    expect(mockStatusRefetch).toHaveBeenCalled();
  });

  it('surfaces failed local model preference writes without refetching status', async () => {
    mockMcpCall.mockImplementation((tool: string) => {
      if (tool === 'update-preference') {
        return Promise.resolve({
          success: false,
          error: 'preferences.yaml is unwritable',
        });
      }
      if (tool === 'query-audit-log') return Promise.resolve({ ok: true, logs: [] });
      if (tool === 'get-security-report') return Promise.resolve({ status: 'no_report' });
      return Promise.resolve({});
    });
    renderLocalBackendSection();

    const modelSelect = await screen.findByLabelText('Local model') as HTMLSelectElement;
    fireEvent.change(modelSelect, {
      target: { value: 'llama3.2:3b' },
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'preferences.yaml is unwritable',
    );
    expect(mockStatusRefetch).not.toHaveBeenCalled();
    expect(modelSelect.value).toBe('qwen3.5:9b');
  });

  it('test connection reports a ready local backend', async () => {
    mockMcpCall.mockImplementation((tool: string) => {
      if (tool === 'get-local-backend-status') return Promise.resolve(readyStatus);
      if (tool === 'query-audit-log') return Promise.resolve({ ok: true, logs: [] });
      if (tool === 'get-security-report') return Promise.resolve({ status: 'no_report' });
      return Promise.resolve({});
    });
    renderLocalBackendSection();

    fireEvent.click(await screen.findByRole('button', { name: 'Test connection' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Ready');
  });

  it('test connection reports not-ready and error states clearly', async () => {
    mockMcpCall.mockImplementation((tool: string) => {
      if (tool === 'get-local-backend-status') {
        return Promise.resolve({
          ollama: {
            installed: true,
            binary: '/opt/homebrew/bin/ollama',
            server_running: false,
            ready: false,
            models: [],
            configured_model: 'qwen3.5:9b',
          },
        });
      }
      if (tool === 'query-audit-log') return Promise.resolve({ ok: true, logs: [] });
      if (tool === 'get-security-report') return Promise.resolve({ status: 'no_report' });
      return Promise.resolve({});
    });
    const { unmount } = renderLocalBackendSection();

    fireEvent.click(await screen.findByRole('button', { name: 'Test connection' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Not ready');

    unmount();
    jest.clearAllMocks();
    mockMcpCall.mockImplementation((tool: string) => {
      if (tool === 'get-local-backend-status') {
        return Promise.reject(new Error('Ollama status timed out'));
      }
      if (tool === 'query-audit-log') return Promise.resolve({ ok: true, logs: [] });
      if (tool === 'get-security-report') return Promise.resolve({ status: 'no_report' });
      return Promise.resolve({});
    });
    renderLocalBackendSection();

    fireEvent.click(await screen.findByRole('button', { name: 'Test connection' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Ollama status timed out');
  });

  it('test connection reports not-ready when Ollama is running but configured model is missing', async () => {
    mockMcpCall.mockImplementation((tool: string) => {
      if (tool === 'get-local-backend-status') {
        return Promise.resolve({
          ollama: {
            installed: true,
            binary: '/opt/homebrew/bin/ollama',
            server_running: true,
            ready: true,
            models: [{ name: 'llama3.2:3b', size: '2.0 GB' }],
            configured_model: 'qwen3.5:9b',
            has_configured_model: false,
          },
        });
      }
      if (tool === 'query-audit-log') return Promise.resolve({ ok: true, logs: [] });
      if (tool === 'get-security-report') return Promise.resolve({ status: 'no_report' });
      return Promise.resolve({});
    });
    renderLocalBackendSection();

    fireEvent.click(await screen.findByRole('button', { name: 'Test connection' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Not ready');
    expect(screen.getByRole('status')).toHaveTextContent(
      'The configured model is not installed locally.',
    );
  });

  it('shows supported integrations and explicit unsupported agents', async () => {
    renderLocalBackendSection({ integrations: ['claude', 'codex', 'copilot'] });

    expect(await screen.findByText('Agent compatibility')).toBeInTheDocument();
    expect(screen.getByText('claude')).toBeInTheDocument();
    expect(screen.getByText('codex')).toBeInTheDocument();
    expect(screen.getByText('copilot-cli')).toBeInTheDocument();
    // copilot is surfaced under its display id (copilot-cli) with the source
    // integration shown as "via copilot".
    expect(screen.getByText('via copilot')).toBeInTheDocument();
    expect(screen.getByText('gemini')).toBeInTheDocument();
    expect(screen.getByText('cursor-cli')).toBeInTheDocument();
    expect(screen.getAllByText('Not supported')).toHaveLength(2);
    expect(screen.getAllByText(/Ollama launch does not support this agent yet/i)).toHaveLength(2);
  });
});
