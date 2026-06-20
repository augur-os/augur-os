import { create } from "zustand";

export type DashboardMode = "operation" | "development";

const STORAGE_KEY = "augur:dashboard-mode";
const DEFAULT_MODE: DashboardMode = "operation";

interface ModeState {
  mode: DashboardMode;
  toggleMode: () => void;
  setMode: (mode: DashboardMode) => void;
}

export const useModeStore = create<ModeState>((set) => ({
  // Always start with server-safe default to avoid hydration mismatch.
  // Client-side hydration happens below via subscribe + localStorage read.
  mode: DEFAULT_MODE,

  toggleMode: () =>
    set((state) => {
      const next = state.mode === "operation" ? "development" : "operation";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* ignore */
      }
      return { mode: next };
    }),

  setMode: (mode) => {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      /* ignore */
    }
    set({ mode });
  },
}));

// Hydrate from localStorage after first client-side render.
// This runs once when the module loads on the client, after React hydration.
if (typeof window !== "undefined") {
  // Use queueMicrotask to run after hydration completes
  queueMicrotask(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "operation" || stored === "development") {
        const current = useModeStore.getState().mode;
        if (stored !== current) {
          useModeStore.setState({ mode: stored });
        }
      }
    } catch {
      /* private browsing */
    }
  });
}
