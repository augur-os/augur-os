/**
 * @jest-environment node
 */
import fs from "fs";
import path from "path";

const ROOT = path.resolve(__dirname, "../../../../../");

const BRAIN_PAGE_FILES = [
  "apps/dashboard/features/pages/workspace/overview/BrainOverviewHome.tsx",
  "apps/dashboard/features/pages/workspace/memory/page.tsx",
  "apps/dashboard/features/pages/workspace/daily-logs/page.tsx",
  "apps/dashboard/features/pages/workspace/profile/page.tsx",
  "apps/dashboard/features/pages/workspace/agents/page.tsx",
  "apps/dashboard/components/plugin/ConfigPage.tsx",
];

describe("Brain page heading contract", () => {
  it("keeps page content below the hub-owned h1", () => {
    for (const relativePath of BRAIN_PAGE_FILES) {
      const source = fs.readFileSync(path.join(ROOT, relativePath), "utf8");
      expect(source).not.toMatch(/<h1[\s>]/);
    }
  });

  it("reserves mobile bottom space for fixed floating controls", () => {
    const source = fs.readFileSync(
      path.join(ROOT, "apps/dashboard/app/layout.tsx"),
      "utf8",
    );

    expect(source).toContain("pb-[calc(6rem+env(safe-area-inset-bottom))]");
  });

  it("seeds the light theme before the first dashboard paint", () => {
    const source = fs.readFileSync(
      path.join(ROOT, "apps/dashboard/app/layout.tsx"),
      "utf8",
    );

    expect(source).toContain('data-theme="futuristic-light"');
    expect(source).toContain('data-mode="light"');
    expect(source).toContain('colorScheme: "light"');
    expect(source).toContain("dangerouslySetInnerHTML");
  });
});
