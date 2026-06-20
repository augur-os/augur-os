/**
 * @jest-environment node
 */

import fs from "fs/promises";
import os from "os";
import path from "path";

import { assembleToolConfig } from "../../../apps/dashboard/scripts/mount/tool-assembly";

const LEGACY_WIKI_COMPILE_TOOLS = [
  "wiki-compile-backlog",
  "wiki-compile-preview",
  "wiki-compile-batch",
  "wiki-compile-selected",
  "wiki-compile-scope",
  "wiki-compile-status",
  "wiki-compile-cycle",
];

describe("assembleToolConfig", () => {
  it("grants the wiki maintenance page the operational wiki MCP tools", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-tool-assembly-"));

    const assembled = await assembleToolConfig(repoRoot);

    expect(assembled.tool_groups.WIKI_MAINTENANCE).toEqual(
      expect.arrayContaining([
        "wiki-read",
        "wiki-write",
        "wiki-list",
        "wiki-tags",
        "wiki-log",
        "wiki-search",
        "wiki-rebuild",
        "wiki-update",
        "wiki-apply-concept-batch",
        "wiki-rewrite-candidates",
        "wiki-report-data",
      ]),
    );
    expect(assembled.tool_groups.WIKI_MAINTENANCE).toEqual(
      expect.not.arrayContaining(LEGACY_WIKI_COMPILE_TOOLS),
    );

    await fs.rm(repoRoot, { recursive: true, force: true });
  });

  it("grants the brain overview page the wiki maintenance group when it surfaces wiki status", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-tool-assembly-brain-"));

    const assembled = await assembleToolConfig(repoRoot);

    expect(assembled.pages["/brain"]?.groups).toEqual(
      expect.arrayContaining(["WIKI_MAINTENANCE"]),
    );

    await fs.rm(repoRoot, { recursive: true, force: true });
  });
});
