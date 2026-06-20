/**
 * @jest-environment jsdom
 */
import { describe, it, expect, jest } from '@jest/globals';
import { render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { createQueryWrapper } from '../../../helpers/component-test-utils';
import type { RowAction } from '@/lib/blocks/types';

// Mock useActionRunner
jest.mock('@/hooks/useActionRunner', () => ({
  useActionRunner: () => ({ runAction: jest.fn(), isExecuting: false }),
}));

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

// Mock useBlockData
jest.mock('@/lib/blocks/useBlockData', () => ({
  useBlockData: () => ({
    data: [
      { id: '1', title: 'Item A', status: 'active' },
      { id: '2', title: 'Item B', status: 'done' },
    ],
    loading: false,
    error: null,
    invalidate: jest.fn(),
    refetch: jest.fn(),
  }),
}));

// Mock useWebMCPReport and useWebMCPSubscribe
jest.mock('@/lib/webmcp/useWebMCPReport', () => ({
  useWebMCPReport: jest.fn(),
  useWebMCPSubscribe: () => ({ configOverride: null, refetchSignal: 0 }),
}));

const sampleActions: RowAction[] = [
  {
    id: 'mark-done',
    icon: 'CheckCircle',
    label: 'Mark Done',
    dispatch: 'fire',
    mcp_tool: 'update-status',
    payload_fields: ['id'],
  },
];

const sampleData = [
  { id: '1', title: 'Item A', status: 'active' },
  { id: '2', title: 'Item B', status: 'done' },
];

const { queryClient, Wrapper } = createQueryWrapper();

describe('DataTableBlock row actions', () => {
  afterEach(() => {
    queryClient.clear();
  });

  it('renders Actions column header when rowActions provided', async () => {
    const mod = await import('@/components/blocks/types/DataTableBlock');
    const DataTableBlock = mod.default;

    render(
      <DataTableBlock
        instanceId="test-actions-1"
        config={{}}
        mode="compact"
        data={sampleData}
        loading={false}
        error={null}
        rowActions={sampleActions}
      />,
      { wrapper: Wrapper },
    );

    expect(screen.getByText('Actions')).toBeInTheDocument();
  });

  it('renders action buttons per data row', async () => {
    const mod = await import('@/components/blocks/types/DataTableBlock');
    const DataTableBlock = mod.default;

    render(
      <DataTableBlock
        instanceId="test-actions-2"
        config={{}}
        mode="compact"
        data={sampleData}
        loading={false}
        error={null}
        rowActions={sampleActions}
      />,
      { wrapper: Wrapper },
    );

    const actionButtons = within(screen.getByRole('table')).getAllByTitle('Mark Done');
    expect(actionButtons).toHaveLength(2);
  });

  it('renders a mobile card alternative for narrow viewports', async () => {
    const mod = await import('@/components/blocks/types/DataTableBlock');
    const DataTableBlock = mod.default;

    render(
      <DataTableBlock
        instanceId="test-actions-mobile"
        config={{}}
        mode="compact"
        data={sampleData}
        loading={false}
        error={null}
      />,
      { wrapper: Wrapper },
    );

    expect(screen.getByTestId('data-table-mobile-cards')).toBeInTheDocument();
    expect(screen.getAllByText('Item A').length).toBeGreaterThan(1);
  });

  it('keeps row actions available in the mobile card layout', async () => {
    const mod = await import('@/components/blocks/types/DataTableBlock');
    const DataTableBlock = mod.default;

    render(
      <DataTableBlock
        instanceId="test-actions-mobile-row-actions"
        config={{}}
        mode="compact"
        data={sampleData}
        loading={false}
        error={null}
        rowActions={sampleActions}
      />,
      { wrapper: Wrapper },
    );

    const mobileCards = screen.getByTestId('data-table-mobile-cards');
    const actionButtons = within(mobileCards).getAllByTitle('Mark Done');
    expect(actionButtons).toHaveLength(2);
    // 44px minimum tap target expressed via Tailwind utilities (min-h-11 = 2.75rem = 44px)
    expect(actionButtons[0]).toHaveClass('min-h-11', 'min-w-11');
  });
});
