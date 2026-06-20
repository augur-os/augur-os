export type WidgetVisibility = Record<string, boolean>;
export type PageLayouts = Record<string, WidgetVisibility>;
export type Favorites = string[];
export type LayoutBlocks = Record<
  string,
  { width?: string; height?: string | number }
>;
export type ActiveTab = "appearance" | "navigation" | "workspace";

export type PageWidget = { id: string; label: string };

export const STORAGE_KEY = "augur:widget-visibility:v1";
export const LAYOUT_STORAGE_PREFIX = "augur:layout:v1:";
export const FONT_SETTINGS_KEY = "augur:font-settings:v1";
export const SIDEBAR_VISIBILITY_KEY = "augur:sidebar-visibility:v1";
export const FAVORITES_KEY = "augur:favorites:v1";
export const SIDEBAR_EVENT_KEY = "sidebar-subscription-update";
export const FAVORITES_EVENT_KEY = "augur:favorites-changed";
export const VISIBILITY_EVENT = "augur:widget-visibility-changed";
export const SIDEBAR_ORDER_KEY = "augur:sidebar-order:v1";
export const SIDEBAR_ORDER_EVENT = "augur:sidebar-order-changed";

export const PAGE_WIDGETS: Record<string, PageWidget[]> = {
  "/workspace/memory": [
    { id: "rag-projects", label: "RAG Projects" },
    { id: "rag-search", label: "RAG Search" },
  ],
};

export const fontFamilyMap: Record<string, string> = {
  system: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  inter: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
  roboto: "Roboto, -apple-system, BlinkMacSystemFont, sans-serif",
  outfit: "Outfit, -apple-system, BlinkMacSystemFont, sans-serif",
  jetbrains: '"JetBrains Mono", "Courier New", monospace',
};

export const fontSizeMap: Record<string, string> = {
  small: "14px",
  medium: "16px",
  large: "18px",
  xlarge: "20px",
};

export const fontOptions = [
  { value: "system", label: "System Default", desc: "Native system font" },
  { value: "inter", label: "Inter", desc: "Modern geometric sans-serif" },
  { value: "roboto", label: "Roboto", desc: "Google's friendly sans-serif" },
  { value: "outfit", label: "Outfit", desc: "Rounded geometric font" },
  {
    value: "jetbrains",
    label: "JetBrains Mono",
    desc: "Code-focused monospace",
  },
];

export const sizeOptions = [
  { value: "small", label: "Small", size: "14px" },
  { value: "medium", label: "Medium", size: "16px" },
  { value: "large", label: "Large", size: "18px" },
  { value: "xlarge", label: "XL", size: "20px" },
];
