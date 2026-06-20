import { NextResponse } from 'next/server';
import { callMCPTool, MCPBridge } from '@/lib/mcp/MCPBridge';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const SKILL_ID = 'auto-git-health';

const monitoringSignals = [
  'Measure the current .git directory footprint directly from the project root.',
  'Raise a warning when repository object storage exceeds the 300 MB threshold.',
  'Limit repair mode to git gc --prune=now so cleanup remains predictable.',
];

const repairStages = [
  'Scan: measure .git size from the project root.',
  'Threshold: promote a warning issue once the repository exceeds 300 MB.',
  'Repair: run git gc --prune=now and report reclaimed space.',
];

const difficultyLevels = [
  'd0: Detect repository growth and count scan results.',
  'd1: Validate the threshold breach and cleanup outcome.',
  'd2: Classify recurring repository growth or git maintenance failures.',
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
      target: '.git',
      thresholdMb: 300,
      fixCommand: 'git gc --prune=now',
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
