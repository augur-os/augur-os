"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import {
  loadPageLayouts,
  loadFavorites,
} from "./storage";

export function useWidgetVisibility(widgetId: string): boolean {
  const pathname = usePathname() ?? "/";
  const [visible, setVisible] = useState(true);
  const VISIBILITY_EVENT = "augur:widget-visibility-changed";

  useEffect(() => {
    const checkVisibility = () => {
      const layouts = loadPageLayouts();
      const pageLayout = layouts[pathname] || {};
      setVisible(pageLayout[widgetId] !== false);
    };

    checkVisibility();
    window.addEventListener("storage", checkVisibility);
    window.addEventListener(VISIBILITY_EVENT, checkVisibility);

    return () => {
      window.removeEventListener("storage", checkVisibility);
      window.removeEventListener(VISIBILITY_EVENT, checkVisibility);
    };
  }, [pathname, widgetId]);

  return visible;
}

export function useIsFavorite(href: string): boolean {
  const [isFav, setIsFav] = useState(false);
  const FAVORITES_EVENT_KEY = "augur:favorites-changed";

  useEffect(() => {
    const checkFavorite = () => {
      const favorites = loadFavorites();
      setIsFav(favorites.includes(href));
    };

    checkFavorite();
    window.addEventListener("storage", checkFavorite);
    window.addEventListener(FAVORITES_EVENT_KEY, checkFavorite);

    return () => {
      window.removeEventListener("storage", checkFavorite);
      window.removeEventListener(FAVORITES_EVENT_KEY, checkFavorite);
    };
  }, [href]);

  return isFav;
}
