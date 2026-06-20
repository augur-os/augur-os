"use client";

import { useReducer, useEffect, useCallback, useMemo } from "react";
import { mcpCall } from "@/lib/mcp/client";
import { RefreshCw, Loader2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";

// ── Types ───────────────────────────────────────────────────────────────

type CliCategory = "remote" | "local" | "ide";

interface CliConfig {
  cli_id: string;
  label: string;
  category: CliCategory;
  group: string;
  available: boolean;
  enabled: boolean;
}

interface DispatchPrefs {
  enabled_groups: string[] | null;
  variant_overrides: Record<string, boolean>;
}

interface GroupData {
  name: string;
  category: CliCategory;
  variants: CliConfig[];
  enabled: boolean;
}

interface DispatchTargetsState {
  configs: CliConfig[];
  prefs: DispatchPrefs;
  loading: boolean;
  saving: boolean;
  error: string | null;
}

type DispatchTargetsAction =
  | { type: "load-start" }
  | { type: "load-success"; configs: CliConfig[]; prefs: DispatchPrefs }
  | { type: "load-error"; error: string }
  | { type: "save-start" }
  | { type: "save-success"; prefs: DispatchPrefs }
  | { type: "save-failed" };

const DEFAULT_PREFS: DispatchPrefs = {
  enabled_groups: null,
  variant_overrides: {},
};

const INITIAL_STATE: DispatchTargetsState = {
  configs: [],
  prefs: DEFAULT_PREFS,
  loading: true,
  saving: false,
  error: null,
};

function dispatchTargetsReducer(
  state: DispatchTargetsState,
  action: DispatchTargetsAction,
): DispatchTargetsState {
  switch (action.type) {
    case "load-start":
      return { ...state, loading: true, error: null };
    case "load-success":
      return {
        ...state,
        configs: action.configs,
        prefs: action.prefs,
        loading: false,
        error: null,
      };
    case "load-error":
      return { ...state, loading: false, error: action.error };
    case "save-start":
      return { ...state, saving: true };
    case "save-success":
      return { ...state, prefs: action.prefs, saving: false };
    case "save-failed":
      return { ...state, saving: false };
    default:
      return state;
  }
}

// ── Category badge styling ───────────────────────────────────────────────

const CATEGORY_BADGE: Record<CliCategory, { bg: string; text: string; border: string; label: string }> = {
  remote: {
    bg: "bg-purple-500/20",
    text: "text-purple-300",
    border: "border-purple-500/30",
    label: "REMOTE",
  },
  local: {
    bg: "bg-emerald-500/20",
    text: "text-emerald-300",
    border: "border-emerald-500/30",
    label: "LOCAL",
  },
  ide: {
    bg: "bg-[var(--bg-hover)]",
    text: "text-[var(--text-muted)]",
    border: "border-[var(--border-color)]",
    label: "IDE",
  },
};

// ── Component ───────────────────────────────────────────────────────────
export default function DispatchTargetsTab() {
  const [{ configs, prefs, loading, saving, error }, dispatch] = useReducer(
    dispatchTargetsReducer,
    INITIAL_STATE,
  );

  // Fetch both configs and current preferences
  const fetchData = useCallback(async () => {
    dispatch({ type: "load-start" });
    try {
      const res = await fetch("/api/cli/configs");
      if (!res.ok) throw new Error("Failed to load dispatch targets");
      const data = await res.json();
      const configs = data.configs || [];

      // Extract current prefs from the enabled state
      // We also fetch prefs directly to get the raw shape
      let prefs = DEFAULT_PREFS;
      try {
        const prefData = await mcpCall<Record<string, unknown>>("get-preferences", { key: "dispatch_targets" });
        const dt = (prefData as any)?.dispatch_targets ?? prefData;
        prefs = {
          enabled_groups: dt?.enabled_groups ?? null,
          variant_overrides: dt?.variant_overrides ?? {},
        };
      } catch {
        // No prefs saved yet — defaults (all enabled)
        prefs = DEFAULT_PREFS;
      }
      dispatch({ type: "load-success", configs, prefs });
    } catch (err) {
      dispatch({
        type: "load-error",
        error: err instanceof Error ? err.message : "Unknown error",
      });
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchData]);

  // Build grouped data
  const groups: GroupData[] = useMemo(() => {
    const groupMap = new Map<string, CliConfig[]>();
    for (const c of configs) {
      const existing = groupMap.get(c.group) || [];
      existing.push(c);
      groupMap.set(c.group, existing);
    }

    return Array.from(groupMap.entries()).map(([name, variants]) => {
      const category = variants[0]?.category ?? "remote";
      const enabled = prefs.enabled_groups === null || prefs.enabled_groups.includes(name);
      return { name, category, variants, enabled };
    });
  }, [configs, prefs]);

  const allGroupNames = useMemo(() => groups.map((g) => g.name), [groups]);

  // Persist prefs
  const savePrefs = useCallback(async (next: DispatchPrefs) => {
    dispatch({ type: "save-start" });
    try {
      await mcpCall("update-preference", {
        key: "dispatch_targets",
        value: next,
      });
      dispatch({ type: "save-success", prefs: next });
      toast.success("Dispatch targets updated");
    } catch (err) {
      dispatch({ type: "save-failed" });
      toast.error(err instanceof Error ? err.message : "Failed to save");
    }
  }, []);

  // Toggle entire group
  const toggleGroup = useCallback(
    (group: string, enabled: boolean) => {
      let nextGroups: string[];

      if (prefs.enabled_groups === null) {
        // First toggle — initialize from all groups, then apply change
        nextGroups = enabled
          ? allGroupNames
          : allGroupNames.filter((g) => g !== group);
      } else if (enabled) {
        nextGroups = [...new Set([...prefs.enabled_groups, group])];
      } else {
        nextGroups = prefs.enabled_groups.filter((g) => g !== group);
      }

      savePrefs({ ...prefs, enabled_groups: nextGroups });
    },
    [prefs, allGroupNames, savePrefs],
  );

  // Toggle individual variant
  const toggleVariant = useCallback(
    (cliId: string, enabled: boolean) => {
      const overrides = { ...prefs.variant_overrides };
      if (enabled) {
        delete overrides[cliId]; // Remove override to re-enable
      } else {
        overrides[cliId] = false;
      }
      savePrefs({ ...prefs, variant_overrides: overrides });
    },
    [prefs, savePrefs],
  );

  // ── Render ──────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[...Array(6)].map((_, i) => (
          <div
            key={i}
            className="h-[88px] rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-xl border border-red-500/30 bg-red-500/10">
        <AlertCircle className="size-5 text-red-400 shrink-0" />
        <div className="flex-1 text-sm text-red-300">{error}</div>
        <Button variant="ghost" size="sm" onClick={fetchData}>
          Retry
        </Button>
      </div>
    );
  }

  if (groups.length === 0) {
    return (
      <div className="p-8 text-center rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)]">
        <p className="text-sm text-[var(--text-muted)]">No dispatch targets configured.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-[var(--text-muted)]">
          {groups.length} group{groups.length !== 1 ? "s" : ""} &middot;{" "}
          {configs.length} target{configs.length !== 1 ? "s" : ""}
        </p>
        <Button
          variant="ghost"
          size="icon"
          onClick={fetchData}
          disabled={loading}
          aria-label="Refresh dispatch targets"
          className="size-8 rounded-lg hover:bg-[var(--accent-primary)]/10 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 text-[var(--accent-primary)] ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {groups.map((group) => (
          <GroupCard
            key={group.name}
            group={group}
            prefs={prefs}
            saving={saving}
            onToggleGroup={toggleGroup}
            onToggleVariant={toggleVariant}
          />
        ))}
      </div>
    </div>
  );
}

// ── GroupCard ────────────────────────────────────────────────────────────

function GroupCard({
  group,
  prefs,
  saving,
  onToggleGroup,
  onToggleVariant,
}: {
  group: GroupData;
  prefs: DispatchPrefs;
  saving: boolean;
  onToggleGroup: (group: string, enabled: boolean) => void;
  onToggleVariant: (cliId: string, enabled: boolean) => void;
}) {
  const badge = CATEGORY_BADGE[group.category];
  const hasMultipleVariants = group.variants.length > 1;

  return (
    <div
      className={`
        rounded-xl border p-4 transition-colors duration-200
        ${group.enabled
          ? "border-[var(--border-color)] bg-[var(--bg-card)]"
          : "border-[var(--border-color)]/50 bg-[var(--bg-card)]/50 opacity-60"
        }
      `}
    >
      {/* Header: group name + category badge + toggle */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-semibold text-[var(--text-primary)] truncate capitalize">
            {group.name}
          </span>
          <span
            className={`
              shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold
              border ${badge.bg} ${badge.text} ${badge.border}
            `}
          >
            {badge.label}
          </span>
        </div>

        {/* Group toggle switch */}
        <button type="button"
          onClick={() => onToggleGroup(group.name, !group.enabled)}
          disabled={saving}
          className={`
            relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 cursor-pointer shrink-0
            ${group.enabled ? "bg-[var(--accent-primary)]" : "bg-[var(--border-color)]"}
            ${saving ? "opacity-50 cursor-not-allowed" : ""}
          `}
          role="switch"
          aria-checked={group.enabled}
          aria-label={`${group.enabled ? "Disable" : "Enable"} ${group.name} group`}
        >
          <span
            className={`
              inline-block size-3.5 rounded-full bg-white shadow-sm transition-transform duration-200
              ${group.enabled ? "translate-x-[18px]" : "translate-x-[3px]"}
            `}
          />
        </button>
      </div>

      {/* Variant list */}
      {group.enabled && hasMultipleVariants && (
        <div className="space-y-1.5 pt-2 border-t border-[var(--border-color)]/50">
          {group.variants.map((variant) => {
            const variantEnabled = prefs.variant_overrides[variant.cli_id] !== false;
            return (
              <label
                key={variant.cli_id}
                className="flex items-center gap-2 py-1 cursor-pointer group"
              >
                <input
                  type="checkbox"
                  checked={variantEnabled}
                  onChange={() => onToggleVariant(variant.cli_id, !variantEnabled)}
                  disabled={saving || !variant.available}
                  className="size-3.5 rounded border-[var(--border-color)] text-[var(--accent-primary)] bg-transparent cursor-pointer disabled:opacity-40"
                />
                <span
                  className={`text-xs ${
                    variant.available
                      ? "text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]"
                      : "text-[var(--text-muted)] line-through"
                  } transition-colors`}
                >
                  {variant.label}
                </span>
                {!variant.available && (
                  <span className="text-[10px] text-[var(--text-muted)] italic">Not installed</span>
                )}
              </label>
            );
          })}
        </div>
      )}

      {/* Single variant — just show availability status */}
      {group.enabled && !hasMultipleVariants && group.variants[0] && (
        <div className="text-xs text-[var(--text-muted)]">
          {group.variants[0].available ? (
            <span className="text-emerald-400">Available</span>
          ) : (
            <span className="text-[var(--text-muted)] italic">Not installed</span>
          )}
        </div>
      )}

      {/* Saving indicator */}
      {saving && (
        <div className="flex items-center gap-1.5 mt-2 text-xs text-[var(--text-muted)]">
          <Loader2 className="size-3 animate-spin" />
          Saving…
        </div>
      )}
    </div>
  );
}
