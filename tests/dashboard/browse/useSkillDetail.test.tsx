/**
 * @jest-environment jsdom
 */
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock block registry
jest.mock('@/lib/blocks/generated-block-registry', () => ({
  BLOCK_REGISTRY: {
    'test-skill:block-1': {
      id: 'test-skill:block-1',
      type: 'stat-grid',
      title: 'Test Block',
      icon: 'Activity',
      configSchema: {},
      hub: 'test',
      skill: 'test-skill',
    },
  },
  BLOCK_LIST: [],
  getBlocksByHub: jest.fn(() => []),
}));

// Mock fetch for skill metadata with proper headers for safeJson
const mockResponseData = {
  skill: {
    id: 'test-skill',
    hub: 'test',
    title: 'Test Skill',
    icon: 'Puzzle',
    ownership: 'adopted',
    upstream: {
      source: 'claude-local',
      path: '.claude/skills/test-skill',
      version: '1.0.0',
    },
  },
  actions: [{ id: 'run-test', label: 'Run Test', dispatch: 'fire' }],
  mcpTools: [{ name: 'gmail-search', description: 'Search Gmail', schema: {} }],
  prompts: [{ id: 'draft', label: 'Draft', prompt: 'Draft the answer' }],
  commands: [{ id: 'test-skill', label: '/test-skill', command: '/test-skill' }],
  skillDoc: { hasSkillMd: true, skillDoc: '## Test Skill\nUse this skill.' },
  health: { status: 'healthy', errors24h: 3 },
};

const mockFetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve(mockResponseData),
    headers: new Headers({ 'content-type': 'application/json' }),
    status: 200,
    statusText: 'OK',
  }),
) as jest.Mock;
global.fetch = mockFetch;

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  };
}

describe('useSkillDetail', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  it('returns null when no skillId provided', async () => {
    const { useSkillDetail } = await import('@/lib/browse/useSkillDetail');
    const { result } = renderHook(() => useSkillDetail(null), {
      wrapper: createWrapper(),
    });
    expect(result.current.detail).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('normalises a skill:<source>:<name> capability id before fetching', async () => {
    // Regression for the /browse?skill=skill%3Aprivate-vault%3Avault bug:
    // useSearchParams round-trips the value as "skill:private-vault:vault" and
    // the hook used to hand that raw string to /api/skill-meta, which 404'd.
    const { useSkillDetail } = await import('@/lib/browse/useSkillDetail');
    const { result } = renderHook(
      () => useSkillDetail('skill:private-vault:test-skill'),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockFetch).toHaveBeenCalledWith('/api/skill-meta/test-skill');
    expect(result.current.detail?.skillId).toBe('test-skill');
    // Block lookup uses the same normalised id, so the registered block matches.
    expect(result.current.detail?.blocks).toHaveLength(1);
  });

  it('fetches and resolves skill detail with blocks from registry', async () => {
    const { useSkillDetail } = await import('@/lib/browse/useSkillDetail');
    const { result } = renderHook(() => useSkillDetail('test-skill'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.detail).not.toBeNull();
    expect(result.current.detail?.title).toBe('Test Skill');
    expect(result.current.detail?.description).toBe('Test Skill');
    expect(result.current.detail?.blocks).toHaveLength(1);
    expect(result.current.detail?.actions).toHaveLength(1);
    // 'docs' intentionally excluded: the raw markdown can't fit a flat
    // label/description card without breaking layout, and the dedicated
    // <Documentation> renderer below the capability profile already shows it.
    expect(result.current.detail?.capabilityProfileSections?.map((section) => section.id)).toEqual([
      'summary',
      'tools',
      'actions',
      'prompts',
      'commands',
      'health',
    ]);
    expect(result.current.detail?.capabilityProfileSections?.find((section) => section.id === 'summary')?.items).toEqual([
      { label: 'test-skill', description: 'Test Skill' },
    ]);
    expect(result.current.detail?.capabilityProfileSections?.find((section) => section.id === 'tools')?.items).toEqual([
      { label: 'gmail-search', description: 'Search Gmail' },
    ]);
    expect(result.current.detail?.capabilityProfileSections?.find((section) => section.id === 'actions')?.items).toEqual([
      { label: 'Run Test', metadata: { dispatch: 'fire' } },
    ]);
    expect(result.current.detail?.capabilityProfileSections?.find((section) => section.id === 'prompts')?.items).toEqual([
      { label: 'Draft', description: 'Draft the answer' },
    ]);
    expect(result.current.detail?.capabilityProfileSections?.find((section) => section.id === 'commands')?.items).toEqual([
      { label: '/test-skill', description: '/test-skill' },
    ]);
    expect(
      result.current.detail?.capabilityProfileSections?.find((section) => section.id === 'docs'),
    ).toBeUndefined();
    expect(result.current.detail?.capabilityProfileSections?.find((section) => section.id === 'health')?.items).toEqual([
      { label: 'healthy', metadata: { errors24h: '3' } },
    ]);
    expect(result.current.detail?.ownership).toBe('adopted');
    expect(result.current.detail?.upstream).toEqual({
      source: 'claude-local',
      path: '.claude/skills/test-skill',
      version: '1.0.0',
    });
  });
});
