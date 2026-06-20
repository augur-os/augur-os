import {
  type PageLayouts,
  type Favorites,
  type LayoutBlocks,
  STORAGE_KEY,
  LAYOUT_STORAGE_PREFIX,
  FONT_SETTINGS_KEY,
  SIDEBAR_VISIBILITY_KEY,
  FAVORITES_KEY,
  FAVORITES_EVENT_KEY,
  VISIBILITY_EVENT,
  fontFamilyMap,
  fontSizeMap,
  SIDEBAR_ORDER_KEY,
} from "./types";

export function loadPageLayouts(): PageLayouts {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function loadFavorites(): Favorites {
  if (typeof window === "undefined") {
    return ["/"];
  }

  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    return raw ? JSON.parse(raw) : ["/"];
  } catch {
    return ["/"];
  }
}

export function saveFavorites(favorites: Favorites): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
    setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent(FAVORITES_EVENT_KEY, { detail: favorites }),
      );
    }, 0);
  } catch {
    // Ignore quota errors
  }
}

export function savePageLayouts(layouts: PageLayouts): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layouts));
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent(VISIBILITY_EVENT));
    }, 0);
  } catch {
    // Ignore quota errors
  }
}

export function applyFontSettings(family: string, size: string): void {
  if (typeof document === "undefined") {
    return;
  }

  const root = document.documentElement;
  root.style.setProperty(
    "--font-family-base",
    fontFamilyMap[family] || fontFamilyMap.system,
  );
  root.style.setProperty(
    "--font-size-base",
    fontSizeMap[size] || fontSizeMap.medium,
  );
}

export function loadLayoutBlocks(pathname: string): LayoutBlocks {
  try {
    const layoutKey = `${LAYOUT_STORAGE_PREFIX}${pathname}`;
    const raw = localStorage.getItem(layoutKey);
    if (!raw) {
      return {};
    }

    const parsed = JSON.parse(raw);
    return parsed.blocks || {};
  } catch {
    return {};
  }
}

export function loadFontSettings() {
  try {
    const raw = localStorage.getItem(FONT_SETTINGS_KEY);
    if (!raw) {
      return { fontFamily: "system", fontSize: "medium" };
    }

    const parsed = JSON.parse(raw);
    return {
      fontFamily: parsed.fontFamily || "system",
      fontSize: parsed.fontSize || "medium",
    };
  } catch {
    return { fontFamily: "system", fontSize: "medium" };
  }
}

export function loadSidebarOrder(): string[] {
  try {
    const raw = localStorage.getItem(SIDEBAR_ORDER_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function loadSidebarVisibility(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(SIDEBAR_VISIBILITY_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function saveLayoutBlocks(pathname: string, blocks: LayoutBlocks) {
  const layoutKey = `${LAYOUT_STORAGE_PREFIX}${pathname}`;
  const layout = { version: 1, blocks };
  localStorage.setItem(layoutKey, JSON.stringify(layout));
  window.dispatchEvent(
    new CustomEvent("augur:layout-updated", { detail: layout }),
  );
}
