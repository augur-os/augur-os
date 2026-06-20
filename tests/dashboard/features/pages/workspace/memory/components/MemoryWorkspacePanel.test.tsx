/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { MemoryWorkspacePanel } from '@/features/pages/workspace/memory/components/MemoryWorkspacePanel';

jest.mock('@/components/ui/GlassCard', () => ({
  GlassCard: ({ children, title }: { children: ReactNode; title: string }) => (
    <section aria-label={title}>{children}</section>
  ),
}));

describe('MemoryWorkspacePanel', () => {
  it('shows notice and error blocks before the workspace files', () => {
    render(
      <MemoryWorkspacePanel
        workspace={{
          rootPath: '/vault/memory',
          files: [
            {
              id: 'memory',
              label: 'Memory',
              description: 'Memory file',
              kind: 'markdown',
              path: '/vault/memory/MEMORY.md',
              exists: true,
              sizeBytes: 2048,
              modifiedAt: '2026-04-22T09:30:00.000Z',
            },
          ],
        }}
        isLoading={false}
        openingFileId={null}
        onOpenFile={jest.fn()}
        onRefresh={jest.fn()}
        notice={{ type: 'success', message: 'Memory workspace loaded.', timestamp: '2026-04-22T10:01:00.000Z' }}
        error="Open memory workspace file failed: permission denied"
      />,
    );

    expect(screen.getByText('Memory workspace loaded.')).toBeInTheDocument();
    expect(screen.getByText('Open memory workspace file failed: permission denied')).toBeInTheDocument();
    expect(screen.getByText('Memory')).toBeInTheDocument();
  });

  it('shows a compact path label with a copy affordance', () => {
    render(
      <MemoryWorkspacePanel
        workspace={{
          rootPath: '/vault/memory',
          files: [
            {
              id: 'memory',
              label: 'Memory',
              description: 'Memory file',
              kind: 'markdown',
              path: '/Users/example/very/deep/path/to/memory/MEMORY.md',
              exists: true,
              sizeBytes: 2048,
              modifiedAt: '2026-04-22T09:30:00.000Z',
            },
          ],
        }}
        isLoading={false}
        openingFileId={null}
        onOpenFile={jest.fn()}
        onRefresh={jest.fn()}
      />,
    );

    expect(screen.getByText('/Users/example/.../MEMORY.md')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /copy path for memory/i })).toHaveClass('min-h-[44px]');
  });

  it('shows copied feedback even when clipboard write is blocked', async () => {
    const writeText = jest.fn().mockRejectedValue(new Error('clipboard denied'));
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });

    render(
      <MemoryWorkspacePanel
        workspace={{
          rootPath: '/vault/memory',
          files: [
            {
              id: 'memory',
              label: 'Memory',
              description: 'Memory file',
              kind: 'markdown',
              path: '/vault/memory/MEMORY.md',
              exists: true,
              sizeBytes: 2048,
              modifiedAt: '2026-04-22T09:30:00.000Z',
            },
          ],
        }}
        isLoading={false}
        openingFileId={null}
        onOpenFile={jest.fn()}
        onRefresh={jest.fn()}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: /copy path for memory/i }));

    expect(writeText).toHaveBeenCalledWith('/vault/memory/MEMORY.md');
    await waitFor(() => expect(screen.getByText('Copied')).toBeInTheDocument());
  });

  it('explains each canonical file with inline preview, validation, and why it matters', () => {
    render(
      <MemoryWorkspacePanel
        workspace={{
          rootPath: '/vault/memory',
          files: [
            {
              id: 'daily',
              label: 'Daily Logs',
              description: 'Session-level decision and preference logs',
              kind: 'directory',
              path: '/runtime/memory/daily',
              exists: true,
              sizeBytes: 4096,
              modifiedAt: null,
              entryCount: 12,
            },
          ],
        }}
        isLoading={false}
        openingFileId={null}
        onOpenFile={jest.fn()}
        onRefresh={jest.fn()}
      />,
    );

    expect(screen.getByText('Preview')).toBeInTheDocument();
    expect(screen.getByText(/Directory with 12 entries/i)).toBeInTheDocument();
    expect(screen.getByText('Why it matters')).toBeInTheDocument();
    expect(screen.getByText(/Feeds recency checks and curation/i)).toBeInTheDocument();
    expect(screen.getByText('Validation')).toBeInTheDocument();
    expect(screen.getByText(/Ready: present with 12 entries/i)).toBeInTheDocument();
  });
});
