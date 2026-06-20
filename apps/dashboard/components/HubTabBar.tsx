"use client";

const EMPTY_ARRAY: never[] = [];

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  Columns3,
  Grid2x2Plus,
} from "lucide-react";
import type { TabItem, TabEntry, BlockNavItem } from "@/lib/tabs/types";
import { isGroupedTab } from "@/lib/tabs/tab-grouping";
import { GroupDropdown } from "./tabs/GroupDropdown";
import { TabLink } from "./tabs/TabLink";
import { useModeStore } from "@/lib/stores/modeStore";
import React, {
  Suspense,
  useRef,
  useState,
  useEffect,
  useEffectEvent,
  useCallback,
  useMemo,
  useSyncExternalStore,
} from "react";
import { CustomizePanel } from "@/components/plugin/CustomizePanel";

interface HubTabBarProps {
  tabs: TabEntry[];
  overflow?: TabEntry[];
  blocks?: BlockNavItem[];
  autoPages?: TabItem[];
  configPages?: TabItem[];
  basePath?: string;
  hubId?: string;
  tabCustomizeLabel?: string;
  tabCustomizeOpen?: boolean;
  onOpenTabCustomize?: () => void;
  onCloseTabCustomize?: () => void;
  tabCustomizePanel?: React.ReactNode;
}

interface MoreAction {
  id: string;
  label: string;
  ariaLabel: string;
  icon?: React.ReactNode;
  onSelect: () => void;
}

const MORE_BUTTON_WIDTH = 90;

const noopSubscribe = () => () => {};

type SearchParamsReader = Pick<URLSearchParams, "get" | "toString">;

function readSearchParam(searchParams: SearchParamsReader, name: string): string | null {
  return searchParams.get(name);
}

function MoreDropdown({
  tabs,
  actions = EMPTY_ARRAY,
  isActive,
  activeLabel,
  isTabActive,
  panel,
  onClosePanel,
}: {
  tabs: TabEntry[];
  actions?: MoreAction[];
  isActive: boolean;
  activeLabel?: string;
  isTabActive: (tab: TabItem) => boolean;
  panel?: React.ReactNode;
  onClosePanel?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const openRef = useRef(open);
  const panelOpenRef = useRef(false);
  const panelOpen = !!panel;
  const hiddenTabCount = tabs.length;
  const buttonLabel = activeLabel || "More";
  const showHiddenTabBadge = !activeLabel && hiddenTabCount > 0;
  const closePanelFromEffect = useEffectEvent(() => {
    onClosePanel?.();
  });

  useEffect(() => {
    openRef.current = open;
    panelOpenRef.current = panelOpen;
  }, [open, panelOpen]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!openRef.current && !panelOpenRef.current) return;
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        closePanelFromEffect();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <button type="button"
        onClick={() => {
          if (panelOpen) {
            onClosePanel?.();
            return;
          }
          setOpen((o) => !o);
        }}
        aria-haspopup="true"
        aria-expanded={open || panelOpen}
        className={cn(
          "group relative flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 whitespace-nowrap",
          isActive || panelOpen
            ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
            : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]/50",
        )}
      >
        <span className="max-w-[8rem] truncate">{buttonLabel}</span>
        {showHiddenTabBadge && (
          <span
            aria-hidden="true"
            className="rounded-full bg-[var(--accent-primary)]/15 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-[var(--accent-primary)]"
          >
            {hiddenTabCount}
          </span>
        )}
        <ChevronDown
          className={cn(
            "size-3.5 transition-transform",
            (open || panelOpen) && "rotate-180",
          )}
        />
      </button>
      {open && (
        <div
          className="absolute top-full right-0 mt-1 z-50 min-w-[180px] rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)] shadow-lg p-1"
          role="menu"
          tabIndex={-1}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setOpen(false);
              return;
            }
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
              e.preventDefault();
              const items = e.currentTarget.querySelectorAll('[role="menuitem"]');
              const current = document.activeElement;
              const idx = Array.from(items).indexOf(current as Element);
              const next = e.key === 'ArrowDown'
                ? items[(idx + 1) % items.length]
                : items[(idx - 1 + items.length) % items.length];
              (next as HTMLElement)?.focus();
            }
          }}
        >
          {actions.map((action) => (
            <button
              key={action.id}
              type="button"
              role="menuitem"
              aria-label={action.ariaLabel}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]/60 hover:text-[var(--text-primary)]"
              onClick={() => {
                setOpen(false);
                action.onSelect();
              }}
            >
              {action.icon}
              <span>{action.label}</span>
            </button>
          ))}
          {tabs.map((tab) =>
            isGroupedTab(tab) ? (
              tab.children.map((child) => (
                <div
                  key={child.href || child.id}
                  role="menuitem"
                  tabIndex={0}
                  onClick={() => setOpen(false)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setOpen(false);
                    }
                  }}
                >
                  <TabLink tab={child} active={isTabActive(child)} />
                </div>
              ))
            ) : (
              <div
                key={tab.href || tab.id}
                role="menuitem"
                tabIndex={0}
                onClick={() => setOpen(false)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setOpen(false);
                  }
                }}
              >
                <TabLink tab={tab} active={isTabActive(tab)} />
              </div>
            )
          )}
        </div>
      )}
      {panelOpen && (
        <div
          data-testid="hub-tab-more-panel-anchor"
          className="absolute top-full right-0 z-50"
        >
          {panel}
        </div>
      )}
    </div>
  );
}
export function HubTabBar(props: HubTabBarProps) {
  return (
    <Suspense fallback={null}>
      <HubTabBarInner {...props} />
    </Suspense>
  );
}

function HubTabBarInner({
  tabs = EMPTY_ARRAY,
  overflow,
  blocks = EMPTY_ARRAY,
  autoPages = EMPTY_ARRAY,
  configPages = EMPTY_ARRAY,
  basePath,
  hubId,
  tabCustomizeLabel,
  tabCustomizeOpen = false,
  onOpenTabCustomize,
  onCloseTabCustomize,
  tabCustomizePanel,
}: HubTabBarProps) {
  const isClient = useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
  const pathname = usePathname();
  const { replace } = useRouter();
  const searchParams = useSearchParams();
  const dashboardMode = useModeStore((state) => state.mode);

  const containerRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLDivElement>(null);
  const [fitCount, setFitCount] = useState<number | null>(null);

  const allTabs: TabEntry[] = useMemo(
    () => [
      ...tabs,
      ...(overflow || []),
      ...configPages,
    ],
    [configPages, overflow, tabs],
  );

  const filteredTabs = useMemo(
    () =>
      allTabs.filter(
        (tab) => !tab.devOnly || (isClient && dashboardMode === "development"),
      ),
    [allTabs, dashboardMode, isClient],
  );

  const [customizeOpen, setCustomizeOpen] = useState(false);
  const hasTabCustomizeAction = !!tabCustomizeLabel && !!onOpenTabCustomize;

  const hasBlocks = blocks.length > 0;
  const hasAutoPages = autoPages.length > 0;
  const hasConfigPages = configPages.length > 0;
  const canCustomizePage =
    dashboardMode === "development" && (hasBlocks || hasAutoPages || hasConfigPages);
  const reservedWidth =
    filteredTabs.length > 0 || hasTabCustomizeAction || canCustomizePage
      ? MORE_BUTTON_WIDTH
      : 0;

  const measure = useCallback(() => {
    const container = containerRef.current;
    const measurer = measureRef.current;
    if (!container || !measurer) return;

    const available = container.clientWidth - 12 - reservedWidth;
    const children = measurer.children;
    let used = 0;
    let count = 0;

    for (let i = 0; i < children.length; i++) {
      const childWidth = (children[i] as HTMLElement).offsetWidth + 2;
      if (used + childWidth > available) break;
      used += childWidth;
      count++;
    }

    setFitCount(count);
  }, [reservedWidth]);

  useEffect(() => {
    if (!isClient) return;
    const frame = requestAnimationFrame(() => measure());
    const observer = new ResizeObserver(measure);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [isClient, measure, filteredTabs.length]);

  useEffect(() => {
    if (!isClient || !canCustomizePage) return;

    const customizeParam = readSearchParam(searchParams, "customize");
    if (customizeParam !== "1") return;
    const openTimer = window.setTimeout(() => {
      setCustomizeOpen(true);
    }, 0);

    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("customize");
    const nextQuery = nextParams.toString();
    replace(nextQuery ? `${pathname}?${nextQuery}` : pathname, {
      scroll: false,
    });

    return () => {
      window.clearTimeout(openTimer);
    };
  }, [
    canCustomizePage,
    isClient,
    pathname,
    replace,
    searchParams,
  ]);

  const visibleTabs =
    fitCount !== null ? filteredTabs.slice(0, fitCount) : filteredTabs;
  const overflowTabs = fitCount !== null ? filteredTabs.slice(fitCount) : [];

  const leafTabs = useMemo(
    () =>
      filteredTabs.flatMap((tab): TabItem[] =>
        isGroupedTab(tab) ? tab.children : [tab],
      ),
    [filteredTabs],
  );
  const shadowingLeafTabs = useMemo(
    () =>
      allTabs.flatMap((tab): TabItem[] =>
        isGroupedTab(tab) ? tab.children : [tab],
      ),
    [allTabs],
  );

  const isTabActive = useCallback(
    (tab: TabItem) => {
      const href = tab.href;
      if (!href) return false;
      const exactMatch = pathname === href;
      const childMatch = href !== "/" && pathname.startsWith(href + "/");
      if (!exactMatch && !childMatch) return false;

      return !shadowingLeafTabs.some(
        (otherTab) =>
          otherTab.href &&
          otherTab.href !== href &&
          otherTab.href.length > href.length &&
          (pathname === otherTab.href ||
            pathname.startsWith(otherTab.href + "/")),
      );
    },
    [pathname, shadowingLeafTabs],
  );

  const activeOverflowTab = overflowTabs
    .flatMap((tab): TabItem[] => (isGroupedTab(tab) ? tab.children : [tab]))
    .find((tab) => isTabActive(tab));
  const isOverflowActive = !!activeOverflowTab;

  const closeMorePanels = useCallback(() => {
    setCustomizeOpen(false);
    onCloseTabCustomize?.();
  }, [onCloseTabCustomize, setCustomizeOpen]);

  const moreActions: MoreAction[] = useMemo(() => {
    const actions: MoreAction[] = [];

    if (hasTabCustomizeAction) {
      actions.push(
        {
          id: "customize-tabs",
          label: "Customize Tabs",
          ariaLabel: tabCustomizeLabel,
          icon: <Columns3 className="size-4" />,
          onSelect: () => {
            setCustomizeOpen(false);
            onOpenTabCustomize?.();
          },
        },
      );
    }

    if (canCustomizePage) {
      actions.push({
        id: "customize-page",
        label: "Customize Page",
        ariaLabel: "Customize page",
        icon: <Grid2x2Plus className="size-4" />,
        onSelect: () => {
          onCloseTabCustomize?.();
          setCustomizeOpen(true);
        },
      });
    }

    return actions;
  }, [
    canCustomizePage,
    hasTabCustomizeAction,
    onCloseTabCustomize,
    onOpenTabCustomize,
    setCustomizeOpen,
    tabCustomizeLabel,
  ]);

  const morePanel = canCustomizePage && customizeOpen
      ? (
          <CustomizePanel
            blocks={blocks}
            autoPages={autoPages}
            configPages={configPages}
            open={customizeOpen}
            onClose={() => {
              setCustomizeOpen(false);
              onCloseTabCustomize?.();
            }}
            route={pathname}
            hubId={hubId}
            anchored={false}
          />
        )
      : tabCustomizeOpen
        ? tabCustomizePanel
      : undefined;

  const shouldShowMoreButton = overflowTabs.length > 0 || moreActions.length > 0;

  if (filteredTabs.length === 0 && !canCustomizePage && !hasTabCustomizeAction) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      className="glass-panel p-1.5 relative mb-6 overflow-visible z-20"
    >
      <div
        ref={measureRef}
        aria-hidden
        className="flex items-center gap-0.5 absolute top-0 left-0 invisible pointer-events-none"
        style={{ whiteSpace: "nowrap" }}
      >
        {filteredTabs.map((t) => (
          <span
            key={t.href || t.id}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap"
          >
            {t.icon && <span className="size-4" />}
            <span>{t.label}</span>
            {isGroupedTab(t) && <span className="size-3.5" />}
          </span>
        ))}
      </div>

      <div className="flex items-center gap-0.5">
        {visibleTabs.map((t) =>
          isGroupedTab(t) ? (
            <GroupDropdown
              key={t.id}
              group={t}
              isTabActive={isTabActive}
            />
          ) : (
            <TabLink key={t.href || t.id} tab={t} active={isTabActive(t)} />
          ),
        )}

        {shouldShowMoreButton && (
          <div className={cn(canCustomizePage && "ml-auto")}>
            <MoreDropdown
              tabs={overflowTabs}
              actions={moreActions}
              isActive={isOverflowActive || customizeOpen || tabCustomizeOpen}
              activeLabel={activeOverflowTab?.label}
              isTabActive={isTabActive}
              panel={morePanel}
              onClosePanel={closeMorePanels}
            />
          </div>
        )}
      </div>
    </div>
  );
}
