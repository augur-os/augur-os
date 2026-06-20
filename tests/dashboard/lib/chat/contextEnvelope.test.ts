/**
 * ADR-161: Unit tests for ContextEnvelope assembly and budget truncation.
 */

import {
  estimateTokens,
  buildPromptFromEnvelope,
  getBudgetForPriority,
  BUDGET_MINIMAL,
  BUDGET_STANDARD,
  BUDGET_RICH,
  type ContextEnvelope,
} from '@/lib/chat/context-envelope';

// ─── estimateTokens ──────────────────────────────────────────────────────────

describe('estimateTokens', () => {
  it('returns chars/4 rounded up', () => {
    expect(estimateTokens('hello')).toBe(2);     // 5/4 = 1.25 → 2
    expect(estimateTokens('12345678')).toBe(2);   // 8/4 = 2
    expect(estimateTokens('')).toBe(0);
  });
});

// ─── getBudgetForPriority ────────────────────────────────────────────────────

describe('getBudgetForPriority', () => {
  it('returns correct budget for each tier', () => {
    expect(getBudgetForPriority('minimal')).toBe(BUDGET_MINIMAL);
    expect(getBudgetForPriority('standard')).toBe(BUDGET_STANDARD);
    expect(getBudgetForPriority('rich')).toBe(BUDGET_RICH);
  });

  it('budget ordering: minimal < standard < rich', () => {
    expect(BUDGET_MINIMAL).toBeLessThan(BUDGET_STANDARD);
    expect(BUDGET_STANDARD).toBeLessThan(BUDGET_RICH);
  });
});

// ─── buildPromptFromEnvelope ─────────────────────────────────────────────────

function makeEnvelope(overrides: Partial<ContextEnvelope> = {}): ContextEnvelope {
  return {
    sessionId: 'test-session',
    timestamp: Date.now(),
    page: '/productivity/notes',
    hub: 'productivity',
    skill: 'apple',
    skillSummary: 'Manages Apple Notes, Reminders, and Calendar.',
    skillDataDir: '/path/to/augur/data',
    skillTools: ['apple-read-notes', 'apple-create-note'],
    skillActions: ['quick-capture', 'search-notes'],
    action: null,
    projectIdentity: 'Augur is a local-first personal knowledge and automation system.',
    maxContextTokens: BUDGET_RICH,
    priority: 'rich',
    ...overrides,
  };
}

describe('buildPromptFromEnvelope', () => {
  it('includes page and hub for any budget', () => {
    const result = buildPromptFromEnvelope(makeEnvelope({ maxContextTokens: BUDGET_MINIMAL }));
    expect(result).toContain('Page: /productivity/notes');
    expect(result).toContain('Hub: productivity');
  });

  it('includes skill name when present', () => {
    const result = buildPromptFromEnvelope(makeEnvelope());
    expect(result).toContain('Skill: apple');
  });

  it('includes action prompt when present', () => {
    const result = buildPromptFromEnvelope(makeEnvelope({
      action: { id: 'test', label: 'Test Action', description: 'A test', prompt: 'Do the thing' },
    }));
    expect(result).toContain('## Task');
    expect(result).toContain('Do the thing');
  });

  it('includes skill summary with rich budget', () => {
    const result = buildPromptFromEnvelope(makeEnvelope({ maxContextTokens: BUDGET_RICH }));
    expect(result).toContain('Manages Apple Notes');
  });

  it('includes tool list with rich budget', () => {
    const result = buildPromptFromEnvelope(makeEnvelope({ maxContextTokens: BUDGET_RICH }));
    expect(result).toContain('apple-read-notes');
    expect(result).toContain('apple-create-note');
  });

  it('includes action list with rich budget', () => {
    const result = buildPromptFromEnvelope(makeEnvelope({ maxContextTokens: BUDGET_RICH }));
    expect(result).toContain('quick-capture');
    expect(result).toContain('search-notes');
  });

  it('handles no skill gracefully', () => {
    const result = buildPromptFromEnvelope(makeEnvelope({
      skill: null,
      skillSummary: null,
      skillDataDir: null,
      skillTools: [],
      skillActions: [],
    }));
    expect(result).toContain('Page: /productivity/notes');
    expect(result).toContain('Hub: productivity');
    expect(result).not.toContain('Skill:');
  });

  it('handles no action gracefully', () => {
    const result = buildPromptFromEnvelope(makeEnvelope({ action: null }));
    expect(result).not.toContain('## Task');
  });

  it('respects budget by cutting low-priority sections first', () => {
    // With a very small budget, project identity (priority 1) should be cut
    const result = buildPromptFromEnvelope(makeEnvelope({
      maxContextTokens: 30, // Very tight — only room for routing + maybe action
      action: { id: 'x', label: 'X', description: 'X', prompt: 'Do X' },
    }));
    // Core routing (priority 5) and action (priority 4) should survive
    expect(result).toContain('Page:');
    expect(result).toContain('Do X');
    // Project identity (priority 1) should be cut
    expect(result).not.toContain('## Project');
  });

  it('preserves priority ordering in output (highest first)', () => {
    const result = buildPromptFromEnvelope(makeEnvelope({
      maxContextTokens: BUDGET_RICH,
      action: { id: 'x', label: 'X', description: 'X', prompt: 'Task prompt here' },
    }));
    const pagePos = result.indexOf('Page:');
    const taskPos = result.indexOf('## Task');
    // Page (priority 5) should come before Task (priority 4)
    expect(pagePos).toBeLessThan(taskPos);
  });
});
