import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockRefresh = jest.fn();
const mockMutate = jest.fn();
const mockUseMcpMutation = jest.fn();
const mockUseMcpHealth = jest.fn();

jest.mock('@/hooks/useMcpHealth', () => ({
  useMcpHealth: (...args: unknown[]) => mockUseMcpHealth(...args),
}));

jest.mock('@/lib/mcp/useMcpMutation', () => ({
  useMcpMutation: (...args: unknown[]) => mockUseMcpMutation(...args),
}));

import MigrationOverlay from '@/features/components/MigrationOverlay';

describe('MigrationOverlay', () => {
  const originalVisibilityPolicy = process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;

  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;
    mockUseMcpHealth.mockReturnValue({
      data: { migrationInProgress: false, staleMcpConfig: true },
      refresh: mockRefresh,
    });
    mockUseMcpMutation.mockReturnValue({
      mutate: mockMutate,
      loading: false,
    });
  });

  afterEach(() => {
    if (originalVisibilityPolicy === undefined) {
      delete process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;
    } else {
      process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = originalVisibilityPolicy;
    }
  });

  it('repairs stale MCP configs via the repair tool', () => {
    render(<MigrationOverlay />);

    expect(mockUseMcpMutation).toHaveBeenCalledWith(
      'repair-mcp-configs',
      expect.any(Object),
    );

    fireEvent.click(screen.getByRole('button', { name: /heal system & update ides/i }));

    expect(mockMutate).toHaveBeenCalled();
  });

  it('does not render when no migration or stale config is detected', () => {
    mockUseMcpHealth.mockReturnValue({
      data: { migrationInProgress: false, staleMcpConfig: false },
      refresh: mockRefresh,
    });

    const { container } = render(<MigrationOverlay />);

    expect(container.firstChild).toBeNull();
  });

  it('does not render stale-config repair overlay on validation-only surfaces', () => {
    process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = 'no_visible_mutation';

    const { container } = render(<MigrationOverlay />);

    expect(container.firstChild).toBeNull();
    expect(screen.queryByRole('button', { name: /heal system & update ides/i })).not.toBeInTheDocument();
  });
});
