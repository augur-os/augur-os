import { NextResponse } from 'next/server';
import { callMCPTool, MCPBridge } from '@/lib/mcp/MCPBridge';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const SKILL_ID = 'auto-logs';

const monitoringSignals = [
  'Check whether the archive helper is importable before claiming the loop can repair anything.',
  'Inspect llm_logs.jsonl directly in the shared logs directory so archival pressure is measured from the real runtime target.',
  'Report the active file size in megabytes when logs are eligible for archival.',
];

const repairStages = [
  'Scan: detect llm_logs.jsonl and measure its current size.',
  'Archive: hand the file to archive_logs() when repair mode is allowed.',
  'Confirm: return an explicit maintenance summary after the archive attempt.',
];

const difficultyLevels = [
  'd0: Detect log buildup and count archivable findings.',
  'd1: Validate the archive target and maintenance outcome.',
  'd2: Classify recurring log growth or archive-helper failures.',
];

type ToolArgs = Record<string, unknown>;

async function loadToolJson<T>(tool: string, args: ToolArgs): Promise<T> {
  const result = await callMCPTool(tool, args);

  if (result.isError) {
    throw new Error(MCPBridge.extractText(result) || `MCP tool failed: ${tool}`);
  }

  const raw = MCPBridge.extractText(result).trim();
  return raw ? (JSON.parse(raw) as T) : ({} as T);
}

function summarizeDoc(content: unknown): string {
  if (typeof content !== 'string' || content.trim().length === 0) {
    return 'Documentation is unavailable.';
  }

  const firstParagraph = content
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith('#'))[0];

  return firstParagraph || 'Documentation is unavailable.';
}

export async function GET(): Promise<Response> {
  try {
    const [health, actions, doc] = await Promise.all([
      loadToolJson('get-skill-health', { skill_id: SKILL_ID }),
      loadToolJson<{ actions?: unknown[] }>('list-skill-actions', {
        skill_id: SKILL_ID,
      }),
      loadToolJson<{ content?: string }>('get-skill-doc', {
        skill_id: SKILL_ID,
      }),
    ]);

    return NextResponse.json({
      skill: SKILL_ID,
      generatedAt: new Date().toISOString(),
      health,
      actions: actions.actions ?? [],
      overview: summarizeDoc(doc.content),
      target: 'llm_logs.jsonl',
      runtimeRoot: 'logs',
      fixCommand: 'archive_logs()',
      monitoringSignals,
      repairStages,
      difficultyLevels,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      {
        skill: SKILL_ID,
        error: message,
      },
      { status: 500 },
    );
  }
}
