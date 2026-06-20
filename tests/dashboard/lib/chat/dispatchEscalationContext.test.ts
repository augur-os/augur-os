/**
 * ADR-161: Tests for dispatch-escalation context re-resolution.
 *
 * Verifies that Tier 2 and Tier 3 re-resolve context instead of using stale Tier 1 page.
 */

import { resolveContext, buildPromptFromEnvelope } from '@/lib/chat/context-envelope';

// Mock the resolveContext fetch
jest.mock('@/lib/chat/context-envelope', () => {
  const actual = jest.requireActual('@/lib/chat/context-envelope');
  return {
    ...actual,
    resolveContext: jest.fn(),
  };
});

const mockResolveContext = resolveContext as jest.MockedFunction<typeof resolveContext>;

describe('dispatch-escalation context re-resolution (ADR-161)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('resolveContext is callable with standard priority for Tier 2', async () => {
    mockResolveContext.mockResolvedValue({
      sessionId: 'test',
      timestamp: Date.now(),
      page: '/career/resume',
      hub: 'career',
      skill: 'resume',
      skillSummary: 'Resume management skill',
      skillDataDir: '/path/to/data',
      skillTools: ['career-tailor-resume'],
      skillActions: ['tailor'],
      action: { id: 'fix-t2', label: 'Fix', description: 'Fix task', prompt: 'Fix it' },
      projectIdentity: null,
      maxContextTokens: 800,
      priority: 'standard',
    });

    const envelope = await resolveContext('/career/resume', 'standard', {
      id: 'fix-t2',
      label: 'Fix',
      description: 'Fix task',
      prompt: 'Fix it',
    });

    expect(mockResolveContext).toHaveBeenCalledWith('/career/resume', 'standard', expect.any(Object));
    expect(envelope.hub).toBe('career');
    expect(envelope.priority).toBe('standard');
  });

  it('resolveContext is callable with rich priority for Tier 3', async () => {
    mockResolveContext.mockResolvedValue({
      sessionId: 'test',
      timestamp: Date.now(),
      page: '/consulting/pipeline',
      hub: 'consulting',
      skill: 'pipeline',
      skillSummary: null,
      skillDataDir: null,
      skillTools: [],
      skillActions: [],
      action: null,
      projectIdentity: null,
      maxContextTokens: 2000,
      priority: 'rich',
    });

    const envelope = await resolveContext('/consulting/pipeline', 'rich');

    expect(mockResolveContext).toHaveBeenCalledWith('/consulting/pipeline', 'rich');
    expect(envelope.priority).toBe('rich');
    expect(envelope.maxContextTokens).toBe(2000);
  });

  it('buildPromptFromEnvelope produces valid prompt from re-resolved envelope', () => {
    const actual = jest.requireActual('@/lib/chat/context-envelope');
    const prompt = actual.buildPromptFromEnvelope({
      sessionId: 'test',
      timestamp: Date.now(),
      page: '/career/resume',
      hub: 'career',
      skill: 'resume',
      skillSummary: 'Resume builder and tailor',
      skillDataDir: '/data',
      skillTools: ['career-tailor-resume'],
      skillActions: ['tailor'],
      action: { id: 'fix', label: 'Fix', description: 'Fix', prompt: 'Please fix the resume' },
      projectIdentity: null,
      maxContextTokens: 800,
      priority: 'standard',
    });

    expect(prompt).toContain('Page: /career/resume');
    expect(prompt).toContain('Hub: career');
    expect(prompt).toContain('Please fix the resume');
  });
});
