"use client";

import { useCallback, useMemo } from "react";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

export type VoiceProfileLanguage = "en" | "he";

export const VOICE_PROFILE_LANGUAGES: readonly VoiceProfileLanguage[] = ["en", "he"] as const;

export interface VoiceProfileAboutMe {
  exists: boolean;
  last_updated_at?: string | null;
  age_days?: number | null;
  size_bytes?: number | null;
}

export interface VoiceProfileSlot {
  language?: VoiceProfileLanguage;
  in_progress?: boolean | null;
  answered?: number | null;
  total?: number | null;
  percentage?: number | null;
  started_at?: string | null;
  last_answered_at?: string | null;
  complete?: boolean | null;
  about_me?: VoiceProfileAboutMe | null;
}

export type VoiceProfileStatus = Record<VoiceProfileLanguage, VoiceProfileSlot | null>;

export interface VoiceProfileReadResult {
  success: boolean;
  language?: VoiceProfileLanguage;
  content?: string;
  metadata?: {
    last_updated_at?: string | null;
    age_days?: number | null;
    size_bytes?: number | null;
  } | null;
  error?: string;
  hint?: string;
}

export type VoiceProfileReadMap = Record<VoiceProfileLanguage, VoiceProfileReadResult | null>;

export interface UseVoiceProfileResult {
  status: VoiceProfileStatus | null;
  profiles: VoiceProfileReadMap;
  loading: boolean;
  statusLoading: boolean;
  profileLoading: boolean;
  error: string | null;
  refetch: () => void;
  refresh: () => void;
}

function slotIsComplete(slot: VoiceProfileSlot | null | undefined): boolean {
  return slot?.about_me?.exists === true;
}

function normalizeSlot(language: VoiceProfileLanguage, slot: VoiceProfileSlot | null | undefined): VoiceProfileSlot | null {
  if (!slot) {
    return null;
  }
  const aboutMeExists = slot.about_me?.exists === true;
  const inProgress = slot.in_progress === true;
  const answered = typeof slot.answered === "number" ? slot.answered : 0;
  if (!aboutMeExists && !inProgress && answered <= 0) {
    return null;
  }
  return {
    ...slot,
    language,
    in_progress: inProgress,
    answered,
    total: typeof slot.total === "number" && slot.total > 0 ? slot.total : 100,
    percentage: typeof slot.percentage === "number" ? slot.percentage : null,
    about_me: slot.about_me ?? {
      exists: false,
      last_updated_at: null,
      age_days: null,
      size_bytes: null,
    },
  };
}

function normalizeStatus(raw: unknown): VoiceProfileStatus {
  const data = raw && typeof raw === "object" ? raw as Partial<VoiceProfileStatus> : {};
  return {
    en: normalizeSlot("en", data.en),
    he: normalizeSlot("he", data.he),
  };
}

export function useVoiceProfile(): UseVoiceProfileResult {
  const statusQuery = useMcpQuery<VoiceProfileStatus>(
    ["voice-profile-status"],
    "profile-status",
    "live",
    {
      fallback: { en: null, he: null },
      refetchInterval: 30_000,
      select: normalizeStatus,
    },
  );

  const status = statusQuery.data ?? null;
  const shouldReadEnglish = slotIsComplete(status?.en);
  const shouldReadHebrew = slotIsComplete(status?.he);

  const englishProfileQuery = useMcpQuery<VoiceProfileReadResult>(
    ["voice-profile-read", "en"],
    "profile-read",
    "user-data",
    {
      args: { language: "en" },
      enabled: shouldReadEnglish,
    },
  );

  const hebrewProfileQuery = useMcpQuery<VoiceProfileReadResult>(
    ["voice-profile-read", "he"],
    "profile-read",
    "user-data",
    {
      args: { language: "he" },
      enabled: shouldReadHebrew,
    },
  );

  const profiles = useMemo<VoiceProfileReadMap>(
    () => ({
      en: englishProfileQuery.data ?? null,
      he: hebrewProfileQuery.data ?? null,
    }),
    [englishProfileQuery.data, hebrewProfileQuery.data],
  );

  const refresh = useCallback(() => {
    statusQuery.refetch();
    if (shouldReadEnglish) {
      englishProfileQuery.refetch();
    }
    if (shouldReadHebrew) {
      hebrewProfileQuery.refetch();
    }
  }, [englishProfileQuery, hebrewProfileQuery, shouldReadEnglish, shouldReadHebrew, statusQuery]);

  const profileLoading =
    (shouldReadEnglish && englishProfileQuery.loading) ||
    (shouldReadHebrew && hebrewProfileQuery.loading);

  return {
    status,
    profiles,
    loading: statusQuery.loading || profileLoading,
    statusLoading: statusQuery.loading,
    profileLoading,
    error: statusQuery.error || englishProfileQuery.error || hebrewProfileQuery.error,
    refetch: refresh,
    refresh,
  };
}
