/**
 * @jest-environment node
 */
import {
  formatFileSize,
  formatAge,
  matchesFileQuery,
} from "@/components/chat/utils";

describe("formatFileSize", () => {
  it('returns "0B" for 0 bytes', () => {
    expect(formatFileSize(0)).toBe("0B");
  });

  it('returns "500B" for 500 bytes', () => {
    expect(formatFileSize(500)).toBe("500B");
  });

  it('returns "1.0 KB" for 1024 bytes', () => {
    expect(formatFileSize(1024)).toBe("1.0 KB");
  });

  it('returns "1.5 KB" for 1536 bytes', () => {
    expect(formatFileSize(1536)).toBe("1.5 KB");
  });

  it('returns "1.0 MB" for 1048576 bytes', () => {
    expect(formatFileSize(1048576)).toBe("1.0 MB");
  });

  it('returns "2.5 MB" for 2621440 bytes', () => {
    expect(formatFileSize(2621440)).toBe("2.5 MB");
  });
});

describe("formatAge", () => {
  let nowSpy: jest.SpyInstance;
  const FIXED_NOW = 1_700_000_000_000;

  beforeEach(() => {
    nowSpy = jest.spyOn(Date, "now").mockReturnValue(FIXED_NOW);
  });

  afterEach(() => {
    nowSpy.mockRestore();
  });

  it('returns "0m ago" for Date.now()', () => {
    expect(formatAge(FIXED_NOW)).toBe("0m ago");
  });

  it('returns "5m ago" for 5 minutes ago', () => {
    expect(formatAge(FIXED_NOW - 5 * 60_000)).toBe("5m ago");
  });

  it('returns "2h ago" for 2 hours ago', () => {
    expect(formatAge(FIXED_NOW - 2 * 60 * 60_000)).toBe("2h ago");
  });

  it('returns "3d ago" for 3 days ago', () => {
    expect(formatAge(FIXED_NOW - 3 * 24 * 60 * 60_000)).toBe("3d ago");
  });
});

describe("matchesFileQuery", () => {
  const file = {
    name: "MyComponent.tsx",
    relativePath: "src/components/chat/MyComponent.tsx",
  };

  it("matches file name case-insensitively", () => {
    expect(matchesFileQuery(file, "MYCOMPONENT")).toBe(true);
  });

  it("matches relative path case-insensitively", () => {
    expect(matchesFileQuery(file, "SRC/COMPONENTS/CHAT")).toBe(true);
  });

  it("returns false for non-matching query", () => {
    expect(matchesFileQuery(file, "nonexistent")).toBe(false);
  });

  it("matches partial name", () => {
    expect(matchesFileQuery(file, "Comp")).toBe(true);
  });

  it("handles empty query (matches everything)", () => {
    expect(matchesFileQuery(file, "")).toBe(true);
  });
});
