/** @jest-environment node */

import { getRawReplayWindow, type PtyEntry } from "@/app/api/cli/pty-setup";

function makeEntry(overrides: Partial<PtyEntry> = {}): PtyEntry {
  return {
    ptyProcess: {} as never,
    startTime: Date.now(),
    outputBuffer: [],
    rawBuffer: [],
    rawCursorStart: 0,
    rawCursorEnd: 0,
    exited: false,
    exitCode: null,
    detached: false,
    detachedAt: null,
    detachTimer: null,
    detachRawIndex: null,
    ...overrides,
  };
}

describe("getRawReplayWindow", () => {
  it("replays only unseen raw chunks when the client provides a current cursor", () => {
    const entry = makeEntry({
      rawBuffer: ["first", "second", "third"],
      rawCursorStart: 0,
      rawCursorEnd: 3,
    });

    const replay = getRawReplayWindow(entry, 2);

    expect(replay).toEqual({
      chunks: ["third"],
      cursorEnd: 3,
      reset: false,
    });
  });

  it("asks the client to reset if its cursor predates the retained buffer", () => {
    const entry = makeEntry({
      rawBuffer: ["third", "fourth"],
      rawCursorStart: 2,
      rawCursorEnd: 4,
    });

    const replay = getRawReplayWindow(entry, 1);

    expect(replay).toEqual({
      chunks: ["third", "fourth"],
      cursorEnd: 4,
      reset: true,
    });
  });
});
