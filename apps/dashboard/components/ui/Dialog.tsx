"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

interface DialogProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

const DialogContext = React.createContext<{
  open: boolean;
  onOpenChange: (open: boolean) => void;
} | null>(null);

const DialogTitleIdContext = React.createContext<string | undefined>(undefined);

export function Dialog({ open = false, onOpenChange, children }: DialogProps) {
  const [localOpen, setLocalOpen] = React.useReducer(
    (_current: boolean, next: boolean) => next,
    open,
  );
  const isOpen = onOpenChange ? open : localOpen;

  const handleOpenChange = React.useCallback((newOpen: boolean) => {
    if (onOpenChange) {
      onOpenChange(newOpen);
    } else {
      setLocalOpen(newOpen);
    }
  }, [onOpenChange]);
  const contextValue = React.useMemo(
    () => ({ open: isOpen, onOpenChange: handleOpenChange }),
    [handleOpenChange, isOpen],
  );

  return (
    <DialogContext.Provider value={contextValue}>
      {children}
    </DialogContext.Provider>
  );
}

function DialogTrigger({
  children,
  asChild,
}: {
  children: React.ReactNode;
  asChild?: boolean;
}) {
  const context = React.use(DialogContext);

  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(
      children as React.ReactElement<{ onClick?: () => void }>,
      {
        onClick: () => context?.onOpenChange(true),
      },
    );
  }

  return (
    <button type="button" onClick={() => context?.onOpenChange(true)}>
      {children}
    </button>
  );
}

export function DialogContent({
  children,
  className = "",
  portal = false,
}: {
  children: React.ReactNode;
  className?: string;
  portal?: boolean;
}) {
  const context = React.use(DialogContext);
  const isOpen = context?.open ?? false;
  const onOpenChange = context?.onOpenChange;
  const titleId = React.useId();
  const containerRef = React.useRef<HTMLDialogElement>(null);
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  // Focus the dialog container when it mounts/opens
  React.useEffect(() => {
    if (isOpen) {
      containerRef.current?.focus();
    }
  }, [isOpen]);

  // Document-level Escape key handler
  React.useEffect(() => {
    if (!isOpen || !onOpenChange) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onOpenChange(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onOpenChange]);

  if (!isOpen || !onOpenChange) return null;

  const dialog = (
    <DialogTitleIdContext.Provider value={titleId}>
      <dialog
        ref={containerRef}
        open
        className={`fixed inset-0 ${portal ? "z-[100]" : "z-50"} m-0 flex h-full max-h-none w-full max-w-none items-center justify-center border-0 bg-transparent p-0 text-inherit`}
        aria-labelledby={titleId}
      >
        {/* Backdrop — distinct accessible name from the explicit close button
            so assistive tech announces one canonical "Close dialog" (the X)
            rather than two identically-named controls. */}
        <button
          type="button"
          aria-label="Dismiss dialog"
          className="fixed inset-0 bg-black/80 backdrop-blur-sm animate-in fade-in-0 border-0 p-0"
          onClick={() => onOpenChange(false)}
        />

        {/* Content */}
        <div
          className={`
            relative z-50 w-full max-w-lg max-h-[90vh] overflow-auto
            glass-panel border border-[var(--border-color)] rounded-xl shadow-xl
            animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-2
            outline-none
            ${className}
          `}
          style={portal ? { background: "var(--bg-primary)" } : undefined}
        >
          {/* Close button */}
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100 transition-opacity"
            aria-label="Close dialog"
          >
            <X className="size-4 text-[var(--text-muted)]" />
            <span className="sr-only">Close</span>
          </button>

          {children}
        </div>
      </dialog>
    </DialogTitleIdContext.Provider>
  );

  if (portal) {
    return mounted ? createPortal(dialog, document.body) : null;
  }

  return dialog;
}

export function DialogHeader({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col space-y-1.5 p-6 pb-0 ${className}`}>
      {children}
    </div>
  );
}

export function DialogTitle({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const titleId = React.use(DialogTitleIdContext);

  return (
    <h2
      id={titleId}
      className={`text-lg font-semibold leading-none tracking-tight text-[var(--text-primary)] ${className}`}
    >
      {children}
    </h2>
  );
}

export function DialogDescription({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p className={`text-sm text-[var(--text-muted)] ${className}`}>
      {children}
    </p>
  );
}

export function DialogFooter({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 p-6 pt-0 ${className}`}
    >
      {children}
    </div>
  );
}
