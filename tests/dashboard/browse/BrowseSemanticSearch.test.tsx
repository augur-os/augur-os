/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { createQueryWrapper } from "../helpers/component-test-utils";

const mockMcpCall = jest.fn();

jest.mock('@/lib/stores/modeStore', () => ({
  useModeStore: (selector: (s: { mode: string }) => string) => selector({ mode: 'development' }),
}));
jest.mock('@/lib/tabs/generated-registry', () => ({
  pluginTabRegistry: {},
}));
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
jest.mock('@/lib/blocks/generated-block-registry', () => ({
  BLOCK_REGISTRY: {},
  BLOCK_LIST: [],
  getBlocksByHub: jest.fn(() => []),
}));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
// Mock mcpCall for any MCP-based data loading
jest.mock('@/lib/mcp/client', () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

describe('Browse semantic search mode', () => {
  beforeEach(() => {
    mockMcpCall.mockResolvedValue({
      success: true,
      results: [
        {
          file: 'project-brain/capabilities/skills/knowledge/SKILL.md',
          content: 'knowledge management result',
          scope: 'brain',
        },
      ],
    });
    (global.fetch as jest.Mock)?.mockClear?.();
  });

  it('does not expose keyword and semantic as separate user modes', async () => {
    const { BrowsePageClient } = await import('@/app/(views)/browse/BrowsePageClient');
    const { Wrapper } = createQueryWrapper();
    render(<BrowsePageClient />, { wrapper: Wrapper });

    expect(screen.queryByLabelText('Search mode')).not.toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /search/i })).toBeInTheDocument();
  });

  it('runs unified-search by default when Enter is pressed', async () => {
    const { BrowsePageClient } = await import('@/app/(views)/browse/BrowsePageClient');
    const { Wrapper } = createQueryWrapper();
    render(<BrowsePageClient />, { wrapper: Wrapper });

    const input = screen.getByRole('textbox', { name: /search/i });
    fireEvent.change(input, { target: { value: 'knowledge management' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      // Search is scoped to the active tab (default "skills") so results stay
      // within the category instead of mixing the whole knowledge base.
      expect(mockMcpCall).toHaveBeenCalledWith(
        'unified-search',
        { query: 'knowledge management', budget: 'balanced', category: 'skills' },
      );
    });
    expect(await screen.findByText(/knowledge management result/i)).toBeInTheDocument();
  });

  it('does not expose retrieval budget as a primary toolbar control', async () => {
    const { BrowsePageClient } = await import('@/app/(views)/browse/BrowsePageClient');
    const { Wrapper } = createQueryWrapper();
    render(<BrowsePageClient />, { wrapper: Wrapper });

    expect(screen.queryByLabelText('Search budget')).not.toBeInTheDocument();
  });

  it('preserves document metadata for semantic result cards', async () => {
    mockMcpCall.mockImplementation((tool: unknown) => {
      if (tool === 'unified-search') {
        return Promise.resolve({
          success: true,
          results: [
            {
              file: '~/Library/Application Support/Augur/rag/documents/venture-augur/IntelSubmit/augur-angel-deck-v20.md',
              content: 'Recent document: augur-angel-deck-v20',
              scope: 'rag',
              category: 'documents',
              hub: 'venture-augur',
              format: 'pptx',
              name: 'augur-angel-deck-v20',
              document_title: 'augur-angel-deck-v20',
              source_path: '~/Projects/Au-docs/venture-augur/IntelSubmit/inteliginite/augur-angel-deck-v20.pptx',
              modified: '2026-05-18T06:59:20+00:00',
            },
          ],
        });
      }
      return Promise.resolve({ success: true, results: [] });
    });

    const { BrowsePageClient } = await import('@/app/(views)/browse/BrowsePageClient');
    const { Wrapper } = createQueryWrapper();
    render(<BrowsePageClient />, { wrapper: Wrapper });

    const input = screen.getByRole('textbox', { name: /search/i });
    fireEvent.change(input, { target: { value: 'pitch slide I am working on' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(await screen.findByText('augur angel deck v20')).toBeInTheDocument();
    expect(screen.getByText(/PPTX · venture-augur \/ IntelSubmit \/ inteliginite \/ augur-angel-deck-v20\.pptx/)).toBeInTheDocument();
    // Note: the standalone collection badge ('venture-augur') was rendered via the
    // now-removed hub badge mechanism (ADR-802); the collection is still shown in the
    // path breadcrumb above.
    expect(screen.getAllByText('pptx').length).toBeGreaterThan(0);
  });
});
