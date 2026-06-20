import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from '@/components/ErrorBoundary';

const emitClientErrorMock = jest.fn();

jest.mock('@/lib/self-heal-event', () => ({
  emitClientError: (...args: unknown[]) => emitClientErrorMock(...args),
}));

function ThrowingChild() {
  throw new Error('boundary explosion');
}

describe('ErrorBoundary', () => {
  const originalConsoleError = console.error;

  beforeEach(() => {
    emitClientErrorMock.mockReset();
    console.error = jest.fn();
  });

  afterEach(() => {
    console.error = originalConsoleError;
  });

  it('reports render crashes to the self-heal client-error pipeline', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(emitClientErrorMock).toHaveBeenCalledWith(
      expect.objectContaining({
        level: 'error',
        source: 'error-boundary',
        message: 'boundary explosion',
        component: expect.stringContaining('ThrowingChild'),
      }),
    );
  });
});
