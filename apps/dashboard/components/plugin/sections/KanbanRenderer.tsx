'use client';

/**
 * ADR-274 D12: Kanban board renderer with drag-and-drop.
 *
 * Uses @dnd-kit/core for drag-and-drop. Columns from configured field values.
 * Drop handler dispatches the on_move action via callback.
 */

import { useState, useMemo, useCallback } from 'react';
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  closestCorners,
} from '@dnd-kit/core';
import { useDraggable } from '@dnd-kit/core';
import { GripVertical } from 'lucide-react';

import type { KanbanDefinition } from './types';

interface KanbanRendererProps {
  data: Record<string, unknown>[];
  kanban: KanbanDefinition;
  onMove?: (itemId: string, newStatus: string) => Promise<void>;
}

// ── Draggable card ──────────────────────────────────────────────────

function KanbanCard({
  item,
  kanban,
  isDragOverlay,
}: {
  item: Record<string, unknown>;
  kanban: KanbanDefinition;
  isDragOverlay?: boolean;
}) {
  const id = String(item.id ?? item[kanban.card_title_field] ?? '');
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id });

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;

  return (
    <div
      ref={isDragOverlay ? undefined : setNodeRef}
      style={isDragOverlay ? undefined : style}
      className={`rounded-lg border border-gray-100 bg-white p-3 shadow-sm ${
        isDragging ? 'opacity-30' : ''
      } ${isDragOverlay ? 'shadow-lg ring-2 ring-gray-200' : ''}`}
    >
      <div className="flex items-start gap-2">
        <button type="button"
          {...(isDragOverlay ? {} : { ...listeners, ...attributes })}
          className="mt-0.5 cursor-grab text-gray-300 hover:text-gray-500 active:cursor-grabbing"
          aria-label="Drag handle"
        >
          <GripVertical className="size-4" />
        </button>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-900 truncate">
            {String(item[kanban.card_title_field] ?? '')}
          </p>
          {kanban.card_subtitle_field && !!item[kanban.card_subtitle_field] && (
            <p className="mt-0.5 text-xs text-gray-500 truncate">
              {String(item[kanban.card_subtitle_field])}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Droppable column ────────────────────────────────────────────────

function KanbanColumn({
  columnId,
  items,
  kanban,
}: {
  columnId: string;
  items: Record<string, unknown>[];
  kanban: KanbanDefinition;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: columnId });

  return (
    <div
      ref={setNodeRef}
      className={`flex min-h-[200px] flex-1 flex-col rounded-xl border p-3 transition-colors ${
        isOver ? 'border-blue-300 bg-blue-50/50' : 'border-gray-100 bg-gray-50/50'
      }`}
    >
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-700 capitalize">{columnId}</h4>
        <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-600">
          {items.length}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {items.map((item, idx) => (
          <KanbanCard key={String(item.id ?? idx)} item={item} kanban={kanban} />
        ))}
      </div>
    </div>
  );
}

// ── Main kanban board ───────────────────────────────────────────────

export function KanbanRenderer({ data, kanban, onMove }: KanbanRendererProps) {
  const [localItems, setLocalItems] = useState<Record<string, unknown>[] | null>(null);
  const [activeItem, setActiveItem] = useState<Record<string, unknown> | null>(null);
  const items = localItems ?? data;

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const columnData = useMemo(() => {
    const map = new Map<string, Record<string, unknown>[]>();
    for (const col of kanban.columns) {
      map.set(col, []);
    }
    for (const item of items) {
      const col = String(item[kanban.column_field] ?? '');
      if (map.has(col)) {
        map.get(col)!.push(item);
      }
    }
    return map;
  }, [items, kanban.columns, kanban.column_field]);

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const item = items.find(
        (i) => String(i.id ?? i[kanban.card_title_field]) === String(event.active.id),
      );
      setActiveItem(item ?? null);
    },
    [items, kanban.card_title_field],
  );

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      setActiveItem(null);
      const { active, over } = event;
      if (!over) return;

      const targetColumn = String(over.id);
      if (!kanban.columns.includes(targetColumn)) return;

      const itemId = String(active.id);
      const item = items.find(
        (i) => String(i.id ?? i[kanban.card_title_field]) === itemId,
      );
      if (!item) return;

      const currentColumn = String(item[kanban.column_field]);
      if (currentColumn === targetColumn) return;

      // Optimistic update
      setLocalItems((prev) =>
        (prev ?? data).map((i) =>
          String(i.id ?? i[kanban.card_title_field]) === itemId
            ? { ...i, [kanban.column_field]: targetColumn }
            : i,
        ),
      );

      // Dispatch action
      if (onMove) {
        try {
          await onMove(itemId, targetColumn);
        } catch {
          // Revert on failure
          setLocalItems((prev) =>
            (prev ?? data).map((i) =>
              String(i.id ?? i[kanban.card_title_field]) === itemId
                ? { ...i, [kanban.column_field]: currentColumn }
                : i,
            ),
          );
        }
      }
    },
    [data, items, kanban, onMove],
  );

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-3 overflow-x-auto pb-2">
        {kanban.columns.map((col) => (
          <KanbanColumn
            key={col}
            columnId={col}
            items={columnData.get(col) ?? []}
            kanban={kanban}
          />
        ))}
      </div>
      <DragOverlay>
        {activeItem && <KanbanCard item={activeItem} kanban={kanban} isDragOverlay />}
      </DragOverlay>
    </DndContext>
  );
}
