/**
 * @jest-environment node
 */

import path from "path";

describe("validate-nav-alignment", () => {
  it("passes against the current plugin bundle layout", () => {
    const repoRoot = path.resolve(__dirname, "../../..");
    const { spawnSync } = jest.requireActual("child_process") as typeof import("child_process");
    const result = spawnSync(
      "node",
      ["apps/dashboard/scripts/dist/validate-nav-alignment.mjs"],
      {
        cwd: repoRoot,
        encoding: "utf8",
      },
    );

    expect(result.status).toBe(0);
  });
});
