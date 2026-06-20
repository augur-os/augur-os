import type { DispatchMode } from "@/lib/actions/types";

export type ResolvedDispatchMode = Exclude<DispatchMode, "api" | "auto">;

export function normalizeDispatchMode(mode: DispatchMode): DispatchMode {
  return mode === "api" ? "oneshot" : mode;
}

export function resolveAutoDispatchMode(options: {
  hasIde: boolean;
}): "ide" | "oneshot" {
  return options.hasIde ? "ide" : "oneshot";
}
