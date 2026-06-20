"use client";

import { useReducer, useEffect, useLayoutEffect, useCallback } from "react";
import { mcpCall } from "@/lib/mcp/client";

const THEME_STORAGE_KEY = "augur:theme:v2";
const MODE_STORAGE_KEY = "augur:theme-mode:v1";
const THEME_CHANGE_EVENT = "augur:theme-changed";

export type ThemeName = "futuristic" | "office" | "modern" | "blossom";
export type ThemeMode = "light" | "dark" | "system";

export interface ThemeDefinition {
  name: ThemeName;
  label: string;
  description: string;
  preview: {
    dark: { primary: string; accent: string };
    light: { primary: string; accent: string };
  };
}

export const themes: ThemeDefinition[] = [
  {
    name: "futuristic",
    label: "Futuristic",
    description: "Cyber-noir / warm paper aesthetic",
    preview: {
      dark: { primary: "#050505", accent: "#00f0ff" },
      light: { primary: "#F9F8F6", accent: "#D97757" },
    },
  },
  {
    name: "office",
    label: "Office",
    description: "Professional corporate appearance",
    preview: {
      dark: { primary: "#0f172a", accent: "#0066cc" },
      light: { primary: "#f8fafc", accent: "#2563eb" },
    },
  },
  {
    name: "modern",
    label: "Modern",
    description: "Clean, minimal design",
    preview: {
      dark: { primary: "#09090b", accent: "#6366f1" },
      light: { primary: "#fafafa", accent: "#4f46e5" },
    },
  },
  {
    name: "blossom",
    label: "Blossom",
    description: "Warm, inviting palette",
    preview: {
      dark: { primary: "#0c0a09", accent: "#f472b6" },
      light: { primary: "#fff1f2", accent: "#e11d48" },
    },
  },
];

function getSystemPreference(): "light" | "dark" {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

function getEffectiveMode(mode: ThemeMode): "light" | "dark" {
  if (mode === "system") {
    return getSystemPreference();
  }
  return mode;
}

function applyTheme(theme: ThemeName, mode: ThemeMode) {
  const effectiveMode = getEffectiveMode(mode);
  const themeValue = effectiveMode === "light" ? `${theme}-light` : theme;
  document.documentElement.setAttribute("data-theme", themeValue);
  document.documentElement.setAttribute("data-mode", effectiveMode);
  document.documentElement.style.colorScheme = effectiveMode;
}

// Helper to get initial theme from localStorage
function getInitialTheme(): ThemeName {
  if (typeof window === "undefined") return "futuristic";
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored && themes.some((t) => t.name === stored)) {
      return stored as ThemeName;
    }
  } catch {
    /* ignore */
  }
  return "futuristic";
}

// Helper to get initial mode from localStorage
function getInitialMode(): ThemeMode {
  if (typeof window === "undefined") return "system";
  try {
    const stored = localStorage.getItem(MODE_STORAGE_KEY);
    if (stored && ["light", "dark", "system"].includes(stored)) {
      return stored as ThemeMode;
    }
  } catch {
    /* ignore */
  }
  return "system";
}

interface ThemeState {
  theme: ThemeName;
  mode: ThemeMode;
}

type ThemeStateAction =
  | { type: "set-theme"; theme: ThemeName }
  | { type: "set-mode"; mode: ThemeMode }
  | { type: "set-preferences"; theme: ThemeName; mode: ThemeMode };

function themeReducer(state: ThemeState, action: ThemeStateAction): ThemeState {
  switch (action.type) {
    case "set-theme":
      return { ...state, theme: action.theme };
    case "set-mode":
      return { ...state, mode: action.mode };
    case "set-preferences":
      return { theme: action.theme, mode: action.mode };
    default:
      return state;
  }
}

function getInitialThemeState(): ThemeState {
  return {
    theme: getInitialTheme(),
    mode: getInitialMode(),
  };
}

function isThemeName(value: string | null | undefined): value is ThemeName {
  return !!value && themes.some((t) => t.name === value);
}

function isThemeMode(value: string | null | undefined): value is ThemeMode {
  return value === "light" || value === "dark" || value === "system";
}

export function useTheme() {
  const [{ theme, mode }, dispatchThemeState] = useReducer(
    themeReducer,
    undefined,
    getInitialThemeState,
  );
  const loaded = true;

  // Get the effective mode (resolves 'system' to actual light/dark)
  const effectiveMode = getEffectiveMode(mode);

  useEffect(() => {
    applyTheme(theme, mode);
  }, [theme, mode]);

  // Backfill localStorage from backend if empty.
  useEffect(() => {
    // INTENTIONAL_SKIP(adr-269): conditional one-time backfill — only fetches when localStorage is empty, not a recurring data fetch
    // Only use backend as fallback when localStorage has no values
    // localStorage is authoritative — it reflects the user's most recent action
    const backfillFromBackend = async () => {
      const hasLocalTheme = !!localStorage.getItem(THEME_STORAGE_KEY);
      const hasLocalMode = !!localStorage.getItem(MODE_STORAGE_KEY);

      // If localStorage already has both values, nothing to do
      if (hasLocalTheme && hasLocalMode) return;

      try {
        const prefs = await mcpCall<Record<string, string>>("get-preferences", {}, { fallback: null });
        if (!prefs) return;
        let nextTheme: ThemeName | null = null;
        let nextMode: ThemeMode | null = null;

        // Backfill theme only if localStorage is empty
        if (!hasLocalTheme && isThemeName(prefs.ui_theme)) {
          nextTheme = prefs.ui_theme;
          localStorage.setItem(THEME_STORAGE_KEY, prefs.ui_theme);
        }

        // Backfill mode only if localStorage is empty
        if (!hasLocalMode && isThemeMode(prefs.ui_mode)) {
          nextMode = prefs.ui_mode;
          localStorage.setItem(MODE_STORAGE_KEY, prefs.ui_mode);
        }

        if (nextTheme || nextMode) {
          const currentTheme = nextTheme ?? getInitialTheme();
          const currentMode = nextMode ?? getInitialMode();
          dispatchThemeState({
            type: "set-preferences",
            theme: currentTheme,
            mode: currentMode,
          });
          applyTheme(currentTheme, currentMode);
        }
      } catch {
        // Non-blocking fallback: localStorage remains the source of truth.
      }
    };
    backfillFromBackend();
  }, []); // Only run on mount - theme/mode changes are handled elsewhere

  // Listen for system preference changes when mode is 'system'
  useEffect(() => {
    if (mode !== "system") return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: light)");
    const handleChange = () => {
      applyTheme(theme, "system");
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [mode, theme]);

  // INTENTIONAL_SKIP(adr-269): fire-and-forget POST — best-effort preference persistence, not a REST GET
  const savePreference = useCallback((key: string, value: string) => {
    // Preference persistence is best-effort; localStorage remains authoritative.
    if (typeof window !== "undefined" && !window.navigator.onLine) {
      return;
    }

    try {
      void mcpCall("update-preference", { key, value }).catch(() => {
        // Ignore transient network errors.
      });
    } catch {
      // Ignore sync failures completely (non-critical).
    }
  }, []);

  // Apply theme and persist
  const setTheme = useCallback(
    (newTheme: ThemeName) => {
      dispatchThemeState({ type: "set-theme", theme: newTheme });
      try {
        localStorage.setItem(THEME_STORAGE_KEY, newTheme);
        applyTheme(newTheme, mode);
        window.dispatchEvent(
          new CustomEvent(THEME_CHANGE_EVENT, {
            detail: { theme: newTheme, mode },
          }),
        );
        savePreference("ui_theme", newTheme);
      } catch {
        // Ignore errors
      }
    },
    [mode, savePreference],
  );

  // Apply mode and persist
  const setMode = useCallback(
    (newMode: ThemeMode) => {
      dispatchThemeState({ type: "set-mode", mode: newMode });
      try {
        localStorage.setItem(MODE_STORAGE_KEY, newMode);
        applyTheme(theme, newMode);
        window.dispatchEvent(
          new CustomEvent(THEME_CHANGE_EVENT, {
            detail: { theme, mode: newMode },
          }),
        );
        savePreference("ui_mode", newMode);
      } catch {
        // Ignore errors
      }
    },
    [theme, savePreference],
  );

  // Listen for cross-tab changes
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      let nextTheme: ThemeName | null = null;
      let nextMode: ThemeMode | null = null;
      if (e.key === THEME_STORAGE_KEY && e.newValue) {
        if (isThemeName(e.newValue)) {
          nextTheme = e.newValue;
        }
      }
      if (e.key === MODE_STORAGE_KEY && e.newValue) {
        if (isThemeMode(e.newValue)) {
          nextMode = e.newValue;
        }
      }
      if (!nextTheme && !nextMode) return;
      const currentTheme = nextTheme ?? theme;
      const currentMode = nextMode ?? mode;
      dispatchThemeState({
        type: "set-preferences",
        theme: currentTheme,
        mode: currentMode,
      });
      applyTheme(currentTheme, currentMode);
    };

    const handleThemeChange = (
      e: CustomEvent<{ theme: ThemeName; mode: ThemeMode }>,
    ) => {
      if (!e.detail) return;
      const nextTheme = isThemeName(e.detail.theme) ? e.detail.theme : theme;
      const nextMode = isThemeMode(e.detail.mode) ? e.detail.mode : mode;
      dispatchThemeState({
        type: "set-preferences",
        theme: nextTheme,
        mode: nextMode,
      });
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener(
      THEME_CHANGE_EVENT,
      handleThemeChange as EventListener,
    );

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(
        THEME_CHANGE_EVENT,
        handleThemeChange as EventListener,
      );
    };
  }, [mode, theme]);

  return { theme, setTheme, mode, setMode, effectiveMode, themes, loaded };
}

/**
 * Lightweight component that applies theme attributes on mount.
 * Must be rendered in the root layout to ensure theme persists after hydration.
 * The inline <script> in <head> handles the initial paint (no flash),
 * but React hydration can strip the data-theme/data-mode attributes.
 * This component re-applies them after hydration completes.
 */
export function ThemeInitializer() {
  useLayoutEffect(() => {
    const t = localStorage.getItem(THEME_STORAGE_KEY) || "futuristic";
    const m = localStorage.getItem(MODE_STORAGE_KEY) || "system";
    const isDark =
      m === "dark" ||
      (m === "system" &&
        window.matchMedia("(prefers-color-scheme:dark)").matches);
    const themeValue = isDark ? t : `${t}-light`;
    document.documentElement.setAttribute("data-theme", themeValue);
    document.documentElement.setAttribute(
      "data-mode",
      isDark ? "dark" : "light",
    );
    document.documentElement.style.colorScheme = isDark ? "dark" : "light";
  }, []);

  return null;
}
