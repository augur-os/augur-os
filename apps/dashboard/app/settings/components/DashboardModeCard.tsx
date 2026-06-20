"use client";

import { Monitor } from "lucide-react";
import { useModeStore } from "@/lib/stores/modeStore";

/**
 * ADR-507: Dashboard mode toggle — switch between operation and development mode.
 * Development mode reveals dev-only Brain tabs and Browse capability categories.
 *
 * ADR-773: Moved out of the General/Workspace tab into Appearance, where the
 * "what the dashboard shows" controls live.
 */
export function DashboardModeCard() {
  const { mode, toggleMode } = useModeStore();
  const isDev = mode === "development";

  return (
    <section className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Monitor className="size-5 text-[var(--accent-primary)]" />
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Dashboard Mode
          </h3>
          <p className="text-xs text-[var(--text-muted)]">
            Switch between operation and development mode. Development mode shows
            diagnostic Brain tabs and developer inventory categories in Browse.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button type="button"
          onClick={toggleMode}
          className={`
            relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 cursor-pointer
            ${isDev ? "bg-[var(--accent-primary)]" : "bg-[var(--border-color)]"}
          `}
          role="switch"
          aria-checked={isDev}
          aria-label="Toggle development mode"
        >
          <span
            className={`
              inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200
              ${isDev ? "translate-x-6" : "translate-x-1"}
            `}
          />
        </button>
        <div className="flex flex-col">
          <span className="text-sm font-medium text-[var(--text-primary)]">
            {isDev ? "Development" : "Operation"}
          </span>
          <span className="text-xs text-[var(--text-muted)]">
            {isDev
              ? "Developer diagnostics and inventory categories are visible"
              : "Streamlined view with Brain and Browse only"}
          </span>
        </div>
      </div>
    </section>
  );
}
