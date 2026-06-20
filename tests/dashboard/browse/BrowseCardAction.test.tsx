/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowseCard } from '@/components/shared/BrowseCard';
import type { BrowseItem } from '@/lib/browse/types';

jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn() }) }));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

// Mock clipboard
const mockClipboard = { writeText: jest.fn(() => Promise.resolve()) };
Object.defineProperty(navigator, 'clipboard', { value: mockClipboard, writable: true });

const baseItem: BrowseItem = {
  id: 'test-skill',
  title: 'Test Skill',
  description: 'A test skill',
  hub: 'dev',
  primaryAction: { label: 'View', type: 'navigate', target: '/dev/test' },
};

describe('BrowseCard per-card actions', () => {
  it('renders secondary actions inside the overflow menu', async () => {
    const item: BrowseItem = {
      ...baseItem,
      actions: [
        { id: 'copy-id', label: 'Copy ID', icon: 'Copy', type: 'copy', target: 'test-skill' },
        { id: 'reveal', label: 'Reveal', icon: 'FolderOpen', type: 'open-file', target: '/path/to/skill' },
      ],
    };
    render(<BrowseCard item={item} />);
    fireEvent.click(screen.getByTestId('browse-card-overflow'));
    expect(screen.getByRole('menuitem', { name: 'Copy ID' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Reveal' })).toBeInTheDocument();
  });

  it('renders no secondary buttons when actions is absent', () => {
    render(<BrowseCard item={baseItem} />);
    // Only the primary action button
    expect(screen.getAllByRole('button')).toHaveLength(1);
  });

  it('danger variant renders with red styling in the overflow menu', async () => {
    const item: BrowseItem = {
      ...baseItem,
      actions: [
        { id: 'remove', label: 'Remove', icon: 'Trash', type: 'run-mcp', target: 'remove-skill', variant: 'danger' },
      ],
    };
    render(<BrowseCard item={item} />);
    fireEvent.click(screen.getByTestId('browse-card-overflow'));
    const btn = screen.getByRole('menuitem', { name: 'Remove' });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute('data-variant', 'danger');
  });

  it('renders private overlay badges from metadata', () => {
    render(
      <BrowseCard
        item={{
          ...baseItem,
          metadata: {
            vault_scope: 'private',
            promotion_state: 'private',
          },
        }}
      />,
    );

    expect(screen.getByText('Private')).toBeInTheDocument();
  });

  it('prioritizes packet overlay badges over shared vault scope', () => {
    render(
      <BrowseCard
        item={{
          ...baseItem,
          metadata: {
            vault_scope: 'shared',
            promotion_state: 'packet',
          },
        }}
      />,
    );

    expect(screen.getByText('Packet')).toBeInTheDocument();
    expect(screen.queryByText('Shared')).not.toBeInTheDocument();
  });
});
