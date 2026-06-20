import type { SkillDetail } from '@/lib/browse/types';
import type { SkillCoverageFindings } from '@/lib/browse/skillCoverage';
import type { SkillDemo } from '@/lib/browse/cardModel';
import {
  aiItemActionsFor,
  type AiItemActionItem,
  type DirectItemAction,
} from '@/lib/browse/itemActions';
import type { ActiveFolderContext } from '@/lib/browse/folderContext';

export interface BrowseDetailPanelProps {
  detail: SkillDetail;
  onClose: () => void;
  /** ADR-741 check-resolvable findings for this skill, if any. */
  coverageFindings?: SkillCoverageFindings;
  /** Demo runbooks from the skill's demos/ directory (rule 32, ADR-813). */
  demos?: SkillDemo[];
  /** ADR-748: dispatches a resolved prompt body to the CLI chat window. */
  onTriggerPrompt?: (resolvedPrompt: string) => void;
  /** Hands a per-category AI-action prompt to the chat as an editable draft. */
  onItemPrompt?: (prompt: string) => void;
  /** Runs a generated direct MCP action against this skill. */
  onItemDirect?: (action: DirectItemAction, item: AiItemActionItem) => void | Promise<void>;
  activeFolderContext?: ActiveFolderContext | null;
}

export type SkillPrompt = NonNullable<SkillDetail['prompts']>[number];
export type CapabilityProfileSection = NonNullable<SkillDetail['capabilityProfileSections']>[number];
export type GeneratedAiAction = ReturnType<typeof aiItemActionsFor>[number];
