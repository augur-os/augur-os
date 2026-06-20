"use client";

import { Columns3 } from "lucide-react";
import { useCallback } from "react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { useActionRunner } from "@/hooks/useActionRunner";
import { BlockShell } from "../BlockShell";
import { KanbanRenderer } from "@/components/plugin/sections/KanbanRenderer";
import type { KanbanDefinition } from "@/components/plugin/sections/types";

interface KanbanConfig {
  title?: string;
  /** Kanban board configuration — maps to ADR-274 D12 KanbanDefinition */
  kanban?: KanbanDefinition;
}

export default function KanbanBlock(props: BlockProps<KanbanConfig>) {
  const { config, dataSource, onExpand } = props;
  const { title = "Kanban", kanban } = config;
  const { runAction } = useActionRunner();

  const selfFetched = useBlockData<Record<string, unknown>[]>(
    dataSource,
    config,
    "kanban",
  );
  const data = (props.data as Record<string, unknown>[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  const items = Array.isArray(data) ? data : [];

  const handleMove = useCallback(
    async (itemId: string, newStatus: string) => {
      if (!kanban?.on_move) return;
      const idField = kanban.on_move.payload?.id_field ?? "id";
      const statusField = kanban.on_move.payload?.status_field ?? kanban.column_field;
      await runAction({
        id: kanban.on_move.action,
        label: "Move card",
        description: `Move card ${itemId} to ${newStatus}`,
        dispatch: "fire",
        page: window.location.pathname,
        args: { [idField]: itemId, [statusField]: newStatus },
        mcp_tools: dataSource?.mcpTool ? [dataSource.mcpTool] : undefined,
      });
    },
    [kanban, runAction, dataSource],
  );

  if (!kanban) {
    return (
      <BlockShell title={title} icon={Columns3} color="purple" onExpand={onExpand}>
        <div className="p-4 text-center">
          <p className="text-xs text-[var(--text-muted)] italic">
            No kanban configuration provided
          </p>
        </div>
      </BlockShell>
    );
  }

  return (
    <BlockShell
      title={title}
      icon={Columns3}
      color="purple"
      onExpand={onExpand}
      staleError={error}
    >
      <div className="p-4">
        {loading && (
          <div className="flex gap-3">
            {Array.from({ length: Math.min(kanban.columns.length, 4) }, (_, i) => (
              <div
                key={i}
                className="flex-1 h-32 rounded-lg bg-[var(--bg-hover)] animate-pulse"
              />
            ))}
          </div>
        )}

        {!loading && items.length === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
            No items
          </p>
        )}
        {!loading && items.length === 0 && error && (
          <div className="text-center py-6">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        )}
        {!loading && items.length > 0 && (
          <KanbanRenderer
            data={items}
            kanban={kanban}
            onMove={kanban.on_move ? handleMove : undefined}
          />
        )}
      </div>
    </BlockShell>
  );
}
