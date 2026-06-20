# IDE Interaction Modes Simplification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the five-mode `dispatch` system (fire/oneshot/ide/chat/auto) with file-based `skills/<skill>/prompts/` and `commands/` directories, a clean `/api/cli/exec` print-mode route, a pre-warmed `SessionManager`, and a new Browse page tabs UI showing prompts, commands, and CLI integration per skill.

**Architecture:** Prompts and commands live as individual `.md` files in `skills/<skill>/prompts/` and `skills/<skill>/commands/` (Agent Skills standard). The dashboard discovers them via a server-side scanner and exposes `/api/cli/exec` which runs them non-interactively via PTY and streams JSONL back. A `SessionManager` singleton pre-warms the default CLI session and handles the "Continue in session" flow. Browse gains Prompts / Commands / Integration tabs replacing the old action buttons.

**Tech Stack:** Next.js 14 App Router, TypeScript, node-pty, SSE, gray-matter (prompt/command `.md` file parsing), Jest + React Testing Library, Python (migration script).

**Spec:** `docs/superpowers/specs/2026-04-20-ide-interaction-modes-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `apps/dashboard/lib/browse/types.ts` | Modify | Add `SkillPrompt`, `SkillCommand`; extend `SkillDetail` |
| `apps/dashboard/lib/server/skillsLookup.ts` | Modify | `readSkillMeta` returns `prompts` + `commands` scanned from skill directories |
| `apps/dashboard/app/api/cli/exec/route.ts` | Create | `POST /api/cli/exec` — resolves default CLI, spawns print-mode PTY |
| `apps/dashboard/app/api/cli/exec/exec-store.ts` | Create | In-memory store for active exec processes |
| `apps/dashboard/app/api/cli/exec/stream/route.ts` | Create | `GET /api/cli/exec/stream?id=xxx` — SSE stream of JSONL events |
| `apps/dashboard/lib/session/SessionManager.ts` | Create | Pre-warmed default CLI PTY lifecycle, resume chain, collision |
| `apps/dashboard/app/api/session/continue/route.ts` | Create | Inject prior result + open session; emits `collision` if active |
| `apps/dashboard/app/api/session/init/route.ts` | Create | Pre-warm endpoint called once on dashboard load |
| `apps/dashboard/components/session/ContinueInSessionListener.tsx` | Create | Window-event listener → POSTs continue route, handles collision toast |
| `apps/dashboard/components/session/SessionPrewarmer.tsx` | Create | Mount-once client component that fires `/api/session/init` |
| `apps/dashboard/app/layout.tsx` | Modify | Mount `ContinueInSessionListener` and `SessionPrewarmer` |
| `apps/dashboard/components/browse/PromptCard.tsx` | Create | Prompt card with multi-var inline inputs, Run button, loading state |
| `apps/dashboard/components/browse/ResultCard.tsx` | Create | Result display: markdown answer, "Continue in session", Copy |
| `apps/dashboard/components/browse/CommandCard.tsx` | Create | Command card: label, command string, Run button |
| `apps/dashboard/components/browse/IntegrationTab.tsx` | Create | Live `augur <skill> --help` output rendered as code block |
| `apps/dashboard/components/browse/SkillDetailTabs.tsx` | Create | Tabs container: Overview / Prompts / Commands / Integration |
| `apps/dashboard/app/(views)/browse/[skill]/page.tsx` | Modify | Use `SkillDetailTabs` instead of bare `ConfigPage` |
| `tests/dashboard/api/exec-route.test.ts` | Create | Unit tests for /api/cli/exec |
| `tests/dashboard/api/continue-route.test.ts` | Create | Unit tests for /api/session/continue |
| `tests/dashboard/browse/PromptCard.test.tsx` | Create | Unit tests for PromptCard |
| `tests/dashboard/browse/ResultCard.test.tsx` | Create | Unit tests for ResultCard |
| `tests/dashboard/session/SessionManager.test.ts` | Create | Unit tests for SessionManager |
| `scripts/migrate_actions_to_prompts.py` | Create | One-time migration: `actions:` → `prompts:` + `commands:` across all skills |

---

## Task 1: Extend TypeScript types

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts`

- [ ] **Step 1: Add `SkillPrompt` and `SkillCommand` interfaces and update `SkillDetail`**

Open `apps/dashboard/lib/browse/types.ts`. After the `SkillAction` interface (line ~161), add:

```ts
export interface SkillPrompt {
  id: string;
  label: string;
  description?: string;
  prompt: string;       // raw prompt string, may contain {{var}} placeholders
  icon?: string;
}

export interface SkillCommand {
  id: string;
  label: string;
  description?: string;
  command: string;      // slash command string e.g. "/knowledge refresh"
  icon?: string;
}
```

Then in `SkillDetail`, add after `actions: SkillAction[];`:

```ts
  prompts: SkillPrompt[];
  commands: SkillCommand[];
```

- [ ] **Step 2: Add `PromptResult` type** (used by ResultCard and exec route)

Add at the bottom of `types.ts`:

```ts
export interface PromptResult {
  promptId: string;
  input: string;        // resolved prompt string sent to CLI
  answer: string;       // extracted final answer markdown
  sessionId: string;    // CLI session ID for --resume
  cliId: string;
  durationMs: number;
  timestamp: Date;
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard && npx tsc --noEmit 2>&1 | head -30
```

Expected: errors only from files that reference `SkillDetail` without the new fields (will fix in later tasks).

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/lib/browse/types.ts
git commit -m "feat(browse): add SkillPrompt, SkillCommand, PromptResult types"
```

---

## Task 2: Discover prompts and commands by scanning skill directories

**Files:**
- Modify: `apps/dashboard/lib/server/skillsLookup.ts`
- Create: `apps/dashboard/lib/server/skillContent.ts`

Per the Agent Skills standard, prompts live as `skills/<skill>/prompts/<id>.md` and commands as `skills/<skill>/commands/<id>.md`. Each file has YAML frontmatter (metadata) and a markdown body (the prompt text or command spec). We add a server-side scanner that returns `SkillPrompt[]` and `SkillCommand[]` from these directories.

- [ ] **Step 1: Create `skillContent.ts` — directory scanner**

Create `apps/dashboard/lib/server/skillContent.ts`:

```ts
import fs from 'fs/promises';
import path from 'path';
import matter from 'gray-matter';

import { getRepoRoot } from '@/lib/server/repo';
import type { SkillPrompt, SkillCommand } from '@/lib/browse/types';

interface ParsedFile {
  id: string;
  label?: string;
  description?: string;
  icon?: string;
  body: string;
}

async function readMarkdownFile(filePath: string): Promise<ParsedFile | null> {
  try {
    const raw = await fs.readFile(filePath, 'utf8');
    const parsed = matter(raw);
    const d = (parsed.data || {}) as Record<string, unknown>;
    const filenameId = path.basename(filePath, '.md');
    const id = typeof d.id === 'string' && d.id.length > 0 ? d.id : filenameId;
    return {
      id,
      label: typeof d.label === 'string' ? d.label : undefined,
      description: typeof d.description === 'string' ? d.description : undefined,
      icon: typeof d.icon === 'string' ? d.icon : undefined,
      body: parsed.content.trim(),
    };
  } catch {
    return null;
  }
}

async function scanDir(dir: string): Promise<ParsedFile[]> {
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return []; // directory does not exist — that's fine
  }

  const mdFiles = entries.filter(name => name.endsWith('.md'));
  const parsed = await Promise.all(
    mdFiles.map(name => readMarkdownFile(path.join(dir, name)))
  );
  return parsed.filter((p): p is ParsedFile => p !== null);
}

function humanize(id: string): string {
  return id
    .split(/[-_]/)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export async function readSkillPrompts(skillId: string): Promise<SkillPrompt[]> {
  const dir = path.join(getRepoRoot(), 'skills', skillId, 'prompts');
  const files = await scanDir(dir);
  return files.map(f => ({
    id: f.id,
    label: f.label ?? humanize(f.id),
    description: f.description,
    prompt: f.body,
    icon: f.icon,
  }));
}

export async function readSkillCommands(skillId: string): Promise<SkillCommand[]> {
  const dir = path.join(getRepoRoot(), 'skills', skillId, 'commands');
  const files = await scanDir(dir);
  return files.map(f => ({
    id: f.id,
    label: f.label ?? humanize(f.id),
    description: f.description,
    // Convention: the slash-command invocation is `/<id>` — body is the spec, not the invocation
    command: `/${f.id}`,
    icon: f.icon,
  }));
}
```

- [ ] **Step 2: Update `readSkillMeta` to expose prompts/commands via the scanner**

Open `apps/dashboard/lib/server/skillsLookup.ts`. Add an import at top:

```ts
import { readSkillPrompts, readSkillCommands } from './skillContent';
```

Replace the current `readSkillMeta` function with:

```ts
export async function readSkillMeta(skillId: string): Promise<{
  title?: string;
  icon?: string;
  hub?: string;
  mcpTools?: string[];
  prompts?: import('@/lib/browse/types').SkillPrompt[];
  commands?: import('@/lib/browse/types').SkillCommand[];
} | null> {
  const repoRoot = getRepoRoot();
  const skillMd = path.join(repoRoot, "skills", skillId, "SKILL.md");
  try {
    const raw = await fs.readFile(skillMd, "utf8");
    const parsed = matter(raw);
    const d = parsed.data || {};

    const [prompts, commands] = await Promise.all([
      readSkillPrompts(skillId),
      readSkillCommands(skillId),
    ]);

    return {
      title: d["x-augur-tab"] || d.name || skillId,
      icon: undefined,
      hub: d["x-augur-hub"],
      mcpTools: Array.isArray(d["x-augur-mcp-tools"]) ? d["x-augur-mcp-tools"] : [],
      prompts,
      commands,
    };
  } catch {
    return null;
  }
}
```

- [ ] **Step 3: Write a unit test for the scanner**

Create `tests/dashboard/server/skillContent.test.ts`:

```ts
import { readSkillPrompts, readSkillCommands } from '@/lib/server/skillContent';

jest.mock('@/lib/server/repo', () => ({
  getRepoRoot: () => process.cwd(),
}));

import fs from 'fs/promises';

jest.mock('fs/promises');

describe('skillContent scanner', () => {
  beforeEach(() => {
    (fs.readdir as jest.Mock).mockReset();
    (fs.readFile as jest.Mock).mockReset();
  });

  it('returns empty array when prompts/ directory missing', async () => {
    (fs.readdir as jest.Mock).mockRejectedValueOnce(new Error('ENOENT'));
    const result = await readSkillPrompts('test-skill');
    expect(result).toEqual([]);
  });

  it('parses prompt files with frontmatter', async () => {
    (fs.readdir as jest.Mock).mockResolvedValueOnce(['agentic-search.md', 'README.txt']);
    (fs.readFile as jest.Mock).mockResolvedValueOnce(
      `---\nid: agentic-search\nlabel: Agentic Search\nicon: Search\n---\n\nSearch for: {{query}}\n`
    );
    const result = await readSkillPrompts('knowledge');
    expect(result).toEqual([{
      id: 'agentic-search',
      label: 'Agentic Search',
      description: undefined,
      prompt: 'Search for: {{query}}',
      icon: 'Search',
    }]);
  });

  it('falls back to filename when id missing in frontmatter', async () => {
    (fs.readdir as jest.Mock).mockResolvedValueOnce(['summarize.md']);
    (fs.readFile as jest.Mock).mockResolvedValueOnce(`---\nlabel: Summarize\n---\n\nDo it.\n`);
    const result = await readSkillPrompts('knowledge');
    expect(result[0].id).toBe('summarize');
  });

  it('humanizes id when label missing', async () => {
    (fs.readdir as jest.Mock).mockResolvedValueOnce(['agentic-search.md']);
    (fs.readFile as jest.Mock).mockResolvedValueOnce(`Search for: x`);
    const result = await readSkillPrompts('knowledge');
    expect(result[0].label).toBe('Agentic Search');
  });

  it('builds command invocation as /<id>', async () => {
    (fs.readdir as jest.Mock).mockResolvedValueOnce(['refresh.md']);
    (fs.readFile as jest.Mock).mockResolvedValueOnce(`---\nid: refresh\n---\nRefresh the data.`);
    const result = await readSkillCommands('knowledge');
    expect(result[0].command).toBe('/refresh');
  });
});
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/dashboard && npx jest tests/dashboard/server/skillContent.test.ts --no-coverage 2>&1 | tail -10
```

Expected: PASS

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd apps/dashboard && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/lib/server/skillContent.ts apps/dashboard/lib/server/skillsLookup.ts tests/dashboard/server/skillContent.test.ts
git commit -m "feat(browse): scan skill prompts/ and commands/ directories (Agent Skills standard)"
```

---

## Task 3: Print-mode exec store and route

**Files:**
- Create: `apps/dashboard/app/api/cli/exec/exec-store.ts`
- Create: `apps/dashboard/app/api/cli/exec/route.ts`

- [ ] **Step 1: Write failing test**

Create `tests/dashboard/api/exec-route.test.ts`:

```ts
import { POST } from '@/app/api/cli/exec/route';
import { NextRequest } from 'next/server';

jest.mock('@/app/api/cli/cli-config', () => ({
  getCliAgentsConfig: () => ({
    claude: {
      cmd: ['claude'],
      print_cmd: ['claude', '-p', '--output-format', 'stream-json'],
    },
  }),
  AUGUR_ROOT: '/tmp/augur',
  buildCliSpawnEnv: () => ({}),
  resolveSpawnCommand: (cmd: string) => cmd,
  isNonEmptyString: (v: unknown) => typeof v === 'string' && v.length > 0,
}));

jest.mock('@/app/api/cli/pty-setup', () => ({
  pty: {
    spawn: jest.fn(() => ({
      pid: 9999,
      onData: jest.fn(),
      onExit: jest.fn(),
      kill: jest.fn(),
    })),
  },
}));

jest.mock('@/app/api/cli/exec/exec-store', () => ({
  execStore: { set: jest.fn(), get: jest.fn(), delete: jest.fn() },
}));

describe('POST /api/cli/exec', () => {
  it('rejects missing prompt', async () => {
    const req = new NextRequest('http://localhost/api/cli/exec', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    const res = await POST(req);
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toMatch(/prompt/i);
  });

  it('returns execId for valid prompt', async () => {
    const req = new NextRequest('http://localhost/api/cli/exec', {
      method: 'POST',
      body: JSON.stringify({ prompt: 'hello' }),
    });
    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(typeof body.execId).toBe('string');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/dashboard && npx jest tests/dashboard/api/exec-route.test.ts --no-coverage 2>&1 | tail -10
```

Expected: FAIL — `Cannot find module '@/app/api/cli/exec/route'`

- [ ] **Step 3: Create exec-store**

Create `apps/dashboard/app/api/cli/exec/exec-store.ts`:

```ts
export interface ExecEntry {
  prompt: string;
  cliId: string;
  startedAt: number;
  output: string[];      // buffered JSONL lines
  done: boolean;
  answer: string | null;
  sessionId: string | null;
  error: string | null;
}

// Module-level map survives hot reload in dev
const store = new Map<string, ExecEntry>();

export const execStore = {
  set(id: string, entry: ExecEntry): void {
    store.set(id, entry);
  },
  get(id: string): ExecEntry | undefined {
    return store.get(id);
  },
  delete(id: string): void {
    store.delete(id);
  },
};
```

- [ ] **Step 4: Create POST route**

Create `apps/dashboard/app/api/cli/exec/route.ts`:

```ts
import { NextRequest, NextResponse } from 'next/server';
import { randomUUID } from 'crypto';
import { pty } from '@/app/api/cli/pty-setup';
import {
  getCliAgentsConfig,
  buildCliSpawnEnv,
  resolveSpawnCommand,
  AUGUR_ROOT,
} from '@/app/api/cli/cli-config';
import { execStore } from './exec-store';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

function resolveDefaultCliId(): string {
  const agents = getCliAgentsConfig();
  if (agents['claude']) return 'claude';
  return Object.keys(agents)[0] || 'claude';
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const isRemote = request.headers.get('x-remote-user') === 'true';
  if (isRemote) {
    return NextResponse.json({ error: 'Not available for remote users' }, { status: 403 });
  }

  const body = await request.json().catch(() => ({})) as { prompt?: string };
  if (!body.prompt || typeof body.prompt !== 'string' || !body.prompt.trim()) {
    return NextResponse.json({ error: 'prompt is required' }, { status: 400 });
  }

  const cliId = resolveDefaultCliId();
  const agents = getCliAgentsConfig();
  const config = agents[cliId];
  const printArgs = config?.print_cmd;
  if (!Array.isArray(printArgs) || printArgs.length === 0) {
    return NextResponse.json(
      { error: `CLI '${cliId}' has no print_cmd (array) configured in cli_agents.yaml` },
      { status: 500 }
    );
  }

  const execId = randomUUID();
  const entry = {
    prompt: body.prompt,
    cliId,
    startedAt: Date.now(),
    output: [] as string[],
    done: false,
    answer: null as string | null,
    sessionId: null as string | null,
    error: null as string | null,
  };
  execStore.set(execId, entry);

  // print_cmd is an array — append the prompt as the final argv entry.
  // No shell interpolation, no quote escaping needed.
  const argv = [...(printArgs as string[]), body.prompt];
  const cmd = resolveSpawnCommand(argv[0]);
  const env = buildCliSpawnEnv(config, undefined, 'dark');
  const cwd = config.cwd === '.' ? AUGUR_ROOT : (config.cwd as string) || AUGUR_ROOT;

  try {
    const proc = pty.spawn(cmd, argv.slice(1), {
      name: 'xterm-256color',
      cols: 200,
      rows: 50,
      cwd,
      env,
    });

    proc.onData((data: string) => {
      const lines = data.split('\n').filter(l => l.trim().startsWith('{'));
      for (const line of lines) {
        entry.output.push(line);
        try {
          const event = JSON.parse(line) as Record<string, unknown>;
          // Claude stream-json: { type: "result", result: "..." }
          if (event.type === 'result' && typeof event.result === 'string') {
            entry.answer = event.result;
          }
          // Codex --json: { type: "turn.completed", content: [{type:"text", text:"..."}] }
          if (event.type === 'turn.completed') {
            const content = (event as { content?: Array<{ type: string; text?: string }> }).content;
            if (Array.isArray(content)) {
              entry.answer = content
                .filter(c => c.type === 'text')
                .map(c => c.text || '')
                .join('');
            }
          }
          // Session ID — both Claude and Gemini emit `session_id` at top level
          if (typeof event.session_id === 'string') {
            entry.sessionId = event.session_id;
          }
        } catch {
          // Non-JSON line — skip
        }
      }
    });

    proc.onExit(({ exitCode }: { exitCode: number }) => {
      entry.done = true;
      if (exitCode !== 0 && !entry.answer) {
        entry.error = `CLI exited with code ${exitCode}`;
      }
    });
  } catch (err) {
    execStore.delete(execId);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Failed to spawn CLI' },
      { status: 500 }
    );
  }

  return NextResponse.json({ execId });
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd apps/dashboard && npx jest tests/dashboard/api/exec-route.test.ts --no-coverage 2>&1 | tail -10
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/app/api/cli/exec/ tests/dashboard/api/exec-route.test.ts
git commit -m "feat(api): add /api/cli/exec print-mode execution route"
```

---

## Task 4: SSE stream route for exec results

**Files:**
- Create: `apps/dashboard/app/api/cli/exec/stream/route.ts`

- [ ] **Step 1: Create SSE stream route**

Create `apps/dashboard/app/api/cli/exec/stream/route.ts`:

```ts
import { NextRequest } from 'next/server';
import { execStore } from '../exec-store';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(request: NextRequest): Promise<Response> {
  const execId = request.nextUrl.searchParams.get('id');
  if (!execId) {
    return new Response('Missing id', { status: 400 });
  }

  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (data: Record<string, unknown>) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
      };

      const POLL_INTERVAL = 100; // ms
      const TIMEOUT = 120_000;   // 2 minutes max
      const start = Date.now();

      const poll = () => {
        const entry = execStore.get(execId);

        if (!entry) {
          send({ type: 'error', error: 'exec not found' });
          controller.close();
          return;
        }

        if (Date.now() - start > TIMEOUT) {
          send({ type: 'error', error: 'timeout' });
          execStore.delete(execId);
          controller.close();
          return;
        }

        if (entry.done) {
          send({
            type: 'done',
            answer: entry.answer ?? '',
            sessionId: entry.sessionId ?? '',
            durationMs: Date.now() - entry.startedAt,
            cliId: entry.cliId,
          });
          execStore.delete(execId);
          controller.close();
          return;
        }

        // Still running — send heartbeat
        send({ type: 'running' });
        setTimeout(poll, POLL_INTERVAL);
      };

      poll();
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  });
}
```

- [ ] **Step 2: Add `print_cmd` (array) to `cli_agents.yaml`**

First, resolve the actual file path:

```bash
python -c "from src.config.paths import get_vault_dir; print(get_vault_dir() / 'ai' / 'cli_agents.yaml')"
```

This prints the absolute path (typically `~/Documents/Au-vault/ai/cli_agents.yaml` or similar). Open that file and, for each agent, add a `print_cmd:` array field. The prompt is appended as the final argv entry by the route — do NOT include `{prompt}` placeholder.

```yaml
agents:
  claude:
    cmd: ["claude", "--dangerously-skip-permissions"]
    print_cmd: ["claude", "-p", "--output-format", "stream-json"]
    # ... rest of existing config untouched

  codex:
    cmd: ["codex"]
    print_cmd: ["codex", "exec", "--json"]
    # ...

  gemini:
    cmd: ["gemini"]
    print_cmd: ["gemini", "--prompt", "--output-format", "stream-json"]
    # ...
```

Add only the `print_cmd:` line per agent — leave all existing fields untouched. The route appends the prompt as the last argv: e.g. `claude -p --output-format stream-json "<prompt>"`.

> **Note for gemini**: `--prompt` expects the prompt as the next arg, which the route's argv-append behavior provides naturally.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/app/api/cli/exec/stream/
git commit -m "feat(api): add SSE stream route for exec results"
```

---

## Task 5: SessionManager

**Files:**
- Create: `apps/dashboard/lib/session/SessionManager.ts`
- Create: `tests/dashboard/session/SessionManager.test.ts`

- [ ] **Step 1: Write failing tests**

Create `tests/dashboard/session/SessionManager.test.ts`:

```ts
import { SessionManager } from '@/lib/session/SessionManager';

jest.mock('@/app/api/cli/cli-config', () => ({
  getCliAgentsConfig: () => ({
    claude: {
      cmd: ['claude'],
      print_cmd: 'claude -p "{prompt}" --output-format stream-json',
      cwd: '.',
    },
  }),
  AUGUR_ROOT: '/tmp',
  buildCliSpawnEnv: () => ({}),
  resolveSpawnCommand: (cmd: string) => cmd,
}));

jest.mock('@/app/api/cli/pty-setup', () => ({
  pty: {
    spawn: jest.fn(() => ({
      pid: 1234,
      onData: jest.fn(),
      onExit: jest.fn(),
      write: jest.fn(),
      kill: jest.fn(),
    })),
  },
}));

jest.mock('fs', () => {
  const actual = jest.requireActual('fs');
  return {
    ...actual,
    existsSync: jest.fn(() => false),
    readFileSync: jest.fn(() => '{}'),
    writeFileSync: jest.fn(),
    mkdirSync: jest.fn(),
  };
});

describe('SessionManager', () => {
  let manager: SessionManager;

  beforeEach(() => {
    manager = new SessionManager();
  });

  it('starts with no active session', () => {
    expect(manager.isRunning()).toBe(false);
  });

  it('saves and reads session ID', () => {
    manager.saveSessionId('abc-123');
    expect(manager.getLastSessionId()).toBe('abc-123');
  });

  it('reports running after initialize', async () => {
    await manager.initialize();
    expect(manager.isRunning()).toBe(true);
  });

  it('detects collision when session is active', async () => {
    await manager.initialize();
    expect(manager.hasActiveConversation()).toBe(false);
    manager.markConversationActive();
    expect(manager.hasActiveConversation()).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/dashboard && npx jest tests/dashboard/session/SessionManager.test.ts --no-coverage 2>&1 | tail -10
```

Expected: FAIL — `Cannot find module '@/lib/session/SessionManager'`

- [ ] **Step 3: Create SessionManager**

Create `apps/dashboard/lib/session/SessionManager.ts`:

```ts
import path from 'path';
import fs from 'fs';
import { pty, type IPtyProcess } from '@/app/api/cli/pty-setup';
import {
  getCliAgentsConfig,
  buildCliSpawnEnv,
  resolveSpawnCommand,
  AUGUR_ROOT,
} from '@/app/api/cli/cli-config';
import { AUGUR_STATE_DIR } from '@/lib/paths';

const SESSION_ID_FILE = path.join(AUGUR_STATE_DIR, 'temp', 'default_cli_session_id.txt');

export class SessionManager {
  private proc: IPtyProcess | null = null;
  private conversationActive = false;
  private _lastSessionId: string | null = null;

  constructor() {
    this._lastSessionId = this.readSessionId();
  }

  isRunning(): boolean {
    return this.proc !== null;
  }

  hasActiveConversation(): boolean {
    return this.conversationActive;
  }

  markConversationActive(): void {
    this.conversationActive = true;
  }

  markConversationIdle(): void {
    this.conversationActive = false;
  }

  getLastSessionId(): string | null {
    return this._lastSessionId;
  }

  saveSessionId(id: string): void {
    this._lastSessionId = id;
    try {
      const dir = path.dirname(SESSION_ID_FILE);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(SESSION_ID_FILE, id, 'utf8');
    } catch {
      // best-effort
    }
  }

  private readSessionId(): string | null {
    try {
      if (fs.existsSync(SESSION_ID_FILE)) {
        return fs.readFileSync(SESSION_ID_FILE, 'utf8').trim() || null;
      }
    } catch {
      // ignore
    }
    return null;
  }

  private resolveDefaultCliId(): string {
    const agents = getCliAgentsConfig();
    if (agents['claude']) return 'claude';
    return Object.keys(agents)[0] || 'claude';
  }

  private buildResumeArgs(cliId: string, config: Record<string, unknown>): string[] {
    const base = [...(config.cmd as string[])];
    const lastId = this._lastSessionId;

    if (!lastId) return base;

    // Preserve config.cmd binary + any flags; append resume idiom per CLI.
    switch (cliId) {
      case 'claude':
        return [...base, '--resume', lastId];
      case 'codex':
        // codex resume is a subcommand: <binary> resume <id>
        // Preserve any flags from base after position 0 by inserting "resume" + id
        return [base[0], 'resume', lastId, ...base.slice(1)];
      case 'gemini':
        return [...base, '--resume', lastId];
      default:
        return base;
    }
  }

  async initialize(): Promise<void> {
    if (this.proc) return;

    const cliId = this.resolveDefaultCliId();
    const agents = getCliAgentsConfig();
    const config = agents[cliId];
    if (!config) throw new Error(`No config for CLI '${cliId}'`);

    const args = this.buildResumeArgs(cliId, config as Record<string, unknown>);
    const cmd = resolveSpawnCommand(args[0]);
    const env = buildCliSpawnEnv(config as Record<string, unknown>);
    const cwd = (config.cwd as string) === '.' ? AUGUR_ROOT : (config.cwd as string) || AUGUR_ROOT;

    this.proc = pty.spawn(cmd, args.slice(1), {
      name: 'xterm-256color',
      cols: 220,
      rows: 50,
      cwd,
      env,
    });

    this.proc.onExit(() => {
      this.proc = null;
      this.conversationActive = false;
    });
  }

  sendMessage(text: string): void {
    if (!this.proc) throw new Error('Session not running');
    this.proc.write(text + '\r');
    this.conversationActive = true;
  }

  terminate(): void {
    if (!this.proc) return;
    try { this.proc.kill(); } catch { /* ignore */ }
    this.proc = null;
    this.conversationActive = false;
  }
}

// Module-level singleton — persists across Next.js requests in same process
let _instance: SessionManager | null = null;

export function getSessionManager(): SessionManager {
  if (!_instance) _instance = new SessionManager();
  return _instance;
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/dashboard && npx jest tests/dashboard/session/SessionManager.test.ts --no-coverage 2>&1 | tail -10
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/session/ tests/dashboard/session/
git commit -m "feat(session): add SessionManager with pre-warm and resume chain"
```

---

## Task 6: ResultCard component

**Files:**
- Create: `apps/dashboard/components/browse/ResultCard.tsx`
- Create: `tests/dashboard/browse/ResultCard.test.tsx`

- [ ] **Step 1: Write failing test**

Create `tests/dashboard/browse/ResultCard.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { ResultCard } from '@/components/browse/ResultCard';
import type { PromptResult } from '@/lib/browse/types';

const mockResult: PromptResult = {
  promptId: 'test-prompt',
  input: 'Search for knowledge management',
  answer: '## Results\n\nFound 3 relevant items.',
  sessionId: 'sess-abc123',
  cliId: 'claude',
  durationMs: 2400,
  timestamp: new Date('2026-04-20T10:00:00Z'),
};

describe('ResultCard', () => {
  it('renders the answer as markdown', () => {
    render(<ResultCard result={mockResult} onContinueInSession={jest.fn()} />);
    expect(screen.getByText('Results')).toBeInTheDocument();
    expect(screen.getByText(/Found 3 relevant items/)).toBeInTheDocument();
  });

  it('shows duration', () => {
    render(<ResultCard result={mockResult} onContinueInSession={jest.fn()} />);
    expect(screen.getByText(/2\.4s/)).toBeInTheDocument();
  });

  it('calls onContinueInSession with sessionId on click', () => {
    const onContinue = jest.fn();
    render(<ResultCard result={mockResult} onContinueInSession={onContinue} />);
    fireEvent.click(screen.getByText(/Continue in session/));
    expect(onContinue).toHaveBeenCalledWith('sess-abc123');
  });

  it('copy button copies answer to clipboard', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
    });
    render(<ResultCard result={mockResult} onContinueInSession={jest.fn()} />);
    fireEvent.click(screen.getByLabelText('Copy result'));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(mockResult.answer);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/dashboard && npx jest tests/dashboard/browse/ResultCard.test.tsx --no-coverage 2>&1 | tail -10
```

Expected: FAIL — `Cannot find module '@/components/browse/ResultCard'`

- [ ] **Step 3: Create ResultCard**

Create `apps/dashboard/components/browse/ResultCard.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { Copy, Check, ExternalLink } from 'lucide-react';
import Markdown from '@/components/Markdown';
import type { PromptResult } from '@/lib/browse/types';

interface ResultCardProps {
  result: PromptResult;
  onContinueInSession: (sessionId: string) => void;
}

export function ResultCard({ result, onContinueInSession }: ResultCardProps) {
  const [copied, setCopied] = useState(false);
  const durationSec = (result.durationMs / 1000).toFixed(1);

  async function handleCopy() {
    await navigator.clipboard.writeText(result.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div
      className="mt-3 rounded-lg border p-4 space-y-3"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}
    >
      <div className="flex items-center justify-between text-xs" style={{ color: 'var(--text-muted)' }}>
        <span>Result · {durationSec}s · {result.cliId}</span>
        <button
          onClick={handleCopy}
          aria-label="Copy result"
          className="hover:text-[var(--text-primary)] transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>

      <div className="prose prose-sm max-w-none text-sm" style={{ color: 'var(--text-primary)' }}>
        <Markdown>{result.answer}</Markdown>
      </div>

      {result.sessionId && (
        <button
          onClick={() => onContinueInSession(result.sessionId)}
          className="flex items-center gap-1.5 text-xs hover:underline"
          style={{ color: 'var(--accent-primary)' }}
        >
          <ExternalLink className="w-3 h-3" />
          Continue in session
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/dashboard && npx jest tests/dashboard/browse/ResultCard.test.tsx --no-coverage 2>&1 | tail -10
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/browse/ResultCard.tsx tests/dashboard/browse/ResultCard.test.tsx
git commit -m "feat(browse): add ResultCard component with markdown, duration, and continue-in-session"
```

---

## Task 7: PromptCard component

**Files:**
- Create: `apps/dashboard/components/browse/PromptCard.tsx`
- Create: `tests/dashboard/browse/PromptCard.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `tests/dashboard/browse/PromptCard.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PromptCard } from '@/components/browse/PromptCard';
import type { SkillPrompt } from '@/lib/browse/types';

global.fetch = jest.fn();

const promptNoVar: SkillPrompt = {
  id: 'summarize',
  label: 'Summarize Recent',
  description: 'Summarize last 7 days',
  prompt: 'Summarize my last 7 days of activity',
  icon: 'FileText',
};

const promptWithVar: SkillPrompt = {
  id: 'search',
  label: 'Search',
  description: 'Search knowledge base',
  prompt: 'Search for: {{query}}',
  icon: 'Search',
};

describe('PromptCard', () => {
  beforeEach(() => {
    (fetch as jest.Mock).mockReset();
  });

  it('renders label and description', () => {
    render(<PromptCard prompt={promptNoVar} onResult={jest.fn()} />);
    expect(screen.getByText('Summarize Recent')).toBeInTheDocument();
    expect(screen.getByText('Summarize last 7 days')).toBeInTheDocument();
  });

  it('shows Run button directly for prompt without {{var}}', () => {
    render(<PromptCard prompt={promptNoVar} onResult={jest.fn()} />);
    expect(screen.getByRole('button', { name: /run/i })).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('shows input field for prompt with {{var}}', () => {
    render(<PromptCard prompt={promptWithVar} onResult={jest.fn()} />);
    expect(screen.getByPlaceholderText('query')).toBeInTheDocument();
  });

  it('renders one input per unique {{var}}', () => {
    const multiVar: SkillPrompt = {
      id: 'multi',
      label: 'Multi',
      prompt: 'Compare {{a}} and {{b}}',
    };
    render(<PromptCard prompt={multiVar} onResult={jest.fn()} />);
    expect(screen.getByPlaceholderText('a')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('b')).toBeInTheDocument();
  });

  it('calls fetch with resolved prompt on run', async () => {
    const mockEventSource = { addEventListener: jest.fn(), close: jest.fn() };
    (global as unknown as { EventSource: unknown }).EventSource = jest.fn(() => mockEventSource);

    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ execId: 'exec-123' }),
    });

    render(<PromptCard prompt={promptWithVar} onResult={jest.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('query'), { target: { value: 'test query' } });
    fireEvent.click(screen.getByRole('button', { name: /run/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/cli/exec',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ prompt: 'Search for: test query' }),
        })
      );
    });
  });

  it('disables Run button while executing', async () => {
    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ execId: 'exec-456' }),
    });
    const mockEventSource = { addEventListener: jest.fn(), close: jest.fn() };
    (global as unknown as { EventSource: unknown }).EventSource = jest.fn(() => mockEventSource);

    render(<PromptCard prompt={promptNoVar} onResult={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /run/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /run/i })).toBeDisabled();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/dashboard && npx jest tests/dashboard/browse/PromptCard.test.tsx --no-coverage 2>&1 | tail -10
```

Expected: FAIL — `Cannot find module '@/components/browse/PromptCard'`

- [ ] **Step 3: Create PromptCard**

Create `apps/dashboard/components/browse/PromptCard.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { Play, Loader2, MessageSquare } from 'lucide-react';
import { resolveIcon } from '@/lib/icon-map';
import { ResultCard } from './ResultCard';
import type { SkillPrompt, PromptResult } from '@/lib/browse/types';

const VAR_PATTERN = /\{\{(\w+)\}\}/g;

/** Extract all unique var names from a prompt template. */
function extractVarNames(template: string): string[] {
  const names = new Set<string>();
  let m: RegExpExecArray | null;
  const re = new RegExp(VAR_PATTERN.source, 'g');
  while ((m = re.exec(template)) !== null) names.add(m[1]);
  return Array.from(names);
}

/** Replace each {{name}} with the corresponding input value. */
function resolvePrompt(template: string, inputs: Record<string, string>): string {
  return template.replace(VAR_PATTERN, (_match, name: string) => inputs[name] ?? '');
}

interface PromptCardProps {
  prompt: SkillPrompt;
  onResult: (result: PromptResult) => void;
}

export function PromptCard({ prompt, onResult }: PromptCardProps) {
  const varNames = extractVarNames(prompt.prompt);
  const [inputs, setInputs] = useState<Record<string, string>>(
    Object.fromEntries(varNames.map(n => [n, '']))
  );
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<PromptResult | null>(null);
  const Icon = resolveIcon(prompt.icon, MessageSquare);
  const allInputsFilled = varNames.every(n => (inputs[n] ?? '').trim().length > 0);

  function handleContinueInSession(sessionId: string) {
    // Dispatch to chat panel — SessionManager handles routing
    window.dispatchEvent(new CustomEvent('augur:continue-in-session', {
      detail: { sessionId, answer: result?.answer ?? '' },
    }));
  }

  async function handleRun() {
    if (executing) return;
    if (varNames.length > 0 && !allInputsFilled) return;

    const trimmed: Record<string, string> = Object.fromEntries(
      Object.entries(inputs).map(([k, v]) => [k, v.trim()])
    );
    const resolvedPrompt =
      varNames.length > 0 ? resolvePrompt(prompt.prompt, trimmed) : prompt.prompt;
    setExecuting(true);
    setResult(null);

    try {
      const res = await fetch('/api/cli/exec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: resolvedPrompt }),
      });

      if (!res.ok) {
        const err = await res.json() as { error?: string };
        throw new Error(err.error || 'Execution failed');
      }

      const { execId } = await res.json() as { execId: string };

      await new Promise<void>((resolve, reject) => {
        const es = new EventSource(`/api/cli/exec/stream?id=${execId}`);
        es.addEventListener('message', (e) => {
          const data = JSON.parse(e.data) as {
            type: string;
            answer?: string;
            sessionId?: string;
            durationMs?: number;
            cliId?: string;
            error?: string;
          };
          if (data.type === 'done') {
            const promptResult: PromptResult = {
              promptId: prompt.id,
              input: resolvedPrompt,
              answer: data.answer ?? '',
              sessionId: data.sessionId ?? '',
              cliId: data.cliId ?? 'claude',
              durationMs: data.durationMs ?? 0,
              timestamp: new Date(),
            };
            setResult(promptResult);
            onResult(promptResult);
            es.close();
            resolve();
          } else if (data.type === 'error') {
            es.close();
            reject(new Error(data.error ?? 'Stream error'));
          }
        });
        es.onerror = () => { es.close(); reject(new Error('SSE connection failed')); };
      });
    } catch {
      // Error shown via toast in a real implementation — keep card clean
    } finally {
      setExecuting(false);
    }
  }

  return (
    <div
      className="rounded-lg border p-4 space-y-3"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 shrink-0" style={{ color: 'var(--accent-primary)' }} />
          <div>
            <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              {prompt.label}
            </div>
            {prompt.description && (
              <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {prompt.description}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-2">
        {varNames.map(name => (
          <input
            key={name}
            type="text"
            value={inputs[name] ?? ''}
            onChange={e => setInputs(prev => ({ ...prev, [name]: e.target.value }))}
            onKeyDown={e => e.key === 'Enter' && allInputsFilled && handleRun()}
            placeholder={name}
            disabled={executing}
            className="w-full rounded-md border px-3 py-1.5 text-sm disabled:opacity-50"
            style={{
              background: 'var(--bg-input)',
              borderColor: 'var(--border-color)',
              color: 'var(--text-primary)',
            }}
          />
        ))}
        <button
          onClick={handleRun}
          disabled={executing || (varNames.length > 0 && !allInputsFilled)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors disabled:opacity-50"
          style={{ background: 'var(--accent-primary)', color: 'white' }}
        >
          {executing
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Play className="w-3.5 h-3.5" />}
          Run
        </button>
      </div>

      {result && (
        <ResultCard result={result} onContinueInSession={handleContinueInSession} />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/dashboard && npx jest tests/dashboard/browse/PromptCard.test.tsx --no-coverage 2>&1 | tail -10
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/browse/PromptCard.tsx tests/dashboard/browse/PromptCard.test.tsx
git commit -m "feat(browse): add PromptCard with inline input, exec integration, and ResultCard"
```

---

## Task 8: CommandCard and IntegrationTab components

**Files:**
- Create: `apps/dashboard/components/browse/CommandCard.tsx`
- Create: `apps/dashboard/components/browse/IntegrationTab.tsx`

- [ ] **Step 1: Create CommandCard**

Create `apps/dashboard/components/browse/CommandCard.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { Terminal, Play, Loader2 } from 'lucide-react';
import { resolveIcon } from '@/lib/icon-map';
import { ResultCard } from './ResultCard';
import type { SkillCommand, PromptResult } from '@/lib/browse/types';

interface CommandCardProps {
  command: SkillCommand;
  onResult: (result: PromptResult) => void;
}

export function CommandCard({ command, onResult }: CommandCardProps) {
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<PromptResult | null>(null);
  const Icon = resolveIcon(command.icon, Terminal);

  function handleContinueInSession(sessionId: string) {
    window.dispatchEvent(new CustomEvent('augur:continue-in-session', {
      detail: { sessionId, answer: result?.answer ?? '' },
    }));
  }

  async function handleRun() {
    if (executing) return;
    setExecuting(true);
    setResult(null);

    try {
      const res = await fetch('/api/cli/exec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: command.command }),
      });

      if (!res.ok) throw new Error('Command execution failed');
      const { execId } = await res.json() as { execId: string };

      await new Promise<void>((resolve, reject) => {
        const es = new EventSource(`/api/cli/exec/stream?id=${execId}`);
        es.addEventListener('message', (e) => {
          const data = JSON.parse(e.data) as {
            type: string;
            answer?: string;
            sessionId?: string;
            durationMs?: number;
            cliId?: string;
            error?: string;
          };
          if (data.type === 'done') {
            const promptResult: PromptResult = {
              promptId: command.id,
              input: command.command,
              answer: data.answer ?? '',
              sessionId: data.sessionId ?? '',
              cliId: data.cliId ?? 'claude',
              durationMs: data.durationMs ?? 0,
              timestamp: new Date(),
            };
            setResult(promptResult);
            onResult(promptResult);
            es.close();
            resolve();
          } else if (data.type === 'error') {
            es.close();
            reject(new Error(data.error));
          }
        });
        es.onerror = () => { es.close(); reject(new Error('SSE failed')); };
      });
    } catch {
      // silent — keep card clean
    } finally {
      setExecuting(false);
    }
  }

  return (
    <div
      className="rounded-lg border p-4 space-y-3"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 shrink-0" style={{ color: 'var(--accent-primary)' }} />
          <div>
            <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              {command.label}
            </div>
            <div className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>
              {command.command}
            </div>
          </div>
        </div>
        <button
          onClick={handleRun}
          disabled={executing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors disabled:opacity-50 shrink-0"
          style={{ background: 'var(--accent-primary)', color: 'white' }}
        >
          {executing
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Play className="w-3.5 h-3.5" />}
          Run
        </button>
      </div>
      {result && (
        <ResultCard result={result} onContinueInSession={handleContinueInSession} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create IntegrationTab**

Create `apps/dashboard/components/browse/IntegrationTab.tsx`:

```tsx
'use client';

import { useMcpQuery } from '@/lib/mcp/useMcpQuery';

interface IntegrationTabProps {
  skillId: string;
}

export function IntegrationTab({ skillId }: IntegrationTabProps) {
  const { data, loading, error } = useMcpQuery<{ output: string; default_cli: string }>(
    ['cli-help', skillId],
    'get-skill-cli-help',
    'realtime',
    { args: { skill_id: skillId } }
  );

  if (loading) {
    return (
      <div className="text-sm py-4" style={{ color: 'var(--text-muted)' }}>
        Loading CLI reference…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-sm py-4" style={{ color: 'var(--text-muted)' }}>
        No CLI reference available for this skill.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
        Default CLI: <span className="font-mono">{data.default_cli}</span>
      </div>
      <pre
        className="rounded-lg p-4 text-xs font-mono overflow-x-auto leading-relaxed"
        style={{ background: 'var(--bg-inset)', color: 'var(--text-primary)' }}
      >
        {data.output}
      </pre>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard && npx tsc --noEmit 2>&1 | grep -E "error TS" | head -20
```

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/components/browse/CommandCard.tsx apps/dashboard/components/browse/IntegrationTab.tsx
git commit -m "feat(browse): add CommandCard and IntegrationTab components"
```

---

## Task 9: SkillDetailTabs and browse page wiring

**Files:**
- Create: `apps/dashboard/components/browse/SkillDetailTabs.tsx`
- Modify: `apps/dashboard/app/(views)/browse/[skill]/page.tsx`

- [ ] **Step 1: Create SkillDetailTabs**

Create `apps/dashboard/components/browse/SkillDetailTabs.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { PromptCard } from './PromptCard';
import { CommandCard } from './CommandCard';
import { IntegrationTab } from './IntegrationTab';
import type { SkillPrompt, SkillCommand, PromptResult } from '@/lib/browse/types';

type Tab = 'overview' | 'prompts' | 'commands' | 'integration';

interface SkillDetailTabsProps {
  skillId: string;
  overviewContent: React.ReactNode;
  prompts: SkillPrompt[];
  commands: SkillCommand[];
}

const TAB_LABELS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'prompts', label: 'Prompts' },
  { id: 'commands', label: 'Commands' },
  { id: 'integration', label: 'Integration' },
];

export function SkillDetailTabs({ skillId, overviewContent, prompts, commands }: SkillDetailTabsProps) {
  const defaultTab: Tab =
    prompts.length > 0 ? 'prompts'
    : commands.length > 0 ? 'commands'
    : 'overview';

  const [active, setActive] = useState<Tab>(defaultTab);

  function handleResult(_result: PromptResult) {
    // Results render inline in the cards — nothing to do at tab level
  }

  const visibleTabs = TAB_LABELS.filter(t => {
    if (t.id === 'prompts' && prompts.length === 0) return false;
    if (t.id === 'commands' && commands.length === 0) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b" style={{ borderColor: 'var(--border-color)' }}>
        {visibleTabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px"
            style={{
              borderBottomColor: active === tab.id ? 'var(--accent-primary)' : 'transparent',
              color: active === tab.id ? 'var(--accent-primary)' : 'var(--text-muted)',
            }}
          >
            {tab.label}
            {tab.id === 'prompts' && prompts.length > 0 && (
              <span className="ml-1.5 text-xs opacity-60">({prompts.length})</span>
            )}
            {tab.id === 'commands' && commands.length > 0 && (
              <span className="ml-1.5 text-xs opacity-60">({commands.length})</span>
            )}
          </button>
        ))}
      </div>

      {active === 'overview' && overviewContent}

      {active === 'prompts' && (
        <div className="space-y-3">
          {prompts.map(p => (
            <PromptCard key={p.id} prompt={p} onResult={handleResult} />
          ))}
        </div>
      )}

      {active === 'commands' && (
        <div className="space-y-3">
          {commands.map(c => (
            <CommandCard key={c.id} command={c} onResult={handleResult} />
          ))}
        </div>
      )}

      {active === 'integration' && <IntegrationTab skillId={skillId} />}
    </div>
  );
}
```

- [ ] **Step 2: Update browse skill page to use SkillDetailTabs**

Open `apps/dashboard/app/(views)/browse/[skill]/page.tsx`. Replace the `return (...)` block with:

```tsx
  const prompts = (meta?.prompts ?? []) as import('@/lib/browse/types').SkillPrompt[];
  const commands = (meta?.commands ?? []) as import('@/lib/browse/types').SkillCommand[];

  return (
    <div className="space-y-6">
      <header className="space-y-4">
        <nav className="flex items-center gap-3 text-sm flex-wrap">
          <Link href="/browse">
            <Button variant="outline" size="sm" className="h-8">
              <ArrowLeft className="w-4 h-4 mr-1" />
              Browse
            </Button>
          </Link>
          {hubId && hubLabel && (
            <>
              <span className="text-[var(--text-muted)]">/</span>
              <Link
                href={`/${hubId}`}
                className="text-[var(--accent-primary)] hover:underline"
                title={`Go to ${hubLabel} hub`}
              >
                {hubLabel}
              </Link>
            </>
          )}
          <span className="text-[var(--text-muted)]">/</span>
          <span className="text-[var(--text-muted)]">{normalizedCanonical}</span>
        </nav>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" size="md" title={`Canonical ID: ${normalizedCanonical}`}>
            ID: {normalizedCanonical}
          </Badge>
          {hubId && (
            <Badge variant="outline" size="md" title={`Part of ${hubLabel} hub`}>
              Hub: {hubLabel}
            </Badge>
          )}
        </div>
      </header>

      <SkillDetailTabs
        skillId={normalizedCanonical}
        prompts={prompts}
        commands={commands}
        overviewContent={<ConfigPage config={config} skillId={normalizedCanonical} />}
      />
    </div>
  );
```

Add import at top of the file:

```ts
import { SkillDetailTabs } from '@/components/browse/SkillDetailTabs';
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard && npx tsc --noEmit 2>&1 | grep -E "error TS" | head -20
```

Expected: no new errors

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/components/browse/SkillDetailTabs.tsx apps/dashboard/app/(views)/browse/[skill]/page.tsx
git commit -m "feat(browse): add SkillDetailTabs with Prompts/Commands/Integration tabs"
```

---

## Task 10: "Continue in session" route, listener, and collision toast

**Files:**
- Create: `apps/dashboard/app/api/session/continue/route.ts`
- Create: `apps/dashboard/components/session/ContinueInSessionListener.tsx`
- Modify: `apps/dashboard/app/layout.tsx` (mount the listener)
- Create: `tests/dashboard/api/continue-route.test.ts`

`PromptCard` / `CommandCard` dispatch a `augur:continue-in-session` window event. The listener component (mounted globally in the root layout) consumes the event, POSTs to the API, handles collision via toast, opens the chat panel via `chatStore`.

- [ ] **Step 1: Write failing test for the route**

Create `tests/dashboard/api/continue-route.test.ts`:

```ts
import { POST } from '@/app/api/session/continue/route';
import { NextRequest } from 'next/server';

const mockManager = {
  hasActiveConversation: jest.fn(() => false),
  isRunning: jest.fn(() => false),
  initialize: jest.fn().mockResolvedValue(undefined),
  saveSessionId: jest.fn(),
  sendMessage: jest.fn(),
};

jest.mock('@/lib/session/SessionManager', () => ({
  getSessionManager: () => mockManager,
}));

describe('POST /api/session/continue', () => {
  beforeEach(() => {
    Object.values(mockManager).forEach(fn => (fn as jest.Mock).mockClear?.());
    mockManager.hasActiveConversation.mockReturnValue(false);
    mockManager.isRunning.mockReturnValue(false);
  });

  it('returns collision when conversation is active', async () => {
    mockManager.hasActiveConversation.mockReturnValue(true);
    const req = new NextRequest('http://localhost/api/session/continue', {
      method: 'POST',
      body: JSON.stringify({ sessionId: 'x', answer: 'y' }),
    });
    const res = await POST(req);
    const body = await res.json();
    expect(body.collision).toBe(true);
  });

  it('initializes session and sends context when idle', async () => {
    const req = new NextRequest('http://localhost/api/session/continue', {
      method: 'POST',
      body: JSON.stringify({ sessionId: 'sess-1', answer: 'prior result' }),
    });
    const res = await POST(req);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(mockManager.saveSessionId).toHaveBeenCalledWith('sess-1');
    expect(mockManager.initialize).toHaveBeenCalled();
    expect(mockManager.sendMessage).toHaveBeenCalledWith(
      expect.stringContaining('prior result')
    );
  });

  it('replaces session when force=true even if active', async () => {
    mockManager.hasActiveConversation.mockReturnValue(true);
    mockManager.isRunning.mockReturnValue(true);
    const req = new NextRequest('http://localhost/api/session/continue', {
      method: 'POST',
      body: JSON.stringify({ sessionId: 'x', answer: 'y', force: true }),
    });
    const res = await POST(req);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(mockManager.sendMessage).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/dashboard && npx jest tests/dashboard/api/continue-route.test.ts --no-coverage 2>&1 | tail -10
```

Expected: FAIL — `Cannot find module '@/app/api/session/continue/route'`

- [ ] **Step 3: Create the continue-in-session route**

Create `apps/dashboard/app/api/session/continue/route.ts`:

```ts
import { NextRequest, NextResponse } from 'next/server';
import { getSessionManager } from '@/lib/session/SessionManager';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(request: NextRequest): Promise<NextResponse> {
  const body = await request.json().catch(() => ({})) as {
    sessionId?: string;
    answer?: string;
    force?: boolean;
  };

  const manager = getSessionManager();

  // Collision: client must explicitly opt to replace
  if (manager.hasActiveConversation() && !body.force) {
    return NextResponse.json({
      collision: true,
      message: 'Session already active',
    });
  }

  if (!manager.isRunning()) {
    if (body.sessionId) manager.saveSessionId(body.sessionId);
    await manager.initialize();
  }

  if (body.answer) {
    const contextMessage = `Previous result:\n${body.answer}\n\nContinue from here.`;
    manager.sendMessage(contextMessage);
  }

  return NextResponse.json({ ok: true });
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd apps/dashboard && npx jest tests/dashboard/api/continue-route.test.ts --no-coverage 2>&1 | tail -10
```

Expected: PASS

- [ ] **Step 5: Create the global listener component**

Create `apps/dashboard/components/session/ContinueInSessionListener.tsx`:

```tsx
'use client';

import { useEffect } from 'react';
import { toast } from 'sonner';
import { useChatStore } from '@/lib/stores/chatStore';

interface EventDetail {
  sessionId: string;
  answer: string;
}

export function ContinueInSessionListener(): null {
  const chatStore = useChatStore();

  useEffect(() => {
    async function postContinue(detail: EventDetail, force: boolean) {
      const res = await fetch('/api/session/continue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...detail, force }),
      });
      const data = await res.json() as { ok?: boolean; collision?: boolean };

      if (data.collision) {
        toast.warning('Session already active', {
          action: {
            label: 'Replace with new',
            onClick: () => postContinue(detail, true),
          },
          cancel: {
            label: 'View current',
            onClick: () => {
              chatStore.openChat({ mode: 'ide' });
              if (!chatStore.isEnlarged) chatStore.toggleEnlarged();
            },
          },
        });
        return;
      }

      if (data.ok) {
        chatStore.openChat({ mode: 'ide' });
        if (!chatStore.isEnlarged) chatStore.toggleEnlarged();
      }
    }

    function handler(e: Event) {
      const ce = e as CustomEvent<EventDetail>;
      if (!ce.detail?.sessionId) return;
      void postContinue(ce.detail, false);
    }

    window.addEventListener('augur:continue-in-session', handler);
    return () => window.removeEventListener('augur:continue-in-session', handler);
  }, [chatStore]);

  return null;
}
```

- [ ] **Step 6: Mount listener in root layout**

Open `apps/dashboard/app/layout.tsx`. Inside the body's outermost client-providers wrapper (next to other global UI components like Toaster), add:

```tsx
import { ContinueInSessionListener } from '@/components/session/ContinueInSessionListener';

// inside the JSX body, alongside <Toaster /> or similar global components:
<ContinueInSessionListener />
```

If `layout.tsx` is a server component, mount the listener inside the existing client-providers wrapper instead (it must be in a `'use client'` boundary).

- [ ] **Step 7: Verify TypeScript compiles**

```bash
cd apps/dashboard && npx tsc --noEmit 2>&1 | grep "error TS" | head -10
```

- [ ] **Step 8: Commit**

```bash
git add apps/dashboard/app/api/session/ apps/dashboard/components/session/ apps/dashboard/app/layout.tsx tests/dashboard/api/continue-route.test.ts
git commit -m "feat(session): continue-in-session route + global listener with collision toast"
```

---

## Task 11: Pre-warm SessionManager on dashboard load

**Files:**
- Create: `apps/dashboard/app/api/session/init/route.ts`
- Create: `apps/dashboard/components/session/SessionPrewarmer.tsx`
- Modify: `apps/dashboard/app/layout.tsx` (mount the prewarmer)

The spec requires the default CLI session to be pre-warmed when the dashboard loads. Without this, the first "Continue in session" click pays the cold-start cost — defeating the design. We add a tiny `/api/session/init` route and a client component that fires it once on mount.

- [ ] **Step 1: Create init route**

Create `apps/dashboard/app/api/session/init/route.ts`:

```ts
import { NextResponse } from 'next/server';
import { getSessionManager } from '@/lib/session/SessionManager';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(): Promise<NextResponse> {
  const manager = getSessionManager();
  if (manager.isRunning()) {
    return NextResponse.json({ ok: true, alreadyRunning: true });
  }
  try {
    await manager.initialize();
    return NextResponse.json({ ok: true, lastSessionId: manager.getLastSessionId() });
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: err instanceof Error ? err.message : 'init failed' },
      { status: 500 }
    );
  }
}
```

- [ ] **Step 2: Create SessionPrewarmer client component**

Create `apps/dashboard/components/session/SessionPrewarmer.tsx`:

```tsx
'use client';

import { useEffect, useRef } from 'react';

export function SessionPrewarmer(): null {
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;

    // Fire-and-forget — pre-warm is best-effort, never blocks UI.
    fetch('/api/session/init', { method: 'POST' }).catch(() => {
      // silent — Continue-in-session will lazy-init on demand
    });
  }, []);

  return null;
}
```

- [ ] **Step 3: Mount prewarmer in root layout**

Open `apps/dashboard/app/layout.tsx`. Add alongside `ContinueInSessionListener` from Task 10:

```tsx
import { SessionPrewarmer } from '@/components/session/SessionPrewarmer';

// Inside the client-providers wrapper, next to ContinueInSessionListener:
<SessionPrewarmer />
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd apps/dashboard && npx tsc --noEmit 2>&1 | grep "error TS" | head -10
```

- [ ] **Step 5: Manual verification**

Start the dashboard with `/dev-build`, open in browser, then check the Network tab for a `POST /api/session/init` call within 1 second of page load returning `{ ok: true }`.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/app/api/session/init/ apps/dashboard/components/session/SessionPrewarmer.tsx apps/dashboard/app/layout.tsx
git commit -m "feat(session): pre-warm default CLI on dashboard load"
```

---

## Task 12: Migration script

**Files:**
- Create: `scripts/migrate_actions_to_prompts.py`

Creates `skills/<skill>/prompts/<id>.md` files (for oneshot/ide/chat/auto actions) and `skills/<skill>/commands/<id>.md` files (for fire actions, only when the file doesn't already exist). Removes migrated actions from `actions:` in SKILL.md, keeping only `dispatch: modal` exceptions.

- [ ] **Step 1: Create migration script**

Create `scripts/migrate_actions_to_prompts.py`:

```python
#!/usr/bin/env python3
"""
Migrate SKILL.md files: convert actions: to skills/<skill>/prompts/ and commands/ files.

dispatch: oneshot|ide|chat|auto  -> skills/<skill>/prompts/<id>.md  (new file)
dispatch: fire                   -> skills/<skill>/commands/<id>.md (only if file absent)
dispatch: modal                  -> stays in actions: (logged as exception)

SKILL.md is modified only to remove migrated actions from actions:.
No prompts: or commands: keys are added to SKILL.md frontmatter.

Usage:
  python scripts/migrate_actions_to_prompts.py --dry-run   # preview diffs
  python scripts/migrate_actions_to_prompts.py             # apply changes
"""
import argparse
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

PROMPTS_DISPATCHES = {"oneshot", "ide", "chat", "auto"}
COMMANDS_DISPATCHES = {"fire"}
MODAL_DISPATCHES = {"modal"}


def load_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.index("---", 3)
    fm_text = text[3:end].strip()
    body = text[end + 3:].lstrip("\n")
    return yaml.safe_load(fm_text) or {}, body


def dump_frontmatter(data: dict, body: str) -> str:
    fm = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{fm}---\n\n{body}"


def make_prompt_file(action: dict) -> str:
    """Render a prompts/<id>.md file for an action."""
    meta: dict = {}
    if action.get("id"):
        meta["id"] = action["id"]
    if action.get("label"):
        meta["label"] = action["label"]
    if action.get("description"):
        meta["description"] = action["description"]
    if action.get("icon"):
        meta["icon"] = action["icon"]
    fm = yaml.dump(meta, allow_unicode=True, sort_keys=False, default_flow_style=False)
    body = action.get("prompt") or f"Run: {action.get('label', action.get('id', ''))}"
    return f"---\n{fm}---\n\n{body}\n"


def make_command_file(action: dict) -> str:
    """Render a commands/<id>.md file for an action."""
    meta: dict = {}
    if action.get("id"):
        meta["id"] = action["id"]
    if action.get("label"):
        meta["label"] = action["label"]
    if action.get("description"):
        meta["description"] = action["description"]
    if action.get("icon"):
        meta["icon"] = action["icon"]
    fm = yaml.dump(meta, allow_unicode=True, sort_keys=False, default_flow_style=False)
    body = action.get("command") or f"/{action.get('id', '').replace('-', ' ')}"
    return f"---\n{fm}---\n\n{body}\n"


def migrate_skill(skill_md: Path, dry_run: bool) -> bool:
    """Returns True if file was (or would be) changed."""
    text = skill_md.read_text(encoding="utf-8")
    data, body = load_frontmatter(text)

    actions = data.get("actions", []) or []
    if not actions:
        return False

    skill_dir = skill_md.parent
    prompts_dir = skill_dir / "prompts"
    commands_dir = skill_dir / "commands"

    remaining_actions = []
    changed = False

    for action in actions:
        dispatch = action.get("dispatch", "")
        action_id = action.get("id") or "unknown"
        if dispatch in PROMPTS_DISPATCHES:
            dest = prompts_dir / f"{action_id}.md"
            if dry_run:
                print(f"  Would create: {dest.relative_to(REPO_ROOT)}")
            else:
                prompts_dir.mkdir(exist_ok=True)
                dest.write_text(make_prompt_file(action), encoding="utf-8")
                print(f"  Created: {dest.relative_to(REPO_ROOT)}")
            changed = True
        elif dispatch in COMMANDS_DISPATCHES:
            dest = commands_dir / f"{action_id}.md"
            if dest.exists():
                print(f"  Skipped (already exists): {dest.relative_to(REPO_ROOT)}")
            elif dry_run:
                print(f"  Would create: {dest.relative_to(REPO_ROOT)}")
            else:
                commands_dir.mkdir(exist_ok=True)
                dest.write_text(make_command_file(action), encoding="utf-8")
                print(f"  Created: {dest.relative_to(REPO_ROOT)}")
            changed = True
        elif dispatch in MODAL_DISPATCHES:
            remaining_actions.append(action)
            print(f"  EXCEPTION (modal, kept in actions:): {action_id}")
        else:
            remaining_actions.append(action)
            print(f"  WARNING: unknown dispatch '{dispatch}' for action '{action_id}' — kept in actions:")

    if not changed:
        return False

    # Update SKILL.md: remove migrated actions, keep modal exceptions
    if remaining_actions:
        data["actions"] = remaining_actions
    else:
        data.pop("actions", None)

    new_text = dump_frontmatter(data, body)
    if dry_run:
        print(f"  Would update SKILL.md: {skill_md.relative_to(REPO_ROOT)}")
    else:
        skill_md.write_text(new_text, encoding="utf-8")
        print(f"  Updated SKILL.md: {skill_md.relative_to(REPO_ROOT)}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    skill_mds = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    print(f"Scanning {len(skill_mds)} SKILL.md files…\n")

    changed = 0
    for skill_md in skill_mds:
        skill_name = skill_md.parent.name
        print(f"{skill_name}:")
        if migrate_skill(skill_md, args.dry_run):
            changed += 1
        else:
            print("  no actions to migrate")

    verb = "Would change" if args.dry_run else "Changed"
    print(f"\n{verb} {changed}/{len(skill_mds)} files.")
    if args.dry_run:
        print("Run without --dry-run to apply.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run dry-run to preview**

```bash
python scripts/migrate_actions_to_prompts.py --dry-run 2>&1 | head -80
```

Expected: lines like `Would create: skills/knowledge/prompts/search.md` and `Would update SKILL.md:` for each affected skill. Any `EXCEPTION (modal)` lines are skills with modal actions that will stay in `actions:`.

- [ ] **Step 3: Run migration for real**

```bash
python scripts/migrate_actions_to_prompts.py
```

Review output. Each `EXCEPTION (modal, kept in actions:)` line is a skill to manually verify.

- [ ] **Step 4: Spot-check 3 migrated skills**

```bash
ls skills/knowledge/prompts/ skills/career/prompts/ skills/geo/prompts/
head -15 skills/knowledge/prompts/*.md
```

Verify `.md` files exist in `prompts/` directories and their frontmatter contains `id`, `label`, `description`. Verify `actions:` key is gone from the skill's SKILL.md.

```bash
grep "^actions:" skills/knowledge/SKILL.md skills/career/SKILL.md skills/geo/SKILL.md
```

Expected: no output (actions removed from frontmatter).

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_actions_to_prompts.py skills/
git commit -m "feat(migration): convert actions dispatch to prompts/ and commands/ files per Agent Skills standard"
```

---

## Task 13: Cleanup — retire old routes and dispatch paths

**Files:**
- Modify: `apps/dashboard/hooks/useActionRunner.ts` — remove `oneshot`/`ide`/`chat`/`auto` cases for browse paths

> **Note:** Do NOT remove `useActionRunner` entirely — it is still used by hub feature pages (geo, career, websites). Only remove the cases that are now handled by the new browse components.

- [ ] **Step 1: Verify no browse component still imports useActionRunner**

```bash
grep -r "useActionRunner" apps/dashboard/components/browse/ apps/dashboard/app/\(views\)/browse/
```

Expected: no matches (browse components use `/api/cli/exec` directly now).

- [ ] **Step 2: Audit `/api/actions/oneshot` callers**

```bash
grep -rn "api/actions/oneshot" apps/dashboard/ --include="*.ts" --include="*.tsx"
```

Record each match: file, line, what it's doing.

- [ ] **Step 3: Migrate each caller to `/api/cli/exec`**

For each caller from Step 2, replace its `fetch('/api/actions/oneshot', ...)` block with the equivalent `/api/cli/exec` + SSE stream pattern from PromptCard (Task 7). The minimum diff per caller:

```ts
// Before:
const res = await fetch('/api/actions/oneshot', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ actionId, prompt, pageContext }),
});
const result = await res.json();

// After:
const res = await fetch('/api/cli/exec', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ prompt }),
});
const { execId } = await res.json() as { execId: string };
// (Then stream via /api/cli/exec/stream?id=… as in PromptCard.handleRun)
```

After all callers are migrated, verify zero remaining references:

```bash
grep -rn "api/actions/oneshot" apps/dashboard/ --include="*.ts" --include="*.tsx"
```

Expected: no output.

- [ ] **Step 4: Delete the old route**

```bash
rm -rf apps/dashboard/app/api/actions/oneshot
```

Verify the directory is gone:

```bash
ls apps/dashboard/app/api/actions/ 2>/dev/null
```

- [ ] **Step 5: Run full test suite**

```bash
cd apps/dashboard && npx jest --no-coverage 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 6: TypeScript full compile check**

```bash
cd apps/dashboard && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore(cleanup): remove legacy dispatch paths from browse, retire /api/actions/oneshot"
```

---

## Self-Review Notes

**Spec coverage:**
- ✅ Schema (file-based `prompts/` + `commands/` directories per Agent Skills standard) — Tasks 1–2
- ✅ `/api/cli/exec` print-mode route — Tasks 3–4
- ✅ SessionManager pre-warm + resume chain — Task 5 + Task 11 (dashboard-load wiring)
- ✅ Result card + Prompt card + multi-var support — Tasks 6–7
- ✅ Browse tabs (Prompts / Commands / Integration) — Tasks 8–9
- ✅ "Continue in session" route + global listener + collision toast — Task 10
- ✅ Migration script — Task 12
- ✅ Cleanup — Task 13

**Known gaps for follow-on (out of scope here):**
- `agentBubbleStore` cleanup for non-browse contexts (still used by hub feature pages)
- `get-skill-cli-help` MCP tool implementation — IntegrationTab falls back to "No CLI reference available" gracefully until the tool is added on the Python side
