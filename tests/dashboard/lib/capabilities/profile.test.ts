import { buildCapabilityProfileSections } from "@/lib/capabilities/profile";

describe("buildCapabilityProfileSections", () => {
  it("creates sections from tools, actions, prompts, commands, integrations, and health", () => {
    const sections = buildCapabilityProfileSections({
      skillId: "gmail-triage",
      description: "Triage Gmail messages.",
      tools: [{ name: "gmail-search", description: "Search Gmail" }],
      actions: [{ id: "triage", label: "Triage Inbox", description: "Rank inbox", dispatch: "mcp" }],
      prompts: [{ id: "reply-draft", label: "Draft Reply", prompt: "Draft a reply" }],
      commands: [{ id: "gmail-triage", label: "/gmail-triage", command: "/gmail-triage" }],
      integrations: [{ id: "gmail", label: "Gmail", status: "connected" }],
      health: { status: "healthy", errors24h: 2 },
    });

    expect(sections.map((section) => section.id)).toEqual([
      "summary",
      "tools",
      "actions",
      "prompts",
      "commands",
      "integrations",
      "health",
    ]);
    expect(sections.find((section) => section.id === "tools")?.items).toEqual([
      { label: "gmail-search", description: "Search Gmail" },
    ]);
    expect(sections.find((section) => section.id === "actions")?.items).toEqual([
      {
        label: "Triage Inbox",
        description: "Rank inbox",
        metadata: { dispatch: "mcp" },
      },
    ]);
    expect(sections.find((section) => section.id === "prompts")?.items).toEqual([
      { label: "Draft Reply", description: "Draft a reply" },
    ]);
    expect(sections.find((section) => section.id === "commands")?.items).toEqual([
      { label: "/gmail-triage", description: "/gmail-triage" },
    ]);
    expect(sections.find((section) => section.id === "integrations")?.items).toEqual([
      {
        label: "Gmail",
        description: "connected",
        metadata: { id: "gmail" },
      },
    ]);
    expect(sections.find((section) => section.id === "docs")).toBeUndefined();
    expect(sections.find((section) => section.id === "health")?.items).toEqual([
      {
        label: "healthy",
        metadata: { errors24h: "2" },
      },
    ]);
  });

  it("omits empty sections but keeps summary", () => {
    const sections = buildCapabilityProfileSections({
      skillId: "empty",
      description: "Empty skill",
    });

    expect(sections).toEqual([
      {
        id: "summary",
        title: "Summary",
        kind: "summary",
        items: [{ label: "empty", description: "Empty skill" }],
      },
    ]);
  });
});
