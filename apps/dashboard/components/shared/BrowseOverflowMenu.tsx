'use client';

import { createElement, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, MoreHorizontal, type LucideIcon } from 'lucide-react';
import { resolveIcon } from '@/lib/icon-map';

export interface BrowseOverflowMenuItem {
  id: string;
  label: string;
  icon?: string;
  onSelect: () => void | Promise<void>;
  variant?: 'default' | 'danger';
  disabled?: boolean;
}

interface BrowseOverflowMenuProps {
  items: BrowseOverflowMenuItem[];
  buttonLabel?: string;
  menuLabel?: string;
  triggerMode?: 'icon' | 'icon-label';
  /** Leading icon for the trigger. Defaults to the "more" dots (MoreHorizontal). */
  triggerIcon?: LucideIcon;
  /** Show a chevron after the label so the trigger reads as a menu (icon-label mode only). */
  showTriggerChevron?: boolean;
  align?: 'left' | 'right';
  stopPropagation?: boolean;
  className?: string;
  buttonTestId?: string;
}

export function BrowseOverflowMenu({
  items,
  buttonLabel = 'More actions',
  menuLabel = 'More actions',
  triggerMode = 'icon',
  triggerIcon: TriggerIcon = MoreHorizontal,
  showTriggerChevron = false,
  align = 'right',
  stopPropagation = false,
  className,
  buttonTestId,
}: BrowseOverflowMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const updateMenuPosition = useCallback(() => {
    const trigger = containerRef.current;
    const menu = menuRef.current;
    if (!trigger || !menu || typeof window === 'undefined') return;

    const triggerRect = trigger.getBoundingClientRect();
    const menuWidth = menu.offsetWidth || 192;
    const menuHeight = menu.offsetHeight || 0;
    const viewportPadding = 8;
    const gap = 8;

    const preferredLeft = align === 'left'
      ? triggerRect.left
      : triggerRect.right - menuWidth;
    const maxLeft = window.innerWidth - menuWidth - viewportPadding;
    const left = Math.max(viewportPadding, Math.min(preferredLeft, maxLeft));

    let top = triggerRect.bottom + gap;
    if (menuHeight > 0 && top + menuHeight > window.innerHeight - viewportPadding) {
      top = Math.max(viewportPadding, triggerRect.top - menuHeight - gap);
    }

    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
  }, [align]);
  const updateMenuPositionRef = useRef(updateMenuPosition);
  useEffect(() => {
    updateMenuPositionRef.current = updateMenuPosition;
  }, [updateMenuPosition]);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      const insideTrigger = containerRef.current?.contains(target);
      const insideMenu = menuRef.current?.contains(target);
      if (!insideTrigger && !insideMenu) {
        setOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    const updatePositionFromEvent = () => updateMenuPositionRef.current();

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    window.addEventListener('resize', updatePositionFromEvent);
    window.addEventListener('scroll', updatePositionFromEvent, true);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('resize', updatePositionFromEvent);
      window.removeEventListener('scroll', updatePositionFromEvent, true);
    };
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    updateMenuPosition();
  }, [open, updateMenuPosition]);

  if (items.length === 0) {
    return null;
  }

  const triggerClassName = triggerMode === 'icon-label'
    ? 'inline-flex h-8 cursor-pointer items-center gap-1.5 px-3 rounded-full border border-[var(--border-color)] bg-[var(--bg-secondary)] text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors duration-200'
    : 'inline-flex cursor-pointer items-center justify-center p-2 min-h-[36px] min-w-[36px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors duration-200';

  return (
    <div ref={containerRef} className={`relative ${open ? 'z-[80]' : 'z-0'} ${className ?? ''}`.trim()}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={buttonLabel}
        data-testid={buttonTestId}
        onClick={(event) => {
          if (stopPropagation) {
            event.stopPropagation();
          }
          setOpen((current) => {
            if (current) return false;
            window.requestAnimationFrame(updateMenuPosition);
            return true;
          });
        }}
        onKeyDown={(event) => {
          if (stopPropagation) {
            event.stopPropagation();
          }
        }}
        className={triggerClassName}
      >
        <TriggerIcon
          className={triggerMode === 'icon-label' ? 'size-3.5 text-[var(--text-muted)]' : 'size-4'}
          aria-hidden="true"
        />
        {triggerMode === 'icon-label' && <span>{buttonLabel}</span>}
        {triggerMode === 'icon-label' && showTriggerChevron && (
          <ChevronDown
            className={`size-3.5 shrink-0 text-[var(--text-muted)] transition-transform ${open ? 'rotate-180' : ''}`}
            aria-hidden="true"
          />
        )}
      </button>

      {open && typeof document !== 'undefined' && createPortal((
        <div
          ref={menuRef}
          role="menu"
          aria-label={menuLabel}
          style={{ left: -9999, top: -9999 }}
          className="fixed z-[1000] min-w-[12rem] rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)] p-1 shadow-xl"
        >
          {items.map((item) => {
            return (
              <button
                key={item.id}
                type="button"
                role="menuitem"
                disabled={item.disabled}
                data-variant={item.variant ?? 'default'}
                onClick={(event) => {
                  if (stopPropagation) {
                    event.stopPropagation();
                  }
                  setOpen(false);
                  void item.onSelect();
                }}
                className={`flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${
                  item.variant === 'danger'
                    ? 'text-[var(--accent-danger)] hover:bg-[var(--accent-danger)]/10'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
                }`}
              >
                {createElement(resolveIcon(item.icon), { className: 'size-3.5 shrink-0' })}
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      ), document.body)}
    </div>
  );
}
