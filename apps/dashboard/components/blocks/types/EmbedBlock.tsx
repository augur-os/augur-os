"use client";

import { Globe } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";

interface EmbedConfig {
  title?: string;
  url?: string;
}
interface EmbedData {
  url: string;
  title?: string;
}

export default function EmbedBlock(props: BlockProps<EmbedConfig>) {
  const { config, dataSource, mode, onExpand } = props;
  const { title = "Embed" } = config;
  const selfFetched = useBlockData<EmbedData>(
    dataSource,
    config,
    "embed",
  );
  const data = (props.data as EmbedData | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;
  const url = data?.url ?? config.url;

  return (
    <BlockShell
      title={title}
      icon={Globe}
      color="pink"
      onExpand={onExpand}
      staleError={error}
    >
      {loading ? (
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="h-24 w-full rounded bg-[var(--bg-hover)] animate-pulse" />
        </div>
      ) : !url && error ? (
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        </div>
      ) : url ? (
        <iframe
          src={url}
          className="w-full flex-1 border-0"
          sandbox="allow-forms allow-popups allow-scripts"
          title={title}
        />
      ) : (
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-xs text-[var(--text-muted)] italic">
            No URL configured
          </p>
        </div>
      )}
    </BlockShell>
  );
}
