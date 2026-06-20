'use client';

import { GlassCard } from '@/components/ui/GlassCard';

import QuickNotes from './QuickNotes';
import DataTable from './DataTable';
import StatCards from './StatCards';
import ChartBlock from './ChartBlock';
import ActionButtons from './ActionButtons';
import AutoForm from './AutoForm';

/**
 * Registry of built-in block components.
 */
const BLOCK_COMPONENTS: Record<string, React.ComponentType<any>> = {
  QuickNotes,
  DataTable,
  StatCards,
  ChartBlock,
  ActionButtons,
  AutoForm,
};

/**
 * Map block type IDs to component names and display info.
 */
const BLOCK_META: Record<string, { component: string; name: string; color: string }> = {
  'quick-notes': { component: 'QuickNotes', name: 'Quick Notes', color: 'blue' },
  'data-table': { component: 'DataTable', name: 'Data Table', color: 'emerald' },
  'stat-cards': { component: 'StatCards', name: 'Stat Cards', color: 'amber' },
  'chart': { component: 'ChartBlock', name: 'Chart', color: 'purple' },
  'action-buttons': { component: 'ActionButtons', name: 'Action Buttons', color: 'rose' },
  'mcp-tool-form': { component: 'AutoForm', name: 'MCP Tool Form', color: 'cyan' },
};

interface BlockRendererProps {
  blockType: string;
  props?: Record<string, unknown>;
  blockId?: string;
  onConfigure?: () => void;
  onRemove?: () => void;
}

export default function BlockRenderer({
  blockType,
  props = {},
  blockId,
  onConfigure,
  onRemove,
}: BlockRendererProps) {
  const meta = BLOCK_META[blockType];

  if (!meta) {
    return (
      <GlassCard color="rose" title={`Unknown Block: ${blockType}`}>
        <p className="text-sm text-[var(--text-muted)]">
          Block type &quot;{blockType}&quot; is not registered.
        </p>
      </GlassCard>
    );
  }

  const Component = BLOCK_COMPONENTS[meta.component];

  if (!Component) {
    return (
      <GlassCard color="rose" title={`Missing Component: ${meta.component}`}>
        <p className="text-sm text-[var(--text-muted)]">
          Component &quot;{meta.component}&quot; could not be loaded.
        </p>
      </GlassCard>
    );
  }

  const blockProps = { ...props, blockId: blockId || blockType };

  return (
    <div className="relative group">
      {/* Block action buttons (shown on hover in builder mode) */}
      {(onConfigure || onRemove) && (
        <div className="absolute top-2 right-2 z-20 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {onConfigure && (
            <button
              onClick={onConfigure}
              className="p-1.5 rounded-lg bg-[var(--bg-secondary)]/80 backdrop-blur border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              title="Configure"
              aria-label="Configure block"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
            </button>
          )}
          {onRemove && (
            <button
              onClick={onRemove}
              className="p-1.5 rounded-lg bg-[var(--bg-secondary)]/80 backdrop-blur border border-[var(--border-color)] text-[var(--text-muted)] hover:text-rose-400 transition-colors"
              title="Remove"
              aria-label="Remove block"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      )}

      <Component {...blockProps} />
    </div>
  );
}
