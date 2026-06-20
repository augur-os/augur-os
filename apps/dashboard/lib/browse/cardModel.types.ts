import type {
  BrowseCardAction,
  BrowseItem,
  BrowsePrimaryAction,
  ViewMode,
} from "@/lib/browse/types";

export type BrowseCardBadgeTone =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "note-url"
  | "note-file"
  | "note-thought"
  | "note-voice-memo"
  | "note-meeting"
  | "note-image"
  | "note-prompt";

export interface BrowseCardBadge {
  id: string;
  label: string;
  tone?: BrowseCardBadgeTone;
  icon?: string;
}

export interface BrowseCardMetadataRow {
  label: string;
  value: string;
}

export interface BrowseCardDetailSection {
  id: string;
  title: string;
  rows: BrowseCardMetadataRow[];
}

export interface BrowseCardModel {
  id: string;
  title: string;
  description: string;
  icon: string;
  path?: string;
  badges: BrowseCardBadge[];
  metadataRows: BrowseCardMetadataRow[];
  primaryAction: BrowsePrimaryAction;
  overflowActions: BrowseCardAction[];
  detailSections: BrowseCardDetailSection[];
  rawItem: BrowseItem;
}

export interface BrowseCardModelContext {
  viewMode: ViewMode;
}

/** A demo runbook shipped in a skill's `demos/` directory (rule 32). */
export interface SkillDemo {
  name: string;
  path: string;
}
