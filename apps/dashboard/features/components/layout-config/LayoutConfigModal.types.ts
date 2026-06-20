import type {
  WidgetVisibility,
  PageLayouts,
  Favorites,
  LayoutBlocks,
  ActiveTab,
} from "./types";

export type LayoutConfigModalProps = {
  onClose?: () => void;
  embedded?: boolean;
};

export interface LayoutConfigState {
  layouts: PageLayouts;
  loaded: boolean;
  activeTab: ActiveTab;
  layoutBlocks: LayoutBlocks;
  fontFamily: string;
  fontSize: string;
  sidebarVisibility: Record<string, boolean>;
  sectionOrder: string[];
  favorites: Favorites;
}

export type LayoutConfigAction =
  | { type: "loaded"; state: Omit<LayoutConfigState, "activeTab"> }
  | { type: "set-active-tab"; activeTab: ActiveTab }
  | { type: "set-font-family"; fontFamily: string }
  | { type: "set-font-size"; fontSize: string }
  | { type: "set-sidebar-state"; sidebarVisibility: Record<string, boolean>; sectionOrder: string[] }
  | { type: "set-section-order"; sectionOrder: string[] }
  | { type: "set-favorites"; favorites: Favorites }
  | { type: "set-layout-blocks"; layoutBlocks: LayoutBlocks }
  | { type: "set-layouts"; layouts: PageLayouts }
  | { type: "toggle-widget"; pathname: string; widgetId: string };

export interface LayoutTabMeta {
  id: ActiveTab;
  label: string;
  description: string;
  icon: React.ReactNode;
}

export interface LayoutSurfaceProps {
  availableTabs: LayoutTabMeta[];
  effectiveTab: ActiveTab;
  activeTabMeta: LayoutTabMeta | undefined;
  tabContentNode: React.ReactNode;
  onSelectTab: (tab: ActiveTab) => void;
  onResetFavorites: () => void;
  onResetSidebar: () => void;
  onResetVisibility: () => void;
  onResetLayout: () => void;
  onClose: () => void;
}

// Re-exported for sibling convenience (controller uses WidgetVisibility via TabContent props).
export type { WidgetVisibility, PageLayouts, Favorites, LayoutBlocks, ActiveTab };
