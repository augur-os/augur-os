"use client";

import { useState } from "react";
import { Code2, Eye, Loader2, Pencil, RotateCcw, Save } from "lucide-react";

import Markdown from "@/components/Markdown";
import { useMcpMutation } from "@/lib/mcp/useMcpMutation";

interface EditableMarkdownProps {
  markdown: string;
  editable?: boolean;
  skillId?: string;
  onSaved?: (content: string) => void;
}

interface UpdateSkillDocResult {
  success?: boolean;
  error?: string;
}

export default function EditableMarkdown({
  markdown,
  editable = false,
  skillId,
  onSaved,
}: EditableMarkdownProps) {
  const canEdit = editable && !!skillId;
  const [mode, setMode] = useState<"preview" | "edit">("preview");
  const [savedMarkdown, setSavedMarkdown] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const current = savedMarkdown ?? markdown;

  const dirty = draft !== current;

  const { mutate: updateSkillDoc, loading, error } = useMcpMutation<
    UpdateSkillDocResult,
    { skill_id: string; content: string }
  >("update-skill-doc", {
    invalidates: ["block-data", "skill-detail"],
  });

  const handleSave = async () => {
    if (!canEdit || !skillId || !dirty) return;
    setLocalError(null);
    let result: UpdateSkillDocResult;
    try {
      result = await updateSkillDoc({ skill_id: skillId, content: draft });
    } catch {
      return;
    }
    if (result?.success === false) {
      setLocalError(result.error || "Failed to save markdown.");
      return;
    }
    setSavedMarkdown(draft);
    setMode("preview");
    onSaved?.(draft);
  };

  const handleRevert = () => {
    setDraft(current);
    setLocalError(null);
  };

  return (
    <div className="space-y-3">
      {canEdit && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-color)]/70 pb-3">
          <div className="inline-flex rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-0.5">
            <button
              type="button"
              aria-label="Switch to markdown preview"
              onClick={() => setMode("preview")}
              className={`inline-flex size-8 items-center justify-center rounded-md transition-colors cursor-pointer ${
                mode === "preview"
                  ? "bg-[var(--text-primary)] text-[var(--bg-primary)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
              }`}
            >
              <Eye className="size-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              aria-label="Switch to source editor"
              onClick={() => {
                setDraft(current);
                setMode("edit");
              }}
              className={`inline-flex size-8 items-center justify-center rounded-md transition-colors cursor-pointer ${
                mode === "edit"
                  ? "bg-[var(--text-primary)] text-[var(--bg-primary)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
              }`}
            >
              <Code2 className="size-4" aria-hidden="true" />
            </button>
          </div>

          {mode === "edit" && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label="Revert markdown"
                disabled={!dirty || loading}
                onClick={handleRevert}
                className="inline-flex size-8 items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
              >
                <RotateCcw className="size-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label="Save markdown"
                disabled={!dirty || loading}
                onClick={() => {
                  void handleSave();
                }}
                className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
              >
                {loading ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <Save className="size-3.5" aria-hidden="true" />
                )}
                Save
              </button>
            </div>
          )}

          {mode === "preview" && (
            <button
              type="button"
              aria-label="Edit markdown"
              onClick={() => {
                setDraft(current);
                setMode("edit");
              }}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] cursor-pointer"
            >
              <Pencil className="size-3.5" aria-hidden="true" />
              Edit
            </button>
          )}
        </div>
      )}

      {mode === "edit" ? (
        <textarea
          aria-label="Markdown source"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          spellCheck={false}
          className="min-h-[360px] w-full resize-y rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-3 font-mono text-sm leading-6 text-[var(--text-primary)] outline-none transition-colors focus:border-[var(--accent-primary)] focus:ring-2 focus:ring-[var(--accent-primary)]/20"
        />
      ) : (
        <Markdown markdown={current} />
      )}

      {(localError || error) && (
        <p className="text-xs text-[var(--accent-danger)]">
          {localError || error}
        </p>
      )}
    </div>
  );
}
