"use client";

import { Monitor, Moon, Palette, Sun } from "lucide-react";
import { useTheme, type ThemeMode } from "@/hooks/useTheme";

/**
 * ADR-773: Surfaces the existing theme engine (useTheme) as a top-level
 * Appearance card. The same controls also exist inside Layout Settings; both
 * read/write the shared useTheme state, so they stay in sync.
 */
const MODE_OPTIONS: { value: ThemeMode; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

export function ThemeModeCard() {
  const { theme, setTheme, mode, setMode, effectiveMode, themes } = useTheme();

  return (
    <section className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-6 space-y-6">
      <div className="flex items-start gap-3">
        <div className="flex size-10 items-center justify-center rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]">
          <Palette className="size-4 text-[var(--accent-primary)]" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-[var(--text-primary)]">
            Theme &amp; Mode
          </h3>
          <p className="text-sm text-[var(--text-secondary)]">
            Pick the color theme and whether the dashboard follows light, dark,
            or your system preference.
          </p>
        </div>
      </div>

      {/* Mode */}
      <div className="space-y-2">
        <span className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Mode
        </span>
        <div
          role="radiogroup"
          aria-label="Color mode"
          className="inline-flex rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-1"
        >
          {MODE_OPTIONS.map(({ value, label, icon: Icon }) => {
            const active = mode === value;
            return (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={active}
                aria-label={`${label} mode`}
                onClick={() => setMode(value)}
                className={`flex min-h-[36px] items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors duration-200 cursor-pointer ${
                  active
                    ? "bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]"
                    : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                }`}
              >
                <Icon className="size-4" />
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Theme */}
      <div className="space-y-2">
        <span className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Theme
        </span>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {themes.map((t) => {
            const active = theme === t.name;
            const swatch = t.preview[effectiveMode];
            return (
              <button
                key={t.name}
                type="button"
                aria-pressed={active}
                aria-label={`${t.label} theme`}
                onClick={() => setTheme(t.name)}
                className={`flex items-center gap-3 rounded-lg border p-3 text-left transition-colors duration-200 cursor-pointer ${
                  active
                    ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/10"
                    : "border-[var(--border-color)] bg-[var(--bg-secondary)] hover:border-[var(--border-hover)]"
                }`}
              >
                <span
                  className="flex size-8 shrink-0 items-center justify-center rounded-md border border-[var(--border-color)]"
                  style={{ backgroundColor: swatch.primary }}
                >
                  <span
                    className="size-3.5 rounded-full"
                    style={{ backgroundColor: swatch.accent }}
                  />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-[var(--text-primary)]">
                    {t.label}
                  </span>
                  <span className="block truncate text-xs text-[var(--text-muted)]">
                    {t.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
