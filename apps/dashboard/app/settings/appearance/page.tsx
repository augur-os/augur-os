"use client";

import dynamic from "next/dynamic";
import { SkillNavSettingsCard } from "../components/SkillNavSettingsCard";
import { DashboardModeCard } from "../components/DashboardModeCard";

// Theme state is read from localStorage (client-authoritative via useTheme), so
// server markup can't match the first client render. Render client-only to avoid
// a hydration mismatch — same pattern as LayoutConfigModal below.
const ThemeModeCard = dynamic(
  () => import("../components/ThemeModeCard").then((m) => m.ThemeModeCard),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-6 space-y-5">
        <div className="h-9 w-48 rounded-lg bg-[var(--bg-secondary)] animate-pulse" />
        <div className="h-9 w-56 rounded-lg bg-[var(--bg-secondary)] animate-pulse" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-16 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] animate-pulse"
            />
          ))}
        </div>
      </div>
    ),
  },
);

const LayoutConfigModal = dynamic(
  () => import("@/features/components/layout-config/LayoutConfigModal"),
  {
    ssr: false,
    loading: () => (
      <div className="overflow-hidden rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)]">
        <div className="grid lg:grid-cols-[250px_minmax(0,1fr)]">
          <div className="space-y-3 border-b border-[var(--border-color)] bg-[var(--bg-secondary)]/40 p-5 lg:border-b-0 lg:border-r">
            {[...Array(3)].map((_, i) => (
              <div
                key={i}
                className="h-14 rounded-xl bg-[var(--bg-secondary)] animate-pulse"
              />
            ))}
          </div>
          <div className="space-y-4 p-6">
            <div className="h-6 w-40 rounded bg-[var(--bg-secondary)] animate-pulse" />
            <div className="h-24 rounded-xl bg-[var(--bg-secondary)] animate-pulse" />
          </div>
        </div>
      </div>
    ),
  },
);

export default function SettingsAppearancePage() {
  return (
    <section className="space-y-6">
      <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-6">
        <div className="max-w-3xl space-y-2">
          <h2 className="text-2xl font-semibold text-[var(--text-primary)]">
            Appearance &amp; Layout
          </h2>
          <p className="text-sm text-[var(--text-secondary)]">
            Customize theme, navigation, sidebar skills, and workspace behavior.
          </p>
        </div>
      </div>

      <ThemeModeCard />

      <DashboardModeCard />

      <SkillNavSettingsCard />

      <LayoutConfigModal embedded />
    </section>
  );
}
