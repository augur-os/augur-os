/**
 * @jest-environment node
 */
import { describe, it, expect } from "@jest/globals";
import { pushBoundedOutput, MAX_EXEC_OUTPUT_LINES, MAX_EXEC_OUTPUT_BYTES, type ExecEntry } from "@/app/api/cli/exec/exec-store";

function makeEntry(): ExecEntry {
  return { prompt: "", cliId: "", startedAt: 0, output: [], done: false, answer: null, sessionId: null, error: null };
}

describe("pushBoundedOutput", () => {
  it("caps the number of retained lines", () => {
    const e = makeEntry();
    for (let i = 0; i < MAX_EXEC_OUTPUT_LINES + 5000; i++) pushBoundedOutput(e, `line ${i}`);
    expect(e.output.length).toBeLessThanOrEqual(MAX_EXEC_OUTPUT_LINES);
    // keeps the most recent lines (ring buffer)
    expect(e.output[e.output.length - 1]).toContain(`${MAX_EXEC_OUTPUT_LINES + 5000 - 1}`);
  });

  it("caps total bytes retained", () => {
    const e = makeEntry();
    const big = "x".repeat(100_000); // 100 KB per line
    for (let i = 0; i < 100; i++) pushBoundedOutput(e, big); // 10 MB pushed
    const bytes = e.output.reduce((n, l) => n + Buffer.byteLength(l), 0);
    expect(bytes).toBeLessThanOrEqual(MAX_EXEC_OUTPUT_BYTES);
  });
});
