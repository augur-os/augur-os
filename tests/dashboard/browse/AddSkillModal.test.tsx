/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { AddSkillModal } from '@/features/browse/AddSkillModal';

const mockRunCliExecPrompt = jest.fn();
const mockMutate = jest.fn();

jest.mock('@/lib/browse/cliExecClient', () => ({
  runCliExecPrompt: (...args: unknown[]) => mockRunCliExecPrompt(...args),
}));

jest.mock('@/lib/mcp/useMcpMutation', () => ({
  useMcpMutation: () => ({
    mutate: mockMutate,
    loading: false,
    error: null,
  }),
}));

jest.mock('@/lib/mcp/useMcpQuery', () => ({
  useMcpQuery: () => ({
    data: { skills: [], scanned_paths: [] },
    loading: false,
    error: null,
    refetch: jest.fn(),
  }),
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), loading: jest.fn(() => 'toast-1') },
}));

function ModalHarness() {
  const [open, setOpen] = React.useState(true);

  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Reopen modal
      </button>
      <AddSkillModal open={open} onOpenChange={setOpen} />
    </div>
  );
}

describe('AddSkillModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRunCliExecPrompt.mockResolvedValue({ answer: 'ok' });
  });

  it('exposes an accessible dialog title and chooser cards', () => {
    render(<AddSkillModal open onOpenChange={jest.fn()} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /add skill/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create from scratch/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /install from url/i })).toBeInTheDocument();
  });

  it('resets to the chooser after closing from a sub-flow', async () => {
    const user = userEvent.setup();
    render(<ModalHarness />);

    await user.click(screen.getByRole('button', { name: /install from url/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /install from url/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /close dialog/i }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await new Promise((resolve) => setTimeout(resolve, 250));

    await user.click(screen.getByRole('button', { name: /reopen modal/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /add skill/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create from scratch/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /install from url/i })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /install from url/i })).not.toBeInTheDocument();
  });

  it('runs CLI creation flows through raw CLI exec and reopens on the chooser', async () => {
    const user = userEvent.setup();
    render(<ModalHarness />);

    await user.click(screen.getByRole('button', { name: /create from scratch/i }));

    expect(mockRunCliExecPrompt).toHaveBeenCalledWith(expect.any(String));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /reopen modal/i }));
    expect(screen.getByRole('button', { name: /create from scratch/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /install from url/i })).toBeInTheDocument();
  });
});
