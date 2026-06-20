/**
 * @jest-environment node
 */
import fs from "fs";
import os from "os";
import path from "path";

import { generateCustomBlockRegistry } from "@/scripts/block-registry-gen";

describe("generateCustomBlockRegistry", () => {
  it("warns about generated private-vault custom blocks using the actual SKILL.md path", async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "augur-custom-blocks-"));
    const scriptsDir = path.join(tempDir, "apps", "dashboard", "scripts");
    const privateRoot = `${tempDir}-private-vault`;
    const privateSkillMd = path.join(
      privateRoot,
      "skills",
      "apple",
      "SKILL.md",
    );
    fs.mkdirSync(scriptsDir, { recursive: true });
    fs.mkdirSync(path.dirname(privateSkillMd), { recursive: true });

    const warnSpy = jest
      .spyOn(console, "warn")
      .mockImplementation(() => undefined);
    try {
      await generateCustomBlockRegistry(
        [
          {
            pageId: "apple",
            routePath: "/life/apple",
            skill: "apple",
            bundle: "life",
            hubId: "life",
            isOwner: false,
            overrides: {},
            sourceConfigPath: privateSkillMd,
            generatedConfig: {
              title: "Apple",
              icon: "Apple",
              hub: "life",
              route: "apple",
              blocks: [{ type: "custom", component: "PrivateApplePanel" }],
            },
          },
        ],
        scriptsDir,
      );

      const warnings = warnSpy.mock.calls.map((call) => String(call[0]));
      expect(warnings.some((warning) => warning.includes(privateSkillMd))).toBe(
        true,
      );
    } finally {
      warnSpy.mockRestore();
      fs.rmSync(tempDir, { recursive: true, force: true });
      fs.rmSync(privateRoot, { recursive: true, force: true });
    }
  });
});
