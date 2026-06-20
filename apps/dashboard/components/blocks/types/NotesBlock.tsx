"use client";

import { useState } from "react";
import { StickyNote } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";

interface NotesConfig {
  hub?: string;
  placeholder?: string;
}
interface NotesData {
  content: string;
}

export default function NotesBlock(props: BlockProps<NotesConfig>) {
  const { config, dataSource } = props;
  const { hub, placeholder = "Write notes..." } = config;
  const selfFetched = useBlockData<NotesData>(
    dataSource,
    config,
    "notes",
  );
  const data = (props.data as NotesData | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;
  const [draftText, setDraftText] = useState<string | null>(null);
  const text = draftText ?? data?.content ?? "";

  return (
    <BlockShell
      title={hub ? `${hub} Notes` : "Notes"}
      icon={StickyNote}
      color="violet"
      staleError={error}
    >
      {loading ? (
        <div className="flex-1 p-4">
          <div className="h-full rounded bg-[var(--bg-hover)] animate-pulse" />
        </div>
      ) : !data && !text ? (
        <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
          No notes available
        </p>
      ) : (
        <textarea
          className="flex-1 w-full p-4 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] resize-none focus:outline-none"
          placeholder={placeholder}
          aria-label={hub ? `${hub} notes` : "Notes"}
          value={text}
          onChange={(e) => setDraftText(e.target.value)}
        />
      )}
    </BlockShell>
  );
}
