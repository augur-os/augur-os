/**
 * Global override for @testing-library/react `render`.
 *
 * Many dashboard components call React Query hooks (useMcpQuery / useMcpPoll,
 * which wrap @tanstack/react-query's useQuery/useQueryClient). Without a
 * QueryClientProvider those hooks throw "No QueryClient set". This module
 * re-exports the real library but wraps every render() in a fresh
 * QueryClientProvider so component tests don't each have to do it. Tests that
 * pass their own `wrapper` are still honored (composed inside the provider).
 *
 * Mapped over `@testing-library/react` via jest.config.js moduleNameMapper.
 */
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Load the real implementation via its package main sub-path so the
// exact-match `^@testing-library/react$` moduleNameMapper entry does not
// redirect this require back to this mock (which would recurse).
const actual = jest.requireActual<typeof import("@testing-library/react")>(
  "@testing-library/react/dist/index.js",
);

type RenderUi = Parameters<typeof actual.render>[0];
type RenderOptions = Parameters<typeof actual.render>[1];

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function render(ui: RenderUi, options?: RenderOptions) {
  const client = createQueryClient();
  const UserWrapper = options?.wrapper;

  const Wrapper = ({ children }: { children?: React.ReactNode }) => (
    <QueryClientProvider client={client}>
      {UserWrapper ? <UserWrapper>{children}</UserWrapper> : children}
    </QueryClientProvider>
  );

  return actual.render(ui, { ...options, wrapper: Wrapper });
}

module.exports = {
  ...actual,
  render,
};
