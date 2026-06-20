import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement } from 'react';

/**
 * Create a QueryClient and wrapper for component tests.
 * Usage:
 *   const { queryClient, Wrapper } = createQueryWrapper();
 *   afterEach(() => { queryClient.clear(); });
 *   render(<Component />, { wrapper: Wrapper });
 */
export function createQueryWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return { queryClient, Wrapper };
}

/**
 * Render a component wrapped in a fresh QueryClientProvider.
 * Drop-in replacement for render() in tests that use React Query hooks.
 */
export function renderWithQuery(ui: ReactElement, options?: RenderOptions) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
    options,
  );
}
