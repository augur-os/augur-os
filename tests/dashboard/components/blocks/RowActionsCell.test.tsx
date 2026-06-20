/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockRunAction = jest.fn();
jest.mock('@/hooks/useActionRunner', () => ({
  useActionRunner: () => ({
    runAction: mockRunAction,
    isExecuting: false,
  }),
}));

import RowActionsCell from '@/components/blocks/RowActionsCell';
import type { RowAction } from '@/lib/blocks/types';

describe('RowActionsCell', () => {
  beforeEach(() => {
    mockRunAction.mockClear();
  });

  it('renders action buttons for <=2 actions', () => {
    const actions: RowAction[] = [
      { id: 'edit', icon: 'Pencil', label: 'Edit', dispatch: 'modal' },
      { id: 'delete', icon: 'Trash2', label: 'Delete', dispatch: 'fire' },
    ];
    render(<RowActionsCell actions={actions} row={{ id: '123' }} />);
    expect(screen.getByTitle('Edit')).toBeInTheDocument();
    expect(screen.getByTitle('Delete')).toBeInTheDocument();
  });

  it('renders kebab menu for >2 actions', () => {
    const actions: RowAction[] = [
      { id: 'edit', icon: 'Pencil', label: 'Edit', dispatch: 'modal' },
      { id: 'delete', icon: 'Trash2', label: 'Delete', dispatch: 'fire' },
      { id: 'archive', icon: 'Archive', label: 'Archive', dispatch: 'fire' },
    ];
    render(<RowActionsCell actions={actions} row={{ id: '123' }} />);
    expect(screen.getByTitle('Actions')).toBeInTheDocument();
  });

  it('dispatches fire action with payload', () => {
    const actions: RowAction[] = [
      {
        id: 'complete',
        icon: 'Check',
        label: 'Complete',
        dispatch: 'fire',
        payload_fields: ['id'],
      },
    ];
    render(<RowActionsCell actions={actions} row={{ id: '123', name: 'Test' }} />);
    fireEvent.click(screen.getByTitle('Complete'));
    expect(mockRunAction).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'complete',
        label: 'Complete',
        dispatch: 'fire',
        args: { id: '123' },
      }),
    );
  });

  it('shows confirm dialog for destructive actions', () => {
    const actions: RowAction[] = [
      {
        id: 'delete',
        icon: 'Trash2',
        label: 'Delete',
        dispatch: 'fire',
        confirm: true,
        confirm_message: 'Are you sure you want to delete this item?',
      },
    ];
    render(<RowActionsCell actions={actions} row={{ id: '123' }} />);
    fireEvent.click(screen.getByTitle('Delete'));
    expect(
      screen.getByText('Are you sure you want to delete this item?'),
    ).toBeInTheDocument();
  });
});
