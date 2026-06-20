"use client";

import { FileText } from "lucide-react";
import EditableMarkdown from "@/components/EditableMarkdown";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";

interface MarkdownConfig {
  title?: string;
  file?: string;
  content?: string;
  skillId?: string;
}
interface MarkdownData {
  content: string;
  editable?: boolean;
  generated?: boolean;
  path?: string;
  source_path?: string;
}

export default function MarkdownBlock(props: BlockProps<MarkdownConfig>) {
  const { config, dataSource, onExpand } = props;
  const { title, file, content: staticContent } = config;
  const displayTitle =
    title || (file ? file.split("/").pop() : "Content") || "Content";
  const selfFetched = useBlockData<MarkdownData>(
    dataSource,
    config,
    "markdown",
  );
  const data = (props.data as MarkdownData | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;
  const content = data?.content || staticContent || "";
  const skillId = typeof config.skillId === "string" ? config.skillId : "";
  const canEdit =
    dataSource?.mcpTool === "get-skill-doc" &&
    !!skillId &&
    data?.editable !== false;

  return (
    <BlockShell
      title={displayTitle}
      icon={FileText}
      color="violet"
      onExpand={onExpand}
      staleError={error}
    >
      <div className="p-4 text-sm text-[var(--text-secondary)] leading-relaxed overflow-auto">
        {loading && (
          <div className="space-y-2">
            {[85, 70, 90].map((w, i) => (
              <div
                key={i}
                className="h-3 rounded bg-[var(--bg-hover)] animate-pulse"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        )}

        {!loading && !content && !error && (
          <p className="text-xs text-[var(--text-muted)] italic">No content</p>
        )}
        {!loading && !content && error && (
          <div className="text-center py-6">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        )}
        {!loading && content && (
          <EditableMarkdown
            markdown={content}
            editable={canEdit}
            skillId={skillId}
            onSaved={selfFetched.invalidate}
          />
        )}
      </div>
    </BlockShell>
  );
}
