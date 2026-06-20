import { act, render, renderHook, waitFor } from '@testing-library/react';
import { ThemeInitializer, useTheme } from '@/hooks/useTheme';

const THEME_STORAGE_KEY = 'augur:theme:v2';
const MODE_STORAGE_KEY = 'augur:theme-mode:v1';

type MediaQueryListener = () => void;

describe('useTheme', () => {
  const originalFetch = global.fetch;
  const originalMatchMedia = window.matchMedia;
  let prefersLight = false;
  let mediaListeners: MediaQueryListener[] = [];
  let mockFetch: jest.Mock;

  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.removeAttribute('data-mode');
    jest.clearAllMocks();
    mediaListeners = [];
    prefersLight = false;

    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: jest.fn().mockImplementation((query: string) => {
        const isLightQuery = query.includes('light');
        const matches = isLightQuery ? prefersLight : !prefersLight;

        return {
          matches,
          media: query,
          onchange: null,
          addEventListener: (_event: string, listener: MediaQueryListener) => {
            mediaListeners.push(listener);
          },
          removeEventListener: (_event: string, listener: MediaQueryListener) => {
            mediaListeners = mediaListeners.filter((entry) => entry !== listener);
          },
          addListener: jest.fn(),
          removeListener: jest.fn(),
          dispatchEvent: jest.fn(),
        };
      }),
    });

    mockFetch = jest.fn().mockResolvedValue({
      ok: false,
      json: async () => ({}),
      text: async () => '',
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    jest.spyOn(console, 'warn').mockImplementation(() => {});
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
    global.fetch = originalFetch;
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: originalMatchMedia,
    });
  });

  it('uses defaults and applies system-dark theme on mount', async () => {
    const { result } = renderHook(() => useTheme());

    expect(result.current.theme).toBe('futuristic');
    expect(result.current.mode).toBe('system');
    expect(result.current.effectiveMode).toBe('dark');
    expect(result.current.loaded).toBe(true);

    await waitFor(() => {
      expect(document.documentElement.getAttribute('data-theme')).toBe('futuristic');
      expect(document.documentElement.getAttribute('data-mode')).toBe('dark');
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/mcp/tool', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ tool: 'get-preferences', args: {} }),
    }));
  });

  it('backfills theme and mode from backend when local storage is empty', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        ui_theme: 'office',
        ui_mode: 'light',
      }),
    });

    const { result } = renderHook(() => useTheme());

    await waitFor(() => {
      expect(result.current.theme).toBe('office');
      expect(result.current.mode).toBe('light');
    });

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('office');
    expect(localStorage.getItem(MODE_STORAGE_KEY)).toBe('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('office-light');
    expect(document.documentElement.getAttribute('data-mode')).toBe('light');
  });

  it('persists setTheme updates and posts ui_theme preference', async () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'futuristic');
    localStorage.setItem(MODE_STORAGE_KEY, 'dark');
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
      text: async () => '',
    });

    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setTheme('blossom');
    });

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('blossom');
    expect(document.documentElement.getAttribute('data-theme')).toBe('blossom');
    expect(document.documentElement.getAttribute('data-mode')).toBe('dark');

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/mcp/tool');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ tool: 'update-preference', args: { key: 'ui_theme', value: 'blossom' } });
  });

  it('persists setMode updates and posts ui_mode preference', async () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'office');
    localStorage.setItem(MODE_STORAGE_KEY, 'dark');
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
      text: async () => '',
    });

    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setMode('light');
    });

    expect(localStorage.getItem(MODE_STORAGE_KEY)).toBe('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('office-light');
    expect(document.documentElement.getAttribute('data-mode')).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/mcp/tool');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ tool: 'update-preference', args: { key: 'ui_mode', value: 'light' } });
  });

  it('updates state from storage events across tabs', async () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'futuristic');
    localStorage.setItem(MODE_STORAGE_KEY, 'dark');

    const { result } = renderHook(() => useTheme());

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: THEME_STORAGE_KEY,
          newValue: 'modern',
        })
      );
    });

    await waitFor(() => {
      expect(result.current.theme).toBe('modern');
      expect(document.documentElement.getAttribute('data-theme')).toBe('modern');
    });

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: MODE_STORAGE_KEY,
          newValue: 'light',
        })
      );
    });

    await waitFor(() => {
      expect(result.current.mode).toBe('light');
      expect(document.documentElement.getAttribute('data-theme')).toBe('modern-light');
      expect(document.documentElement.getAttribute('data-mode')).toBe('light');
    });
  });

  it('reapplies stored theme in ThemeInitializer after hydration', async () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'office');
    localStorage.setItem(MODE_STORAGE_KEY, 'system');
    prefersLight = false;

    render(<ThemeInitializer />);

    await waitFor(() => {
      expect(document.documentElement.getAttribute('data-theme')).toBe('office');
      expect(document.documentElement.getAttribute('data-mode')).toBe('dark');
      expect(document.documentElement.style.colorScheme).toBe('dark');
    });
  });

  it('responds to system mode media changes by re-applying theme', async () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'futuristic');
    localStorage.setItem(MODE_STORAGE_KEY, 'system');

    renderHook(() => useTheme());

    prefersLight = true;
    act(() => {
      mediaListeners.forEach((listener) => listener());
    });

    await waitFor(() => {
      expect(document.documentElement.getAttribute('data-theme')).toBe('futuristic-light');
      expect(document.documentElement.getAttribute('data-mode')).toBe('light');
    });
  });
});
