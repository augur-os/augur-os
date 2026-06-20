/**
 * @jest-environment node
 */
/**
 * Tests for MCPContextClient (ADR-254)
 *
 * Validates singleton pattern, context switching, and state tracking.
 * Focus-specific methods (broadcastFocusState, focusContext, FocusPayload)
 * were removed as part of ADR-254 Phase 3.
 */

// Mock global fetch before importing MCPContextClient
const mockFetch = jest.fn();
global.fetch = mockFetch as unknown as typeof fetch;

// Mock window to avoid SSR guard returning dummy instance
Object.defineProperty(global, 'window', {
  value: {},
  writable: true,
});

import { MCPContextClient } from '@/lib/mcp/MCPContextClient';

// Reset singleton between tests
function resetSingleton() {
  (MCPContextClient as any).instance = null;
}

beforeEach(() => {
  jest.clearAllMocks();
  resetSingleton();
  mockFetch.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
});

describe('MCPContextClient', () => {
  // =========================================================================
  // Singleton
  // =========================================================================

  describe('singleton pattern', () => {
    it('returns the same instance on multiple calls', () => {
      const a = MCPContextClient.getInstance();
      const b = MCPContextClient.getInstance();
      expect(a).toBe(b);
    });
  });

  // =========================================================================
  // State tracking
  // =========================================================================

  describe('state tracking', () => {
    it('getCurrentPage returns initial "/"', () => {
      const client = MCPContextClient.getInstance();
      expect(client.getCurrentPage()).toBe('/');
    });

    it('isContextSwitching returns false initially', () => {
      const client = MCPContextClient.getInstance();
      expect(client.isContextSwitching()).toBe(false);
    });
  });
});
