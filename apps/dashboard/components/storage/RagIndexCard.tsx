"use client";

import { Search } from "lucide-react";
import { SettingsCard } from "@/components/ui/SettingsCard";
import { CleanupButton } from "./CleanupButton";
import type { CleanupResult, RagIndex } from "./types";

interface RagIndexCardProps {
  ragIndex: RagIndex;
  onCleanup?: (
    category: string,
    dryRun: boolean,
  ) => Promise<CleanupResult | null>;
  cleanupLoading?: string | null;
}

export function RagIndexCard({
  ragIndex,
  onCleanup,
  cleanupLoading,
}: RagIndexCardProps) {
  if (!ragIndex.exists) {
    return (
      <SettingsCard
        icon={Search}
        title="RAG Index"
        subtitle="No indexes created yet"
        variant="muted"
        value="0 MB"
        valueLabel="0 plugins"
      />
    );
  }

  const pluginLabel = ragIndex.project_count === 1 ? "Plugin" : "Plugins";

  return (
    <SettingsCard
      icon={Search}
      title="RAG Index"
      subtitle={`${ragIndex.project_count} ${pluginLabel.toLowerCase()} with RAG data`}
      variant="info"
      badge={`${ragIndex.project_count} ${pluginLabel}`}
      value={`${ragIndex.size_mb} MB`}
      valueLabel="Total Size"
      action={
        onCleanup ? (
          <CleanupButton
            category="rag_index"
            onCleanup={onCleanup}
            loading={cleanupLoading === "rag_index"}
          />
        ) : undefined
      }
    >
      {ragIndex.plugins && ragIndex.plugins.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {ragIndex.plugins.slice(0, 4).map((plugin) => (
            <span
              key={plugin.skill}
              className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--bg-hover)] text-[var(--text-muted)] font-mono"
            >
              {plugin.skill} ({plugin.size_mb} MB)
            </span>
          ))}
          {ragIndex.plugins.length > 4 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--bg-hover)] text-[var(--text-muted)]">
              +{ragIndex.plugins.length - 4} more
            </span>
          )}
        </div>
      )}
    </SettingsCard>
  );
}
