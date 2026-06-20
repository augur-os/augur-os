import { useMemo, useState } from "react";
import {
  Eye,
  EyeOff,
  Heart,
  GripVertical,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Reorder, useDragControls } from "framer-motion";
import { getEnabledSections, type NavSection } from "@/lib/navigation";
import { getHubConfig } from "@/lib/tabs/registry";
import type { Favorites } from "./types";
import { SectionHeader } from "./ui-helpers";

export function FavoritesTabContent({
  favorites,
  onToggleFavorite,
}: {
  favorites: Favorites;
  onToggleFavorite: (href: string) => void;
}) {
  const allNavItems = getEnabledSections(true).flatMap(
    (section) => section.items,
  );

  return (
    <div className="space-y-1.5">
      <p className="px-2 text-xs text-[var(--text-muted)]">
        Favorites are always shown in the sidebar.
      </p>
      <div className="space-y-0.5 px-1">
        {allNavItems.map((item) => {
          const Icon = item.icon;
          const isFav = favorites.includes(item.href);

          return (
            <button type="button"
              key={item.href}
              onClick={() => onToggleFavorite(item.href)}
              className={`w-full flex items-center gap-3 px-2 py-2 rounded-lg transition-colors ${
                isFav
                  ? "bg-[var(--accent-primary)]/10 hover:bg-[var(--accent-primary)]/15"
                  : "hover:bg-[var(--bg-hover)]"
              }`}
            >
              <Icon
                className={`size-3.5 ${
                  isFav
                    ? "text-[var(--accent-primary)]"
                    : "text-[var(--text-muted)]"
                }`}
              />
              <span
                className={`flex-1 text-left text-xs font-medium ${
                  isFav
                    ? "text-[var(--text-primary)]"
                    : "text-[var(--text-secondary)]"
                }`}
              >
                {item.label}
                {item.href === "/" && (
                  <span className="ml-1.5 text-xs text-[var(--text-muted)]">
                    (pinned)
                  </span>
                )}
              </span>
              {isFav ? (
                <Heart className="size-3.5 text-[var(--accent-primary)] fill-[var(--accent-primary)]" />
              ) : (
                <Heart className="size-3.5 text-[var(--text-muted)]" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function DraggableSectionRow({
  label,
  section,
  sidebarVisibility,
  onToggleVisibility,
}: {
  label: string;
  section: NavSection;
  sidebarVisibility: Record<string, boolean>;
  onToggleVisibility: (href: string, nextVisible: boolean) => void;
}) {
  const controls = useDragControls();
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <Reorder.Item
      value={label}
      dragListener={false}
      dragControls={controls}
      className="rounded-lg select-none"
    >
      <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-[var(--bg-hover)]/50">
        <GripVertical
          className="size-3 text-[var(--text-muted)] cursor-grab active:cursor-grabbing shrink-0"
          onPointerDown={(e) => controls.start(e)}
        />
        <span className="flex-1 text-xs font-bold text-[var(--accent-primary)] uppercase tracking-wider">
          {label}
        </span>
        <button type="button"
          onClick={() => setIsExpanded((p) => !p)}
          className="p-0.5 rounded hover:bg-[var(--bg-hover)] transition-colors"
          aria-label={isExpanded ? "Collapse section" : "Expand section"}
        >
          {isExpanded ? (
            <ChevronDown className="size-3 text-[var(--text-muted)]" />
          ) : (
            <ChevronRight className="size-3 text-[var(--text-muted)]" />
          )}
        </button>
      </div>

      {isExpanded && (
        <div className="space-y-0.5 pl-6 pr-1 py-1">
          {section.items.map((item) => {
            const Icon = item.icon;
            const isVisible = sidebarVisibility[item.href] !== false;

            return (
              <button type="button"
                key={item.href}
                onClick={() => onToggleVisibility(item.href, !isVisible)}
                className={`w-full flex items-center gap-3 px-2 py-1.5 rounded-lg transition-colors ${
                  isVisible
                    ? "hover:bg-[var(--bg-hover)]"
                    : "opacity-50 hover:bg-[var(--bg-hover)]"
                }`}
              >
                <Icon
                  className={`size-3 ${
                    isVisible
                      ? "text-[var(--text-secondary)]"
                      : "text-[var(--text-muted)]"
                  }`}
                />
                <span
                  className={`flex-1 text-left text-xs ${
                    isVisible
                      ? "text-[var(--text-primary)]"
                      : "text-[var(--text-muted)]"
                  }`}
                >
                  {item.label}
                </span>
                {isVisible ? (
                  <Eye className="size-3 text-[var(--accent-primary)]" />
                ) : (
                  <EyeOff className="size-3 text-[var(--text-muted)]" />
                )}
              </button>
            );
          })}
        </div>
      )}
    </Reorder.Item>
  );
}

export function SidebarTabContent({
  sidebarVisibility,
  onToggleVisibility,
  sectionOrder,
  onReorderSections,
}: {
  sidebarVisibility: Record<string, boolean>;
  onToggleVisibility: (href: string, nextVisible: boolean) => void;
  sectionOrder: string[];
  onReorderSections: (order: string[]) => void;
}) {
  const allSections = getEnabledSections(true).filter((s) => s.label);

  const sectionMap = useMemo(() => {
    const map: Record<string, NavSection> = {};
    for (const section of allSections) {
      map[section.label] = section;
    }
    return map;
  }, [allSections]);

  const orderedLabels = useMemo(() => {
    const labels = allSections.map((s) => s.label);
    if (sectionOrder.length === 0) return labels;
    const labelSet = new Set(labels);
    const ordered: string[] = [];
    for (const label of sectionOrder) {
      if (labelSet.has(label)) ordered.push(label);
    }
    const orderedSet = new Set(ordered);
    for (const label of labels) {
      if (!orderedSet.has(label)) ordered.push(label);
    }
    return ordered;
  }, [allSections, sectionOrder]);

  return (
    <div className="space-y-1.5">
      <p className="px-2 text-xs text-[var(--text-muted)]">
        Drag to reorder sections. Expand to toggle items.
      </p>
      <Reorder.Group
        values={orderedLabels}
        onReorder={onReorderSections}
        axis="y"
        className="space-y-0.5 px-1"
      >
        {orderedLabels.map((label) => {
          const section = sectionMap[label];
          if (!section) return null;
          return (
            <DraggableSectionRow
              key={label}
              label={label}
              section={section}
              sidebarVisibility={sidebarVisibility}
              onToggleVisibility={onToggleVisibility}
            />
          );
        })}
      </Reorder.Group>
    </div>
  );
}

function DraggableTabRow({ label, value }: { label: string; value: string }) {
  const controls = useDragControls();
  return (
    <Reorder.Item
      value={value}
      dragListener={false}
      dragControls={controls}
      className="rounded-lg select-none"
    >
      <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-[var(--bg-hover)]/50">
        <GripVertical
          className="size-3 text-[var(--text-muted)] cursor-grab active:cursor-grabbing shrink-0"
          onPointerDown={(e) => controls.start(e)}
        />
        <span className="flex-1 text-xs text-[var(--text-primary)]">
          {label}
        </span>
      </div>
    </Reorder.Item>
  );
}

export function TabsReorderContent({
  pathname,
  onReorderTabs,
}: {
  pathname: string;
  onReorderTabs: (
    hubId: string,
    tabOrder: { pageId: string; order: number }[],
  ) => void;
}) {
  const hubId = pathname.split("/").filter(Boolean)[0] || "";
  const hubConfig = hubId ? getHubConfig(hubId) : undefined;

  const initialTabs = useMemo(() => {
    if (!hubConfig?.tabs) return [];
    return hubConfig.tabs.filter((t) => t.id !== "overview");
  }, [hubConfig]);

  // Tab label lookup
  const tabMap = useMemo(() => {
    const m: Record<string, { id: string; label: string }> = {};
    for (const t of initialTabs) {
      if (t.id) m[t.id] = { id: t.id, label: t.label };
    }
    return m;
  }, [initialTabs]);

  // Flat mode state
  const [flatOrder, setFlatOrder] = useState<string[]>(() =>
    initialTabs.map((t) => t.id || ""),
  );

  const handleFlatReorder = (newOrder: string[]) => {
    setFlatOrder(newOrder);
    const items = newOrder.map((pageId, idx) => ({
      pageId,
      order: (idx + 1) * 10,
    }));
    onReorderTabs(hubId, items);
  };

  if (!hubConfig || initialTabs.length === 0) {
    return (
      <div className="px-2 py-4 text-center">
        <p className="text-xs text-[var(--text-muted)]">
          Navigate to a hub page to reorder its tabs.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <SectionHeader>{hubConfig.title} Tabs</SectionHeader>
      <p className="px-2 text-xs text-[var(--text-muted)]">
        Drag to reorder tabs. Changes persist to plugin config.
      </p>
      <div className="px-1 py-0.5 mb-1 flex items-center gap-2">
        <div className="size-3" />
        <span className="text-xs text-[var(--text-muted)] italic">
          Overview (pinned first)
        </span>
      </div>
      <Reorder.Group
        values={flatOrder}
        onReorder={handleFlatReorder}
        axis="y"
        className="space-y-0.5 px-1"
      >
        {flatOrder.map((id) => {
          const tab = tabMap[id];
          if (!tab) return null;
          return <DraggableTabRow key={id} label={tab.label} value={id} />;
        })}
      </Reorder.Group>
    </div>
  );
}
