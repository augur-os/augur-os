/**
 * API Route Template Generator (ADR-190)
 *
 * Generates an API route.ts file for pages that contain MCP-backed blocks.
 * The route proxies MCP tool calls for each MCP block.
 */

import type { PageBuilderState } from '../types';

/**
 * Check if a page needs an API route (has MCP blocks).
 */
export function needsApiRoute(state: PageBuilderState, blockRegistry: Map<string, { source: string; mcpTool?: string }>): boolean {
  return state.blocks.some((b) => {
    const manifest = blockRegistry.get(b.blockType);
    if (manifest?.source === 'mcp' && manifest?.mcpTool) return true;
    if (manifest?.source === 'mcp') return true;
    return typeof b.props?.mcpTool === 'string' && b.props.mcpTool.trim().length > 0;
  });
}

/**
 * Generate an API route.ts file for MCP tool proxying.
 */
export function generateRouteTemplate(
  state: PageBuilderState,
  blockRegistry: Map<string, { source: string; mcpTool?: string; mcpServer?: string }>
): string {
  const mcpBlocks = state.blocks.filter((b) => {
    const manifest = blockRegistry.get(b.blockType);
    if (manifest?.source === 'mcp') return true;
    return typeof b.props?.mcpTool === 'string' && b.props.mcpTool.trim().length > 0;
  });

  const toolCases = mcpBlocks
    .map((b) => {
      const manifest = blockRegistry.get(b.blockType);
      const configuredTool =
        typeof b.props?.mcpTool === 'string' ? b.props.mcpTool : '';
      return `    case '${b.blockType}':
      toolName = '${manifest?.mcpTool ?? configuredTool}';
      break;
    case '${b.id}':
      toolName = '${manifest?.mcpTool ?? configuredTool}';
      break;`;
    })
    .join('\n');

  return `import { NextRequest, NextResponse } from 'next/server';
import { callMCPTool, extractContextFromRequest, MCPBridge } from '@/lib/mcp/MCPBridge';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { blockType, blockId, params } = body;

    let toolName = '';
    switch (blockId || blockType) {
${toolCases}
      default:
        break;
    }

    const payload = typeof params === 'object' && params !== null
      ? { ...(params as Record<string, unknown>) }
      : {};

    // mcp-tool-form can provide tool name dynamically
    if (!toolName && typeof payload.mcpTool === 'string') {
      toolName = payload.mcpTool;
    }

    if (!toolName) {
      return NextResponse.json({ error: 'No MCP tool configured for this block' }, { status: 400 });
    }

    delete payload.mcpTool;
    delete payload.mcpServer;

    const mcpContext = extractContextFromRequest(request);
    const result = await callMCPTool(toolName, payload, mcpContext);
    if (result.isError) {
      return NextResponse.json(
        { error: MCPBridge.extractText(result) || 'MCP call failed' },
        { status: 500 }
      );
    }

    const data = MCPBridge.parseJSON<Record<string, unknown>>(result);
    if (data.error) {
      return NextResponse.json(
        { error: String(data.error), details: data.message ?? null },
        { status: Number(data.statusCode) || 500 }
      );
    }

    return NextResponse.json({ success: true, data });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
`;
}
