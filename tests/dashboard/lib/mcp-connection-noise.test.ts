/**
 * @jest-environment node
 */

import { isNoisyServerStderr } from "@/lib/mcp/connection";

describe("MCPBridge stderr noise filtering", () => {
  it("filters non-actionable unified indexer progress", () => {
    expect(isNoisyServerStderr("Chunks pending contextualization: 7842")).toBe(
      true,
    );
    expect(isNoisyServerStderr("Contextualized 12 chunks via LLM")).toBe(true);
    expect(isNoisyServerStderr("Generated index.md (100 entries, 6 hubs)")).toBe(
      true,
    );
  });

  it("keeps actionable stderr visible", () => {
    expect(
      isNoisyServerStderr("Warning: contextualization skipped: missing model"),
    ).toBe(false);
    expect(isNoisyServerStderr("Traceback (most recent call last):")).toBe(
      false,
    );
  });
});
