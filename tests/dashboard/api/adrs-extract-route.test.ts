/**
 * @jest-environment node
 *
 * Tests for POST /api/adrs/extract — ADR-608 Phase 2.
 *
 * The route shells out to .github/scripts/adr_archive.py extract <ADR-NNN>
 * and appends a recent-views log line. We mock execFile and fs.promises so
 * the test never touches disk or runs Python.
 */

import { describe, it, expect, beforeEach, jest } from "@jest/globals";

type ExecFileCallback = (
  err: NodeJS.ErrnoException | null,
  stdout: string,
  stderr: string,
) => void;

const mockExecFile = jest.fn();
const mockMkdir = jest.fn(async () => undefined);
const mockAppendFile = jest.fn(async () => undefined);

jest.mock("child_process", () => ({
  execFile: (...args: unknown[]) => mockExecFile(...args),
}));

jest.mock("fs", () => ({
  promises: {
    mkdir: (...args: unknown[]) => mockMkdir(...args),
    appendFile: (...args: unknown[]) => mockAppendFile(...args),
  },
}));

jest.mock("@/lib/paths", () => ({
  AUGUR_ROOT: "/repo",
  AUGUR_PYTHON: "/usr/bin/python3",
  AUGUR_STATE_DIR: "/state",
}));

// Import the route AFTER the mocks are in place.
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { POST } = require("@/app/api/adrs/extract/route") as {
  POST: (req: Request) => Promise<Response>;
};

function makeReq(body: unknown): Request {
  return new Request("http://localhost/api/adrs/extract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

beforeEach(() => {
  mockExecFile.mockReset();
  mockMkdir.mockReset();
  mockMkdir.mockImplementation(async () => undefined);
  mockAppendFile.mockReset();
  mockAppendFile.mockImplementation(async () => undefined);
});

describe("POST /api/adrs/extract", () => {
  it("returns 400 when adr_number is missing", async () => {
    const res = await POST(makeReq({}));
    expect(res.status).toBe(400);
    const data = (await res.json()) as { error?: string };
    expect(data.error).toMatch(/adr_number/i);
    expect(mockExecFile).not.toHaveBeenCalled();
  });

  it("returns 400 when adr_number is malformed", async () => {
    const res = await POST(makeReq({ adr_number: "not-an-adr" }));
    expect(res.status).toBe(400);
    expect(mockExecFile).not.toHaveBeenCalled();
  });

  it("rejects non-JSON bodies with 400", async () => {
    const res = await POST(makeReq("not json {{{"));
    expect(res.status).toBe(400);
    expect(mockExecFile).not.toHaveBeenCalled();
  });

  it("shells out via execFile (no shell), returns the extracted path, and appends to recent-views", async () => {
    const extractedPath = "/state/adrs/extracted/ADR-042-foo.md";
    mockExecFile.mockImplementation(
      (
        cmd: string,
        args: string[],
        _opts: unknown,
        cb: ExecFileCallback,
      ) => {
        // Sanity: the route must invoke python3 with [scriptPath, "extract", "ADR-042"].
        expect(cmd).toBe("/usr/bin/python3");
        expect(args).toEqual([
          "/repo/.github/scripts/adr_archive.py",
          "extract",
          "ADR-042",
        ]);
        cb(null, `${extractedPath}\n`, "");
      },
    );

    const res = await POST(makeReq({ adr_number: "ADR-042" }));
    expect(res.status).toBe(200);
    const data = (await res.json()) as { path?: string };
    expect(data.path).toBe(extractedPath);
    expect(mockExecFile).toHaveBeenCalledTimes(1);

    expect(mockMkdir).toHaveBeenCalledWith("/state/adrs", { recursive: true });
    expect(mockAppendFile).toHaveBeenCalledTimes(1);
    const appendArgs = mockAppendFile.mock.calls[0] as unknown as [
      string,
      string,
      string,
    ];
    expect(appendArgs[0]).toBe("/state/adrs/recent-views.jsonl");
    const line = JSON.parse(appendArgs[1].trim()) as Record<string, unknown>;
    expect(line.adr_number).toBe("ADR-042");
    expect(line.archived).toBe(true);
    expect(typeof line.ts).toBe("string");
  });

  it("normalises bare numeric adr_number to padded ADR-NNN before exec", async () => {
    mockExecFile.mockImplementation(
      (
        _cmd: string,
        args: string[],
        _opts: unknown,
        cb: ExecFileCallback,
      ) => {
        expect(args[2]).toBe("ADR-007");
        cb(null, "/tmp/extracted/ADR-007.md\n", "");
      },
    );

    const res = await POST(makeReq({ adr_number: "7" }));
    expect(res.status).toBe(200);
  });

  it("returns 500 with stderr when the extract script fails", async () => {
    mockExecFile.mockImplementation(
      (
        _cmd: string,
        _args: string[],
        _opts: unknown,
        cb: ExecFileCallback,
      ) => {
        const err = new Error("non-zero exit") as NodeJS.ErrnoException & {
          stderr?: string;
        };
        cb(err, "", "ADR-999 not found in archive ledger");
      },
    );

    const res = await POST(makeReq({ adr_number: "ADR-999" }));
    expect(res.status).toBe(500);
    const data = (await res.json()) as { error?: string };
    expect(data.error).toContain("ADR-999");
  });

  it("does not fail the request when recent-views logging throws", async () => {
    mockExecFile.mockImplementation(
      (
        _cmd: string,
        _args: string[],
        _opts: unknown,
        cb: ExecFileCallback,
      ) => {
        cb(null, "/tmp/extracted/ADR-042.md\n", "");
      },
    );
    mockAppendFile.mockImplementation(async () => {
      throw new Error("disk full");
    });

    const res = await POST(makeReq({ adr_number: "ADR-042" }));
    expect(res.status).toBe(200);
    const data = (await res.json()) as { path?: string };
    expect(data.path).toBe("/tmp/extracted/ADR-042.md");
  });
});
