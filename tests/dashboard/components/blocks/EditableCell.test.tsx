/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockRunAction = jest.fn().mockResolvedValue(undefined);
jest.mock('@/hooks/useActionRunner', () => ({
  useActionRunner: () => ({
    runAction: mockRunAction,
    isExecuting: false,
  }),
}));

import { EditableCell } from '@/components/blocks/EditableCell';
import type { EditableField } from '@/lib/blocks/types';

describe('EditableCell', () => {
  beforeEach(() => {
    mockRunAction.mockClear();
    mockRunAction.mockResolvedValue(undefined);
  });

  it('renders value in read mode by default', () => {
    const field: EditableField = {
      field: 'title',
      type: 'text',
      save_action: 'save-title',
    };
    render(<EditableCell field={field} value="Hello" rowId="1" />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('enters edit mode on double-click', () => {
    const field: EditableField = {
      field: 'title',
      type: 'text',
      save_action: 'save-title',
    };
    render(<EditableCell field={field} value="Hello" rowId="1" />);
    fireEvent.doubleClick(screen.getByText('Hello'));
    expect(screen.getByDisplayValue('Hello')).toBeInTheDocument();
  });

  it('saves on Enter key', async () => {
    const field: EditableField = {
      field: 'title',
      type: 'text',
      save_action: 'save-title',
    };
    render(<EditableCell field={field} value="Hello" rowId="1" />);
    fireEvent.doubleClick(screen.getByText('Hello'));
    const input = screen.getByDisplayValue('Hello');
    fireEvent.change(input, { target: { value: 'World' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => {
      expect(mockRunAction).toHaveBeenCalledWith(
        expect.objectContaining({
          args: { id: '1', field: 'title', value: 'World' },
        }),
      );
    });
  });

  it('cancels on Escape key', () => {
    const field: EditableField = {
      field: 'title',
      type: 'text',
      save_action: 'save-title',
    };
    render(<EditableCell field={field} value="Hello" rowId="1" />);
    fireEvent.doubleClick(screen.getByText('Hello'));
    const input = screen.getByDisplayValue('Hello');
    fireEvent.change(input, { target: { value: 'Changed' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('renders toggle for boolean fields', () => {
    const field: EditableField = {
      field: 'active',
      type: 'toggle',
      save_action: 'toggle-active',
    };
    render(<EditableCell field={field} value={true} rowId="1" />);
    const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });

  it('renders select for select fields', () => {
    const field: EditableField = {
      field: 'status',
      type: 'select',
      save_action: 'update-status',
      options: ['open', 'closed', 'pending'],
    };
    render(<EditableCell field={field} value="open" rowId="1" />);
    fireEvent.doubleClick(screen.getByText('open'));
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });
});
