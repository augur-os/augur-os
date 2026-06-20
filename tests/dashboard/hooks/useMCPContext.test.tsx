/**
 * Tests for useMCPContext hook (ADR-254)
 *
 * Validates that:
 * - All pages use switchContext for unified context switching
 * - MCP config page is skipped entirely
 * - Dedup prevents re-trigger on same pathname
 * - handleLinkHover triggers preload
 */

import { renderHook, act, waitFor } from '@testing-library/react';

// Mock next/navigation — return value controlled by mockPathname
let currentPathname = '/';
jest.mock('next/navigation', () => ({
  usePathname: () => currentPathname,
}));

// Mock MCPContextClient
const mockSwitchContext = jest.fn().mockResolvedValue(undefined);
const mockGetCurrentPage = jest.fn().mockReturnValue('/');
const mockIsContextSwitching = jest.fn().mockReturnValue(false);
const mockPreloadContext = jest.fn().mockResolvedValue(undefined);

jest.mock('@/lib/mcp/MCPContextClient', () => ({
  getMCPContextClient: () => ({
    switchContext: mockSwitchContext,
    getCurrentPage: mockGetCurrentPage,
    isContextSwitching: mockIsContextSwitching,
    preloadContext: mockPreloadContext,
  }),
}));

import { useMCPContext } from '@/hooks/useMCPContext';

beforeEach(() => {
  jest.clearAllMocks();
  currentPathname = '/';
  mockGetCurrentPage.mockReturnValue('/');
  mockIsContextSwitching.mockReturnValue(false);
});

describe('useMCPContext', () => {
  // =========================================================================
  // All pages use switchContext
  // =========================================================================

  describe('page navigation', () => {
    const pages = ['/settings', '/browse', '/workspace', '/workspace/memory'];

    test.each(pages)('uses switchContext for %s', async (page) => {
      currentPathname = '/';
      mockGetCurrentPage.mockReturnValue('/');

      const { rerender } = renderHook(() => useMCPContext());

      currentPathname = page;
      mockGetCurrentPage.mockReturnValue('/');
      rerender();

      await waitFor(() => {
        expect(mockSwitchContext).toHaveBeenCalledWith(page);
      });
    });
  });

  // =========================================================================
  // MCP config page — skip entirely
  // =========================================================================

  describe('MCP config page', () => {
    it('skips context switching for /hands/mcp-config', async () => {
      currentPathname = '/';
      mockGetCurrentPage.mockReturnValue('/');

      const { rerender } = renderHook(() => useMCPContext());

      currentPathname = '/hands/mcp-config';
      rerender();

      await new Promise((r) => setTimeout(r, 50));
      expect(mockSwitchContext).not.toHaveBeenCalled();
    });
  });

  // =========================================================================
  // Dedup — same page, no re-trigger
  // =========================================================================

  describe('deduplication', () => {
    it('does not re-trigger when pathname has not changed', async () => {
      currentPathname = '/workspace';
      mockGetCurrentPage.mockReturnValue('/workspace');

      renderHook(() => useMCPContext());

      await new Promise((r) => setTimeout(r, 50));
      expect(mockSwitchContext).not.toHaveBeenCalled();
    });
  });

  describe('focus state broadcast', () => {
    let visibilityState = 'visible';

    beforeEach(() => {
      jest.useFakeTimers();
      global.fetch = jest.fn().mockResolvedValue({ ok: true });
      visibilityState = 'visible';
      Object.defineProperty(document, 'visibilityState', {
        configurable: true,
        get: () => visibilityState,
      });
    });

    afterEach(() => {
      jest.useRealTimers();
      jest.restoreAllMocks();
    });

    it('uses sendBeacon so navigation does not abort focus-state updates', async () => {
      const sendBeacon = jest.fn(() => true);
      Object.defineProperty(navigator, 'sendBeacon', {
        configurable: true,
        value: sendBeacon,
      });

      currentPathname = '/';
      mockGetCurrentPage.mockReturnValue('/');

      const { rerender } = renderHook(() => useMCPContext());

      currentPathname = '/workspace/memory';
      mockGetCurrentPage.mockReturnValue('/');
      rerender();

      await waitFor(() => {
        expect(mockSwitchContext).toHaveBeenCalledWith('/workspace/memory');
      });

      act(() => {
        jest.advanceTimersByTime(2000);
      });

      await waitFor(() => {
        expect(sendBeacon).toHaveBeenCalledWith('/api/focus-state', expect.any(Blob));
      });
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('skips the focus-state broadcast if the tab becomes hidden before debounce fires', async () => {
      const sendBeacon = jest.fn(() => true);
      Object.defineProperty(navigator, 'sendBeacon', {
        configurable: true,
        value: sendBeacon,
      });

      currentPathname = '/';
      mockGetCurrentPage.mockReturnValue('/');

      const { rerender } = renderHook(() => useMCPContext());

      currentPathname = '/workspace/inbox';
      mockGetCurrentPage.mockReturnValue('/');
      rerender();

      await waitFor(() => {
        expect(mockSwitchContext).toHaveBeenCalledWith('/workspace/inbox');
      });

      visibilityState = 'hidden';

      act(() => {
        jest.advanceTimersByTime(2000);
      });

      expect(sendBeacon).not.toHaveBeenCalled();
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('falls back to keepalive fetch when sendBeacon is unavailable', async () => {
      Object.defineProperty(navigator, 'sendBeacon', {
        configurable: true,
        value: undefined,
      });

      currentPathname = '/';
      mockGetCurrentPage.mockReturnValue('/');

      const { rerender } = renderHook(() => useMCPContext());

      currentPathname = '/workspace/memory';
      mockGetCurrentPage.mockReturnValue('/');
      rerender();

      await waitFor(() => {
        expect(mockSwitchContext).toHaveBeenCalledWith('/workspace/memory');
      });

      act(() => {
        jest.advanceTimersByTime(2000);
      });

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/focus-state',
          expect.objectContaining({ keepalive: true }),
        );
      });
    });

    it('cancels the previous focus-state timer before a slow context switch', async () => {
      const sendBeacon = jest.fn(() => true);
      Object.defineProperty(navigator, 'sendBeacon', {
        configurable: true,
        value: sendBeacon,
      });

      currentPathname = '/';
      mockGetCurrentPage.mockReturnValue('/');

      const { rerender } = renderHook(() => useMCPContext());

      currentPathname = '/workspace';
      mockGetCurrentPage.mockReturnValue('/');
      rerender();

      await waitFor(() => {
        expect(mockSwitchContext).toHaveBeenCalledWith('/workspace');
      });

      act(() => {
        jest.advanceTimersByTime(500);
      });

      let resolveSlowSwitch!: () => void;
      mockSwitchContext.mockImplementationOnce(
        () => new Promise<void>((resolve) => {
          resolveSlowSwitch = resolve;
        }),
      );

      currentPathname = '/workspace/memory';
      mockGetCurrentPage.mockReturnValue('/workspace');
      rerender();

      act(() => {
        jest.advanceTimersByTime(2500);
      });

      expect(sendBeacon).not.toHaveBeenCalled();

      await act(async () => {
        resolveSlowSwitch();
        await Promise.resolve();
      });

      act(() => {
        jest.advanceTimersByTime(2000);
      });

      await waitFor(() => {
        expect(sendBeacon).toHaveBeenCalledTimes(1);
      });
    });
  });

  // =========================================================================
  // handleLinkHover — preload
  // =========================================================================

  describe('handleLinkHover', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('preloads context on hover after debounce', async () => {
      currentPathname = '/';
      mockGetCurrentPage.mockReturnValue('/');

      const { result } = renderHook(() => useMCPContext());

      act(() => {
        result.current.handleLinkHover('/workspace');
      });

      // Should not fire immediately (debounced by 400ms)
      expect(mockPreloadContext).not.toHaveBeenCalled();

      // Advance past the debounce delay
      act(() => {
        jest.advanceTimersByTime(400);
      });

      await waitFor(() => {
        expect(mockPreloadContext).toHaveBeenCalledWith('/workspace');
      });
    });

    it('does not preload current page', () => {
      currentPathname = '/workspace';
      mockGetCurrentPage.mockReturnValue('/workspace');

      const { result } = renderHook(() => useMCPContext());

      act(() => {
        result.current.handleLinkHover('/workspace');
      });

      act(() => {
        jest.advanceTimersByTime(400);
      });

      expect(mockPreloadContext).not.toHaveBeenCalled();
    });

    it('does not preload during context switch', () => {
      currentPathname = '/';
      mockGetCurrentPage.mockReturnValue('/');
      mockIsContextSwitching.mockReturnValue(true);

      const { result } = renderHook(() => useMCPContext());

      act(() => {
        result.current.handleLinkHover('/workspace');
      });

      act(() => {
        jest.advanceTimersByTime(400);
      });

      expect(mockPreloadContext).not.toHaveBeenCalled();
    });

    it('deduplicates preloads for the same page', async () => {
      currentPathname = '/';
      mockGetCurrentPage.mockReturnValue('/');

      const { result } = renderHook(() => useMCPContext());

      act(() => {
        result.current.handleLinkHover('/workspace');
      });

      act(() => {
        jest.advanceTimersByTime(400);
      });

      await waitFor(() => {
        expect(mockPreloadContext).toHaveBeenCalledTimes(1);
      });

      // Second hover on same page should not re-trigger
      act(() => {
        result.current.handleLinkHover('/workspace');
      });

      act(() => {
        jest.advanceTimersByTime(400);
      });

      expect(mockPreloadContext).toHaveBeenCalledTimes(1);
    });
  });
});
