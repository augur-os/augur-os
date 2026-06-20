/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { BrowseItem } from '@/lib/browse/types';

// Mock hooks
jest.mock('@/hooks/useActionRunner', () => ({
  useActionRunner: () => ({ runAction: jest.fn(), isExecuting: false }),
}));

jest.mock('@tanstack/react-query', () => {
  const actual = jest.requireActual('@tanstack/react-query');
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: jest.fn() }),
  };
});

const mockAdoptSkill = jest.fn();
const mockNoteClassificationUpdate = jest.fn();
let mockNoteClassificationError: string | null = null;
jest.mock('@/lib/mcp/useMcpMutation', () => {
  const React = jest.requireActual('react') as typeof import('react');
  return {
    useMcpMutation: (tool: string, opts?: { onSuccess?: (result: unknown) => void }) => {
      if (tool === 'note-classification-update') {
        const [error, setError] = React.useState<string | null>(mockNoteClassificationError);
        return {
          mutate: async (body: unknown) => {
            setError(null);
            try {
              const result = await mockNoteClassificationUpdate(body);
              opts?.onSuccess?.(result);
              return result;
            } catch (err) {
              const message = err instanceof Error ? err.message : String(err);
              setError(message);
              throw err;
            }
          },
          loading: false,
          error,
        };
      }
      return {
        mutate: mockAdoptSkill,
        loading: false,
        error: null,
      };
    },
  };
});

const mockMcpCall = jest.fn();
jest.mock('@/lib/mcp/client', () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

jest.mock('@/lib/blocks/generated-block-registry', () => ({
  BLOCK_REGISTRY: {},
  BLOCK_LIST: [],
  getBlocksByHub: jest.fn(() => []),
}), { virtual: true });

jest.mock('@/lib/blocks/useBlockData', () => ({
  useBlockData: () => ({
    data: null,
    loading: false,
    error: null,
    invalidate: jest.fn(),
    refetch: jest.fn(),
  }),
}));

jest.mock('@/components/shared/BrowseDetailActions', () => ({
  BrowseDetailActions: ({ actions }: { actions: Array<{ id: string; label: string }> }) => (
    <div data-testid="browse-detail-actions">
      {actions.map((action) => (
        <span key={action.id}>{action.label}</span>
      ))}
    </div>
  ),
}));

jest.mock('@/components/shared/BrowseBlockStack', () => ({
  BrowseBlockStack: () => <div data-testid="browse-block-stack" />,
}));

jest.mock('@/components/Markdown', () => ({
  __esModule: true,
  default: ({ markdown }: { markdown: string }) => (
    <div data-testid="markdown">{markdown}</div>
  ),
}));

jest.mock('@/lib/webmcp/useWebMCPReport', () => ({
  useWebMCPReport: jest.fn(),
  useWebMCPSubscribe: () => ({ configOverride: null, refetchSignal: 0 }),
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

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

describe('BrowseDetailPanel', () => {
  beforeEach(() => {
    mockAdoptSkill.mockClear();
    mockNoteClassificationUpdate.mockReset();
    mockNoteClassificationUpdate.mockResolvedValue({ success: true });
    mockNoteClassificationError = null;
    mockMcpCall.mockReset();
    mockMcpCall.mockImplementation(() => new Promise(() => {}));
  });

  it('renders skill title and close button', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const detail = {
      skillId: 'test',
      hub: 'dev',
      title: 'Test Skill',
      icon: 'Puzzle',
      description: 'A test skill',
      blocks: [],
      actions: [],
      ownership: 'augur',
    };
    const onClose = jest.fn();
    render(<BrowseDetailPanel detail={detail} onClose={onClose} />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText('Test Skill')).toBeInTheDocument();
    fireEvent.click(screen.getByTitle('Close (Esc)'));
    expect(onClose).toHaveBeenCalled();
  });

  it('renders action buttons when actions are provided', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const detail = {
      skillId: 'test',
      hub: 'dev',
      title: 'Test',
      icon: 'Puzzle',
      description: 'Test',
      blocks: [],
      actions: [{ id: 'run', label: 'Run Test', dispatch: 'fire' }],
      ownership: 'augur',
    };
    render(<BrowseDetailPanel detail={detail} onClose={jest.fn()} />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText('Run Test')).toBeInTheDocument();
  });

  it('renders generated skill item actions and routes AI/direct clicks', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const detail = {
      skillId: 'test',
      hub: 'dev',
      title: 'Test Skill',
      icon: 'Puzzle',
      description: 'Test',
      blocks: [],
      actions: [],
      ownership: 'augur',
    };
    const onItemPrompt = jest.fn();
    const onItemDirect = jest.fn();

    render(
      <BrowseDetailPanel
        detail={detail}
        onClose={jest.fn()}
        onItemPrompt={onItemPrompt}
        onItemDirect={onItemDirect}
      />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByRole('button', { name: 'Enhance' }));
    expect(onItemPrompt).toHaveBeenCalledWith(expect.stringContaining('Test Skill'));

    fireEvent.click(screen.getByRole('button', { name: 'Health' }));
    expect(onItemDirect).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'skill-health',
        tool: 'skill-resolvable-report',
      }),
      expect.objectContaining({
        id: 'test',
        title: 'Test Skill',
      }),
    );
  });

  it('renders problem evidence and chat action for inventory-backed file items', async () => {
    const onItemPrompt = jest.fn();
    const { BrowseItemDetailPanel } = await import('@/components/shared/BrowseDetailPanel');
    const item: BrowseItem = {
      id: 'codex-agent',
      title: 'Codex agent',
      description: 'agent profile',
      hub: 'system',
      typeBadge: 'agent-profile',
      path: '/repo/.codex/agents/dev.md',
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/repo/.codex/agents/dev.md',
      },
      metadata: {
        inventory_source: 'ai-artifact-inventory',
        problem_tags: 'unknown_source',
        problem_count: '1',
        problem_evidence:
          '[{"id":"unknown_source","severity":"warning","reason":"Scanner warning: unknown_source","source_path":"/repo/.codex/agents/dev.md"}]',
      },
    };

    render(
      <BrowseItemDetailPanel
        item={item}
        onClose={jest.fn()}
        category="agent-profiles"
        categoryLabel="Agent profile"
        onItemPrompt={onItemPrompt}
      />,
    );

    expect(screen.getByText('Problems')).toBeInTheDocument();
    expect(screen.getByText(/Scanner warning: unknown_source/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /send action items to chat/i }));
    expect(onItemPrompt.mock.calls[0][0]).toContain('Do not modify');
  });

  it('renders wiki maintenance status rows for no-apply freshness', async () => {
    const { BrowseItemDetailPanel } = await import('@/components/shared/BrowseDetailPanel');
    const item: BrowseItem = {
      id: 'concepts/wiki-freshness',
      title: 'Wiki Freshness',
      description: 'Maintenance status for the wiki surface.',
      typeBadge: 'Concept',
      path: '/wiki/concepts/wiki-freshness.md',
      primaryAction: {
        label: 'Read Wiki',
        type: 'open-file',
        target: '/wiki/concepts/wiki-freshness.md',
      },
      metadata: {
        pageType: 'concept',
        wikiMaintenanceVerdict: 'structure_ok_compile_backlog',
        wikiPendingSources: '1812',
        wikiSourceTotal: '1930',
        wikiLastReindexedAt: '2026-06-07T03:35:00+00:00',
        wikiLastBatchQuality: 'weak',
        wikiLastBatchReason:
          '19/20 low-signal sources; reindex refreshed Browse but no wiki pages were applied.',
      },
    };

    render(
      <BrowseItemDetailPanel
        item={item}
        onClose={jest.fn()}
        category="wiki"
        categoryLabel="Wiki"
      />,
    );

    expect(screen.getByText('Pending sources')).toBeInTheDocument();
    expect(screen.getByText('1812 / 1930')).toBeInTheDocument();
    expect(screen.getByText('Batch quality')).toBeInTheDocument();
    expect(screen.getByText('Weak')).toBeInTheDocument();
    expect(screen.getByText('Batch reason')).toBeInTheDocument();
    expect(screen.getByText(/no wiki pages were applied/)).toBeInTheDocument();
  });

  it('renders generated capability profile sections from skill detail', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const detail = {
      skillId: 'gmail-triage',
      hub: 'workspace',
      title: 'Gmail Triage',
      icon: 'Puzzle',
      description: 'Triage Gmail messages',
      blocks: [],
      actions: [],
      ownership: 'augur',
      capabilityProfileSections: [
        {
          id: 'integrations',
          title: 'Integrations',
          kind: 'integrations',
          items: [{ label: 'Gmail', description: 'connected' }],
        },
      ],
    };

    render(<BrowseDetailPanel detail={detail} onClose={jest.fn()} />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText('Integrations')).toBeInTheDocument();
    expect(screen.getByText('Gmail')).toBeInTheDocument();
    expect(screen.getByText('connected')).toBeInTheDocument();
  });

  it('shows health status badge', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const detail = {
      skillId: 'test',
      hub: 'dev',
      title: 'Test',
      icon: 'Puzzle',
      description: 'Test',
      blocks: [],
      actions: [],
      health: { status: 'healthy', errors24h: 0 },
      ownership: 'augur',
    };
    render(<BrowseDetailPanel detail={detail} onClose={jest.fn()} />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText('healthy')).toBeInTheDocument();
  });

  it('shows adopt CTA for external skills', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const detail = {
      skillId: 'external-skill',
      hub: 'dev',
      title: 'External Skill',
      icon: 'Puzzle',
      description: 'External',
      blocks: [],
      actions: [],
      ownership: 'external',
      source: 'claude-local',
    };

    render(<BrowseDetailPanel detail={detail} onClose={jest.fn()} />);

    expect(screen.getByRole('heading', { name: 'External Skill' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /adopt to augur/i }));
    expect(mockAdoptSkill).toHaveBeenCalledTimes(1);
  });

  it('shows upstream summary for adopted skills', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const detail = {
      skillId: 'adopted-skill',
      hub: 'dev',
      title: 'Adopted Skill',
      icon: 'Puzzle',
      description: 'Adopted',
      blocks: [],
      actions: [],
      ownership: 'adopted',
      source: 'claude-local',
      upstream: {
        source: 'claude-local',
        path: '.claude/skills/adopted-skill',
        version: '1.2.3',
      },
    };

    render(<BrowseDetailPanel detail={detail} onClose={jest.fn()} />);

    expect(screen.getByRole('heading', { name: 'Adopted Skill' })).toBeInTheDocument();
    expect(screen.getByText('Upstream')).toBeInTheDocument();
    expect(screen.getByText('claude-local')).toBeInTheDocument();
    expect(screen.getByText('.claude/skills/adopted-skill')).toBeInTheDocument();
  });

  it('does not offer direct edits for generated documentation exports', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const detail = {
      skillId: 'adr',
      hub: 'command',
      title: 'ADR',
      icon: 'Puzzle',
      description: 'Generated command wrapper',
      blocks: [],
      actions: [],
      ownership: 'augur',
      skillDoc: `---
name: adr
---
<!--
AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: skills/augur-core/commands/adr.md
-->

# ADR Command`,
    };

    render(<BrowseDetailPanel detail={detail} onClose={jest.fn()} />);

    expect(
      screen.queryByRole('button', { name: 'Edit markdown' }),
    ).not.toBeInTheDocument();
  });

  // ADR-748 Decision §4: trigger action wired in BrowseDetailPanel.
  it('renders the Prompts section with source badges and trigger buttons when onTriggerPrompt is provided', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const detail = {
      skillId: 'ingest',
      hub: 'workspace',
      title: 'Ingest',
      icon: 'Inbox',
      description: 'Capture sources',
      blocks: [],
      actions: [],
      ownership: 'augur',
      prompts: [
        {
          id: 'ingest:vault:morning-review',
          label: 'Morning review',
          description: 'Triage overnight inbox',
          prompt: 'Summarise items added since {{since}}',
          placeholders: ['since'],
          source: 'vault' as const,
        },
        {
          id: 'ingest:skill:digest',
          label: 'Skill digest',
          prompt: 'Run the digest now',
          source: 'skill' as const,
        },
      ],
    };
    const onTriggerPrompt = jest.fn();
    render(
      <BrowseDetailPanel
        detail={detail}
        onClose={jest.fn()}
        onTriggerPrompt={onTriggerPrompt}
      />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByText('Prompts')).toBeInTheDocument();
    expect(screen.getByText('Morning review')).toBeInTheDocument();
    expect(screen.getByText('Skill digest')).toBeInTheDocument();
    // Both source badges present and distinct.
    expect(screen.getByText('vault')).toBeInTheDocument();
    expect(screen.getByText('skill')).toBeInTheDocument();
  });

  it('omits the Prompts section when onTriggerPrompt is not wired', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const detail = {
      skillId: 'ingest',
      hub: 'workspace',
      title: 'Ingest',
      icon: 'Inbox',
      description: 'Capture sources',
      blocks: [],
      actions: [],
      ownership: 'augur',
      prompts: [
        {
          id: 'ingest:vault:foo',
          label: 'Foo',
          prompt: 'Do foo',
          source: 'vault' as const,
        },
      ],
    };
    render(<BrowseDetailPanel detail={detail} onClose={jest.fn()} />, {
      wrapper: createWrapper(),
    });
    expect(screen.queryByText('Prompts')).not.toBeInTheDocument();
  });

  it('renders voice-memo audio player and transcript pane', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item = {
      id: 'voice-memo',
      title: 'Voice memo',
      description: 'Personal note',
      hub: 'workspace',
      typeBadge: 'voice-memo',
      path: 'notes/voice.md',
      primaryAction: { label: 'Open', type: 'open-file' as const, target: 'notes/voice.md' },
      metadata: {
        audio_path: '/tmp/voice.m4a',
        duration_seconds: '72',
        provider: 'whisper-cpp',
        transcript: 'Hello there.',
      },
    };

    const { container } = render(<BrowseItemDetailPanel item={item} onClose={jest.fn()} />);
    expect(container.querySelector('audio')).toBeTruthy();
    expect(screen.getByText(/1 min/)).toBeInTheDocument();
    expect(screen.getByText(/Hello there/)).toBeInTheDocument();
  });

  it('renders an audio player for file-backed audio browse items', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item: BrowseItem = {
      id: 'audio-1',
      title: 'Meeting',
      description: 'M4A · Downloads',
      hub: 'downloads',
      icon: 'FileAudio',
      typeBadge: 'm4a',
      path: '~/Downloads/meeting.m4a',
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '~/Downloads/meeting.m4a',
      },
      metadata: { media_kind: 'audio', file_ext: 'm4a' },
    };

    render(
      <BrowseItemDetailPanel
        item={item}
        onClose={jest.fn()}
        category="documents"
        categoryLabel="Documents"
      />,
    );

    const player = screen.getByLabelText('Audio preview');
    expect(player).toHaveAttribute(
      'src',
      `/api/vault-asset?path=${encodeURIComponent(item.path!)}`,
    );
    expect(screen.getByRole('button', { name: /open file/i })).toBeInTheDocument();
  });

  it('preserves mcp-tool primary action args from the item detail panel', async () => {
    mockMcpCall.mockResolvedValue({ success: true, message: 'ok' });
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const sourcePath =
      '~/Projects/Augur/project-brain/capabilities/skills/ingest/SKILL.md';
    const item: BrowseItem = {
      id: 'skill:ingest',
      title: 'Ingest',
      description: 'Local-first file inbox ingestion for Brain',
      hub: 'brain',
      icon: 'FileText',
      typeBadge: 'skill',
      path: sourcePath,
      primaryAction: {
        label: 'Run',
        type: 'mcp-tool',
        target: 'get-skill-health',
        args: {
          skill: 'ingest',
          source_path: sourcePath,
        },
      },
      metadata: {},
    };

    render(
      <BrowseItemDetailPanel
        item={item}
        onClose={jest.fn()}
        category="skills"
        categoryLabel="Skills"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /^run$/i }));

    await waitFor(() => {
      expect(mockMcpCall).toHaveBeenCalledWith(
        'get-skill-health',
        {
          skill: 'ingest',
          source_path: sourcePath,
        },
      );
    });
  });

  it('surfaces command quality and KPI metadata in the shared item detail panel', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item: BrowseItem = {
      id: 'command:ask',
      title: '/ask',
      description: 'Ask the project brain',
      hub: 'command',
      icon: 'Terminal',
      typeBadge: 'command',
      path: 'command://ask',
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: 'command://ask',
      },
      metadata: {
        qualityTier: 'A',
        qualityScore: '88',
        docsScore: '80',
        wiringScore: '100',
        kpiStatus: 'pass',
      },
    };

    render(
      <BrowseItemDetailPanel
        item={item}
        onClose={jest.fn()}
        category="commands"
        categoryLabel="Commands"
      />,
    );

    expect(screen.getByText('Quality A 88')).toBeInTheDocument();
    expect(screen.getByText('80')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('pass')).toBeInTheDocument();
  });

  it('renders a video player for file-backed video browse items', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item: BrowseItem = {
      id: 'video-1',
      title: 'Demo',
      description: 'MP4 · Desktop',
      hub: 'desktop',
      icon: 'FileVideo',
      typeBadge: 'mp4',
      path: '~/Desktop/demo.mp4',
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '~/Desktop/demo.mp4',
      },
      metadata: { media_kind: 'video', file_ext: 'mp4' },
    };

    render(
      <BrowseItemDetailPanel
        item={item}
        onClose={jest.fn()}
        category="documents"
        categoryLabel="Documents"
      />,
    );

    const player = screen.getByLabelText('Video preview');
    expect(player.tagName.toLowerCase()).toBe('video');
    expect(player).toHaveAttribute(
      'src',
      `/api/vault-asset?path=${encodeURIComponent(item.path!)}`,
    );
  });

  it('renders meeting attendees and transcript', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item = {
      id: 'meeting',
      title: 'Q2 Planning',
      description: 'Meeting note',
      hub: 'workspace',
      typeBadge: 'meeting',
      path: 'notes/meeting.md',
      primaryAction: { label: 'Open', type: 'open-file' as const, target: 'notes/meeting.md' },
      metadata: {
        audio_path: '/tmp/q2.mp4',
        duration_seconds: '2280',
        attendee_count: '2',
        attendee_slugs: 'sasha-chen,priya-rao',
        provider: 'whisper-cpp',
        transcript: '[Sasha] hi.',
      },
    };

    render(<BrowseItemDetailPanel item={item} onClose={jest.fn()} />);
    expect(screen.getByText('sasha-chen')).toBeInTheDocument();
    expect(screen.getByText('priya-rao')).toBeInTheDocument();
    expect(screen.getByText(/Merge to timeline/)).toBeInTheDocument();
    expect(screen.getByText(/\[Sasha\] hi\./)).toBeInTheDocument();
  });

  it('keeps Enrich off non-article note detail panels when generated actions are wired', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item: BrowseItem = {
      id: 'note:thought:example',
      title: 'Loose thought',
      description: 'Thought note',
      hub: 'workspace',
      icon: 'MessageSquare',
      typeBadge: 'thought',
      path: '/v/notes/thought.md',
      metadata: {
        'x-augur-note-type': 'thought',
      },
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/v/notes/thought.md',
      },
    };
    const onItemPrompt = jest.fn();
    const onItemDirect = jest.fn();

    render(
      <BrowseItemDetailPanel
        item={item}
        category="notes"
        onClose={jest.fn()}
        onItemPrompt={onItemPrompt}
        onItemDirect={onItemDirect}
      />,
    );

    expect(screen.queryByRole('button', { name: 'Enrich' })).not.toBeInTheDocument();
  });

  it('routes generated article note enrichment through an AI prompt from the note detail panel', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item: BrowseItem = {
      id: 'note:url:example',
      title: 'Example article',
      description: 'Saved URL note',
      hub: 'workspace',
      icon: 'Link2',
      typeBadge: 'url',
      path: '/v/notes/example.md',
      metadata: {
        'x-augur-note-type': 'url',
        enrichment_status: 'raw',
      },
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/v/notes/example.md',
      },
    };
    const onItemPrompt = jest.fn();
    const onItemDirect = jest.fn();

    render(
      <BrowseItemDetailPanel
        item={item}
        category="notes"
        onClose={jest.fn()}
        onItemPrompt={onItemPrompt}
        onItemDirect={onItemDirect}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Enrich' }));
    expect(onItemPrompt).toHaveBeenCalledWith(expect.stringContaining('submit-enrich-article-result'));
    expect(onItemPrompt).toHaveBeenCalledWith(expect.stringContaining('/v/notes/example.md'));
    expect(onItemDirect).not.toHaveBeenCalled();
    expect(mockMcpCall).not.toHaveBeenCalledWith('enrich-article', expect.anything());
  });

  it('surfaces enriched article sections from note metadata when present', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item: BrowseItem = {
      id: 'note:file:report',
      title: 'Research report',
      description: 'Saved file note',
      hub: 'workspace',
      icon: 'File',
      typeBadge: 'file',
      path: '/v/notes/report.md',
      metadata: {
        'x-augur-note-type': 'file',
        enrichment_status: 'enriched',
        executive_summary: 'This report explains the operating model.',
        key_insights: 'Local-first capture keeps provenance close to the note.',
      },
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/v/notes/report.md',
      },
    };

    render(<BrowseItemDetailPanel item={item} onClose={jest.fn()} />);

    expect(screen.getByText('Article Enrichment')).toBeInTheDocument();
    expect(screen.getByText('Executive summary')).toBeInTheDocument();
    expect(screen.getByText('This report explains the operating model.')).toBeInTheDocument();
    expect(screen.getByText('Key insights')).toBeInTheDocument();
  });

  it('renders note classification controls and saves through MCP', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const user = userEvent.setup();
    const item: BrowseItem = {
      id: 'note:job',
      title: 'AI Engineer',
      description: 'Job note',
      hub: 'workspace',
      icon: 'BookOpen',
      path: '/vault/notes/job.md',
      typeBadge: 'url',
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/vault/notes/job.md',
      },
      metadata: {
        'x-augur-note-type': 'url',
        'x-augur-domain': 'jobs',
        'x-augur-source': 'linkedin',
        'x-augur-status': 'saved',
        'x-augur-classification-confidence': 'high',
      },
    };

    render(
      <BrowseItemDetailPanel
        item={item}
        category="notes"
        categoryLabel="Notes"
        categoryIcon="BookOpen"
        onClose={jest.fn()}
      />,
    );

    expect(screen.getByText('Classification')).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Domain'), 'projects');
    await user.selectOptions(screen.getByLabelText('Source'), 'github');
    await user.selectOptions(screen.getByLabelText('Status'), 'watching');
    await user.click(screen.getByRole('button', { name: 'Save classification' }));

    expect(mockNoteClassificationUpdate).toHaveBeenCalledWith({
      note_path: '/vault/notes/job.md',
      domain: 'projects',
      source: 'github',
      status: 'watching',
      classification_confidence: 'high',
    });
    expect(screen.getByText('Saved', { selector: 'span' })).toBeInTheDocument();
  });

  it('resets note classification controls when the selected note changes', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const user = userEvent.setup();
    const firstItem: BrowseItem = {
      id: 'note:job',
      title: 'AI Engineer',
      description: 'Job note',
      hub: 'workspace',
      icon: 'BookOpen',
      path: '/vault/notes/job.md',
      typeBadge: 'url',
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/vault/notes/job.md',
      },
      metadata: {
        'x-augur-note-type': 'url',
        'x-augur-domain': 'jobs',
        'x-augur-source': 'linkedin',
        'x-augur-status': 'saved',
      },
    };
    const secondItem: BrowseItem = {
      id: 'note:repo',
      title: 'Repository Watch',
      description: 'Project note',
      hub: 'workspace',
      icon: 'BookOpen',
      path: '/vault/notes/repo.md',
      typeBadge: 'url',
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/vault/notes/repo.md',
      },
      metadata: {
        'x-augur-note-type': 'url',
        'x-augur-domain': 'projects',
        'x-augur-source': 'github',
        'x-augur-status': 'watching',
      },
    };

    const { rerender } = render(
      <BrowseItemDetailPanel
        item={firstItem}
        category="notes"
        categoryLabel="Notes"
        categoryIcon="BookOpen"
        onClose={jest.fn()}
      />,
    );

    expect(screen.getByLabelText('Domain')).toHaveValue('jobs');
    expect(screen.getByLabelText('Source')).toHaveValue('linkedin');
    expect(screen.getByLabelText('Status')).toHaveValue('saved');

    rerender(
      <BrowseItemDetailPanel
        item={secondItem}
        category="notes"
        categoryLabel="Notes"
        categoryIcon="BookOpen"
        onClose={jest.fn()}
      />,
    );

    expect(screen.getByText('Repository Watch')).toBeInTheDocument();
    expect(screen.getByLabelText('Domain')).toHaveValue('projects');
    expect(screen.getByLabelText('Source')).toHaveValue('github');
    expect(screen.getByLabelText('Status')).toHaveValue('watching');

    await user.click(screen.getByRole('button', { name: 'Save classification' }));

    expect(mockNoteClassificationUpdate).toHaveBeenCalledWith({
      note_path: '/vault/notes/repo.md',
      domain: 'projects',
      source: 'github',
      status: 'watching',
      classification_confidence: 'high',
    });
  });

  it('shows correction failure without changing the visible note', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const user = userEvent.setup();
    mockNoteClassificationUpdate.mockResolvedValue({ success: false, error: 'invalid domain: unknown' });
    const item: BrowseItem = {
      id: 'note:bad',
      title: 'Bad',
      description: 'Bad note',
      hub: 'workspace',
      icon: 'BookOpen',
      path: '/vault/notes/bad.md',
      typeBadge: 'url',
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/vault/notes/bad.md',
      },
      metadata: {
        'x-augur-note-type': 'url',
        'x-augur-domain': 'research',
        'x-augur-source': 'website',
      },
    };

    render(
      <BrowseItemDetailPanel
        item={item}
        category="notes"
        categoryLabel="Notes"
        categoryIcon="BookOpen"
        onClose={jest.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Save classification' }));

    expect(mockNoteClassificationUpdate).toHaveBeenCalledWith({
      note_path: '/vault/notes/bad.md',
      domain: 'research',
      source: 'website',
      status: '',
      classification_confidence: 'high',
    });
    expect(await screen.findByText('invalid domain: unknown')).toBeInTheDocument();
    expect(screen.getByText('Bad')).toBeInTheDocument();
    expect(screen.queryByText('Saved', { selector: 'span' })).not.toBeInTheDocument();
  });

  it('does not render note classification controls for profile memory entries', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item: BrowseItem = {
      id: 'profile:memory',
      title: 'Standing preference',
      description: 'Profile memory',
      hub: 'workspace',
      icon: 'User',
      path: '/vault/profile/preference.md',
      typeBadge: 'memory-entry',
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/vault/profile/preference.md',
      },
      metadata: {
        kind: 'memory-entry',
        source: 'personal-profile',
      },
    };

    render(
      <BrowseItemDetailPanel
        item={item}
        category="profile"
        categoryLabel="Profile"
        categoryIcon="User"
        onClose={jest.fn()}
      />,
    );

    expect(screen.queryByRole('button', { name: 'Save classification' })).not.toBeInTheDocument();
  });

  it('does not render note classification controls for profile-shaped items in notes', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item: BrowseItem = {
      id: 'note:profile-memory',
      title: 'Misfiled profile memory',
      description: 'Profile memory in notes results',
      hub: 'workspace',
      icon: 'User',
      path: '/vault/profile/misfiled.md',
      typeBadge: 'memory-entry',
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/vault/profile/misfiled.md',
      },
      metadata: {
        kind: 'memory-entry',
        'x-augur-note-type': 'thought',
        'x-augur-domain': 'people',
        'x-augur-source': 'linkedin',
      },
    };

    render(
      <BrowseItemDetailPanel
        item={item}
        category="notes"
        categoryLabel="Notes"
        categoryIcon="BookOpen"
        onClose={jest.fn()}
      />,
    );

    expect(screen.queryByRole('button', { name: 'Save classification' })).not.toBeInTheDocument();
  });

  // Rule 32 (ADR-813): demo runbooks ride the owning skill's card — the panel
  // renders a Demos section from the skills-index `demos` metadata.
  it('renders a Demos section when the skill card metadata carries demos', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const { parseSkillDemos } = await import('@/lib/browse/cardModel');
    const detail = {
      skillId: 'skill:project-brain:ingest',
      hub: 'brain',
      title: 'Ingest',
      icon: 'Inbox',
      description: 'Capture sources',
      blocks: [],
      actions: [],
      ownership: 'augur',
    };
    const demos = parseSkillDemos(
      'Wiki Llm Cross Agent Ask|project-brain/capabilities/skills/ingest/demos/demo_01_wiki_llm_cross_agent_ask.md,' +
        'Compound Dry Run|project-brain/capabilities/skills/ingest/demos/demo_04_compound_dry_run.md',
    );

    render(
      <BrowseDetailPanel detail={detail} onClose={jest.fn()} demos={demos} />,
      { wrapper: createWrapper() },
    );

    expect(screen.getByTestId('skill-demos')).toBeInTheDocument();
    expect(screen.getByText('Demos')).toBeInTheDocument();
    expect(screen.getByText('Wiki Llm Cross Agent Ask')).toBeInTheDocument();
    expect(screen.getByText('Compound Dry Run')).toBeInTheDocument();
  });

  it('renders no Demos section when the skill has no demos metadata', async () => {
    const { BrowseDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const { parseSkillDemos } = await import('@/lib/browse/cardModel');
    const detail = {
      skillId: 'skill:project-brain:knowledge',
      hub: 'brain',
      title: 'Knowledge',
      icon: 'Book',
      description: 'Search memory',
      blocks: [],
      actions: [],
      ownership: 'augur',
    };

    render(
      <BrowseDetailPanel
        detail={detail}
        onClose={jest.fn()}
        demos={parseSkillDemos(undefined)}
      />,
      { wrapper: createWrapper() },
    );

    expect(screen.queryByTestId('skill-demos')).not.toBeInTheDocument();
    expect(screen.queryByText('Demos')).not.toBeInTheDocument();
  });

  it('renders the markdown source preview for file notes in the notes category', async () => {
    const { BrowseItemDetailPanel } = await import(
      '@/components/shared/BrowseDetailPanel'
    );
    const item: BrowseItem = {
      id: 'note:file:demo-01',
      title: 'Workflow Example 01 Cross-Agent Wiki Compounding',
      description: 'Saved workflow example proof card',
      hub: 'workspace',
      icon: 'File',
      typeBadge: 'file',
      path: '/v/notes/examples/artifacts/demo-01-wiki-llm-cross-agent-ask.md',
      metadata: {
        'x-augur-note-type': 'file',
        enrichment_status: 'raw',
      },
      primaryAction: {
        label: 'Open',
        type: 'open-file',
        target: '/v/notes/examples/artifacts/demo-01-wiki-llm-cross-agent-ask.md',
      },
    };
    mockMcpCall.mockResolvedValueOnce({
      content: `---
title: Workflow Example 01 Cross-Agent Wiki Compounding
---

# Workflow Example 01: Cross-Agent Wiki Compounding

## Bottom Line
Augur turns repeated ask answers into a source-backed workflow example judges can read.
`,
    });

    render(
      <BrowseItemDetailPanel
        item={item}
        category="notes"
        onClose={jest.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockMcpCall).toHaveBeenCalledWith('file-read', {
        path: '/v/notes/examples/artifacts/demo-01-wiki-llm-cross-agent-ask.md',
      });
    });
    expect(screen.getByText('Preview')).toBeInTheDocument();
    expect(
      await screen.findByText(/source-backed workflow example judges can read/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/title: Workflow Example 01/)).not.toBeInTheDocument();
  });
});
