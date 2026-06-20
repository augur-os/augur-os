"use client";

import { useEffect, useEffectEvent } from "react";
import { AlertTriangle } from "lucide-react";

interface ConfirmDialogProps {
  open: boolean;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({
  open,
  message,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelFromEffect = useEffectEvent(onCancel);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") cancelFromEffect();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  if (!open) return null;

  return (
    <dialog
      open
      className="fixed inset-0 z-50 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center border-0 bg-transparent p-0 text-inherit"
      role="alertdialog"
      aria-label="Confirmation"
    >
      <button
        type="button"
        aria-label="Cancel confirmation"
        className="absolute inset-0 bg-black/50 border-0 p-0"
        onClick={onCancel}
      />
      <div
        className="relative bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-xl p-6 max-w-[400px] w-[90%] flex flex-col gap-4"
      >
        <div className="flex items-center gap-3">
          <AlertTriangle
            className="size-6 text-[var(--accent-warning)] shrink-0"
          />
          <p className="text-sm text-[var(--text-primary)] leading-relaxed">
            {message}
          </p>
        </div>
        <div className="flex justify-end gap-2">
          <button type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] text-sm cursor-pointer hover:bg-[var(--bg-hover)] transition-colors"
          >
            Cancel
          </button>
          <button type="button"
            onClick={onConfirm}
            className="px-4 py-2 rounded-lg border-none bg-[var(--accent-danger)] text-white text-sm cursor-pointer hover:opacity-90 transition-opacity"
          >
            Confirm
          </button>
        </div>
      </div>
    </dialog>
  );
}
