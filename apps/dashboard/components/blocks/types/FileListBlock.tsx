"use client";

import { Folder, File, FileText, Image as ImageIcon, Sheet } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";
import { formatTimeAgo } from "@/lib/timestamps";
import { formatFileSize } from "@/lib/utils/format";

interface FileListConfig {
  title?: string;
  limit?: number;
}

interface FileItem {
  name: string;
  type?: string;
  size?: number;
  modified?: string;
  path?: string;
}

function getFileIcon(type?: string) {
  if (!type) return <File className="size-3.5 text-[var(--text-muted)]" />;
  const ext = type.toLowerCase();
  if (ext === "pdf") return <FileText className="size-3.5 text-red-400" />;
  if (["jpg", "jpeg", "png", "gif", "webp", "svg"].includes(ext))
    return <ImageIcon className="size-3.5 text-blue-400" />;
  if (["xls", "xlsx", "csv", "ods"].includes(ext))
    return <Sheet className="size-3.5 text-emerald-400" />;
  if (["md", "txt"].includes(ext))
    return <FileText className="size-3.5 text-purple-400" />;
  return <File className="size-3.5 text-[var(--text-muted)]" />;
}

export default function FileListBlock(props: BlockProps<FileListConfig>) {
  const { config, dataSource, onExpand } = props;
  const { title = "Files", limit = 8 } = config;
  const selfFetched = useBlockData<FileItem[]>(dataSource, config, "file-list");
  const data = (props.data as FileItem[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  const files = Array.isArray(data) ? data : [];
  const visibleFiles = files.slice(0, limit);
  const overflow = files.length > limit ? files.length - limit : 0;

  return (
    <BlockShell title={title} icon={Folder} color="blue" onExpand={onExpand} staleError={error}>
      <div className="p-3">
        {loading &&
          Array.from({ length: 3 }, (_, i) => (
            <div
              key={i}
              className="h-10 mb-1.5 rounded-lg bg-[var(--bg-hover)] animate-pulse"
            />
          ))}

        {!loading && files.length === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
            No files
          </p>
        )}


        {!loading && visibleFiles.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {visibleFiles.map((file, i) => (
              <div
                key={file.name ?? i}
                className="rounded-lg bg-[var(--bg-hover)]/30 px-3 py-2 flex items-center gap-3"
              >
                <div className="flex-shrink-0">
                  {getFileIcon(file.type)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-[var(--text-primary)] truncate">
                    {file.name}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    {file.size != null && (
                      <span className="text-[10px] text-[var(--text-muted)]">
                        {formatFileSize(file.size)}
                      </span>
                    )}
                    {file.size != null && file.modified && (
                      <span className="text-[10px] text-[var(--text-muted)]">&middot;</span>
                    )}
                    {file.modified && (
                      <span className="text-[10px] text-[var(--text-muted)]">
                        {formatTimeAgo(file.modified)}
                      </span>
                    )}
                    {file.type && (
                      <>
                        <span className="text-[10px] text-[var(--text-muted)]">&middot;</span>
                        <span className="text-[10px] text-[var(--text-muted)] uppercase">
                          {file.type}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && overflow > 0 && (
          <p className="mt-2 text-[10px] text-[var(--text-muted)] text-right">
            +{overflow} more
          </p>
        )}
      </div>
    </BlockShell>
  );
}
