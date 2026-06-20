import type { Diagnostic, ManagerResponse, ManagerSnapshot } from "./harness.types";

export function pluralize(count: number, singular: string, plural: string) {
  return count === 1 ? singular : plural;
}

export function summarizeDiagnostics(diagnostics: Diagnostic[]) {
  const errors = diagnostics.filter((diagnostic) => diagnostic.severity === "error").length;
  const warnings = diagnostics.filter((diagnostic) => diagnostic.severity === "warning").length;
  if (errors > 0) {
    return `${errors} ${pluralize(errors, "error", "errors")} block user-facing capability wiring`;
  }
  if (warnings > 0) {
    return `${warnings} ${pluralize(warnings, "warning", "warnings")} needs review`;
  }
  return "No blockers detected";
}

export function capabilityLabelFromId(id: string) {
  const raw = id.includes(":") ? id.split(":").slice(1).join(":") : id;
  return raw.replace(/^brain-/, "");
}

export function normalizeManagerSnapshot(data: ManagerResponse | null | undefined): ManagerSnapshot | null {
  if (!data) return null;
  if (data.snapshot) return data.snapshot;
  if (data.groups && data.tier_details && data.tiers && data.generated_at) {
    return data as ManagerSnapshot;
  }
  return null;
}
