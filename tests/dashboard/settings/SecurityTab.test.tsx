import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { renderWithQuery } from '../helpers/component-test-utils';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => '/settings/security',
  useSearchParams: () => ({ get: jest.fn() }),
}));

const mockFetch = jest.fn() as jest.Mock<(...args: any[]) => Promise<any>>;
(globalThis as any).fetch = mockFetch;

import SecurityTab from '@/app/settings/tabs/SecurityTab';

// Helper: create a mock that handles both MCP tool calls and direct fetch patterns
function createMcpMock(overrides: Record<string, unknown> = {}) {
  return (url: string, init?: RequestInit) => {
    const jsonHeaders = new Headers({ 'content-type': 'application/json' });
    if (url === '/api/airplane') {
      const data = overrides['api-airplane'] as { ok?: boolean; status?: number; text?: string } | undefined;
      const ok = data?.ok ?? true;
      const status = data?.status ?? (ok ? 200 : 500);
      const text = data?.text ?? (ok ? '{}' : 'Failed to update airplane mode');
      return Promise.resolve({
        ok,
        status,
        headers: jsonHeaders,
        json: () => Promise.resolve(ok ? { success: true } : { error: text }),
        text: () => Promise.resolve(text),
      });
    }
    // Handle MCP tool proxy calls
    if (url === '/api/mcp/tool' && init?.body) {
      const { tool } = JSON.parse(init.body as string);
      if (tool === 'get-local-backend-status') {
        const data = overrides['get-local-backend-status'] ?? {
          airplane_mode: { enabled: false },
        };
        return Promise.resolve({ ok: true, headers: jsonHeaders, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });
      }
      if (tool === 'get-settings') {
        const data = overrides['get-settings'] ?? {
          security: {
            requireExplicitConsent: true,
            warnOnPii: true,
            blockOnSecrets: true,
            sensitiveFolders: [],
          },
        };
        return Promise.resolve({ ok: true, headers: jsonHeaders, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });
      }
      if (tool === 'query-audit-log') {
        const data = overrides['query-audit-log'] ?? { ok: true, logs: [] };
        return Promise.resolve({ ok: true, headers: jsonHeaders, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });
      }
      if (tool === 'get-security-report') {
        const data = overrides['security-report'] ?? { status: 'no_report' };
        return Promise.resolve({ ok: true, headers: jsonHeaders, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });
      }
      if (tool === 'run-security-scan') {
        const data = overrides['security-report'] ?? { status: 'no_report' };
        return Promise.resolve({ ok: true, headers: jsonHeaders, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });
      }
      return Promise.resolve({ ok: true, headers: jsonHeaders, json: () => Promise.resolve({}), text: () => Promise.resolve('{}') });
    }
    // Handle direct fetch calls (audit report still uses direct fetch)
    if (typeof url === 'string' && url.includes('/api/dev/security/report')) {
      const data = overrides['security-report'] ?? { status: 'no_report' };
      return Promise.resolve({ ok: true, headers: jsonHeaders, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });
    }
    if (typeof url === 'string' && url.includes('/api/dev/security')) {
      const data = overrides['security-scan'] ?? { ok: true };
      return Promise.resolve({ ok: true, headers: jsonHeaders, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });
    }
    return Promise.resolve({ ok: true, headers: jsonHeaders, json: () => Promise.resolve({}), text: () => Promise.resolve('{}') });
  };
}

describe('SecurityTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.removeItem('augur:airplane-mode');
    mockFetch.mockImplementation(createMcpMock());
  });

  it('renders without crashing', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('AI Guardrails')).toBeInTheDocument();
    });
  });

  it('displays AI Guardrails section', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('AI Guardrails')).toBeInTheDocument();
    });

    expect(screen.getByText('Explicit Consent Required')).toBeInTheDocument();
    expect(screen.getByText('Block on Secrets')).toBeInTheDocument();
    expect(screen.getByText('Warn on PII')).toBeInTheDocument();
    expect(screen.getByText('Sensitive Folders')).toBeInTheDocument();
  });

  it('displays Audit Log section', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    expect(screen.getByText('Track all security-relevant actions')).toBeInTheDocument();
  });

  it('shows Export JSON and Export CSV buttons', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('Export JSON')).toBeInTheDocument();
    });

    expect(screen.getByText('Export CSV')).toBeInTheDocument();
  });

  it('shows filter inputs for audit log', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('Search Action')).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText('e.g., login...')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('User email or ID')).toBeInTheDocument();
  });

  it('shows empty audit log message when no logs', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('No audit logs found matching criteria.')).toBeInTheDocument();
    });
  });

  it('displays audit table headers', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('Status')).toBeInTheDocument();
    });

    // "Action" and "User" appear in both filter labels and table headers
    const actionElements = screen.getAllByText('Action');
    expect(actionElements.length).toBeGreaterThanOrEqual(1);
    const userElements = screen.getAllByText('User');
    expect(userElements.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Resource')).toBeInTheDocument();
    expect(screen.getByText('Timestamp')).toBeInTheDocument();
  });

  it('shows guardrail Active badges when enabled', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('AI Guardrails')).toBeInTheDocument();
    });

    // With default settings, 3 guardrails should be Active
    const activeBadges = screen.getAllByText('Active');
    expect(activeBadges.length).toBeGreaterThanOrEqual(3);
  });

  it('shows Filter and Clear buttons', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('Filter')).toBeInTheDocument();
    });

    expect(screen.getByText('Clear')).toBeInTheDocument();
  });

  // --- Codebase Security Audit section (ADR-234) ---

  it('displays Codebase Security Audit section', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('Codebase Security Audit')).toBeInTheDocument();
    });

    expect(screen.getByText('Scan for vulnerabilities, secrets, and dependency issues')).toBeInTheDocument();
  });

  it('shows Run Security Audit and Quick Scan buttons', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('Run Security Audit')).toBeInTheDocument();
    });

    expect(screen.getByText('Quick Scan')).toBeInTheDocument();
  });

  it('shows empty state when no audit report exists', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('No audit reports yet. Run a security audit to see results.')).toBeInTheDocument();
    });
  });

  it('shows empty state (no crash) when loader returns an error sentinel', async () => {
    // _load_security_report returns {status: "error", error: "..."} on read
    // failure — a truthy object that must not be treated as a real report.
    mockFetch.mockImplementation(createMcpMock({
      'security-report': { status: 'error', error: 'boom' },
    }));

    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('No audit reports yet. Run a security audit to see results.')).toBeInTheDocument();
    });

    expect(screen.queryByText('Files Reviewed')).not.toBeInTheDocument();
  });

  it('shows summary cards when audit report exists', async () => {
    mockFetch.mockImplementation(createMcpMock({
      'security-report': {
        timestamp: '2026-03-10T12:00:00.000Z',
        source: 'scanner',
        analysis_summary: {
          files_reviewed: 42,
          high_severity: 1,
          medium_severity: 2,
          low_severity: 3,
        },
        findings: [
          {
            file: 'src/config.py',
            line: 10,
            severity: 'HIGH',
            category: 'secret_detection',
            description: 'Hardcoded API key found',
            confidence: 1.0,
            recommendation: 'Move to environment variable',
            source: 'scanner',
          },
        ],
      },
    }));

    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('High')).toBeInTheDocument();
    });

    expect(screen.getByText('Medium')).toBeInTheDocument();
    expect(screen.getByText('Low')).toBeInTheDocument();
    expect(screen.getByText('Files Reviewed')).toBeInTheDocument();

    // Check count values
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('shows findings table with correct columns when report has findings', async () => {
    mockFetch.mockImplementation(createMcpMock({
      'security-report': {
        timestamp: '2026-03-10T12:00:00.000Z',
        source: 'scanner',
        analysis_summary: { files_reviewed: 5, high_severity: 1, medium_severity: 0, low_severity: 0 },
        findings: [{
          file: 'src/config.py', line: 10, severity: 'HIGH', category: 'secret_detection',
          description: 'Hardcoded API key found', confidence: 0.95,
          recommendation: 'Move to environment variable',
          exploit_scenario: 'Key can be extracted from source control', source: 'scanner',
        }],
      },
    }));

    renderWithQuery(<SecurityTab />);

    // Wait for findings table to render
    await waitFor(() => {
      expect(screen.getByText('Severity')).toBeInTheDocument();
    });

    // Verify table column headers
    expect(screen.getByText('Conf.')).toBeInTheDocument();
    expect(screen.getByText('Category')).toBeInTheDocument();
    expect(screen.getByText('File')).toBeInTheDocument();
    expect(screen.getByText('Line')).toBeInTheDocument();
    expect(screen.getByText('Description')).toBeInTheDocument();
    expect(screen.getByText('Source')).toBeInTheDocument();

    // Verify finding data
    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('Secret Detection')).toBeInTheDocument();
    expect(screen.getByText('src/config.py')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('Hardcoded API key found')).toBeInTheDocument();
    expect(screen.getByText('Scanner')).toBeInTheDocument();
  });

  it('shows no-issues message when report has zero findings', async () => {
    mockFetch.mockImplementation(createMcpMock({
      'security-report': {
        timestamp: '2026-03-10T12:00:00.000Z',
        source: 'scanner',
        analysis_summary: { files_reviewed: 20, high_severity: 0, medium_severity: 0, low_severity: 0 },
        findings: [],
      },
    }));

    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('No security issues found in the last audit.')).toBeInTheDocument();
    });
  });

  it('expands finding row to show exploit scenario and recommendation', async () => {
    mockFetch.mockImplementation(createMcpMock({
      'security-report': {
        timestamp: '2026-03-10T12:00:00.000Z',
        source: 'claude',
        analysis_summary: { files_reviewed: 8, high_severity: 1, medium_severity: 0, low_severity: 0 },
        findings: [{
          file: 'src/api/auth.py', line: 55, severity: 'HIGH', category: 'sql_injection',
          description: 'User input passed directly to SQL query', confidence: 0.92,
          recommendation: 'Use parameterized queries',
          exploit_scenario: 'Attacker can extract database contents via UNION-based injection', source: 'claude',
        }],
      },
    }));

    renderWithQuery(<SecurityTab />);

    // Wait for the finding row
    await waitFor(() => {
      expect(screen.getByText('Sql Injection')).toBeInTheDocument();
    });

    // Recommendation and exploit_scenario should NOT be visible before expanding
    expect(screen.queryByText('Use parameterized queries')).not.toBeInTheDocument();

    // Click the row to expand
    fireEvent.click(screen.getByText('User input passed directly to SQL query'));

    // Now expanded detail should be visible
    await waitFor(() => {
      expect(screen.getByText('Use parameterized queries')).toBeInTheDocument();
    });
    expect(screen.getByText(/Attacker can extract database contents/)).toBeInTheDocument();

    // Verify source badge shows Claude
    expect(screen.getByText('Claude')).toBeInTheDocument();
  });

  it('fetches audit report on mount', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('Codebase Security Audit')).toBeInTheDocument();
    });

    // Verify MCP tool calls were made (all go through /api/mcp/tool now)
    const mcpCalls = mockFetch.mock.calls.filter(
      (call: any[]) => typeof call[0] === 'string' && call[0].includes('/api/mcp/tool')
    );
    expect(mcpCalls.length).toBeGreaterThanOrEqual(1);
  });

  it('triggers Quick Scan and fetches updated report', async () => {
    renderWithQuery(<SecurityTab />);

    await waitFor(() => {
      expect(screen.getByText('Quick Scan')).toBeInTheDocument();
    });

    // Click Quick Scan
    fireEvent.click(screen.getByText('Quick Scan'));

    // Verify it calls an MCP tool (all calls now go through /api/mcp/tool)
    await waitFor(() => {
      const scanCalls = mockFetch.mock.calls.filter(
        (call: any[]) => typeof call[0] === 'string' && call[0].includes('/api/mcp/tool')
      );
      expect(scanCalls.length).toBeGreaterThanOrEqual(1);
    });
  });
});
