'use client';

import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useMcpMutation } from '@/lib/mcp/useMcpMutation';
import type { BrowseItem } from '@/lib/browse/types';
import { BrowseDetailActions } from './BrowseDetailActions';
import { BrowseBlockStack } from './BrowseBlockStack';
import EditableMarkdown from '@/components/EditableMarkdown';
import {
  aiItemActionsFor,
  directItemActionsFor,
  type AiItemActionItem,
  type DirectItemAction,
} from '@/lib/browse/itemActions';
import type { ActiveFolderContext } from '@/lib/browse/folderContext';
import { NOTE_PANEL_CATEGORY_IDS } from './BrowseDetailPanel.constants';
import {
  isGeneratedDoc,
  normalizeOwnership,
  rawNoteType,
  stripFrontmatter,
  stripHtmlComments,
  upstreamSummary,
} from './BrowseDetailPanel.helpers';
import {
  CapabilityProfileSections,
  CoverageFindingsSection,
  GeneratedSkillActionsSection,
  OwnershipSkillSection,
  SkillDemosSection,
  SkillPromptsSection,
} from './BrowseDetailPanel.sections';
import {
  BrowseDetailHeader,
  FileItemDetailPanel,
  NoteItemDetailView,
} from './BrowseDetailPanel.views';
import type { BrowseDetailPanelProps } from './BrowseDetailPanel.types';

/**
 * Dispatcher for browse-item detail. Calls no hooks itself, so the selected item
 * switching between a file-backed item and a note swaps component types cleanly
 * (no React hook-order violation). `category` is the active BrowseCategory id.
 */
export function BrowseItemDetailPanel({
  item,
  onClose,
  category,
  categoryLabel,
  categoryIcon,
  onItemPrompt,
  onItemDirect,
  activeFolderContext,
}: {
  item: BrowseItem;
  onClose: () => void;
  category?: string;
  categoryLabel?: string;
  categoryIcon?: string;
  onItemPrompt?: (prompt: string) => void;
  onItemDirect?: (action: DirectItemAction, item: AiItemActionItem) => void | Promise<void>;
  activeFolderContext?: ActiveFolderContext | null;
}) {
  const usesNotePanel = category
    ? NOTE_PANEL_CATEGORY_IDS.has(category)
    : rawNoteType(item) !== null;
  if (usesNotePanel) {
    return (
      <NoteItemDetailView
        item={item}
        onClose={onClose}
        category={category}
        onItemPrompt={onItemPrompt}
        onItemDirect={onItemDirect}
        activeFolderContext={activeFolderContext}
      />
    );
  }
  return (
    <FileItemDetailPanel
      key={item.id}
      item={item}
      onClose={onClose}
      onItemPrompt={onItemPrompt}
      onItemDirect={onItemDirect}
      label={categoryLabel || item.typeBadge || 'File'}
      iconName={categoryIcon || item.icon}
      category={category}
      activeFolderContext={activeFolderContext}
    />
  );
}

export function BrowseDetailPanel({
  detail,
  onClose,
  coverageFindings,
  demos,
  onTriggerPrompt,
  onItemPrompt,
  onItemDirect,
  activeFolderContext,
}: BrowseDetailPanelProps) {
  const queryClient = useQueryClient();
  const ownership = normalizeOwnership(detail.ownership);
  const adoptSource = detail.source ?? detail.upstream?.source ?? '';
  const upstream = upstreamSummary(detail.upstream);
  const capabilityProfileSections = detail.capabilityProfileSections ?? [];
  const hasCapabilityProfileSections = capabilityProfileSections.length > 0;
  const hasEmptyState =
    !detail.skillDoc && detail.blocks.length === 0 && !hasCapabilityProfileSections;
  const itemActionTarget: AiItemActionItem = {
    id: detail.skillId,
    title: detail.title,
    path: detail.upstream?.path ?? detail.skillId,
    hub: detail.hub,
    metadata: {
      skillId: detail.skillId,
      ownership,
      source: detail.source ?? '',
      qualityTier: detail.qualityTier ? String(detail.qualityTier) : '',
      masterClient: detail.masterClient ?? '',
    },
  };
  const skillAiActions = onItemPrompt
    ? aiItemActionsFor('skills', itemActionTarget, { activeFolderContext })
    : [];
  const skillDirectActions = onItemDirect ? directItemActionsFor('skills', itemActionTarget) : [];
  const hasGeneratedSkillActions = skillAiActions.length > 0 || skillDirectActions.length > 0;

  const { mutate: adoptSkill, loading: adopting, error: adoptError } = useMcpMutation(
    'skill-adopt',
    {
      staticArgs: { name: detail.skillId, source: adoptSource },
      invalidates: ['skill-detail', 'browse-index'],
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['skill-detail', detail.skillId] });
      },
    },
  );

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <section className="h-full flex flex-col overflow-hidden" aria-label={`${detail.title} detail panel`}>
      <BrowseDetailHeader detail={detail} ownership={ownership} onClose={onClose} />

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <OwnershipSkillSection
          adoptError={adoptError}
          adoptSkill={adoptSkill}
          adoptSource={adoptSource}
          adopting={adopting}
          ownership={ownership}
          upstream={upstream}
        />

        {/* Actions */}
        {detail.actions.length > 0 && (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Actions
            </h3>
            <BrowseDetailActions actions={detail.actions} skillId={detail.skillId} />
          </section>
        )}

        <GeneratedSkillActionsSection
          aiActions={skillAiActions}
          directActions={skillDirectActions}
          item={itemActionTarget}
          onItemDirect={onItemDirect}
          onItemPrompt={onItemPrompt}
          show={hasGeneratedSkillActions}
        />

        {/* ADR-748 Decision §4: trigger action wired in BrowseDetailPanel.
            Each prompt (skill-shipped or vault) renders with a source badge
            and the same BrowsePromptTrigger affordance used on cards. */}
        <SkillPromptsSection
          onTriggerPrompt={onTriggerPrompt}
          prompts={detail.prompts ?? []}
        />

        {coverageFindings && coverageFindings.issueCount > 0 && (
          <CoverageFindingsSection findings={coverageFindings} />
        )}

        {demos && demos.length > 0 && <SkillDemosSection demos={demos} />}

        <CapabilityProfileSections
          sections={capabilityProfileSections}
          show={hasCapabilityProfileSections}
        />

        {/* Documentation — always shown when available */}
        {detail.skillDoc && (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Documentation
            </h3>
            <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 backdrop-blur-sm p-4">
              <EditableMarkdown
                markdown={stripHtmlComments(stripFrontmatter(detail.skillDoc))}
                editable={ownership !== 'external' && !isGeneratedDoc(detail.skillDoc)}
                skillId={detail.skillId}
              />
            </div>
          </section>
        )}

        {/* Blocks — shown below docs when available */}
        {detail.blocks.length > 0 && (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Blocks
            </h3>
            <BrowseBlockStack blocks={detail.blocks} />
          </section>
        )}

        {/* Empty state */}
        {hasEmptyState && (
          <p className="text-sm text-[var(--text-muted)] py-4">
            No documentation or blocks available for this skill.
          </p>
        )}
      </div>
    </section>
  );
}
