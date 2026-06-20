/**
 * @jest-environment node
 */
import { describe, it, expect } from "@jest/globals";
import {
  isBlockState,
  isWebMCPError,
  type BlockState,
  type WebMCPError,
} from "@/lib/webmcp/types";

describe("WebMCP types", () => {
  describe("isBlockState", () => {
    it("validates a complete BlockState", () => {
      const state: BlockState = {
        blockId: "career:pipeline",
        instanceId: "inst-1",
        type: "data-table",
        mounted: true,
        renderState: "ready",
        config: { stage_filter: "active" },
        data: [{ company: "Acme" }],
        lastUpdated: Date.now(),
      };
      expect(isBlockState(state)).toBe(true);
    });

    it("rejects missing blockId", () => {
      expect(isBlockState({ instanceId: "x" })).toBe(false);
    });

    it("rejects invalid renderState", () => {
      expect(
        isBlockState({
          blockId: "x",
          instanceId: "y",
          type: "stat-card",
          mounted: true,
          renderState: "invalid",
          config: {},
          data: null,
          lastUpdated: 0,
        }),
      ).toBe(false);
    });
  });

  describe("isWebMCPError", () => {
    it("validates an error shape", () => {
      const err: WebMCPError = {
        error: true,
        code: "NOT_FOUND",
        message: "Block not found",
        blockId: "x:y",
      };
      expect(isWebMCPError(err)).toBe(true);
    });

    it("rejects non-error objects", () => {
      expect(isWebMCPError({ success: true })).toBe(false);
    });
  });
});
