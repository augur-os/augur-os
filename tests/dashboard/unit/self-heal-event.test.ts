import { emitHealEvent, emitClientError, type HealEvent } from '@/lib/self-heal-event';

describe('emitHealEvent', () => {
  const originalFetch = global.fetch;
  const baseEvent: HealEvent = {
    source: 'dashboard',
    category: 'test',
    severity: 'medium',
    message: 'test event',
  };

  afterEach(() => {
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  it('posts a heal event to the API route', () => {
    const fetchMock = jest.fn().mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = fetchMock as unknown as typeof fetch;

    emitHealEvent(baseEvent);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/mcp/tool',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      tool: 'set-config',
      args: {
        scope: 'self-heal-event',
        source: baseEvent.source,
        category: baseEvent.category,
        severity: baseEvent.severity,
        message: baseEvent.message,
      },
    });
  });

  it('does not throw when fetch throws synchronously', () => {
    global.fetch = jest.fn(() => {
      throw new Error('sync fetch failure');
    }) as unknown as typeof fetch;

    expect(() => emitHealEvent(baseEvent)).not.toThrow();
  });

  it('does not throw when fetch promise rejects', async () => {
    const fetchMock = jest.fn().mockRejectedValue(new Error('network failure'));
    global.fetch = fetchMock as unknown as typeof fetch;

    expect(() => emitHealEvent(baseEvent)).not.toThrow();
    await Promise.resolve();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('maps client errors into self-heal events', () => {
    const fetchMock = jest.fn().mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = fetchMock as unknown as typeof fetch;

    emitClientError({
      level: 'error',
      message: 'Cannot read properties of undefined',
      source: 'error-boundary',
      url: '/command/self-heal',
      stack: 'TypeError: boom',
      component: 'StatsHero',
      fingerprint: 'eb-123',
      count: 2,
      timestamp: '2026-03-22T19:00:00.000Z',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/mcp/tool',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      tool: 'set-config',
      args: {
        scope: 'self-heal-event',
        source: 'error-boundary',
        category: 'client-error',
        severity: 'high',
        message: 'Cannot read properties of undefined',
        context: {
          level: 'error',
          url: '/command/self-heal',
          stack: 'TypeError: boom',
          component: 'StatsHero',
          timestamp: '2026-03-22T19:00:00.000Z',
          fingerprint: 'eb-123',
          count: 2,
        },
      },
    });
  });
});
