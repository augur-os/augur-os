import { randomUUID } from "crypto";
import { NextRequest, NextResponse } from "next/server";
import {
  AUGUR_ROOT,
  buildCliSpawnEnv,
  getCliAgentsConfig,
  isNonEmptyString,
  resolveDefaultCliId,
  resolveSpawnCommand,
} from "../cli-config";
// @spawn-exempt: print-mode native AI client handoff uses the configured CLI argv through a PTY.
import { pty } from "../pty-setup";
import { execStore, pushBoundedOutput, type ExecEntry } from "./exec-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const EXEC_ORPHAN_CLEANUP_MS = 120_000;

interface ExecRequestBody {
  prompt?: unknown;
}

interface PtyExitEvent {
  exitCode?: number;
}

interface ExecPtyProcess {
  onData(callback: (chunk: string) => void): void;
  onExit(callback: (event: PtyExitEvent) => void): void;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.length > 0 && value.every(isNonEmptyString);
}

function resolveCwd(config: Record<string, unknown>): string {
  const cwd = config.cwd;
  if (!isNonEmptyString(cwd) || cwd === ".") {
    return AUGUR_ROOT;
  }
  return cwd;
}

function commandBasename(command: string): string {
  return command.split(/[\\/]/).pop()?.replace(/\.(cmd|exe)$/i, "").toLowerCase() || command.toLowerCase();
}

function normalizePrintCommand(cliId: string, printCmd: string[]): string[] {
  const argv = [...printCmd];
  const isClaude =
    cliId.trim().toLowerCase() === "claude" ||
    commandBasename(argv[0] || "") === "claude";
  if (
    isClaude &&
    argv.includes("--output-format") &&
    argv.includes("stream-json") &&
    !argv.includes("--verbose")
  ) {
    argv.push("--verbose");
  }
  return argv;
}

function readCodexAnswer(content: unknown): string | undefined {
  if (!Array.isArray(content)) return undefined;

  const text = content
    .map((item) => {
      if (
        item &&
        typeof item === "object" &&
        (item as { type?: unknown }).type === "text" &&
        isNonEmptyString((item as { text?: unknown }).text)
      ) {
        return (item as { text: string }).text;
      }
      return "";
    })
    .filter(Boolean)
    .join("");

  return text || undefined;
}

function applyJsonEvent(entry: ExecEntry, line: string): void {
  try {
    const event = JSON.parse(line) as Record<string, unknown>;

    if (isNonEmptyString(event.session_id)) {
      entry.sessionId = event.session_id;
    }

    if (event.type === "result" && isNonEmptyString(event.result)) {
      entry.answer = event.result;
      return;
    }

    if (event.type === "turn.completed") {
      const answer = readCodexAnswer(event.content);
      if (answer) {
        entry.answer = answer;
      }
    }
  } catch {
    // Ignore malformed JSON-looking lines; raw output is retained for inspection.
  }
}

function attachExecHandlers(entry: ExecEntry, ptyProcess: ExecPtyProcess): void {
  let pending = "";

  ptyProcess.onData((chunk: string) => {
    pending += chunk;
    const lines = pending.split(/\r?\n/);
    pending = lines.pop() || "";

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line.startsWith("{") || !line.endsWith("}")) continue;

      pushBoundedOutput(entry, line);
      applyJsonEvent(entry, line);
    }
  });

  ptyProcess.onExit((event: PtyExitEvent) => {
    if (pending.trim().startsWith("{") && pending.trim().endsWith("}")) {
      const line = pending.trim();
      pushBoundedOutput(entry, line);
      applyJsonEvent(entry, line);
    }

    entry.done = true;
    const exitCode = typeof event.exitCode === "number" ? event.exitCode : 0;
    if (exitCode !== 0 && !entry.answer) {
      entry.error = `CLI exited with code ${exitCode}`;
    }
  });
}

export async function POST(request: NextRequest) {
  if (request.headers.get("x-remote-user") === "true") {
    return NextResponse.json(
      { error: "Print-mode CLI execution is not available for remote users." },
      { status: 403 },
    );
  }

  let body: ExecRequestBody;
  try {
    body = (await request.json()) as ExecRequestBody;
  } catch {
    return NextResponse.json(
      { error: "Request body must be valid JSON with a prompt." },
      { status: 400 },
    );
  }

  if (!isNonEmptyString(body.prompt)) {
    return NextResponse.json(
      { error: "prompt is required." },
      { status: 400 },
    );
  }

  try {
    const agents = getCliAgentsConfig();
    const cliId = resolveDefaultCliId(agents);
    const config = agents[cliId] as Record<string, unknown> | undefined;

    if (!config) {
      return NextResponse.json(
        { error: `CLI '${cliId}' is not configured.` },
        { status: 400 },
      );
    }

    const printCmd = config.print_cmd;
    if (!isStringArray(printCmd)) {
      return NextResponse.json(
        { error: `CLI '${cliId}' does not define a print_cmd.` },
        { status: 400 },
      );
    }

    const argv = [...normalizePrintCommand(cliId, printCmd), body.prompt];
    const execId = randomUUID();
    const entry: ExecEntry = {
      prompt: body.prompt,
      cliId,
      startedAt: Date.now(),
      output: [],
      done: false,
      answer: null,
      sessionId: null,
      error: null,
      cleanupTimer: null,
    };
    execStore.set(execId, entry);

    try {
      const ptyProcess = pty.spawn(resolveSpawnCommand(argv[0]), argv.slice(1), {
        name: "xterm-256color",
        cols: 200,
        rows: 50,
        cwd: resolveCwd(config),
        env: buildCliSpawnEnv(config, undefined, "dark"),
      });

      entry.kill = () => ptyProcess.kill();
      attachExecHandlers(entry, ptyProcess);
      entry.cleanupTimer = setTimeout(() => {
        const latest = execStore.get(execId);
        if (!latest) return;
        if (!latest.done) {
          try {
            latest.kill?.();
          } catch {
            // Best effort: the process may already have exited.
          }
        }
        execStore.delete(execId);
      }, EXEC_ORPHAN_CLEANUP_MS);
      (entry.cleanupTimer as { unref?: () => void }).unref?.();
    } catch (error) {
      execStore.delete(execId);
      const message = error instanceof Error ? error.message : "Failed to spawn CLI.";
      return NextResponse.json({ error: message }, { status: 500 });
    }

    return NextResponse.json({ execId });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Internal error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
