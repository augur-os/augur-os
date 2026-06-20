export interface ExecEntry {
  prompt: string;
  cliId: string;
  startedAt: number;
  output: string[];
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
