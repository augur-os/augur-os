"use client";

import { useState } from "react";
import {
  Database,
  RefreshCw,
  FolderCode,
  Layers,
  Server,
  PenTool,
  FolderOpen,
  Loader2,
  Settings2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SettingsCard } from "@/components/ui/SettingsCard";
import { usePathConfig } from "@/components/StorageSection";
import { RagIndexCard } from "@/components/storage/RagIndexCard";
import type { PathConfig, PathCategory } from "@/components/storage/types";
import { EditorPreferences } from "@/components/EditorPreferences";
import { useMcpMutation } from "@/lib/mcp/useMcpMutation";
type FilterCategory = "storage" | "editors";
type StorageGroup = "code" | "knowledge" | "runtime";

const FILTER_CONFIG: Record<
  FilterCategory,
  {
    label: string;
    icon: typeof Database;
    activeBg: string;
    activeText: string;
    activeBorder: string;
  }
> = {
  storage: {
    label: "Storage",
    icon: Database,
    activeBg: "bg-[var(--accent-primary)]/15",
    activeText: "text-[var(--accent-primary)]",
    activeBorder: "border-[var(--accent-primary)]/30",
  },
  editors: {
    label: "Editors",
    icon: PenTool,
    activeBg: "bg-[var(--accent-primary)]/15",
    activeText: "text-[var(--accent-primary)]",
    activeBorder: "border-[var(--accent-primary)]/30",
  },
};

// Maps the canonical path-config category ids (core/data/plugins/runtime
// returned by `get-path-config`) to friendly labels, icons, and grouping.
const STORAGE_META: Record<
  string,
  { label: string; group: StorageGroup; icon: typeof Database }
> = {
  core: { label: "Code", group: "code", icon: FolderCode },
  data: { label: "Vault", group: "knowledge", icon: Database },
  plugins: { label: "Skills", group: "code", icon: Layers },
  runtime: { label: "Runtime", group: "runtime", icon: Server },
};

function buildStorageCards(
  activeFilters: Set<FilterCategory>,
  pathConfig: PathConfig | null,
  onOpenPath: (path: string) => Promise<void>,
  openingPath: string | null,
) {
  if (!activeFilters.has("storage") || !pathConfig) return [];

  const categories: PathCategory[] = [
    pathConfig.core,
    pathConfig.data,
    pathConfig.plugins,
    pathConfig.runtime,
  ].filter(Boolean);

  const categoryCards = categories.map((cat) => {
    const meta = STORAGE_META[cat.id] ?? {
      label: cat.id.charAt(0).toUpperCase() + cat.id.slice(1),
      group: "code" as StorageGroup,
      icon: Database,
    };
    const Icon = meta.icon;
    const value = `${Math.round(cat.size_mb)} MB`;
    return (
      <SettingsCard
        key={`storage-${cat.id}`}
        icon={Icon}
        title={meta.label}
        subtitle={cat.path}
        isPath
        variant={meta.group === "runtime" ? "info" : "default"}
        badge={cat.gitignored ? "Managed" : undefined}
        secondaryBadge={
          meta.group === "knowledge"
            ? "Knowledge"
            : meta.group === "runtime"
              ? "Runtime"
              : undefined
        }
        value={value}
        valueLabel="Size"
        action={
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={(event) => {
              event.stopPropagation();
              void onOpenPath(cat.path);
            }}
            disabled={openingPath === cat.path}
            title={`Open ${meta.label} folder`}
            aria-label={`Open ${meta.label} folder`}
          >
            {openingPath === cat.path ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <FolderOpen className="size-3.5" />
            )}
          </Button>
        }
      />
    );
  });

  if (!pathConfig.rag_index) return categoryCards;

  return [
    ...categoryCards,
    <RagIndexCard key="storage-rag-index" ragIndex={pathConfig.rag_index} />,
  ];
}

function getTotalStorage(pathConfig: PathConfig | null) {
  if (!pathConfig) return null;
  const categories: PathCategory[] = [
    pathConfig.core,
    pathConfig.data,
    pathConfig.plugins,
    pathConfig.runtime,
  ].filter(Boolean);
  const base = categories.reduce(
    (total, cat) => total + (typeof cat.size_mb === "number" ? cat.size_mb : 0),
    0,
  );
  const rag =
    typeof pathConfig.rag_index?.size_mb === "number"
      ? pathConfig.rag_index.size_mb
      : 0;
  return Math.round(base + rag);
}

function FilterChip({
  category,
  active,
  onClick,
}: {
  category: FilterCategory;
  active: boolean;
  onClick: () => void;
}) {
  const config = FILTER_CONFIG[category];
  const Icon = config.icon;

  return (
    <button type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={`${active ? "Hide" : "Show"} ${config.label} section`}
      className={`
        flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium
        cursor-pointer transition-all duration-200 border
        ${
          active
            ? `${config.activeBg} ${config.activeText} ${config.activeBorder}`
            : "bg-[var(--bg-card)] text-[var(--text-muted)] border-[var(--border-color)] hover:border-[var(--border-hover)]"
        }
      `}
    >
      <Icon className="size-3.5" />
      {config.label}
    </button>
  );
}

export default function GeneralTab() {
  const [activeFilters, setActiveFilters] = useState<Set<FilterCategory>>(
    new Set(["storage", "editors"]),
  );
  const [openingStoragePath, setOpeningStoragePath] = useState<string | null>(
    null,
  );

  const { config: pathConfig, loading, refresh } = usePathConfig();

  const { mutate: openPath } = useMcpMutation<Record<string, unknown>, { path: string }>(
    "system-open",
  );

  const openStoragePath = async (path: string) => {
    try {
      setOpeningStoragePath(path);
      await openPath({ path });
    } finally {
      setOpeningStoragePath(null);
    }
  };

  const toggleFilter = (category: FilterCategory) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  const selectAll = () => {
    setActiveFilters(new Set(["storage", "editors"]));
  };

  const clearAll = () => {
    setActiveFilters(new Set());
  };

  const cards = buildStorageCards(
    activeFilters,
    pathConfig,
    openStoragePath,
    openingStoragePath,
  );
  const totalStorage = getTotalStorage(pathConfig);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {(Object.keys(FILTER_CONFIG) as FilterCategory[]).map((category) => (
            <FilterChip
              key={category}
              category={category}
              active={activeFilters.has(category)}
              onClick={() => toggleFilter(category)}
            />
          ))}

          <div className="h-4 w-px bg-[var(--border-color)] mx-2" />

          <button type="button"
            onClick={selectAll}
            aria-label="Select all filters"
            className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer transition-colors duration-200 px-1.5 py-1"
          >
            All
          </button>
          <button type="button"
            onClick={clearAll}
            aria-label="Clear all filters"
            className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer transition-colors duration-200 px-1.5 py-1"
          >
            None
          </button>
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={refresh}
          disabled={loading}
          aria-label="Refresh storage paths"
          className="size-8 rounded-lg hover:bg-[var(--accent-primary)]/10 transition-colors"
        >
          <RefreshCw
            className={`w-4 h-4 text-[var(--accent-primary)] ${loading ? "animate-spin" : ""}`}
          />
        </Button>
      </div>

      {activeFilters.size === 0 ? (
        <div className="p-8 text-center rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)]">
          <Settings2 className="size-6 text-[var(--text-muted)] mx-auto mb-2" />
          <p className="text-sm text-[var(--text-muted)]">
            Select a filter to view items
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {activeFilters.has("storage") && (
            <div className="space-y-3">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                  Data locations
                </h3>
                <p className="text-xs text-[var(--text-muted)]">
                  Read-only: where Augur keeps code, knowledge, and runtime
                  state on disk.
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
                <span>{cards.length} {cards.length === 1 ? "folder" : "folders"}</span>
                {totalStorage !== null && (
                  <span className="font-semibold text-[var(--text-primary)]">
                    Total Storage: {totalStorage} MB
                  </span>
                )}
              </div>

              {loading && cards.length === 0 ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {[...Array(6)].map((_, i) => (
                    <div
                      key={i}
                      className="h-28 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] animate-pulse"
                    />
                  ))}
                </div>
              ) : cards.length === 0 ? (
                <div className="p-8 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)]">
                  <p className="text-sm text-[var(--text-muted)] text-center">
                    No storage paths available.
                  </p>
                </div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {cards}
                </div>
              )}
            </div>
          )}

          {activeFilters.has("editors") && <EditorPreferences />}
        </div>
      )}

      <div className="h-8" />
    </div>
  );
}
