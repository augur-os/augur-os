"use client";

import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import type { View, BlockInstance } from "@/lib/blocks/types";
import { BlockRenderer } from "@/components/blocks/BlockRenderer";

interface UserBlocksSectionProps {
  hubId: string;
}

/**
 * Renders user-added blocks for a hub overview.
 *
 * Loads the hub's view from the server-side ViewStorage API
 * (view ID: `hub-{hubId}-overview`). When the view exists and
 * has blocks, they are rendered using BlockRenderer. When there are no blocks this
 * component renders nothing — the block picker "Add" button in
 * the CustomizePanel is the entry point for adding blocks.
 */
export function UserBlocksSection({ hubId }: UserBlocksSectionProps) {
  const viewId = `hub-${hubId}-overview`;
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);

  const { data: view } = useQuery<View | null>({
    queryKey: ["hub-view", viewId],
    queryFn: async () => {
      const res = await fetch(`/api/views/${viewId}`);
      if (res.status === 404) return null;
      if (!res.ok) return null;
      return res.json();
    },
    staleTime: 30_000,
  });

  const { mutateAsync: removeBlockMutation } = useMutation({
    mutationFn: async (instanceId: string) => {
      await fetch(`/api/views/${viewId}/blocks/${instanceId}`, {
        method: "DELETE",
      });
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["hub-view", viewId] }),
  });

  const handleRemoveBlock = useCallback(
    async (instanceId: string) => {
      await removeBlockMutation(instanceId);
    },
    [removeBlockMutation],
  );

  // Nothing to show if no view or no blocks
  if (!view || view.blocks.length === 0) return null;

  return (
    <div className="mt-6 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Pinned Blocks
        </h2>
        <button type="button"
          onClick={() => setEditing((e) => !e)}
          aria-label={editing ? "Done editing blocks" : "Edit pinned blocks"}
          className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 rounded"
        >
          {editing ? "Done" : "Edit"}
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {view.blocks.map((block: BlockInstance) => (
          <div key={block.instanceId} className="relative group">
            {editing && (
              <button type="button"
                onClick={() => handleRemoveBlock(block.instanceId)}
                aria-label="Remove block"
                className="absolute top-1 right-1 z-10 p-1 rounded bg-[var(--bg-primary)]/80 hover:bg-red-500/20 border border-[var(--border-primary)] cursor-pointer transition-colors opacity-0 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
              >
                <X className="size-3 text-[var(--text-secondary)]" />
              </button>
            )}
            <BlockRenderer
              instance={block}
              editing={false}
              onRemove={editing ? handleRemoveBlock : undefined}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
