"use client";

import { useMemo, useReducer, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, ChevronDown, Heart } from "lucide-react";
// eslint-disable-next-line no-restricted-imports -- ADR-490 shell exception
import DynamicSkillsNav from "@/features/components/DynamicSkillsNav";
// eslint-disable-next-line no-restricted-imports -- ADR-490 shell exception
import { SetupWidget } from "@/features/setup/SetupWidget";
import {
  getEnabledSections,
  FOOTER_ITEMS,
  TOOLTIP_MAP,
  NavItem,
} from "../lib/navigation";
import { Tooltip } from "./ui/Tooltip";
import { useMCPContext } from "../hooks/useMCPContext";
import { useModeStore } from "../lib/stores/modeStore";

function resolveActiveHref(pathname: string, items: NavItem[]): string | null {
  if (!pathname) return null;
  // Collect all hrefs including children
  const allHrefs: string[] = [];
  for (const item of items) {
    allHrefs.push(item.href);
    if (item.children) {
      for (const child of item.children) {
        allHrefs.push(child.href);
      }
    }
  }
  const sorted = allHrefs.toSorted((a, b) => b.length - a.length);
  for (const href of sorted) {
    if (href === "/") {
      if (pathname === "/") return href;
      continue;
    }
    if (pathname === href || pathname.startsWith(`${href}/`)) {
      return href;
    }
  }
  return null;
}

const STORAGE_KEY = "augur:sidebar-visibility:v1";
const COLLAPSE_KEY = "augur:sidebar-collapsed:v2";
const FAVORITES_KEY = "augur:favorites:v2";
const SIDEBAR_ORDER_KEY = "augur:sidebar-order:v1";
const EVENT_KEY = "sidebar-subscription-update";
const FAVORITES_EVENT_KEY = "augur:favorites-changed";
const SIDEBAR_ORDER_EVENT = "augur:sidebar-order-changed";

// Default favorites - Browse is always a favorite
const DEFAULT_FAVORITES = ["/browse"];

function loadFavorites(): string[] {
  if (typeof window === "undefined") return DEFAULT_FAVORITES;
  try {
    const stored = localStorage.getItem(FAVORITES_KEY);
    return stored ? JSON.parse(stored) : DEFAULT_FAVORITES;
  } catch {
    return DEFAULT_FAVORITES;
  }
}

interface SidebarNavProps {
  onNavigate?: () => void;
}

type NavSection = ReturnType<typeof getEnabledSections>[number];

interface SidebarState {
  visibility: Record<string, boolean>;
  collapsed: Record<string, boolean>;
  expandedItems: Record<string, boolean>;
  favorites: string[];
  sectionOrder: string[];
  mounted: boolean;
}

type SidebarStateAction =
  | { type: "loaded"; state: Omit<SidebarState, "expandedItems"> }
  | { type: "set-visibility"; visibility: Record<string, boolean> }
  | { type: "set-favorites"; favorites: string[] }
  | { type: "set-section-order"; sectionOrder: string[] }
  | { type: "set-collapsed"; collapsed: Record<string, boolean> }
  | { type: "toggle-expanded-item"; href: string };

const initialSidebarState: SidebarState = {
  visibility: {},
  collapsed: {},
  expandedItems: {},
  favorites: DEFAULT_FAVORITES,
  sectionOrder: [],
  mounted: false,
};

function sidebarReducer(
  state: SidebarState,
  action: SidebarStateAction,
): SidebarState {
  switch (action.type) {
    case "loaded":
      return { ...action.state, expandedItems: state.expandedItems };
    case "set-visibility":
      return { ...state, visibility: action.visibility };
    case "set-favorites":
      return { ...state, favorites: action.favorites };
    case "set-section-order":
      return { ...state, sectionOrder: action.sectionOrder };
    case "set-collapsed":
      return { ...state, collapsed: action.collapsed };
    case "toggle-expanded-item":
      return {
        ...state,
        expandedItems: {
          ...state.expandedItems,
          [action.href]: !state.expandedItems[action.href],
        },
      };
    default:
      return state;
  }
}

function buildInitialCollapsed(
  sections: NavSection[],
  activeHref: string | null,
  pathname: string,
): Record<string, boolean> {
  const initialCollapsed: Record<string, boolean> = {};
  sections.forEach((section) => {
    if (!section.label) return;
    const hasActiveItem = section.items.some(
      (item) => item.href === activeHref || pathname.startsWith(`${item.href}/`),
    );
    initialCollapsed[section.label] =
      section.label === "Hubs" ? false : !hasActiveItem;
  });
  return initialCollapsed;
}

function loadSidebarState(
  sections: NavSection[],
  activeHref: string | null,
  pathname: string,
): Omit<SidebarState, "expandedItems"> {
  let visibility: Record<string, boolean> = {};
  const favorites = loadFavorites();
  let sectionOrder: string[] = [];
  let collapsed: Record<string, boolean>;

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      visibility = JSON.parse(stored);
    }
  } catch {
    // Ignore corrupted visibility state.
  }

  try {
    const storedOrder = localStorage.getItem(SIDEBAR_ORDER_KEY);
    if (storedOrder) {
      sectionOrder = JSON.parse(storedOrder);
    }
  } catch {
    // Ignore corrupted ordering state.
  }

  try {
    const storedCollapsed = localStorage.getItem(COLLAPSE_KEY);
    collapsed = storedCollapsed
      ? JSON.parse(storedCollapsed)
      : buildInitialCollapsed(sections, activeHref, pathname);
  } catch {
    collapsed = {};
    for (const section of sections) {
      if (section.label) {
        collapsed[section.label] = true;
      }
    }
  }

  return {
    visibility,
    collapsed,
    favorites,
    sectionOrder,
    mounted: true,
  };
}

function getPriorityClass(priority?: "primary" | "secondary" | "tertiary") {
  switch (priority) {
    case "primary":
      return "nav-section-primary";
    case "secondary":
      return "nav-section-secondary";
    case "tertiary":
      return "nav-section-tertiary";
    default:
      return "";
  }
}

interface NavLinkItemProps {
  item: NavItem;
  activeHref: string | null;
  pathname: string;
  tooltip?: string;
  onHover: (href: string) => void;
  onNavigate?: () => void;
  child?: boolean;
  activeWhenParentHasActiveChild?: boolean;
  fill?: boolean;
}

function NavLinkItem({
  item,
  activeHref,
  pathname,
  tooltip,
  onHover,
  onNavigate,
  child = false,
  activeWhenParentHasActiveChild = false,
  fill = false,
}: NavLinkItemProps) {
  const Icon = item.icon;
  const childActive = item.children?.some(
    (childItem) =>
      pathname === childItem.href || pathname.startsWith(`${childItem.href}/`),
  );
  const isActive =
    item.href === activeHref && (activeWhenParentHasActiveChild || !childActive);

  return (
    <Tooltip
      content={tooltip ?? TOOLTIP_MAP[item.href] ?? item.label}
      side="right"
      className="contents"
    >
      <Link
        href={item.href}
        prefetch={false}
        aria-current={isActive ? "page" : undefined}
        className={`nav-link ${fill ? "flex-1" : ""} ${child ? "text-xs" : ""} ${isActive ? "nav-link-active" : ""}`}
        onMouseEnter={() => onHover(item.href)}
        onClick={onNavigate}
      >
        <Icon className={child ? "size-4" : "size-5"} />
        <span className={child ? "text-xs font-medium" : "text-sm font-medium"}>
          {item.label}
        </span>
      </Link>
    </Tooltip>
  );
}

interface NavChildrenProps {
  childrenItems: NavItem[];
  activeHref: string | null;
  pathname: string;
  onHover: (href: string) => void;
  onNavigate?: () => void;
}

function NavChildren({
  childrenItems,
  activeHref,
  pathname,
  onHover,
  onNavigate,
}: NavChildrenProps) {
  return (
    <div className="flex flex-col gap-0.5 ml-4 mt-0.5 border-l border-[var(--border-color)] pl-2">
      {childrenItems.map((child) => (
        <NavLinkItem
          key={child.href}
          item={child}
          activeHref={activeHref}
          pathname={pathname}
          tooltip={child.label}
          onHover={onHover}
          onNavigate={onNavigate}
          child
          activeWhenParentHasActiveChild
        />
      ))}
    </div>
  );
}

function FavoritesSection({
  favoriteItems,
  activeHref,
  pathname,
  onHover,
  onNavigate,
}: {
  favoriteItems: NavItem[];
  activeHref: string | null;
  pathname: string;
  onHover: (href: string) => void;
  onNavigate?: () => void;
}) {
  if (favoriteItems.length === 0) return null;

  return (
    <div className="flex flex-col mb-4">
      <div className="nav-section-collapsible nav-section-primary flex items-center gap-2 py-1.5 px-3">
        <Heart className="size-3.5" />
        <span>Favorites</span>
      </div>
      <div className="flex flex-col gap-0.5 mt-1">
        {favoriteItems.map((item) => (
          <NavLinkItem
            key={`fav-${item.href}`}
            item={item}
            activeHref={activeHref}
            pathname={pathname}
            onHover={onHover}
            onNavigate={onNavigate}
          />
        ))}
      </div>
    </div>
  );
}

function SidebarNavSection({
  section,
  activeHref,
  pathname,
  visibility,
  favorites,
  collapsed,
  effectiveExpandedItems,
  onHover,
  onNavigate,
  onToggleSection,
  onToggleItemExpand,
}: {
  section: NavSection;
  activeHref: string | null;
  pathname: string;
  visibility: Record<string, boolean>;
  favorites: string[];
  collapsed: Record<string, boolean>;
  effectiveExpandedItems: Record<string, boolean>;
  onHover: (href: string) => void;
  onNavigate?: () => void;
  onToggleSection: (label: string) => void;
  onToggleItemExpand: (href: string) => void;
}) {
  const visibleItems = section.items.filter(
    (item) => visibility[item.href] !== false && !favorites.includes(item.href),
  );

  if (visibleItems.length === 0 && section.label) return null;

  if (section.label && visibleItems.length === 1) {
    const item = visibleItems[0];
    const hasChildren = item.children && item.children.length > 0;
    const isExpanded = effectiveExpandedItems[item.href] ?? false;
    return (
      <div key={section.label} className="flex flex-col mb-0.5">
        <div className="flex items-center">
          <div className="contents">
            <NavLinkItem
              item={item}
              activeHref={activeHref}
              pathname={pathname}
              onHover={onHover}
              onNavigate={onNavigate}
              fill
            />
          </div>
          {hasChildren && (
            <button type="button"
              onClick={() => onToggleItemExpand(item.href)}
              className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              aria-label={
                isExpanded ? `Collapse ${item.label}` : `Expand ${item.label}`
              }
            >
              {isExpanded ? (
                <ChevronDown className="size-3" />
              ) : (
                <ChevronRight className="size-3" />
              )}
            </button>
          )}
        </div>
        {hasChildren && isExpanded && (
          <NavChildren
            childrenItems={item.children!}
            activeHref={activeHref}
            pathname={pathname}
            onHover={onHover}
            onNavigate={onNavigate}
          />
        )}
      </div>
    );
  }

  const isCollapsed = section.label
    ? (collapsed[section.label] ?? (section.label !== "Apps"))
    : false;
  const sectionSpacing = isCollapsed ? "mb-0.5" : "mb-4";

  return (
    <div
      key={section.label || "root"}
      className={`flex flex-col ${sectionSpacing}`}
    >
      {section.label ? (
        <button type="button"
          onClick={() => onToggleSection(section.label)}
          className={`nav-section-collapsible ${getPriorityClass(section.priority)} flex items-center justify-between w-full cursor-pointer hover:opacity-80 transition-opacity py-1.5 px-3`}
          aria-expanded={!isCollapsed}
          aria-label={
            isCollapsed ? `Expand ${section.label}` : `Collapse ${section.label}`
          }
        >
          <span>{section.label}</span>
          <span className="text-[var(--text-muted)]">
            {isCollapsed ? (
              <ChevronRight className="size-3.5" />
            ) : (
              <ChevronDown className="size-3.5" />
            )}
          </span>
        </button>
      ) : null}

      <div
        className={`flex flex-col gap-0.5 overflow-hidden transition-[grid-template-rows,opacity] duration-200 ease-in-out grid ${
          isCollapsed
            ? "grid-rows-[0fr] opacity-0"
            : "grid-rows-[1fr] opacity-100 mt-1"
        }`}
      >
        <div className="min-h-0">
          {visibleItems.map((item) => {
            const hasChildren = item.children && item.children.length > 0;
            const isExpanded = effectiveExpandedItems[item.href] ?? false;

            if (!hasChildren) {
              return (
                <NavLinkItem
                  key={item.href}
                  item={item}
                  activeHref={activeHref}
                  pathname={pathname}
                  onHover={onHover}
                  onNavigate={onNavigate}
                />
              );
            }

            return (
              <div key={item.href} className="flex flex-col">
                <div className="flex items-center">
                  <div className="contents">
                    <NavLinkItem
                      item={item}
                      activeHref={activeHref}
                      pathname={pathname}
                      onHover={onHover}
                      onNavigate={onNavigate}
                      fill
                    />
                  </div>
                  <button type="button"
                    onClick={() => onToggleItemExpand(item.href)}
                    className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                    aria-label={
                      isExpanded
                        ? `Collapse ${item.label}`
                        : `Expand ${item.label}`
                    }
                  >
                    {isExpanded ? (
                      <ChevronDown className="size-3" />
                    ) : (
                      <ChevronRight className="size-3" />
                    )}
                  </button>
                </div>
                {isExpanded && (
                  <NavChildren
                    childrenItems={item.children!}
                    activeHref={activeHref}
                    pathname={pathname}
                    onHover={onHover}
                    onNavigate={onNavigate}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function SidebarNav({ onNavigate }: SidebarNavProps = {}) {
  const pathname = usePathname();
  const { mode } = useModeStore();
  const isDev = mode === "development";
  const [sidebarState, dispatchSidebar] = useReducer(
    sidebarReducer,
    initialSidebarState,
  );
  const {
    visibility,
    collapsed,
    expandedItems,
    favorites,
    sectionOrder,
    mounted,
  } = sidebarState;

  const sections = useMemo(() => getEnabledSections(isDev), [isDev]);
  // Apply custom section order
  const orderedSections = useMemo(() => {
    if (sectionOrder.length === 0) return sections;
    return sections.toSorted((a, b) => {
      const aIdx = sectionOrder.indexOf(a.label);
      const bIdx = sectionOrder.indexOf(b.label);
      if (aIdx === -1 && bIdx === -1) return 0;
      if (aIdx === -1) return 1;
      if (bIdx === -1) return -1;
      return aIdx - bIdx;
    });
  }, [sections, sectionOrder]);

  const allItems = useMemo(
    () => [
      ...orderedSections.flatMap((s) => s.items),
      ...FOOTER_ITEMS,
    ],
    [orderedSections],
  );
  const activeHref = useMemo(
    () => resolveActiveHref(pathname, allItems),
    [pathname, allItems],
  );
  const { handleLinkHover } = useMCPContext({ autoSwitch: false });
  useEffect(() => {
    let cancelled = false;
    Promise.resolve().then(() => {
      if (cancelled) return;
      dispatchSidebar({
        type: "loaded",
        state: loadSidebarState(sections, activeHref, pathname),
      });
    });

    // Listen for updates from Settings page
    const handleUpdate = (event: Event) => {
      const customEvent = event as CustomEvent<Record<string, boolean>>;
      dispatchSidebar({
        type: "set-visibility",
        visibility: customEvent.detail,
      });
    };

    // Listen for favorites updates
    const handleFavoritesUpdate = (event: Event) => {
      const customEvent = event as CustomEvent<string[]>;
      dispatchSidebar({
        type: "set-favorites",
        favorites: customEvent.detail,
      });
    };

    // Listen for section order updates
    const handleOrderUpdate = (event: Event) => {
      const customEvent = event as CustomEvent<string[]>;
      dispatchSidebar({
        type: "set-section-order",
        sectionOrder: customEvent.detail,
      });
    };

    window.addEventListener(EVENT_KEY, handleUpdate);
    window.addEventListener(FAVORITES_EVENT_KEY, handleFavoritesUpdate);
    window.addEventListener(SIDEBAR_ORDER_EVENT, handleOrderUpdate);

    return () => {
      cancelled = true;
      window.removeEventListener(EVENT_KEY, handleUpdate);
      window.removeEventListener(FAVORITES_EVENT_KEY, handleFavoritesUpdate);
      window.removeEventListener(SIDEBAR_ORDER_EVENT, handleOrderUpdate);
    };
  }, [activeHref, pathname, sections]);

  const toggleSection = (label: string) => {
    const next = { ...collapsed, [label]: !collapsed[label] };
    localStorage.setItem(COLLAPSE_KEY, JSON.stringify(next));
    dispatchSidebar({
      type: "set-collapsed",
      collapsed: next,
    });
  };

  const toggleItemExpand = (href: string) => {
    dispatchSidebar({ type: "toggle-expanded-item", href });
  };

  // Auto-expand items whose children contain the active route
  const autoExpanded = useMemo(() => {
    if (!mounted) return {};
    const result: Record<string, boolean> = {};
    for (const section of sections) {
      for (const item of section.items) {
        if (item.children) {
          const selfActive =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          const childActive = item.children.some(
            (c) => pathname === c.href || pathname.startsWith(`${c.href}/`),
          );
          if (selfActive || childActive) result[item.href] = true;
        }
      }
    }
    return result;
  }, [pathname, mounted, sections]);

  const effectiveExpandedItems = { ...autoExpanded, ...expandedItems };

  // Get favorite items that are visible
  const favoriteItems = useMemo(() => {
    return favorites
      .map((href) => allItems.find((item) => item.href === href))
      .filter(
        (item): item is NavItem =>
          item !== undefined && visibility[item.href] !== false,
      );
  }, [favorites, allItems, visibility]);

  // Render with defaults before mount — visibility={} shows all items,
  // collapsed={} defaults all sections to collapsed via ?? true,
  // favorites=DEFAULT_FAVORITES shows Overview only.
  // This avoids the empty→full jump that the old mounted guard caused.

  return (
    <nav className="flex flex-col overflow-y-auto flex-1 pr-2 group/nav relative">
      <FavoritesSection
        favoriteItems={favoriteItems}
        activeHref={activeHref}
        pathname={pathname}
        onHover={handleLinkHover}
        onNavigate={onNavigate}
      />

      {orderedSections.map((section) => (
        <SidebarNavSection
          key={section.label || "root"}
          section={section}
          activeHref={activeHref}
          pathname={pathname}
          visibility={visibility}
          favorites={favorites}
          collapsed={collapsed}
          effectiveExpandedItems={effectiveExpandedItems}
          onHover={handleLinkHover}
          onNavigate={onNavigate}
          onToggleSection={toggleSection}
          onToggleItemExpand={toggleItemExpand}
        />
      ))}

      {/* Dynamic Skills */}
      <DynamicSkillsNav />

      <div className="mt-auto pt-4">
        <SetupWidget variant="sidebar" />
      </div>

      {/* Footer Items */}
      {FOOTER_ITEMS.length > 0 && (
        <div className="mt-4 border-t border-[var(--border-color)] pt-4 flex flex-col gap-2">
          {FOOTER_ITEMS.map((item) => (
            <NavLinkItem
              key={item.href}
              item={item}
              activeHref={activeHref}
              pathname={pathname}
              onHover={handleLinkHover}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      )}
    </nav>
  );
}
