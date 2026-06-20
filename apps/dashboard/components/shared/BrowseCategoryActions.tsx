'use client';

import React, { useState, useCallback, useReducer } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { SlidersHorizontal } from 'lucide-react';
import { mcpCall } from '@/lib/mcp/client';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { runCliExecPrompt } from '@/lib/browse/cliExecClient';
import type { ViewMode, BrowseCategory } from '@/lib/browse/types';
import { BrowseOverflowMenu, type BrowseOverflowMenuItem } from '@/components/shared/BrowseOverflowMenu';
// eslint-disable-next-line no-restricted-imports -- ADR-490 shell exception until AddSkillModal is extracted to framework/shared
import { AddSkillModal } from '@/features/browse/AddSkillModal';

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */

interface BrowseCategoryActionsProps {
  category: ViewMode;
  activeCategory: BrowseCategory;
  itemCount: number;
  onRefetch: () => void;
  projectQuestionAction?: {
    label: string;
    onSelect: () => void;
    disabled?: boolean;
  };
  onAddContent?: () => void;
  onSweepVisible?: () => void;
  sweeping?: boolean;
  onReindex?: () => void;
  reindexing?: boolean;
  onAttachDocumentSource?: () => void;
}

type RoutineRefreshState = {
  codex: boolean;
  cloud: boolean;
};

type RoutineRefreshAction =
  | { type: 'start'; target: keyof RoutineRefreshState }
  | { type: 'finish'; target: keyof RoutineRefreshState };

function routineRefreshReducer(
  state: RoutineRefreshState,
  action: RoutineRefreshAction,
): RoutineRefreshState {
  return { ...state, [action.target]: action.type === 'start' };
}

/* ------------------------------------------------------------------ */
/*  Skills form                                                        */
/* ------------------------------------------------------------------ */

function SkillsForm({ onRefetch, onClose }: { onRefetch: () => void; onClose: () => void }) {
  const [title, setTitle] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (!title.trim() || !sourceUrl.trim()) {
      toast.error('Skill title and source URL are required');
      return;
    }
    setSubmitting(true);
    try {
      const data = await mcpCall<{ error?: string }>(
        'browse-index',
        { action: 'import', title: title.trim(), source_url: sourceUrl.trim(), description: description.trim() || undefined },
      );
      if (data.error) { toast.error(data.error || 'Failed to add discovery'); return; }
      toast.success('Discovery added to catalog');
      setTitle(''); setSourceUrl(''); setDescription('');
      onClose();
      onRefetch();
    } catch { toast.error('Network error'); }
    finally { setSubmitting(false); }
  }, [title, sourceUrl, description, onRefetch, onClose]);

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 space-y-3 max-w-xl">
      <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Skill Title (e.g., Sonos Extended Controls)" aria-label="Skill Title" className="w-full px-3 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50" />
      <input type="text" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="Source URL (https://github.com/user/repo or ...)" aria-label="Source URL" className="w-full px-3 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50" />
      <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description (optional) — What this skill does and why it is useful" aria-label="Description" rows={3} className="w-full px-3 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50" />
      <div className="flex gap-2">
        <button type="button" onClick={handleSubmit} disabled={submitting} className="min-h-[44px] px-3 py-1.5 rounded-lg text-sm font-medium bg-[var(--accent-primary)] text-white hover:opacity-90 disabled:opacity-50 transition-opacity cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-secondary)]">{submitting ? 'Adding...' : 'Add Discovery'}</button>
        <button type="button" onClick={onClose} className="min-h-[44px] px-3 py-1.5 rounded-lg text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50">Cancel</button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  API Routes stats                                                   */
/* ------------------------------------------------------------------ */

interface RoutesStats {
  stats: {
    total: number;
    byStatus: { migrated: number; legacy: number; unknown?: number };
  };
}

export function ApiRoutesStats({ itemCount }: { itemCount: number }) {
  const { data } = useMcpQuery<RoutesStats>('browse-api-routes-stats', 'get-api-route-stats', 'config', {
    fallback: { stats: { total: 0, byStatus: { migrated: 0, legacy: 0 } } } as RoutesStats,
  });
  const [isExecuting, setIsExecuting] = useState(false);

  const handleAudit = () => {
    if (isExecuting) return;
    setIsExecuting(true);
    const toastId = toast.loading('Running API architecture audit...');
    void runCliExecPrompt(
      'Audit all API routes in apps/dashboard/app/api/ for MCP-first architecture compliance. Check callMCPTool usage, error handling, and identify legacy routes to prioritize.',
    )
      .then(() => toast.success('API architecture audit completed', { id: toastId }))
      .catch((error) => {
        const message = error instanceof Error ? error.message : 'Audit failed';
        toast.error(message, { id: toastId });
      })
      .finally(() => setIsExecuting(false));
  };

  const total = data?.stats?.total ?? itemCount;
  const migrated = data?.stats?.byStatus?.migrated ?? 0;
  const legacy = data?.stats?.byStatus?.legacy ?? 0;
  const unknown = total - migrated - legacy;

  return (
    <div className="flex items-center gap-4 text-sm">
      <span className="text-[var(--text-secondary)]"><span className="font-medium text-[var(--text-primary)]">{total}</span> routes</span>
      <span className="text-[var(--accent-success)]"><span className="font-medium">{migrated}</span> migrated</span>
      <span className="text-[var(--accent-warning)]"><span className="font-medium">{legacy}</span> legacy</span>
      {unknown > 0 && <span className="text-[var(--text-secondary)]"><span className="font-medium">{unknown}</span> unknown</span>}
      <button type="button" onClick={handleAudit} disabled={isExecuting} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border border-[var(--accent-primary)]/30 hover:bg-[var(--accent-primary)]/20 disabled:opacity-50 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50">Architecture Audit</button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  CLI prompt map for generic "New" actions                            */
/* ------------------------------------------------------------------ */

const NEW_ACTION_PROMPTS: Partial<Record<ViewMode, string>> = {
  notes: 'Create a new note in the vault. Ask me what should be captured and which note type fits it.',
  archive: 'Archive an item. Ask me what should be archived and what retention or retrieval context should be preserved.',
  skills: 'Create a new skill in the Augur project. Ask me what the skill should do, which hub/bundle it belongs to, and what capabilities it needs.',
  pages: 'Create a new dashboard page or HTML artifact. Ask me which hub and skill it should belong to and what content it should show.',
  wiki: 'Bootstrap or repair the Augur wiki from current knowledge sources. If no wiki exists, build it. If it exists, repair and harden it instead of starting from blank creation.',
  'mcp-tools': 'Create a new MCP tool. Ask me what it should do and which skill it belongs to.',
  'mcp-servers': 'Create a new MCP server definition. Ask me what service it exposes, which tools it owns, and how it should be configured.',
  integrations: 'Set up a new integration. Ask me which service to integrate and what capabilities are needed.',
  commands: 'Create a new command doc. Ask me what it should do and which skill command folder it belongs to.',
  'agent-profiles': 'Create a new agent configuration. Ask me what model, tools, and instructions it should have.',
  'background-routines': 'Create a new background routine. Ask me what should run, what trigger owns it, and how cadence, cost, and failures should be surfaced.',
  tests: 'Create a new test file. Ask me what module or feature to test.',
  'api-routes': 'Create a new API route. Ask me what endpoint and methods it should support.',
  scripts: 'Create a new script. Ask me what it should automate.',
  logs: 'Create a new log source entry. Ask me which runtime or service should be tracked and where logs are stored.',
  'system-metadata': 'Create or repair system metadata. Ask me what metadata surface is missing and which scanner or registry should own it.',
};

/* ------------------------------------------------------------------ */
/*  Main export                                                        */
/* ------------------------------------------------------------------ */

/**
 * Builds the category-specific action items + owns the AddSkillModal. Returned
 * as data so the items can render inside the unified Browse context popover
 * (the single header button) rather than a standalone "Manage" menu.
 */
export function useBrowseCategoryActions({
  category,
  activeCategory,
  itemCount,
  onRefetch,
  projectQuestionAction,
  onAddContent,
  onSweepVisible,
  sweeping = false,
  onReindex,
  reindexing = false,
  onAttachDocumentSource,
}: BrowseCategoryActionsProps): { items: BrowseOverflowMenuItem[]; modal: React.ReactNode } {
  const [addSkillOpen, setAddSkillOpen] = useState(false);
  const [routineRefresh, dispatchRoutineRefresh] = useReducer(routineRefreshReducer, {
    codex: false,
    cloud: false,
  });
  const { push } = useRouter();
  const wikiAction = category === 'wiki';
  const newLabel = wikiAction ? 'New Wiki' : `New ${activeCategory.singularLabel}`;

  const handleRefreshCodex = useCallback(async () => {
    if (routineRefresh.codex) return;
    dispatchRoutineRefresh({ type: 'start', target: 'codex' });
    const toastId = toast.loading('Rescanning Codex automations...');
    try {
      const data = await mcpCall<{ success: boolean; count?: number; error?: string }>(
        'routine-refresh-codex',
        {},
      );
      if (data.success === false) {
        toast.error(data.error || 'Refresh failed', { id: toastId });
        return;
      }
      toast.success(`Codex routines refreshed (${data.count ?? 0} found)`, { id: toastId });
      onRefetch();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Network error';
      toast.error(message, { id: toastId });
    } finally {
      dispatchRoutineRefresh({ type: 'finish', target: 'codex' });
    }
  }, [routineRefresh.codex, onRefetch]);

  const handleRefreshCloud = useCallback(async () => {
    if (routineRefresh.cloud) return;
    dispatchRoutineRefresh({ type: 'start', target: 'cloud' });
    const toastId = toast.loading('Refreshing Claude cloud routines (spawning claude CLI)...');
    try {
      const data = await mcpCall<{ success: boolean; count?: number; error?: string }>(
        'routine-refresh-cloud',
        {},
      );
      if (data.success === false) {
        toast.error(data.error || 'Cloud refresh failed', { id: toastId });
        return;
      }
      toast.success(`Cloud routines refreshed (${data.count ?? 0} cached)`, { id: toastId });
      onRefetch();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Network error';
      toast.error(message, { id: toastId });
    } finally {
      dispatchRoutineRefresh({ type: 'finish', target: 'cloud' });
    }
  }, [routineRefresh.cloud, onRefetch]);

  const runBrowsePrompt = useCallback((label: string, prompt: string) => {
    const toastId = toast.loading(`Running ${label}...`);
    void runCliExecPrompt(prompt)
      .then(() => toast.success(`${label} completed`, { id: toastId }))
      .catch((error) => {
        const message = error instanceof Error ? error.message : `${label} failed`;
        toast.error(message, { id: toastId });
      });
  }, []);

  const handleNew = useCallback(() => {
    if (category === 'skills') {
      setAddSkillOpen(true);
      return;
    }
    const prompt = NEW_ACTION_PROMPTS[category];
    if (prompt) {
      runBrowsePrompt(newLabel, prompt);
    }
  }, [category, newLabel, runBrowsePrompt]);

  const handleSkillsAction = useCallback((_actionId: string, label: string, prompt: string) => {
    runBrowsePrompt(label, prompt);
  }, [runBrowsePrompt]);

  const handleOpenSkillsSettings = useCallback(() => {
    push('/settings/skills');
  }, [push]);

  const menuItems: BrowseOverflowMenuItem[] = [];
  if (category === 'skills') {
    menuItems.push(
      {
        id: 'skills-add',
        label: 'Add skill',
        icon: 'Plus',
        onSelect: () => setAddSkillOpen(true),
      },
      {
        id: 'skills-discover-clients',
        label: 'Discover client skills',
        icon: 'Search',
        onSelect: () =>
          handleSkillsAction(
            'discover-skills',
            'Discover client skills',
            'Discover all skills installed in connected IDE clients and report which are managed, unmanaged, or out-of-sync.',
          ),
      },
      {
        id: 'skills-sync-managed',
        label: 'Sync managed skills to clients',
        icon: 'RefreshCw',
        onSelect: () =>
          handleSkillsAction(
            'sync-managed-skills',
            'Sync managed skills to clients',
            'Synchronize all managed Augur skills into configured IDE clients, applying any pending schema updates.',
          ),
      },
      {
        id: 'skills-review-external',
        label: 'Review external skills',
        icon: 'ShieldCheck',
        onSelect: () =>
          handleSkillsAction(
            'review-external-skills',
            'Review external skills',
            'Review all external and marketplace-installed skills in IDE clients; flag risky/inactive ones and recommend removal, review, or replacement.',
          ),
      },
      {
        id: 'skills-reindex',
        label: reindexing ? 'Reindexing...' : 'Reindex skills',
        icon: 'RefreshCw',
        onSelect: onReindex ?? (() => undefined),
        disabled: !onReindex || reindexing,
      },
      {
        id: 'skills-settings',
        label: 'Open skills settings',
        icon: 'Settings',
        onSelect: handleOpenSkillsSettings,
      },
    );
  } else {
    menuItems.push({
      id: `new-${category}`,
      label: newLabel,
      icon: 'Plus',
      onSelect: () => handleNew(),
    });
  }

  if (projectQuestionAction) {
    menuItems.unshift({
      id: 'ask-project-inventory-summary',
      label: projectQuestionAction.label,
      icon: 'MessageSquare',
      onSelect: projectQuestionAction.onSelect,
      disabled: projectQuestionAction.disabled,
    });
  }

  if (category !== 'skills' && onAddContent) {
    menuItems.push({
      id: `add-content-${category}`,
      label: category === 'notes' ? 'Add Note' : 'Add Content',
      icon: 'Upload',
      onSelect: onAddContent,
    });
  }

  if (category === 'documents' && onAttachDocumentSource) {
    menuItems.push({
      id: 'documents-attach-shared-source',
      label: 'Attach shared source',
      icon: 'FolderPlus',
      onSelect: onAttachDocumentSource,
    });
  }

  if ((category === 'notes' || category === 'documents' || category === 'pages') && onSweepVisible) {
    menuItems.push({
      id: `sweep-visible-${category}`,
      label: sweeping ? 'Sweeping...' : 'Sweep visible',
      icon: 'Archive',
      onSelect: onSweepVisible,
      disabled: sweeping || itemCount === 0,
    });
  }

  if (category === 'background-routines') {
    menuItems.push(
      {
        id: 'routines-refresh-codex',
        label: routineRefresh.codex ? 'Refreshing Codex...' : 'Refresh Codex routines',
        icon: 'RefreshCw',
        onSelect: handleRefreshCodex,
        disabled: routineRefresh.codex,
      },
      {
        id: 'routines-refresh-cloud',
        label: routineRefresh.cloud ? 'Refreshing cloud...' : 'Refresh cloud routines',
        icon: 'RefreshCw',
        onSelect: handleRefreshCloud,
        disabled: routineRefresh.cloud,
      },
    );
  }

  if (category !== 'skills' && onReindex) {
    menuItems.push({
      id: `reindex-${category}`,
      label: reindexing ? 'Reindexing...' : 'Reindex',
      icon: 'RefreshCw',
      onSelect: onReindex,
      disabled: reindexing,
    });
  }

  return {
    items: menuItems,
    modal: <AddSkillModal open={addSkillOpen} onOpenChange={setAddSkillOpen} />,
  };
}

/**
 * Thin standalone "Manage" menu. Retained for reuse; the Browse header now folds
 * these actions into the unified context popover via {@link useBrowseCategoryActions}.
 */
export function BrowseCategoryActions(props: BrowseCategoryActionsProps) {
  const { items, modal } = useBrowseCategoryActions(props);
  return (
    <div className="relative shrink-0">
      <BrowseOverflowMenu
        items={items}
        buttonLabel="Manage"
        menuLabel={`${props.activeCategory.label} actions`}
        triggerMode="icon-label"
        triggerIcon={SlidersHorizontal}
        showTriggerChevron
        buttonTestId="browse-category-actions-trigger"
      />

      {modal}
    </div>
  );
}
