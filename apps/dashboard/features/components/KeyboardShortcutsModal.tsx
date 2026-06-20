"use client";

import { useEffect, useEffectEvent } from "react";
import { X, Keyboard } from "lucide-react";
import { SHORTCUT_LIST } from "@/hooks/useKeyboardShortcuts";

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function KeyboardShortcutsModal({
  isOpen,
  onClose,
}: KeyboardShortcutsModalProps) {
  const closeFromEffect = useEffectEvent(onClose);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        closeFromEffect();
      }
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <dialog
      open
      className="fixed inset-0 z-50 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center border-0 bg-transparent p-0 text-inherit"
      aria-label="Keyboard shortcuts"
    >
      <button
        type="button"
        aria-label="Close shortcuts"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm border-0 p-0"
        onClick={onClose}
      />
      <div
        className="relative glass-panel p-6 w-full max-w-md mx-4 animate-in fade-in zoom-in-95 duration-200"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-[var(--text-primary)]">
            <Keyboard className="size-5 text-[var(--accent-info)]" />
            <h2 className="text-lg font-semibold">Keyboard Shortcuts</h2>
          </div>
          <button type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
            aria-label="Close shortcuts"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        <div className="space-y-2">
          {SHORTCUT_LIST.map((shortcut) => (
            <div
              key={shortcut.keys.join("+")}
              className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-[var(--bg-hover)]"
            >
              <span className="text-sm text-[var(--text-secondary)]">
                {shortcut.description}
              </span>
              <div className="flex gap-1">
                {shortcut.keys.map((key) => (
                  <kbd
                    key={key}
                    className="px-2 py-1 text-xs font-mono bg-[var(--bg-secondary)] text-[var(--text-primary)] rounded border border-[var(--border-color)]"
                  >
                    {key}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 pt-4 border-t border-[var(--border-color)] text-center">
          <span className="text-xs text-[var(--text-muted)]">
            Press{" "}
            <kbd className="px-1.5 py-0.5 bg-[var(--bg-secondary)] text-[var(--text-secondary)] rounded text-[10px] font-mono">
              ?
            </kbd>{" "}
            anywhere to show this help
          </span>
        </div>
      </div>
    </dialog>
  );
}
