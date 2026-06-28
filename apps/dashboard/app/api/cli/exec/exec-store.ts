export interface ExecEntry {
  prompt: string;
  cliId: string;
  startedAt: number;
  output: string[];
  outputBytes?: number;
  done: boolean;
  answer: string | null;
  sessionId: string | null;
  error: string | null;
  kill?: () => void;
  cleanupTimer?: ReturnType<typeof setTimeout> | null;
}

const EXEC_STORE_KEY = Symbol.for("augur.cli.execStore");
const proc = process as unknown as {
  [EXEC_STORE_KEY]?: Map<string, ExecEntry>;
};

if (!proc[EXEC_STORE_KEY]) {
  proc[EXEC_STORE_KEY] = new Map<string, ExecEntry>();
}

const store = proc[EXEC_STORE_KEY]!;

export const execStore = {
  set(execId: string, entry: ExecEntry): void {
    store.set(execId, entry);
  },

  get(execId: string): ExecEntry | undefined {
    return store.get(execId);
  },

  delete(execId: string): boolean {
    const entry = store.get(execId);
    if (entry?.cleanupTimer) {
      clearTimeout(entry.cleanupTimer);
      entry.cleanupTimer = null;
    }
    return store.delete(execId);
  },
};

export const MAX_EXEC_OUTPUT_LINES = 2000;
export const MAX_EXEC_OUTPUT_BYTES = 2 * 1024 * 1024; // 2 MB

// Ring-buffered append: keeps at most MAX_EXEC_OUTPUT_LINES recent lines and
// at most MAX_EXEC_OUTPUT_BYTES total, dropping oldest. Prevents a verbose CLI
// run from growing entry.output without bound (the root cause of the OOM).
export function pushBoundedOutput(entry: ExecEntry, line: string): void {
  entry.output.push(line);
  entry.outputBytes = (entry.outputBytes ?? 0) + Buffer.byteLength(line);
  if (entry.output.length > MAX_EXEC_OUTPUT_LINES) {
    const drop = entry.output.length - MAX_EXEC_OUTPUT_LINES;
    for (let i = 0; i < drop; i++) {
      const removed = entry.output.shift();
      if (removed !== undefined) entry.outputBytes -= Buffer.byteLength(removed);
    }
  }
  while (entry.outputBytes > MAX_EXEC_OUTPUT_BYTES && entry.output.length > 1) {
    const removed = entry.output.shift();
    if (removed === undefined) break;
    entry.outputBytes -= Buffer.byteLength(removed);
  }
}
