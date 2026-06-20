'use client';

import { BlockRenderer } from '@/components/blocks/BlockRenderer';
import type { BlockManifest, BlockInstance } from '@/lib/blocks/types';

interface BrowseBlockStackProps {
  blocks: BlockManifest[];
}

function manifestToInstance(manifest: BlockManifest, index: number): BlockInstance {
  return {
    instanceId: `detail-${manifest.id}`,
    blockId: manifest.id,
    config: {},
    position: { x: 0, y: index, w: 12, h: 1 },
  };
}

export function BrowseBlockStack({ blocks }: BrowseBlockStackProps) {
  if (blocks.length === 0) {
    return (
      <p className="text-sm text-[var(--text-muted)] py-4">
        No blocks available for this skill.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {blocks.map((manifest, i) => (
        <div key={manifest.id} className="min-h-[120px]">
          <BlockRenderer
            instance={manifestToInstance(manifest, i)}
            editing={false}
          />
        </div>
      ))}
    </div>
  );
}
