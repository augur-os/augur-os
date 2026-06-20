"use client";

import { useState } from "react";
import { Eye, File, FileText, ChevronDown, ChevronRight } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { keyedRenderItems } from "@/lib/stable-render-key";
import { BlockShell } from "../BlockShell";

interface DataPreviewConfig {
  title?: string;
  limit?: number;
}

interface DataFile {
  name: string;
  type: "yaml" | "json" | "md";
  count?: number;
  preview?: Array<Record<string, unknown>>;
  content?: string;
}

const TYPE_STYLES: Record<string, { border: string; badge: string }> = {
  yaml: { border: "border-l-blue-400", badge: "bg-blue-500/20 text-blue-400" },
  json: { border: "border-l-emerald-400", badge: "bg-emerald-500/20 text-emerald-400" },
  md: { border: "border-l-purple-400", badge: "bg-purple-500/20 text-purple-400" },
};

function FileTypeIcon({ type }: { type: string }) {
  if (type === "json") return <File className="size-3.5 text-emerald-400" />;
  if (type === "md") return <FileText className="size-3.5 text-purple-400" />;
  return <File className="size-3.5 text-blue-400" />;
}

function PreviewEntry({ entry }: { entry: Record<string, unknown> }) {
  const keys = Object.keys(entry).slice(0, 3);
  return (
    <div className="rounded bg-[var(--bg-secondary)]/50 px-2.5 py-1.5 text-[10px]">
      {keys.map((k) => (
        <div key={k} className="flex gap-1.5 truncate">
          <span className="shrink-0 font-medium text-[var(--text-muted)]">{k}:</span>
          <span className="truncate text-[var(--text-primary)]">{String(entry[k])}</span>
        </div>
      ))}
    </div>
  );
}

function DataFileCard({ file }: { file: DataFile }) {
  const [expanded, setExpanded] = useState(false);
  const styles = TYPE_STYLES[file.type] ?? TYPE_STYLES.yaml;
  const preview = file.preview ?? [];
  const visibleEntries = expanded ? preview.slice(0, 6) : preview.slice(0, 2);
  const extraCount = preview.length - visibleEntries.length;

  return (
    <div className={`rounded-lg bg-[var(--bg-hover)]/30 p-3 border-l-4 ${styles.border}`}>
      <button type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left"
      >
        {expanded ? (
          <ChevronDown className="size-3 text-[var(--text-muted)] flex-shrink-0" />
        ) : (
          <ChevronRight className="size-3 text-[var(--text-muted)] flex-shrink-0" />
        )}
        <FileTypeIcon type={file.type} />
        <span className="flex-1 truncate text-xs font-medium text-[var(--text-primary)]">
          {file.name}
        </span>
        {file.count != null && (
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${styles.badge}`}
          >
            {file.count}
          </span>
        )}
      </button>

      {/* Content preview: structured entries or raw text */}
      {visibleEntries.length > 0 && (
        <div className="mt-2 space-y-1">
          {keyedRenderItems(visibleEntries).map(({ item: entry, key }) => (
            <PreviewEntry key={key} entry={entry} />
          ))}
        </div>
      )}

      {!preview.length && file.content && (
        <div className="mt-2">
          <pre className="text-[10px] text-[var(--text-secondary)] bg-[var(--bg-secondary)]/50 rounded px-2.5 py-1.5 overflow-x-auto max-h-32 whitespace-pre-wrap">
            {expanded ? file.content : file.content.slice(0, 200)}
            {!expanded && file.content.length > 200 && "\u2026"}
          </pre>
        </div>
      )}

      {extraCount > 0 && (
        <p className="mt-1 text-[10px] text-[var(--text-muted)]">+{extraCount} more</p>
      )}
    </div>
  );
}

export default function DataPreviewBlock(props: BlockProps<DataPreviewConfig>) {
  const { config, dataSource, onExpand } = props;
  const { title = "Data Preview", limit = 4 } = config;
  const selfFetched = useBlockData<DataFile[]>(dataSource, config, "data-preview");
  const data = (props.data as DataFile[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  const files = Array.isArray(data) ? data : [];
  const visibleFiles = files.slice(0, limit);
  const overflow = files.length > limit ? files.length - limit : 0;

  return (
    <BlockShell title={title} icon={Eye} color="violet" onExpand={onExpand} staleError={error}>
      <div className="p-3">
        {loading &&
          ["file-preview-skeleton-primary", "file-preview-skeleton-secondary"].map((key) => (
            <div
              key={key}
              className="h-20 mb-2 rounded-lg bg-[var(--bg-hover)] animate-pulse"
            />
          ))}

        {!loading && files.length === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
            No data files
          </p>
        )}


        {!loading && visibleFiles.length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            {visibleFiles.map((file) => (
              <DataFileCard key={file.name} file={file} />
            ))}
          </div>
        )}

        {!loading && overflow > 0 && (
          <p className="mt-2 text-[10px] text-[var(--text-muted)] text-right">
            +{overflow} more files
          </p>
        )}
      </div>
    </BlockShell>
  );
}
