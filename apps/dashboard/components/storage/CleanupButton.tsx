"use client";

import { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import type { CleanupResult } from "./types";

interface CleanupButtonProps {
  category: string;
  onCleanup: (
    category: string,
    dryRun: boolean,
  ) => Promise<CleanupResult | null>;
  loading: boolean;
  disabled?: boolean;
}

export function CleanupButton({
  category,
  onCleanup,
  loading,
  disabled,
}: CleanupButtonProps) {
  const [showConfirm, setShowConfirm] = useState(false);
  const [previewResult, setPreviewResult] = useState<CleanupResult | null>(
    null,
  );

  const handlePreview = async () => {
    const result = await onCleanup(category, true);
    if (result) {
      setPreviewResult(result);
      setShowConfirm(true);
    }
  };

  const handleConfirm = async () => {
    await onCleanup(category, false);
    setShowConfirm(false);
    setPreviewResult(null);
  };

  if (showConfirm && previewResult) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-amber-400">
          {previewResult.cleaned.length} items ({previewResult.freed_mb} MB)
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setShowConfirm(false);
            setPreviewResult(null);
          }}
          className="h-6 px-2 text-xs"
        >
          Cancel
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleConfirm}
          disabled={loading || previewResult.cleaned.length === 0}
          className="h-6 px-2 text-xs text-red-400 border-red-500/30 hover:bg-red-500/10"
        >
          {loading ? (
            <Loader2 className="size-3 motion-safe:animate-spin" />
          ) : (
            "Confirm"
          )}
        </Button>
      </div>
    );
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handlePreview}
      disabled={loading || disabled}
      className="h-7 px-2 text-xs text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/10"
    >
      {loading ? (
        <Loader2 className="size-3 motion-safe:animate-spin" />
      ) : (
        <Trash2 className="size-3" />
      )}
      <span className="ml-1">Cleanup</span>
    </Button>
  );
}
