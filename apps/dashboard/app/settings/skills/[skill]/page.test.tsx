import Page from "./page";
import { readFile } from "fs/promises";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => "/",
  useSearchParams: () => ({ get: jest.fn() }),
}));

// Mock server side utilities
jest.mock("@/lib/server/skillsLookup", () => ({
  resolveSkillInfo: jest.fn().mockResolvedValue({
    path: "test/path",
    canonicalId: "test-skill",
    source: "skill-package",
  }),
}));
jest.mock("@/lib/server/repo", () => ({
  getRepoRoot: jest.fn().mockReturnValue("/mock/root"),
}));
jest.mock("@/lib/server/skillsState", () => ({
  CORE_SKILLS: new Set(["test-skill"]),
  readDisabledSkills: jest.fn().mockResolvedValue(new Set()),
}));
jest.mock("@/lib/paths", () => ({
  getSkillAugurDataPath: jest.fn().mockReturnValue("/mock/vault/test-skill"),
}));
jest.mock("fs/promises", () => ({
  stat: jest.fn().mockResolvedValue({ isDirectory: () => true }),
  readFile: jest.fn().mockResolvedValue("# Test Skill\n\nBody content"),
}));

// Mock API calls if possible (generic)
global.fetch = jest.fn(
  () =>
    Promise.resolve({
      json: () => Promise.resolve({ success: true, data: [] }),
      ok: true,
    }) as Promise<Response>,
);

describe("Page (RSC)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders without crashing", async () => {
    const result = await Page({
      params: { skill: "test-skill" },
    });
    expect(result).toBeDefined();
  });

  it("loads migrated augur README fallback", async () => {
    const mockReadFile = readFile as jest.MockedFunction<typeof readFile>;
    mockReadFile.mockImplementation(async (target) => {
      const filePath = String(target);
      if (filePath.endsWith("/augur/README.md")) {
        return "# Generated README\n\nSkill body";
      }
      throw new Error("missing");
    });

    const result = await Page({
      params: { skill: "test-skill" },
    });

    expect(result).toBeDefined();
    expect(mockReadFile).toHaveBeenCalledWith(
      "/mock/root/plugins/test/path/skill-package/SKILL.md",
      "utf8",
    );
    expect(mockReadFile).toHaveBeenCalledWith(
      "/mock/root/plugins/test/path/augur/README.md",
      "utf8",
    );
  });
});
