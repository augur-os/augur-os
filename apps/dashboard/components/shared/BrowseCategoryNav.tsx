"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { ChevronDown } from "lucide-react";
import {
  JOURNEY_GROUP_LABELS,
  JOURNEY_GROUP_ORDER,
  JOURNEY_GROUP_SUBTITLES,
  compareBrowseCategoriesByJourney,
  partitionBrowseCategoriesByTier,
  type BrowseCategory,
  type JourneyGroup,
} from "@/lib/browse/types";

interface BrowseCategoryNavProps {
  categories: BrowseCategory[];
  activeId: string;
  onSelect: (id: string) => void;
  renderTrailing?: (category: BrowseCategory) => ReactNode;
  ariaLabel?: string;
  className?: string;
  moreLabel?: string;
}

interface JourneyGroupSection {
  group: JourneyGroup;
  items: BrowseCategory[];
}

interface MoreCluster {
  key: "content" | "dev";
  label: string;
  sections: JourneyGroupSection[];
}

function groupByJourney(categories: BrowseCategory[]): JourneyGroupSection[] {
  const sorted = categories.slice().sort(compareBrowseCategoriesByJourney);
  const byGroup = new Map<JourneyGroup, BrowseCategory[]>();
  for (const category of sorted) {
    const items = byGroup.get(category.journey_group) ?? [];
    items.push(category);
    byGroup.set(category.journey_group, items);
  }
  return JOURNEY_GROUP_ORDER.flatMap((group) => {
    const items = byGroup.get(group);
    return items ? [{ group, items }] : [];
  });
}

function buildMoreClusters(categories: BrowseCategory[]): MoreCluster[] {
  const sections = groupByJourney(categories);
  const contentSections: JourneyGroupSection[] = [];
  const devSections: JourneyGroupSection[] = [];
  for (const section of sections) {
    const allDev = section.items.every((item) => item.devOnly);
    (allDev ? devSections : contentSections).push(section);
  }

  const clusters: MoreCluster[] = [];
  if (contentSections.length > 0) {
    clusters.push({ key: "content", label: "Content", sections: contentSections });
  }
  if (devSections.length > 0) {
    clusters.push({ key: "dev", label: "Dev", sections: devSections });
  }
  return clusters;
}

export function BrowseCategoryNav({
  categories,
  activeId,
  onSelect,
  renderTrailing,
  ariaLabel = "Browse categories",
  className,
  moreLabel = "More",
}: BrowseCategoryNavProps) {
  const { primary, more } = useMemo(
    () => partitionBrowseCategoriesByTier(categories),
    [categories],
  );
  const primaryGroups = useMemo(() => groupByJourney(primary), [primary]);
  const moreClusters = useMemo(() => buildMoreClusters(more), [more]);
  const moreFlatOrder = useMemo(() => {
    const ids: string[] = [];
    for (const cluster of moreClusters) {
      for (const section of cluster.sections) {
        for (const item of section.items) ids.push(item.id);
      }
    }
    return ids;
  }, [moreClusters]);
  const activeMoreCategory = useMemo(
    () => more.find((category) => category.id === activeId),
    [more, activeId],
  );
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const itemRefMap = useMemo(() => new Map<string, HTMLButtonElement>(), []);
  const setItemRef = useCallback((id: string) => (element: HTMLButtonElement | null) => {
    if (element) itemRefMap.set(id, element);
    else itemRefMap.delete(id);
  }, [itemRefMap]);

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (containerRef.current?.contains(target) || popoverRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setOpen(false);
        moreButtonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const initialId =
      activeMoreCategory?.id && moreFlatOrder.includes(activeMoreCategory.id)
        ? activeMoreCategory.id
        : moreFlatOrder[0];
    if (!initialId) return;
    const element = itemRefMap.get(initialId);
    if (!element) return;
    const id = window.requestAnimationFrame(() => element.focus());
    return () => window.cancelAnimationFrame(id);
  }, [open, activeMoreCategory, moreFlatOrder, itemRefMap]);

  const handleSelect = useCallback(
    (id: string) => {
      onSelect(id);
      setOpen(false);
    },
    [onSelect],
  );
  const focusItemAt = useCallback(
    (index: number) => {
      if (moreFlatOrder.length === 0) return;
      const wrapped = ((index % moreFlatOrder.length) + moreFlatOrder.length) % moreFlatOrder.length;
      itemRefMap.get(moreFlatOrder[wrapped])?.focus();
    },
    [moreFlatOrder, itemRefMap],
  );
  const handleItemKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>, currentId: string) => {
      const index = moreFlatOrder.indexOf(currentId);
      if (index < 0) return;
      if (event.key === "ArrowDown" || event.key === "ArrowRight") {
        event.preventDefault();
        focusItemAt(index + 1);
      } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
        event.preventDefault();
        focusItemAt(index - 1);
      } else if (event.key === "Home") {
        event.preventDefault();
        focusItemAt(0);
      } else if (event.key === "End") {
        event.preventDefault();
        focusItemAt(moreFlatOrder.length - 1);
      }
    },
    [moreFlatOrder, focusItemAt],
  );

  const hasMore = more.length > 0;
  const moreActive = Boolean(activeMoreCategory);

  return (
    <div
      ref={containerRef}
      role="tablist"
      aria-label={ariaLabel}
      className={`flex flex-wrap items-end gap-x-6 gap-y-3 ${className ?? ""}`}
    >
      <PrimaryCategoryGroups
        activeId={activeId}
        groups={primaryGroups}
        onSelect={handleSelect}
        renderTrailing={renderTrailing}
      />
      <MoreCategoryCluster
        activeCategory={activeMoreCategory}
        activeId={activeId}
        buttonRef={moreButtonRef}
        clusters={moreClusters}
        hasMore={hasMore}
        moreActive={moreActive}
        moreCount={more.length}
        moreLabel={moreLabel}
        onItemKeyDown={handleItemKeyDown}
        onOpenChange={setOpen}
        onSelect={handleSelect}
        open={open}
        popoverRef={popoverRef}
        renderTrailing={renderTrailing}
        setItemRef={setItemRef}
      />
    </div>
  );
}

function CategoryPill({
  category,
  isActive,
  onSelect,
  renderTrailing,
}: {
  category: BrowseCategory;
  isActive: boolean;
  onSelect: (id: string) => void;
  renderTrailing?: (category: BrowseCategory) => ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      onClick={() => onSelect(category.id)}
      className={`inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-medium transition-colors duration-200 whitespace-nowrap cursor-pointer ${
        isActive
          ? "bg-[var(--text-primary)] text-[var(--bg-primary)]"
          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]"
      }`}
    >
      {category.label}
      {renderTrailing?.(category)}
    </button>
  );
}

function PrimaryCategoryGroups({
  activeId,
  groups,
  onSelect,
  renderTrailing,
}: {
  activeId: string;
  groups: JourneyGroupSection[];
  onSelect: (id: string) => void;
  renderTrailing?: (category: BrowseCategory) => ReactNode;
}) {
  return (
    <>
      {groups.map(({ group, items }) => (
        <div key={group} className="flex min-w-0 flex-col gap-1.5">
          <span
            className="px-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]"
            title={JOURNEY_GROUP_SUBTITLES[group]}
          >
            {JOURNEY_GROUP_LABELS[group]}
          </span>
          <div className="flex flex-wrap items-center gap-1.5">
            {items.map((category) => (
              <CategoryPill
                key={category.id}
                category={category}
                isActive={category.id === activeId}
                onSelect={onSelect}
                renderTrailing={renderTrailing}
              />
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

function MoreCategoryCluster({
  activeCategory,
  activeId,
  buttonRef,
  clusters,
  hasMore,
  moreActive,
  moreCount,
  moreLabel,
  onItemKeyDown,
  onOpenChange,
  onSelect,
  open,
  popoverRef,
  renderTrailing,
  setItemRef,
}: {
  activeCategory?: BrowseCategory;
  activeId: string;
  buttonRef: RefObject<HTMLButtonElement | null>;
  clusters: MoreCluster[];
  hasMore: boolean;
  moreActive: boolean;
  moreCount: number;
  moreLabel: string;
  onItemKeyDown: (event: KeyboardEvent<HTMLButtonElement>, id: string) => void;
  onOpenChange: (open: boolean | ((previous: boolean) => boolean)) => void;
  onSelect: (id: string) => void;
  open: boolean;
  popoverRef: RefObject<HTMLDivElement | null>;
  renderTrailing?: (category: BrowseCategory) => ReactNode;
  setItemRef: (id: string) => (element: HTMLButtonElement | null) => void;
}) {
  const popoverColsClass = clusters.length > 1 ? "sm:grid-cols-3" : "sm:grid-cols-2";

  return (
    <div className="relative ml-auto flex flex-col gap-1.5 self-end">
      <span className="px-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-transparent" aria-hidden="true">
        .
      </span>
      <div className="flex items-center gap-1.5">
        {activeCategory ? (
          <CategoryPill
            category={activeCategory}
            isActive
            onSelect={onSelect}
            renderTrailing={renderTrailing}
          />
        ) : null}
        {activeCategory && hasMore ? (
          <span className="mx-1 h-5 w-px bg-[var(--border-color)]" aria-hidden="true" />
        ) : null}
        {hasMore ? (
          <button
            ref={buttonRef}
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            onClick={() => onOpenChange((previous) => !previous)}
            className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors duration-200 whitespace-nowrap cursor-pointer ${
              moreActive
                ? "text-[var(--text-primary)] bg-[var(--bg-secondary)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]"
            }`}
          >
            {moreLabel}
            <span className="text-xs tabular-nums text-[var(--text-muted)]">
              {moreCount}
            </span>
            <ChevronDown className={`h-4 w-4 transition-transform duration-150 ${open ? "rotate-180" : ""}`} aria-hidden="true" />
          </button>
        ) : null}
      </div>
      {open ? (
        <MorePopover
          activeId={activeId}
          clusters={clusters}
          onItemKeyDown={onItemKeyDown}
          onSelect={onSelect}
          popoverColsClass={popoverColsClass}
          popoverRef={popoverRef}
          renderTrailing={renderTrailing}
          setItemRef={setItemRef}
        />
      ) : null}
    </div>
  );
}

function MorePopover({
  activeId,
  clusters,
  onItemKeyDown,
  onSelect,
  popoverColsClass,
  popoverRef,
  renderTrailing,
  setItemRef,
}: {
  activeId: string;
  clusters: MoreCluster[];
  onItemKeyDown: (event: KeyboardEvent<HTMLButtonElement>, id: string) => void;
  onSelect: (id: string) => void;
  popoverColsClass: string;
  popoverRef: RefObject<HTMLDivElement | null>;
  renderTrailing?: (category: BrowseCategory) => ReactNode;
  setItemRef: (id: string) => (element: HTMLButtonElement | null) => void;
}) {
  return (
    <div
      ref={popoverRef}
      role="menu"
      aria-label="More browse categories"
      className="absolute right-0 z-50 mt-2 w-[min(94vw,720px)] rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)] p-3 shadow-2xl"
    >
      <div className="flex flex-col gap-4">
        {clusters.map((cluster) => (
          <MorePopoverCluster
            key={cluster.key}
            activeId={activeId}
            cluster={cluster}
            clusterCount={clusters.length}
            onItemKeyDown={onItemKeyDown}
            onSelect={onSelect}
            popoverColsClass={popoverColsClass}
            renderTrailing={renderTrailing}
            setItemRef={setItemRef}
          />
        ))}
      </div>
    </div>
  );
}

function MorePopoverCluster({
  activeId,
  cluster,
  clusterCount,
  onItemKeyDown,
  onSelect,
  popoverColsClass,
  renderTrailing,
  setItemRef,
}: {
  activeId: string;
  cluster: MoreCluster;
  clusterCount: number;
  onItemKeyDown: (event: KeyboardEvent<HTMLButtonElement>, id: string) => void;
  onSelect: (id: string) => void;
  popoverColsClass: string;
  renderTrailing?: (category: BrowseCategory) => ReactNode;
  setItemRef: (id: string) => (element: HTMLButtonElement | null) => void;
}) {
  return (
    <div className="min-w-0">
      {clusterCount > 1 ? (
        <div className="mb-2 flex items-center gap-2 px-1">
          <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-primary)]">
            {cluster.label}
          </span>
          <span className="h-px flex-1 bg-[var(--border-color)]" aria-hidden="true" />
        </div>
      ) : null}
      <div className={`grid gap-3 ${popoverColsClass}`}>
        {cluster.sections.map(({ group, items }) => (
          <MorePopoverSection
            key={group}
            activeId={activeId}
            group={group}
            items={items}
            onItemKeyDown={onItemKeyDown}
            onSelect={onSelect}
            renderTrailing={renderTrailing}
            setItemRef={setItemRef}
          />
        ))}
      </div>
    </div>
  );
}

function MorePopoverSection({
  activeId,
  group,
  items,
  onItemKeyDown,
  onSelect,
  renderTrailing,
  setItemRef,
}: {
  activeId: string;
  group: JourneyGroup;
  items: BrowseCategory[];
  onItemKeyDown: (event: KeyboardEvent<HTMLButtonElement>, id: string) => void;
  onSelect: (id: string) => void;
  renderTrailing?: (category: BrowseCategory) => ReactNode;
  setItemRef: (id: string) => (element: HTMLButtonElement | null) => void;
}) {
  return (
    <div className="min-w-0">
      <div
        className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]"
        title={JOURNEY_GROUP_SUBTITLES[group]}
      >
        {JOURNEY_GROUP_LABELS[group]}
      </div>
      <ul className="flex flex-col">
        {items.map((category) => (
          <MoreMenuItem
            key={category.id}
            category={category}
            isActive={category.id === activeId}
            onItemKeyDown={onItemKeyDown}
            onSelect={onSelect}
            renderTrailing={renderTrailing}
            setItemRef={setItemRef}
          />
        ))}
      </ul>
    </div>
  );
}

function MoreMenuItem({
  category,
  isActive,
  onItemKeyDown,
  onSelect,
  renderTrailing,
  setItemRef,
}: {
  category: BrowseCategory;
  isActive: boolean;
  onItemKeyDown: (event: KeyboardEvent<HTMLButtonElement>, id: string) => void;
  onSelect: (id: string) => void;
  renderTrailing?: (category: BrowseCategory) => ReactNode;
  setItemRef: (id: string) => (element: HTMLButtonElement | null) => void;
}) {
  return (
    <li>
      <button
        ref={setItemRef(category.id)}
        type="button"
        role="menuitem"
        onClick={() => onSelect(category.id)}
        onKeyDown={(event) => onItemKeyDown(event, category.id)}
        className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm transition-colors duration-150 ${
          isActive
            ? "bg-[var(--text-primary)] text-[var(--bg-primary)]"
            : "text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)] hover:text-[var(--text-primary)]"
        }`}
      >
        <span className="truncate">{category.label}</span>
        {renderTrailing?.(category)}
      </button>
    </li>
  );
}
