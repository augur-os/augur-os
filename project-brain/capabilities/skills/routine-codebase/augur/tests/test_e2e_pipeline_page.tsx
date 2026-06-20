import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import AutoE2EPipelinePage from '../dashboard/page';

jest.mock('@/lib/mcp/useMcpQuery', () => ({
  useMcpQuery: jest.fn(),
}));

const mockUseMcpQuery = useMcpQuery as jest.Mock;

describe('AutoE2EPipelinePage', () => {
  beforeEach(() => {
    mockUseMcpQuery.mockReset();
    mockUseMcpQuery
      .mockReturnValueOnce({
        data: {
          status: 'verified',
          lastCheck: '2026-03-27T12:00:00.000Z',
          errors24h: 0,
          uptime: '4h 11m',
          structure: {
            has_skill_md: true,
            has_scripts: true,
            has_commands: true,
          },
        },
        error: null,
      })
      .mockReturnValueOnce({
        data: {
          actions: [
            {
              id: 'auto-e2e-pipeline-overview',
              label: 'Auto E2E Pipeline Overview',
              description: 'Open the end-to-end pipeline dashboard.',
              dispatch: 'fire',
            },
          ],
        },
        error: null,
      })
      .mockReturnValueOnce({
        data: {
          content:
            '# auto-e2e-pipeline\n\nValidate the full data pipeline from vault files through RAG index, MCP tools, API routes, to dashboard rendering.',
        },
        error: null,
      });
  });

  it('renders the pipeline dashboard sections', () => {
    render(<AutoE2EPipelinePage />);

    expect(screen.getByText('Pipeline Coverage')).toBeInTheDocument();
    expect(screen.getByText('Browse Categories')).toBeInTheDocument();
    expect(screen.getByText('Difficulty Progression')).toBeInTheDocument();
    expect(screen.getByText('Registered Actions')).toBeInTheDocument();
    expect(screen.getByText('Operator Overview')).toBeInTheDocument();
    expect(screen.getByText('Auto E2E Pipeline Overview')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('Vault Files')).toBeInTheDocument();
    expect(screen.getByText('mcp-tools')).toBeInTheDocument();
    expect(screen.getByText('Cross-reference')).toBeInTheDocument();
  });
});
