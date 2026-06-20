import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import AutoCommandHelpCoveragePage from '../dashboard/page';

jest.mock('@/lib/mcp/useMcpQuery', () => ({
  useMcpQuery: jest.fn(),
}));

const mockUseMcpQuery = useMcpQuery as jest.Mock;

describe('AutoCommandHelpCoveragePage', () => {
  beforeEach(() => {
    mockUseMcpQuery.mockReset();
    mockUseMcpQuery
      .mockReturnValueOnce({
        data: {
          status: 'verified',
          lastCheck: '2026-03-27T12:00:00.000Z',
          errors24h: 0,
          uptime: '2h 14m',
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
              id: 'auto-command-help-coverage-overview',
              label: 'Auto Command Help Coverage Overview',
              description: 'Open the command help coverage dashboard.',
              dispatch: 'fire',
            },
          ],
        },
        error: null,
      })
      .mockReturnValueOnce({
        data: {
          content:
            '# auto-command-help-coverage\n\nAudit command-hub SKILL.md files for missing help sections that power slash command discoverability and --help output.',
        },
        error: null,
      });
  });

  it('renders the help coverage dashboard sections', () => {
    render(<AutoCommandHelpCoveragePage />);

    expect(screen.getByText('Help Coverage')).toBeInTheDocument();
    expect(screen.getByText('Registered Actions')).toBeInTheDocument();
    expect(screen.getByText('Difficulty Progression')).toBeInTheDocument();
    expect(screen.getByText('Operator Overview')).toBeInTheDocument();
    expect(screen.getByText('Mode Selection')).toBeInTheDocument();
    expect(screen.getByText('Auto Command Help Coverage Overview')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Audit command-hub SKILL.md files for missing help sections that power slash command discoverability and --help output.',
      ),
    ).toBeInTheDocument();
  });
});
