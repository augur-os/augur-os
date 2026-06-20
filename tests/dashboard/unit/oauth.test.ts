/**
 * @jest-environment node
 */
import {
  buildAuthorizationUrl,
  exchangeCodeGlama,
  exchangeCodeOpenRouter,
  generateCodeChallenge,
  generateCodeVerifier,
  generateState,
} from '@/lib/remote/oauth';

describe('oauth utilities', () => {
  const mockFetch = jest.fn();

  beforeAll(() => {
    (global as typeof globalThis & { fetch: typeof fetch }).fetch = mockFetch as unknown as typeof fetch;
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('generateCodeVerifier', () => {
    it('returns a verifier with requested length and allowed characters', () => {
      const verifier = generateCodeVerifier(64);
      expect(verifier).toHaveLength(64);
      expect(verifier).toMatch(/^[A-Za-z0-9\-._~]+$/);
    });
  });

  describe('generateCodeChallenge', () => {
    it('creates a base64url encoded SHA-256 challenge', async () => {
      const challenge = await generateCodeChallenge('test-verifier');
      expect(challenge).toBe('JBbiqONGWPaAmwXk_8bT6UnlPfrn65D32eZlJS-zGG0');
      expect(challenge).not.toContain('+');
      expect(challenge).not.toContain('/');
      expect(challenge).not.toContain('=');
    });
  });

  describe('generateState', () => {
    it('returns a 32-byte hex state', () => {
      const state = generateState();
      expect(state).toMatch(/^[a-f0-9]{64}$/);
      expect(state).toHaveLength(64);
    });
  });

  describe('buildAuthorizationUrl', () => {
    const baseParams = {
      codeChallenge: 'challenge',
      state: 'state123',
      callbackUrl: 'http://localhost:3000/callback',
    };

    it('builds glama URL with required params', () => {
      const url = new URL(buildAuthorizationUrl('glama', baseParams));
      expect(url.origin).toBe('https://glama.ai');
      expect(url.pathname).toBe('/oauth/authorize');
      expect(url.searchParams.get('callback_url')).toBe(baseParams.callbackUrl);
      expect(url.searchParams.get('code_challenge')).toBe(baseParams.codeChallenge);
      expect(url.searchParams.get('code_challenge_method')).toBe('S256');
      expect(url.searchParams.get('state')).toBe(baseParams.state);
    });

    it('builds openrouter URL with required params', () => {
      const url = new URL(buildAuthorizationUrl('openrouter', baseParams));
      expect(url.origin).toBe('https://openrouter.ai');
      expect(url.pathname).toBe('/auth');
      expect(url.searchParams.get('callback_url')).toBe(baseParams.callbackUrl);
      expect(url.searchParams.get('code_challenge')).toBe(baseParams.codeChallenge);
      expect(url.searchParams.get('code_challenge_method')).toBe('S256');
      expect(url.searchParams.get('state')).toBe(baseParams.state);
    });

    it('throws for unsupported providers', () => {
      expect(() =>
        buildAuthorizationUrl('unsupported' as unknown as 'glama', baseParams)
      ).toThrow('OAuth not supported for provider: unsupported');
    });
  });

  describe('exchangeCodeGlama', () => {
    it('returns api key on success', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ apiKey: 'glama-key-123' }),
      });

      const result = await exchangeCodeGlama('code123', 'verifier123');
      expect(result).toEqual({ apiKey: 'glama-key-123' });
      expect(mockFetch).toHaveBeenCalledWith(
        'https://glama.ai/api/gateway/v1/auth/exchange-code',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    it('returns upstream error message when response is not ok', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ error: { message: 'unauthorized' } }),
      });

      const result = await exchangeCodeGlama('bad', 'verifier');
      expect(result).toEqual({ error: 'unauthorized' });
    });

    it('returns HTTP status fallback when error body parsing fails', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('invalid json');
        },
      });

      const result = await exchangeCodeGlama('bad', 'verifier');
      expect(result).toEqual({ error: 'HTTP 500' });
    });

    it('returns error when success payload is missing api key', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({}),
      });

      const result = await exchangeCodeGlama('code', 'verifier');
      expect(result).toEqual({ error: 'No API key in response' });
    });

    it('returns network error message on fetch failure', async () => {
      mockFetch.mockRejectedValue(new Error('network down'));
      const result = await exchangeCodeGlama('code', 'verifier');
      expect(result).toEqual({ error: 'network down' });
    });
  });

  describe('exchangeCodeOpenRouter', () => {
    it('returns api key on success', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ key: 'openrouter-key-123' }),
      });

      const result = await exchangeCodeOpenRouter('code123', 'verifier123');
      expect(result).toEqual({ apiKey: 'openrouter-key-123' });
      expect(mockFetch).toHaveBeenCalledWith(
        'https://openrouter.ai/api/v1/auth/keys',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    it('returns HTTP status fallback when response is not ok and body parse fails', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => {
          throw new Error('broken body');
        },
      });

      const result = await exchangeCodeOpenRouter('bad', 'verifier');
      expect(result).toEqual({ error: 'HTTP 403' });
    });

    it('returns error when key is missing from success response', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ ok: true }),
      });

      const result = await exchangeCodeOpenRouter('code', 'verifier');
      expect(result).toEqual({ error: 'No API key in response' });
    });
  });
});
