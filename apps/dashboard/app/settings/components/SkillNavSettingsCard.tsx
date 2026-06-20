"use client";

import { useMemo } from "react";
import { Loader2, Navigation } from "lucide-react";
import { useMcpMutation } from "@/lib/mcp/useMcpMutation";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

type SkillNavEntry = {
  skill: string;
  bundle: string;
  hub: string;
  navVisible: boolean;
  reason: string;
  canToggle: boolean;
};

export function SkillNavSettingsCard() {
  const { data, loading } = useMcpQuery<{ skills?: SkillNavEntry[] }>(
    ["skill-nav-settings"],
    "list-skills",
    "config",
    {
      args: { nav: true },
    },
  );

  const { mutate: toggleSkillNav, loading: toggling } = useMcpMutation<
    { success?: boolean; message?: string; error?: string },
    { scope: string; skill: string; visible: boolean }
  >("set-config", {
    invalidates: ["skill-nav-settings"],
  });

  const entries = useMemo(
    () =>
      [...(data?.skills ?? [])]
        .filter((entry) => entry.canToggle)
        .sort((a, b) => {
          if (a.navVisible !== b.navVisible) return a.navVisible ? -1 : 1;
          return a.skill.localeCompare(b.skill);
        }),
    [data],
  );

  return (
    <section className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-6">
      <div className="mb-4 flex items-start gap-3">
        <div className="flex size-10 items-center justify-center rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]">
          <Navigation className="size-4 text-[var(--accent-primary)]" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-[var(--text-primary)]">
            Sidebar Skills
          </h3>
          <p className="text-sm text-[var(--text-secondary)]">
            Choose which standalone skills stay visible in the sidebar. This replaces the old builder-mode Skill Nav menu.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3 text-sm text-[var(--text-secondary)]">
          <Loader2 className="size-4 animate-spin" />
          Loading sidebar skills…
        </div>
      ) : entries.length === 0 ? (
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3 text-sm text-[var(--text-secondary)]">
          No standalone skills are available for sidebar toggling.
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => (
            <div
              key={entry.skill}
              className="flex items-center justify-between gap-4 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    {entry.skill}
                  </span>
                  <span className="rounded-full border border-[var(--border-color)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                    {entry.bundle}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  {entry.reason}
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  toggleSkillNav({
                    scope: "skill-nav-toggle",
                    skill: entry.skill,
                    visible: !entry.navVisible,
                  })
                }
                disabled={toggling}
                aria-pressed={entry.navVisible}
                aria-label={`${entry.navVisible ? "Hide" : "Show"} ${entry.skill} in sidebar`}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ${
                  entry.navVisible
                    ? "bg-[var(--accent-primary)]"
                    : "bg-[var(--border-color)]"
                } ${toggling ? "opacity-60" : ""}`}
              >
                <span
                  className={`inline-block size-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
                    entry.navVisible ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
