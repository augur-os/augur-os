import { act, renderHook, waitFor } from '@testing-library/react';

jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

import { useIdeBridge } from '@/features/hooks/useIdeBridge';

describe('useIdeBridge', () => {
  const originalFetch = global.fetch;
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        success: true,
        active_ide: 'Codex',
        available_ides: ['Codex'],
      }),
      text: async () => '',
    });
    global.fetch = mockFetch as unknown as typeof fetch;
  });

  afterEach(() => {
    jest.useRealTimers();
    global.fetch = originalFetch;
  });

  it('does not poll IDE status by default', () => {
    renderHook(() => useIdeBridge());

    act(() => {
      jest.advanceTimersByTime(60000);
    });

    expect(mockFetch).not.toHaveBeenCalledWith('/api/ide/status', expect.anything());
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('polls IDE status only when explicitly enabled', async () => {
    renderHook(() => useIdeBridge({ pollStatus: true, pollIntervalMs: 1000 }));

    await act(async () => {
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      jest.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(3);
    });
    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      '/api/ide/status',
      expect.objectContaining({ cache: 'no-store' }),
    );
  });
});
