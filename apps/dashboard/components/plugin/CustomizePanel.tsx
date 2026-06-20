"use client";

const EMPTY_ARRAY: never[] = [];

import React, { useState, useRef, useEffect, useMemo, useCallback, useEffectEvent } from "react";
import { Box, ChevronDown, ChevronUp, FileText, MoreHorizontal, X } from "lucide-react";
import { resolveIcon as resolveIconFromMap } from "@/lib/icon-map";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { BlockNavItem, TabItem } from "@/lib/tabs/types";
import type { BlockSize } from "@/lib/blocks/flow-types";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { getHubViewId, randomUUID } from "@/lib/blocks/utils";

/** localStorage key for page layout persistence */
function storageKey(route: string): string {
  return `augur:page-layout:${route}`;
}

/** A block that has been added to the page layout */
interface LayoutBlock {
  id: string;
  size: BlockSize;
}

/** Read persisted layout from localStorage */
function readLayout(route: string): LayoutBlock[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(storageKey(route));
    if (!raw) return [];
    return JSON.parse(raw) as LayoutBlock[];
  } catch {
    return [];
  }
}

/** Write layout to localStorage */
function writeLayout(route: string, layout: LayoutBlock[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(storageKey(route), JSON.stringify(layout));
  } catch {
    // localStorage full or unavailable — silently ignore
  }
}

interface CustomizePanelProps {
  /** All available blocks from the hub's contributing skills */
  blocks: BlockNavItem[];
  /** Config-driven auto pages available in this hub */
  autoPages?: TabItem[];
  /** YAML config pages — shown as "Skill Pages" in the panel */
  configPages?: TabItem[];
  /** Whether the panel is open */
  open: boolean;
  /** Callback to close the panel */
  onClose: () => void;
  /** Current route path for layout persistence */
  route: string;
  /** Hub ID — when provided, blocks are also persisted to the hub view via ViewStorage API */
  hubId?: string;
  /** Whether the panel should position itself below its own trigger */
  anchored?: boolean;
}
export function CustomizePanel({
  blocks,
  autoPages = EMPTY_ARRAY,
  configPages = EMPTY_ARRAY,
  open,
  onClose,
  route,
  hubId,
  anchored = true,
}: CustomizePanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<LayoutBlock[]>(() => readLayout(route));
  const [search, setSearch] = useState("");
  const queryClient = useQueryClient();

  const hubViewId = hubId ? getHubViewId(hubId) : null;

  // Sync layout to localStorage on change
  useEffect(() => {
    writeLayout(route, layout);
  }, [route, layout]);

  // Re-read layout when route changes
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLayout(readLayout(route));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [route]);

  const closeFromEffect = useEffectEvent(onClose);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        closeFromEffect();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeFromEffect();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const addedIds = useMemo(() => new Set(layout.map((b) => b.id)), [layout]);

  const filtered = useMemo(() => {
    if (!search) return blocks;
    const q = search.toLowerCase();
    return blocks.filter(
      (b) => b.label.toLowerCase().includes(q) || b.skill.toLowerCase().includes(q),
    );
  }, [blocks, search]);

  const grouped = useMemo(() => {
    const map = new Map<string, BlockNavItem[]>();
    for (const block of filtered) {
      if (!map.has(block.skill)) map.set(block.skill, []);
      map.get(block.skill)!.push(block);
    }
    return map;
  }, [filtered]);

  /** Ensure the hub view exists on the server, creating it if needed. */
  const ensureHubView = useCallback(async (): Promise<void> => {
    if (!hubViewId) return;
    const res = await fetch(`/api/views/${hubViewId}`);
    if (res.status === 404) {
      await fetch("/api/views", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: `${hubId} Overview`, id: hubViewId }),
      });
    }
  }, [hubViewId, hubId]);

  const addBlock = useCallback(
    async (id: string) => {
      if (addedIds.has(id)) return;
      setLayout((prev) => [...prev, { id, size: "full" }]);

      // Persist to hub view storage API
      if (hubViewId) {
        await ensureHubView();
        const instance = {
          instanceId: randomUUID(),
          blockId: id,
          config: {},
          position: { x: 0, y: 0, w: 6, h: 4 },
        };
        await fetch(`/api/views/${hubViewId}/blocks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(instance),
        });
        queryClient.invalidateQueries({ queryKey: ["hub-view", hubViewId] });
      }
    },
    [addedIds, hubViewId, ensureHubView, queryClient],
  );

  const removeBlock = useCallback(async (id: string) => {
    setLayout((prev) => prev.filter((b) => b.id !== id));

    // Remove from hub view storage API — find the instance by blockId
    if (hubViewId) {
      const res = await fetch(`/api/views/${hubViewId}`);
      if (res.ok) {
        const view = await res.json();
        const instance = view.blocks?.find(
          (b: { blockId: string }) => b.blockId === id,
        );
        if (instance) {
          await fetch(`/api/views/${hubViewId}/blocks/${instance.instanceId}`, {
            method: "DELETE",
          });
          queryClient.invalidateQueries({ queryKey: ["hub-view", hubViewId] });
        }
      }
    }
  }, [hubViewId, queryClient]);

  const moveBlock = useCallback((index: number, direction: "up" | "down") => {
    setLayout((prev) => {
      const next = [...prev];
      const target = direction === "up" ? index - 1 : index + 1;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }, []);

  const resizeBlock = useCallback((id: string, size: BlockSize) => {
    setLayout((prev) => prev.map((b) => (b.id === id ? { ...b, size } : b)));
  }, []);

  const resetLayout = useCallback(async () => {
    setLayout([]);
    if (typeof window !== "undefined") {
      localStorage.removeItem(storageKey(route));
    }
    // Clear all blocks from hub view
    if (hubViewId) {
      await fetch(`/api/views/${hubViewId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blocks: [] }),
      });
      queryClient.invalidateQueries({ queryKey: ["hub-view", hubViewId] });
    }
  }, [route, hubViewId, queryClient]);

  const blockLookup = useMemo(() => new Map(blocks.map((b) => [b.id, b])), [blocks]);

  if (!open) return null;

  return (
    <CustomizePanelView
      addedIds={addedIds}
      addBlock={addBlock}
      anchored={anchored}
      autoPages={autoPages}
      blockLookup={blockLookup}
      blocks={blocks}
      configPages={configPages}
      grouped={grouped}
      layout={layout}
      moveBlock={moveBlock}
      onClose={onClose}
      panelRef={panelRef}
      removeBlock={removeBlock}
      resetLayout={resetLayout}
      resizeBlock={resizeBlock}
      search={search}
      setSearch={setSearch}
    />
  );
}

function CustomizePanelView({
  addedIds,
  addBlock,
  anchored,
  autoPages,
  blockLookup,
  blocks,
  configPages,
  grouped,
  layout,
  moveBlock,
  onClose,
  panelRef,
  removeBlock,
  resetLayout,
  resizeBlock,
  search,
  setSearch,
}: {
  addedIds: Set<string>;
  addBlock: (id: string) => Promise<void>;
  anchored: boolean;
  autoPages: TabItem[];
  blockLookup: Map<string, BlockNavItem>;
  blocks: BlockNavItem[];
  configPages: TabItem[];
  grouped: Map<string, BlockNavItem[]>;
  layout: LayoutBlock[];
  moveBlock: (index: number, direction: "up" | "down") => void;
  onClose: () => void;
  panelRef: React.RefObject<HTMLDivElement | null>;
  removeBlock: (id: string) => Promise<void>;
  resetLayout: () => Promise<void>;
  resizeBlock: (id: string, size: BlockSize) => void;
  search: string;
  setSearch: (value: string) => void;
}) {
  return (
    <div
      ref={panelRef}
      className={cn(
        "z-50 w-[360px] rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)] shadow-xl overflow-hidden",
        anchored && "absolute top-full right-0 mt-1",
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-color)]">
        <div className="flex items-center gap-2">
          <MoreHorizontal className="size-4 text-[var(--accent-primary)]" />
          <span className="text-sm font-semibold text-[var(--text-primary)]">
            More
          </span>
        </div>
        <button type="button"
          onClick={onClose}
          aria-label="Close customize panel"
          className="p-1 rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
        >
          <X className="size-4" />
        </button>
      </div>

      {/* Active blocks section */}
      {layout.length > 0 && (
        <div className="border-b border-[var(--border-color)]">
          <div className="px-4 py-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Active Blocks ({layout.length})
            </span>
            <button type="button"
              onClick={resetLayout}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--accent-danger)] transition-colors"
            >
              Reset
            </button>
          </div>
          <div className="max-h-[200px] overflow-y-auto px-2 pb-2 space-y-1">
            {layout.map((item, index) => {
              const block = blockLookup.get(item.id);
              if (!block) return null;
              const Icon = resolveIconFromMap(block.icon, Box);
              return (
                <div
                  key={item.id}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]"
                >
                  <Icon className="size-3.5 text-[var(--accent-primary)] flex-shrink-0" />
                  <span className="text-sm text-[var(--text-primary)] truncate flex-1">
                    {block.label}
                  </span>

                  {/* Size selector */}
                  <div className="flex items-center gap-0.5">
                    {(["full", "half", "third"] as BlockSize[]).map((size) => (
                      <button type="button"
                        key={size}
                        onClick={() => resizeBlock(item.id, size)}
                        className={cn(
                          "px-1.5 py-0.5 text-[10px] rounded transition-colors",
                          item.size === size
                            ? "bg-[var(--accent-primary)] text-white"
                            : "text-[var(--text-muted)] hover:bg-[var(--bg-hover)]",
                        )}
                        title={`${size} width`}
                        aria-label={`Set block to ${size} width`}
                      >
                        {size === "full" ? "1" : size === "half" ? "\u00BD" : "\u2153"}
                      </button>
                    ))}
                  </div>

                  {/* Move buttons */}
                  <button type="button"
                    onClick={() => moveBlock(index, "up")}
                    disabled={index === 0}
                    aria-label="Move block up"
                    className="p-0.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-30 transition-colors"
                  >
                    <ChevronUp className="size-3.5" />
                  </button>
                  <button type="button"
                    onClick={() => moveBlock(index, "down")}
                    disabled={index === layout.length - 1}
                    aria-label="Move block down"
                    className="p-0.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-30 transition-colors"
                  >
                    <ChevronDown className="size-3.5" />
                  </button>

                  {/* Remove */}
                  <button type="button"
                    onClick={() => removeBlock(item.id)}
                    aria-label="Remove block"
                    className="p-0.5 text-[var(--text-muted)] hover:text-[var(--accent-danger)] transition-colors"
                  >
                    <X className="size-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Skill Pages — YAML config pages accessible via block picker */}
      {configPages.length > 0 && (
        <div className="border-b border-[var(--border-color)]">
          <div className="px-4 py-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Skill Pages ({configPages.length})
            </span>
          </div>
          <div className="max-h-[200px] overflow-y-auto px-2 pb-2 space-y-0.5">
            {configPages.map((page) => {
              const iconName = typeof page.icon === "string" ? page.icon : "FileText";
              const Icon = resolveIconFromMap(iconName, FileText);
              return (
                <Link
                  key={page.id}
                  href={page.href || "#"}
                  onClick={onClose}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
                >
                  <Icon className="size-3.5 text-[var(--text-muted)] flex-shrink-0" />
                  <span className="truncate">{page.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Auto pages — auto-generated skill pages */}
      {autoPages.length > 0 && (
        <div className="border-b border-[var(--border-color)]">
          <div className="px-4 py-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Pages ({autoPages.length})
            </span>
          </div>
          <div className="max-h-[200px] overflow-y-auto px-2 pb-2 space-y-0.5">
            {autoPages.map((page) => {
              const iconName = typeof page.icon === "string" ? page.icon : "FileText";
              const Icon = resolveIconFromMap(iconName, FileText);
              return (
                <Link
                  key={page.id}
                  href={page.skillId ? `/browse/${page.skillId}` : (page.href || "#")}
                  onClick={onClose}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
                >
                  <Icon className="size-3.5 text-[var(--text-muted)] flex-shrink-0" />
                  <span className="truncate">{page.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Block catalog */}
      <div>
        <div className="px-4 py-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Available Blocks
          </span>
        </div>

        {blocks.length > 8 && (
          <div className="px-3 pb-2">
            <Input
              type="text"
              placeholder="Search blocks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-3 py-1.5 text-sm rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none focus:border-[var(--accent-primary)]/40"
              autoFocus
            />
          </div>
        )}

        <div className="max-h-[280px] overflow-y-auto pb-2">
          {grouped.size === 0 && (
            <div className="px-3 py-4 text-center text-sm text-[var(--text-muted)]">
              No blocks found
            </div>
          )}
          {Array.from(grouped.entries()).map(([skill, items]) => (
            <div key={skill}>
              <div className="px-4 py-1 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                {skill.replace(/-/g, " ")}
              </div>
              {items.map((block) => {
                const Icon = resolveIconFromMap(block.icon, Box);
                const isAdded = addedIds.has(block.id);
                return (
                  <div
                    key={block.id}
                    className="flex items-center gap-2 px-4 py-1.5 text-sm"
                  >
                    <Icon className="size-3.5 text-[var(--text-muted)] flex-shrink-0" />
                    <span
                      className={cn(
                        "truncate flex-1",
                        isAdded ? "text-[var(--text-muted)]" : "text-[var(--text-secondary)]",
                      )}
                    >
                      {block.label}
                    </span>
                    <Button
                      variant={isAdded ? "ghost" : "outline"}
                      size="xs"
                      onClick={() => (isAdded ? removeBlock(block.id) : addBlock(block.id))}
                      className={cn(
                        "h-6 px-2 text-[10px]",
                        isAdded && "text-[var(--text-muted)]",
                      )}
                    >
                      {isAdded ? "Remove" : "Add"}
                    </Button>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
