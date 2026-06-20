import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import type { BlockProps } from "./types";
import { BLOCK_REGISTRY } from "./generated-block-registry";

type BlockComponent = ComponentType<BlockProps<any>>;

export const BLOCK_COMPONENTS: Record<string, BlockComponent> = {
  "stat-card": dynamic(() => import("@/components/blocks/types/StatCardBlock")),
  "stat-grid": dynamic(() => import("@/components/blocks/types/StatGridBlock")),
  "data-list": dynamic(() => import("@/components/blocks/types/DataListBlock")),
  "data-table": dynamic(
    () => import("@/components/blocks/types/DataTableBlock"),
  ),
  "action-bar": dynamic(
    () => import("@/components/blocks/types/ActionBarBlock"),
  ),
  "card-grid": dynamic(() => import("@/components/blocks/types/CardGridBlock")),
  chart: dynamic(() => import("@/components/blocks/types/ChartBlock")),
  markdown: dynamic(() => import("@/components/blocks/types/MarkdownBlock")),
  calendar: dynamic(() => import("@/components/blocks/types/CalendarBlock")),
  "activity-feed": dynamic(
    () => import("@/components/blocks/types/ActivityFeedBlock"),
  ),
  notes: dynamic(() => import("@/components/blocks/types/NotesBlock")),
  embed: dynamic(() => import("@/components/blocks/types/EmbedBlock")),
  "ops-board": dynamic(() => import("@/components/blocks/types/OpsBoardBlock")),
  progress: dynamic(() => import("@/components/blocks/types/ProgressBlock")),
  kanban: dynamic(() => import("@/components/blocks/types/KanbanBlock")),
  tabbed: dynamic(() => import("@/components/blocks/types/TabbedBlock")),
  health: dynamic(() => import("@/components/blocks/types/HealthBlock")),
  "vault-notes": dynamic(() => import("@/components/blocks/types/VaultNotesBlock")),
  "custom-sources": dynamic(() => import("@/components/blocks/types/CustomSourcesBlock")),
  "file-list": dynamic(() => import("@/components/blocks/types/FileListBlock")),
  "data-preview": dynamic(() => import("@/components/blocks/types/DataPreviewBlock")),
  widget: dynamic(() => import("@/components/blocks/types/WidgetBlock")),
  "metrics-dashboard": dynamic(() => import("@/components/blocks/types/MetricsDashboardBlock")),
};

export function resolveBlockComponent(type: string): BlockComponent | null {
  return BLOCK_COMPONENTS[type] ?? null;
}

export function getBlockManifest(blockId: string) {
  return BLOCK_REGISTRY[blockId] ?? null;
}
