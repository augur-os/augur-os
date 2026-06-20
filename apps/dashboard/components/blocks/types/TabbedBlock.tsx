"use client";

import { Layers } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { keyedRenderItems } from "@/lib/stable-render-key";
import { BlockShell } from "../BlockShell";
import { TabbedSectionRenderer } from "@/components/plugin/sections/TabbedSectionRenderer";
import type { TabbedSectionTab } from "@/components/plugin/sections/types";

interface TabbedConfig {
  title?: string;
  /** Tab definitions — maps to ADR-274 D13 TabbedSectionTab[] */
  tabs?: TabbedSectionTab[];
}

export default function TabbedBlock(props: BlockProps<TabbedConfig>) {
  const { config, onExpand, instanceId } = props;
  const { title = "Tabs", tabs } = config;

  if (!tabs || tabs.length === 0) {
    return (
      <BlockShell title={title} icon={Layers} color="cyan" onExpand={onExpand}>
        <div className="p-4 text-center">
          <p className="text-xs text-[var(--text-muted)] italic">
            No tabs configured
          </p>
        </div>
      </BlockShell>
    );
  }

  return (
    <BlockShell title={title} icon={Layers} color="cyan" onExpand={onExpand}>
      <div className="p-4">
        <TabbedSectionRenderer
          sectionId={`block-${instanceId}`}
          tabs={tabs}
          renderContent={(data, tabId) => {
            if (data.length === 0) {
              return (
                <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
                  No data for this tab
                </p>
              );
            }
            return (
              <div className="space-y-2">
                {keyedRenderItems(data).map(({ item, key: itemKey }) => {
                  const record =
                    typeof item === "object" && item !== null
                      ? (item as Record<string, unknown>)
                      : { value: item };
                  const keys = Object.keys(record).filter((k) => k !== "id").slice(0, 4);
                  return (
                    <div
                      key={itemKey}
                      className="rounded-lg border border-[var(--border-color)]/20 p-3 text-xs"
                    >
                      {keys.map((key) => (
                        <div key={key} className="flex justify-between py-0.5">
                          <span className="text-[var(--text-muted)] capitalize">{key}</span>
                          <span className="text-[var(--text-primary)]">
                            {String(record[key] ?? "")}
                          </span>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            );
          }}
        />
      </div>
    </BlockShell>
  );
}
