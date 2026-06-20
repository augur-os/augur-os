/**
 * Page Template Generator (ADR-190)
 *
 * Generates a page.tsx file from a PageBuilderState.
 * The generated file imports BlockRenderer and renders each block
 * in the standard responsive dashboard grid.
 */

import type { PageBuilderState } from '../types';

/**
 * Generate a page.tsx file content from builder state.
 */
export function generatePageTemplate(
  state: PageBuilderState,
  mcpBlockTypes: string[] = []
): string {
  const blockImports = state.blocks
    .map(
      (b) =>
        `  { id: '${b.id}', blockType: '${b.blockType}', props: ${JSON.stringify(b.props)}, layout: ${JSON.stringify(b.layout)} }`
    )
    .join(',\n');
  const mcpTypesLiteral = JSON.stringify(mcpBlockTypes);

  return `'use client';

import { BlockRenderer } from '@/components/blocks/BlockRenderer';

const blocks = [
${blockImports}
];

const mcpBlockTypes = new Set(${mcpTypesLiteral});
const pageApiUrl = '/api/${state.hub}/${state.slug}';

export default function ${toPascalCase(state.slug)}Page() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {blocks.map((block) => {
          const isMcpBlock = mcpBlockTypes.has(block.blockType);
          const props = isMcpBlock
            ? { ...block.props, apiUrl: pageApiUrl, blockType: block.blockType }
            : block.props;
          const instance = {
            instanceId: block.id,
            blockId: block.blockType,
            config: props,
            position: {
              x: block.layout.col,
              y: block.layout.row,
              w: block.layout.w,
              h: block.layout.h,
            },
          };

          return (
            <div key={block.id} className={block.layout.w >= 2 ? 'lg:col-span-2' : undefined}>
              <BlockRenderer instance={instance} editing={false} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
`;
}

function toPascalCase(str: string): string {
  return str
    .split(/[-_\s]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join('');
}
