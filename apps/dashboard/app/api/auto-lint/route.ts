import { NextResponse } from 'next/server';
import { callMCPTool, MCPBridge } from '@/lib/mcp/MCPBridge';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const SKILL_ID = 'auto-lint';

const lintSignals = [
  'Run ESLint autofix before deeper follow-up so safe repairs land early.',
  'Keep unresolved diagnostics visible instead of masking them behind empty success states.',
  'Escalate only the remaining lint failures once autofix has reduced the issue set.',
];

const repairStages = [
  'Scan: collect lint diagnostics through the shared lint ops library.',
  'Autofix: apply safe ESLint fixes to reduce the remaining error set.',
  'Follow-Up: route unresolved diagnostics into deeper repair work.',
];

const difficultyLevels = [
  'd0: Discover lint issues and count diagnostics quickly.',
  'd1: Validate the autofix outcome and confirm the remaining failures are real.',
  'd2: Classify recurring lint failures and stale heuristics before they repeat.',
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
      lintSignals,
      repairStages,
      difficultyLevels,
      fixStrategy: 'eslint --fix',
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
