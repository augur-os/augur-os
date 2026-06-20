"use client";

import Markdown from "@/components/Markdown";
import DashboardWidget from "@/features/components/DashboardWidget";
import { formatTimeAgo } from "@/lib/timestamps";
import { AlertTriangle, CheckCircle2, Clock3, Copy, Languages, RefreshCcw } from "lucide-react";
import type { ReactNode } from "react";
import { toast } from "sonner";
import {
  VOICE_PROFILE_LANGUAGES,
  useVoiceProfile,
  type VoiceProfileLanguage,
  type VoiceProfileReadResult,
  type VoiceProfileSlot,
} from "../hooks/useVoiceProfile";

const STALE_PROFILE_DAYS = 180;

const LANGUAGE_META: Record<
  VoiceProfileLanguage,
  {
    badge: string;
    label: string;
    direction: "ltr" | "rtl";
  }
> = {
  en: { badge: "EN", label: "English", direction: "ltr" },
  he: { badge: "HE", label: "Hebrew", direction: "rtl" },
};

function isActiveSlot(slot: VoiceProfileSlot | null): slot is VoiceProfileSlot {
  return slot?.about_me?.exists === true || slot?.in_progress === true;
}

function isCompleteSlot(slot: VoiceProfileSlot): boolean {
  return slot.about_me?.exists === true;
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function positiveNumber(value: number | null | undefined, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : fallback;
}

function progressFor(slot: VoiceProfileSlot): number {
  if (typeof slot.percentage === "number") {
    return clampPercent(slot.percentage);
  }
  const total = positiveNumber(slot.total, 100);
  const answered = positiveNumber(slot.answered, 0);
  return total > 0 ? clampPercent((answered / total) * 100) : 0;
}

function ageDaysFor(slot: VoiceProfileSlot, profile: VoiceProfileReadResult | null): number | null {
  const profileAge = profile?.metadata?.age_days;
  if (typeof profileAge === "number" && Number.isFinite(profileAge)) {
    return profileAge;
  }
  const slotAge = slot.about_me?.age_days;
  return typeof slotAge === "number" && Number.isFinite(slotAge) ? slotAge : null;
}

function formatNullableTime(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }
  return formatTimeAgo(value);
}

async function copyCommand(command: string) {
  try {
    if (typeof navigator === "undefined" || !navigator.clipboard) {
      throw new Error("Clipboard unavailable");
    }
    await navigator.clipboard.writeText(command);
    toast.success("Paste in your AI client");
  } catch {
    toast.error(`Copy failed: ${command}`);
  }
}

function LanguageBadge({ language }: { language: VoiceProfileLanguage }) {
  const meta = LANGUAGE_META[language];
  return (
    <span className="inline-flex min-h-7 items-center rounded-full border border-[var(--border-color)] bg-[var(--bg-hover)] px-2.5 text-xs font-semibold text-[var(--text-secondary)]">
      {meta.badge}
    </span>
  );
}

function ActionButton({
  command,
  children,
  icon,
}: {
  command: string;
  children: ReactNode;
  icon: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={() => void copyCommand(command)}
      className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-secondary)] transition-colors hover:border-[var(--text-muted)]/40 hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
      aria-label={`Copy ${command}`}
    >
      {icon}
      <span>{children}</span>
    </button>
  );
}

function EmptyVoiceProfileCard() {
  return (
    <div
      className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5"
      data-testid="voice-profile-empty-card"
    >
      <div className="flex items-start gap-3">
        <div className="rounded-xl border border-purple-500/25 bg-purple-500/10 p-3">
          <Languages className="size-5 text-purple-400" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-[var(--text-primary)]">Create your voice profile</h3>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            Your voice profile captures how you think, write, and speak so AI clients can personalize their responses
            to you.
          </p>
          <p className="mt-2 text-sm text-[var(--text-muted)]">
            Run <code>/profile interview</code> in your AI client to create one. English or Hebrew supported.
          </p>
          <div className="mt-4">
            <ActionButton command="/profile interview" icon={<Copy className="size-4" aria-hidden="true" />}>
              Copy /profile interview
            </ActionButton>
          </div>
        </div>
      </div>
    </div>
  );
}

function InProgressLanguageCard({
  language,
  slot,
}: {
  language: VoiceProfileLanguage;
  slot: VoiceProfileSlot;
}) {
  const meta = LANGUAGE_META[language];
  const answered = positiveNumber(slot.answered, 0);
  const total = positiveNumber(slot.total, 100);
  const percent = progressFor(slot);

  return (
    <section
      className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5"
      data-testid={`voice-profile-card-${language}`}
      aria-label={`${meta.label} voice profile interview`}
      dir={meta.direction}
    >
      <div data-testid="voice-profile-language-card" className="space-y-4">
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <LanguageBadge language={language} />
              <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-300">
                <Clock3 className="size-3.5" aria-hidden="true" />
                Interview in progress
              </span>
            </div>
            <h3 className="mt-3 text-base font-semibold text-[var(--text-primary)]">{meta.label} Voice Profile</h3>
          </div>
        </header>

        <div>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="font-medium text-[var(--text-primary)]">
              {answered} of {total} questions answered
            </span>
            <span className="text-[var(--text-muted)]">{percent}%</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-[var(--bg-hover)]">
            <progress
              className="sr-only"
              value={percent}
              max={100}
              aria-label={`${meta.label} interview progress`}
              aria-valuenow={percent}
            />
            <div className="h-full rounded-full bg-amber-400 transition-[width]" style={{ width: `${percent}%` }} aria-hidden="true" />
          </div>
        </div>

        <p className="text-xs text-[var(--text-muted)]">
          Started: {formatNullableTime(slot.started_at)} / Last answered: {formatNullableTime(slot.last_answered_at)}
        </p>
        <p className="text-sm text-[var(--text-secondary)]">
          Continue by running <code>/profile interview</code> in your AI client. Progress saves after every answer.
        </p>
        <ActionButton command="/profile interview" icon={<Copy className="size-4" aria-hidden="true" />}>
          Copy /profile interview
        </ActionButton>
      </div>
    </section>
  );
}

function CompletedLanguageCard({
  language,
  slot,
  profile,
}: {
  language: VoiceProfileLanguage;
  slot: VoiceProfileSlot;
  profile: VoiceProfileReadResult | null;
}) {
  const meta = LANGUAGE_META[language];
  const ageDays = ageDaysFor(slot, profile);
  const lastUpdated = profile?.metadata?.last_updated_at ?? slot.about_me?.last_updated_at ?? null;
  const isStale = typeof ageDays === "number" && ageDays > STALE_PROFILE_DAYS;
  const markdown = profile?.success && typeof profile.content === "string" ? profile.content : "";

  return (
    <section
      className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5"
      data-testid={`voice-profile-card-${language}`}
      aria-label={`${meta.label} voice profile`}
      dir={meta.direction}
    >
      <div data-testid="voice-profile-language-card" className="space-y-4">
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <LanguageBadge language={language} />
              <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-300">
                <CheckCircle2 className="size-3.5" aria-hidden="true" />
                Complete
              </span>
            </div>
            <h3 className="mt-3 text-base font-semibold text-[var(--text-primary)]">{meta.label} Voice Profile</h3>
          </div>
        </header>

        {isStale && (
          <div
            role="alert"
            className="rounded-lg border border-amber-500/35 bg-amber-500/10 px-3 py-2 text-sm text-amber-100"
          >
            <AlertTriangle className="mr-2 inline size-4 text-amber-300" aria-hidden="true" />
            Profile is {ageDays} days old. Consider running <code>/profile update {language}</code> in your AI client.
          </div>
        )}

        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-4">
          {markdown ? (
            <Markdown markdown={markdown} />
          ) : (
            <p className="text-sm text-[var(--text-muted)]">Profile content is loading.</p>
          )}
        </div>

        <div className="flex flex-col gap-3 text-xs text-[var(--text-muted)] md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <span>Last updated: {formatNullableTime(lastUpdated)}</span>
            <span>Age: {ageDays === null ? "Unknown" : `${ageDays} days`}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <ActionButton command="/profile interview" icon={<RefreshCcw className="size-4" aria-hidden="true" />}>
              Re-run interview
            </ActionButton>
            <ActionButton command={`/profile update ${language}`} icon={<Copy className="size-4" aria-hidden="true" />}>
              Update {meta.badge}
            </ActionButton>
          </div>
        </div>
      </div>
    </section>
  );
}

export function VoiceProfile() {
  const { status, profiles, loading, error } = useVoiceProfile();
  const activeLanguages = VOICE_PROFILE_LANGUAGES.filter((language) => isActiveSlot(status?.[language] ?? null));

  return (
    <DashboardWidget title="Voice Profile" icon={Languages} fillHeight={false} maxHeight={null} scrollable={false}>
      <div className="space-y-3">
        {error && (
          <div className="rounded-lg border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 px-3 py-2 text-sm text-[var(--text-primary)]" role="alert">
            {error}
          </div>
        )}

        {!status && loading && (
          <div className="h-40 animate-pulse rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]" />
        )}

        {status && activeLanguages.length === 0 && <EmptyVoiceProfileCard />}

        {activeLanguages.map((language) => {
          const slot = status?.[language];
          if (!slot) {
            return null;
          }
          return isCompleteSlot(slot) ? (
            <CompletedLanguageCard key={language} language={language} slot={slot} profile={profiles[language]} />
          ) : (
            <InProgressLanguageCard key={language} language={language} slot={slot} />
          );
        })}
      </div>
    </DashboardWidget>
  );
}
