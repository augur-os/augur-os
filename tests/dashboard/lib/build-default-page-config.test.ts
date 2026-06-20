/**
 * @jest-environment node
 */

import { buildDefaultPageConfig } from "@/lib/blocks/build-default-page-config";

describe("buildDefaultPageConfig", () => {
  it("does not auto-generate action buttons for update tools that need inputs", () => {
    const config = buildDefaultPageConfig("daemon", {
      title: "Daemon",
      hub: "command",
      mcpTools: [
        "get-daemon-loop-history",
        "update-notification-preferences",
      ],
    });

    expect(config.blocks.some((block) => block.type === "action-bar")).toBe(false);
    expect(config.blocks).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: "metrics-dashboard",
          title: "Daemon Loop History",
        }),
      ]),
    );
  });

  it("still auto-generates one-click actions for run and refresh tools", () => {
    const config = buildDefaultPageConfig("daemon", {
      title: "Daemon",
      hub: "command",
      mcpTools: [
        "run-loop-cycle",
        "refresh-loop-status",
      ],
    });

    expect(config.blocks).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: "action-bar",
          actions: [
            expect.objectContaining({ mcp_tool: "run-loop-cycle", dispatch: "fire" }),
            expect.objectContaining({ mcp_tool: "refresh-loop-status", dispatch: "fire" }),
          ],
        }),
      ]),
    );
  });
});
