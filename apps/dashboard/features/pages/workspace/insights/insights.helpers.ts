import type { BrainInsight, BrainInsightsRun, InsightSource } from "./types";

export function formatNumber(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString() : "0";
}

export function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "Unknown";
  }
  return `${Math.round(value * 100)}%`;
}

export function formatWhen(value: string | null | undefined) {
  if (!value) {
    return "Unknown time";
  }
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timestampValue(value: string | null | undefined) {
  if (!value) {
    return null;
  }
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : null;
}

export function metricIssues(values: Array<unknown[] | undefined>) {
  return values.reduce((total, value) => total + (Array.isArray(value) ? value.length : 0), 0);
}

export function sourceLabel(source: string | InsightSource) {
  if (typeof source === "string") {
    return source;
  }
  return source.title || source.path || source.kind || "Unknown source";
}

export function dedupeByKey<T>(items: T[], getKey: (item: T) => string) {
  const seen = new Set<string>();

  return items.filter((item) => {
    const key = getKey(item).trim().toLowerCase();
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

export function compactText(value: string, limit = 280) {
  if (value.length <= limit) {
    return value;
  }
  const boundary = value.lastIndexOf(" ", limit);
  return `${value.slice(0, boundary > 180 ? boundary : limit).trim()}...`;
}

export function insightTimestamp(insight: BrainInsight, run: BrainInsightsRun) {
  return (
    timestampValue(insight.updated_at) ??
    timestampValue(insight.created_at) ??
    timestampValue(run.completed_at) ??
    timestampValue(run.started_at) ??
    timestampValue(run.created_at) ??
    0
  );
}

export function numericImpact(insight: BrainInsight) {
  const candidates = [insight.impact_score, insight.confidence];
  for (const candidate of candidates) {
    if (typeof candidate === "number" && Number.isFinite(candidate)) {
      return candidate > 1 ? candidate / 100 : candidate;
    }
  }
  if (insight.priority) {
    const priority = insight.priority.toLowerCase();
    if (["critical", "urgent", "high"].includes(priority)) {
      return 0.9;
    }
    if (priority === "medium") {
      return 0.6;
    }
    if (priority === "low") {
      return 0.25;
    }
  }
  return null;
}

export function derivedImpactScore(insight: BrainInsight, run: BrainInsightsRun) {
  const explicitImpact = numericImpact(insight);
  if (explicitImpact !== null) {
    return explicitImpact;
  }
  const sourceWeight = Math.min((insight.sources?.length ?? 0) * 0.08, 0.24);
  const actionWeight = Math.min((insight.next_actions?.length ?? 0) * 0.12, 0.24);
  const failureWeight = (run.files_failed ?? 0) > 0 ? 0.18 : 0;
  return Math.min(0.95, 0.25 + sourceWeight + actionWeight + failureWeight);
}

export function impactLabel(score: number) {
  if (score >= 0.75) {
    return "High impact";
  }
  if (score >= 0.45) {
    return "Medium impact";
  }
  return "Low impact";
}

export function pluralize(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}
