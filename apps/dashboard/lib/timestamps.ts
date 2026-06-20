/**
 * Timestamp utilities for data freshness indicators
 *
 * Provides staleness detection, color coding, and formatting for "last updated" tooltips.
 */

// Staleness thresholds in milliseconds
const STALENESS_THRESHOLDS = {
  FRESH: 24 * 60 * 60 * 1000, // 1 day
  STALE: 7 * 24 * 60 * 60 * 1000, // 7 days
} as const;

export type StalenessLevel = "fresh" | "aging" | "stale";

/**
 * Determine staleness level based on timestamp age
 */
export function getStalenessLevel(
  timestamp: Date | string | number,
): StalenessLevel {
  const now = Date.now();
  const then =
    typeof timestamp === "number" ? timestamp : new Date(timestamp).getTime();
  const age = now - then;

  if (age < STALENESS_THRESHOLDS.FRESH) return "fresh";
  if (age < STALENESS_THRESHOLDS.STALE) return "aging";
  return "stale";
}

/**
 * Get Tailwind color classes for staleness level
 */
export function getStalenessColors(level: StalenessLevel): {
  icon: string;
  text: string;
} {
  switch (level) {
    case "fresh":
      return {
        icon: "text-emerald-400",
        text: "text-emerald-400",
      };
    case "aging":
      return {
        icon: "text-amber-400",
        text: "text-amber-400",
      };
    case "stale":
      return {
        icon: "text-rose-400",
        text: "text-rose-400",
      };
  }
}

/**
 * Format timestamp to human-readable relative time
 * Examples: "just now", "5m ago", "2h ago", "3d ago", "2w ago", "1mo ago"
 */
export function formatTimeAgo(
  timestamp: Date | string | number,
  nowMs?: number,
): string {
  const now = nowMs ?? Date.now();
  const then =
    typeof timestamp === "number" ? timestamp : new Date(timestamp).getTime();
  const diff = now - then;

  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  const weeks = Math.floor(days / 7);
  const months = Math.floor(days / 30);

  if (months > 0) return `${months}mo ago`;
  if (weeks > 0) return `${weeks}w ago`;
  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (mins > 0) return `${mins}m ago`;
  return "just now";
}

/**
 * Format timestamp to full localized date string
 * Example: "Jan 16, 2026, 3:45 PM"
 */
export function formatDateFull(timestamp: Date | string | number): string {
  const date = new Date(timestamp);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Format timestamp to ISO date string (YYYY-MM-DD)
 */
function formatDateShort(timestamp: Date | string | number): string {
  const date = new Date(timestamp);
  return date.toISOString().split("T")[0];
}
