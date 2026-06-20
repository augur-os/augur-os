'use client';

/**
 * ADR-274 D8: Detail modal for auto-page row/card clicks.
 *
 * Opens a detail modal showing item data in configured section renderers.
 * State managed via URL search params namespaced by section ID to avoid
 * collisions with other modals and tabbed sections (D13) on the same page.
 */

import { useEffect, useEffectEvent, useRef } from 'react';
import { X } from 'lucide-react';

import Markdown from '@/components/Markdown';
import type { RowActionDefinition } from './types';

interface DetailModalProps {
  item: Record<string, unknown>;
  config: RowActionDefinition;
  onClose: () => void;
}

export function DetailModal({ item, config, onClose }: DetailModalProps) {
  const modalRef = useRef<HTMLDialogElement>(null);
  const closeFromEffect = useEffectEvent(onClose);

  // Trap focus and handle Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeFromEffect();
    };
    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';
    // Focus trap
    modalRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, []);

  const title = String(item[config.title_field] ?? '');

  return (
    <dialog
      ref={modalRef}
      open
      className="fixed inset-0 z-50 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center border-0 bg-transparent p-0 text-inherit"
      aria-label={title}
    >
      <button
        type="button"
        aria-label="Close detail modal"
        className="absolute inset-0 bg-black/40 border-0 p-0"
        onClick={onClose}
      />
      <div
        className="relative max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-[var(--bg-card)] p-6 shadow-xl border border-[var(--border-color)]"
      >
        {/* Header */}
        <div className="mb-4 flex items-start justify-between">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h2>
          <button type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-secondary)] transition-colors"
            aria-label="Close detail modal"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>

        {/* Sections */}
        <div className="space-y-4">
          {config.sections.map((section) => {
            const value = item[section.field];
            if (value == null) return null;

            return (
              <div key={section.field}>
                <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                  {section.field}
                </h3>
                <SectionContent value={value} render={section.render} />
              </div>
            );
          })}
        </div>
      </div>
    </dialog>
  );
}

function SectionContent({ value, render }: { value: unknown; render: string }) {
  switch (render) {
    case 'markdown':
      return <Markdown markdown={String(value)} />;

    case 'key-value': {
      const obj = typeof value === 'object' && value !== null ? value : {};
      const entries = Object.entries(obj as Record<string, unknown>);
      return (
        <div className="rounded-lg bg-[var(--bg-secondary)] p-3">
          {entries.map(([k, v]) => (
            <div key={k} className="flex justify-between py-1.5 text-sm border-b border-[var(--border-color)] last:border-0">
              <span className="text-[var(--text-muted)]">{k}</span>
              <span className="font-medium text-[var(--text-primary)]">{String(v ?? '-')}</span>
            </div>
          ))}
        </div>
      );
    }

    case 'text':
    default:
      return (
        <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{String(value)}</p>
      );
  }
}
