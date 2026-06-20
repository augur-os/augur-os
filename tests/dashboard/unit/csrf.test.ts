/**
 * @jest-environment node
 */
import { cookies } from 'next/headers';

import {
  CSRF_COOKIE_NAME,
  generateCSRFToken,
  getCSRFToken,
  getCSRFTokenFromRequest,
  setCSRFToken,
  validateCSRFToken,
  validateCSRFTokenDirect,
  withCSRFProtection,
} from '@/lib/csrf';

jest.mock('next/headers', () => ({
  cookies: jest.fn(),
}));

jest.mock('nanoid', () => ({
  nanoid: jest.fn(() => 'x'.repeat(32)),
}));

describe('csrf utilities', () => {
  const mockCookies = cookies as unknown as jest.Mock;
  const cookieStore = {
    set: jest.fn(),
    get: jest.fn(),
  };
  const originalNodeEnv = process.env.NODE_ENV;

  beforeEach(() => {
    jest.clearAllMocks();
    cookieStore.set.mockReset();
    cookieStore.get.mockReset();
    mockCookies.mockResolvedValue(cookieStore);
  });

  afterAll(() => {
    if (originalNodeEnv === undefined) {
      delete process.env.NODE_ENV;
    } else {
      process.env.NODE_ENV = originalNodeEnv;
    }
  });

  it('generates token with expected length', () => {
    expect(generateCSRFToken()).toBe('x'.repeat(32));
  });

  it('sets csrf cookie and returns token', async () => {
    process.env.NODE_ENV = 'production';
    const token = await setCSRFToken();

    expect(token).toBe('x'.repeat(32));
    expect(cookieStore.set).toHaveBeenCalledWith(
      CSRF_COOKIE_NAME,
      token,
      expect.objectContaining({
        httpOnly: false,
        secure: true,
        sameSite: 'strict',
        path: '/',
      })
    );
  });

  it('reads csrf token from cookie store', async () => {
    cookieStore.get.mockReturnValue({ value: 'cookie-token' });
    await expect(getCSRFToken()).resolves.toBe('cookie-token');
  });

  it('extracts csrf token from header or query string', () => {
    const reqWithHeader = new Request('https://example.com/api', {
      headers: { 'x-csrf-token': 'header-token' },
    });
    expect(getCSRFTokenFromRequest(reqWithHeader)).toBe('header-token');

    const reqWithQuery = new Request('https://example.com/api?csrf_token=query-token');
    expect(getCSRFTokenFromRequest(reqWithQuery)).toBe('query-token');

    const reqWithoutToken = new Request('https://example.com/api');
    expect(getCSRFTokenFromRequest(reqWithoutToken)).toBeNull();
  });

  it('validates csrf token from cookie and header', async () => {
    cookieStore.get.mockReturnValue({ value: 'abc123' });
    const validReq = new Request('https://example.com/api', {
      method: 'POST',
      headers: { 'x-csrf-token': 'abc123' },
    });
    await expect(validateCSRFToken(validReq)).resolves.toBe(true);

    const invalidReq = new Request('https://example.com/api', {
      method: 'POST',
      headers: { 'x-csrf-token': 'different' },
    });
    await expect(validateCSRFToken(invalidReq)).resolves.toBe(false);

    cookieStore.get.mockReturnValue(undefined);
    await expect(validateCSRFToken(validReq)).resolves.toBe(false);
  });

  it('validates direct token comparison helper', () => {
    expect(validateCSRFTokenDirect('abc', 'abc')).toBe(true);
    expect(validateCSRFTokenDirect('abc', 'abd')).toBe(false);
    expect(validateCSRFTokenDirect(null, 'abc')).toBe(false);
    expect(validateCSRFTokenDirect('abc', undefined)).toBe(false);
  });

  it('withCSRFProtection blocks invalid state-changing requests and allows valid ones', async () => {
    const handler = jest.fn(async () => new Response('ok', { status: 200 }));
    const wrapped = withCSRFProtection(handler);

    cookieStore.get.mockReturnValue(undefined);
    const blockedResponse = await wrapped(new Request('https://example.com/api', { method: 'POST' }));
    expect(blockedResponse.status).toBe(403);
    expect(await blockedResponse.json()).toEqual({ error: 'Invalid CSRF token' });
    expect(handler).not.toHaveBeenCalled();

    cookieStore.get.mockReturnValue({ value: 'token-1' });
    const allowedResponse = await wrapped(
      new Request('https://example.com/api', {
        method: 'POST',
        headers: { 'x-csrf-token': 'token-1' },
      })
    );
    expect(allowedResponse.status).toBe(200);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('withCSRFProtection skips validation for safe methods', async () => {
    const handler = jest.fn(async () => new Response('ok'));
    const wrapped = withCSRFProtection(handler);

    const response = await wrapped(new Request('https://example.com/api', { method: 'GET' }));
    expect(response.status).toBe(200);
    expect(handler).toHaveBeenCalledTimes(1);
  });
});
