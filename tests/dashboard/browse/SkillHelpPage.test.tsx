/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockSkillDetailTabs = jest.fn(({ skillLabel }: { skillLabel: string }) => (
  <div>Tabs {skillLabel}</div>
));

jest.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

jest.mock("@/components/DisabledSkillPage", () => ({
  __esModule: true,
  default: ({ title }: { title: string }) => <div>Disabled {title}</div>,
}));

jest.mock("@/components/ui/Button", () => ({
  Button: ({ children }: { children: React.ReactNode }) => <button>{children}</button>,
}));

jest.mock("@/components/ui/Badge", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

jest.mock("@/components/plugin/ConfigPage", () => ({
  ConfigPage: ({ skillId }: { skillId: string }) => <div>Config {skillId}</div>,
}));

jest.mock("@/components/browse/SkillDetailTabs", () => ({
  SkillDetailTabs: mockSkillDetailTabs,
}));

jest.mock("@/lib/server/skillsState", () => ({
  CORE_SKILLS: new Set<string>(),
  readDisabledSkills: jest.fn().mockResolvedValue(new Set<string>()),
}));

jest.mock("@/lib/server/skillsLookup", () => ({
  parseSkillSlug: (value: string) => ({ name: value, sourceRoot: null }),
  resolveSkillInfo: jest.fn().mockResolvedValue({
    path: "ai",
    canonicalId: "ai",
  }),
  normalizeSlug: (value: string) => value,
  parseSkillSlug: (raw: string) => ({ name: raw, sourceRoot: null, hadPrefix: false }),
  readSkillMeta: jest.fn().mockResolvedValue({
    title: "AI",
    description: "AI inbox triage",
    mcpTools: ["gmail-search"],
    prompts: [{ id: "draft", label: "Draft", prompt: "Draft the answer" }],
    commands: [{ id: "ai", label: "/ai", command: "/ai" }],
  }),
}));

jest.mock("@/lib/blocks/build-default-page-config", () => ({
  buildDefaultPageConfig: jest.fn().mockReturnValue({
    title: "AI",
  }),
}));

describe("SkillHelpPage", () => {
  beforeEach(() => {
    mockSkillDetailTabs.mockClear();
  });

  it("renders a primary heading for the skill", async () => {
    const mod = await import("@/app/(views)/browse/[skill]/page");
    const ui = await mod.default({
      params: { skill: "ai" } as any,
    });

    render(ui);

    expect(screen.getByRole("heading", { name: "AI" })).toBeInTheDocument();
  });

  it("passes generated capability profile sections to skill detail tabs", async () => {
    const mod = await import("@/app/(views)/browse/[skill]/page");
    const ui = await mod.default({
      params: { skill: "ai" } as any,
    });

    render(ui);

    expect(mockSkillDetailTabs).toHaveBeenCalledWith(
      expect.objectContaining({
        capabilityProfileSections: expect.arrayContaining([
          expect.objectContaining({
            id: "summary",
            items: expect.arrayContaining([
              expect.objectContaining({
                label: "ai",
                description: "AI inbox triage",
              }),
            ]),
          }),
          expect.objectContaining({
            id: "tools",
            items: expect.arrayContaining([
              expect.objectContaining({ label: "gmail-search" }),
            ]),
          }),
          expect.objectContaining({
            id: "prompts",
            items: expect.arrayContaining([
              expect.objectContaining({
                label: "Draft",
                description: "Draft the answer",
              }),
            ]),
          }),
          expect.objectContaining({
            id: "commands",
            items: expect.arrayContaining([
              expect.objectContaining({
                label: "/ai",
                description: "/ai",
              }),
            ]),
          }),
        ]),
      }),
      undefined,
    );
  });

});
