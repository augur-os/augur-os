"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from "react";
import { usePathname } from "next/navigation";
import {
  Layout,
  Type,
  Navigation,
} from "lucide-react";
import { pluginNavItems } from "@/lib/tabs/generated-registry";
import {
  PAGE_WIDGETS,
  FONT_SETTINGS_KEY,
  SIDEBAR_VISIBILITY_KEY,
  SIDEBAR_EVENT_KEY,
  SIDEBAR_ORDER_KEY,
  SIDEBAR_ORDER_EVENT,
  LAYOUT_STORAGE_PREFIX,
} from "./types";
import {
  loadPageLayouts,
  loadFavorites,
  saveFavorites,
  savePageLayouts,
  applyFontSettings,
  loadLayoutBlocks,
  loadFontSettings,
  loadSidebarOrder,
  loadSidebarVisibility,
  saveLayoutBlocks,
} from "./storage";
import {
  persistHubNavOrder,
  persistTabNavOrder,
} from "./nav-order";
import type {
  LayoutBlocks,
  ActiveTab,
} from "./types";

import type {
  LayoutConfigModalProps,
  LayoutConfigState,
  LayoutConfigAction,
  LayoutTabMeta,
  LayoutSurfaceProps,
} from "./LayoutConfigModal.types";
import { TabContent } from "./LayoutConfigModal.surfaces";

const initialLayoutConfigState: LayoutConfigState = {
  layouts: {},
  loaded: false,
  activeTab: "appearance",
  layoutBlocks: {},
  fontFamily: "system",
  fontSize: "medium",
  sidebarVisibility: {},
  sectionOrder: [],
  favorites: ["/"],
};

function layoutConfigReducer(
  state: LayoutConfigState,
  action: LayoutConfigAction,
): LayoutConfigState {
  switch (action.type) {
    case "loaded":
      return { ...action.state, activeTab: state.activeTab };
    case "set-active-tab":
      return { ...state, activeTab: action.activeTab };
    case "set-font-family":
      return { ...state, fontFamily: action.fontFamily };
    case "set-font-size":
      return { ...state, fontSize: action.fontSize };
    case "set-sidebar-state":
      return {
        ...state,
        sidebarVisibility: action.sidebarVisibility,
        sectionOrder: action.sectionOrder,
      };
    case "set-section-order":
      return { ...state, sectionOrder: action.sectionOrder };
    case "set-favorites":
      return { ...state, favorites: action.favorites };
    case "set-layout-blocks":
      return { ...state, layoutBlocks: action.layoutBlocks };
    case "set-layouts":
      return { ...state, layouts: action.layouts };
    case "toggle-widget": {
      const pageLayout = state.layouts[action.pathname] || {};
      const isCurrentlyVisible = pageLayout[action.widgetId] !== false;
      return {
        ...state,
        layouts: {
          ...state.layouts,
          [action.pathname]: {
            ...pageLayout,
            [action.widgetId]: !isCurrentlyVisible,
          },
        },
      };
    }
    default:
      return state;
  }
}

export function useLayoutConfigController({
  onClose,
  embedded = false,
}: LayoutConfigModalProps): LayoutSurfaceProps {
  const closeModal = onClose ?? (() => {});
  const pathname = usePathname() ?? "/";
  const [layoutState, dispatchLayoutState] = useReducer(
    layoutConfigReducer,
    initialLayoutConfigState,
  );
  const {
    layouts,
    loaded,
    activeTab,
    layoutBlocks,
    fontFamily,
    fontSize,
    sidebarVisibility,
    sectionOrder,
    favorites,
  } = layoutState;

  // Timer refs for cleanup on unmount (memory leak prevention)
  const blockRequestTimerRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const sidebarEventTimerRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const favoriteSaveTimerRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const layoutResetTimerRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const sectionPersistTimerRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const tabPersistTimerRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const clearPendingTimers = useCallback(() => {
    clearTimeout(blockRequestTimerRef.current);
    clearTimeout(sidebarEventTimerRef.current);
    clearTimeout(favoriteSaveTimerRef.current);
    clearTimeout(layoutResetTimerRef.current);
    clearTimeout(sectionPersistTimerRef.current);
    clearTimeout(tabPersistTimerRef.current);
  }, []);

  // Clear all timer refs on unmount
  useEffect(() => {
    return clearPendingTimers;
  }, [clearPendingTimers]);

  const requestLayoutBlocks = useCallback(() => {
    clearTimeout(blockRequestTimerRef.current);
    blockRequestTimerRef.current = setTimeout(() => {
      window.dispatchEvent(new CustomEvent("augur:layout-request-blocks"));
    }, 0);
  }, []);

  useEffect(() => {
    let cancelled = false;

    Promise.resolve().then(() => {
      if (cancelled) {
        return;
      }

      const storedFontSettings = loadFontSettings();
      applyFontSettings(
        storedFontSettings.fontFamily,
        storedFontSettings.fontSize,
      );

      dispatchLayoutState({
        type: "loaded",
        state: {
          layouts: loadPageLayouts(),
          loaded: true,
          layoutBlocks: loadLayoutBlocks(pathname),
          fontFamily: storedFontSettings.fontFamily,
          fontSize: storedFontSettings.fontSize,
          sidebarVisibility: loadSidebarVisibility(),
          sectionOrder: loadSidebarOrder(),
          favorites: loadFavorites(),
        },
      });
    });

    return () => {
      cancelled = true;
    };
  }, [pathname]);

  useEffect(() => {
    if (loaded) {
      savePageLayouts(layouts);
    }
  }, [layouts, loaded]);

  useEffect(() => {
    const handleBlocks = (event: CustomEvent<{ blocks?: LayoutBlocks }>) => {
      if (event.detail?.blocks) {
        dispatchLayoutState({
          type: "set-layout-blocks",
          layoutBlocks: event.detail.blocks,
        });
      }
    };

    window.addEventListener(
      "augur:layout-blocks",
      handleBlocks as EventListener,
    );
    requestLayoutBlocks();
    const blockRequestTimer = blockRequestTimerRef.current;

    return () => {
      clearTimeout(blockRequestTimer);
      window.removeEventListener(
        "augur:layout-blocks",
        handleBlocks as EventListener,
      );
    };
  }, [pathname, requestLayoutBlocks]);

  const currentVisibility = layouts[pathname] || {};

  const hasWidgets = (PAGE_WIDGETS[pathname] || []).length > 0;
  const hasBlocks = Object.keys(layoutBlocks).length > 0;

  const tabIconClass = embedded ? "size-4" : "size-3";

  const availableTabs = useMemo(() => {
    const tabs: LayoutTabMeta[] = [
      {
        id: "appearance",
        label: "Typography",
        description: "Font family and size defaults.",
        icon: <Type className={tabIconClass} />,
      },
      {
        id: "navigation",
        label: "Navigation",
        description: "Favorites, sidebar visibility, and tab order.",
        icon: <Navigation className={tabIconClass} />,
      },
      {
        id: "workspace",
        label: "Workspace",
        description: "Widget visibility and per-block sizing controls.",
        icon: <Layout className={tabIconClass} />,
      },
    ];
    return tabs;
  }, [tabIconClass]);

  const effectiveTab = availableTabs.find((t) => t.id === activeTab)
    ? activeTab
    : "appearance";
  const activeTabMeta =
    availableTabs.find((tab) => tab.id === effectiveTab) ?? availableTabs[0];

  const selectActiveTab = useCallback(
    (tab: ActiveTab) => {
      dispatchLayoutState({ type: "set-active-tab", activeTab: tab });
      if (tab === "workspace") {
        requestLayoutBlocks();
      }
    },
    [requestLayoutBlocks],
  );

  const handleFontFamilyChange = (family: string) => {
    dispatchLayoutState({ type: "set-font-family", fontFamily: family });
    applyFontSettings(family, fontSize);
    localStorage.setItem(
      FONT_SETTINGS_KEY,
      JSON.stringify({ fontFamily: family, fontSize }),
    );
  };

  const handleFontSizeChange = (size: string) => {
    dispatchLayoutState({ type: "set-font-size", fontSize: size });
    applyFontSettings(fontFamily, size);
    localStorage.setItem(
      FONT_SETTINGS_KEY,
      JSON.stringify({ fontFamily, fontSize: size }),
    );
  };

  const handleSidebarVisibilityChange = (href: string, isVisible: boolean) => {
    const nextVisibility = { ...sidebarVisibility };
    if (isVisible) {
      delete nextVisibility[href];
    } else {
      nextVisibility[href] = false;
    }

    dispatchLayoutState({
      type: "set-sidebar-state",
      sidebarVisibility: nextVisibility,
      sectionOrder,
    });
    localStorage.setItem(
      SIDEBAR_VISIBILITY_KEY,
      JSON.stringify(nextVisibility),
    );
    clearTimeout(sidebarEventTimerRef.current);
    sidebarEventTimerRef.current = setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent(SIDEBAR_EVENT_KEY, { detail: nextVisibility }),
      );
    }, 0);
  };

  const scheduleSectionPersist = (sectionLabels: string[]) => {
    clearTimeout(sectionPersistTimerRef.current);
    sectionPersistTimerRef.current = setTimeout(() => {
      const items = sectionLabels.map((label, idx) => {
        const hub = label.toLowerCase();
        const navItem = pluginNavItems.find(
          (p) => p.category === hub || p.hubId === hub,
        );
        return { hubId: navItem?.hubId || hub, navOrder: (idx + 1) * 10 };
      });
      // INTENTIONAL_SKIP(adr-269): debounced POST mutation — persisting drag-and-drop order, not a REST GET
      persistHubNavOrder(items).catch(() => {
        /* best-effort persist */
      });
    }, 500);
  };

  const scheduleTabPersist = (
    hubId: string,
    items: { pageId: string; order: number }[],
  ) => {
    clearTimeout(tabPersistTimerRef.current);
    tabPersistTimerRef.current = setTimeout(() => {
      // INTENTIONAL_SKIP(adr-269): debounced POST mutation — persisting drag-and-drop order, not a REST GET
      persistTabNavOrder(
        hubId,
        items,
      ).catch(() => {
        /* best-effort persist */
      });
    }, 500);
  };

  const handleReorderSections = (newOrder: string[]) => {
    dispatchLayoutState({ type: "set-section-order", sectionOrder: newOrder });
    localStorage.setItem(SIDEBAR_ORDER_KEY, JSON.stringify(newOrder));
    clearTimeout(sidebarEventTimerRef.current);
    sidebarEventTimerRef.current = setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent(SIDEBAR_ORDER_EVENT, { detail: newOrder }),
      );
    }, 0);
    scheduleSectionPersist(newOrder);
  };

  const handleReorderTabs = (
    hubId: string,
    tabOrder: { pageId: string; order: number }[],
  ) => {
    scheduleTabPersist(hubId, tabOrder);
  };

  const resetSidebarVisibility = () => {
    dispatchLayoutState({
      type: "set-sidebar-state",
      sidebarVisibility: {},
      sectionOrder: [],
    });
    localStorage.removeItem(SIDEBAR_VISIBILITY_KEY);
    localStorage.removeItem(SIDEBAR_ORDER_KEY);
    clearTimeout(sidebarEventTimerRef.current);
    sidebarEventTimerRef.current = setTimeout(() => {
      window.dispatchEvent(new CustomEvent(SIDEBAR_EVENT_KEY, { detail: {} }));
      window.dispatchEvent(
        new CustomEvent(SIDEBAR_ORDER_EVENT, { detail: [] }),
      );
    }, 0);
  };

  const toggleFavorite = (href: string) => {
    const next = favorites.includes(href)
      ? favorites.filter((item) => item !== href)
      : [...favorites, href];
    dispatchLayoutState({ type: "set-favorites", favorites: next });
    clearTimeout(favoriteSaveTimerRef.current);
    favoriteSaveTimerRef.current = setTimeout(() => saveFavorites(next), 0);
  };

  const resetFavorites = () => {
    const defaultFavorites = ["/"];
    dispatchLayoutState({
      type: "set-favorites",
      favorites: defaultFavorites,
    });
    clearTimeout(favoriteSaveTimerRef.current);
    favoriteSaveTimerRef.current = setTimeout(() => saveFavorites(defaultFavorites), 0);
  };

  const setBlock = (
    id: string,
    patch: { width?: string; height?: string | number },
  ) => {
    const current = layoutBlocks[id] || {};
    const next = { ...current, ...patch };

    if (next.width === "auto") {
      delete next.width;
    }

    if (next.height === "auto") {
      delete next.height;
    }

    const blocks = { ...layoutBlocks };
    if (!next.width && next.height === undefined) {
      delete blocks[id];
    } else {
      blocks[id] = next;
    }

    dispatchLayoutState({ type: "set-layout-blocks", layoutBlocks: blocks });
    saveLayoutBlocks(pathname, blocks);
  };

  const resetBlock = (id: string) => {
    const blocks = { ...layoutBlocks };
    delete blocks[id];
    dispatchLayoutState({ type: "set-layout-blocks", layoutBlocks: blocks });
    saveLayoutBlocks(pathname, blocks);
  };

  const resetAllLayout = () => {
    dispatchLayoutState({ type: "set-layout-blocks", layoutBlocks: {} });
    const layoutKey = `${LAYOUT_STORAGE_PREFIX}${pathname}`;
    localStorage.removeItem(layoutKey);
    clearTimeout(layoutResetTimerRef.current);
    layoutResetTimerRef.current = setTimeout(() => {
      window.dispatchEvent(new CustomEvent("augur:layout-reset-all"));
    }, 0);
  };

  const toggleWidget = useCallback(
    (widgetId: string) => {
      dispatchLayoutState({ type: "toggle-widget", pathname, widgetId });
    },
    [pathname],
  );

  const resetPage = useCallback(() => {
    const next = { ...layouts };
    delete next[pathname];
    dispatchLayoutState({ type: "set-layouts", layouts: next });
  }, [layouts, pathname]);

  const tabContentNode = loaded ? (
    <TabContent
      activeTab={effectiveTab}
      pathname={pathname}
      fontFamily={fontFamily}
      onFontFamilyChange={handleFontFamilyChange}
      fontSize={fontSize}
      onFontSizeChange={handleFontSizeChange}
      favorites={favorites}
      onToggleFavorite={toggleFavorite}
      sidebarVisibility={sidebarVisibility}
      onToggleSidebarVisibility={handleSidebarVisibilityChange}
      sectionOrder={sectionOrder}
      onReorderSections={handleReorderSections}
      onReorderTabs={handleReorderTabs}
      currentVisibility={currentVisibility}
      onToggleWidget={toggleWidget}
      layoutBlocks={layoutBlocks}
      onSetBlock={setBlock}
      onResetBlock={resetBlock}
      hasWidgets={hasWidgets}
      hasBlocks={hasBlocks}
    />
  ) : (
    <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/30 p-6">
      <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
        <Layout className="size-4 motion-safe:animate-pulse text-[var(--accent-primary)]" />
        Loading saved layout preferences…
      </div>
    </div>
  );

  const surfaceProps: LayoutSurfaceProps = {
    availableTabs,
    effectiveTab,
    activeTabMeta,
    tabContentNode,
    onSelectTab: selectActiveTab,
    onResetFavorites: resetFavorites,
    onResetSidebar: resetSidebarVisibility,
    onResetVisibility: resetPage,
    onResetLayout: resetAllLayout,
    onClose: closeModal,
  };

  return surfaceProps;
}
