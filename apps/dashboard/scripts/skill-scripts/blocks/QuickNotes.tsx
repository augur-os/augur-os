'use client';

import { useState } from 'react';
import { GlassCard } from '@/components/ui/GlassCard';

interface QuickNotesProps {
  blockId: string;
  defaultContent?: string;
}

export default function QuickNotes({ blockId, defaultContent = '' }: QuickNotesProps) {
  const storageKey = `augur:block:notes:${blockId}`;
  const [content, setContent] = useState<string>(() => {
    if (typeof window === 'undefined') return defaultContent;
    return localStorage.getItem(storageKey) ?? defaultContent;
  });

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const value = e.target.value;
    setContent(value);
    localStorage.setItem(storageKey, value);
  }

  return (
    <GlassCard className="p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
          Notes
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Auto-saved
        </span>
      </div>
      <textarea
        className="flex-1 w-full resize-none rounded-md p-3 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-colors"
        style={{
          background: 'var(--bg-card)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-color)',
          minHeight: '160px',
        }}
        placeholder="Type your notes..."
        value={content}
        onChange={handleChange}
      />
    </GlassCard>
  );
}
