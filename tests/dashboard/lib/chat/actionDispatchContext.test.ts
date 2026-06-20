/**
 * ADR-161 Phase 5.3: Integration test for action → resolveContext → prompt pipeline.
 *
 * Verifies that all dispatch paths (fire, oneshot, chat, ide, escalation)
 * produce properly structured prompts via ContextEnvelope.
 */

import {
  resolveContext,
  buildPromptFromEnvelope,
  getBudgetForPriority,
  BUDGET_MINIMAL,
  BUDGET_STANDARD,
  BUDGET_RICH,
  type ContextEnvelope,
  type ContextPriority,
} from '@/lib/chat/context-envelope';

const mockMcpCall = jest.fn();

jest.mock('@/lib/mcp/client', () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

function makeEnvelope(overrides: Partial<ContextEnvelope> = {}): ContextEnvelope {
  return {
    sessionId: 'integration-test',
    timestamp: Date.now(),
    page: '/productivity/notes',
    hub: 'productivity',
    skill: 'apple',
    skillSummary: 'Manages Apple Notes, Reminders, and Calendar.',
    skillDataDir: '/path/to/augur/data',
    skillTools: ['apple-read-notes', 'apple-create-note'],
    skillActions: ['quick-capture', 'search-notes'],
    action: null,
    projectIdentity: 'Augur is a local-first personal knowledge system.',
    maxContextTokens: BUDGET_RICH,
    priority: 'rich',
    ...overrides,
  };
}

function mockResolveResponse(envelope: ContextEnvelope): void {
  mockMcpCall.mockResolvedValueOnce(envelope);
}

describe('ADR-161 action → resolveContext → prompt integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ─── Dispatch path: fire (minimal context) ─────────────────────────────

  describe('fire dispatch path', () => {
    it('resolves context with minimal priority and extracts hub/skill', async () => {
      const envelope = makeEnvelope({
        priority: 'minimal',
        maxContextTokens: BUDGET_MINIMAL,
      });
      mockResolveResponse(envelope);

      const result = await resolveContext('/productivity/notes', 'minimal');

      expect(mockMcpCall).toHaveBeenCalledWith(
        'get-context',
        { page: '/productivity/notes', priority: 'minimal', action: undefined },
      );
      expect(result.hub).toBe('productivity');
      expect(result.skill).toBe('apple');
    });
  });

  // ─── Dispatch path: oneshot (minimal budget) ───────────────────────────

  describe('oneshot dispatch path', () => {
    it('resolves context with minimal priority and action, builds prompt', async () => {
      const action = {
        id: 'search-notes',
        label: 'Search Notes',
        description: 'Search Apple Notes',
        prompt: 'Find notes about meeting prep',
      };
      const envelope = makeEnvelope({
        priority: 'minimal',
        maxContextTokens: BUDGET_MINIMAL,
        action,
      });
      mockResolveResponse(envelope);

      const result = await resolveContext('/productivity/notes', 'minimal', action);
      const prompt = buildPromptFromEnvelope(result);

      expect(result.action).toEqual(action);
      expect(prompt).toContain('Page: /productivity/notes');
      expect(prompt).toContain('Hub: productivity');
      expect(prompt).toContain('Find notes about meeting prep');
    });

    it('minimal budget cuts project identity but preserves action', () => {
      // Use a tight budget (30 tokens) to force truncation of low-priority sections
      const prompt = buildPromptFromEnvelope(makeEnvelope({
        priority: 'minimal',
        maxContextTokens: 30,
        action: {
          id: 'test',
          label: 'Test',
          description: 'Test',
          prompt: 'Do the thing',
        },
      }));

      expect(prompt).toContain('Page:');
      expect(prompt).toContain('Do the thing');
      // Project identity (priority 1) should be cut under tight budget
      expect(prompt).not.toContain('## Project');
    });
  });

  // ─── Dispatch path: chat (standard budget) ─────────────────────────────

  describe('chat dispatch path', () => {
    it('resolves context with standard priority, includes skill summary', async () => {
      const envelope = makeEnvelope({
        priority: 'standard',
        maxContextTokens: BUDGET_STANDARD,
      });
      mockResolveResponse(envelope);

      const result = await resolveContext('/productivity/notes', 'standard');
      const prompt = buildPromptFromEnvelope(result);

      expect(result.priority).toBe('standard');
      expect(prompt).toContain('Skill: apple');
      expect(prompt).toContain('Manages Apple Notes');
    });

    it('standard budget includes tools when space allows', () => {
      const prompt = buildPromptFromEnvelope(makeEnvelope({
        priority: 'standard',
        maxContextTokens: BUDGET_STANDARD,
      }));

      expect(prompt).toContain('apple-read-notes');
    });
  });

  // ─── Dispatch path: ide (rich budget) ──────────────────────────────────

  describe('ide dispatch path', () => {
    it('resolves context with rich priority, includes all sections', async () => {
      const action = {
        id: 'tailor-resume',
        label: 'Tailor Resume',
        description: 'Tailor resume for job',
        prompt: 'Tailor my resume for the frontend role at Acme',
      };
      const envelope = makeEnvelope({
        page: '/career/resume',
        hub: 'career',
        skill: 'resume',
        skillSummary: 'Resume management and tailoring',
        skillTools: ['career-tailor-resume', 'career-read-resume'],
        skillActions: ['tailor', 'review'],
        priority: 'rich',
        maxContextTokens: BUDGET_RICH,
        action,
      });
      mockResolveResponse(envelope);

      const result = await resolveContext('/career/resume', 'rich', action);
      const prompt = buildPromptFromEnvelope(result);

      // Rich budget should include everything
      expect(prompt).toContain('Page: /career/resume');
      expect(prompt).toContain('Hub: career');
      expect(prompt).toContain('Skill: resume');
      expect(prompt).toContain('Resume management and tailoring');
      expect(prompt).toContain('career-tailor-resume');
      expect(prompt).toContain('tailor, review');
      expect(prompt).toContain('Tailor my resume for the frontend role at Acme');
    });
  });

  // ─── Dispatch path: escalation (re-resolution) ─────────────────────────

  describe('escalation dispatch path', () => {
    it('Tier 2 re-resolves with standard priority and fresh page', async () => {
      // Tier 1 was on /consulting/pipeline
      const tier1Envelope = makeEnvelope({
        page: '/consulting/pipeline',
        hub: 'consulting',
        priority: 'minimal',
        maxContextTokens: BUDGET_MINIMAL,
      });
      mockResolveResponse(tier1Envelope);
      await resolveContext('/consulting/pipeline', 'minimal');

      // User navigated to /career/resume during Tier 1 execution
      const tier2Envelope = makeEnvelope({
        page: '/career/resume',
        hub: 'career',
        skill: 'resume',
        priority: 'standard',
        maxContextTokens: BUDGET_STANDARD,
      });
      mockResolveResponse(tier2Envelope);

      const result = await resolveContext('/career/resume', 'standard', {
        id: 'fix-t2',
        label: 'Fix',
        description: 'Re-run task',
        prompt: 'Fix it',
      });

      // Tier 2 should see the NEW page, not the stale Tier 1 page
      expect(result.page).toBe('/career/resume');
      expect(result.hub).toBe('career');
      expect(result.priority).toBe('standard');
    });

    it('Tier 3 re-resolves with rich priority', async () => {
      const tier3Action = {
        id: 'fix-t3',
        label: 'Fix (IDE)',
        description: 'Full IDE dispatch',
        prompt: 'Investigate and fix',
      };
      const tier3Envelope = makeEnvelope({
        page: '/career/resume',
        hub: 'career',
        skill: 'resume',
        priority: 'rich',
        maxContextTokens: BUDGET_RICH,
        action: tier3Action,
      });
      mockResolveResponse(tier3Envelope);

      const result = await resolveContext('/career/resume', 'rich', tier3Action);
      const prompt = buildPromptFromEnvelope(result);

      expect(result.priority).toBe('rich');
      expect(result.maxContextTokens).toBe(BUDGET_RICH);
      expect(prompt).toContain('Investigate and fix');
    });
  });

  // ─── Budget tier mapping ───────────────────────────────────────────────

  describe('budget tier mapping matches dispatch modes', () => {
    const cases: Array<[string, ContextPriority, number]> = [
      ['fire/oneshot → minimal', 'minimal', BUDGET_MINIMAL],
      ['chat → standard', 'standard', BUDGET_STANDARD],
      ['ide → rich', 'rich', BUDGET_RICH],
    ];

    it.each(cases)('%s maps to correct budget', (_label, priority, expected) => {
      expect(getBudgetForPriority(priority)).toBe(expected);
    });
  });

  // ─── Fallback behavior ────────────────────────────────────────────────

  describe('fallback on resolve-context failure', () => {
    it('returns fallback envelope when API returns non-ok', async () => {
      mockMcpCall.mockRejectedValueOnce(new Error('Internal error'));

      const result = await resolveContext('/productivity/notes', 'standard');

      // Should return a fallback envelope with the page path
      expect(result.page).toBe('/productivity/notes');
      expect(result.hub).toBe('productivity');
    });

    it('returns fallback envelope when MCP rejects', async () => {
      mockMcpCall.mockRejectedValueOnce(new Error('Network error'));

      await expect(resolveContext('/career/resume', 'rich')).resolves.toMatchObject({
        page: '/career/resume',
        hub: 'career',
        priority: 'rich',
      });
    });
  });
});
