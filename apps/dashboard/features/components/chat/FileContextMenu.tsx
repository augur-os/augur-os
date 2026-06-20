"use client";

import { useState, useEffect, useCallback, useRef, useEffectEvent } from "react";
import { createPortal } from "react-dom";
import { Paperclip, Eye, ExternalLink, Copy } from "lucide-react";

export interface FileContextMenuProps {
  children: React.ReactNode;
  filePath: string;
  fileName: string;
  onAttach: (filePath: string) => void;
  onPreview?: (filePath: string) => void;
  onOpenExternal?: (filePath: string) => void;
}

interface MenuPosition {
  x: number;
  y: number;
}

interface MenuOption {
  label: string;
  icon: React.ReactNode;
  action: () => void;
}

export function FileContextMenu({
  children,
  filePath,
  fileName,
  onAttach,
  onPreview,
  onOpenExternal,
}: FileContextMenuProps) {
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const closeMenu = useCallback(() => {
    setMenuPosition(null);
  }, []);
  const closeMenuFromEffect = useEffectEvent(closeMenu);

  useEffect(() => {
    if (!menuPosition) return;

    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        closeMenuFromEffect();
      }
    }

    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") closeMenuFromEffect();
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [menuPosition]);

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setMenuPosition({ x: e.clientX, y: e.clientY });
    },
    [],
  );

  const attachSelectedFile = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onAttach(filePath);
    },
    [onAttach, filePath],
  );

  const options: MenuOption[] = [
    {
      label: "Attach to Chat",
      icon: <Paperclip className="size-3.5" />,
      action: () => {
        onAttach(filePath);
        closeMenu();
      },
    },
  ];

  if (onPreview) {
    options.push({
      label: "Preview",
      icon: <Eye className="size-3.5" />,
      action: () => {
        onPreview(filePath);
        closeMenu();
      },
    });
  }

  if (onOpenExternal) {
    options.push({
      label: "Open in Finder",
      icon: <ExternalLink className="size-3.5" />,
      action: () => {
        onOpenExternal(filePath);
        closeMenu();
      },
    });
  }

  options.push({
    label: "Copy Path",
    icon: <Copy className="size-3.5" />,
    action: () => {
      navigator.clipboard.writeText(filePath);
      closeMenu();
    },
  });

  return (
    <>
      <button
        type="button"
        aria-label={`Attach ${fileName}`}
        onClick={attachSelectedFile}
        onContextMenu={handleContextMenu}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onAttach(filePath);
          }
        }}
        className="cursor-pointer border-0 bg-transparent p-0 text-left"
      >
        {children}
      </button>

      {menuPosition &&
        createPortal(
          <div
            ref={menuRef}
            role="menu"
            aria-label={`Actions for ${fileName}`}
            className="fixed z-[65] min-w-[180px] bg-[var(--bg-popover)] backdrop-blur-xl border border-[var(--border-color)]/60 rounded-xl shadow-2xl py-1 animate-in fade-in duration-100"
            style={{ top: menuPosition.y, left: menuPosition.x }}
          >
            <div className="px-2.5 py-1.5 border-b border-[var(--border-color)]">
              <span className="text-[10px] text-[var(--text-muted)] font-medium truncate block max-w-[200px]">
                {fileName}
              </span>
            </div>
            {options.map((option) => (
              <button
                key={option.label}
                type="button"
                role="menuitem"
                onClick={option.action}
                className="w-full text-left px-2.5 py-1.5 flex items-center gap-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
              >
                {option.icon}
                <span>{option.label}</span>
              </button>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}
