import { render } from '@testing-library/react';
import ClientErrorReporter from '@/components/ClientErrorReporter';

const emitClientErrorMock = jest.fn();

jest.mock('@/lib/self-heal-event', () => ({
  emitClientError: (...args: unknown[]) => emitClientErrorMock(...args),
}));

describe('ClientErrorReporter', () => {
  const originalConsoleError = console.error;

  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    console.error = originalConsoleError;
  });

  it('forwards console errors into the self-heal client-error pipeline', () => {
    render(<ClientErrorReporter />);

    const err = new Error('client render failed');
    console.error(err);

    jest.advanceTimersByTime(5000);

    expect(emitClientErrorMock).toHaveBeenCalledWith(
      expect.objectContaining({
        level: 'error',
        source: 'console.error',
        message: expect.stringContaining('client render failed'),
        url: '/',
      }),
    );
  });
});
